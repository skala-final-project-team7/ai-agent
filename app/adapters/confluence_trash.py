"""Confluence Trash 소스 — 삭제된 page/attachment id 수집."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

_CONFLUENCE_API_ORIGIN = "https://api.atlassian.com"


@dataclass(frozen=True, slots=True)
class TrashedIds:
    """Trash 조회 결과."""

    pages: set[str] = field(default_factory=set)
    attachments: set[str] = field(default_factory=set)

    @property
    def is_empty(self) -> bool:
        return not self.pages and not self.attachments


class TrashSource(Protocol):
    def list_trashed_ids(self) -> TrashedIds:
        """Trashed 상태인 page_id/attachment_id 를 반환한다."""
        ...


@dataclass(frozen=True, slots=True)
class FakeTrashSource:
    trashed: TrashedIds = field(default_factory=TrashedIds)

    def list_trashed_ids(self) -> TrashedIds:
        return self.trashed


def parse_trashed_content(results: Iterable[Any]) -> TrashedIds:
    """Confluence content 목록에서 trashed page/attachment id 를 분류한다."""
    pages: set[str] = set()
    attachments: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        content_id = str(item.get("id") or "").strip()
        if not content_id:
            continue
        status = str(item.get("status") or "").strip().lower()
        if status and status != "trashed":
            continue
        content_type = str(item.get("type") or "page").strip().lower()
        if content_type == "attachment":
            attachments.add(content_id)
        else:
            pages.add(content_id)
    return TrashedIds(pages=pages, attachments=attachments)


class TrashContentClient(Protocol):
    def fetch_trashed(self, *, space_key: str, cursor: str | None) -> dict[str, Any]:
        """status=trashed content 한 페이지를 반환한다."""
        ...


@dataclass(frozen=True, slots=True)
class ConfluenceTrashSource:
    client: TrashContentClient
    space_keys: Sequence[str]
    max_pages: int = 100

    def list_trashed_ids(self) -> TrashedIds:
        pages: set[str] = set()
        attachments: set[str] = set()
        for space_key in self.space_keys:
            cursor: str | None = None
            for _ in range(self.max_pages):
                body = self.client.fetch_trashed(space_key=space_key, cursor=cursor)
                batch = parse_trashed_content(body.get("results") or [])
                pages |= batch.pages
                attachments |= batch.attachments
                cursor = (body.get("_links") or {}).get("next")
                if not cursor:
                    break
        return TrashedIds(pages=pages, attachments=attachments)


class _TrashHttpTransport(Protocol):
    def get_json(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        """url 을 GET 해 JSON body 를 dict 로 반환한다."""
        ...


class _UrllibTrashHttpTransport:
    def __init__(self, *, timeout_seconds: int = 20) -> None:
        self._timeout_seconds = timeout_seconds

    def get_json(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
            body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return body


@dataclass(frozen=True, slots=True)
class ConfluenceTrashContentClient:
    cloud_id: str
    access_token: str
    use_admin_key: bool = False
    page_limit: int = 100
    transport: _TrashHttpTransport | None = None

    def fetch_trashed(self, *, space_key: str, cursor: str | None) -> dict[str, Any]:
        transport = self.transport or _UrllibTrashHttpTransport()
        url = self._absolutize(cursor) if cursor else self._initial_url(space_key)
        return transport.get_json(url, self._headers())

    def _wiki_base(self) -> str:
        return f"{_CONFLUENCE_API_ORIGIN}/ex/confluence/{self.cloud_id}/wiki"

    def _initial_url(self, space_key: str) -> str:
        query = urlencode(
            {
                "status": "trashed",
                "spaceKey": space_key,
                "limit": self.page_limit,
                "expand": "container",
            }
        )
        return f"{self._wiki_base()}/rest/api/content?{query}"

    def _absolutize(self, next_path: str) -> str:
        if next_path.startswith("http://") or next_path.startswith("https://"):
            return next_path
        if next_path.startswith("/wiki/"):
            return urljoin(_CONFLUENCE_API_ORIGIN, f"/ex/confluence/{self.cloud_id}{next_path}")
        return f"{self._wiki_base()}{next_path}"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }
        if self.use_admin_key:
            headers["Atl-Confluence-With-Admin-Key"] = "true"
        return headers
