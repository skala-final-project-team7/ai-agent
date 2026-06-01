"""Ingest job lifecycle store tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.schemas.enums import IngestJobStatus
from app.storage.ingest_jobs import (
    InMemoryIngestJobStore,
    MongoIngestJobStore,
)


@dataclass(slots=True)
class _UpdateResult:
    matched_count: int


class _FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs[doc["job_id"]] = dict(doc)

    def find_one(self, filter_doc: dict[str, Any], projection: dict[str, int] | None = None):
        doc = self.docs.get(filter_doc["job_id"])
        if doc is None:
            return None
        return dict(doc)

    def update_one(self, filter_doc: dict[str, Any], update_doc: dict[str, Any]) -> _UpdateResult:
        job_id = filter_doc["job_id"]
        if job_id not in self.docs:
            return _UpdateResult(matched_count=0)
        self.docs[job_id].update(update_doc["$set"])
        return _UpdateResult(matched_count=1)


class _FakeDb:
    def __init__(self, collection: _FakeCollection) -> None:
        self.collection = collection

    def __getitem__(self, name: str) -> _FakeCollection:
        return self.collection


class _FakeClient:
    def __init__(self, collection: _FakeCollection) -> None:
        self.collection = collection

    def __getitem__(self, name: str) -> _FakeDb:
        return _FakeDb(self.collection)


def test_in_memory_ingest_job_store_create_get_update() -> None:
    store = InMemoryIngestJobStore()

    created = store.create()
    updated = store.update(
        created.job_id,
        status=IngestJobStatus.COMPLETED,
        total_pages=3,
        processed_pages=2,
        failed_pages=1,
    )

    assert updated is not None
    fetched = store.get(created.job_id)
    assert fetched is updated
    assert fetched.status is IngestJobStatus.COMPLETED
    assert fetched.total_pages == 3
    assert fetched.processed_pages == 2
    assert fetched.failed_pages == 1


def test_mongo_ingest_job_store_create_get_update_round_trip() -> None:
    collection = _FakeCollection()
    store = MongoIngestJobStore(
        _FakeClient(collection),
        "lina_rag",
        collection_name="ingest_job_status",
    )
    created = store.create()
    finished_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    updated = store.update(
        created.job_id,
        status=IngestJobStatus.COMPLETED,
        total_pages=5,
        processed_pages=4,
        failed_pages=1,
        finished_at=finished_at,
    )

    assert updated is not None
    assert updated.job_id == created.job_id
    assert updated.status is IngestJobStatus.COMPLETED
    assert updated.total_pages == 5
    assert updated.processed_pages == 4
    assert updated.failed_pages == 1
    assert updated.finished_at == finished_at
    assert collection.docs[created.job_id]["status"] == "COMPLETED"


def test_mongo_ingest_job_store_update_missing_returns_none() -> None:
    store = MongoIngestJobStore(_FakeClient(_FakeCollection()), "lina_rag")

    result = store.update("job-missing", status=IngestJobStatus.FAILED)

    assert result is None


def test_build_ingest_job_store_uses_mongo_in_real_mode(monkeypatch) -> None:
    from app.api import ingest_deps as deps_mod

    class _FakeMongoStore:
        @classmethod
        def from_settings(cls, settings: Settings) -> str:
            return "mongo-store"

    monkeypatch.setattr(deps_mod, "MongoIngestJobStore", _FakeMongoStore)

    store = deps_mod.build_ingest_job_store(Settings(use_real_adapters=True))

    assert store == "mongo-store"
