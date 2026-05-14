# Data Sync Agent

공통 규칙은 루트 `AGENTS.md`와 `ai-agent/AGENTS.md`를 따른다. 이 문서는 Data Sync Agent 고유 개발 명세만 정의한다.

---

## Agent 목표

Confluence 문서의 변경/삭제를 감지하고, 변경된 Page만 재수집 대상으로 식별하여 후속 Chunking/Embedding/Vector DB update 단계가 소비할 수 있는 동기화 산출물을 생성한다.

초기 MVP는 **local snapshot 기반 Page metadata delta sync**를 구현한다.

---

## MVP 범위

포함:

- Confluence API 직접 호출
- 외부 주입된 `cloud_id`, `access_token` 사용
- Space 목록 조회
- Space별 Page metadata 목록 조회
- cursor pagination
- 이전 snapshot과 현재 snapshot 비교
- `version.number`, `version.createdAt` 기준 변경 감지
- deleted candidate 감지
- 변경 Page 상세 조회
- 변경 Page storage HTML 보존 및 plain text 변환
- changed/deleted/message/report/failed 파일 생성
- LangGraph workflow
- CLI 수동 실행
- fixture 기반 테스트

제외:

- 실제 scheduler 실행
- MongoDB 실제 조회/저장
- RabbitMQ 실제 발행
- Qdrant 실제 upsert/delete
- FastAPI endpoint
- OAuth token 발급/refresh
- Trash API / Webhook / Reconciliation 실제 구현
- PDF / Word / Excel 첨부 파일 동기화
- Chunking / Embedding 실제 수행

후속 확장:

- MongoDB repository adapter
- RabbitMQ publisher / worker
- Qdrant update/delete adapter
- scheduler
- FastAPI endpoint
- Trash API deletion collector
- Webhook event consumer
- Reconciliation workflow
- Attachment sync

---

## 책임 범위

책임진다:

- Confluence API client
- Space 및 Page metadata 수집
- cursor pagination
- previous/current snapshot 관리
- diff 계산
- changed/deleted candidate 분류
- 변경 Page 상세 수집
- 변경 Page HTML 변환
- changed document 생성
- deleted item 생성
- message payload 생성
- sync report / failed item 생성
- LangGraph workflow와 CLI

책임지지 않는다:

- 사용자 로그인 UI
- OAuth authorization code flow
- token 저장/갱신
- Data Ingestion Agent의 Full Crawl 본구현
- Chunking / Embedding / Vector DB 실제 처리
- 답변 생성/검증 Agent
- RAG 검색/응답 생성

---

## 실행 모델

MVP는 CLI 기반 단일 delta sync job이다.

```bash
python ai-agent/data-sync-agent/scripts/run_delta_sync.py \
  --cloud-id "$ATLASSIAN_CLOUD_ID" \
  --access-token "$ATLASSIAN_ACCESS_TOKEN" \
  --previous-snapshot ai-agent/data-sync-agent/data/snapshots/latest_snapshot.json \
  --output-dir ai-agent/data-sync-agent/data
```

운영 목표 주기는 `1 hour`다. MVP에서는 스케줄러를 구현하지 않고 CLI 수동 실행만 제공한다.

---

## Confluence API 계약

Base URL:

```text
https://api.atlassian.com/ex/confluence/{CLOUD_ID}/wiki/api/v2
```

MVP 사용 API:

| API | 목적 |
| --- | --- |
| `GET /spaces?limit=25` | sync 대상 Space 확보 |
| `GET /spaces/{spaceId}/pages?limit=25&body-format=storage` | Page metadata 목록 조회 |
| `GET /pages/{pageId}?body-format=storage&include-version=true` | 변경 Page 상세 조회 |

목록형 API는 `_links.next` 기반 cursor pagination을 처리한다.

---

## Delta Sync 판단 기준

Page key:

```text
cloud_id + space_id + page_id
```

분류:

| 분류 | 조건 | MVP 처리 |
| --- | --- | --- |
| `new` | previous snapshot에 없고 current snapshot에 있음 | 상세 조회 후 changed document 생성 |
| `updated` | version 또는 lastModifiedAt 변경 | 상세 조회 후 changed document 생성 |
| `unchanged` | version/lastModifiedAt 동일 | 상세 조회하지 않음 |
| `deleted_candidate` | previous에 있으나 current에 없음 | deleted item 기록 |
| `failed` | 조회/변환/저장 실패 | failed item 기록 |

삭제 후보는 확정 삭제가 아니다. Trash API/Webhook/Reconciliation 후속 단계에서 확정한다.

---

## Workflow

```text
load_config
  -> load_previous_snapshot
  -> list_spaces
  -> fetch_current_page_metadata
  -> build_current_snapshot
  -> diff_snapshots
  -> fetch_changed_page_details
  -> transform_changed_html
  -> build_changed_documents
  -> build_deleted_items
  -> build_message_payloads
  -> write_outputs
  -> write_report
```

핵심 규칙:

- metadata 조회 단계에서는 Page 상세 본문을 수집하지 않는다.
- `new`와 `updated` Page만 상세 조회한다.
- API 조회 실패를 삭제로 간주하지 않는다.
- `deleted_candidate`는 실제 Qdrant delete를 수행하지 않는다.
- Data Ingestion Agent의 processed document 계약과 호환되게 설계한다.

---

## Canonical Schema

### Page Snapshot

```json
{
  "snapshot_id": "string",
  "sync_id": "string",
  "cloud_id": "string",
  "created_at": "ISO-8601",
  "pages": [
    {
      "page_key": "{cloud_id}:{space_id}:{page_id}",
      "space_id": "string",
      "space_key": "string",
      "space_name": "string",
      "page_id": "string",
      "title": "string",
      "status": "current",
      "page_url": "string",
      "last_modified_at": "ISO-8601",
      "version_number": 0
    }
  ]
}
```

### Changed Document

Data Ingestion Agent의 `ProcessedDocument`와 호환되며 `sync_id`, `change_type`을 추가한다.

```json
{
  "document_id": "confluence-page-{page_id}-{version_number}",
  "sync_id": "string",
  "source_type": "confluence_page",
  "change_type": "new|updated",
  "cloud_id": "string",
  "space": {},
  "page": {},
  "body": {
    "representation": "storage",
    "storage_html": "string",
    "plain_text": "string"
  },
  "metadata": {
    "attachment_processing_status": "not_supported_in_mvp"
  }
}
```

### Deleted Item

```json
{
  "sync_id": "string",
  "delete_type": "deleted_candidate",
  "page_key": "{cloud_id}:{space_id}:{page_id}",
  "cloud_id": "string",
  "space_id": "string",
  "page_id": "string",
  "title": "string",
  "detection_method": "snapshot_missing",
  "requires_confirmation": true
}
```

### Message Payload

```json
{
  "sync_id": "string",
  "event_type": "chunking_requested|delete_candidate_detected",
  "source_type": "confluence_page",
  "page_id": "string",
  "space_id": "string",
  "document_id": "string|null",
  "change_type": "new|updated|deleted_candidate",
  "payload_ref": "string"
}
```

---

## Error Handling

| Status | 처리 |
| --- | --- |
| 400 | non-retryable failure |
| 401 | auth failure, job 중단 가능 |
| 403 | permission failure, item failure |
| 404 | item not found, deleted candidate와 구분 필요 |
| 429 | retryable, backoff |
| 5xx / timeout | retryable |

기본 권장값:

```json
{
  "request_delay_seconds": 0.3,
  "max_retries": 3,
  "timeout_seconds": 20
}
```

---

## 권장 구현 구조

```text
ai-agent/data-sync-agent/
  data-sync-agent.md
  src/data_sync_agent/
    app/
    confluence/
    graph/
    sync/
    extraction/
    storage/
    messaging/
    schemas/
    config/
    utils/
  tests/
    fixtures/
    unit/
    integration/
  data/
    snapshots/
    changed/
    deleted/
    messages/
    reports/
    failed/
  scripts/
```

---

## Feature Breakdown

### feature1_project_skeleton_and_schema

- package 구조 생성
- `pyproject.toml` 설정
- sync job / snapshot / changed document / deleted item / message / report schema 정의
- schema 단위 테스트 작성

### feature2_snapshot_repository

- previous snapshot 로드
- current snapshot 저장
- snapshot 없음 처리
- malformed snapshot 처리
- repository 테스트 작성

### feature3_confluence_metadata_client

- Confluence API client 구현
- `/spaces` 호출
- `/spaces/{spaceId}/pages` 호출
- pagination 처리
- retry/backoff 기본 처리
- client/pagination 테스트 작성

### feature4_diff_engine

- page key 생성
- `new`, `updated`, `unchanged`, `deleted_candidate` 분류
- API 실패와 삭제 후보 구분
- diff engine 테스트 작성

### feature5_changed_page_processing

- changed Page 상세 조회
- storage HTML 원문 보존
- HTML to plain text 변환
- changed document 생성
- 처리 테스트 작성

### feature6_deleted_and_message_payloads

- deleted item 생성
- `chunking_requested` payload 생성
- `delete_candidate_detected` payload 생성
- local message writer 구현
- payload 테스트 작성

### feature7_langgraph_workflow_and_cli

- LangGraph workflow 구성
- CLI 실행 스크립트 구현
- local output 저장
- fixture 기반 workflow integration test 작성

### feature8_fixture_and_safety_tests

- synthetic previous/current fixture 작성
- token safety 테스트
- output report 검증
- boundary test 작성

---

## 수용 기준

- CLI로 Delta Sync workflow를 실행할 수 있다.
- Confluence API 호출은 외부 주입 token을 사용한다.
- token 값이 로그, fixture, output file에 저장되지 않는다.
- previous snapshot과 current snapshot을 비교할 수 있다.
- `new`, `updated`, `unchanged`, `deleted_candidate`가 올바르게 분류된다.
- `new`/`updated` Page만 상세 조회한다.
- 변경 Page의 storage HTML 원문과 plain text가 분리 저장된다.
- changed documents, deleted items, message payloads, report, failed 파일이 생성된다.
- 첨부 파일은 `not_supported_in_mvp`로 표시된다.
- LangGraph workflow가 전체 단계를 orchestration한다.
- fixture 기반 integration test가 통과한다.

