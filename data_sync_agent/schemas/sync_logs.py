"""data_sync_agent/schemas/sync_logs.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent

--------------------------------------------------
작성자 : 이영훈
작성목적 : 관리자 대시보드 sync_logs 컬렉션에 기록할 Delta/Full sync log schema 정의.
작성일 : 2026-06-17
변경사항 내역 (날짜, 변경목적, 변경내용 순)
  - 2026-06-17, 관리자 동기화 이력 표시용 sync log record schema 추가
--------------------------------------------------
[호환성]
  - Python 3.11.x 권장
  - 표준 라이브러리 dataclasses 기반
--------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from data_sync_agent.schemas._serialization import to_primitive


class SyncLogStatus(StrEnum):
    """관리자 화면과 BFF API 계약에 맞춘 sync log 상태."""

    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(slots=True)
class SyncLogRecord:
    """MongoDB ``sync_logs`` 컬렉션에 적재할 동기화 이력 record."""

    sync_id: str
    status: SyncLogStatus
    mode: str = "delta"
    job_id: str | None = None
    updated_pages: int = 0
    deleted_pages: int = 0
    failed_pages: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: int = 0
    raw_status: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.status = SyncLogStatus(self.status)
        self.validate()

    def validate(self) -> None:
        """관리자 표시와 Mongo 저장에 필요한 최소 유효성을 검증한다."""
        if not self.sync_id:
            raise ValueError("sync_id is required")
        if not self.mode:
            raise ValueError("mode is required")
        for field_name in (
            "updated_pages",
            "deleted_pages",
            "failed_pages",
            "duration_seconds",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be greater than or equal to 0")

    def to_dict(self) -> dict[str, Any]:
        """snake_case 기반 primitive dictionary를 반환한다."""
        self.validate()
        return to_primitive(self)

    def to_admin_document(self) -> dict[str, Any]:
        """BFF 관리자 API가 읽는 ``sync_logs`` 문서 필드명으로 변환한다."""
        self.validate()
        document: dict[str, Any] = {
            "syncId": self.sync_id,
            "mode": self.mode,
            "status": self.status.value,
            "updatedPages": self.updated_pages,
            "deletedPages": self.deleted_pages,
            "failedPages": self.failed_pages,
            "duration": self.duration_seconds,
        }
        if self.job_id:
            document["jobId"] = self.job_id
        if self.started_at:
            document["startedAt"] = self.started_at
        if self.completed_at:
            document["completedAt"] = self.completed_at
        if self.raw_status:
            document["rawStatus"] = self.raw_status
        if self.error:
            document["error"] = self.error
        if self.metadata:
            document["metadata"] = to_primitive(self.metadata)
        return document
