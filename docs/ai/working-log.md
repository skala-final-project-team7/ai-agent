# Working Log

## 2026-05-14 - Data Ingestion Agent feature1_project_skeleton_and_schema

### 작업 목표

- Data Ingestion Agent의 기본 Python package 구조와 schema/config 기반을 만든다.
- `feature2` 이후 범위인 Confluence API 호출, HTML extraction, LangGraph workflow, local output pipeline은 구현하지 않는다.
- `access_token`과 `cloud_id`는 외부 주입 가능한 config schema로만 정의하고, token은 안전 직렬화에서 노출하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-ingestion-agent/tests/unit/test_schema_config.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, package 미구현으로 `ModuleNotFoundError: No module named 'data_ingestion_agent'`가 발생하는 실패를 확인했다.

### 구현 내용

- `ai-agent/data-ingestion-agent/pyproject.toml`을 추가했다.
- `src/data_ingestion_agent` package 기본 구조를 추가했다.
- `DataIngestionConfig`를 추가하고 필수값 검증 및 `to_safe_dict()` token redaction을 구현했다.
- processed document, failed item, ingestion report, ingestion job schema를 추가했다.
- feature2 이후 영역을 위한 package placeholder만 추가했다.
- `scripts/run_full_crawl.py`는 config 검증과 app container 생성까지만 수행하는 최소 skeleton으로 추가했다.
- fixture, integration test, local data output 디렉토리 placeholder를 추가했다.

### 검증 명령

```bash
python3 -m pytest tests/unit/test_schema_config.py
python3.11 -m pytest tests/unit/test_schema_config.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3 -m pytest tests/unit/test_schema_config.py`: 실패. 기본 `python3`는 Python 3.14 환경이며 pytest module이 없었다.
- `python3.11 -m pytest tests/unit/test_schema_config.py`: 구현 전 `ModuleNotFoundError` 실패 확인 후, 구현 후 6 passed.
- `python3.11 -m pytest`: 6 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 현재 루트 스크립트는 `ai-agent/data-ingestion-agent/pyproject.toml` 하위 package 테스트를 자동 발견하지 않는다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 루트 스크립트는 하위 agent package 테스트 자동 실행 대상이 아니다.

### 남은 작업

- `feature2_confluence_client_and_pagination`: Confluence client, pagination, retry/backoff 테스트 우선 구현.
- 루트 검증 스크립트가 agent 하위 package를 자동 발견해야 하는지는 별도 작업 범위에서 결정한다.

## 2026-05-14 - Data Ingestion Agent feature2_confluence_client_and_pagination

### 작업 목표

- Confluence API base URL, Authorization header, spaces/descendants/page detail GET 호출 기반을 구현한다.
- `_links.next` cursor pagination, 429/5xx/timeout retry, 400/401/403/404 오류 분류를 구현한다.
- 실제 네트워크 테스트 없이 fake transport 기반으로 검증한다.
- HTML extraction, processed document pipeline, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-ingestion-agent/tests/unit/test_confluence_client.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `ConfluenceApiError`, `ConfluenceClient`, `ConfluenceRequest`, `ConfluenceResponse` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 base URL, Authorization header redaction, spaces pagination, descendants pagination, page detail query, 429 retry, 5xx retry, timeout retry, 401 auth failure, 403/404 item-level failure, max retry exhaustion을 포함했다.

### 구현 내용

- `ai-agent/data-ingestion-agent/src/data_ingestion_agent/confluence/client.py`를 추가했다.
- `ConfluenceClient`를 추가하고 기존 `DataIngestionConfig`의 `cloud_id`, `access_token`, `timeout_seconds`, `request_delay_seconds`, `max_retries`를 사용하게 했다.
- `ConfluenceRequest`, `ConfluenceResponse`, `ConfluenceTransport` protocol을 정의해 fake transport 테스트가 가능하게 했다.
- 기본 `UrllibConfluenceTransport`를 추가했지만 feature2 테스트에서는 실제 네트워크 호출을 사용하지 않았다.
- `list_spaces()`, `list_page_descendants()`, `get_page_detail()`을 구현했다.
- retryable 오류와 non-retryable 오류를 `ConfluenceApiError`로 분류했다.
- 오류 문자열에서 access token과 Authorization header가 노출되지 않도록 했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_confluence_client.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_confluence_client.py`: 12 passed.
- `python3.11 -m pytest`: 18 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 현재 루트 스크립트는 `ai-agent/data-ingestion-agent/pyproject.toml` 하위 package 테스트를 자동 발견하지 않는다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 루트 스크립트는 하위 agent package 테스트 자동 실행 대상이 아니다.
- `ruff`, `mypy`는 현재 PATH에 없어 직접 실행하지 못했다.

### 남은 작업

- `feature3_html_extraction`: storage HTML 원문 보존과 plain text 변환 테스트 우선 구현.

## 2026-05-14 - Data Ingestion Agent feature3_html_extraction

### 작업 목표

- Confluence Page 상세의 `body.storage.value` storage HTML 원문을 손실 없이 보존한다.
- 후속 processed document가 사용할 plain text를 별도 함수/service에서 안정적으로 추출한다.
- heading, paragraph, list, table, link, HTML entity, malformed HTML, 빈 입력, Confluence macro/attachment/image 태그를 처리한다.
- processed document pipeline, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-ingestion-agent/tests/unit/test_html_extraction.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `HtmlExtractionResult`, `extract_storage_html` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 heading/paragraph, ul/ol list, table cell, anchor display text, entity decoding, script/style 제거, 공백/빈 줄 정규화, 빈 입력, malformed HTML, Confluence macro/attachment/image 태그, 원문/plain text 분리 반환을 포함했다.

### 구현 내용

- `ai-agent/data-ingestion-agent/src/data_ingestion_agent/extraction/html_extractor.py`를 추가했다.
- `HtmlExtractionResult`로 `storage_html`과 `plain_text`를 분리해 반환하게 했다.
- `extract_storage_html()`을 추가하고 `None` 또는 빈 문자열 입력을 안전하게 처리했다.
- 표준 라이브러리 `HTMLParser` 기반 parser를 구현해 외부 의존성을 추가하지 않았다.
- block tag 줄바꿈, ul/ol list marker, table row/cell 구분, anchor display text, HTML entity decoding, script/style 제거, 중복 공백/빈 줄 정규화를 구현했다.
- Confluence macro/attachment/image 계열 태그는 실패시키지 않고 추출 가능한 텍스트만 처리하도록 했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_html_extraction.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_html_extraction.py`: 11 passed.
- `python3.11 -m pytest`: 29 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 현재 루트 스크립트는 `ai-agent/data-ingestion-agent/pyproject.toml` 하위 package 테스트를 자동 발견하지 않는다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 루트 스크립트는 하위 agent package 테스트 자동 실행 대상이 아니다.
- `ruff`, `mypy`는 현재 PATH에 없어 직접 실행하지 못했다.

### 남은 작업

- `feature4_processed_document_pipeline`: raw page detail to processed document mapping, failed item/report 생성, local file repository 테스트 우선 구현.

## 2026-05-14 - Data Ingestion Agent feature4_processed_document_pipeline

### 작업 목표

- Confluence Page 상세 응답과 Space/Page tree metadata를 canonical `ProcessedDocument`로 매핑한다.
- feature3 HTML extractor를 연결해 storage HTML 원문과 plain text를 모두 보존한다.
- failed item과 ingestion report 생성 helper를 후속 workflow에서 재사용 가능한 함수로 분리한다.
- local JSON/JSONL writer를 구현해 processed document, failed item, report를 파일로 저장한다.
- LangGraph workflow, 최종 CLI full crawl orchestration, MongoDB/RabbitMQ/Qdrant/Chunking/Embedding은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-ingestion-agent/tests/unit/test_processed_document_pipeline.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `PageDetailMapper`, `build_failed_item`, `build_ingestion_report`, `LocalFileRepository` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 page detail mapping, HTML 원문/plain text 분리 보존, 핵심 metadata 보존, 빈 storage body 처리, attachment MVP 미지원 상태, failed item helper, report count helper, local JSON/JSONL writer, token/Authorization 비포함, missing directory 생성 검증을 포함했다.

### 구현 내용

- `ai-agent/data-ingestion-agent/src/data_ingestion_agent/ingestion/mapper.py`를 추가했다.
- `PageDetailMapper.to_processed_document()`를 구현해 page detail dict와 page ref dict를 canonical schema로 변환했다.
- `feature3`의 `extract_storage_html()`을 연결해 `storage_html`, `plain_text`, `content_length`, `plain_text_length`를 산출했다.
- attachment 처리는 MVP 범위에 맞게 `has_attachments=False`, `attachment_processing_status=not_supported_in_mvp`로 유지했다.
- `ai-agent/data-ingestion-agent/src/data_ingestion_agent/ingestion/helpers.py`를 추가해 `build_failed_item()`, `build_ingestion_report()`를 구현했다.
- `ai-agent/data-ingestion-agent/src/data_ingestion_agent/storage/local_repository.py`를 추가해 `processed/documents.jsonl`, `failed/failed_items.jsonl`, `reports/ingestion_report.json` 파일 출력을 구현했다.
- writer는 필요한 디렉토리를 자동 생성하고, schema의 `to_dict()` 결과만 직렬화해 token/access_token/Authorization 값이 포함되지 않도록 했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_processed_document_pipeline.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_processed_document_pipeline.py`: 9 passed.
- `python3.11 -m pytest`: 38 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 현재 루트 스크립트는 `ai-agent/data-ingestion-agent/pyproject.toml` 하위 package 테스트를 자동 발견하지 않는다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 루트 스크립트는 하위 agent package 테스트 자동 실행 대상이 아니다.
- `ruff`, `mypy`는 현재 PATH에 없어 직접 실행하지 못했다.

### 남은 작업

- `feature5_langgraph_workflow_and_cli`: workflow orchestration, CLI full crawl, fixture 기반 integration test.

## 2026-05-14 - Data Ingestion Agent feature5_langgraph_workflow_and_cli

### 작업 목표

- feature1-4의 config, Confluence client, HTML extraction, processed document mapper, local repository를 full crawl workflow로 연결한다.
- `load_config -> list_spaces -> collect_page_tree -> fetch_page_details -> transform_html -> build_processed_documents -> write_outputs -> write_report` 단계 구조를 구현한다.
- CLI `scripts/run_full_crawl.py`를 실제 workflow 실행 진입점으로 확장한다.
- 테스트는 fake client 기반으로 작성하고 실제 Confluence API 네트워크 호출은 수행하지 않는다.
- MongoDB, RabbitMQ, FastAPI endpoint, Qdrant, Chunking/Embedding, 첨부파일 추출은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-ingestion-agent/tests/integration/test_workflow_cli.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `data_ingestion_agent.app.cli` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 fake client full crawl, partial success, list_spaces 인증 실패, empty spaces, empty pages, CLI 인자 처리, CLI 출력 token redaction, output file 생성, LangGraph optional fallback, script entrypoint import를 포함했다.

### 구현 내용

- `ai-agent/data-ingestion-agent/src/data_ingestion_agent/workflow.py`를 추가했다.
- `DataIngestionWorkflowState`, `DataIngestionWorkflowRunner`, `DataIngestionWorkflowResult`, `run_full_crawl_workflow()`를 구현했다.
- workflow node는 orchestration만 담당하고 기존 `ConfluenceClient`, `PageDetailMapper`, helper, `LocalFileRepository`를 재사용하게 했다.
- page detail 일부 실패 시 failed item으로 기록하고 가능한 문서는 계속 처리하도록 했다.
- list_spaces 단계 실패는 job-level failure로 보고 report status를 `failed`로 기록하게 했다.
- empty spaces와 empty pages에서도 빈 JSONL/report 산출물을 생성하도록 했다.
- `ai-agent/data-ingestion-agent/src/data_ingestion_agent/graph/workflow.py`를 추가해 LangGraph optional availability와 sequential fallback을 명시했다.
- `pyproject.toml`에 optional dependency `langgraph`를 명시했다.
- `ai-agent/data-ingestion-agent/src/data_ingestion_agent/app/cli.py`를 추가하고 `--cloud-id`, `--access-token`, `--output-dir`, `--request-delay`, `--max-retries`, `--timeout` 인자를 처리했다.
- `scripts/run_full_crawl.py`를 CLI workflow 진입점으로 확장하고 직접 실행 시 `src` package를 찾도록 처리했다.
- CLI summary와 output path 출력에는 access token 또는 Authorization header가 포함되지 않도록 했다.

### 검증 명령

```bash
python3.11 -m pytest tests/integration/test_workflow_cli.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/integration/test_workflow_cli.py`: 8 passed.
- `python3.11 -m pytest`: 46 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 현재 루트 스크립트는 `ai-agent/data-ingestion-agent/pyproject.toml` 하위 package 테스트를 자동 발견하지 않는다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 루트 스크립트는 하위 agent package 테스트 자동 실행 대상이 아니다.
- `ruff`, `mypy`는 현재 PATH에 없어 직접 실행하지 못했다.

### 남은 작업

- `feature6_fixture_and_safety_tests`: synthetic Confluence fixture, output file 검증, token safety, boundary test 보강.

## 2026-05-14 - Data Ingestion Agent feature6_fixture_and_safety_tests

### 작업 목표

- Data Ingestion Agent MVP 전체를 synthetic fixture 기반으로 검증한다.
- 민감정보 노출 방지와 MVP 제외 범위를 테스트로 고정한다.
- 실제 Confluence API 네트워크 호출, MongoDB, RabbitMQ, FastAPI endpoint, Qdrant, Chunking/Embedding, 첨부파일 추출은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-ingestion-agent/tests/integration/test_fixture_safety.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `tests/fixtures/confluence_synthetic.json` 부재로 8개 테스트 실패를 확인했다.
- 테스트 케이스에는 fixture secret marker 검사, full workflow output shape, canonical processed document 필드, HTML 원문/plain text 보존, report count, partial failure failed item, empty space/page, macro/attachment MVP 미지원 상태, CLI stdout/stderr redaction, output 파일 redaction, long/empty body boundary를 포함했다.

### 구현 내용

- `ai-agent/data-ingestion-agent/tests/fixtures/confluence_synthetic.json`을 추가했다.
- fixture는 synthetic Space, descendants page tree, page detail, partial failure, missing homepage, empty page set, unsupported macro/attachment, empty body, long body boundary 케이스를 포함한다.
- fixture에는 실제 회사 문서, 개인정보, 실제 token, 실제 cloud id, Authorization header 형태 값을 포함하지 않았다.
- feature1-5 공개 API는 변경하지 않았다.

### 검증 명령

```bash
python3.11 -m pytest tests/integration/test_fixture_safety.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/integration/test_fixture_safety.py`: fixture 추가 전 8 failed, fixture 추가 후 8 passed.
- `python3.11 -m pytest`: 54 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 현재 루트 스크립트는 `ai-agent/data-ingestion-agent/pyproject.toml` 하위 package 테스트를 자동 발견하지 않는다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 루트 스크립트는 하위 agent package 테스트 자동 실행 대상이 아니다.
- `ruff`, `mypy`는 현재 PATH에 없어 직접 실행하지 못했다.

### MVP 완료 여부

- Data Ingestion Agent MVP feature1-6 구현 및 fixture/safety 검증을 완료했다.
- 남은 범위는 MVP 제외 항목 또는 후속 확장 항목이다.
