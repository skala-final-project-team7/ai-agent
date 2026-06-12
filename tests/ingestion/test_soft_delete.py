"""apply_soft_deletes 단위 테스트.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

from collections.abc import Iterable

from app.ingestion.soft_delete import SoftDeleteResult, apply_soft_deletes


class _RecordingStore:
    def __init__(
        self,
        *,
        fail_page_ids: Iterable[str] = (),
        fail_attachment_ids: Iterable[str] = (),
    ) -> None:
        self.page_calls: list[str] = []
        self.attachment_calls: list[str] = []
        self._fail_pages = set(fail_page_ids)
        self._fail_attachments = set(fail_attachment_ids)

    def soft_delete_by_page_id(self, page_id: str) -> None:
        self.page_calls.append(page_id)
        if page_id in self._fail_pages:
            raise RuntimeError(page_id)

    def soft_delete_by_attachment_id(self, attachment_id: str) -> None:
        self.attachment_calls.append(attachment_id)
        if attachment_id in self._fail_attachments:
            raise RuntimeError(attachment_id)


def test_apply_soft_deletes_pages_and_attachments() -> None:
    store = _RecordingStore()

    result = apply_soft_deletes(
        store=store,
        page_ids=["P2", "P1"],
        attachment_ids=["A1"],
    )

    assert store.page_calls == ["P1", "P2"]
    assert store.attachment_calls == ["A1"]
    assert result.soft_deleted_page_ids == ["P1", "P2"]
    assert result.soft_deleted_attachment_ids == ["A1"]
    assert result.total_soft_deleted == 3
    assert result.has_failures is False


def test_apply_soft_deletes_normalizes_and_isolates_failures() -> None:
    store = _RecordingStore(fail_page_ids=["P2"], fail_attachment_ids=["A2"])

    result = apply_soft_deletes(
        store=store,
        page_ids=["P1", "P2", " P1 ", ""],
        attachment_ids=["A1", "A2"],
    )

    assert store.page_calls == ["P1", "P2"]
    assert store.attachment_calls == ["A1", "A2"]
    assert result.soft_deleted_page_ids == ["P1"]
    assert result.failed_page_ids == ["P2"]
    assert result.soft_deleted_attachment_ids == ["A1"]
    assert result.failed_attachment_ids == ["A2"]
    assert result.has_failures is True


def test_apply_soft_deletes_empty_input_is_noop() -> None:
    store = _RecordingStore()

    result = apply_soft_deletes(store=store)

    assert store.page_calls == []
    assert store.attachment_calls == []
    assert result == SoftDeleteResult()
