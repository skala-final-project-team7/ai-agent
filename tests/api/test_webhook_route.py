"""Confluence 삭제 Webhook 라우트 회귀 테스트."""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest
from httpx import ASGITransport

from app.api.ingest_deps import IngestDeps
from app.api.ingest_routes import get_deps
from app.api.main import create_app
from app.api.webhook_routes import parse_confluence_delete_event
from app.ingestion.crawler import CrawlRequest, CrawlResult
from app.ingestion.embedder.base import SparseVector
from app.ingestion.sync import DeltaSyncResult
from app.ingestion.vector_store import CONTENT_POOL
from app.ingestion.workers.sync_worker import SyncWorker, SyncWorkerDeps
from app.schemas.chunk import Chunk, ChunkMetadata
from app.schemas.enums import DocType, SourceType
from app.storage.ingest_jobs import InMemoryIngestJobStore
from app.storage.qdrant_fake import FakeQdrantPoolStore

_EMPTY_SPARSE = SparseVector(indices=(), values=())


def test_parse_delete_events() -> None:
    page = parse_confluence_delete_event({"event": "page_removed", "page": {"id": "P1"}})
    attachment = parse_confluence_delete_event(
        {"event": "attachment_removed", "attachment": {"id": "ATT-1"}}
    )

    assert page is not None and page.page_id == "P1"
    assert attachment is not None and attachment.attachment_id == "ATT-1"
    assert parse_confluence_delete_event({"event": "page_created", "page": {"id": "P1"}}) is None


def _chunk(*, chunk_id: str, page_id: str) -> Chunk:
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
            source_type=SourceType.PAGE,
            token_count=10,
        ),
    )


def _deps_with_seeded_store() -> tuple[IngestDeps, FakeQdrantPoolStore]:
    store = FakeQdrantPoolStore()
    store.upsert_chunks_batch(
        CONTENT_POOL, [(_chunk(chunk_id="a" * 40, page_id="P1"), 1, [], _EMPTY_SPARSE)]
    )

    def _run_crawl(request: CrawlRequest) -> CrawlResult:
        return CrawlResult(space_key=request.space_key, pages_collected=0, failed_page_ids=[])

    def _run_delta(request: object) -> DeltaSyncResult:
        return DeltaSyncResult()

    deps = IngestDeps(
        job_store=InMemoryIngestJobStore(),
        run_crawl=_run_crawl,
        run_delta=_run_delta,
        previous_snapshot_path="/tmp/previous_snapshot.json",
        sync_worker=SyncWorker(SyncWorkerDeps(store=store)),
    )
    return deps, store


def _client(deps: IngestDeps) -> httpx.AsyncClient:
    app = create_app()
    app.dependency_overrides[get_deps] = lambda: deps
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_webhook_page_removed_soft_deletes() -> None:
    deps, store = _deps_with_seeded_store()
    async with _client(deps) as client:
        resp = await client.post(
            "/ml/confluence/webhook",
            json={"event": "page_removed", "page": {"id": "P1"}},
        )

    assert resp.status_code == 200
    assert resp.json()["softDeleted"]["pageIds"] == ["P1"]
    assert store.points[CONTENT_POOL]["a" * 40].is_deleted is True


@pytest.mark.asyncio
async def test_webhook_invalid_json_returns_400_envelope() -> None:
    deps, _store = _deps_with_seeded_store()
    async with _client(deps) as client:
        resp = await client.post(
            "/ml/confluence/webhook",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )

    assert resp.status_code == 400
    assert resp.json()["errorCode"] == "INVALID_REQUEST"
