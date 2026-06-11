"""Ingestion completion event publisher.

api-spec v2.5.0 replaces the old BFF polling/revoke callback flow with a RabbitMQ
completion event. ML/Data Ingestion publishes terminal job state, and BFF consumes the
event to request Admin Key deactivation through auth-server.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.ingestion.workers.publisher import QueuePublisher
from app.schemas.enums import IngestJobStatus

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestCompletionEvent:
    """RabbitMQ completion event payload.

    Credential values such as accessToken, refreshToken, and cloudId are intentionally absent.
    BFF/auth-server resolve credentials by adminUserId and own the Admin Key deactivate call.
    """

    job_id: str
    mode: str
    status: IngestJobStatus
    admin_user_id: str | None = None
    error_code: str | None = None
    message: str | None = None
    completed_at: datetime | None = None

    def to_payload(self) -> dict[str, object]:
        completed_at = self.completed_at or datetime.now(UTC)
        event_type = "INGEST_COMPLETED"
        if self.status is IngestJobStatus.FAILED:
            event_type = "INGEST_FAILED"
        return {
            "eventType": event_type,
            "jobId": self.job_id,
            "adminUserId": self.admin_user_id,
            "mode": self.mode,
            "status": self.status.value,
            "completedAt": completed_at.isoformat(),
            "errorCode": self.error_code,
            "message": self.message,
        }


class IngestCompletionPublisher(Protocol):
    """Completion event publisher seam."""

    def publish(self, event: IngestCompletionEvent) -> None:
        """Publish or record terminal ingestion event."""


@dataclass(frozen=True, slots=True)
class NoopIngestCompletionPublisher:
    """No-op publisher used by local HTTP smoke and tests unless explicitly injected."""

    def publish(self, event: IngestCompletionEvent) -> None:
        return None


@dataclass(frozen=True, slots=True)
class QueueIngestCompletionPublisher:
    """QueuePublisher-backed completion event publisher."""

    publisher: QueuePublisher
    routing_key: str = "ingestion.completed"

    def publish(self, event: IngestCompletionEvent) -> None:
        self.publisher.publish(routing_key=self.routing_key, message=event.to_payload())


def publish_ingest_completion_safely(
    publisher: IngestCompletionPublisher | None,
    event: IngestCompletionEvent,
) -> None:
    """Publish completion event without changing terminal job status on publish failure."""
    if publisher is None:
        return
    try:
        publisher.publish(event)
    except Exception:  # noqa: BLE001 - event publish failure is an ops/retry concern.
        _LOGGER.exception(
            "ingest completion event publish failed: job_id=%s status=%s",
            event.job_id,
            event.status.value,
        )
