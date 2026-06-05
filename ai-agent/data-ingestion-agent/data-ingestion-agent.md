# Data Ingestion Agent

공통 규칙은 루트 `AGENTS.md`와 `ai-agent/AGENTS.md`를 따른다. 이 문서는 Data Ingestion Agent 고유 개발 명세만 정의한다.

---

## Agent 목표

Confluence API를 직접 호출하여 사용자가 접근 가능한 Space/Page 데이터를 수집하고, Page 상세의 `storage` HTML 본문을 plain text로 변환한 뒤, 후속 Chunking/Embedding/RAG 파이프라인이 소비할 수 있는 processed document 산출물을 생성한다.

초기 MVP는 **Page 본문 HTML 처리**까지만 구현한다.

---

## MVP 범위

포함:

- Confluence API 직접 호출
- 외부 주입된 `cloud_id`, `access_token` 사용
- Space 목록 조회
- Space `homepageId` 기준 descendants Page Tree 조회
- Page 상세 조회
- storage HTML 원문 보존
- HTML to plain text 변환
- processed document JSON/JSONL 생성
- ingestion report 생성
- failed item 기록
- LangGraph workflow
- CLI 수동 실행
- fixture 기반 테스트

제외:

- PDF / Word / Excel 첨부 파일 텍스트 추출
- Attachment API 호출
- MongoDB 실제 저장
- RabbitMQ 실제 발행
- FastAPI endpoint
- OAuth token 발급/refresh
- ACL restriction API 수집
- Qdrant upsert
- Chunking / Embedding 실제 수행

후속 확장:

- attachment collector / extractor
- MongoDB repository adapter
- RabbitMQ publisher / worker
- FastAPI endpoint
- ACL metadata collector
- Cloud ID discovery API

---

## 책임 범위

책임진다:

- Confluence API client
- Space 목록 수집
- descendants 기반 Page Tree 수집
- Page 상세 수집
- cursor pagination
- retry/backoff 기본 처리
- HTML 원문 보존 및 plain text 변환
- processed document 생성
- report / failed item 생성
- local file output
- LangGraph workflow와 CLI

책임지지 않는다:

- 사용자 로그인 UI
- OAuth authorization code flow
- token 저장/갱신
- BFF wrapper response
- Data Sync Agent
- RAG retrieval / generation / verification
- Chunking / Embedding / Vector DB upsert

---

## 실행 모델

MVP는 CLI 기반 단일 full crawl job이다.

```bash
python ai-agent/data-ingestion-agent/scripts/run_full_crawl.py \
  --cloud-id "$ATLASSIAN_CLOUD_ID" \
  --access-token "$ATLASSIAN_ACCESS_TOKEN" \
  --output-dir ai-agent/data-ingestion-agent/data/processed
```

민감값은 환경변수, CLI 인자, 런타임 secret provider 등 외부 주입만 허용한다.

---

## Confluence API 계약

Base URL:

```text
https://api.atlassian.com/ex/confluence/{CLOUD_ID}/wiki/api/v2
```

MVP 사용 API:

| API | 목적 |
| --- | --- |
| `GET /spaces?limit=25` | 접근 가능한 Space 목록 및 `homepageId` 확보 |
| `GET /pages/{homepageId}/descendants?limit=25` | Space Page Tree 수집 |
| `GET /pages/{pageId}?body-format=storage&include-version=true` | Page 상세 본문 조회 |

목록형 API는 `_links.next` 기반 cursor pagination을 처리한다.

---

## Workflow

```text
load_config
  -> list_spaces
  -> collect_page_tree
  -> fetch_page_details
  -> transform_html
  -> build_processed_documents
  -> write_outputs
  -> write_report
```

핵심 규칙:

- `descendants` API로 Page Tree를 우선 수집한다.
- Page 상세 API에서 `body.storage.value`를 수집한다.
- storage HTML 원문을 보존하고 plain text와 분리한다.
- Page 단위 실패는 failed item으로 기록한다.
- 첨부 파일 상태는 `not_supported_in_mvp`로 표시한다.

---

## Canonical Schema

### Processed Document

```json
{
  "document_id": "confluence-page-{page_id}-{version_number}",
  "job_id": "string",
  "source_type": "confluence_page",
  "cloud_id": "string",
  "space": {
    "space_id": "string",
    "space_key": "string",
    "space_name": "string"
  },
  "page": {
    "page_id": "string",
    "parent_id": "string|null",
    "title": "string",
    "status": "current",
    "depth": 0,
    "child_position": 0,
    "page_url": "string",
    "created_at": "ISO-8601",
    "last_modified_at": "ISO-8601",
    "version_number": 0
  },
  "body": {
    "representation": "storage",
    "storage_html": "string",
    "plain_text": "string"
  },
  "metadata": {
    "content_length": 0,
    "plain_text_length": 0,
    "has_attachments": false,
    "attachment_processing_status": "not_supported_in_mvp"
  }
}
```

### Failed Item

```json
{
  "job_id": "string",
  "stage": "list_spaces|collect_page_tree|fetch_page_detail|transform_html|write_output",
  "item_type": "space|page|document",
  "item_id": "string|null",
  "status": "failed",
  "error_type": "string",
  "error_message": "string",
  "retryable": true,
  "attempt_count": 1
}
```

### Ingestion Report

```json
{
  "job_id": "string",
  "status": "completed|completed_with_errors|failed",
  "counts": {
    "spaces": 0,
    "page_refs": 0,
    "pages_fetched": 0,
    "documents_written": 0,
    "failed_items": 0
  },
  "output_paths": {}
}
```

---

## Error Handling

| Status | 처리 |
| --- | --- |
| 400 | non-retryable failure |
| 401 | auth failure, job 중단 가능 |
| 403 | permission failure, item failure |
| 404 | item not found, item failure |
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
ai-agent/data-ingestion-agent/
  data-ingestion-agent.md
  src/data_ingestion_agent/
    app/
    confluence/
    graph/
    ingestion/
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
    raw/
    processed/
    reports/
    failed/
  scripts/
```

---

## Feature Breakdown

### feature1_project_skeleton_and_schema

- package 구조 생성
- `pyproject.toml` 설정
- ingestion job / processed document / failed item / report schema 정의
- CLI config 구조 정의
- schema 단위 테스트 작성

### feature2_confluence_client_and_pagination

- Confluence API client 구현
- `/spaces` 호출
- `/pages/{homepageId}/descendants` 호출
- `/pages/{pageId}` 상세 호출
- `_links.next` pagination 처리
- retry/backoff 기본 처리
- client/pagination 테스트 작성

### feature3_html_extraction

- storage HTML 원문 보존
- plain text 변환
- heading/list/table/link 처리
- malformed HTML 처리
- HTML extractor 테스트 작성

### feature4_processed_document_pipeline

- raw page detail to processed document mapping
- failed item 생성
- ingestion report 생성
- local file repository 구현
- mapper/repository/report 테스트 작성

### feature5_langgraph_workflow_and_cli

- LangGraph workflow 구성
- CLI 실행 스크립트 구현
- local output 저장
- fixture 기반 workflow integration test 작성

### feature6_fixture_and_safety_tests

- synthetic Confluence fixture 작성
- token safety 테스트
- output file 검증
- boundary test 작성

---

## 수용 기준

- CLI로 Full Crawl workflow를 실행할 수 있다.
- Confluence API 호출은 외부 주입 token을 사용한다.
- token 값이 로그, fixture, output file에 저장되지 않는다.
- Space 목록, descendants, Page 상세 API 호출 함수가 분리되어 있다.
- `_links.next` 기반 pagination이 동작한다.
- storage HTML 원문과 plain text가 분리 저장된다.
- processed document, report, failed item 파일이 생성된다.
- 첨부 파일은 `not_supported_in_mvp`로 표시된다.
- LangGraph workflow가 전체 단계를 orchestration한다.
- fixture 기반 integration test가 통과한다.

