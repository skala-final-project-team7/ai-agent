"""BFF Admin Key revoke callback client.

ML 서버는 Atlassian Admin Key를 직접 말소하지 않는다. 수집 작업이 terminal 상태에
도달하면 BFF가 제공한 callback endpoint로 말소 요청만 보낸다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx

from app.config import Settings
from app.schemas.enums import IngestJobStatus

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AdminKeyRevokeRequest:
    """BFF Admin Key revoke callback payload.

    access_token은 절대 포함하지 않는다. BFF는 job_id/cloud_id/status를 통해 자신의
    admin ingest watcher/session을 식별하고 Auth Server에 deactivate를 요청한다.
    """

    job_id: str
    mode: str
    status: IngestJobStatus
    cloud_id: str | None = None
    error: str | None = None
    finished_at: datetime | None = None

    def to_payload(self) -> dict[str, object]:
        finished_at = self.finished_at or datetime.now(UTC)
        return {
            "jobId": self.job_id,
            "mode": self.mode,
            "status": self.status.value,
            "cloudId": self.cloud_id,
            "finishedAt": finished_at.isoformat(),
            "error": self.error,
        }


class AdminKeyRevokeNotifier(Protocol):
    """BFF Admin Key revoke callback seam."""

    def notify(self, request: AdminKeyRevokeRequest) -> None:
        """Send or record a revoke request."""


@dataclass(frozen=True, slots=True)
class NoopAdminKeyRevokeNotifier:
    """No-op notifier used when no BFF callback URL is configured."""

    def notify(self, request: AdminKeyRevokeRequest) -> None:
        return None


@dataclass(frozen=True, slots=True)
class BffAdminKeyRevokeNotifier:
    """Synchronous HTTP notifier for BFF Admin Key revoke callback."""

    url: str
    bearer_token: str = ""
    timeout_seconds: float = 5.0

    def notify(self, request: AdminKeyRevokeRequest) -> None:
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.url, json=request.to_payload(), headers=headers)
            response.raise_for_status()


def build_admin_key_revoke_notifier(settings: Settings) -> AdminKeyRevokeNotifier:
    """Build BFF callback notifier from settings.

    Empty URL means the integration point is disabled. This keeps local tests and PoC execution
    independent from backend availability.
    """
    if not settings.bff_admin_key_revoke_url:
        return NoopAdminKeyRevokeNotifier()
    return BffAdminKeyRevokeNotifier(
        url=settings.bff_admin_key_revoke_url,
        bearer_token=settings.bff_admin_key_revoke_token.get_secret_value(),
        timeout_seconds=settings.bff_admin_key_revoke_timeout_seconds,
    )


def notify_admin_key_revoke_safely(
    notifier: AdminKeyRevokeNotifier,
    request: AdminKeyRevokeRequest,
) -> None:
    """Invoke BFF revoke callback without changing ingestion job result.

    Revoke callback failure is a security/ops event, but the ingestion job has already reached a
    terminal state. The failure is logged for alerting and retry policy discussion, not rethrown.
    """
    try:
        notifier.notify(request)
    except Exception:  # noqa: BLE001 - callback failure must not mask job terminal status.
        _LOGGER.exception(
            "admin key revoke callback failed: job_id=%s status=%s",
            request.job_id,
            request.status.value,
        )
