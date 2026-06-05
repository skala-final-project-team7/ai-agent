"""RabbitMQ channel runner tests for chunking worker ack/nack behavior."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.ingestion.workers import QUEUE_ATTACHMENT, QUEUE_CHUNKING
from app.ingestion.workers.attachment_worker import (
    AttachmentExtractionNotFoundError,
    AttachmentExtractionResult,
)
from app.ingestion.workers.chunking_worker import (
    ChunkingMessageResult,
    RawPageNotFoundError,
)
from app.ingestion.workers.runner import (
    run_attachment_extraction_worker_channel,
    run_chunking_worker_channel,
)
from app.schemas.enums import IngestionStatus


@dataclass(slots=True)
class _Method:
    delivery_tag: int


class _FakeChannel:
    def __init__(self, bodies: list[bytes]) -> None:
        self._bodies = bodies
        self.consumed: list[tuple[str, bool]] = []
        self.acks: list[int] = []
        self.nacks: list[tuple[int, bool]] = []

    def consume(self, queue: str, *, auto_ack: bool) -> Any:
        self.consumed.append((queue, auto_ack))
        for index, body in enumerate(self._bodies, start=1):
            yield _Method(index), None, body

    def basic_ack(self, delivery_tag: int) -> None:
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag: int, *, requeue: bool) -> None:
        self.nacks.append((delivery_tag, requeue))


def _body(message: dict[str, Any]) -> bytes:
    return json.dumps(message).encode("utf-8")


def test_channel_runner_acks_successful_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = _FakeChannel([_body({"page_id": "page-1"})])

    def _process(message: dict[str, Any], deps: object) -> ChunkingMessageResult:
        assert message == {"page_id": "page-1"}
        assert deps is object_deps
        return ChunkingMessageResult(page_id="page-1", status=IngestionStatus.SUCCESS)

    object_deps = object()
    monkeypatch.setattr("app.ingestion.workers.runner.process_chunking_message", _process)

    result = run_chunking_worker_channel(channel, object_deps, max_messages=1)

    assert channel.consumed == [(QUEUE_CHUNKING, False)]
    assert channel.acks == [1]
    assert channel.nacks == []
    assert result.processed == 1
    assert result.permanent_failures == 0
    assert result.transient_failures == 0


def test_channel_runner_acks_known_permanent_pipeline_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _FakeChannel([_body({"page_id": "ghost"})])

    def _process(message: dict[str, Any], deps: object) -> ChunkingMessageResult:
        raise RawPageNotFoundError(message["page_id"])

    monkeypatch.setattr("app.ingestion.workers.runner.process_chunking_message", _process)

    result = run_chunking_worker_channel(channel, object(), max_messages=1)

    assert channel.acks == [1]
    assert channel.nacks == []
    assert result.processed == 0
    assert result.permanent_failures == 1


def test_channel_runner_nacks_malformed_json_without_requeue() -> None:
    channel = _FakeChannel([b"{not-json"])

    result = run_chunking_worker_channel(channel, object(), max_messages=1)

    assert channel.acks == []
    assert channel.nacks == [(1, False)]
    assert result.processed == 0
    assert result.permanent_failures == 1


def test_channel_runner_nacks_unexpected_error_then_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _FakeChannel([_body({"page_id": "page-1"})])

    def _process(message: dict[str, Any], deps: object) -> ChunkingMessageResult:
        raise RuntimeError("qdrant unavailable")

    monkeypatch.setattr("app.ingestion.workers.runner.process_chunking_message", _process)

    with pytest.raises(RuntimeError, match="qdrant unavailable"):
        run_chunking_worker_channel(channel, object(), max_messages=1, requeue_on_error=True)

    assert channel.acks == []
    assert channel.nacks == [(1, True)]


def test_attachment_channel_runner_acks_successful_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _FakeChannel([_body({"page_id": "page-1", "attachment_id": "att-1"})])

    def _process(message: dict[str, Any], deps: object) -> AttachmentExtractionResult:
        assert message == {"page_id": "page-1", "attachment_id": "att-1"}
        assert deps is object_deps
        return AttachmentExtractionResult(
            page_id="page-1",
            attachment_id="att-1",
            status=IngestionStatus.SUCCESS,
        )

    object_deps = object()
    monkeypatch.setattr(
        "app.ingestion.workers.runner.process_attachment_extraction_message", _process
    )

    result = run_attachment_extraction_worker_channel(channel, object_deps, max_messages=1)

    assert channel.consumed == [(QUEUE_ATTACHMENT, False)]
    assert channel.acks == [1]
    assert channel.nacks == []
    assert result.processed == 1


def test_attachment_channel_runner_acks_known_permanent_pipeline_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _FakeChannel([_body({"page_id": "page-1", "attachment_id": "ghost"})])

    def _process(message: dict[str, Any], deps: object) -> AttachmentExtractionResult:
        raise AttachmentExtractionNotFoundError(message["attachment_id"])

    monkeypatch.setattr(
        "app.ingestion.workers.runner.process_attachment_extraction_message", _process
    )

    result = run_attachment_extraction_worker_channel(channel, object(), max_messages=1)

    assert channel.acks == [1]
    assert channel.nacks == []
    assert result.processed == 0
    assert result.permanent_failures == 1


def test_attachment_channel_runner_nacks_malformed_json_without_requeue() -> None:
    channel = _FakeChannel([b"{not-json"])

    result = run_attachment_extraction_worker_channel(channel, object(), max_messages=1)

    assert channel.acks == []
    assert channel.nacks == [(1, False)]
    assert result.processed == 0
    assert result.permanent_failures == 1


def test_attachment_channel_runner_nacks_unexpected_error_then_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _FakeChannel([_body({"page_id": "page-1", "attachment_id": "att-1"})])

    def _process(message: dict[str, Any], deps: object) -> AttachmentExtractionResult:
        raise RuntimeError("download unavailable")

    monkeypatch.setattr(
        "app.ingestion.workers.runner.process_attachment_extraction_message", _process
    )

    with pytest.raises(RuntimeError, match="download unavailable"):
        run_attachment_extraction_worker_channel(
            channel, object(), max_messages=1, requeue_on_error=True
        )

    assert channel.acks == []
    assert channel.nacks == [(1, True)]
