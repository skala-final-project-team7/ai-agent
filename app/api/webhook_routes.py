"""Confluence 삭제 Webhook 라우트 — POST /ml/confluence/webhook.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.ingest_routes import IngestDepsDep
from app.ingestion.workers.sync_worker import WebhookDeleteEvent

webhook_router = APIRouter()

_DELETE_EVENTS: frozenset[str] = frozenset(
    {
        "page_removed",
        "page_trashed",
        "blogpost_removed",
        "blogpost_trashed",
        "attachment_removed",
        "attachment_trashed",
        "content_removed",
    }
)
_PAGE_KEYS: tuple[str, ...] = ("page", "blogpost", "blogPost", "content")


def parse_confluence_delete_event(payload: Any) -> WebhookDeleteEvent | None:
    """Confluence webhook payload 에서 삭제 대상 id 를 추출한다."""
    if not isinstance(payload, dict):
        return None
    event = str(payload.get("event") or payload.get("eventType") or "").strip().lower()
    if event not in _DELETE_EVENTS:
        return None

    attachment = payload.get("attachment")
    if isinstance(attachment, dict):
        attachment_id = str(attachment.get("id") or "").strip()
        if attachment_id:
            return WebhookDeleteEvent(attachment_id=attachment_id)

    for key in _PAGE_KEYS:
        obj = payload.get(key)
        if isinstance(obj, dict):
            page_id = str(obj.get("id") or "").strip()
            if page_id:
                return WebhookDeleteEvent(page_id=page_id)

    top_id = str(payload.get("id") or "").strip()
    if top_id:
        if "attachment" in event:
            return WebhookDeleteEvent(attachment_id=top_id)
        return WebhookDeleteEvent(page_id=top_id)
    return None


@webhook_router.post("/ml/confluence/webhook")
async def confluence_webhook_route(request: Request, deps: IngestDepsDep) -> Any:
    """Confluence 삭제 webhook 수신 후 soft-delete 한다."""
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(
            status_code=400,
            content={
                "isSuccess": False,
                "code": 400,
                "errorCode": "INVALID_REQUEST",
                "message": "유효한 JSON 본문이 아닙니다",
            },
        )

    event = parse_confluence_delete_event(payload)
    if event is None or event.is_empty:
        return {"softDeleted": {"pageIds": [], "attachmentIds": []}, "ignored": True}
    if deps.sync_worker is None:
        return JSONResponse(
            status_code=503,
            content={
                "isSuccess": False,
                "code": 503,
                "errorCode": "ML_SERVER_ERROR",
                "message": "삭제 동기화 worker가 초기화되지 않았습니다",
            },
        )

    result = deps.sync_worker.handle_webhook_event(event)
    return {
        "softDeleted": {
            "pageIds": result.soft_deleted_page_ids,
            "attachmentIds": result.soft_deleted_attachment_ids,
        },
        "ignored": False,
    }
