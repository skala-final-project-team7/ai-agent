"""수집 잡 수명주기 저장소 — `/ml/ingest` 트리거·상태 조회 [Storage 경계].

--------------------------------------------------
작성자 : 최태성
작성목적 : api-spec v2.2.0 §2-2/§2-3 의 수집 HTTP API 가 사용하는 **잡 수명주기** 저장소를
          정의한다. ``POST /ml/ingest`` 가 잡을 생성(``STARTED``)하고 백그라운드 크롤이
          진행하며 상태(``IN_PROGRESS`` → ``COMPLETED``|``FAILED``)와 집계 카운트
          (total/processed/failed pages)를 갱신하면, ``GET /ml/ingest/status/{jobId}`` 가
          이를 조회한다. 페이지 단위 처리 로그(``app/storage/jobs.py`` ``IngestionJobRecord``,
          db-schema §2.3)와는 책임이 다르다 — 본 저장소는 잡 1건의 진행 상태만 추적한다.
작성일 : 2026-05-29 (api-spec v2.2.0 §2-2/§2-3 HTTP API)
변경사항 내역 (날짜, 변경목적, 변경내용 순)
  - 2026-05-29, 최초 작성 — IngestJobRecord + IngestJobStore ABC + InMemoryIngestJobStore
    (PoC/단일 프로세스). 운영 다중 워커 환경은 공유 저장소(MySQL/Redis) 구현으로 교체한다.
--------------------------------------------------
[호환성]
  - Python 3.11.x
  - 외부 의존성 0 (표준 라이브러리만 사용 — threading/uuid/datetime/dataclasses)
--------------------------------------------------
"""

from __future__ import annotations

import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from app.config import Settings
from app.schemas.enums import IngestJobStatus


@dataclass
class IngestJobRecord:
    """수집 잡 1건의 수명주기 상태 (api-spec v2.2.0 §2-3 응답 필드의 내부 표현).

    저장 시각은 UTC(`datetime`, tz-aware)로 보관하고, API 직렬화 단계에서 KST(+09:00)로
    절대 전환한다(시간 표기 정책). ``total_pages`` / ``processed_pages`` / ``failed_pages``
    는 크롤 완료 시 ``CrawlResult`` 집계로 채운다.
    """

    job_id: str
    status: IngestJobStatus
    started_at: datetime
    total_pages: int = 0
    processed_pages: int = 0
    failed_pages: int = 0
    finished_at: datetime | None = None
    error: str | None = None


class IngestJobStore(ABC):
    """수집 잡 수명주기 저장소 인터페이스 — 라우트·백그라운드 태스크가 공유한다."""

    @abstractmethod
    def create(self, job_id: str | None = None) -> IngestJobRecord:
        """``STARTED`` 상태의 새 잡을 생성하고 고유 ``job_id`` 를 부여해 반환한다."""

    @abstractmethod
    def get(self, job_id: str) -> IngestJobRecord | None:
        """``job_id`` 로 잡을 조회한다. 없으면 None(라우트가 404로 매핑)."""

    @abstractmethod
    def update(self, job_id: str, **changes: object) -> IngestJobRecord | None:
        """잡의 필드를 부분 갱신한다(존재하지 않으면 None)."""


class InMemoryIngestJobStore(IngestJobStore):
    """프로세스 메모리 기반 잡 저장소 (PoC/단일 워커).

    백그라운드 크롤 태스크와 상태 조회 라우트가 서로 다른 스레드에서 접근하므로
    ``threading.Lock`` 으로 보호한다. 운영 다중 워커 환경에서는 공유 저장소 구현으로
    교체한다(본 클래스만 갈아끼우면 됨).
    """

    def __init__(self) -> None:
        self._jobs: dict[str, IngestJobRecord] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str | None = None) -> IngestJobRecord:
        with self._lock:
            record = IngestJobRecord(
                job_id=job_id or f"job-{uuid.uuid4()}",
                status=IngestJobStatus.STARTED,
                started_at=datetime.now(UTC),
            )
            self._jobs[record.job_id] = record
            return record

    def get(self, job_id: str) -> IngestJobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes: object) -> IngestJobRecord | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            for key, value in changes.items():
                setattr(record, key, value)
            return record


class MongoIngestJobStore(IngestJobStore):
    """MongoDB 기반 수집 잡 수명주기 저장소.

    페이지/단계별 처리 로그(``MongoIngestionJobsRepository``)와 구분하기 위해 기본 컬렉션은
    ``ingest_job_status`` 를 사용한다. ``job_id`` 기준 upsert/update 로 API 상태 조회에 필요한
    잡 1건의 lifecycle snapshot 만 저장한다.
    """

    def __init__(
        self,
        client: object,
        db_name: str,
        *,
        collection_name: str = "ingest_job_status",
    ) -> None:
        self._collection = client[db_name][collection_name]  # type: ignore[index]

    @classmethod
    def from_settings(cls, settings: Settings) -> MongoIngestJobStore:
        """환경 설정에서 MongoClient 를 생성해 인스턴스화한다."""
        from pymongo import MongoClient

        client: MongoClient = MongoClient(settings.mongo_uri)  # type: ignore[type-arg]
        return cls(
            client=client,
            db_name=settings.mongo_db,
            collection_name=settings.ingest_job_status_collection,
        )

    def create(self, job_id: str | None = None) -> IngestJobRecord:
        record = IngestJobRecord(
            job_id=job_id or f"job-{uuid.uuid4()}",
            status=IngestJobStatus.STARTED,
            started_at=datetime.now(UTC),
        )
        self._collection.insert_one(_record_to_doc(record))  # type: ignore[attr-defined]
        return record

    def get(self, job_id: str) -> IngestJobRecord | None:
        doc = self._collection.find_one(  # type: ignore[attr-defined]
            {"job_id": job_id}, projection={"_id": 0}
        )
        if doc is None:
            return None
        return _record_from_doc(doc)

    def update(self, job_id: str, **changes: object) -> IngestJobRecord | None:
        if not changes:
            return self.get(job_id)
        update_doc = {
            key: _serialize_value(value)
            for key, value in changes.items()
            if key in _UPDATABLE_FIELDS
        }
        if not update_doc:
            return self.get(job_id)
        result = self._collection.update_one(  # type: ignore[attr-defined]
            {"job_id": job_id},
            {"$set": update_doc},
        )
        if getattr(result, "matched_count", 0) == 0:
            return None
        return self.get(job_id)


_UPDATABLE_FIELDS = frozenset(
    {
        "status",
        "total_pages",
        "processed_pages",
        "failed_pages",
        "finished_at",
        "error",
    }
)


def _record_to_doc(record: IngestJobRecord) -> dict[str, object]:
    return {
        "job_id": record.job_id,
        "status": record.status.value,
        "started_at": record.started_at,
        "total_pages": record.total_pages,
        "processed_pages": record.processed_pages,
        "failed_pages": record.failed_pages,
        "finished_at": record.finished_at,
        "error": record.error,
    }


def _record_from_doc(doc: dict[str, object]) -> IngestJobRecord:
    return IngestJobRecord(
        job_id=str(doc["job_id"]),
        status=IngestJobStatus(str(doc["status"])),
        started_at=_coerce_datetime(doc["started_at"]),
        total_pages=_coerce_int(doc.get("total_pages")),
        processed_pages=_coerce_int(doc.get("processed_pages")),
        failed_pages=_coerce_int(doc.get("failed_pages")),
        finished_at=_optional_datetime(doc.get("finished_at")),
        error=_optional_str(doc.get("error")),
    )


def _serialize_value(value: object) -> object:
    if isinstance(value, IngestJobStatus):
        return value.value
    return value


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"expected datetime-compatible value, got {type(value).__name__}")


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return _coerce_datetime(value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _coerce_int(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected int-compatible value, got {type(value).__name__}")
