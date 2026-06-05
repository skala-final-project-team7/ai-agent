"""Temporary Confluence Basic Auth smoke for Admin Key ACL checks.

This script is intentionally separate from the production ingestion adapter. The production
path expects an OAuth access token from BFF/Auth Server. Use this smoke only while the backend
OAuth flow is not ready, to verify real Confluence page visibility and restriction metadata.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class JsonClient(Protocol):
    def get_json(self, path: str, *, admin_key: bool = False) -> dict[str, Any]:
        """Return JSON for a Confluence path."""


@dataclass(frozen=True)
class SmokeConfig:
    base_url: str
    email: str
    api_token: str
    limit: int = 250
    sample_page_id: str | None = None


@dataclass(frozen=True)
class SmokeResult:
    normal_count: int
    admin_count: int
    admin_only_page_ids: list[str]
    sample_page_id: str | None
    sample_title: str | None
    normal_sample_status: int | None
    admin_sample_status: int | None
    restriction_user_count: int | None
    restriction_group_count: int | None


class ConfluenceBasicClient:
    def __init__(self, config: SmokeConfig) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._client = httpx.Client(
            auth=(config.email, config.api_token),
            headers={"Accept": "application/json"},
            timeout=30,
        )

    def close(self) -> None:
        self._client.close()

    def get_json(self, path: str, *, admin_key: bool = False) -> dict[str, Any]:
        headers = {"Atl-Confluence-With-Admin-Key": "true"} if admin_key else None
        response = self._client.get(f"{self._base_url}{path}", headers=headers)
        return {
            "status_code": response.status_code,
            "json": response.json() if response.content else None,
        }


def config_from_env(argv: list[str] | None = None) -> SmokeConfig:
    args = parse_args(argv)
    missing = [
        name
        for name in ("CONF_BASE_URL", "ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN")
        if not os.getenv(name)
    ]
    if missing:
        raise RuntimeError(
            "missing required environment variables: "
            + ", ".join(missing)
            + "\nSet them in your shell before running this temporary smoke.",
        )

    sample_page_id = args.sample_page_id or os.getenv("CONFLUENCE_SMOKE_PAGE_ID") or None
    return SmokeConfig(
        base_url=os.environ["CONF_BASE_URL"],
        email=os.environ["ATLASSIAN_EMAIL"],
        api_token=os.environ["ATLASSIAN_API_TOKEN"],
        limit=args.limit,
        sample_page_id=sample_page_id,
    )


def run_smoke(config: SmokeConfig, *, client: JsonClient | None = None) -> SmokeResult:
    owned_client: ConfluenceBasicClient | None = None
    if client is None:
        owned_client = ConfluenceBasicClient(config)
        client = owned_client

    try:
        normal_pages = _get_pages(client, limit=config.limit, admin_key=False)
        admin_pages = _get_pages(client, limit=config.limit, admin_key=True)
        normal_ids = {str(page["id"]) for page in normal_pages}
        admin_ids = {str(page["id"]) for page in admin_pages}
        admin_only_ids = sorted(admin_ids - normal_ids)

        sample_page_id = config.sample_page_id or (admin_only_ids[0] if admin_only_ids else None)
        sample_title: str | None = None
        normal_sample_status: int | None = None
        admin_sample_status: int | None = None
        restriction_user_count: int | None = None
        restriction_group_count: int | None = None

        if sample_page_id:
            normal_page = client.get_json(
                f"/api/v2/pages/{sample_page_id}?body-format=storage",
                admin_key=False,
            )
            admin_page = client.get_json(
                f"/api/v2/pages/{sample_page_id}?body-format=storage",
                admin_key=True,
            )
            normal_sample_status = int(normal_page["status_code"])
            admin_sample_status = int(admin_page["status_code"])
            if admin_sample_status == 200 and isinstance(admin_page["json"], dict):
                sample_title = admin_page["json"].get("title")

            restrictions = client.get_json(
                f"/rest/api/content/{sample_page_id}/restriction/byOperation/read",
                admin_key=True,
            )
            if restrictions["status_code"] == 200 and isinstance(restrictions["json"], dict):
                user_restrictions = (
                    restrictions["json"].get("restrictions", {}).get("user", {}).get("results", [])
                )
                group_restrictions = (
                    restrictions["json"].get("restrictions", {}).get("group", {}).get("results", [])
                )
                restriction_user_count = len(user_restrictions)
                restriction_group_count = len(group_restrictions)

        return SmokeResult(
            normal_count=len(normal_pages),
            admin_count=len(admin_pages),
            admin_only_page_ids=admin_only_ids,
            sample_page_id=sample_page_id,
            sample_title=sample_title,
            normal_sample_status=normal_sample_status,
            admin_sample_status=admin_sample_status,
            restriction_user_count=restriction_user_count,
            restriction_group_count=restriction_group_count,
        )
    finally:
        if owned_client is not None:
            owned_client.close()


def _get_pages(client: JsonClient, *, limit: int, admin_key: bool) -> list[dict[str, Any]]:
    response = client.get_json(
        f"/api/v2/pages?limit={limit}&body-format=storage",
        admin_key=admin_key,
    )
    if response["status_code"] != 200:
        mode = "admin-key" if admin_key else "normal"
        raise RuntimeError(f"{mode} page list failed: HTTP {response['status_code']}")
    payload = response["json"]
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise RuntimeError("unexpected Confluence pages response shape")
    return payload["results"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Temporary Confluence Basic Auth/Admin Key smoke.",
    )
    parser.add_argument("--limit", type=int, default=250, help="Page list limit. Default: 250")
    parser.add_argument(
        "--sample-page-id",
        default=None,
        help="Optional page id to compare normal vs Admin Key access.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        result = run_smoke(config_from_env(argv))
    except Exception as exc:
        print(f"[confluence-smoke] failed: {exc}", file=sys.stderr)
        return 1

    print("[confluence-smoke] completed")
    print(f"[confluence-smoke] normal_pages={result.normal_count}")
    print(f"[confluence-smoke] admin_key_pages={result.admin_count}")
    print(f"[confluence-smoke] admin_only_pages={len(result.admin_only_page_ids)}")
    if result.admin_only_page_ids:
        print("[confluence-smoke] admin_only_page_ids=" + ",".join(result.admin_only_page_ids))
    if result.sample_page_id:
        print(
            "[confluence-smoke] sample="
            f"id:{result.sample_page_id} "
            f"title:{result.sample_title or ''} "
            f"normal_status:{result.normal_sample_status} "
            f"admin_status:{result.admin_sample_status} "
            f"read_users:{result.restriction_user_count} "
            f"read_groups:{result.restriction_group_count}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
