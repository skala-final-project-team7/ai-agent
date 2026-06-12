"""soft-delete 적용 seam — Delta / Trash / Webhook 삭제 트리거 공통 funnel.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol


class SoftDeleteStore(Protocol):
    """soft-delete 능력만 노출하는 store seam."""

    def soft_delete_by_page_id(self, page_id: str) -> None:
        """page_id 일치 청크의 payload is_deleted 를 True 로 set 한다."""
        ...

    def soft_delete_by_attachment_id(self, attachment_id: str) -> None:
        """attachment_id 일치 청크의 payload is_deleted 를 True 로 set 한다."""
        ...


@dataclass(frozen=True, slots=True)
class SoftDeleteResult:
    """soft-delete 적용 결과."""

    soft_deleted_page_ids: list[str] = field(default_factory=list)
    soft_deleted_attachment_ids: list[str] = field(default_factory=list)
    failed_page_ids: list[str] = field(default_factory=list)
    failed_attachment_ids: list[str] = field(default_factory=list)

    @property
    def total_soft_deleted(self) -> int:
        return len(self.soft_deleted_page_ids) + len(self.soft_deleted_attachment_ids)

    @property
    def has_failures(self) -> bool:
        return bool(self.failed_page_ids or self.failed_attachment_ids)


def _normalize_ids(ids: Iterable[str]) -> list[str]:
    return sorted({str(raw).strip() for raw in ids if str(raw).strip()})


def apply_soft_deletes(
    *,
    store: SoftDeleteStore,
    page_ids: Iterable[str] = (),
    attachment_ids: Iterable[str] = (),
) -> SoftDeleteResult:
    """page_id/attachment_id 목록을 store soft-delete 로 적용한다.

    입력은 dedup+정렬해 결정론적으로 처리하고, id 단위 예외를 격리해 부분 성공을 보장한다.
    """
    soft_pages: list[str] = []
    failed_pages: list[str] = []
    for page_id in _normalize_ids(page_ids):
        try:
            store.soft_delete_by_page_id(page_id)
        except Exception:  # noqa: BLE001
            failed_pages.append(page_id)
        else:
            soft_pages.append(page_id)

    soft_attachments: list[str] = []
    failed_attachments: list[str] = []
    for attachment_id in _normalize_ids(attachment_ids):
        try:
            store.soft_delete_by_attachment_id(attachment_id)
        except Exception:  # noqa: BLE001
            failed_attachments.append(attachment_id)
        else:
            soft_attachments.append(attachment_id)

    return SoftDeleteResult(
        soft_deleted_page_ids=soft_pages,
        soft_deleted_attachment_ids=soft_attachments,
        failed_page_ids=failed_pages,
        failed_attachment_ids=failed_attachments,
    )
