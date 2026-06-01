"""Ingestion LangGraph 조립 + 그래프 호출 래퍼 [Pipeline].

--------------------------------------------------
작성자 : 최태성
작성목적 : feature6 Phase 4 — 표준 PageObject 를 받아 본문 + 첨부 청크를 적재까지 가는
          단일 페이지 Ingestion LangGraph. 설계서 §3.1 Big Picture 정합으로 analyze →
          chunk → embed_upsert 3 stage 를 한 위치에서 wiring 한다. Agent 노드(문서
          분석기)는 stub 으로 두고, 각 단계 종료 시 `IngestionJobsRepository.record`
          로 db-schema §2.3 ingestion_jobs 에 기록한다 (`docs/rag-pipeline-design.md`
          §3, `docs/db-schema.md` §2.3, `app/CLAUDE.md` §2).
작성일 : 2026-05-18
변경사항 내역 (날짜, 변경목적, 변경내용 순)
  - 2026-05-18, 최초 작성, feature6 Phase 4 — IngestionGraphDeps + build_ingestion_graph
    + run_ingestion + 3 노드 (analyze_document / chunk_documents / embed_upsert).
    chunk_attachment 는 deps 에 callable 로 주입 가능 (파일 시스템 의존성 회피).
    PDF/CSV (feature4-B 대기) 의 ValueError 는 catch 후 잡 기록 + 본문은 정상 진행.
--------------------------------------------------
[호환성]
  - Python 3.11.x, LangGraph 0.2.x
  - 외부 의존성: dense/sparse 임베더·QdrantPoolStore·EmbeddingCache·ChunkTextLookup·
    IngestionJobsRepository 는 모두 호출자가 주입한다 (`app/CLAUDE.md` §8).
  - NOTE: 본 그래프는 단일 페이지 단위로 동작한다. 여러 페이지 일괄 처리(Full Crawl /
          Delta Sync)는 본 그래프의 호출자(RabbitMQ Worker, 운영) 책임이다. 삭제
          동기화(Reconciliation)는 별도 함수(`app/ingestion/sync.py`)가 담당한다.
--------------------------------------------------
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph

from app.ingestion.attachment_analyzer import analyze_attachment
from app.ingestion.chunker import chunk_attachment, chunk_page
from app.ingestion.embedder.base import DenseEmbedder, SparseEmbedder
from app.ingestion.indexer import index_chunks
from app.pipeline.stubs import document_analyzer_stub
from app.schemas.chunk import Chunk
from app.schemas.enums import IngestionStage, IngestionStatus
from app.schemas.page_object import Attachment, PageObject
from app.schemas.rag_state import IngestionState
from app.storage.chunk_lookup import ChunkTextLookup, FakeChunkTextLookup
from app.storage.jobs import (
    FakeIngestionJobsRepository,
    IngestionJobRecord,
    IngestionJobsRepository,
)
from app.storage.mongo_cache import EmbeddingCache
from app.storage.qdrant_client import QdrantPoolStore

# 노드 시그니처 — (IngestionState) -> IngestionState.
IngestionNode = Callable[[IngestionState], IngestionState]

# chunk_attachment 시그니처 — 파일 시스템 의존성을 갖는 함수라 deps 주입으로 테스트 가능.
ChunkAttachmentFn = Callable[..., list[Chunk]]


@dataclass(slots=True)
class IngestionGraphDeps:
    """Ingestion 그래프 의존성 묶음 — 그래프 빌더가 노드에 wiring 한다.

    Pipeline / Storage 의존성(Phase 1·2·3 모듈)은 모두 호출자가 주입한다. Agent 노드
    (문서 분석기)는 stub 기본값. Agent 코드 전달 시 ``document_analyzer_node`` 만
    교체하면 그래프는 변경 없이 동작한다.
    """

    # --- Pipeline / Storage 의존성 ---
    dense_embedder: DenseEmbedder
    sparse_embedder: SparseEmbedder
    store: QdrantPoolStore
    cache: EmbeddingCache
    chunk_lookup: ChunkTextLookup = field(default_factory=FakeChunkTextLookup)
    jobs: IngestionJobsRepository = field(default_factory=FakeIngestionJobsRepository)

    # --- Agent 노드 — 기본값은 stub. 실 Agent 코드 전달 시 교체. ---
    document_analyzer_node: IngestionNode = field(default=document_analyzer_stub)

    # --- chunk_attachment 주입 — 테스트에서 파일 시스템 의존성 회피용. ---
    chunk_attachment_fn: ChunkAttachmentFn = field(default=chunk_attachment)


def build_ingestion_graph(deps: IngestionGraphDeps) -> Any:
    """Ingestion LangGraph StateGraph 를 조립해 컴파일된 그래프를 반환한다.

    그래프 구조 (설계서 §3.1 Big Picture, stage 정합):
        analyze_document → chunk_documents → embed_upsert → END
            (ANALYZE)         (CHUNK)             (UPSERT)
            jobs.record       jobs.record         jobs.record

    Args:
        deps: 그래프 노드 wiring 에 필요한 의존성 묶음.

    Returns:
        LangGraph CompiledGraph (`graph.invoke(state)` 로 실행).
    """
    builder = StateGraph(IngestionState)

    # 노드 등록 — 외부 의존성은 functools.partial 로 wiring.
    # NOTE: 노드명은 IngestionState 필드명(page/doc_type/chunks/stage/status/error)과
    # 네임스페이스를 공유한다 (LangGraph 1.x 제약). 모든 노드명이 필드명과 다르도록
    # 확인 — 'analyze_document' / 'chunk_documents' / 'embed_upsert'.
    builder.add_node("analyze_document", partial(_analyze_document_node, deps=deps))
    builder.add_node("chunk_documents", partial(_chunk_documents_node, deps=deps))
    builder.add_node("embed_upsert", partial(_embed_upsert_node, deps=deps))

    builder.set_entry_point("analyze_document")
    builder.add_edge("analyze_document", "chunk_documents")
    builder.add_edge("chunk_documents", "embed_upsert")
    builder.add_edge("embed_upsert", END)

    return builder.compile()


def run_ingestion(state: IngestionState, *, graph: Any) -> IngestionState:
    """그래프를 invoke 해 IngestionState 를 채워 반환한다.

    LangGraph 0.2.x 는 Pydantic state 를 dict 로 직렬화해 반환하므로
    ``IngestionState.model_validate`` 로 재구성한다 (query_graph.run_query 패턴 정합).

    Args:
        state: 초기 IngestionState. ``page`` 만 채워져 진입한다.
        graph: ``build_ingestion_graph`` 로 컴파일된 그래프.

    Returns:
        그래프 종료 후 ``IngestionState`` — ``doc_type`` / ``chunks`` / ``stage`` /
        ``status`` 가 채워져 있다.
    """
    result_dict = graph.invoke(state)
    return IngestionState.model_validate(result_dict)


# --- 노드 구현 ---


def _analyze_document_node(state: IngestionState, *, deps: IngestionGraphDeps) -> IngestionState:
    """ANALYZE stage — Agent stub 호출 후 페이지 단위 잡 기록."""
    started = datetime.now(UTC)
    state = deps.document_analyzer_node(state)
    state.stage = IngestionStage.ANALYZE
    state.status = IngestionStatus.SUCCESS

    deps.jobs.record(
        IngestionJobRecord(
            page_id=state.page.page_id,
            attachment_id=None,
            stage=IngestionStage.ANALYZE,
            status=IngestionStatus.SUCCESS,
            started_at=started,
            finished_at=datetime.now(UTC),
            error=None,
        )
    )
    return state


def _chunk_documents_node(state: IngestionState, *, deps: IngestionGraphDeps) -> IngestionState:
    """CHUNK stage — 본문 + 유효 첨부 청킹. 무효 첨부는 첨부 단위 잡 기록 후 스킵."""
    started = datetime.now(UTC)
    page = state.page

    # 본문 청킹 (외부 의존성 0).
    body_chunks = chunk_page(page, state.doc_type)

    # 첨부 순회 — 분석 → (유효 시) 청킹 → (PDF/CSV 등) ValueError 잡으면 잡 기록 + 스킵.
    attachment_chunks: list[Chunk] = []
    for attachment in page.attachments:
        attachment_chunks.extend(_process_attachment(attachment, page, deps))

    state.chunks = body_chunks + attachment_chunks
    state.stage = IngestionStage.CHUNK
    state.status = IngestionStatus.SUCCESS

    deps.jobs.record(
        IngestionJobRecord(
            page_id=page.page_id,
            attachment_id=None,
            stage=IngestionStage.CHUNK,
            status=IngestionStatus.SUCCESS,
            started_at=started,
            finished_at=datetime.now(UTC),
            error=None,
        )
    )
    return state


def _process_attachment(
    attachment: Attachment, page: PageObject, deps: IngestionGraphDeps
) -> list[Chunk]:
    """첨부 단위 분석 → 청킹 → 잡 기록. 무효/실패 시 빈 list 반환 (본문은 정상 진행)."""
    started = datetime.now(UTC)
    analysis = analyze_attachment(attachment)
    if not analysis.analyzable:
        deps.jobs.record(
            IngestionJobRecord(
                page_id=page.page_id,
                attachment_id=attachment.attachment_id,
                stage=IngestionStage.ANALYZE,
                status=analysis.status,
                started_at=started,
                finished_at=datetime.now(UTC),
                error=analysis.reason,
            )
        )
        return []

    chunk_started = datetime.now(UTC)
    try:
        chunks = deps.chunk_attachment_fn(attachment, page, analysis.attachment_type)
        deps.jobs.record(
            IngestionJobRecord(
                page_id=page.page_id,
                attachment_id=attachment.attachment_id,
                stage=IngestionStage.CHUNK,
                status=IngestionStatus.SUCCESS,
                started_at=chunk_started,
                finished_at=datetime.now(UTC),
                error=None,
            )
        )
        return list(chunks)
    except ValueError as exc:
        # PDF/CSV (feature4-B 대기) 또는 알 수 없는 attachment_type — 잡 기록 후 본문은 정상.
        deps.jobs.record(
            IngestionJobRecord(
                page_id=page.page_id,
                attachment_id=attachment.attachment_id,
                stage=IngestionStage.CHUNK,
                status=IngestionStatus.UNSUPPORTED_ATTACH_TYPE,
                started_at=chunk_started,
                finished_at=datetime.now(UTC),
                error=str(exc),
            )
        )
        return []


def _embed_upsert_node(state: IngestionState, *, deps: IngestionGraphDeps) -> IngestionState:
    """UPSERT stage — index_chunks 호출 (임베딩 + Qdrant + chunk_lookup 적재)."""
    started = datetime.now(UTC)
    page = state.page

    if not state.chunks:
        # 본문이 비어 있고 유효 첨부도 0 — 적재 자체를 회피.
        deps.jobs.record(
            IngestionJobRecord(
                page_id=page.page_id,
                attachment_id=None,
                stage=IngestionStage.UPSERT,
                status=IngestionStatus.SUCCESS,
                started_at=started,
                finished_at=datetime.now(UTC),
                error=None,
            )
        )
        state.stage = IngestionStage.UPSERT
        state.status = IngestionStatus.SUCCESS
        return state

    # 첨부 download_url 매핑은 page.attachments 에서 합성 — chunk_lookup 적재 시점에 사용.
    attachment_download_urls = {att.attachment_id: att.download_url for att in page.attachments}

    index_chunks(
        state.chunks,
        version_by_page_id={page.page_id: page.version_number},
        dense_embedder=deps.dense_embedder,
        sparse_embedder=deps.sparse_embedder,
        store=deps.store,
        cache=deps.cache,
        chunk_lookup=deps.chunk_lookup,
        attachment_download_urls=attachment_download_urls,
    )

    state.stage = IngestionStage.UPSERT
    state.status = IngestionStatus.SUCCESS

    deps.jobs.record(
        IngestionJobRecord(
            page_id=page.page_id,
            attachment_id=None,
            stage=IngestionStage.UPSERT,
            status=IngestionStatus.SUCCESS,
            started_at=started,
            finished_at=datetime.now(UTC),
            error=None,
        )
    )
    return state


__all__ = [
    "ChunkAttachmentFn",
    "IngestionGraphDeps",
    "IngestionNode",
    "build_ingestion_graph",
    "run_ingestion",
]
