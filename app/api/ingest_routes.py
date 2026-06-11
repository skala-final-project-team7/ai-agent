"""수집 HTTP API 라우트 — POST /ml/ingest + status + health [Pipeline].

--------------------------------------------------
작성자 : 최태성
작성목적 : api-spec v2.2.0 §2-2/§2-3/§2-4-2 의 수집(Data Ingestion) HTTP 계약을 제공한다.
          ``POST /ml/ingest`` 는 잡을 생성(``STARTED``)하고 백그라운드에서 crawl→chunk→
          upsert 를 실행하며, ``GET /ml/ingest/status/{jobId}`` 가 진행 상태·집계 카운트를,
          ``GET /ml/ingest/health`` 가 서버 가용성을 반환한다. 응답은 BFF 가 공통 Wrapper 로
          감싸므로 ML 은 **data 객체를 그대로(unwrapped)** 반환한다(§2-3 "외부 API data 동일",
          §2-4 health 선례와 정합).
작성일 : 2026-05-29 (api-spec v2.2.0 §2-2/§2-3/§2-4-2)
변경사항 내역 (날짜, 변경목적, 변경내용 순)
  - 2026-05-29, 최초 작성 — IngestRequest(spaceKey/mode/accessToken/cloudId) + POST 트리거
    (BackgroundTasks 로 비동기 크롤) + status 조회(KST startedAt) + health.
  - 2026-06-05, api-spec v2.4.0 정합 — IngestRequest 에서 spaceKey 제거.
  - 2026-06-05, api-spec v2.5.0 정합 — Admin Key 말소 트리거를 BFF HTTP callback 에서
    RabbitMQ completion event 로 전환. adminUserId 를 preferred job 식별자로 추가하고,
    accessToken/cloudId 직접 전달은 legacy PoC 호환 필드로만 유지.
  - 2026-06-11, api-spec v2.6.1 정합 — BFF 생성 jobId 수용/idempotent 재요청 처리.
  - 2026-06-11, api-spec v2.6.2 정합 — auth-server credential lookup 응답을
    accessToken/cloudId/siteUrl 모델로 정정(siteUrl은 출처 URL 정규화용).
--------------------------------------------------
[보안] 요청 ``accessToken``/``cloudId`` 는 로그·응답 본문에 남기지 않는다(루트 CLAUDE.md
       보안 규칙). 상태 응답에도 토큰 관련 필드를 포함하지 않는다.
[호환성]
  - Python 3.11.x, FastAPI 0.111+
--------------------------------------------------
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.ingest_completion import IngestCompletionEvent, publish_ingest_completion_safely
from app.api.ingest_deps import IngestDeps
from app.ingestion.crawler import CrawlRequest
from app.ingestion.credentials import AdminConfluenceCredential
from app.ingestion.sync import DeltaSyncRequest
from app.schemas.enums import IngestJobStatus

_LOGGER = logging.getLogger(__name__)

# api-spec "시간 표기 정책" — 응답 timestamp 는 KST(+09:00)로 절대 전환해 반환한다.
_KST = timezone(timedelta(hours=9))

# 허용 수집 모드(api-spec §2-2). full 은 Data Ingestion Agent 기반 crawl 경로,
# delta 는 Data Sync Agent 기반 변경분 재수집 경로로 분기한다.
_ALLOWED_MODES: frozenset[str] = frozenset({"full", "delta"})

router = APIRouter()


def _to_kst(dt: datetime) -> str:
    """UTC(또는 naive) datetime 을 KST(+09:00) ISO 8601 문자열로 변환한다."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(_KST).isoformat()


class IngestRequest(BaseModel):
    """``POST /ml/ingest`` 요청 본문 (api-spec v2.6.2 §2-2).

    Preferred 운영 경로는 RabbitMQ ingest job 또는 HTTP 위임 payload 에 credential set 을 싣지
    않고 ``adminUserId`` 만 전달한다. Data Ingestion Worker 는 auth-server 내부 credential API
    로 콘텐츠 조회용 ``accessToken`` + ``cloudId`` 와 출처 URL 정규화용 ``siteUrl`` 를 조회한다.

    ``accessToken``/``cloudId`` 는 backend OAuth 완성 전 local/PoC smoke 호환 필드로만 남긴다.
    production RabbitMQ job/completion payload 에는 절대 포함하지 않는다.
    """

    model_config = ConfigDict(populate_by_name=True)

    mode: str = Field(default="full", description="수집 모드 — full(전체) | delta(변경분)")
    job_id: str | None = Field(
        default=None,
        alias="jobId",
        description="BFF 생성 작업 식별자. 없으면 Pipeline 이 발급한다.",
    )
    admin_user_id: str | None = Field(
        default=None,
        alias="adminUserId",
        description="Admin Confluence accountId. v2.5 preferred credential lookup key.",
    )
    access_token: str | None = Field(
        default=None,
        alias="accessToken",
        description="Legacy PoC-only Confluence OAuth access token. 로그/큐/응답 금지.",
    )
    cloud_id: str | None = Field(
        default=None,
        alias="cloudId",
        description="Legacy PoC-only Confluence cloudId. RabbitMQ payload 포함 금지.",
    )

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        """mode 는 ``full`` | ``delta`` 만 허용한다(api-spec §2-2)."""
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_MODES:
            raise ValueError(f"mode 는 full | delta 여야 합니다 (받음: {value!r})")
        return normalized


def get_deps(request: Request) -> IngestDeps:
    """FastAPI Depends — lifespan 에서 만든 수집 의존성을 반환한다.

    테스트는 ``app.dependency_overrides[get_deps] = lambda: fake_deps`` 로 교체할 수 있다.
    """
    return request.app.state.ingest_deps


IngestDepsDep = Annotated[IngestDeps, Depends(get_deps)]


def _run_full_ingest_job(deps: IngestDeps, job_id: str, crawl_request: CrawlRequest) -> None:
    """백그라운드 Full Crawl 잡 — 상태를 ``IN_PROGRESS`` 로 올리고 크롤 실행 후 마감한다.

    크롤 성공 시 ``CrawlResult`` 집계로 카운트를 채워 ``COMPLETED`` 로, 예외 시 ``FAILED``
    로 마감한다(예외는 잡 단위로 격리 — 서버 전체로 전파하지 않는다). 토큰은 로그에 남기지
    않는다(``crawl_request`` 전체를 로깅하지 않고 ``job_id`` 만 기록).
    """
    deps.job_store.update(job_id, status=IngestJobStatus.IN_PROGRESS)
    try:
        crawl_request = _resolve_crawl_credentials(deps, crawl_request)
        result = deps.run_crawl(crawl_request)
    except Exception as exc:  # noqa: BLE001 — 크롤/외부 호출 예외 광범위 캐치(잡 단위 격리)
        _LOGGER.exception("ingest job failed: job_id=%s", job_id)
        finished_at = datetime.now(UTC)
        deps.job_store.update(
            job_id,
            status=IngestJobStatus.FAILED,
            finished_at=finished_at,
            error=str(exc),
        )
        _publish_ingest_completion(
            deps,
            job_id=job_id,
            mode="full",
            status=IngestJobStatus.FAILED,
            admin_user_id=crawl_request.admin_user_id,
            error_code="INGEST_FAILED",
            error=str(exc),
            finished_at=finished_at,
        )
        return
    failed = len(result.failed_page_ids)
    finished_at = datetime.now(UTC)
    deps.job_store.update(
        job_id,
        status=IngestJobStatus.COMPLETED,
        total_pages=result.pages_collected + failed,
        processed_pages=result.pages_collected,
        failed_pages=failed,
        finished_at=finished_at,
    )
    _publish_ingest_completion(
        deps,
        job_id=job_id,
        mode="full",
        status=IngestJobStatus.COMPLETED,
        admin_user_id=crawl_request.admin_user_id,
        finished_at=finished_at,
    )


def _run_delta_ingest_job(deps: IngestDeps, job_id: str, delta_request: DeltaSyncRequest) -> None:
    """백그라운드 Delta Sync 잡 — Data Sync Agent wrapper 를 실행하고 상태를 마감한다.

    Delta Sync 결과는 현재 api-spec 의 공통 카운트 필드에 맞춰 집계한다.

    - ``changed_pages``: 변경되어 raw_store 적재 + chunking queue 재투입된 페이지.
    - ``deleted_candidate_page_ids``: 삭제 후보로 감지됐지만 아직 soft_delete 확정 전인 페이지.
    - ``failed_items``: Data Sync Agent 가 실패로 기록한 항목 수.

    상태 조회 필드에는 별도 deletedCandidatePages 필드가 없으므로, ``totalPages`` 는 세 항목의
    합, ``processedPages`` 는 변경 페이지 + 삭제 후보, ``failedPages`` 는 실패 항목 수로 표현한다.
    """
    deps.job_store.update(job_id, status=IngestJobStatus.IN_PROGRESS)
    try:
        delta_request = _resolve_delta_credentials(deps, delta_request)
        result = deps.run_delta(delta_request)
    except Exception as exc:  # noqa: BLE001 — sync/외부 호출 예외는 잡 단위로 격리.
        _LOGGER.exception("delta ingest job failed: job_id=%s", job_id)
        finished_at = datetime.now(UTC)
        deps.job_store.update(
            job_id,
            status=IngestJobStatus.FAILED,
            finished_at=finished_at,
            error=str(exc),
        )
        _publish_ingest_completion(
            deps,
            job_id=job_id,
            mode="delta",
            status=IngestJobStatus.FAILED,
            admin_user_id=delta_request.admin_user_id,
            error_code="INGEST_FAILED",
            error=str(exc),
            finished_at=finished_at,
        )
        return
    deleted_candidates = len(result.deleted_candidate_page_ids)
    finished_at = datetime.now(UTC)
    deps.job_store.update(
        job_id,
        status=IngestJobStatus.COMPLETED,
        total_pages=result.changed_pages + deleted_candidates + result.failed_items,
        processed_pages=result.changed_pages + deleted_candidates,
        failed_pages=result.failed_items,
        finished_at=finished_at,
    )
    _publish_ingest_completion(
        deps,
        job_id=job_id,
        mode="delta",
        status=IngestJobStatus.COMPLETED,
        admin_user_id=delta_request.admin_user_id,
        finished_at=finished_at,
    )


def _publish_ingest_completion(
    deps: IngestDeps,
    *,
    job_id: str,
    mode: str,
    status: IngestJobStatus,
    admin_user_id: str | None,
    finished_at: datetime,
    error_code: str | None = None,
    error: str | None = None,
) -> None:
    """수집 terminal 상태 도달 후 RabbitMQ completion event 를 발행한다.

    api-spec v2.5.0 기준 ML은 Atlassian Admin Key를 직접 말소하지 않고, BFF HTTP callback도
    호출하지 않는다. BFF consumer 가 completion event 를 consume하고 auth-server deactivate
    내부 API 를 호출한다. event payload 에 credential set 은 포함하지 않는다.
    """
    publish_ingest_completion_safely(
        deps.completion_publisher,
        IngestCompletionEvent(
            job_id=job_id,
            mode=mode,
            status=status,
            admin_user_id=admin_user_id,
            error_code=error_code,
            message=error,
            completed_at=finished_at,
        ),
    )


def _resolve_crawl_credentials(deps: IngestDeps, request: CrawlRequest) -> CrawlRequest:
    """Hydrate a full-crawl request with auth-server OAuth credentials when configured."""
    credential = _resolve_admin_credential(deps, request.admin_user_id)
    if credential is None:
        return request
    return replace(
        request,
        access_token=credential.access_token,
        cloud_id=credential.cloud_id,
        site_url=credential.site_url,
    )


def _resolve_delta_credentials(deps: IngestDeps, request: DeltaSyncRequest) -> DeltaSyncRequest:
    """Hydrate a delta-sync request with auth-server OAuth credentials when configured."""
    credential = _resolve_admin_credential(deps, request.admin_user_id)
    if credential is None:
        return request
    return replace(
        request,
        access_token=credential.access_token,
        cloud_id=credential.cloud_id,
        site_url=credential.site_url,
    )


def _resolve_admin_credential(
    deps: IngestDeps,
    admin_user_id: str | None,
) -> AdminConfluenceCredential | None:
    """Resolve auth-server credential by adminUserId without exposing it to payloads/events."""
    if deps.credential_resolver is None or not admin_user_id:
        return None
    return deps.credential_resolver(admin_user_id)


@router.post("/ml/ingest")
async def ingest_route(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    deps: IngestDepsDep,
) -> dict[str, Any]:
    """수집 트리거 (api-spec v2.5.0 §2-2).

    잡을 ``STARTED`` 로 생성하고 백그라운드 태스크로 crawl→chunk→upsert 를 실행한 뒤,
    즉시 ``jobId`` / ``status`` / ``startedAt``(KST)을 반환한다. 진행 상태는
    ``GET /ml/ingest/status/{jobId}`` 로 조회한다. 스페이스 스코프 파라미터는 없으며,
    Admin Key 로 접근 가능한 전체 스페이스를 수집한다.
    """
    if payload.job_id:
        existing = deps.job_store.get(payload.job_id)
        if existing is not None:
            return {
                "jobId": existing.job_id,
                "status": existing.status.value,
                "startedAt": _to_kst(existing.started_at),
            }

    job = deps.job_store.create(job_id=payload.job_id)
    # credential 값은 legacy request 객체에만 전달하고 로그/응답/큐 메시지에 남기지 않는다.
    if payload.mode == "delta":
        delta_request = DeltaSyncRequest(
            previous_snapshot_path=deps.previous_snapshot_path,
            access_token=payload.access_token,
            cloud_id=payload.cloud_id,
            admin_user_id=payload.admin_user_id,
        )
        background_tasks.add_task(_run_delta_ingest_job, deps, job.job_id, delta_request)
    else:
        crawl_request = CrawlRequest(
            access_token=payload.access_token,
            cloud_id=payload.cloud_id,
            admin_user_id=payload.admin_user_id,
        )
        background_tasks.add_task(_run_full_ingest_job, deps, job.job_id, crawl_request)
    return {
        "jobId": job.job_id,
        "status": job.status.value,
        "startedAt": _to_kst(job.started_at),
    }


@router.get("/ml/ingest/status/{job_id}")
async def ingest_status_route(job_id: str, deps: IngestDepsDep) -> Any:
    """수집 상태 조회 (api-spec v2.2.0 §2-3).

    잡을 찾으면 ``jobId`` / ``status`` / ``totalPages`` / ``processedPages`` /
    ``failedPages`` / ``startedAt``(KST)를 반환한다. 없으면 4필드 에러 봉투로 404 응답.
    """
    record = deps.job_store.get(job_id)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={
                "isSuccess": False,
                "code": 404,
                "errorCode": "RESOURCE_NOT_FOUND",
                "message": f"수집 작업을 찾을 수 없습니다: {job_id}",
            },
        )
    return {
        "jobId": record.job_id,
        "status": record.status.value,
        "totalPages": record.total_pages,
        "processedPages": record.processed_pages,
        "failedPages": record.failed_pages,
        "startedAt": _to_kst(record.started_at),
    }


@router.get("/ml/ingest/health")
async def ingest_health() -> dict[str, str]:
    """Data Ingestion Pipeline 헬스체크 (api-spec v2.2.0 §2-4-2).

    BFF 가 수집 서버(Confluence 수집/청킹/임베딩)가 정상 응답 가능한지만 확인하는 용도.
    내부 의존성(Vector DB / Confluence / RabbitMQ 등) 상세 상태는 보고하지 않고, 서버가
    요청을 받아 응답할 수 있는 상태인지만 ``{"status": "UP"}`` 로 알린다(§2-4 공통 규칙).
    """
    return {"status": "UP"}
