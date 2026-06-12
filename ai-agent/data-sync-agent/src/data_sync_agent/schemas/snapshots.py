"""ai-agent/data-sync-agent/src/data_sync_agent/schemas/snapshots.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

"""
--------------------------------------------------
작성자 : 이영훈
작성목적 : Data Sync Agent page snapshot canonical schema 정의.
작성일 : 2026-05-14
변경사항 내역 (날짜, 변경목적, 변경내용 순)
  - 2026-05-14, 최초 작성, feature1 snapshot schema 구현
--------------------------------------------------
[호환성]
  - Python 3.11.x 권장
  - 표준 라이브러리 dataclasses 기반
--------------------------------------------------
"""

from dataclasses import dataclass
from typing import Any

from data_sync_agent.schemas._serialization import to_primitive


def build_page_key(cloud_id: str, space_id: str, page_id: str) -> str:
    """cloud, space, page id로 snapshot diff용 stable page key를 생성한다."""
    if not cloud_id:
        raise ValueError("cloud_id is required")
    if not space_id:
        raise ValueError("space_id is required")
    if not page_id:
        raise ValueError("page_id is required")
    return f"{cloud_id}:{space_id}:{page_id}"


@dataclass(slots=True)
class PageSnapshotItem:
    """Delta sync 비교에 사용하는 Confluence Page metadata snapshot item."""

    cloud_id: str
    space_id: str
    space_key: str
    space_name: str
    page_id: str
    title: str
    status: str
    page_url: str
    last_modified_at: str
    version_number: int
    page_key: str | None = None

    def __post_init__(self) -> None:
        if self.page_key is None:
            self.page_key = build_page_key(
                self.cloud_id,
                self.space_id,
                self.page_id,
            )
        self.validate()

    def validate(self) -> None:
        """Snapshot item 필수 metadata를 검증한다."""
        if self.page_key != build_page_key(self.cloud_id, self.space_id, self.page_id):
            raise ValueError("page_key must match cloud_id:space_id:page_id")
        if not self.space_key:
            raise ValueError("space_key is required")
        if not self.space_name:
            raise ValueError("space_name is required")
        if not self.title:
            raise ValueError("title is required")
        if self.status != "current":
            raise ValueError("status must be current")
        if not self.page_url:
            raise ValueError("page_url is required")
        if not self.last_modified_at:
            raise ValueError("last_modified_at is required")
        if self.version_number < 0:
            raise ValueError("version_number must be greater than or equal to 0")

    def to_dict(self) -> dict[str, Any]:
        """JSON snapshot 산출물에 사용할 primitive dictionary를 반환한다."""
        self.validate()
        return to_primitive(self)


@dataclass(slots=True)
class PageSnapshot:
    """Delta sync job의 previous/current page metadata snapshot."""

    snapshot_id: str
    sync_id: str
    cloud_id: str
    created_at: str
    pages: list[PageSnapshotItem]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Snapshot 필수값과 포함된 page metadata를 검증한다."""
        if not self.snapshot_id:
            raise ValueError("snapshot_id is required")
        if not self.sync_id:
            raise ValueError("sync_id is required")
        if not self.cloud_id:
            raise ValueError("cloud_id is required")
        if not self.created_at:
            raise ValueError("created_at is required")
        for page in self.pages:
            page.validate()
            if page.cloud_id != self.cloud_id:
                raise ValueError("snapshot page cloud_id must match snapshot cloud_id")

    def to_dict(self) -> dict[str, Any]:
        """JSON snapshot 산출물에 사용할 primitive dictionary를 반환한다."""
        self.validate()
        return to_primitive(self)
