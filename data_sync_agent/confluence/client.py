"""data_sync_agent/confluence/client.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

"""
--------------------------------------------------
작성자 : 이영훈
작성목적 : Data Sync Agent Confluence metadata API client 구현.
          Space 목록과 Space별 Page metadata 수집, pagination, retry/error 분류를 담당한다.
작성일 : 2026-05-15
변경사항 내역 (날짜, 변경목적, 변경내용 순)
  - 2026-05-15, 최초 작성, feature3 metadata client와 fakeable transport 구현
--------------------------------------------------
[호환성]
  - Python 3.11.x 권장
  - 표준 라이브러리 urllib 기반 기본 transport
--------------------------------------------------
"""

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from data_sync_agent.config import DataSyncConfig
from data_sync_agent.schemas import PageSnapshotItem

DEFAULT_PAGE_LIMIT = 25
CONFLUENCE_API_ORIGIN = "https://api.atlassian.com"


@dataclass(frozen=True, slots=True)
class ConfluenceRequest:
    """Transport가 수행할 Confluence HTTP request."""

    method: str
    url: str
    headers: dict[str, str] = field(repr=False)
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ConfluenceResponse:
    """Transport가 반환하는 최소 HTTP response."""

    status_code: int
    json_body: dict[str, Any]


class ConfluenceTransport(Protocol):
    """Confluence request를 수행하는 transport protocol."""

    def send(self, request: ConfluenceRequest) -> ConfluenceResponse:
        """HTTP request를 수행하고 response를 반환한다."""


class ConfluenceApiError(RuntimeError):
    """Confluence API 실패를 안전하게 표현하는 예외."""

    def __init__(
        self,
        *,
        status_code: int | None,
        error_type: str,
        message: str,
        retryable: bool,
        item_level: bool,
        attempt_count: int,
    ) -> None:
        self.status_code = status_code
        self.error_type = error_type
        self.retryable = retryable
        self.item_level = item_level
        self.attempt_count = attempt_count
        super().__init__(
            "Confluence API request failed "
            f"(status_code={status_code}, error_type={error_type}, "
            f"retryable={retryable}, item_level={item_level}, "
            f"attempt_count={attempt_count}): {message}"
        )


class UrllibConfluenceTransport:
    """urllib 기반 기본 transport.

    Unit test는 fake transport를 사용하므로 실제 네트워크 호출을 수행하지 않는다.
    """

    def send(self, request: ConfluenceRequest) -> ConfluenceResponse:
        """Confluence HTTP request를 수행한다."""
        urllib_request = Request(
            request.url,
            headers=request.headers,
            method=request.method,
        )
        try:
            with urlopen(urllib_request, timeout=request.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                return ConfluenceResponse(
                    status_code=response.status,
                    json_body=json.loads(body) if body else {},
                )
        except HTTPError as error:
            body = error.read().decode("utf-8")
            return ConfluenceResponse(
                status_code=error.code,
                json_body=json.loads(body) if body else {},
            )
        except TimeoutError:
            raise
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise error.reason
            raise TimeoutError("Confluence request failed before response") from error


class ConfluenceMetadataClient:
    """Confluence API v2 metadata client.

    Space 목록, Space별 Page metadata 목록, changed page detail 조회 interface를
    제공한다. Diff 계산과 changed document 처리는 후속 feature의 책임이다.
    """

    def __init__(
        self,
        *,
        config: DataSyncConfig,
        transport: ConfluenceTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibConfluenceTransport()
        self.sleeper = sleeper
        if config.use_admin_key:
            self.base_url = f"{config.site_url.rstrip('/')}/wiki/api/v2"
        else:
            self.base_url = (
                f"{CONFLUENCE_API_ORIGIN}/ex/confluence/{config.cloud_id}/wiki/api/v2"
            )

    def list_spaces(self) -> list[dict[str, Any]]:
        """접근 가능한 Confluence Space 목록을 pagination 처리해 반환한다."""
        return self._get_paginated("/spaces", {"limit": DEFAULT_PAGE_LIMIT})

    def list_space_pages(self, space_id: str) -> list[dict[str, Any]]:
        """Space 내 Page metadata 목록을 pagination 처리해 반환한다."""
        if not space_id:
            raise ValueError("space_id is required")
        return self._get_paginated(
            f"/spaces/{space_id}/pages",
            {"limit": DEFAULT_PAGE_LIMIT, "body-format": "storage"},
        )

    def get_page_detail(self, page_id: str) -> dict[str, Any]:
        """Changed page processing feature에서 사용할 Page 상세 조회 interface."""
        if not page_id:
            raise ValueError("page_id is required")
        return self._request_json(
            f"/pages/{page_id}",
            {"body-format": "storage", "include-version": "true"},
        )

    def _get_paginated(
        self,
        path: str,
        query: dict[str, str | int],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_path_or_url: str | None = self._build_path_with_query(path, query)

        while next_path_or_url:
            response_body = self._request_json(next_path_or_url)
            results = response_body.get("results", [])
            if not isinstance(results, list):
                raise ConfluenceApiError(
                    status_code=None,
                    error_type="invalid_response",
                    message="Paginated response results must be a list",
                    retryable=False,
                    item_level=False,
                    attempt_count=1,
                )
            items.extend(results)
            next_path_or_url = response_body.get("_links", {}).get("next")

        return items

    def _request_json(
        self,
        path_or_url: str,
        query: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        url = self._build_url(path_or_url, query)
        attempt_count = 0
        last_retryable_response: ConfluenceResponse | None = None

        while attempt_count <= self.config.max_retries:
            attempt_count += 1
            request = ConfluenceRequest(
                method="GET",
                url=url,
                headers=self._headers(),
                timeout_seconds=self.config.timeout_seconds,
            )
            try:
                response = self.transport.send(request)
            except TimeoutError:
                if attempt_count > self.config.max_retries:
                    raise ConfluenceApiError(
                        status_code=None,
                        error_type="retry_exhausted",
                        message="Confluence request timed out after retries",
                        retryable=True,
                        item_level=False,
                        attempt_count=attempt_count,
                    ) from None
                self._sleep_before_retry(attempt_count)
                continue

            if 200 <= response.status_code < 300:
                return response.json_body

            error_classification = self._classify_response(response.status_code)
            if not error_classification.retryable:
                raise self._api_error(
                    response=response,
                    error_type=error_classification.error_type,
                    retryable=False,
                    item_level=error_classification.item_level,
                    attempt_count=attempt_count,
                )

            last_retryable_response = response
            if attempt_count > self.config.max_retries:
                break
            self._sleep_before_retry(attempt_count)

        if last_retryable_response is None:
            raise ConfluenceApiError(
                status_code=None,
                error_type="retry_exhausted",
                message="Confluence request exhausted retries",
                retryable=True,
                item_level=False,
                attempt_count=attempt_count,
            )

        raise self._api_error(
            response=last_retryable_response,
            error_type="retry_exhausted",
            retryable=True,
            item_level=False,
            attempt_count=attempt_count,
        )

    def _headers(self) -> dict[str, str]:
        if self.config.use_admin_key:
            raw = f"{self.config.admin_email}:{self.config.admin_api_token}".encode()
            return {
                "Accept": "application/json",
                "Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}",
                "Atl-Confluence-With-Admin-Key": "true",
            }
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.access_token}",
        }

    def _build_url(
        self,
        path_or_url: str,
        query: dict[str, str | int] | None = None,
    ) -> str:
        if path_or_url.startswith("https://"):
            return path_or_url

        path_with_query = self._build_path_with_query(path_or_url, query or {})
        if self.config.use_admin_key:
            site_url = self.config.site_url.rstrip("/")
            if path_with_query.startswith("/wiki/"):
                return f"{site_url}{path_with_query}"
            if path_with_query.startswith("/rest/api/"):
                return f"{site_url}/wiki{path_with_query}"
            return f"{self.base_url}{path_with_query}"
        if path_with_query.startswith("/wiki/api/v2/"):
            return urljoin(CONFLUENCE_API_ORIGIN, path_with_query)
        return f"{self.base_url}{path_with_query}"

    @staticmethod
    def _build_path_with_query(path: str, query: dict[str, str | int]) -> str:
        if not query:
            return path
        return f"{path}?{urlencode(query)}"

    def _sleep_before_retry(self, attempt_count: int) -> None:
        delay_seconds = self.config.request_delay_seconds * attempt_count
        if delay_seconds > 0:
            self.sleeper(delay_seconds)

    def _api_error(
        self,
        *,
        response: ConfluenceResponse,
        error_type: str,
        retryable: bool,
        item_level: bool,
        attempt_count: int,
    ) -> ConfluenceApiError:
        return ConfluenceApiError(
            status_code=response.status_code,
            error_type=error_type,
            message=self._safe_error_message(response),
            retryable=retryable,
            item_level=item_level,
            attempt_count=attempt_count,
        )

    def _safe_error_message(self, response: ConfluenceResponse) -> str:
        raw_message = response.json_body.get("message")
        if not isinstance(raw_message, str) or not raw_message:
            return "Confluence API returned an error"
        safe_message = raw_message
        if self.config.access_token:
            safe_message = safe_message.replace(self.config.access_token, "<redacted>")
        return (
            safe_message.replace("Authorization", "<redacted-header>")
            .replace("Bearer", "<redacted-auth-scheme>")
        )

    @staticmethod
    def _classify_response(status_code: int) -> "_ErrorClassification":
        if status_code == 401:
            return _ErrorClassification(
                error_type="auth_failure",
                retryable=False,
                item_level=False,
            )
        if status_code == 403:
            return _ErrorClassification(
                error_type="permission_failure",
                retryable=False,
                item_level=True,
            )
        if status_code == 404:
            return _ErrorClassification(
                error_type="item_not_found",
                retryable=False,
                item_level=True,
            )
        if status_code == 429 or status_code >= 500:
            return _ErrorClassification(
                error_type="retryable_http_error",
                retryable=True,
                item_level=False,
            )
        if status_code == 400:
            return _ErrorClassification(
                error_type="bad_request",
                retryable=False,
                item_level=False,
            )
        return _ErrorClassification(
            error_type="http_error",
            retryable=False,
            item_level=False,
        )


def map_page_metadata_to_snapshot_item(
    page: dict[str, Any],
    *,
    space: dict[str, Any],
    cloud_id: str,
) -> PageSnapshotItem:
    """Confluence Page metadata response를 PageSnapshotItem schema로 변환한다."""
    version = page.get("version") or {}
    last_modified_at = (
        page.get("lastModifiedAt")
        or version.get("createdAt")
        or version.get("created_at")
        or ""
    )
    page_url = _page_url(page)
    return PageSnapshotItem(
        cloud_id=cloud_id,
        space_id=str(space["id"]),
        space_key=str(space.get("key") or ""),
        space_name=str(space.get("name") or ""),
        page_id=str(page["id"]),
        title=str(page.get("title") or ""),
        status=str(page.get("status") or "current"),
        page_url=page_url,
        last_modified_at=str(last_modified_at),
        version_number=int(version.get("number", page.get("version_number", -1))),
    )


def _page_url(page: dict[str, Any]) -> str:
    links = page.get("_links")
    if isinstance(links, dict):
        webui = links.get("webui")
        if isinstance(webui, str) and webui:
            return webui
    return str(page.get("page_url") or page.get("url") or "")


@dataclass(frozen=True, slots=True)
class _ErrorClassification:
    error_type: str
    retryable: bool
    item_level: bool
