"""수집 HTTP API 라우트 회귀 — POST /ml/ingest + status + health.

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
from app.ingestion.sync import DeltaSyncRequest, DeltaSyncResult
from app.schemas.enums import IngestJobStatus
from app.storage.ingest_jobs import InMemoryIngestJobStore


class _RecordingAdminKeyRevokeNotifier:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requests = []

    def notify(self, request) -> None:  # type: ignore[no-untyped-def]
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("bff unavailable")


def _stub_deps(
    *,
    notifier: _RecordingAdminKeyRevokeNotifier | None = None,
    fail_crawl: bool = False,
) -> IngestDeps:
    """stub 크롤 러너(3 성공 + 1 실패)를 가진 IngestDeps — 카운트 집계 결정론."""

    def _run_crawl(request: CrawlRequest) -> CrawlResult:
        if fail_crawl:
            raise RuntimeError("crawl failed")
        return CrawlResult(
            space_key=request.space_key,
            pages_collected=3,
            failed_page_ids=["p-bad"],
        )

    def _run_delta(request: DeltaSyncRequest) -> DeltaSyncResult:
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
        admin_key_revoke_notifier=notifier,
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
async def test_ingest_full_completion_notifies_bff_admin_key_revoke() -> None:
    """Full 수집 완료 후 ML은 BFF에 Admin Key revoke 요청을 보낸다."""
    notifier = _RecordingAdminKeyRevokeNotifier()
    deps = _stub_deps(notifier=notifier)

    async with _client(deps) as client:
        resp = await client.post(
            "/ml/ingest",
            json={"mode": "full", "accessToken": "token-secret", "cloudId": "cloud-1"},
        )

    assert resp.status_code == 200
    assert len(notifier.requests) == 1
    request = notifier.requests[0]
    assert request.job_id == resp.json()["jobId"]
    assert request.mode == "full"
    assert request.status is IngestJobStatus.COMPLETED
    assert request.cloud_id == "cloud-1"
    assert request.error is None
    assert "token-secret" not in str(request.to_payload())


@pytest.mark.asyncio
async def test_ingest_failure_still_notifies_bff_admin_key_revoke() -> None:
    """수집 실패도 terminal 상태이므로 BFF revoke 요청을 보낸다."""
    notifier = _RecordingAdminKeyRevokeNotifier()
    deps = _stub_deps(notifier=notifier, fail_crawl=True)

    async with _client(deps) as client:
        resp = await client.post(
            "/ml/ingest",
            json={"mode": "full", "accessToken": "token-secret", "cloudId": "cloud-2"},
        )
        job_id = resp.json()["jobId"]
        status_resp = await client.get(f"/ml/ingest/status/{job_id}")

    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "FAILED"
    assert len(notifier.requests) == 1
    request = notifier.requests[0]
    assert request.job_id == job_id
    assert request.status is IngestJobStatus.FAILED
    assert request.cloud_id == "cloud-2"
    assert request.error == "crawl failed"


@pytest.mark.asyncio
async def test_admin_key_revoke_failure_does_not_mask_completed_status() -> None:
    """BFF revoke callback 실패는 job terminal 상태를 덮어쓰지 않는다."""
    notifier = _RecordingAdminKeyRevokeNotifier(fail=True)
    deps = _stub_deps(notifier=notifier)

    async with _client(deps) as client:
        resp = await client.post("/ml/ingest", json={"mode": "full"})
        job_id = resp.json()["jobId"]
        status_resp = await client.get(f"/ml/ingest/status/{job_id}")

    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "COMPLETED"
    assert len(notifier.requests) == 1


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
async def test_ingest_delta_completion_notifies_bff_admin_key_revoke() -> None:
    """Delta 수집 완료 후에도 BFF Admin Key revoke callback을 호출한다."""
    notifier = _RecordingAdminKeyRevokeNotifier()
    deps = _stub_deps(notifier=notifier)

    async with _client(deps) as client:
        resp = await client.post(
            "/ml/ingest",
            json={"mode": "delta", "accessToken": "token-secret", "cloudId": "cloud-delta"},
        )

    assert resp.status_code == 200
    assert len(notifier.requests) == 1
    request = notifier.requests[0]
    assert request.job_id == resp.json()["jobId"]
    assert request.mode == "delta"
    assert request.status is IngestJobStatus.COMPLETED
    assert request.cloud_id == "cloud-delta"


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
