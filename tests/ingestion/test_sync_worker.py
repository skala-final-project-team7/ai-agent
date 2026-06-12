"""SyncWorker 삭제 트리거 테스트.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

from datetime import datetime

from app.adapters.confluence_trash import FakeTrashSource, TrashedIds
from app.ingestion.embedder.base import SparseVector
from app.ingestion.sync import DeltaSyncResult
from app.ingestion.vector_store import CONTENT_POOL
from app.ingestion.workers.sync_worker import SyncWorker, SyncWorkerDeps, WebhookDeleteEvent
from app.schemas.chunk import Chunk, ChunkMetadata
from app.schemas.enums import DocType, SourceType
from app.storage.qdrant_fake import FakeQdrantPoolStore

_EMPTY_SPARSE = SparseVector(indices=(), values=())


def _chunk(*, chunk_id: str, page_id: str, attachment_id: str | None = None) -> Chunk:
    return Chunk(
        text="body",
        metadata=ChunkMetadata(
            chunk_id=chunk_id,
            page_id=page_id,
            page_title="T",
            section_header="H",
            section_path="H",
            chunk_index=0,
            labels=[],
            doc_type=DocType.OPERATION,
            space_key="CLOUD",
            allowed_groups=["space:CLOUD"],
            allowed_users=[],
            webui_link="/x",
            last_modified=datetime.fromisoformat("2026-05-14T01:00:00+00:00"),
            source_type=SourceType.PAGE if attachment_id is None else SourceType.ATTACHMENT,
            attachment_id=attachment_id,
            token_count=10,
        ),
    )


def _seeded_store() -> FakeQdrantPoolStore:
    store = FakeQdrantPoolStore()
    store.upsert_chunks_batch(
        CONTENT_POOL, [(_chunk(chunk_id="a" * 40, page_id="P1"), 1, [], _EMPTY_SPARSE)]
    )
    store.upsert_chunks_batch(
        CONTENT_POOL, [(_chunk(chunk_id="b" * 40, page_id="P2"), 1, [], _EMPTY_SPARSE)]
    )
    store.upsert_chunks_batch(
        CONTENT_POOL,
        [(_chunk(chunk_id="c" * 40, page_id="P3", attachment_id="ATT-1"), 1, [], _EMPTY_SPARSE)],
    )
    return store


def _flag(store: FakeQdrantPoolStore, chunk_id: str) -> bool:
    return store.points[CONTENT_POOL][chunk_id].is_deleted


def test_apply_delta_deletions_requires_confirm() -> None:
    store = _seeded_store()
    worker = SyncWorker(SyncWorkerDeps(store=store))

    result = worker.apply_delta_deletions(DeltaSyncResult(deleted_candidate_page_ids=["P2"]))

    assert result.total_soft_deleted == 0
    assert _flag(store, "b" * 40) is False

    confirmed = worker.apply_delta_deletions(
        DeltaSyncResult(deleted_candidate_page_ids=["P2"]),
        confirm=True,
    )
    assert confirmed.soft_deleted_page_ids == ["P2"]
    assert _flag(store, "b" * 40) is True


def test_trash_and_webhook_soft_delete_paths() -> None:
    store = _seeded_store()
    worker = SyncWorker(
        SyncWorkerDeps(
            store=store,
            trash_source=FakeTrashSource(TrashedIds(pages={"P1"}, attachments={"ATT-1"})),
        )
    )

    trash_result = worker.run_trash_sync()
    webhook_result = worker.handle_webhook_event(WebhookDeleteEvent(page_id="P2"))

    assert trash_result.soft_deleted_page_ids == ["P1"]
    assert trash_result.soft_deleted_attachment_ids == ["ATT-1"]
    assert webhook_result.soft_deleted_page_ids == ["P2"]
    assert _flag(store, "a" * 40) is True
    assert _flag(store, "b" * 40) is True
    assert _flag(store, "c" * 40) is True
