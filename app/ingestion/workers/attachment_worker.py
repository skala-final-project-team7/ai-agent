"""Attachment extraction worker for ``content.extract.attachment`` messages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.ingestion.attachment_downloader import AttachmentDownloader
from app.ingestion.chunker import infer_attachment_type
from app.ingestion.crawler import build_attachment_chunking_message
from app.ingestion.extractor import extract_attachment_text
from app.ingestion.workers import QUEUE_CHUNKING
from app.ingestion.workers.consumer import MessageConsumer
from app.ingestion.workers.publisher import QueuePublisher
from app.schemas.enums import IngestionStage, IngestionStatus
from app.storage.jobs import IngestionJobRecord, IngestionJobsRepository
from app.storage.raw_store import RawPageStore

_LOGGER = logging.getLogger(__name__)


class AttachmentExtractionNotFoundError(KeyError):
    """Attachment extraction message points at a missing raw attachment or parent page."""


@dataclass(slots=True)
class AttachmentExtractionDeps:
    """Dependencies used by the attachment extraction worker."""

    raw_store: RawPageStore
    downloader: AttachmentDownloader
    publisher: QueuePublisher
    jobs: IngestionJobsRepository | None = None
    chunking_routing_key: str = QUEUE_CHUNKING


@dataclass(slots=True)
class AttachmentExtractionResult:
    """Attachment extraction message result."""

    page_id: str
    attachment_id: str
    status: IngestionStatus
    published_chunking: bool = False
    text_length: int = 0


def process_attachment_extraction_message(
    message: dict[str, Any], deps: AttachmentExtractionDeps
) -> AttachmentExtractionResult:
    """Download, extract, persist, and route one attachment extraction message."""
    page_id = str(message["page_id"])
    attachment_id = str(message["attachment_id"])
    started_at = datetime.now(UTC)

    page = deps.raw_store.get_page(page_id)
    if page is None:
        raise AttachmentExtractionNotFoundError(page_id)
    attachment = deps.raw_store.get_attachment(attachment_id)
    if attachment is None:
        raise AttachmentExtractionNotFoundError(attachment_id)

    try:
        attachment_type = infer_attachment_type(attachment)
    except ValueError as exc:
        _record(
            deps,
            page_id,
            attachment_id,
            IngestionStatus.UNSUPPORTED_ATTACH_TYPE,
            started_at,
            error=str(exc),
        )
        return AttachmentExtractionResult(
            page_id=page_id,
            attachment_id=attachment_id,
            status=IngestionStatus.UNSUPPORTED_ATTACH_TYPE,
        )

    downloaded = deps.downloader.download(attachment)
    extracted = extract_attachment_text(
        attachment_id=attachment.attachment_id,
        attachment_type=attachment_type,
        content=downloaded.content,
    )
    updated = attachment.model_copy(
        update={
            "extracted_text": extracted.text,
            "extracted_format": extracted.extracted_format,
            "local_path": downloaded.local_path,
        }
    )
    deps.raw_store.save_attachment(updated)

    if not extracted.ok:
        _record(
            deps,
            page_id,
            attachment_id,
            IngestionStatus.PARTIAL_PARSE,
            started_at,
            error=extracted.reason,
        )
        return AttachmentExtractionResult(
            page_id=page_id,
            attachment_id=attachment_id,
            status=IngestionStatus.PARTIAL_PARSE,
        )

    deps.publisher.publish(
        routing_key=deps.chunking_routing_key,
        message=build_attachment_chunking_message(page, updated),
    )
    _record(deps, page_id, attachment_id, IngestionStatus.SUCCESS, started_at, error=None)
    return AttachmentExtractionResult(
        page_id=page_id,
        attachment_id=attachment_id,
        status=IngestionStatus.SUCCESS,
        published_chunking=True,
        text_length=len(extracted.text),
    )


def run_attachment_extraction_worker(
    consumer: MessageConsumer, deps: AttachmentExtractionDeps
) -> list[AttachmentExtractionResult]:
    """Process attachment extraction messages, isolating known missing raw objects."""
    results: list[AttachmentExtractionResult] = []
    for message in consumer.consume():
        try:
            results.append(process_attachment_extraction_message(message, deps))
        except AttachmentExtractionNotFoundError as exc:
            _LOGGER.warning(
                "attachment worker: raw object mismatch skip — %s: %s",
                type(exc).__name__,
                exc,
            )
    return results


def _record(
    deps: AttachmentExtractionDeps,
    page_id: str,
    attachment_id: str,
    status: IngestionStatus,
    started_at: datetime,
    *,
    error: str | None,
) -> None:
    if deps.jobs is None:
        return
    deps.jobs.record(
        IngestionJobRecord(
            page_id=page_id,
            attachment_id=attachment_id,
            stage=IngestionStage.ANALYZE,
            status=status,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            error=error,
        )
    )
