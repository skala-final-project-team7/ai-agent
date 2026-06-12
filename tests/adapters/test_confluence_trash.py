"""Confluence Trash 소스 테스트.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

from typing import Any

from app.adapters.confluence_trash import (
    ConfluenceTrashContentClient,
    ConfluenceTrashSource,
    TrashedIds,
    parse_trashed_content,
)


def test_parse_trashed_content_classifies_page_and_attachment() -> None:
    parsed = parse_trashed_content(
        [
            {"id": "100", "type": "page", "status": "trashed"},
            {"id": "200", "type": "attachment", "status": "trashed"},
            {"id": "300", "type": "page"},
            {"id": "400", "type": "page", "status": "current"},
            "not-a-dict",
        ]
    )

    assert parsed.pages == {"100", "300"}
    assert parsed.attachments == {"200"}


class _FakeTrashContentClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def fetch_trashed(self, *, space_key: str, cursor: str | None) -> dict[str, Any]:
        self.calls.append((space_key, cursor))
        if cursor is None:
            return {
                "results": [{"id": "100", "type": "page", "status": "trashed"}],
                "_links": {"next": "/wiki/rest/api/content?status=trashed&start=1"},
            }
        return {
            "results": [{"id": "200", "type": "attachment", "status": "trashed"}],
            "_links": {},
        }


def test_confluence_trash_source_paginates_and_accumulates() -> None:
    client = _FakeTrashContentClient()
    source = ConfluenceTrashSource(client=client, space_keys=["CLOUD"])

    trashed = source.list_trashed_ids()

    assert trashed.pages == {"100"}
    assert trashed.attachments == {"200"}
    assert client.calls == [
        ("CLOUD", None),
        ("CLOUD", "/wiki/rest/api/content?status=trashed&start=1"),
    ]


def test_confluence_trash_source_empty_space_keys_returns_empty() -> None:
    source = ConfluenceTrashSource(client=_FakeTrashContentClient(), space_keys=[])

    assert source.list_trashed_ids() == TrashedIds()


class _RecordingTransport:
    def __init__(self) -> None:
        self.url = ""
        self.headers: dict[str, str] = {}

    def get_json(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        self.url = url
        self.headers = headers
        return {"results": [], "_links": {}}


def test_trash_content_client_builds_url_and_auth_headers() -> None:
    transport = _RecordingTransport()
    client = ConfluenceTrashContentClient(
        cloud_id="CID",
        access_token="secret-token",
        use_admin_key=True,
        page_limit=50,
        transport=transport,
    )

    client.fetch_trashed(space_key="CLOUD", cursor=None)

    assert transport.url.startswith(
        "https://api.atlassian.com/ex/confluence/CID/wiki/rest/api/content?"
    )
    assert "status=trashed" in transport.url
    assert "spaceKey=CLOUD" in transport.url
    assert "limit=50" in transport.url
    assert transport.headers["Authorization"] == "Bearer secret-token"
    assert transport.headers["Atl-Confluence-With-Admin-Key"] == "true"
