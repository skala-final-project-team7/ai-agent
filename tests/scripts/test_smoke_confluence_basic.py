"""Regression tests for the temporary Confluence Basic Auth smoke."""

from __future__ import annotations

from typing import Any

import pytest

from scripts.smoke_confluence_basic import SmokeConfig, config_from_env, run_smoke


class FakeConfluenceClient:
    def get_json(self, path: str, *, admin_key: bool = False) -> dict[str, Any]:
        if path.startswith("/api/v2/pages?") and not admin_key:
            return {
                "status_code": 200,
                "json": {
                    "results": [
                        {"id": "1", "title": "visible"},
                        {"id": "2", "title": "also visible"},
                    ],
                },
            }
        if path.startswith("/api/v2/pages?") and admin_key:
            return {
                "status_code": 200,
                "json": {
                    "results": [
                        {"id": "1", "title": "visible"},
                        {"id": "2", "title": "also visible"},
                        {"id": "3", "title": "restricted"},
                    ],
                },
            }
        if path == "/api/v2/pages/3?body-format=storage" and not admin_key:
            return {"status_code": 404, "json": {"errors": [{"code": "NOT_FOUND"}]}}
        if path == "/api/v2/pages/3?body-format=storage" and admin_key:
            return {"status_code": 200, "json": {"id": "3", "title": "restricted"}}
        if path == "/rest/api/content/3/restriction/byOperation/read" and admin_key:
            return {
                "status_code": 200,
                "json": {
                    "restrictions": {
                        "user": {"results": [{"accountId": "user-1"}]},
                        "group": {"results": [{"id": "group-1"}]},
                    },
                },
            }
        raise AssertionError(f"unexpected request: {path} admin_key={admin_key}")


def test_config_from_env_requires_basic_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONF_BASE_URL", raising=False)
    monkeypatch.delenv("ATLASSIAN_EMAIL", raising=False)
    monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="CONF_BASE_URL"):
        config_from_env([])


def test_config_from_env_builds_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONF_BASE_URL", "https://example.atlassian.net/wiki")
    monkeypatch.setenv("ATLASSIAN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret-token")
    monkeypatch.setenv("CONFLUENCE_SMOKE_PAGE_ID", "123")

    config = config_from_env(["--limit", "10"])

    assert config.base_url == "https://example.atlassian.net/wiki"
    assert config.email == "admin@example.com"
    assert config.api_token == "secret-token"
    assert config.limit == 10
    assert config.sample_page_id == "123"


def test_run_smoke_compares_normal_and_admin_key_visibility() -> None:
    result = run_smoke(
        SmokeConfig(
            base_url="https://example.atlassian.net/wiki",
            email="admin@example.com",
            api_token="secret-token",
        ),
        client=FakeConfluenceClient(),
    )

    assert result.normal_count == 2
    assert result.admin_count == 3
    assert result.admin_only_page_ids == ["3"]
    assert result.sample_page_id == "3"
    assert result.sample_title == "restricted"
    assert result.normal_sample_status == 404
    assert result.admin_sample_status == 200
    assert result.restriction_user_count == 1
    assert result.restriction_group_count == 1
