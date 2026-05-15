# History Manager Agent MVP 개발 계획

## 0. 기존 계획 교체 확인

- [x] 기존 `docs/ai/current-plan.md`가 Data Sync Agent 계획임을 확인했다.
- [x] `docs/ai/working-log.md`에 Data Sync Agent feature1-8 완료 및 MVP 마감 기록이 있음을 확인했다.
- [x] 이번 작업을 위해 `docs/ai/current-plan.md`를 History Manager Agent 전용 계획으로 교체한다.
- [x] Data Sync Agent 계획과 History Manager Agent 계획을 한 파일에 섞지 않는다.
- [x] 이번 세션에서는 구현 코드를 작성하지 않는다.

## 1. 작업 범위 확인

- [x] 프로젝트 root: `/Users/younghoonlee/workspace_prj/ai-agent-templates`
- [x] 담당 영역: `ai-agent/history-manager-agent`
- [x] 목표: History Manager Agent MVP 개발 계획 수립 및 본 파일 저장
- [x] API/DB 계약 변경 없음
- [x] Secret, token, API key, `.env` 생성 또는 하드코딩 금지
- [x] `OPENAI_API_KEY`는 외부 주입 방식으로만 사용한다.

## 2. 확인한 문서

- [x] `AGENTS.md`
- [x] `docs/architecture.md`
- [x] `docs/conventions.md`
- [x] `docs/ai/workflow.md`
- [x] `docs/ai/prompt-templates.md`
- [x] `ai-agent/AGENTS.md`
- [x] `ai-agent/history-manager-agent/history-manager-agent.md`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

## 3. 요구사항 요약

- [x] History Manager Agent는 RAG 파이프라인의 Entry Agent다.
- [x] BFF가 전달한 conversation history JSON과 현재 질문을 입력으로 받는다.
- [x] 현재 질문을 `follow_up`, `new_topic`, `ambiguous` 중 하나로 분류한다.
- [x] `confidence`와 `reason`을 항상 포함한다.
- [x] `follow_up`은 최근 대화 맥락을 보존하고 독립적인 `contextualized_question`을 생성한다.
- [x] `new_topic`은 이전 맥락을 reset하고 원문 질문을 유지한다.
- [x] `ambiguous`는 보수적으로 최소 context만 보존하고 낮은 confidence를 표현한다.
- [x] `preserved_context.summary`, `entities`, `turn_refs`를 생성한다.
- [x] Query Routing Agent가 바로 소비 가능한 routing input schema를 생성한다.
- [x] 최근 N개 turn 및 `max_context_chars` 기준 context trimming을 deterministic service로 구현한다.
- [x] malformed turn은 가능한 범위에서 warning으로 기록하고 처리를 계속한다.
- [x] 빈 history는 `new_topic`으로 처리한다.
- [x] OpenAI provider는 provider interface 뒤에 분리한다.
- [x] 기본 테스트 suite는 fake LLM provider만 사용한다.
- [x] 실제 OpenAI live smoke test는 opt-in 방식으로 기본 테스트에서 제외한다.
- [x] LangGraph node는 orchestration에 집중하고 핵심 분류/정규화/정책/재작성 로직은 테스트 가능한 함수 또는 service로 분리한다.
- [x] MVP는 CLI 수동 실행과 local JSON input/output을 우선 지원한다.
- [x] BFF API 직접 호출, DB 직접 조회, DB 저장/갱신, RAG 검색, 다른 Agent 구현, SSE streaming은 구현하지 않는다.
- [x] MVP 제외 기능은 `planned`, `interface_only`, `not_supported_in_mvp` 상태로만 남긴다.

## 4. 수정 대상 파일/디렉토리

### 이번 계획 세션

- [x] `docs/ai/current-plan.md`

### MVP 구현 중 생성/수정된 영역

- [x] `ai-agent/history-manager-agent/pyproject.toml`
- [x] `ai-agent/history-manager-agent/.env.example`
- [x] `ai-agent/history-manager-agent/src/history_manager_agent/**`
- [x] `ai-agent/history-manager-agent/tests/**`
- [x] `ai-agent/history-manager-agent/scripts/**`
- [x] `ai-agent/history-manager-agent/data/input/**`
- [x] `ai-agent/history-manager-agent/data/output/**`
- [x] `ai-agent/history-manager-agent/data/reports/**`
- [x] `ai-agent/history-manager-agent/data/failed/**`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

### 수정하지 않았음을 확인한 영역

- [x] `ai-agent/data-sync-agent/**`
- [x] `ai-agent/data-ingestion-agent/**`
- [x] 다른 Agent 디렉토리
- [x] `backend/**`
- [x] `frontend/**`
- [x] `rag-pipeline/**`
- [x] `infra/**`
- [x] `docs/api-spec.md` 및 `docs/db-schema.md`
- [x] 실제 `.env` 파일
- [x] Secret, token, credential, 실제 API key를 포함한 파일

## 5. OpenAI API Key 및 Provider 원칙

- [x] `OPENAI_API_KEY`는 환경변수, 로컬 secret provider, 또는 런타임 주입으로만 읽는다.
- [x] CLI 기본 인자로 raw API key를 받지 않는다.
- [x] 실제 `.env` 파일은 생성하거나 커밋하지 않는다.
- [x] 필요한 경우 `.env.example`에는 placeholder 이름만 기록하고 실제 key 형태의 값은 넣지 않는다.
- [x] OpenAI provider는 `HistoryLLMProvider` interface 뒤에 둔다.
- [x] 기본 unit/integration test는 fake LLM provider를 사용한다.
- [x] OpenAI live smoke test는 MVP 기본 검증에서 수행하지 않았고, 필요 시 별도 opt-in flag 또는 별도 script로 분리한다.
- [x] provider error, log, report, output에는 API key, Authorization header, secret-like 문자열이 포함되지 않아야 한다.

## 6. Feature Breakdown 및 테스트 계획

### feature1_project_skeleton_and_schema

- [x] package 구조 생성
- [x] `pyproject.toml` 설정
- [x] config schema 정의
- [x] conversation turn schema 정의
- [x] History Manager input schema 정의
- [x] History Decision output schema 정의
- [x] Query Routing Agent 입력 호환 schema 정의
- [x] History Report / warning / failed item schema 정의
- [x] CLI skeleton 작성
- [x] `.env.example` 필요 여부 판단 및 placeholder만 작성
- [x] schema/config 단위 테스트 작성

테스트 케이스:

- [x] config가 `history_window_turns`, `max_context_chars`, model, timeout, retry 설정을 검증한다.
- [x] config는 `OPENAI_API_KEY`를 외부 주입 가능하게 표현하되 safe serialization에서 노출하지 않는다.
- [x] conversation turn schema가 `turn_id`, `role`, `content`, `created_at`, `citations`, `metadata`를 검증한다.
- [x] input schema가 `conversation_id`, `user_id`, `current_question`, `history`, `metadata`를 검증한다.
- [x] decision schema가 `history_decision`, `contextualized_question`, `preserved_context`, `reset_required`, `confidence`, `reason`, `warnings`를 검증한다.
- [x] Query Routing input schema가 `query`, `history_decision`, `preserved_context`, `reset_required`, `metadata`를 포함한다.
- [x] report schema가 `job_id`, `conversation_id`, `status`, `decision`, counts, `created_at`을 검증한다.
- [x] 필수값 누락 시 명확한 validation error가 발생한다.
- [x] schema/config 직렬화 결과에 API key, Authorization, secret-like 값이 포함되지 않는다.

### feature2_history_input_normalization

- [x] input JSON loader 구현
- [x] conversation turn normalization 구현
- [x] role validation 구현
- [x] `created_at` 기반 정렬 구현
- [x] empty history 처리
- [x] malformed turn warning 처리
- [x] 최근 N개 turn trimming 구현
- [x] `max_context_chars` trimming 구현
- [x] normalization/trimming 테스트 작성

테스트 케이스:

- [x] valid input JSON을 History Manager input schema로 로드한다.
- [x] malformed JSON은 non-retryable failed result 또는 명확한 loader error로 분류된다.
- [x] `current_question` 누락 또는 빈 문자열은 validation error가 된다.
- [x] 입력 history 순서가 깨져 있으면 `created_at` 기준으로 정렬한다.
- [x] `user`, `assistant`, `system` role은 허용하고 unknown role은 warning 또는 invalid turn으로 처리한다.
- [x] malformed turn은 warning에 기록하고 가능한 valid turn만 유지한다.
- [x] 빈 history는 downstream에서 `new_topic` 처리가 가능하도록 빈 normalized history로 유지된다.
- [x] `history_window_turns`를 초과하면 최신 N개 turn만 유지한다.
- [x] `max_context_chars`를 초과하면 오래된 turn부터 제거한다.
- [x] system role은 보존하되 LLM 판단 입력에는 제한적으로 포함하는 정책을 검증한다.
- [x] normalization/trimming 결과에 API key, secret-like 값이 포함되지 않는다.

### feature3_llm_provider_and_classification

- [x] `HistoryLLMProvider` interface 정의
- [x] OpenAI provider 구현
- [x] fake LLM provider 구현
- [x] `follow_up` / `new_topic` / `ambiguous` classification 구현
- [x] confidence/reason parsing 구현
- [x] LLM output schema validation 구현
- [x] retry/safe error 처리 구현
- [x] provider/classification 테스트 작성

테스트 케이스:

- [x] fake provider로 `follow_up` classification을 반환할 수 있다.
- [x] fake provider로 `new_topic` classification을 반환할 수 있다.
- [x] fake provider로 `ambiguous` classification과 낮은 confidence를 반환할 수 있다.
- [x] classification result는 label, confidence, reason을 항상 포함한다.
- [x] invalid LLM output schema는 fallback 또는 safe failed item으로 처리된다.
- [x] OpenAI provider는 `OPENAI_API_KEY`를 외부 주입으로만 읽는다.
- [x] OpenAI provider는 missing API key를 provider configuration error로 분류한다.
- [x] OpenAI timeout/5xx는 retryable safe error로 분류한다.
- [x] OpenAI auth error는 non-retryable auth failure로 분류한다.
- [x] provider error/log/result 문자열에 API key, Authorization, Bearer가 포함되지 않는다.
- [x] 기본 테스트 suite는 실제 OpenAI API를 호출하지 않는다.

### feature4_context_policy

- [x] decision별 context preservation policy 구현
- [x] follow_up context summary 생성
- [x] new_topic reset policy 구현
- [x] ambiguous conservative policy 구현
- [x] preserved_context `turn_refs` / `entities` 구조 생성
- [x] context policy 테스트 작성

테스트 케이스:

- [x] `follow_up`은 `reset_required=false`이고 최근 context와 summary를 보존한다.
- [x] `new_topic`은 `reset_required=true`이고 이전 context를 비우거나 최소화한다.
- [x] `ambiguous`는 `reset_required=false`이고 최근 1-2개 turn만 보수적으로 보존한다.
- [x] preserved_context는 `summary`, `entities`, `turn_refs` 필드를 포함한다.
- [x] `turn_refs`는 output에 전체 history를 복제하지 않고 참조만 포함한다.
- [x] summary는 빈 history에서 빈 문자열 또는 안전한 기본값을 사용한다.
- [x] malformed turn warning은 decision output warnings에 반영된다.
- [x] context policy output에 API key, Authorization, secret-like 값이 포함되지 않는다.

### feature5_contextualized_question

- [x] follow_up 질문 재작성 구현
- [x] new_topic 원문 유지 구현
- [x] ambiguous fallback 구현
- [x] contextualized question validation 구현
- [x] Query Routing Agent input builder 구현
- [x] contextualized question 테스트 작성

테스트 케이스:

- [x] `follow_up`은 이전 맥락을 반영한 독립 질문을 생성한다.
- [x] `new_topic`은 current question 원문을 유지한다.
- [x] `ambiguous`는 과도한 추론 없이 원문 또는 보수적 재작성을 반환한다.
- [x] contextualized question은 빈 문자열일 수 없다.
- [x] contextualized question은 원본 history 전체를 그대로 붙이지 않는다.
- [x] Query Routing input의 `query`가 contextualized question과 일치한다.
- [x] Query Routing input은 `conversation_id`, `user_id`, `original_question`, `history_decision`, `preserved_context`, `reset_required`, `metadata`를 포함한다.
- [x] output에 API key, Authorization, secret-like 값이 포함되지 않는다.

### feature6_langgraph_workflow_and_cli

- [x] LangGraph workflow 구성
- [x] sequential fallback 구성
- [x] `load_config -> load_input -> normalize_history -> trim_history -> classify_history -> apply_context_policy -> build_contextualized_question -> build_routing_input -> write_output -> write_report` node 흐름 구현
- [x] CLI 실행 스크립트 구현
- [x] local output 저장
- [x] report 저장
- [x] fake provider 기반 workflow integration test 작성

테스트 케이스:

- [x] fake provider를 주입한 workflow가 full history decision job을 완료한다.
- [x] workflow가 local input JSON을 읽고 output decision JSON을 생성한다.
- [x] workflow가 Query Routing input JSON을 생성하거나 decision output에 포함한다.
- [x] workflow가 report JSON을 생성한다.
- [x] malformed input은 safe failed report를 생성한다.
- [x] LLM provider 실패 시 API key를 노출하지 않고 failed 또는 partial_success로 종료한다.
- [x] CLI는 `--input`, `--output`, `--report-output` 등 필요한 인자를 처리한다.
- [x] CLI는 fake provider 또는 fixture mode로 테스트 가능하다.
- [x] CLI stdout/stderr에 API key, Authorization, secret-like 값이 포함되지 않는다.
- [x] LangGraph 미설치 환경에서도 명확한 fallback 또는 오류가 있다.

### feature7_fixture_and_safety_tests

- [x] synthetic follow-up fixture 작성
- [x] synthetic new-topic fixture 작성
- [x] synthetic ambiguous fixture 작성
- [x] long history trimming fixture 작성
- [x] malformed history fixture 작성
- [x] fake provider fixture 작성
- [x] OpenAI API key/token safety 테스트 작성
- [x] output schema 검증
- [x] boundary test 작성

테스트 케이스:

- [x] fixture에는 실제 회사 문서, 개인정보, 실제 API key, secret-like 값이 포함되지 않는다.
- [x] follow-up fixture는 `follow_up`, `reset_required=false`, context 보존, contextualized question 생성을 검증한다.
- [x] new-topic fixture는 `new_topic`, `reset_required=true`, 원문 질문 유지 또는 동등 처리를 검증한다.
- [x] ambiguous fixture는 `ambiguous`, 낮은 confidence, 최소 context 보존을 검증한다.
- [x] long history fixture는 최근 N개 turn 및 max char trimming을 검증한다.
- [x] malformed history fixture는 warning과 가능한 처리 지속을 검증한다.
- [x] empty history fixture는 `new_topic` 처리로 종료된다.
- [x] output decision, routing input, report 파일 shape를 검증한다.
- [x] CLI stdout/stderr와 output/report/failed 파일에 API key, Authorization, Bearer가 포함되지 않는다.
- [x] 기본 전체 테스트 suite가 fake provider만 사용하고 외부 네트워크를 호출하지 않는다.

## 7. 구현 순서

- [x] 1단계: `feature1_project_skeleton_and_schema` 테스트 작성 후 최소 구현
- [x] 2단계: `feature2_history_input_normalization` 테스트 작성 후 최소 구현
- [x] 3단계: `feature3_llm_provider_and_classification` 테스트 작성 후 최소 구현
- [x] 4단계: `feature4_context_policy` 테스트 작성 후 최소 구현
- [x] 5단계: `feature5_contextualized_question` 테스트 작성 후 최소 구현
- [x] 6단계: `feature6_langgraph_workflow_and_cli` 테스트 작성 후 최소 구현
- [x] 7단계: `feature7_fixture_and_safety_tests` 보강 및 전체 검증

## 8. 예상 영향 범위

- [x] `ai-agent/history-manager-agent` 내부에 독립 실행 가능한 Python package, tests, fixtures, scripts가 추가된다.
- [x] local JSON input/output 기반 History Manager workflow 경로가 정의된다.
- [x] OpenAI provider adapter와 fake provider test 구조가 정의된다.
- [x] Query Routing Agent가 소비할 수 있는 output schema가 정의된다.
- [x] Backend, Frontend, RAG Pipeline, Infra, 다른 Agent에는 영향이 없어야 한다.
- [x] Public API, DB Schema, 인증/인가 흐름은 변경하지 않는다.
- [x] Data Sync Agent 및 Data Ingestion Agent 구현은 수정하지 않는다.

## 9. 문서 수정 필요 여부

- [x] 이번 세션: `docs/ai/current-plan.md`를 History Manager Agent 전용 계획으로 교체
- [x] 후속 feature 구현 중 설계 결정 또는 실행 결과는 `docs/ai/working-log.md`에 기록
- [x] API endpoint를 추가하지 않으므로 `docs/api-spec.md` 수정 불필요
- [x] DB 저장을 구현하지 않으므로 `docs/db-schema.md` 수정 불필요
- [x] 아키텍처 변경이 아니므로 `docs/architecture.md` 수정 불필요

## 10. 완료 기준

### 이번 계획 세션 완료 기준

- [x] 기존 Data Sync Agent 계획 완료 여부와 working-log 완료 기록을 확인했다.
- [x] 필수 문서 9개를 읽고 History Manager Agent 요구사항을 요약했다.
- [x] `Feature Breakdown` 기준 feature 목록을 정리했다.
- [x] feature별 테스트 케이스를 먼저 정의했다.
- [x] 구현 순서를 정했다.
- [x] 수정할 파일/디렉토리와 수정하지 않을 영역을 구분했다.
- [x] OpenAI API key 주입 방식과 fake provider 기본 테스트 원칙을 명시했다.
- [x] 완료 기준과 검증 명령을 정리했다.
- [x] 계획을 `docs/ai/current-plan.md`에 체크리스트 형태로 저장했다.
- [x] 구현 코드는 작성하지 않았다.

### 전체 MVP 완료 기준

- [x] BFF conversation history JSON input schema가 fixture 기반 테스트로 검증된다.
- [x] history normalization, role validation, sorting, warning 처리가 테스트로 검증된다.
- [x] 최근 N개 turn 및 `max_context_chars` trimming이 테스트로 검증된다.
- [x] fake LLM provider 기반 `follow_up`, `new_topic`, `ambiguous` classification이 검증된다.
- [x] OpenAI provider가 provider interface 뒤에 분리되고 API key 외부 주입 원칙을 지킨다.
- [x] context policy가 decision별 `preserved_context`, `reset_required`, warnings를 생성한다.
- [x] contextualized question과 Query Routing input이 canonical schema를 따른다.
- [x] LangGraph workflow 및 CLI가 fixture/mock 기반 integration test로 검증된다.
- [x] local output 파일 검증과 API key/token safety 테스트가 통과한다.
- [x] MVP 제외 기능은 실제 동작 없이 `not_supported_in_mvp`, `interface_only`, `planned` 중 하나로 명시된다.
- [x] 기본 테스트 suite는 fake provider만 사용하고 외부 네트워크를 호출하지 않는다.
- [x] `./scripts/format.sh`, `./scripts/lint.sh`, `./scripts/test.sh`, `./scripts/verify.sh` 결과를 기록한다.
- [x] `git diff` 기준으로 요청 범위 외 변경이 없다. 남은 변경은 History Manager Agent MVP 산출물, 본 계획/작업 로그, 허용된 `.DS_Store` 정리뿐이다.

## 11. 검증 명령

후속 feature 구현 완료 전 가능한 범위에서 아래 명령을 실행한다.

```bash
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

History Manager package가 구성되면 agent 디렉토리에서 다음 명령을 별도로 실행한다.

```bash
python3.11 -m pytest
python3.11 -m compileall src scripts
```

feature별 구현 세션에서는 해당 feature test를 먼저 실행하고, milestone 완료 시 agent 전체 pytest와 root 검증 명령을 실행한다. 루트 script가 agent 하위 pytest를 자동 발견하지 못하면 agent 디렉토리 pytest 결과를 별도로 보고한다.
