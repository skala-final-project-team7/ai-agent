# Query Routing Agent MVP 개발 계획

## 0. 기존 계획 교체 확인

- [x] 기존 `docs/ai/current-plan.md`가 History Manager Agent 계획임을 확인했다.
- [x] `docs/ai/working-log.md`에 History Manager Agent feature1-7 완료 및 MVP 마감 기록이 있음을 확인했다.
- [x] 이번 작업을 위해 `docs/ai/current-plan.md`를 Query Routing Agent 전용 계획으로 교체한다.
- [x] History Manager Agent 계획과 Query Routing Agent 계획을 한 파일에 섞지 않는다.
- [x] 이번 세션에서는 구현 코드를 작성하지 않는다.

## 1. 작업 범위 확인

- [x] 프로젝트 root: `/Users/younghoonlee/workspace_prj/ai-agent-templates`
- [x] 담당 영역: `ai-agent/query-routing-agent`
- [x] 목표: Query Routing Agent MVP 개발 계획 수립 및 본 파일 저장
- [x] API/DB 계약 변경 없음
- [x] Secret, token, API key, `.env` 생성 또는 하드코딩 금지
- [x] `OPENAI_API_KEY`는 외부 주입 방식으로만 사용한다.
- [x] 실제 Qdrant 검색, embedding 생성, Cross-Encoder reranking, ACL enforcement는 구현하지 않고 search request payload 생성까지만 수행한다.

## 2. 확인한 문서

- [x] `AGENTS.md`
- [x] `docs/architecture.md`
- [x] `docs/conventions.md`
- [x] `docs/ai/workflow.md`
- [x] `docs/ai/prompt-templates.md`
- [x] `ai-agent/AGENTS.md`
- [x] `ai-agent/query-routing-agent/query-routing-agent.md`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

## 3. 요구사항 요약

- [x] Query Routing Agent는 History Manager Agent 다음 단계에서 RAG 검색/Answer Generation용 routing decision을 생성한다.
- [x] 입력은 History Manager Agent output JSON이며 `query`, `history_decision`, `preserved_context`, `reset_required`, `metadata`를 검증한다.
- [x] intent는 `incident_response`, `operations_guide`, `policy_procedure`, `history_lookup`, `unknown`을 지원한다.
- [x] LLM output drift 또는 invalid intent는 실패가 아니라 `unknown` safe fallback으로 처리한다.
- [x] 검색용 expanded query는 기본 3개, 최대 5개로 제한하고 중복/빈 query를 제거한다.
- [x] metadata filter는 canonical schema로 생성하고 실제 Qdrant filter 문법에 고정하지 않는다.
- [x] ACL 관련 `user_id`, `groups`는 filter payload로 전달하지만 권한 판정/enforcement는 수행하지 않는다.
- [x] intent별 Multi-Pool weight를 생성하고 합계가 1.0이 되도록 normalize한다.
- [x] Answer Generation Agent가 사용할 `task_prompt_type`을 intent mapping으로 생성한다.
- [x] routing decision과 RAG search request payload를 local JSON output으로 생성한다.
- [x] `OPENAI_API_KEY`는 config에서 외부 주입 가능한 값으로만 정의한다.
- [x] 기본 테스트 suite는 fake LLM provider만 사용하고 실제 OpenAI live 호출은 포함하지 않는다.
- [x] LangGraph node는 orchestration에 집중하고 입력 정규화, 분류, query rewrite, filter/weight, decision 생성은 테스트 가능한 service/helper로 분리한다.
- [x] 실제 Qdrant 검색, Dense/Sparse embedding 생성, Cross-Encoder reranking, ACL enforcement, Answer Generation/Verification Agent, BFF/DB 직접 연동, SSE streaming은 MVP에서 제외한다.
- [x] MVP 제외 기능은 `planned`, `interface_only`, `not_supported_in_mvp` 상태로만 남긴다.

## 4. 수정 대상 파일/디렉토리

### 이번 계획 세션

- [x] `docs/ai/current-plan.md`

### MVP 구현 중 생성/수정된 영역

- [x] `ai-agent/query-routing-agent/pyproject.toml`
- [x] `ai-agent/query-routing-agent/.env.example`
- [x] `ai-agent/query-routing-agent/src/query_routing_agent/**`
- [x] `ai-agent/query-routing-agent/tests/**`
- [x] `ai-agent/query-routing-agent/scripts/**`
- [x] `ai-agent/query-routing-agent/data/input/**`
- [x] `ai-agent/query-routing-agent/data/output/**`
- [x] `ai-agent/query-routing-agent/data/reports/**`
- [x] `ai-agent/query-routing-agent/data/failed/**`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

### 수정하지 않았음을 확인한 영역

- [x] `ai-agent/history-manager-agent/**`
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
- [x] OpenAI provider는 `RoutingLLMProvider` interface 뒤에 둔다.
- [x] 기본 unit/integration test는 fake LLM provider를 사용한다.
- [x] OpenAI live smoke test는 MVP 기본 검증에서 수행하지 않고, 필요 시 별도 opt-in flag 또는 별도 script로 분리한다.
- [x] feature1 config/schema/CLI skeleton 출력에는 API key, Authorization header, secret-like 문자열이 포함되지 않아야 한다.

## 6. MVP 제외 범위 고정

- [x] 실제 Qdrant 검색 실행은 하지 않고 search request payload만 생성한다.
- [x] Dense/Sparse embedding 생성은 하지 않는다.
- [x] Cross-Encoder reranking 실행은 하지 않는다.
- [x] ACL 권한 판정 또는 enforcement는 하지 않고 ACL filter field 전달만 수행한다.
- [x] Answer Generation Agent와 Answer Verification Agent는 구현하지 않는다.
- [x] BFF API 직접 호출, DB 직접 조회/저장, SSE streaming은 구현하지 않는다.
- [x] production prompt tuning 자동화와 live evaluation regression은 후속 확장으로 둔다.

## 7. Feature Breakdown 및 테스트 계획

### feature1_project_skeleton_and_schema

- [x] Python package 구조 생성
- [x] `pyproject.toml` 설정
- [x] config schema 정의
- [x] routing input schema 정의
- [x] routing decision schema 정의
- [x] metadata filter schema 정의
- [x] pool weight schema 정의
- [x] search request payload schema 정의
- [x] routing report / failed item / warning schema 정의
- [x] CLI skeleton 작성
- [x] fixture/data 디렉토리 기본 구조 생성
- [x] schema/config 단위 테스트 작성

테스트 케이스:

- [x] config가 model, temperature, timeout, max_retries, default_query_count, max_query_count, top_k, rerank_top_k, default_pool_weights를 외부 입력으로 받을 수 있다.
- [x] config 또는 repr/log-safe 표현에서 `OPENAI_API_KEY`, API key, Authorization 값이 노출되지 않는다.
- [x] routing input schema가 History Manager output 호환 필드 `conversation_id`, `user_id`, `original_question`, `query`, `history_decision`, `preserved_context`, `reset_required`, `metadata`를 검증한다.
- [x] routing decision schema가 `intent`, `task_prompt_type`, `expanded_queries`, `metadata_filters`, `pool_weights`, `confidence`, `reason`, `warnings`를 포함한다.
- [x] metadata filter schema가 space_keys, labels, document_types, source_types, date_range, attachment_required, acl을 표현한다.
- [x] pool weight schema가 title/content/label weight를 표현하고 합계 검증 기반을 제공한다.
- [x] search request payload schema가 queries, filters, pool_weights, top_k_candidates, rerank_top_k, reranking_required를 포함한다.
- [x] routing report/failed item schema가 status, counts, warnings, safe error를 표현한다.
- [x] 필수 값 누락 시 명확한 validation error가 발생한다.
- [x] CLI skeleton이 실제 OpenAI 호출 없이 config/input validation 수준에서 동작 가능하다.

### feature2_routing_input_normalization

- [x] History Manager output JSON loader 구현
- [x] malformed JSON 처리
- [x] routing input validation 구현
- [x] preserved_context normalization 구현
- [x] metadata/user/groups normalization 구현
- [x] empty preserved_context 처리
- [x] unsupported history_decision warning 처리
- [x] query/original_question fallback 정책 구현
- [x] normalization result schema 또는 service result 구조 구현
- [x] normalization 테스트 작성

테스트 케이스:

- [x] valid History Manager output JSON을 routing input schema로 로드한다.
- [x] malformed JSON에서 명확한 non-retryable error가 발생한다.
- [x] `query` 누락 또는 빈 문자열에서 명확한 validation error가 발생한다.
- [x] `original_question`이 누락되면 명확한 validation error가 발생한다.
- [x] `preserved_context`가 비어 있어도 정상 처리된다.
- [x] malformed preserved_context는 warning 후 안전한 기본값으로 정규화된다.
- [x] metadata의 `groups`, `space_keys`, labels 후보가 list 형태로 정규화된다.
- [x] unsupported `history_decision`은 warning과 safe fallback으로 처리된다.
- [x] normalized result에 원본 전체 history가 복제되지 않는다.
- [x] normalized result/warning 문자열에 `OPENAI_API_KEY`, Authorization, secret-like 값이 포함되지 않는다.

### feature3_intent_classification_provider

- [x] `RoutingLLMProvider` interface 정의
- [x] `FakeRoutingLLMProvider` 구현
- [x] `OpenAIRoutingLLMProvider` 구현
- [x] provider factory 또는 config 기반 provider 생성 구조 구현
- [x] routing prompt builder 구현
- [x] intent classification output schema 구현
- [x] confidence/reason/filter hint/query rewrite parsing 구현
- [x] invalid intent -> `unknown` fallback 구현
- [x] invalid JSON/schema mismatch 처리
- [x] OpenAI timeout/5xx retryable safe error 처리
- [x] OpenAI auth/configuration error 처리
- [x] provider/classification 테스트 작성

테스트 케이스:

- [x] fake provider가 `incident_response` intent를 반환하면 classification result가 올바르게 생성된다.
- [x] fake provider가 `operations_guide`, `policy_procedure`, `history_lookup`, `unknown` intent를 각각 반환할 수 있다.
- [x] confidence가 0.0~1.0 범위를 벗어나면 명확한 validation 또는 fallback 정책이 적용된다.
- [x] invalid intent label은 `unknown` fallback과 warning으로 처리된다.
- [x] invalid JSON 또는 schema mismatch LLM 응답에서 safe error 또는 fallback이 발생한다.
- [x] routing prompt에 query와 제한된 preserved_context가 포함된다.
- [x] routing prompt에 원본 전체 history가 과도하게 포함되지 않는다.
- [x] OpenAI provider는 API key를 환경변수 또는 외부 config에서만 읽는다.
- [x] API key가 없는 경우 provider configuration error가 발생한다.
- [x] OpenAI provider request 구성에 model/temperature/timeout이 반영된다.
- [x] OpenAI auth error는 non-retryable로 분류된다.
- [x] OpenAI timeout/5xx는 retryable로 분류된다.
- [x] error/repr/log-safe 문자열에 `OPENAI_API_KEY`, Authorization, secret-like 값이 포함되지 않는다.
- [x] 기본 pytest suite가 실제 OpenAI 네트워크 호출 없이 통과한다.

### feature4_query_rewrite

- [x] expanded query parsing service 구현
- [x] 기본 3개 query 생성/선택 정책 구현
- [x] 최대 5개 제한 구현
- [x] 중복 query 제거 구현
- [x] 빈 query fallback 구현
- [x] 과도하게 긴 query 제한 또는 warning 구현
- [x] preserved_context 기반 query enrichment 구현
- [x] 한국어 질문과 기술 영어 용어 병기 허용 정책 구현
- [x] query rewrite 테스트 작성

테스트 케이스:

- [x] LLM result의 expanded_queries가 routing query list로 정규화된다.
- [x] expanded query가 없으면 원본 query가 fallback으로 포함된다.
- [x] 기본 query count가 3개가 되도록 부족분 fallback 또는 deterministic 보강이 적용된다.
- [x] max_query_count를 초과하면 5개 이하로 trim된다.
- [x] 중복 query와 빈 query가 제거된다.
- [x] 첫 번째 query는 원본 query와 의미적으로 가까운 값으로 유지된다.
- [x] preserved_context entity/summary가 follow-up query enrichment에 제한적으로 반영된다.
- [x] 과도하게 긴 query는 제한되거나 warning이 생성된다.
- [x] rewritten queries에 원본 전체 history가 복제되지 않는다.
- [x] output/warning 문자열에 `OPENAI_API_KEY`, Authorization, secret-like 값이 포함되지 않는다.

### feature5_filter_and_pool_weight_builder

- [x] metadata filter builder 구현
- [x] ACL filter 전달 구현
- [x] task prompt type mapping 구현
- [x] intent별 pool weight builder 구현
- [x] weight normalization 구현
- [x] invalid weight fallback 구현
- [x] filter hint validation 구현
- [x] filter/weight 테스트 작성

테스트 케이스:

- [x] metadata의 `space_keys`, labels, document_types, source_types가 canonical filter로 매핑된다.
- [x] `user_id`, `groups`가 ACL filter payload로 전달된다.
- [x] ACL 권한 판정/enforcement는 수행되지 않는다.
- [x] missing ACL metadata는 warning 또는 빈 ACL filter로 안전하게 처리된다.
- [x] `incident_response`, `operations_guide`, `policy_procedure`, `history_lookup`, `unknown` intent가 task prompt type으로 매핑된다.
- [x] intent별 pool weight가 생성된다.
- [x] pool weight 합이 1.0으로 normalize된다.
- [x] 음수 weight 또는 모든 weight 0은 default weight fallback으로 처리된다.
- [x] invalid metadata filter hint는 warning 후 safe filter로 처리된다.
- [x] filter/weight output에 API key, Authorization, secret-like 값이 포함되지 않는다.

### feature6_routing_decision_builder

- [x] routing decision 생성 service 구현
- [x] search request payload 생성 service 구현
- [x] warning/report helper 구현
- [x] local JSON writer 구현
- [x] failed item 또는 safe failure helper 구현
- [x] Answer Generation 입력 준비 필드 검증
- [x] MVP 제외 기능 marker 포함
- [x] routing decision/search payload 테스트 작성

테스트 케이스:

- [x] normalized input, classification, rewritten queries, filters, weights가 routing decision으로 매핑된다.
- [x] routing decision이 canonical schema 필수 필드를 모두 포함한다.
- [x] search request payload가 queries, filters, pool_weights, top_k_candidates, rerank_top_k, reranking_required를 포함한다.
- [x] search request payload는 실제 Qdrant 검색을 실행하지 않는다.
- [x] Answer Generation용 task_prompt_type이 routing decision에 포함된다.
- [x] warning/report helper가 total status, warning count, expanded query count를 계산한다.
- [x] local writer가 output/report/failed JSON 파일을 생성한다.
- [x] 저장 디렉토리가 없으면 자동 생성된다.
- [x] writer 결과에 API key, token, Authorization 값이 포함되지 않는다.
- [x] MVP 제외 기능이 `not_supported_in_mvp` 또는 동등한 상태로 명시된다.

### feature7_langgraph_workflow_and_cli

- [x] Query Routing workflow state 정의
- [x] workflow result schema 또는 result object 정의
- [x] LangGraph workflow builder 또는 동등한 orchestration 구조 구현
- [x] LangGraph optional wrapper와 sequential fallback 구조 구현
- [x] `load_config -> load_input -> normalize_routing_input -> classify_intent_and_rewrite -> build_metadata_filters -> build_pool_weights -> build_task_prompt_type -> build_routing_decision -> build_search_request -> write_output -> write_report` node 흐름 구현
- [x] fake provider/injected provider로 workflow 실행 가능하게 구성
- [x] success/partial success/failed 상태 처리
- [x] CLI `scripts/run_query_router.py`를 실제 workflow 실행 진입점으로 확장
- [x] CLI 인자 처리: `--input`, `--output`, `--report-output`, `--provider`, `--model`, `--default-query-count`, `--max-query-count`
- [x] CLI 실행 결과 summary 출력
- [x] workflow/CLI integration test 작성

테스트 케이스:

- [x] fake provider를 사용해 workflow가 input normalization -> classification/rewrite -> filter/weight -> routing decision -> search request 순서로 실행된다.
- [x] workflow가 routing decision JSON과 report JSON을 생성한다.
- [x] incident/operations/policy/history/unknown fixture가 각각 기대 intent와 task_prompt_type을 생성한다.
- [x] provider failure에서 failed output/report가 생성되고 secret이 노출되지 않는다.
- [x] malformed input JSON에서 failed output 또는 safe error가 생성된다.
- [x] CLI가 `--input`, `--output`, `--report-output` 인자를 받아 workflow를 실행한다.
- [x] CLI 또는 workflow output에 `OPENAI_API_KEY`, Authorization, API key, secret-like 값이 포함되지 않는다.
- [x] LangGraph가 설치되어 있지 않거나 optional dependency인 경우에도 sequential fallback으로 실행된다.
- [x] workflow 결과가 feature8 fixture/safety test에서 검증 가능한 안정적 반환값을 제공한다.

### feature8_fixture_and_safety_tests

- [x] synthetic incident response fixture 작성
- [x] synthetic operations guide fixture 작성
- [x] synthetic policy/procedure fixture 작성
- [x] synthetic history lookup fixture 작성
- [x] unknown intent fixture 작성
- [x] malformed input fixture 작성
- [x] provider failure fixture 또는 fake provider scenario 작성
- [x] output file shape 검증
- [x] routing decision schema 검증
- [x] search request payload schema 검증
- [x] report/failed output shape 검증
- [x] token/API key/Authorization 비노출 검증
- [x] MVP 제외 기능 boundary test 작성

테스트 케이스:

- [x] incident response fixture 기반 full workflow가 `intent=incident_response`, `task_prompt_type=timeline`, expanded queries, search request를 생성한다.
- [x] operations guide fixture가 `operations_guide`, `step_by_step` mapping을 생성한다.
- [x] policy/procedure fixture가 `policy_procedure`, `evidence_first` mapping을 생성한다.
- [x] history lookup fixture가 `history_lookup`, `history_summary` mapping을 생성한다.
- [x] unknown intent fixture가 failure 없이 `unknown`, `general` safe fallback으로 처리된다.
- [x] malformed input fixture에서 failed output/report가 생성된다.
- [x] provider failure fixture에서 safe failed output/report가 생성되고 secret이 노출되지 않는다.
- [x] output JSON이 canonical routing decision schema의 필수 필드를 모두 포함한다.
- [x] search request payload는 queries, filters, pool_weights를 포함하되 실제 검색 실행 정보나 embedding 결과를 포함하지 않는다.
- [x] metadata/ACL filter는 전달되지만 ACL enforcement 결과를 포함하지 않는다.
- [x] CLI stdout/stderr와 output/report/failed files에 `OPENAI_API_KEY`, Authorization, API key, secret-like 문자열이 포함되지 않는다.
- [x] 실제 OpenAI live API 호출 없이 전체 suite가 통과한다.
- [x] Qdrant/embedding/reranking/Answer Generation/Answer Verification/BFF/DB/SSE 기능이 MVP에서 실행되지 않는다.

## 8. 구현 순서

- [x] 1단계: `feature1_project_skeleton_and_schema` 테스트 작성 후 최소 구현
- [x] 2단계: `feature2_routing_input_normalization` 테스트 작성 후 최소 구현
- [x] 3단계: `feature3_intent_classification_provider` 테스트 작성 후 최소 구현
- [x] 4단계: `feature4_query_rewrite` 테스트 작성 후 최소 구현
- [x] 5단계: `feature5_filter_and_pool_weight_builder` 테스트 작성 후 최소 구현
- [x] 6단계: `feature6_routing_decision_builder` 테스트 작성 후 최소 구현
- [x] 7단계: `feature7_langgraph_workflow_and_cli` 테스트 작성 후 최소 구현
- [x] 8단계: `feature8_fixture_and_safety_tests` 보강 및 전체 검증

## 9. 예상 영향 범위

- [x] `ai-agent/query-routing-agent` 내부에 독립 실행 가능한 Python package, tests, fixtures, scripts가 추가된다.
- [x] local JSON input/output 기반 Query Routing workflow 경로가 정의된다.
- [x] OpenAI provider adapter와 fake provider test 구조가 정의된다.
- [x] RAG 검색 파이프라인이 소비할 수 있는 canonical search request payload가 정의된다.
- [x] Answer Generation Agent가 소비할 수 있는 task prompt type과 routing decision field가 정의된다.
- [x] Backend, Frontend, RAG Pipeline, Infra, 다른 Agent에는 영향이 없어야 한다.
- [x] Public API, DB Schema, 인증/인가 흐름은 변경하지 않는다.
- [x] History Manager Agent 구현은 수정하지 않고 output contract만 입력 fixture로 참조한다.

## 10. 문서 수정 필요 여부

- [x] 이번 세션: `docs/ai/current-plan.md`를 Query Routing Agent 전용 계획으로 교체
- [x] 후속 feature 구현 중 설계 결정 또는 실행 결과는 `docs/ai/working-log.md`에 기록
- [x] API endpoint를 추가하지 않으므로 `docs/api-spec.md` 수정 불필요
- [x] DB 저장을 구현하지 않으므로 `docs/db-schema.md` 수정 불필요
- [x] 아키텍처 변경이 아니므로 `docs/architecture.md` 수정 불필요

## 11. 완료 기준

### 이번 계획 세션 완료 기준

- [x] 기존 History Manager Agent 계획 완료 여부와 working-log 완료 기록을 확인했다.
- [x] 필수 문서 9개를 읽고 Query Routing Agent 요구사항을 요약했다.
- [x] `Feature Breakdown` 기준 feature1-8 목록을 정리했다.
- [x] feature별 테스트 케이스를 먼저 정의했다.
- [x] 구현 순서를 정했다.
- [x] 수정할 파일/디렉토리와 수정하지 않을 영역을 구분했다.
- [x] OpenAI API key 주입 방식과 fake provider 기본 테스트 원칙을 명시했다.
- [x] 실제 Qdrant 검색, embedding, Cross-Encoder reranking, ACL enforcement는 MVP에서 제외하고 search request payload까지만 생성한다는 점을 명시했다.
- [x] 완료 기준과 검증 명령을 정리했다.
- [x] 계획을 `docs/ai/current-plan.md`에 체크리스트 형태로 저장했다.
- [x] 구현 코드는 작성하지 않았다.

### 전체 MVP 완료 기준

- [x] History Manager Agent output JSON input schema가 fixture 기반 테스트로 검증된다.
- [x] routing input normalization과 malformed input warning/error 처리가 테스트로 검증된다.
- [x] fake LLM provider 기반 intent classification이 검증된다.
- [x] OpenAI provider가 provider interface 뒤에 분리되고 API key 외부 주입 원칙을 지킨다.
- [x] expanded query가 기본 3개, 최대 5개 정책을 따른다.
- [x] metadata filter와 ACL 전달 payload가 canonical schema를 따른다.
- [x] Multi-Pool weight가 생성되고 합계가 1.0으로 normalize된다.
- [x] task prompt type과 routing decision이 Answer Generation 입력 계약을 고려해 생성된다.
- [x] search request payload가 생성되며 실제 Qdrant 검색/embedding/reranking은 수행하지 않는다.
- [x] LangGraph workflow 및 CLI가 fixture/mock 기반 integration test로 검증된다.
- [x] local output 파일 검증과 API key/token safety 테스트가 통과한다.
- [x] MVP 제외 기능은 실제 동작 없이 `not_supported_in_mvp`, `interface_only`, `planned` 중 하나로 명시된다.
- [x] 기본 테스트 suite는 fake provider만 사용하고 외부 네트워크를 호출하지 않는다.
- [x] `./scripts/format.sh`, `./scripts/lint.sh`, `./scripts/test.sh`, `./scripts/verify.sh` 결과를 기록한다.
- [x] `git diff` 기준으로 요청 범위 외 변경이 없다.

## 12. 검증 명령

후속 feature 구현 완료 전 가능한 범위에서 아래 명령을 실행한다.

```bash
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

Query Routing package가 구성되면 agent 디렉토리에서 다음 명령을 별도로 실행한다.

```bash
python3.11 -m pytest
python3.11 -m compileall src scripts
```

feature별 구현 세션에서는 해당 feature test를 먼저 실행하고, milestone 완료 시 agent 전체 pytest와 root 검증 명령을 실행한다. 루트 script가 agent 하위 pytest를 자동 발견하지 못하면 agent 디렉토리 pytest 결과를 별도로 보고한다.
