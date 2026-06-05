"""BFF Admin Key revoke callback client tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from app.api.admin_key_revoke import (
    AdminKeyRevokeRequest,
    BffAdminKeyRevokeNotifier,
    NoopAdminKeyRevokeNotifier,
    build_admin_key_revoke_notifier,
    notify_admin_key_revoke_safely,
)
from app.config import Settings
from app.schemas.enums import IngestJobStatus


def test_revoke_request_payload_excludes_access_token() -> None:
    request = AdminKeyRevokeRequest(
        job_id="job-1",
        mode="full",
        status=IngestJobStatus.COMPLETED,
        cloud_id="cloud-1",
        finished_at=datetime(2026, 6, 5, 1, 2, 3, tzinfo=UTC),
    )

    payload = request.to_payload()

    assert payload == {
        "jobId": "job-1",
        "mode": "full",
        "status": "COMPLETED",
        "cloudId": "cloud-1",
        "finishedAt": "2026-06-05T01:02:03+00:00",
        "error": None,
    }
    assert "accessToken" not in payload


def test_build_notifier_defaults_to_noop_when_url_empty() -> None:
    settings = Settings(_env_file=None)  # type: ignore[arg-type]

    notifier = build_admin_key_revoke_notifier(settings)

    assert isinstance(notifier, NoopAdminKeyRevokeNotifier)


def test_build_notifier_uses_bff_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_BFF_ADMIN_KEY_REVOKE_URL", "https://bff.example/internal/revoke")
    monkeypatch.setenv("RAG_BFF_ADMIN_KEY_REVOKE_TOKEN", "callback-secret")
    monkeypatch.setenv("RAG_BFF_ADMIN_KEY_REVOKE_TIMEOUT_SECONDS", "7")
    settings = Settings(_env_file=None)  # type: ignore[arg-type]

    notifier = build_admin_key_revoke_notifier(settings)

    assert isinstance(notifier, BffAdminKeyRevokeNotifier)
    assert notifier.url == "https://bff.example/internal/revoke"
    assert notifier.bearer_token == "callback-secret"
    assert notifier.timeout_seconds == 7


def test_bff_notifier_posts_payload_with_bearer_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _Response:
        def raise_for_status(self) -> None:
            captured["raise_for_status"] = True

    class _Client:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def post(self, url: str, *, json: dict[str, object], headers: dict[str, str]) -> _Response:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _Response()

    monkeypatch.setattr(httpx, "Client", _Client)
    notifier = BffAdminKeyRevokeNotifier(
        url="https://bff.example/internal/revoke",
        bearer_token="callback-secret",
        timeout_seconds=3.5,
    )

    notifier.notify(
        AdminKeyRevokeRequest(
            job_id="job-1",
            mode="delta",
            status=IngestJobStatus.FAILED,
            cloud_id="cloud-1",
            error="boom",
            finished_at=datetime(2026, 6, 5, 1, 2, 3, tzinfo=UTC),
        )
    )

    assert captured["timeout"] == 3.5
    assert captured["url"] == "https://bff.example/internal/revoke"
    assert captured["headers"]["Authorization"] == "Bearer callback-secret"
    assert captured["json"]["jobId"] == "job-1"
    assert captured["json"]["status"] == "FAILED"
    assert captured["json"]["error"] == "boom"
    assert captured["raise_for_status"] is True


def test_notify_safely_swallows_callback_errors() -> None:
    class _FailingNotifier:
        def notify(self, request: AdminKeyRevokeRequest) -> None:
            raise RuntimeError("bff unavailable")

    notify_admin_key_revoke_safely(
        _FailingNotifier(),
        AdminKeyRevokeRequest(
            job_id="job-1",
            mode="full",
            status=IngestJobStatus.COMPLETED,
        ),
    )
