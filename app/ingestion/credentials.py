"""Confluence ingestion credential boundary.

작성자 : 이영훈
담당 영역 : ai-agent

auth-server owns credential storage and Admin Key activation/deactivation.  The
ingestion worker receives only an ``adminUserId`` in public job payloads, then
resolves it through an internal auth-server API before calling Confluence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdminConfluenceCredential:
    """Credential set resolved from auth-server for one admin ingestion job.

    api-spec v2.6.2 §2-5 returns OAuth credentials for content reads plus
    ``siteUrl`` for source-link normalization. Admin API Token stays inside
    auth-server and is not exposed to the ingestion worker.
    """

    access_token: str
    cloud_id: str
    site_url: str
    expires_at: str | None = None

    def __post_init__(self) -> None:
        missing = [
            name
            for name, value in (
                ("access_token", self.access_token),
                ("cloud_id", self.cloud_id),
                ("site_url", self.site_url),
            )
            if not value.strip()
        ]
        if missing:
            raise ValueError(f"admin credential missing required field(s): {', '.join(missing)}")


CredentialResolver = Callable[[str], AdminConfluenceCredential]
