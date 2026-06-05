"""Sync Worker — Delta / Trash / Webhook 삭제 트리거를 soft-delete 로 수렴."""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.confluence_trash import TrashSource
from app.ingestion.soft_delete import SoftDeleteResult, SoftDeleteStore, apply_soft_deletes
from app.ingestion.sync import DeltaSyncResult


@dataclass(frozen=True, slots=True)
class WebhookDeleteEvent:
    """Confluence 삭제 webhook 1건."""

    page_id: str | None = None
    attachment_id: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.page_id and not self.attachment_id


@dataclass
class SyncWorkerDeps:
    store: SoftDeleteStore
    trash_source: TrashSource | None = None


class SyncWorker:
    """3중 삭제 트리거를 soft-delete store 로 적용하는 worker."""

    def __init__(self, deps: SyncWorkerDeps) -> None:
        self._deps = deps

    def apply_delta_deletions(
        self,
        result: DeltaSyncResult,
        *,
        confirm: bool = False,
    ) -> SoftDeleteResult:
        """Delta Sync 삭제 후보를 confirm=True 일 때만 soft-delete 한다."""
        if not confirm:
            return SoftDeleteResult()
        return apply_soft_deletes(
            store=self._deps.store,
            page_ids=result.deleted_candidate_page_ids,
        )

    def run_trash_sync(self) -> SoftDeleteResult:
        """Trash API 결과를 soft-delete 한다. trash_source 없으면 no-op."""
        if self._deps.trash_source is None:
            return SoftDeleteResult()
        trashed = self._deps.trash_source.list_trashed_ids()
        return apply_soft_deletes(
            store=self._deps.store,
            page_ids=trashed.pages,
            attachment_ids=trashed.attachments,
        )

    def handle_webhook_event(self, event: WebhookDeleteEvent) -> SoftDeleteResult:
        """Webhook 삭제 이벤트 1건을 즉시 soft-delete 한다."""
        if event.is_empty:
            return SoftDeleteResult()
        page_ids = [event.page_id] if event.page_id else []
        attachment_ids = [event.attachment_id] if event.attachment_id else []
        return apply_soft_deletes(
            store=self._deps.store,
            page_ids=page_ids,
            attachment_ids=attachment_ids,
        )
