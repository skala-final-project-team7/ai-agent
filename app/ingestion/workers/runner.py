"""RabbitMQ channel runners for ingestion workers.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.ingestion.workers import QUEUE_ATTACHMENT, QUEUE_CHUNKING
from app.ingestion.workers.attachment_worker import (
    AttachmentExtractionDeps,
    AttachmentExtractionNotFoundError,
    process_attachment_extraction_message,
)
from app.ingestion.workers.chunking_worker import (
    AttachmentNotFoundError,
    ChunkingWorkerDeps,
    RawPageNotFoundError,
    process_chunking_message,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class WorkerLoopResult:
    """Summary counters for a RabbitMQ worker loop run."""

    processed: int = 0
    permanent_failures: int = 0
    transient_failures: int = 0


def run_chunking_worker_channel(
    channel: Any,
    deps: ChunkingWorkerDeps | object,
    *,
    queue: str = QUEUE_CHUNKING,
    max_messages: int | None = None,
    requeue_on_error: bool = True,
) -> WorkerLoopResult:
    """Consume RabbitMQ deliveries and apply explicit ack/nack semantics.

    Known pipeline mismatches are permanent failures: redelivery will not create the missing
    raw page/attachment, so they are acked after warning to avoid an infinite poison loop.
    Malformed JSON is nacked with ``requeue=False`` so a broker DLQ policy can capture it.
    Unexpected errors are nacked according to ``requeue_on_error`` and re-raised for visibility.
    """
    result = WorkerLoopResult()
    seen = 0
    for method, _properties, body in channel.consume(queue, auto_ack=False):
        delivery_tag = method.delivery_tag
        try:
            message = _decode_body(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            _LOGGER.warning("chunking worker: malformed JSON message nacked — %s", exc)
            channel.basic_nack(delivery_tag, requeue=False)
            result.permanent_failures += 1
        else:
            try:
                process_chunking_message(message, deps)  # type: ignore[arg-type]
            except (RawPageNotFoundError, AttachmentNotFoundError) as exc:
                _LOGGER.warning(
                    "chunking worker: permanent pipeline mismatch acked — %s: %s",
                    type(exc).__name__,
                    exc,
                )
                channel.basic_ack(delivery_tag)
                result.permanent_failures += 1
            except Exception:
                result.transient_failures += 1
                channel.basic_nack(delivery_tag, requeue=requeue_on_error)
                raise
            else:
                channel.basic_ack(delivery_tag)
                result.processed += 1

        seen += 1
        if max_messages is not None and seen >= max_messages:
            break
    return result


def run_attachment_extraction_worker_channel(
    channel: Any,
    deps: AttachmentExtractionDeps | object,
    *,
    queue: str = QUEUE_ATTACHMENT,
    max_messages: int | None = None,
    requeue_on_error: bool = True,
) -> WorkerLoopResult:
    """Consume attachment extraction deliveries with explicit ack/nack semantics.

    Missing raw page/attachment is treated as a permanent pipeline mismatch and acked. Malformed
    JSON is nacked without requeue for DLQ capture. Unexpected errors are nacked according to
    ``requeue_on_error`` and re-raised for supervisor visibility.
    """
    result = WorkerLoopResult()
    seen = 0
    for method, _properties, body in channel.consume(queue, auto_ack=False):
        delivery_tag = method.delivery_tag
        try:
            message = _decode_body(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            _LOGGER.warning("attachment worker: malformed JSON message nacked — %s", exc)
            channel.basic_nack(delivery_tag, requeue=False)
            result.permanent_failures += 1
        else:
            try:
                process_attachment_extraction_message(message, deps)  # type: ignore[arg-type]
            except AttachmentExtractionNotFoundError as exc:
                _LOGGER.warning(
                    "attachment worker: permanent pipeline mismatch acked — %s: %s",
                    type(exc).__name__,
                    exc,
                )
                channel.basic_ack(delivery_tag)
                result.permanent_failures += 1
            except Exception:
                result.transient_failures += 1
                channel.basic_nack(delivery_tag, requeue=requeue_on_error)
                raise
            else:
                channel.basic_ack(delivery_tag)
                result.processed += 1

        seen += 1
        if max_messages is not None and seen >= max_messages:
            break
    return result


def _decode_body(body: bytes | bytearray | memoryview | str) -> dict[str, Any]:
    raw = body if isinstance(body, str) else bytes(body).decode("utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise json.JSONDecodeError("message body must be a JSON object", raw, 0)
    return value
