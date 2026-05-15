# Data Sync Agent MVP 개발 계획

## 0. 기존 계획 교체 확인

- [x] 기존 `docs/ai/current-plan.md`가 Data Ingestion Agent 계획임을 확인했다.
- [x] 기존 계획의 Data Ingestion Agent feature1-6 및 전체 MVP 완료 체크를 확인했다.
- [x] `docs/ai/working-log.md`에 Data Ingestion Agent feature1-6 작업 기록과 MVP 완료 기록이 있음을 확인했다.
- [x] 이번 작업을 위해 `docs/ai/current-plan.md`를 Data Sync Agent 전용 계획으로 교체한다.
- [x] Data Ingestion Agent 계획과 Data Sync Agent 계획을 한 파일에 섞지 않는다.

## 1. 작업 범위 확인

- [x] 프로젝트 root: `/Users/younghoonlee/workspace_prj/ai-agent-templates`
- [x] 담당 영역: `ai-agent/data-sync-agent`
- [x] 초기 계획 세션 목표: Data Sync Agent 개발 계획 수립 및 본 파일 저장
- [x] 초기 계획 세션에서는 구현 코드를 작성하지 않았다.
- [x] API/DB 계약 변경 없음
- [x] Secret, token, cloud id, `.env` 생성 또는 하드코딩 금지

## 2. 확인한 문서

- [x] `AGENTS.md`
- [x] `docs/architecture.md`
- [x] `docs/conventions.md`
- [x] `docs/ai/workflow.md`
- [x] `docs/ai/prompt-templates.md`
- [x] `ai-agent/AGENTS.md`
- [x] `ai-agent/data-sync-agent/data-sync-agent.md`

## 3. 요구사항 요약

- [x] Data Sync Agent는 Confluence 문서의 변경/삭제 후보를 감지한다.
- [x] 초기 MVP는 local snapshot 기반 Page metadata delta sync만 구현한다.
- [x] `cloud_id`, `access_token`은 CLI 인자, 환경변수, secret provider 등 외부 주입으로만 받는다.
- [x] Confluence API 직접 호출 코드는 adapter/client 계층으로 분리한다.
- [x] Space 목록과 Space별 Page metadata 목록을 수집한다.
- [x] 목록 API는 `_links.next` 기반 cursor pagination을 처리한다.
- [x] previous snapshot과 current snapshot을 비교한다.
- [x] Page key는 `{cloud_id}:{space_id}:{page_id}` 형식을 사용한다.
- [x] `version.number`, `version.createdAt` 또는 `lastModifiedAt` 변경을 기준으로 `new`, `updated`, `unchanged`, `deleted_candidate`를 분류한다.
- [x] `new`와 `updated` Page만 상세 조회한다.
- [x] 변경 Page 상세의 `storage` HTML 원문을 보존하고 plain text로 변환한다.
- [x] Data Ingestion Agent의 processed document 계약과 호환되는 changed document를 생성하되 `sync_id`, `change_type`을 추가한다.
- [x] previous에는 있으나 current에는 없는 Page는 확정 삭제가 아니라 `deleted_candidate`로 기록한다.
- [x] API 조회 실패를 삭제로 간주하지 않는다.
- [x] changed documents, deleted items, message payloads, sync report, failed items를 local file output으로 생성한다.
- [x] LangGraph node는 orchestration에 집중하고, diff/snapshot/변환/검증 로직은 테스트 가능한 함수 또는 service로 분리한다.
- [x] MVP는 CLI 기반 단일 delta sync job을 우선 지원한다.
- [x] fixture 기반 테스트를 먼저 작성한 뒤 feature별 최소 구현을 진행한다.
- [x] scheduler, MongoDB, RabbitMQ, Qdrant, FastAPI endpoint, OAuth refresh, Trash API, Webhook, Reconciliation, Attachment sync, Chunking/Embedding 실제 수행은 구현하지 않는다.
- [x] MVP 제외 기능은 필요한 경우 `interface_only`, `planned`, `not_supported_in_mvp` 상태로만 남긴다.

## 4. 수정 대상 파일/디렉토리

### 이번 세션

- [x] `docs/ai/current-plan.md`

### 후속 구현 세션에서 수정 가능한 영역

- [x] `ai-agent/data-sync-agent/pyproject.toml`
- [x] `ai-agent/data-sync-agent/src/data_sync_agent/**`
- [x] `ai-agent/data-sync-agent/tests/**`
- [x] `ai-agent/data-sync-agent/scripts/**`
- [x] `ai-agent/data-sync-agent/data/snapshots/**`
- [x] `ai-agent/data-sync-agent/data/changed/**`
- [x] `ai-agent/data-sync-agent/data/deleted/**`
- [x] `ai-agent/data-sync-agent/data/messages/**`
- [x] `ai-agent/data-sync-agent/data/reports/**`
- [x] `ai-agent/data-sync-agent/data/failed/**`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

### 수정하지 않은 영역 확인

- [x] `ai-agent/data-ingestion-agent/**` 수정 없음
- [x] 다른 Agent 디렉토리 수정 없음
- [x] `backend/**` 수정 없음
- [x] `frontend/**` 수정 없음
- [x] `rag-pipeline/**` 수정 없음
- [x] `infra/**` 수정 없음
- [x] `docs/api-spec.md` 및 `docs/db-schema.md` 수정 없음
- [x] Secret, token, credential, `.env` 파일 생성 또는 수정 없음

## 5. Feature Breakdown 및 테스트 계획

### feature1_project_skeleton_and_schema

- [x] package 구조 생성
- [x] `pyproject.toml` 설정
- [x] sync job schema 정의
- [x] page snapshot schema 정의
- [x] changed document schema 정의
- [x] deleted item schema 정의
- [x] message payload schema 정의
- [x] sync report / failed item schema 정의
- [x] CLI config schema 정의
- [x] MongoDB/RabbitMQ/Qdrant/Scheduler/Attachment 등 MVP 제외 지점은 실제 구현 없이 명시적 상태 또는 interface만 정의

테스트 케이스:

- [x] page snapshot schema가 `snapshot_id`, `sync_id`, `cloud_id`, `created_at`, `pages` 필드를 검증한다.
- [x] page snapshot item의 `page_key`가 `{cloud_id}:{space_id}:{page_id}` 형식으로 생성된다.
- [x] changed document schema가 Data Ingestion Agent processed document 호환 필드와 `sync_id`, `change_type`을 보존한다.
- [x] deleted item schema가 `delete_type=deleted_candidate`, `detection_method=snapshot_missing`, `requires_confirmation=true`를 검증한다.
- [x] message payload schema가 `chunking_requested`, `delete_candidate_detected` 이벤트를 검증한다.
- [x] sync report schema가 counts와 output_paths를 보존한다.
- [x] config schema는 `cloud_id`, `access_token`, `previous_snapshot`, `output_dir` 누락 시 검증 실패한다.
- [x] schema/config 직렬화 결과에 access token이 포함되지 않는다.

### feature2_snapshot_repository

- [x] previous snapshot 로드
- [x] current snapshot 저장
- [x] previous snapshot 없음 처리
- [x] malformed snapshot 처리
- [x] snapshot repository 테스트 작성

테스트 케이스:

- [x] valid previous snapshot JSON을 schema 객체로 로드한다.
- [x] previous snapshot 파일이 없으면 빈 snapshot으로 처리한다.
- [x] malformed JSON은 failed item 또는 명확한 snapshot load error로 분류된다.
- [x] required field가 누락된 snapshot은 검증 실패한다.
- [x] current snapshot을 `data/snapshots/latest_snapshot.json` 또는 지정 경로에 저장한다.
- [x] snapshot 저장 결과에 token, Authorization header가 포함되지 않는다.
- [x] 저장 디렉토리가 없으면 필요한 디렉토리를 생성한다.

### feature3_confluence_metadata_client

- [x] Confluence API client 구현
- [x] `GET /spaces?limit=25` 호출
- [x] `GET /spaces/{spaceId}/pages?limit=25&body-format=storage` 호출
- [x] `GET /pages/{pageId}?body-format=storage&include-version=true` 상세 호출 인터페이스 준비
- [x] `_links.next` cursor pagination 처리
- [x] 429, 5xx, timeout retry/backoff 기본 처리
- [x] 400, 401, 403, 404 오류 분류
- [x] client/pagination 테스트 작성

테스트 케이스:

- [x] client가 Base URL에 외부 주입된 `cloud_id`를 사용한다.
- [x] Authorization header는 요청에 포함되지만 로그나 예외 문자열에 노출되지 않는다.
- [x] spaces pagination에서 `_links.next`를 따라 모든 Space를 수집한다.
- [x] space pages pagination에서 `_links.next`를 따라 모든 Page metadata를 수집한다.
- [x] page metadata 요청에 `limit=25`, `body-format=storage`가 포함된다.
- [x] changed page detail 요청에 `body-format=storage`, `include-version=true`가 포함된다.
- [x] 429 또는 5xx 응답은 retryable failure로 분류하고 max retry를 따른다.
- [x] timeout은 retryable failure로 분류한다.
- [x] 401은 retry하지 않고 auth failure로 분류한다.
- [x] 403/404는 item-level failure로 변환 가능한 오류 정보를 남긴다.
- [x] max retry 초과 시 민감정보 없는 오류를 반환하거나 발생시킨다.

### feature4_diff_engine

- [x] page key 생성
- [x] previous/current snapshot 비교
- [x] `new`, `updated`, `unchanged`, `deleted_candidate` 분류
- [x] version number 변경 감지
- [x] version createdAt 또는 lastModifiedAt 변경 감지
- [x] API 실패와 삭제 후보 구분
- [x] diff engine 테스트 작성

테스트 케이스:

- [x] previous에 없고 current에 있는 page는 `new`로 분류된다.
- [x] version number가 바뀐 page는 `updated`로 분류된다.
- [x] lastModifiedAt 또는 version createdAt이 바뀐 page는 `updated`로 분류된다.
- [x] version/modified metadata가 동일한 page는 `unchanged`로 분류된다.
- [x] previous에는 있고 current에는 없는 page는 `deleted_candidate`로 분류된다.
- [x] API 실패로 수집하지 못한 Space/Page는 deleted candidate로 오분류하지 않는다.
- [x] diff 결과가 changed refs, unchanged refs, deleted candidates, failed refs를 분리한다.
- [x] page key 생성 함수가 cloud/space/page id를 안정적으로 결합한다.

### feature5_changed_page_processing

- [x] `new`/`updated` Page 상세 조회
- [x] `unchanged` Page 상세 조회 생략
- [x] storage HTML 원문 보존
- [x] HTML to plain text 변환
- [x] changed document 생성
- [x] attachment 상태를 `not_supported_in_mvp`로 기록
- [x] 처리 테스트 작성

테스트 케이스:

- [x] `new` Page는 상세 조회 후 `change_type=new` changed document가 생성된다.
- [x] `updated` Page는 상세 조회 후 `change_type=updated` changed document가 생성된다.
- [x] `unchanged` Page는 상세 조회하지 않는다.
- [x] changed document가 Data Ingestion Agent processed document 호환 필드를 포함한다.
- [x] storage HTML 원문과 plain text가 분리 저장된다.
- [x] `document_id`가 `confluence-page-{page_id}-{version_number}` 형식으로 생성된다.
- [x] Page 상세 조회 실패는 failed item으로 기록된다.
- [x] 빈 body.storage는 빈 HTML/plain text로 안전하게 처리된다.
- [x] attachment/macro 태그가 있어도 실패하지 않고 attachment status는 `not_supported_in_mvp`로 남는다.

### feature6_deleted_and_message_payloads

- [x] deleted item 생성
- [x] `chunking_requested` message payload 생성
- [x] `delete_candidate_detected` message payload 생성
- [x] local message writer 구현
- [x] payload 테스트 작성

테스트 케이스:

- [x] `deleted_candidate` diff item이 canonical deleted item으로 변환된다.
- [x] deleted item은 `requires_confirmation=true`를 포함한다.
- [x] changed document마다 `chunking_requested` payload가 생성된다.
- [x] deleted item마다 `delete_candidate_detected` payload가 생성된다.
- [x] payload의 `payload_ref`가 local output path 또는 stable reference를 가리킨다.
- [x] message payload JSONL이 local file로 저장된다.
- [x] payload에 access token, Authorization header가 포함되지 않는다.
- [x] RabbitMQ 발행은 구현하지 않고 local message writer 또는 `interface_only` 상태로만 남긴다.

### feature7_langgraph_workflow_and_cli

- [x] `load_config -> load_previous_snapshot -> list_spaces -> fetch_current_page_metadata -> build_current_snapshot -> diff_snapshots -> fetch_changed_page_details -> transform_changed_html -> build_changed_documents -> build_deleted_items -> build_message_payloads -> write_outputs -> write_report` workflow 구성
- [x] LangGraph node는 orchestration 중심으로 유지
- [x] LangGraph optional dependency 또는 fallback 처리
- [x] CLI 실행 스크립트 구현
- [x] local output 저장
- [x] fixture 기반 workflow integration test 작성

테스트 케이스:

- [x] fixture client를 주입한 workflow가 delta sync를 완료한다.
- [x] workflow가 previous snapshot을 로드하고 current snapshot을 저장한다.
- [x] workflow가 `new`/`updated`만 상세 조회한다.
- [x] partial page detail failure가 failed item으로 기록되고 가능한 output은 생성된다.
- [x] empty previous snapshot은 모든 current page를 `new`로 분류한다.
- [x] empty current snapshot은 previous pages를 `deleted_candidate`로 분류한다.
- [x] CLI는 `--cloud-id`, `--access-token`, `--previous-snapshot`, `--output-dir`를 받아 workflow를 호출한다.
- [x] CLI는 필요 시 `--request-delay`, `--max-retries`, `--timeout`을 config에 반영한다.
- [x] CLI stdout/stderr에 token 또는 Authorization 값이 포함되지 않는다.
- [x] output dir 미존재 시 필요한 하위 디렉토리를 생성한다.
- [x] LangGraph 미설치 환경이면 명확한 fallback 또는 오류가 있다.

### feature8_fixture_and_safety_tests

- [x] synthetic previous/current fixture 작성
- [x] synthetic partial failure fixture 작성
- [x] token safety 테스트
- [x] output report 검증
- [x] boundary test 작성

테스트 케이스:

- [x] fixture에는 실제 회사 문서, 개인정보, 실제 token, 실제 cloud id가 포함되지 않는다.
- [x] fixture 기반 full delta workflow가 changed/deleted/messages/report/failed/snapshot 파일을 생성한다.
- [x] processed changed document가 canonical 필수 필드를 모두 포함한다.
- [x] HTML 원문과 plain text가 모두 보존된다.
- [x] report의 total/new/updated/unchanged/deleted_candidate/failed count가 fixture 결과와 일치한다.
- [x] partial failure fixture에서 실패 Page가 failed item으로 기록된다.
- [x] empty previous/current snapshot boundary가 예외 없이 처리된다.
- [x] malformed previous snapshot boundary가 명확한 실패로 처리된다.
- [x] unsupported attachment/macro fixture에서 MVP 미지원 상태가 명시되고 전체 workflow가 실패하지 않는다.
- [x] CLI stdout/stderr에 access token, Authorization header, secret-like 문자열이 포함되지 않는다.
- [x] output JSON/JSONL/report/failed/message/snapshot 파일에 access token이나 Authorization 값이 포함되지 않는다.
- [x] 전체 테스트 suite가 통과한다.

## 6. 구현 순서

- [x] 1단계: `feature1_project_skeleton_and_schema` 테스트 작성 후 최소 구현
- [x] 2단계: `feature2_snapshot_repository` 테스트 작성 후 최소 구현
- [x] 3단계: `feature3_confluence_metadata_client` 테스트 작성 후 최소 구현
- [x] 4단계: `feature4_diff_engine` 테스트 작성 후 최소 구현
- [x] 5단계: `feature5_changed_page_processing` 테스트 작성 후 최소 구현
- [x] 6단계: `feature6_deleted_and_message_payloads` 테스트 작성 후 최소 구현
- [x] 7단계: `feature7_langgraph_workflow_and_cli` 테스트 작성 후 최소 구현
- [x] 8단계: `feature8_fixture_and_safety_tests` 보강 및 전체 검증

## 7. 예상 영향 범위

- [x] `ai-agent/data-sync-agent` 내부에 독립 실행 가능한 Python package, tests, fixtures, scripts가 추가된다.
- [x] local snapshot 기반 delta sync와 local output 파일 생성 경로가 정의된다.
- [x] Backend, Frontend, RAG Pipeline, Infra, 다른 Agent에는 영향이 없어야 한다.
- [x] Public API, DB Schema, 인증/인가 흐름은 변경하지 않는다.
- [x] Data Ingestion Agent 구현은 수정하지 않는다.

## 8. 문서 수정 필요 여부

- [x] 이번 세션: `docs/ai/current-plan.md`를 Data Sync Agent 전용 계획으로 교체
- [x] 후속 feature 구현 중 설계 결정 또는 실행 결과는 `docs/ai/working-log.md`에 기록
- [x] API endpoint를 추가하지 않으므로 `docs/api-spec.md` 수정 불필요
- [x] DB 저장을 구현하지 않으므로 `docs/db-schema.md` 수정 불필요
- [x] 아키텍처 변경이 아니므로 `docs/architecture.md` 수정 불필요

## 9. 완료 기준

### 이번 세션 완료 기준

- [x] 기존 Data Ingestion Agent 계획 완료 여부와 working-log 완료 기록을 확인했다.
- [x] 필수 문서 7개를 읽고 Data Sync Agent 요구사항을 요약했다.
- [x] `Feature Breakdown` 기준 feature 목록을 정리했다.
- [x] feature별 테스트 케이스를 먼저 정의했다.
- [x] 구현 순서를 정했다.
- [x] 수정할 파일/디렉토리와 수정하지 않을 영역을 구분했다.
- [x] 완료 기준과 검증 명령을 정리했다.
- [x] 계획을 `docs/ai/current-plan.md`에 체크리스트 형태로 저장했다.
- [x] 구현 코드는 작성하지 않았다.

### 전체 MVP 완료 기준

- [x] Confluence metadata client, pagination, retry/backoff가 fixture/mock 기반 테스트로 검증된다.
- [x] previous/current snapshot repository가 fixture 기반 테스트로 검증된다.
- [x] diff engine이 `new`, `updated`, `unchanged`, `deleted_candidate`를 올바르게 분류한다.
- [x] `new`/`updated` Page만 상세 조회되고 changed document로 생성된다.
- [x] changed document, deleted item, message payload, sync report, failed item이 canonical schema를 따른다.
- [x] CLI delta sync가 fixture/mock 기반 integration test로 검증된다.
- [x] local output 파일 검증과 token safety 테스트가 통과한다.
- [x] MVP 제외 기능은 실제 동작 없이 `not_supported_in_mvp`, `interface_only`, `planned` 중 하나로 명시된다.
- [x] `./scripts/format.sh`, `./scripts/lint.sh`, `./scripts/test.sh`, `./scripts/verify.sh` 결과를 기록한다.
- [x] `git diff` 기준으로 요청 범위 외 변경이 없다.

## 10. 검증 명령

후속 구현 완료 전 아래 명령을 실행한다.

```bash
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

Feature별 구현 세션에서는 해당 package 테스트 명령을 먼저 실행하고, milestone 완료 시 루트 검증 명령을 실행한다. Python package가 `ai-agent/data-sync-agent` 하위에 구성되면 agent 디렉토리에서 다음 명령을 별도로 실행한다.

```bash
python3.11 -m pytest
python3.11 -m compileall src scripts
```
