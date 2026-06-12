"""수집 HTTP API 라우트 회귀 — POST /ml/ingest + status + health.

작성자 : 이영훈
담당 영역 : ai-agent

본 테스트는 api-spec v2.4.0 §2-2/§2-3/§2-4-2 계약을 검증한다.
- POST /ml/ingest → jobId 발급 + status=STARTED + startedAt(KST), 백그라운드 크롤 후 COMPLETED.
- GET /ml/ingest/status/{jobId} → jobId/status/totalPages/processedPages/failedPages/startedAt.
- GET /ml/ingest/health → {"status": "UP"}.

크롤 러너는 stub 으로 주입해(외부 컨테이너·샘플 파일 의존 없이) 잡 카운트 집계만 결정론적으로
검증한다. ASGITransport 는 응답 완료 전에 BackgroundTasks 를 끝내므로 POST 직후 상태 조회 시
이미 COMPLETED 다.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.api.ingest_deps import IngestDeps
from app.api.ingest_routes import get_deps
from app.api.main import create_app
from app.ingestion.crawler import CrawlRequest, CrawlResult
from app.ingestion.credentials import AdminConfluenceCredential, CredentialResolver
from app.ingestion.sync import DeltaSyncRequest, DeltaSyncResult
from app.schemas.enums import IngestJobStatus
from app.storage.ingest_jobs import InMemoryIngestJobStore


class _RecordingCompletionPublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events = []

    def publish(self, event) -> None:  # type: ignore[no-untyped-def]
        self.events.append(event)
        if self.fail:
            raise RuntimeError("rabbitmq unavailable")


def _stub_deps(
    *,
    completion_publisher: _RecordingCompletionPublisher | None = None,
    fail_crawl: bool = False,
    credential_resolver: CredentialResolver | None = None,
    seen_crawl_requests: list[CrawlRequest] | None = None,
    seen_delta_requests: list[DeltaSyncRequest] | None = None,
) -> IngestDeps:
    """stub 크롤 러너(3 성공 + 1 실패)를 가진 IngestDeps — 카운트 집계 결정론."""

    def _run_crawl(request: CrawlRequest) -> CrawlResult:
        if seen_crawl_requests is not None:
            seen_crawl_requests.append(request)
        if fail_crawl:
            raise RuntimeError("crawl failed")
        return CrawlResult(
            space_key=request.space_key,
            pages_collected=3,
            failed_page_ids=["p-bad"],
        )

    def _run_delta(request: DeltaSyncRequest) -> DeltaSyncResult:
        if seen_delta_requests is not None:
            seen_delta_requests.append(request)
        return DeltaSyncResult(
            changed_pages=2,
            deleted_candidate_page_ids=["p-deleted"],
            failed_items=1,
        )

    return IngestDeps(
        job_store=InMemoryIngestJobStore(),
        run_crawl=_run_crawl,
        run_delta=_run_delta,
        previous_snapshot_path="/tmp/previous_snapshot.json",
        completion_publisher=completion_publisher,
        credential_resolver=credential_resolver,
    )


def _client(deps: IngestDeps) -> httpx.AsyncClient:
    """ASGITransport 클라이언트 — get_deps 를 stub 으로 override(lifespan 우회)."""
    app = create_app()
    app.dependency_overrides[get_deps] = lambda: deps
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_ingest_health_returns_up() -> None:
    """api-spec v2.2.0 §2-4-2 — GET /ml/ingest/health → {"status": "UP"}."""
    async with _client(_stub_deps()) as client:
        resp = await client.get("/ml/ingest/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "UP"}


@pytest.mark.asyncio
async def test_ingest_trigger_then_status_completed() -> None:
    """POST /ml/ingest → STARTED + jobId, 백그라운드 완료 후 status=COMPLETED + 카운트 집계."""
    deps = _stub_deps()
    async with _client(deps) as client:
        resp = await client.post("/ml/ingest", json={"mode": "full"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "STARTED"
        assert body["jobId"].startswith("job-")
        assert body["startedAt"].endswith("+09:00")  # KST 절대 전환
        job_id = body["jobId"]

        # ASGITransport 는 응답 완료 전 BackgroundTasks 를 끝내므로 이미 COMPLETED.
        status_resp = await client.get(f"/ml/ingest/status/{job_id}")
    assert status_resp.status_code == 200
    status = status_resp.json()
    assert status["jobId"] == job_id
    assert status["status"] == "COMPLETED"
    assert status["totalPages"] == 4  # 3 성공 + 1 실패
    assert status["processedPages"] == 3
    assert status["failedPages"] == 1
    assert status["startedAt"].endswith("+09:00")


@pytest.mark.asyncio
async def test_ingest_uses_bff_job_id_and_retries_are_idempotent() -> None:
    """api-spec v2.6.x — BFF 가 보낸 jobId 를 유지하고 같은 jobId 재요청은 기존 상태 반환."""
    deps = _stub_deps()
    async with _client(deps) as client:
        first = await client.post("/ml/ingest", json={"jobId": "job-bff-001", "mode": "full"})
        second = await client.post("/ml/ingest", json={"jobId": "job-bff-001", "mode": "full"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["jobId"] == "job-bff-001"
    assert second.json()["jobId"] == "job-bff-001"
    assert second.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_ingest_full_completion_publishes_rabbitmq_completion_event() -> None:
    """Full 수집 완료 후 ML은 RabbitMQ completion event를 발행한다."""
    publisher = _RecordingCompletionPublisher()
    deps = _stub_deps(completion_publisher=publisher)

    async with _client(deps) as client:
        resp = await client.post(
            "/ml/ingest",
            json={
                "mode": "full",
                "adminUserId": "712020:admin",
                "accessToken": "token-secret",
                "cloudId": "cloud-1",
            },
        )

    assert resp.status_code == 200
    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.job_id == resp.json()["jobId"]
    assert event.mode == "full"
    assert event.status is IngestJobStatus.COMPLETED
    assert event.admin_user_id == "712020:admin"
    assert event.message is None
    payload = event.to_payload()
    assert payload["adminUserId"] == "712020:admin"
    assert "token-secret" not in str(payload)
    assert "cloud-1" not in str(payload)
    assert "accessToken" not in payload
    assert "cloudId" not in payload


@pytest.mark.asyncio
async def test_ingest_full_resolves_admin_credential_before_crawl() -> None:
    """adminUserId만 받은 운영 경로는 auth-server credential을 내부 request에만 주입한다."""
    publisher = _RecordingCompletionPublisher()
    seen_requests: list[CrawlRequest] = []
    resolved_admin_users: list[str] = []

    def _resolve(admin_user_id: str) -> AdminConfluenceCredential:
        resolved_admin_users.append(admin_user_id)
        return AdminConfluenceCredential(
            access_token="admin-oauth-token-secret",
            cloud_id="cloud-tenant-1",
            site_url="https://tenant.atlassian.net",
            expires_at="2026-06-11T20:00:00+09:00",
        )

    deps = _stub_deps(
        completion_publisher=publisher,
        credential_resolver=_resolve,
        seen_crawl_requests=seen_requests,
    )

    async with _client(deps) as client:
        resp = await client.post(
            "/ml/ingest",
            json={"mode": "full", "adminUserId": "712020:admin"},
        )

    assert resp.status_code == 200
    assert resolved_admin_users == ["712020:admin"]
    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert request.use_admin_key is False
    assert request.access_token == "admin-oauth-token-secret"
    assert request.site_url == "https://tenant.atlassian.net"
    assert request.cloud_id == "cloud-tenant-1"

    payload = publisher.events[0].to_payload()
    assert payload["adminUserId"] == "712020:admin"
    assert "admin-oauth-token-secret" not in str(payload)
    assert "https://tenant.atlassian.net" not in str(payload)
    assert "cloud-tenant-1" not in str(payload)


@pytest.mark.asyncio
async def test_ingest_failure_still_publishes_completion_event() -> None:
    """수집 실패도 terminal 상태이므로 completion event를 발행한다."""
    publisher = _RecordingCompletionPublisher()
    deps = _stub_deps(completion_publisher=publisher, fail_crawl=True)

    async with _client(deps) as client:
        resp = await client.post(
            "/ml/ingest",
            json={"mode": "full", "adminUserId": "712020:admin"},
        )
        job_id = resp.json()["jobId"]
        status_resp = await client.get(f"/ml/ingest/status/{job_id}")

    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "FAILED"
    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.job_id == job_id
    assert event.status is IngestJobStatus.FAILED
    assert event.admin_user_id == "712020:admin"
    assert event.error_code == "INGEST_FAILED"
    assert event.message == "crawl failed"


@pytest.mark.asyncio
async def test_completion_event_publish_failure_does_not_mask_completed_status() -> None:
    """completion event 발행 실패는 job terminal 상태를 덮어쓰지 않는다."""
    publisher = _RecordingCompletionPublisher(fail=True)
    deps = _stub_deps(completion_publisher=publisher)

    async with _client(deps) as client:
        resp = await client.post("/ml/ingest", json={"mode": "full"})
        job_id = resp.json()["jobId"]
        status_resp = await client.get(f"/ml/ingest/status/{job_id}")

    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "COMPLETED"
    assert len(publisher.events) == 1


@pytest.mark.asyncio
async def test_ingest_delta_mode_uses_delta_runner_and_counts_changed_deleted_failed() -> None:
    """mode=delta 는 Data Sync runner 를 호출하고 변경/삭제후보/실패 집계를 status 에 반영한다."""
    deps = _stub_deps()
    async with _client(deps) as client:
        resp = await client.post(
            "/ml/ingest",
            json={
                "mode": "delta",
                "accessToken": "token-synthetic",
                "cloudId": "cloud-synthetic",
            },
        )
        assert resp.status_code == 200
        job_id = resp.json()["jobId"]

        status_resp = await client.get(f"/ml/ingest/status/{job_id}")

    assert status_resp.status_code == 200
    status = status_resp.json()
    assert status["status"] == "COMPLETED"
    assert status["totalPages"] == 4  # 2 changed + 1 deleted candidate + 1 failed
    assert status["processedPages"] == 3  # changed + deleted candidate
    assert status["failedPages"] == 1


@pytest.mark.asyncio
async def test_ingest_delta_completion_publishes_completion_event() -> None:
    """Delta 수집 완료 후에도 completion event를 발행한다."""
    publisher = _RecordingCompletionPublisher()
    deps = _stub_deps(completion_publisher=publisher)

    async with _client(deps) as client:
        resp = await client.post(
            "/ml/ingest",
            json={"mode": "delta", "adminUserId": "712020:admin"},
        )

    assert resp.status_code == 200
    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.job_id == resp.json()["jobId"]
    assert event.mode == "delta"
    assert event.status is IngestJobStatus.COMPLETED
    assert event.admin_user_id == "712020:admin"


@pytest.mark.asyncio
async def test_ingest_delta_resolves_admin_credential_before_sync() -> None:
    """delta 경로도 full과 동일한 auth-server credential seam을 사용한다."""
    seen_requests: list[DeltaSyncRequest] = []

    def _resolve(admin_user_id: str) -> AdminConfluenceCredential:
        assert admin_user_id == "712020:admin"
        return AdminConfluenceCredential(
            access_token="admin-oauth-token-secret",
            cloud_id="cloud-tenant-1",
            site_url="https://tenant.atlassian.net",
        )

    deps = _stub_deps(credential_resolver=_resolve, seen_delta_requests=seen_requests)

    async with _client(deps) as client:
        resp = await client.post(
            "/ml/ingest",
            json={"mode": "delta", "adminUserId": "712020:admin"},
        )

    assert resp.status_code == 200
    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert request.use_admin_key is False
    assert request.access_token == "admin-oauth-token-secret"
    assert request.site_url == "https://tenant.atlassian.net"
    assert request.cloud_id == "cloud-tenant-1"


@pytest.mark.asyncio
async def test_ingest_status_unknown_job_returns_404_envelope() -> None:
    """존재하지 않는 jobId → 4필드 에러 봉투(isSuccess/code/errorCode/message)로 404."""
    async with _client(_stub_deps()) as client:
        resp = await client.get("/ml/ingest/status/job-does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body == {
        "isSuccess": False,
        "code": 404,
        "errorCode": "RESOURCE_NOT_FOUND",
        "message": "수집 작업을 찾을 수 없습니다: job-does-not-exist",
    }


@pytest.mark.asyncio
async def test_ingest_rejects_invalid_mode() -> None:
    """mode 는 full | delta 만 허용 — 그 외 값은 422(Pydantic 검증)."""
    async with _client(_stub_deps()) as client:
        resp = await client.post("/ml/ingest", json={"mode": "bogus"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_accepts_empty_body_no_space_key() -> None:
    """api-spec v2.4.0 §2-2 — spaceKey 제거. 빈 본문도 mode 기본 full 로 허용한다."""
    async with _client(_stub_deps()) as client:
        resp = await client.post("/ml/ingest", json={})
    assert resp.status_code == 200
