# Working Log

## 2026-05-15 - Data Sync Agent MVP 마감 문서 정리

- `docs/ai/current-plan.md`에서 feature1-8과 전체 MVP 완료 기준이 모두 완료 상태임을 확인했다.
- 요구사항 요약의 MVP 완료 항목과 MVP 제외 범위 유지 항목을 완료 체크로 정리했다.
- 수정 금지 대상 섹션은 실제 수정하지 않은 영역 확인 의미가 드러나도록 정리했다.
- 소스 코드, 테스트 코드, CLI script는 수정하지 않았다.

## 2026-05-15 - Data Sync Agent feature8_fixture_and_safety_tests

### 작업 목표

- Data Sync Agent MVP 전체를 synthetic fixture 기반으로 검증한다.
- CLI stdout/stderr와 snapshot/changed/deleted/message/report/failed output의 민감정보 비노출을 테스트로 고정한다.
- scheduler, MongoDB, RabbitMQ 발행, Qdrant update/delete, FastAPI endpoint, Chunking/Embedding, 첨부파일 동기화는 구현하지 않고 MVP 범위 경계를 검증한다.

### 테스트 우선 진행

- `ai-agent/data-sync-agent/tests/fixtures/sync/*.json` synthetic fixture를 추가했다.
- `ai-agent/data-sync-agent/tests/integration/test_fixture_safety.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, malformed previous snapshot을 failed item으로 기록하는 workflow 경로에서 `_failed_item_from_message()`의 `attempt_count` 인자 처리 누락으로 실패를 확인했다.
- 테스트 케이스에는 fixture 안전성, full workflow output shape/count/schema, missing previous snapshot all-new 처리, empty current deleted candidate 처리, partial failure failed item, malformed previous snapshot boundary, unsupported attachment/macro 상태, CLI/output 민감정보 비노출, MVP 제외 기능 미실행 검증을 포함했다.

### 구현 내용

- `ai-agent/data-sync-agent/tests/fixtures/sync/previous_snapshot.json`, `spaces.json`, `current_pages.json`, `page_details.json`, `partial_failure_pages.json`, `empty_pages.json`을 추가했다.
- fixture는 모두 `synthetic-*`, `example.invalid` 값을 사용하고 실제 token, 실제 cloud id, 개인정보, 회사 문서를 포함하지 않게 했다.
- `ai-agent/data-sync-agent/tests/integration/test_fixture_safety.py`에서 current snapshot, changed documents, deleted items, message payloads, report, failed item 파일 shape와 schema를 검증했다.
- `workflow.py`의 failed item helper가 `attempt_count`를 받을 수 있게 보강해 malformed previous snapshot boundary를 안전하게 failed item으로 기록하게 했다.

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

- `python3.11 -m pytest tests/integration/test_fixture_safety.py`: 구현 전 1 failed 확인 후, 구현 후 8 passed.
- `python3.11 -m pytest`: 72 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### MVP 완료 여부

- Data Sync Agent MVP feature1-8 구현과 fixture/safety 검증을 완료했다.
- 남은 항목은 MVP 제외 범위의 후속 확장이다: scheduler, MongoDB adapter, RabbitMQ publisher, Qdrant update/delete adapter, FastAPI endpoint, OAuth refresh, Trash API/Webhook/Reconciliation, Attachment sync, Chunking/Embedding 실제 수행.

## 2026-05-15 - Data Sync Agent feature7_langgraph_workflow_and_cli

### 작업 목표

- snapshot repository, Confluence metadata client, diff engine, changed page processor, deleted/message payload helper를 workflow와 CLI 수동 실행 흐름으로 연결한다.
- LangGraph는 optional dependency로 두고, 미설치 환경에서는 sequential fallback으로 명확하게 실행한다.
- 실제 scheduler, MongoDB, RabbitMQ 발행, Qdrant update/delete, FastAPI endpoint, Chunking/Embedding은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-sync-agent/tests/integration/test_workflow_cli.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `data_sync_agent.scripts` 및 workflow 모듈 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 fake client 기반 delta sync, previous/current snapshot 비교, changed/deleted/message/report/current snapshot 파일 생성, missing previous snapshot all-new 처리, empty current snapshot deleted candidate 처리, detail partial failure, CLI config 구성과 token redaction, LangGraph fallback을 포함했다.

### 구현 내용

- `ai-agent/data-sync-agent/src/data_sync_agent/workflow.py`를 추가했다.
- `DataSyncWorkflowState`, `DataSyncWorkflowResult`, `DataSyncWorkflow`, `build_data_sync_workflow()`, `run_data_sync_workflow()`를 구현했다.
- workflow node 흐름은 `load_config -> load_previous_snapshot -> list_spaces -> fetch_current_page_metadata -> build_current_snapshot -> diff_previous_current_snapshots -> fetch_changed_page_details -> transform_changed_html -> build_changed_documents -> build_deleted_items -> build_message_payload_nodes -> write_outputs -> write_report`로 구성했다.
- HTML 변환과 changed document 생성은 기존 `ChangedPageProcessor`가 담당하고, workflow node는 orchestration contract만 유지한다.
- local output은 `snapshots/latest_snapshot.json`, `changed/changed_documents.jsonl`, `deleted/deleted_items.jsonl`, `messages/message_payloads.jsonl`, `failed/failed_items.jsonl`, `reports/sync_report.json`으로 저장한다.
- `ai-agent/data-sync-agent/src/data_sync_agent/scripts/run_delta_sync.py`를 추가해 CLI parser와 workflow 실행을 구현했다.
- 기존 `ai-agent/data-sync-agent/scripts/run_delta_sync.py`는 package CLI module에 위임하는 수동 실행 스크립트로 유지했다.

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

- `python3.11 -m pytest tests/integration/test_workflow_cli.py`: 구현 전 import 실패 확인 후, 구현 후 6 passed.
- `python3.11 -m pytest`: 64 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature8_fixture_and_safety_tests`: fixture/safety integration을 보강하고 MVP 범위 경계와 민감정보 비노출을 전체 suite로 고정한다.

## 2026-05-15 - Data Sync Agent feature6_deleted_and_message_payloads

### 작업 목표

- diff 결과의 `deleted_candidate` Page를 canonical deleted item 산출물로 변환한다.
- changed document와 deleted item을 후속 Chunking/Embedding/Vector DB update 또는 RabbitMQ 연동에서 소비할 수 있는 message payload 구조로 만든다.
- 실제 RabbitMQ 발행, Qdrant update/delete, Chunking/Embedding, LangGraph workflow, full CLI orchestration은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-sync-agent/tests/unit/test_deleted_and_message_payloads.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `data_sync_agent.messaging.LocalMessagePayloadWriter` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 deleted candidate 변환, candidate 상태와 confirmation flag, changed/deleted payload 생성, event/operation/downstream target, deterministic payload id/idempotency key, skipped/failed 항목 필터링, JSONL writer, 민감정보 비노출을 포함했다.

### 구현 내용

- `ai-agent/data-sync-agent/src/data_sync_agent/messaging/payloads.py`를 추가했다.
- `build_deleted_item_from_change()`는 `ChangeType.DELETED_CANDIDATE` diff item의 previous snapshot을 `DeletedItem`으로 변환한다.
- `build_changed_message_payload()`와 `build_deleted_message_payload()`는 각각 `chunking_requested`, `delete_candidate_detected` event payload를 생성한다.
- `build_message_payloads()`는 changed/deleted 산출물만 payload로 만들고 skipped/failed 항목은 payload 대상에서 제외한다.
- `LocalMessagePayloadWriter`는 message payload를 local JSONL 파일로 저장하며, 실제 RabbitMQ 발행은 구현하지 않았다.
- `DeletedItem`, `MessagePayload` schema에 feature6 payload 생성에 필요한 candidate metadata, downstream target, deterministic payload id/idempotency key를 보강했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_deleted_and_message_payloads.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_deleted_and_message_payloads.py`: 구현 전 import 실패 확인 후, 구현 후 7 passed.
- `python3.11 -m pytest`: 58 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature7_langgraph_workflow_and_cli`: snapshot load, metadata collection, diff, changed/deleted/message output을 workflow와 CLI 수동 실행 흐름으로 연결한다.

## 2026-05-15 - Data Sync Agent feature5_changed_page_processing

### 작업 목표

- diff engine에서 `new` 또는 `updated`로 분류된 Page에 대해서만 Page 상세를 가져온다.
- Page 상세의 storage HTML 원문을 보존하고 plain text를 추출해 changed document 산출물로 변환한다.
- deleted item/message payload 생성, LangGraph workflow, full CLI orchestration은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-sync-agent/tests/unit/test_changed_page_processing.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `data_sync_agent.sync.changed_page_processor` 미구현으로 `ModuleNotFoundError` 실패를 확인했다.
- 테스트 케이스에는 `new`/`updated`만 상세 조회, `unchanged`/`deleted_candidate` 조회 생략, storage HTML 보존, heading/paragraph/list/table/link plain text 추출, malformed HTML 처리, macro/attachment MVP 미지원 상태, partial failure failed item 기록, changed document metadata 필수 필드, 민감정보 비노출을 포함했다.

### 구현 내용

- `ai-agent/data-sync-agent/src/data_sync_agent/extraction/html_extractor.py`를 추가했다.
- `HtmlExtractionResult`, `extract_storage_html()`을 구현해 storage HTML 원문과 plain text를 분리 반환하게 했다.
- `script/style` 내용은 제외하고 block/list/table/link 텍스트를 plain text에 포함하도록 표준 라이브러리 `HTMLParser` 기반 extractor를 구현했다.
- `ai-agent/data-sync-agent/src/data_sync_agent/sync/changed_page_processor.py`를 추가했다.
- `ChangedPageProcessor`는 `ChangeType.NEW`, `ChangeType.UPDATED`만 `get_page_detail()` 대상으로 삼고, 나머지 change type은 건너뛴다.
- Page detail response를 feature1 `ChangedDocument` schema로 매핑하고 `detected_at`, content length, plain text length, unsupported content 상태를 metadata에 기록한다.
- Page detail 일부 실패는 `FailedItem(stage=fetch_page_detail)`으로 기록하고 나머지 Page 처리는 계속 진행한다.
- failed item error message에서 access token 관련 field, Authorization, Bearer 문자열이 노출되지 않도록 redaction을 적용했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_changed_page_processing.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_changed_page_processing.py`: 구현 전 `ModuleNotFoundError` 실패 확인 후, 구현 후 7 passed.
- `python3.11 -m pytest`: 51 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature6_deleted_and_message_payloads`: deleted item 생성, chunking/delete_candidate message payload 생성, local message writer 테스트 우선 구현.

## 2026-05-15 - Data Sync Agent feature4_diff_engine

### 작업 목표

- previous snapshot과 current snapshot을 비교해 `new`, `updated`, `unchanged`, `deleted_candidate` Page를 분류하는 diff engine을 구현한다.
- diff engine은 I/O 없이 feature1 `PageSnapshot`/`PageSnapshotItem` schema를 입력으로 받는 순수 service로 유지한다.
- changed page detail fetch, HTML extraction, message payload 생성, LangGraph workflow, full CLI orchestration은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-sync-agent/tests/unit/test_diff_engine.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `data_sync_agent.sync.diff_engine` 미구현으로 `ModuleNotFoundError` 실패를 확인했다.
- 테스트 케이스에는 empty previous -> `new`, empty current -> `deleted_candidate`, version 증가 -> `updated`, timestamp 변경 -> `updated`, 동일 version/timestamp -> `unchanged`, space/cloud 차이 page key 분리, duplicate page key 오류, changed/deleted 별도 목록, summary count, unavailable page key를 failed로 분리, deterministic output order를 포함했다.

### 구현 내용

- `ai-agent/data-sync-agent/src/data_sync_agent/sync/diff_engine.py`를 추가했다.
- `DiffEngineError`, `PageChange`, `DiffSummary`, `DiffResult`, `index_snapshot_pages()`, `diff_snapshots()`를 구현했다.
- `page_key` 기준으로 previous/current snapshot index를 만들고 duplicate page key는 명확한 오류로 처리한다.
- current에만 있는 Page는 `new`, version 또는 `last_modified_at`이 바뀐 Page는 `updated`, 동일한 Page는 `unchanged`, previous에만 있는 Page는 `deleted_candidate`로 분류한다.
- `unavailable_page_keys` 입력을 추가해 API 수집 실패 등으로 current에 없어진 Page를 삭제 후보로 오분류하지 않고 `failed_pages`로 분리한다.
- output은 page key 정렬 기반 deterministic order를 유지한다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_diff_engine.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_diff_engine.py`: 구현 전 `ModuleNotFoundError` 실패 확인 후, 구현 후 12 passed.
- `python3.11 -m pytest`: 44 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature5_changed_page_processing`: `new`/`updated` Page 상세 조회 연결, storage HTML 원문 보존, plain text 변환, changed document 생성 테스트 우선 구현.

## 2026-05-15 - Data Sync Agent feature3_confluence_metadata_client

### 작업 목표

- Data Sync Agent가 Confluence API에서 Space 목록과 Space별 Page metadata 목록을 수집할 수 있도록 metadata client를 구현한다.
- Confluence API base URL, Authorization header, pagination, retry/backoff, 오류 분류, Page metadata to `PageSnapshotItem` mapper를 제공한다.
- diff engine, changed page processing, deleted/message payload, LangGraph workflow, full CLI orchestration은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-sync-agent/tests/unit/test_confluence_metadata_client.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `ConfluenceApiError`, `ConfluenceMetadataClient`, `ConfluenceRequest`, `ConfluenceResponse`, `map_page_metadata_to_snapshot_item` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 base URL, Authorization header redaction, spaces pagination, space pages pagination, `body-format=storage`, page detail interface query, Page Snapshot schema mapping, 429/5xx/timeout retry, 401 auth failure, 403/404 item-level failure, max retry exhaustion을 포함했다.

### 구현 내용

- `ai-agent/data-sync-agent/src/data_sync_agent/confluence/client.py`를 추가했다.
- `ConfluenceMetadataClient`, `ConfluenceRequest`, `ConfluenceResponse`, `ConfluenceTransport`, `UrllibConfluenceTransport`, `ConfluenceApiError`를 정의했다.
- `DataSyncConfig`의 `cloud_id`, `access_token`, `timeout_seconds`, `request_delay_seconds`, `max_retries`를 사용하게 했다.
- `list_spaces()`, `list_space_pages()`, `get_page_detail()`을 구현했다.
- `_links.next` 기반 cursor pagination을 처리했다.
- 429, 5xx, timeout은 retryable로 처리하고 400, 401, 403, 404는 non-retry 또는 item-level failure로 분류했다.
- `map_page_metadata_to_snapshot_item()` helper를 추가해 Confluence Page metadata 응답을 feature1 `PageSnapshotItem` schema로 변환하게 했다.
- 오류 문자열에서 access token, Authorization, Bearer 문자열이 노출되지 않도록 redaction을 적용했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_confluence_metadata_client.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_confluence_metadata_client.py`: 구현 전 import 실패 확인 후, 구현 후 13 passed.
- `python3.11 -m pytest`: 32 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature4_diff_engine`: previous/current snapshot 비교, `new`, `updated`, `unchanged`, `deleted_candidate` 분류 테스트 우선 구현.

## 2026-05-15 - Data Sync Agent feature2_snapshot_repository

### 작업 목표

- Data Sync Agent의 local snapshot repository를 구현한다.
- previous snapshot JSON 로드, missing file 빈 snapshot 처리, malformed/schema invalid 오류 처리, current snapshot JSON 저장을 지원한다.
- Confluence metadata client, diff engine, changed page processing, deleted/message payload, LangGraph workflow, MongoDB/RabbitMQ/Qdrant 등 feature3 이후 범위는 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-sync-agent/tests/unit/test_snapshot_repository.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `data_sync_agent.sync.snapshot_repository` 미구현으로 `ModuleNotFoundError` 실패를 확인했다.
- 테스트 케이스에는 valid previous snapshot 복원, missing previous snapshot 빈 snapshot 반환, malformed JSON 오류, schema invalid 오류, current snapshot 저장, 디렉토리 자동 생성, format metadata, 민감정보 비저장, feature1 `PageSnapshot` schema round trip 호환을 포함했다.

### 구현 내용

- `ai-agent/data-sync-agent/src/data_sync_agent/sync/snapshot_repository.py`를 추가했다.
- `SnapshotRepository` protocol, `LocalSnapshotRepository`, `SnapshotRepositoryError`, `SnapshotWriteResult`를 정의했다.
- snapshot file envelope에 `format_version=data-sync-snapshot-v1`, `generated_at`, `snapshot`을 기록하게 했다.
- `load_previous_snapshot()`은 파일이 없을 때 `empty-previous-{sync_id}` 빈 `PageSnapshot`을 반환한다.
- malformed JSON과 schema invalid snapshot은 `SnapshotRepositoryError`로 명확히 분류한다.
- `save_current_snapshot()`은 기본 경로 `output_dir/snapshots/latest_snapshot.json` 또는 지정 경로에 JSON을 저장하고 필요한 디렉토리를 생성한다.
- 저장 payload는 feature1 schema의 `PageSnapshot.to_dict()`만 사용해 access token, Authorization header, secret-like runtime value가 포함되지 않도록 했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_snapshot_repository.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_snapshot_repository.py`: 구현 전 `ModuleNotFoundError` 실패 확인 후, 구현 후 8 passed.
- `python3.11 -m pytest`: 19 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature3_confluence_metadata_client`: Confluence metadata API client, pagination, retry/backoff 테스트 우선 구현.

## 2026-05-14 - Data Sync Agent feature1_project_skeleton_and_schema

### 작업 목표

- Data Sync Agent의 기본 Python package 구조와 schema/config 기반을 만든다.
- `feature2` 이후 범위인 Confluence API 호출, snapshot repository, diff engine, changed page processing, LangGraph workflow, local output pipeline은 구현하지 않는다.
- `cloud_id`와 `access_token`은 외부 주입 가능한 config schema로만 정의하고, token은 안전 직렬화와 CLI 출력에서 노출하지 않는다.

### 테스트 우선 진행

- `ai-agent/data-sync-agent/tests/unit/test_schema_config.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, package 미구현으로 `ModuleNotFoundError: No module named 'data_sync_agent'`가 발생하는 실패를 확인했다.
- 테스트 케이스에는 config 외부 주입과 token redaction, 필수값 validation, page snapshot/page key, sync job, changed document, deleted candidate, message payload, sync report, failed item schema 검증을 포함했다.

### 구현 내용

- `ai-agent/data-sync-agent/pyproject.toml`을 추가했다.
- `src/data_sync_agent` package 기본 구조를 추가했다.
- `DataSyncConfig`를 추가하고 필수값 검증 및 `to_safe_dict()` token redaction을 구현했다.
- sync job, page snapshot, changed document, deleted item, message payload, sync report, failed item schema를 추가했다.
- changed document는 Data Ingestion Agent processed document 계약과 호환되는 `source_type`, `space`, `page`, `body`, `metadata` 구조를 유지하고 `sync_id`, `change_type`을 추가했다.
- deleted item은 확정 삭제가 아닌 `deleted_candidate`, `snapshot_missing`, `requires_confirmation=true`로만 표현하게 했다.
- message payload는 후속 RabbitMQ 연동을 고려한 local payload schema만 정의했다.
- `scripts/run_delta_sync.py`는 config 검증과 app context 생성까지만 수행하는 최소 skeleton으로 추가했다.
- fixture, integration test, local data output 디렉토리 placeholder를 추가했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_schema_config.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_schema_config.py`: 구현 전 `ModuleNotFoundError` 실패 확인 후, 구현 후 11 passed.
- `python3.11 -m pytest`: 11 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature2_snapshot_repository`: previous/current snapshot load/save와 malformed snapshot 처리 테스트 우선 구현.

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
