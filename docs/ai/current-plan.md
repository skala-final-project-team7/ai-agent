# Data Ingestion Agent MVP 개발 계획

## 0. 작업 범위 확인

- [x] 프로젝트 root: `/Users/younghoonlee/workspace_prj/ai-agent-templates`
- [x] 담당 영역: `ai-agent/data-ingestion-agent`
- [x] 이번 세션 목표: Data Ingestion Agent 구현 계획 수립 및 본 파일 저장
- [x] 이번 세션에서 구현 코드 작성 금지
- [x] API/DB 계약 변경 없음
- [x] Secret, token, cloud id, `.env` 생성 또는 하드코딩 금지

## 1. 확인한 문서

- [x] `AGENTS.md`
- [x] `docs/architecture.md`
- [x] `docs/conventions.md`
- [x] `docs/ai/workflow.md`
- [x] `docs/ai/prompt-templates.md`
- [x] `ai-agent/AGENTS.md`
- [x] `ai-agent/data-ingestion-agent/data-ingestion-agent.md`

## 2. 요구사항 요약

- [ ] Data Ingestion Agent는 Confluence API를 직접 호출한다.
- [ ] `cloud_id`, `access_token`은 CLI 인자, 환경변수, secret provider 등 외부 주입으로만 받는다.
- [ ] 접근 가능한 Space 목록을 조회하고 각 Space의 `homepageId` 기준 descendants Page Tree를 수집한다.
- [ ] Page 상세 API에서 `body.storage.value`를 수집한다.
- [ ] storage HTML 원문은 보존하고, 별도 plain text 필드로 변환한다.
- [ ] 후속 Chunking/Embedding/RAG 파이프라인이 사용할 processed document JSON/JSONL 산출물을 만든다.
- [ ] ingestion report와 failed item을 로컬 파일로 생성한다.
- [ ] Page 단위 실패는 job 전체 실패로 바로 확정하지 않고 failed item으로 기록한다.
- [ ] LangGraph node는 orchestration만 담당하고, 핵심 변환/검증 로직은 일반 함수 또는 service로 분리한다.
- [ ] MVP는 CLI 기반 단일 full crawl job을 우선 지원한다.
- [ ] fixture 기반 테스트를 먼저 작성한 뒤 feature별 최소 구현을 진행한다.
- [ ] 첨부파일 추출, MongoDB 저장, RabbitMQ 발행, FastAPI endpoint, Qdrant upsert, Chunking/Embedding 실제 수행은 구현하지 않는다.
- [ ] MVP 제외 기능은 필요한 경우 `interface_only`, `planned`, `not_supported_in_mvp` 상태로만 남긴다.

## 3. 수정 대상 파일/디렉토리

### 이번 세션

- [x] `docs/ai/current-plan.md`

### 후속 구현 세션에서 수정 가능한 영역

- [ ] `ai-agent/data-ingestion-agent/pyproject.toml`
- [ ] `ai-agent/data-ingestion-agent/src/data_ingestion_agent/**`
- [ ] `ai-agent/data-ingestion-agent/tests/**`
- [ ] `ai-agent/data-ingestion-agent/scripts/**`
- [ ] `ai-agent/data-ingestion-agent/data/raw/**`
- [ ] `ai-agent/data-ingestion-agent/data/processed/**`
- [ ] `ai-agent/data-ingestion-agent/data/reports/**`
- [ ] `ai-agent/data-ingestion-agent/data/failed/**`
- [ ] `docs/ai/current-plan.md`
- [ ] `docs/ai/working-log.md` 또는 해당 파일이 없으면 후속 세션에서 필요 시 생성

### 수정하지 않을 영역

- [ ] `ai-agent/data-sync-agent/**`
- [ ] 다른 Agent 디렉토리
- [ ] `backend/**`
- [ ] `frontend/**`
- [ ] `rag-pipeline/**`
- [ ] `infra/**`
- [ ] `docs/api-spec.md` 및 `docs/db-schema.md`, 단 API/DB 계약 변경이 별도 승인되는 경우 제외
- [ ] Secret, token, credential, `.env` 파일

## 4. Feature Breakdown 및 테스트 계획

### feature1_project_skeleton_and_schema

- [x] package 구조 생성
- [x] `pyproject.toml` 설정
- [x] ingestion job, processed document, failed item, report schema 정의
- [x] CLI config 구조 정의
- [x] MongoDB/RabbitMQ/Attachment/Embedding 등 MVP 제외 지점은 실제 구현 없이 명시적 상태 또는 interface만 정의

테스트 케이스:

- [x] processed document schema가 canonical 필수 필드를 검증한다.
- [x] `document_id`가 `confluence-page-{page_id}-{version_number}` 형식으로 생성된다.
- [x] failed item schema가 stage, item_type, retryable, attempt_count를 검증한다.
- [x] ingestion report schema가 counts와 output_paths를 보존한다.
- [x] CLI config는 `cloud_id`, `access_token`, `output_dir` 누락 시 검증 실패한다.
- [x] schema 직렬화 결과에 access token이 포함되지 않는다.

### feature2_confluence_client_and_pagination

- [x] Confluence API client 구현
- [x] `GET /spaces?limit=25` 호출
- [x] `GET /pages/{homepageId}/descendants?limit=25` 호출
- [x] `GET /pages/{pageId}?body-format=storage&include-version=true` 호출
- [x] `_links.next` cursor pagination 처리
- [x] 429, 5xx, timeout retry/backoff 기본 처리
- [x] 400, 401, 403, 404 오류 분류

테스트 케이스:

- [x] client가 Base URL에 외부 주입된 `cloud_id`를 사용한다.
- [x] Authorization header는 외부 주입된 token으로 구성하되 로그나 예외 메시지에 노출하지 않는다.
- [x] spaces pagination에서 `_links.next`를 따라 모든 page를 합친다.
- [x] descendants pagination에서 모든 page ref를 합친다.
- [x] page detail 요청에 `body-format=storage`, `include-version=true`가 포함된다.
- [x] 429 또는 5xx 응답은 retryable failure로 분류하고 최대 재시도 횟수를 따른다.
- [x] 403/404 page detail 실패는 item failure로 변환 가능한 오류 정보를 남긴다.

### feature3_html_extraction

- [x] storage HTML 원문 보존
- [x] plain text 변환
- [x] heading, paragraph, list, table, link 처리
- [x] malformed HTML 처리
- [x] 빈 본문 처리

테스트 케이스:

- [x] 입력 storage HTML이 processed document의 `storage_html`에 원문 그대로 보존된다.
- [x] heading과 paragraph가 읽기 가능한 줄 단위 plain text로 변환된다.
- [x] ul/ol list 항목이 plain text에서 항목 경계를 잃지 않는다.
- [x] table cell 텍스트가 행/열 순서를 유지한 plain text로 변환된다.
- [x] link는 표시 텍스트를 plain text에 포함한다.
- [x] malformed HTML도 예외로 job을 중단하지 않고 가능한 plain text를 반환한다.
- [x] script/style 또는 의미 없는 markup은 plain text에서 제거된다.

### feature4_processed_document_pipeline

- [x] raw page detail to processed document mapping
- [x] failed item 생성
- [x] ingestion report 생성
- [x] local file repository 구현
- [x] attachment 상태를 `not_supported_in_mvp`로 기록

테스트 케이스:

- [x] page detail fixture가 canonical processed document로 매핑된다.
- [x] space/page metadata가 `space`, `page`, `metadata` 필드에 정확히 들어간다.
- [x] `content_length`, `plain_text_length`, `has_attachments`, `attachment_processing_status`가 산출된다.
- [x] page detail 변환 실패가 failed item으로 기록된다.
- [x] local repository가 documents JSONL, report JSON, failed items JSONL을 지정 output dir 아래에 쓴다.
- [x] ingestion report counts가 수집/성공/실패/쓰기 결과와 일치한다.
- [x] 산출물에 access token이 포함되지 않는다.

### feature5_langgraph_workflow_and_cli

- [x] `load_config -> list_spaces -> collect_page_tree -> fetch_page_details -> transform_html -> build_processed_documents -> write_outputs -> write_report` workflow 구성
- [x] LangGraph node는 orchestration 중심으로 유지
- [x] CLI 실행 스크립트 구현
- [x] local output 저장
- [x] fixture 기반 workflow integration test 작성

테스트 케이스:

- [x] fixture client를 주입한 workflow가 full crawl을 완료한다.
- [x] 일부 page detail 실패 시 workflow가 `completed_with_errors` report를 생성한다.
- [x] 전체 인증 실패 또는 list_spaces 실패 시 job 실패 report를 생성한다.
- [x] CLI는 `--cloud-id`, `--access-token`, `--output-dir`를 받아 workflow를 호출한다.
- [x] CLI 출력과 로그에 token이 포함되지 않는다.
- [x] output dir 미존재 시 필요한 하위 디렉토리를 생성한다.

### feature6_fixture_and_safety_tests

- [x] synthetic Confluence fixture 작성
- [x] token safety 테스트
- [x] output file 검증
- [x] boundary test 작성

테스트 케이스:

- [x] fixture에는 실제 회사 문서, 개인정보, 실제 token, 실제 cloud id가 포함되지 않는다.
- [x] output JSON/JSONL 전체에 access token 문자열이 포함되지 않는다.
- [x] 빈 spaces 응답에서 completed report와 0 counts가 생성된다.
- [x] homepageId가 없는 space는 failed item 또는 skip policy로 일관되게 처리된다.
- [x] 빈 HTML 본문은 빈 plain text와 정상 metadata로 처리된다.
- [x] 매우 긴 HTML 본문도 schema 직렬화와 파일 쓰기에서 실패하지 않는다.
- [x] attachment 관련 필드는 항상 `not_supported_in_mvp` 정책을 따른다.

## 5. 구현 순서

- [x] 1단계: `feature1_project_skeleton_and_schema` 테스트 작성 후 최소 구현
- [x] 2단계: `feature2_confluence_client_and_pagination` 테스트 작성 후 최소 구현
- [x] 3단계: `feature3_html_extraction` 테스트 작성 후 최소 구현
- [x] 4단계: `feature4_processed_document_pipeline` 테스트 작성 후 최소 구현
- [x] 5단계: `feature5_langgraph_workflow_and_cli` 테스트 작성 후 최소 구현
- [x] 6단계: `feature6_fixture_and_safety_tests` 보강 및 전체 검증

## 6. 예상 영향 범위

- [x] `ai-agent/data-ingestion-agent` 내부에 독립 실행 가능한 Python package, tests, fixtures, scripts가 추가된다.
- [x] 로컬 파일 기반 processed output/report/failed item 생성 경로가 정의된다.
- [x] Backend, Frontend, RAG Pipeline, Infra, 다른 Agent에는 영향이 없어야 한다.
- [x] Public API, DB Schema, 인증/인가 흐름은 변경하지 않는다.

## 7. 문서 수정 필요 여부

- [x] 이번 세션: `docs/ai/current-plan.md` 생성만 필요
- [x] 후속 feature 구현 중 설계 결정 또는 실행 결과는 `docs/ai/working-log.md`에 기록
- [ ] API endpoint를 추가하지 않으므로 `docs/api-spec.md` 수정 불필요
- [ ] DB 저장을 구현하지 않으므로 `docs/db-schema.md` 수정 불필요
- [ ] 아키텍처 변경이 아니므로 `docs/architecture.md` 수정 불필요

## 8. 완료 기준

### 이번 세션 완료 기준

- [x] 필수 문서 7개를 읽고 요구사항을 요약했다.
- [x] `Feature Breakdown` 기준 feature 목록을 정리했다.
- [x] feature별 테스트 케이스를 먼저 정의했다.
- [x] 구현 순서를 정했다.
- [x] 수정할 파일/디렉토리와 수정하지 않을 영역을 구분했다.
- [x] 완료 기준과 검증 명령을 정리했다.
- [x] 계획을 `docs/ai/current-plan.md`에 체크리스트 형태로 저장했다.
- [x] 구현 코드는 작성하지 않았다.

### 전체 MVP 완료 기준

- [x] Confluence API client, pagination, retry/backoff가 fixture/mock 기반 테스트로 검증된다.
- [x] storage HTML 원문 보존과 plain text 변환이 fixture 기반 테스트로 검증된다.
- [x] processed document, failed item, ingestion report가 canonical schema를 따른다.
- [x] CLI full crawl이 fixture/mock 기반 integration test로 검증된다.
- [x] 로컬 output 파일 검증과 token safety 테스트가 통과한다.
- [x] MVP 제외 기능은 실제 동작 없이 `not_supported_in_mvp`, `interface_only`, `planned` 중 하나로 명시된다.
- [x] `./scripts/format.sh`, `./scripts/lint.sh`, `./scripts/test.sh`, `./scripts/verify.sh` 결과를 기록한다.
- [x] `git diff` 기준으로 요청 범위 외 변경이 없다.

## 9. 검증 명령

후속 구현 완료 전 아래 명령을 실행한다.

```bash
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

Feature별 구현 세션에서는 해당 package 테스트 명령을 먼저 실행하고, milestone 완료 시 루트 검증 명령을 실행한다.
