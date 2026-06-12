"""Attachment extraction worker tests.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.ingestion.attachment_downloader import DownloadedAttachment
from app.ingestion.workers import QUEUE_CHUNKING
from app.ingestion.workers.attachment_worker import (
    AttachmentExtractionDeps,
    AttachmentExtractionNotFoundError,
    process_attachment_extraction_message,
    run_attachment_extraction_worker,
)
from app.ingestion.workers.consumer import FakeMessageConsumer
from app.ingestion.workers.publisher import FakeQueuePublisher
from app.schemas.enums import ExtractedFormat, IngestionStage, IngestionStatus
from app.schemas.page_object import Attachment, PageObject
from app.storage.jobs import FakeIngestionJobsRepository
from app.storage.raw_store import FakeRawPageStore

_VALID_CSV = (
    "step,description\n"
    "1,Stop the service and verify all inflight requests are drained before continuing.\n"
    "2,Clear the cache and confirm the health endpoint returns green across instances.\n"
)


@dataclass(slots=True)
class _FakeDownloader:
    content: bytes
    local_path: str = "/tmp/att-1.csv"

    def download(self, attachment: Attachment) -> DownloadedAttachment:
        return DownloadedAttachment(content=self.content, local_path=self.local_path)


def _page(page_id: str = "page-1") -> PageObject:
    return PageObject(
        page_id=page_id,
        space_key="ENG",
        title="Runbook",
        body_html="<p>body</p>",
        version_number=3,
        last_modified=datetime.fromisoformat("2026-05-14T01:00:00+00:00"),
        allowed_groups=["space:ENG"],
        allowed_users=[],
        webui_link=f"/wiki/{page_id}",
    )


def _attachment(
    attachment_id: str = "att-1",
    *,
    page_id: str = "page-1",
    filename: str = "att-1.csv",
    mime_type: str = "text/csv",
) -> Attachment:
    return Attachment(
        attachment_id=attachment_id,
        filename=filename,
        mime_type=mime_type,
        extracted_text="",
        extracted_format=ExtractedFormat.RAW_TEXT,
        download_url=f"https://confluence.example/download/{attachment_id}",
        parent_page_id=page_id,
        last_modified=datetime.fromisoformat("2026-05-14T01:00:00+00:00"),
    )


def _deps(
    raw: FakeRawPageStore,
    *,
    downloader: _FakeDownloader | None = None,
    publisher: FakeQueuePublisher | None = None,
    jobs: FakeIngestionJobsRepository | None = None,
) -> AttachmentExtractionDeps:
    return AttachmentExtractionDeps(
        raw_store=raw,
        downloader=downloader or _FakeDownloader(_VALID_CSV.encode("utf-8")),
        publisher=publisher or FakeQueuePublisher(),
        jobs=jobs,
    )


def test_process_attachment_extracts_updates_raw_store_and_publishes_chunking() -> None:
    raw = FakeRawPageStore()
    raw.save_page(_page())
    raw.save_attachment(_attachment())
    publisher = FakeQueuePublisher()
    jobs = FakeIngestionJobsRepository()

    result = process_attachment_extraction_message(
        {"page_id": "page-1", "attachment_id": "att-1"},
        _deps(raw, publisher=publisher, jobs=jobs),
    )

    assert result.status is IngestionStatus.SUCCESS
    assert result.published_chunking is True
    updated = raw.get_attachment("att-1")
    assert updated is not None
    assert updated.local_path == "/tmp/att-1.csv"
    assert updated.extracted_format is ExtractedFormat.SHEET_SERIALIZED
    assert "step: 1" in updated.extracted_text
    assert [message.routing_key for message in publisher.messages] == [QUEUE_CHUNKING]
    assert publisher.messages[0].body["source_type"] == "attachment"
    assert [record.stage for record in jobs.records] == [IngestionStage.ANALYZE]
    assert jobs.records[0].status is IngestionStatus.SUCCESS


def test_process_attachment_uses_injected_chunking_routing_key() -> None:
    raw = FakeRawPageStore()
    raw.save_page(_page())
    raw.save_attachment(_attachment())
    publisher = FakeQueuePublisher()
    deps = _deps(raw, publisher=publisher)
    deps.chunking_routing_key = "custom.content.chunking"

    process_attachment_extraction_message(
        {"page_id": "page-1", "attachment_id": "att-1"},
        deps,
    )

    assert [message.routing_key for message in publisher.messages] == ["custom.content.chunking"]


def test_process_attachment_records_unsupported_type_without_publishing() -> None:
    raw = FakeRawPageStore()
    raw.save_page(_page())
    raw.save_attachment(_attachment(filename="archive.zip", mime_type="application/zip"))
    publisher = FakeQueuePublisher()
    jobs = FakeIngestionJobsRepository()

    result = process_attachment_extraction_message(
        {"page_id": "page-1", "attachment_id": "att-1"},
        _deps(raw, publisher=publisher, jobs=jobs),
    )

    assert result.status is IngestionStatus.UNSUPPORTED_ATTACH_TYPE
    assert publisher.messages == []
    assert jobs.records[0].status is IngestionStatus.UNSUPPORTED_ATTACH_TYPE


def test_process_attachment_records_partial_parse_without_publishing() -> None:
    raw = FakeRawPageStore()
    raw.save_page(_page())
    raw.save_attachment(_attachment(filename="att-1.pdf", mime_type="application/pdf"))
    publisher = FakeQueuePublisher()

    result = process_attachment_extraction_message(
        {"page_id": "page-1", "attachment_id": "att-1"},
        _deps(raw, downloader=_FakeDownloader(b"not a pdf"), publisher=publisher),
    )

    assert result.status is IngestionStatus.PARTIAL_PARSE
    assert publisher.messages == []


def test_process_attachment_raises_when_raw_object_missing() -> None:
    raw = FakeRawPageStore()

    try:
        process_attachment_extraction_message(
            {"page_id": "page-1", "attachment_id": "att-1"}, _deps(raw)
        )
    except AttachmentExtractionNotFoundError as exc:
        assert "page-1" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("AttachmentExtractionNotFoundError expected")


def test_run_attachment_worker_isolates_missing_message_and_continues() -> None:
    raw = FakeRawPageStore()
    raw.save_page(_page("page-1"))
    raw.save_page(_page("page-2"))
    raw.save_attachment(_attachment("att-1", page_id="page-1"))
    raw.save_attachment(_attachment("att-2", page_id="page-2"))
    consumer = FakeMessageConsumer(
        messages=[
            {"page_id": "page-1", "attachment_id": "att-1"},
            {"page_id": "page-1", "attachment_id": "ghost"},
            {"page_id": "page-2", "attachment_id": "att-2"},
        ]
    )

    results = run_attachment_extraction_worker(consumer, _deps(raw))

    assert [result.attachment_id for result in results] == ["att-1", "att-2"]
    assert all(result.status is IngestionStatus.SUCCESS for result in results)
