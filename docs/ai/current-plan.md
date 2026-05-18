# Answer Generation Agent MVP 개발 계획

## 0. 기존 계획 교체 확인

- [x] 기존 `docs/ai/current-plan.md`가 Query Routing Agent 계획임을 확인했다.
- [x] `docs/ai/working-log.md`에 Query Routing Agent feature1-8 완료 및 MVP 마감 기록이 있음을 확인했다.
- [x] 이번 작업을 위해 `docs/ai/current-plan.md`를 Answer Generation Agent 전용 계획으로 교체한다.
- [x] Query Routing Agent 계획과 Answer Generation Agent 계획을 한 파일에 섞지 않는다.
- [x] 이번 세션에서는 구현 코드를 작성하지 않는다.

## 1. 작업 범위 확인

- [x] 프로젝트 root: `/Users/younghoonlee/workspace_prj/ai-agent-templates`
- [x] 담당 영역: `ai-agent/answer-generation-agent`
- [x] 목표: Answer Generation Agent MVP 개발 계획 수립 및 본 파일 저장
- [x] API/DB 계약 변경 없음
- [x] Secret, token, API key, `.env` 생성 또는 하드코딩 금지
- [x] `OPENAI_API_KEY`는 외부 주입 방식으로만 사용한다.
- [x] 실제 Qdrant 검색, embedding 생성, Cross-Encoder reranking, Answer Verification 호출, 실제 SSE streaming은 구현하지 않고 input/output schema 또는 interface까지만 다룬다.

## 2. 확인한 문서

- [x] `AGENTS.md`
- [x] `docs/architecture.md`
- [x] `docs/conventions.md`
- [x] `docs/ai/workflow.md`
- [x] `docs/ai/prompt-templates.md`
- [x] `ai-agent/AGENTS.md`
- [x] `ai-agent/answer-generation-agent/answer-generation-agent.md`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

## 3. 요구사항 요약

- [x] Answer Generation Agent는 Query Routing Agent 다음 단계에서 routing decision과 RAG Pipeline이 선별한 Top-5 context를 입력으로 받는다.
- [x] `routing_decision`과 `top_contexts`를 검증, 정규화하고 context 5개 제한을 적용한다.
- [x] task prompt type은 `timeline`, `step_by_step`, `evidence_first`, `history_summary`, `general`을 지원한다.
- [x] task prompt type별 prompt template을 조립하고 context-only answer rule과 citation instruction을 포함한다.
- [x] 실제 OpenAI provider는 provider interface 뒤에 구현하되, 기본 테스트 suite는 fake LLM provider만 사용한다.
- [x] context가 부족할 때 무조건 "모른다"고 답하지 않는다.
- [x] 입력 context가 존재하면 근거 있는 범위에서 최대한 답변하되, context 밖의 사실/절차/수치/정책은 단정하지 않는다.
- [x] context가 비어 있거나 사용할 수 없으면 `answer_status=insufficient_context`로 처리한다.
- [x] 문장별 citation은 Top context의 `context_id`만 참조해야 한다.
- [x] Answer Verification Agent가 바로 소비할 수 있는 sentence-level citation 기반 output schema를 생성한다.
- [x] source list는 context/source metadata를 보존한다.
- [x] 실제 SSE streaming은 수행하지 않고 stream chunk schema/interface만 준비한다.
- [x] 실제 Qdrant 검색, Dense/Sparse embedding, Cross-Encoder reranking, Answer Verification 직접 호출, BFF/DB/QCA/feedback/UI formatting은 MVP에서 제외한다.
- [x] MVP 제외 기능은 `planned`, `interface_only`, `not_supported_in_mvp` 상태로만 남긴다.

## 4. 수정 대상 파일/디렉토리

### 이번 계획 세션

- [x] `docs/ai/current-plan.md`

### MVP 구현 중 생성/수정된 영역

- [x] `ai-agent/answer-generation-agent/pyproject.toml`
- [x] `ai-agent/answer-generation-agent/.env.example`
- [x] `ai-agent/answer-generation-agent/src/answer_generation_agent/**`
- [x] `ai-agent/answer-generation-agent/tests/**`
- [x] `ai-agent/answer-generation-agent/scripts/**`
- [x] `ai-agent/answer-generation-agent/data/input/**`
- [x] `ai-agent/answer-generation-agent/data/output/**`
- [x] `ai-agent/answer-generation-agent/data/reports/**`
- [x] `ai-agent/answer-generation-agent/data/failed/**`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

### 수정하지 않았음을 확인한 영역

- [x] `ai-agent/query-routing-agent/**`
- [x] `ai-agent/history-manager-agent/**`
- [x] `ai-agent/data-sync-agent/**`
- [x] `ai-agent/data-ingestion-agent/**`
- [x] `ai-agent/answer-verification-agent/**`
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
- [x] OpenAI provider는 `AnswerLLMProvider` interface 뒤에 둔다.
- [x] 기본 unit/integration test는 fake LLM provider를 사용한다.
- [x] OpenAI live smoke test는 MVP 기본 검증에서 수행하지 않고, 필요 시 별도 opt-in flag 또는 별도 script로 분리한다.
- [x] provider error, prompt, request, response, log-safe 출력에는 API key, Authorization header, secret-like 문자열이 포함되지 않아야 한다.

## 6. MVP 제외 범위 고정

- [x] 실제 Qdrant 검색 실행은 하지 않고 RAG Pipeline이 이미 선별한 Top-5 context JSON만 입력으로 받는다.
- [x] Dense/Sparse embedding 생성은 하지 않는다.
- [x] Cross-Encoder reranking 실행은 하지 않는다.
- [x] Query Routing Agent는 호출하지 않고 routing decision JSON contract만 입력으로 검증한다.
- [x] Answer Verification Agent는 직접 호출하지 않고 소비 가능한 output schema까지만 생성한다.
- [x] 실제 SSE streaming 전송은 하지 않고 stream chunk schema/interface만 준비한다.
- [x] BFF API 직접 호출, DB 직접 조회/저장, QCA 저장, feedback 저장, UI response formatting은 구현하지 않는다.
- [x] production prompt tuning 자동화와 live evaluation regression은 후속 확장으로 둔다.

## 7. Feature Breakdown 및 테스트 계획

### feature1_project_skeleton_and_schema

- [x] Python package 구조 생성
- [x] `pyproject.toml` 설정
- [x] config schema 정의
- [x] generation input schema 정의
- [x] routing decision input 호환 schema 정의
- [x] top context schema 정의
- [x] generated sentence schema 정의
- [x] generated source schema 정의
- [x] answer output schema 정의
- [x] stream chunk schema 정의
- [x] generation report / failed item / warning schema 정의
- [x] CLI skeleton 작성
- [x] fixture/data 디렉토리 기본 구조 생성
- [x] schema/config 단위 테스트 작성

테스트 케이스:

- [x] config가 model, fallback_model, temperature, timeout_seconds, max_retries, max_contexts, max_answer_sentences, streaming_supported 값을 외부 입력으로 받을 수 있다.
- [x] config 또는 repr/log-safe 표현에서 `OPENAI_API_KEY`, API key, Authorization 값이 노출되지 않는다.
- [x] generation input schema가 `conversation_id`, `user_id`, `routing_decision`, `search_results.top_contexts`, `metadata`를 포함한다.
- [x] routing decision 호환 schema가 `routing_id`, `query`, `intent`, `task_prompt_type`, `expanded_queries`, `confidence`, `warnings`를 표현한다.
- [x] top context schema가 `context_id`, `document_id`, `chunk_id`, `title`, `space_key`, `source_url`, `content`, `score`, `rerank_score`, `metadata`를 표현한다.
- [x] generated sentence schema가 `sentence_id`, `text`, `citations`, `citation_required`를 포함한다.
- [x] generated source schema가 context/source metadata를 보존한다.
- [x] answer output schema가 `answer_status`, `answer`, `sentences`, `sources`, `used_context_ids`, `routing`, `model`, `confidence`, `insufficient_context`, `unsupported_gaps`, `streaming`, `warnings`를 포함한다.
- [x] stream chunk schema가 `generation_id`, `chunk_index`, `chunk_type`, `content`, `metadata`를 포함하고 실제 SSE 전송 정보는 포함하지 않는다.
- [x] 필수 값 누락 시 명확한 validation error가 발생한다.
- [x] CLI skeleton이 실제 OpenAI 호출 없이 config/input validation 수준에서 동작 가능하다.

### feature2_generation_input_normalization

- [x] Query Routing output + Top-5 context JSON loader 구현
- [x] malformed JSON 처리
- [x] generation input validation 구현
- [x] routing decision normalization 구현
- [x] top context normalization 구현
- [x] context 5개 제한 구현
- [x] `rerank_score` 또는 입력 순서 기반 top context 선택 정책 구현
- [x] empty/invalid context warning 처리
- [x] unsupported task prompt type -> `general` fallback 구현
- [x] context sufficiency 판단에 필요한 normalized result 구조 구현
- [x] normalization 테스트 작성

테스트 케이스:

- [x] valid generation input JSON을 내부 schema로 로드한다.
- [x] malformed JSON에서 명확한 non-retryable error가 발생한다.
- [x] `routing_decision` 누락 시 명확한 validation error가 발생한다.
- [x] `query` 또는 `task_prompt_type` 누락 시 명확한 validation error가 발생한다.
- [x] top_contexts가 5개를 초과하면 상위 5개만 사용한다.
- [x] `rerank_score`가 있으면 점수 기준으로 우선 정렬하거나 명확한 정책을 적용한다.
- [x] content가 빈 context는 warning 후 제외된다.
- [x] top_contexts가 비어 있으면 `insufficient_context` 판단이 가능하도록 빈 normalized context로 유지된다.
- [x] unsupported task_prompt_type은 `general` fallback과 warning으로 처리된다.
- [x] normalized result에 실제 검색/reranking/embedding 결과나 원본 전체 history가 과도하게 복제되지 않는다.
- [x] warning/error/result 문자열에 `OPENAI_API_KEY`, Authorization, secret-like 값이 포함되지 않는다.

### feature3_prompt_template_builder

- [x] prompt builder service 추가
- [x] `timeline` prompt 구현
- [x] `step_by_step` prompt 구현
- [x] `evidence_first` prompt 구현
- [x] `history_summary` prompt 구현
- [x] `general` prompt 구현
- [x] context-only answer rule 포함
- [x] context가 존재하면 근거 있는 범위에서 최대한 답변하되, context 밖 사실은 단정하지 않는 rule 포함
- [x] sentence-level citation instruction 포함
- [x] Top context formatting 구현
- [x] prompt length guard 또는 max_contexts 기반 제한 구현
- [x] prompt builder 테스트 작성

테스트 케이스:

- [x] `timeline` prompt가 상황 요약, 시간/단계 흐름, 조치 순서, 근거 요구를 포함한다.
- [x] `step_by_step` prompt가 단계별 절차, 주의사항, 확인 방법 요구를 포함한다.
- [x] `evidence_first` prompt가 근거 문서/조항 우선, 결론, 예외/주의사항 요구를 포함한다.
- [x] `history_summary` prompt가 변경/처리 이력, 날짜/대상/결과 요구를 포함한다.
- [x] `general` prompt가 간결한 직접 답변과 근거 출처 요구를 포함한다.
- [x] 모든 prompt에 context 밖 사실 단정 금지 rule이 포함된다.
- [x] 모든 prompt에 sentence-level citation JSON 또는 구조화 citation instruction이 포함된다.
- [x] prompt에 context_id와 source metadata가 포함된다.
- [x] prompt에 실제 API key, Authorization, secret-like 값이 포함되지 않는다.
- [x] prompt에 Top-5를 초과하는 context가 포함되지 않는다.

### feature4_llm_provider_and_answer_generation

- [x] `AnswerLLMProvider` interface 정의
- [x] `FakeAnswerLLMProvider` 구현
- [x] `OpenAIAnswerLLMProvider` 구현
- [x] provider factory 또는 config 기반 provider 생성 구조 구현
- [x] answer generation request/result schema 구현
- [x] answer generation service 구현
- [x] context sufficiency handling 구현
- [x] model policy interface 또는 simple model selection 구조 구현
- [x] OpenAI timeout/5xx retryable safe error 처리
- [x] OpenAI auth/configuration error 처리
- [x] invalid LLM response safe error 또는 fallback 처리
- [x] provider/generation 테스트 작성

테스트 케이스:

- [x] fake provider가 citation-aware answer를 반환하면 generation result가 올바르게 생성된다.
- [x] fake provider 기반 테스트는 실제 OpenAI 네트워크 호출 없이 통과한다.
- [x] context가 비어 있으면 LLM 호출 없이 `insufficient_context`로 처리된다.
- [x] context가 일부만 관련 있으면 근거 있는 범위에서 답변하고 warning/unsupported_gaps를 남긴다.
- [x] context 밖 사실을 단정하는 provider output은 후속 citation/output 단계에서 warning 대상으로 남길 수 있다.
- [x] OpenAI provider는 API key를 환경변수 또는 외부 config에서만 읽는다.
- [x] API key가 없는 경우 provider configuration error가 발생한다.
- [x] OpenAI provider request 구성에 model/temperature/timeout이 반영된다.
- [x] OpenAI auth error는 non-retryable로 분류된다.
- [x] OpenAI timeout/5xx는 retryable로 분류된다.
- [x] error/repr/log-safe 문자열에 `OPENAI_API_KEY`, Authorization, secret-like 값이 포함되지 않는다.

### feature5_citation_mapping

- [x] LLM answer sentence parsing 구현
- [x] sentence id 생성 또는 정규화 구현
- [x] citation extraction 구현
- [x] context id validation 구현
- [x] source list builder 구현
- [x] missing citation warning 구현
- [x] invalid context id citation warning 및 제거 구현
- [x] citation mapping fallback 구현
- [x] citation 테스트 작성

테스트 케이스:

- [x] LLM output 문장이 `GeneratedSentence` 목록으로 파싱된다.
- [x] 문장별 citation이 Top context의 `context_id`만 참조한다.
- [x] 존재하지 않는 context id citation은 warning 후 제거된다.
- [x] citation이 없는 핵심 문장은 warning 대상으로 남는다.
- [x] source list가 context_id/document_id/chunk_id/title/source_url/space_key/page_id/score/rerank_score를 보존한다.
- [x] 같은 context가 여러 문장에서 참조되어도 source list는 중복 없이 생성된다.
- [x] answer text와 sentence list가 일관되게 유지된다.
- [x] citation mapping 결과에 API key, Authorization, secret-like 값이 포함되지 않는다.

### feature6_answer_output_builder

- [x] Answer Verification Agent 입력 호환 output builder 구현
- [x] answer status 결정 구현
- [x] confidence/warnings/unsupported_gaps 병합 구현
- [x] used_context_ids 계산 구현
- [x] streaming chunk schema/interface 생성
- [x] generation report helper 구현
- [x] failed item 또는 safe failure helper 구현
- [x] local JSON writer 구현
- [x] output path 생성 규칙 구현
- [x] output builder 테스트 작성

테스트 케이스:

- [x] Answer output이 canonical schema 필수 필드를 모두 포함한다.
- [x] success output이 answer, sentences, sources, used_context_ids, routing metadata를 포함한다.
- [x] insufficient context output이 `answer_status=insufficient_context`, `insufficient_context=true`, warnings를 포함한다.
- [x] failed output 또는 failed item이 safe reason, retryable 여부, error_type을 포함한다.
- [x] used_context_ids는 sentence citations에서 계산된다.
- [x] stream chunk schema는 생성되지만 실제 SSE 전송은 수행하지 않는다.
- [x] generation report가 status, answer_status, context_count, used_context_count, sentence_count, citation_count, warnings_count를 계산한다.
- [x] local writer가 output/report/failed JSON 파일을 생성한다.
- [x] 저장 디렉토리가 없으면 자동 생성된다.
- [x] output/report/failed files에 API key, token, Authorization 값이 포함되지 않는다.

### feature7_langgraph_workflow_and_cli

- [x] Answer Generation workflow state 정의
- [x] workflow result schema 또는 result object 정의
- [x] LangGraph workflow builder 또는 동등한 orchestration 구조 구현
- [x] LangGraph optional wrapper와 sequential fallback 구조 구현
- [x] `load_config -> load_input -> normalize_generation_input -> validate_top_contexts -> assess_context_sufficiency -> build_task_prompt -> generate_answer -> map_sentence_citations -> build_answer_output -> write_output -> write_report` node 흐름 구현
- [x] fake provider/injected provider로 workflow 실행 가능하게 구성
- [x] success/insufficient_context/failed 상태 처리
- [x] CLI `scripts/run_answer_generation.py`를 실제 workflow 실행 진입점으로 확장
- [x] CLI 인자 처리: `--input`, `--output`, `--report-output`, `--failed-output`, `--provider`, `--model`, `--max-contexts`, `--max-answer-sentences`
- [x] CLI 실행 결과 summary 출력
- [x] workflow/CLI integration test 작성

테스트 케이스:

- [x] fake provider를 사용해 workflow가 input normalization -> prompt build -> answer generation -> citation mapping -> output/report 저장 순서로 실행된다.
- [x] workflow가 Answer Verification 호환 answer output JSON과 report JSON을 생성한다.
- [x] timeline fixture에서 sentence-level citation answer가 생성된다.
- [x] step_by_step/evidence_first/history_summary/general fixture가 각각 기대 prompt/output shape를 생성한다.
- [x] insufficient context fixture에서 LLM 호출 없이 insufficient output/report가 생성된다.
- [x] provider failure에서 failed output/report가 생성되고 secret이 노출되지 않는다.
- [x] CLI가 `--input`, `--output`, `--report-output` 인자를 받아 workflow를 실행한다.
- [x] CLI 또는 workflow output에 `OPENAI_API_KEY`, Authorization, API key, secret-like 값이 포함되지 않는다.
- [x] LangGraph가 설치되어 있지 않거나 optional dependency인 경우에도 sequential fallback으로 실행된다.
- [x] 실제 SSE streaming, Answer Verification 호출, Qdrant/embedding/reranking이 실행되지 않는다.

### feature8_fixture_and_safety_tests

- [x] synthetic timeline fixture 작성
- [x] synthetic step-by-step fixture 작성
- [x] synthetic evidence-first fixture 작성
- [x] synthetic history-summary fixture 작성
- [x] synthetic general fixture 작성
- [x] insufficient context fixture 작성
- [x] malformed input fixture 작성
- [x] provider failure fixture 또는 fake provider scenario 작성
- [x] output file shape 검증
- [x] Answer Verification input 호환 schema 검증
- [x] sentence-level citation 검증
- [x] source list 검증
- [x] report/failed output shape 검증
- [x] token/API key/Authorization 비노출 검증
- [x] MVP 제외 기능 boundary test 작성

테스트 케이스:

- [x] timeline fixture 기반 full workflow가 `task_prompt_type=timeline`, citation-aware answer, source list를 생성한다.
- [x] step-by-step fixture가 단계형 답변과 sentence-level citation을 생성한다.
- [x] evidence-first fixture가 근거 우선 답변과 citation을 생성한다.
- [x] history-summary fixture가 날짜/대상/결과 중심 답변과 citation을 생성한다.
- [x] general fixture가 간결한 직접 답변과 citation을 생성한다.
- [x] insufficient context fixture가 `answer_status=insufficient_context`를 생성하고 context 밖 사실을 단정하지 않는다.
- [x] malformed input fixture에서 failed output/report가 생성된다.
- [x] provider failure fixture에서 safe failed output/report가 생성되고 secret이 노출되지 않는다.
- [x] output JSON이 Answer Verification Agent 소비 schema의 필수 필드를 모두 포함한다.
- [x] 모든 sentence citation은 sources의 context_id를 참조한다.
- [x] output JSON/report/failed files에 `OPENAI_API_KEY`, Authorization, API key, secret-like 문자열이 포함되지 않는다.
- [x] 실제 OpenAI live API 호출 없이 전체 suite가 통과한다.
- [x] Qdrant/embedding/reranking/Answer Verification 직접 호출/SSE/BFF/DB/QCA/feedback/UI formatting 기능이 MVP에서 실행되지 않는다.

## 8. 구현 순서

- [x] 1단계: `feature1_project_skeleton_and_schema` 테스트 작성 후 최소 구현
- [x] 2단계: `feature2_generation_input_normalization` 테스트 작성 후 최소 구현
- [x] 3단계: `feature3_prompt_template_builder` 테스트 작성 후 최소 구현
- [x] 4단계: `feature4_llm_provider_and_answer_generation` 테스트 작성 후 최소 구현
- [x] 5단계: `feature5_citation_mapping` 테스트 작성 후 최소 구현
- [x] 6단계: `feature6_answer_output_builder` 테스트 작성 후 최소 구현
- [x] 7단계: `feature7_langgraph_workflow_and_cli` 테스트 작성 후 최소 구현
- [x] 8단계: `feature8_fixture_and_safety_tests` 보강 및 전체 검증

## 9. 예상 영향 범위

- [x] `ai-agent/answer-generation-agent` 내부에 독립 실행 가능한 Python package, tests, fixtures, scripts가 추가된다.
- [x] local JSON input/output 기반 Answer Generation workflow 경로가 정의된다.
- [x] OpenAI provider adapter와 fake provider test 구조가 정의된다.
- [x] Answer Verification Agent가 소비할 수 있는 sentence-level citation 기반 canonical output이 정의된다.
- [x] Backend, Frontend, RAG Pipeline, Infra, 다른 Agent에는 영향이 없어야 한다.
- [x] Public API, DB Schema, 인증/인가 흐름은 변경하지 않는다.
- [x] Query Routing Agent 구현은 수정하지 않고 output contract만 입력 fixture로 참조한다.

## 10. 문서 수정 필요 여부

- [x] 이번 세션: `docs/ai/current-plan.md`를 Answer Generation Agent 전용 계획으로 교체
- [x] 후속 feature 구현 중 설계 결정 또는 실행 결과는 `docs/ai/working-log.md`에 기록
- [x] API endpoint를 추가하지 않으므로 `docs/api-spec.md` 수정 불필요
- [x] DB 저장을 구현하지 않으므로 `docs/db-schema.md` 수정 불필요
- [x] 아키텍처 변경이 아니므로 `docs/architecture.md` 수정 불필요

## 11. 완료 기준

### 이번 계획 세션 완료 기준

- [x] 기존 Query Routing Agent 계획 완료 여부와 working-log 완료 기록을 확인했다.
- [x] 필수 문서 9개를 읽고 Answer Generation Agent 요구사항을 요약했다.
- [x] `Feature Breakdown` 기준 feature1-8 목록을 정리했다.
- [x] feature별 테스트 케이스를 먼저 정의했다.
- [x] 구현 순서를 정했다.
- [x] 수정할 파일/디렉토리와 수정하지 않을 영역을 구분했다.
- [x] OpenAI API key 주입 방식과 fake provider 기본 테스트 원칙을 명시했다.
- [x] 실제 Qdrant 검색, embedding, Cross-Encoder reranking, Answer Verification 호출, 실제 SSE streaming은 MVP에서 제외하고 input/output schema 또는 interface까지만 다룬다는 점을 명시했다.
- [x] context가 부족할 때 무조건 "모른다"고 답하지 않고, 입력 context가 존재하면 근거 있는 범위에서 최대한 답변하되 context 밖의 사실은 단정하지 않는 원칙을 명시했다.
- [x] Answer Verification Agent가 소비할 수 있는 sentence-level citation 기반 output schema를 완료 기준에 포함했다.
- [x] 완료 기준과 검증 명령을 정리했다.
- [x] 계획을 `docs/ai/current-plan.md`에 체크리스트 형태로 저장했다.
- [x] 구현 코드는 작성하지 않았다.

### 전체 MVP 완료 기준

- [x] Query Routing Agent output + Top-5 context JSON input schema가 fixture 기반 테스트로 검증된다.
- [x] generation input normalization과 malformed input warning/error 처리가 테스트로 검증된다.
- [x] task prompt type별 prompt template이 테스트로 검증된다.
- [x] fake LLM provider 기반 answer generation이 검증된다.
- [x] OpenAI provider가 provider interface 뒤에 분리되고 API key 외부 주입 원칙을 지킨다.
- [x] context sufficiency handling이 `success|insufficient_context|failed` 상태로 검증된다.
- [x] 입력 context가 존재하면 근거 있는 범위에서 답변하고 context 밖 사실은 단정하지 않는 정책이 prompt/test로 검증된다.
- [x] sentence-level citation이 Top context의 context_id만 참조한다.
- [x] source list가 Answer Verification Agent 검증에 필요한 metadata를 보존한다.
- [x] Answer Verification Agent 입력 호환 output schema가 생성된다.
- [x] stream chunk schema/interface는 정의되지만 실제 SSE 전송은 수행하지 않는다.
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

Answer Generation package가 구성되면 agent 디렉토리에서 다음 명령을 별도로 실행한다.

```bash
python3.11 -m pytest
python3.11 -m compileall src scripts
```

feature별 구현 세션에서는 해당 feature test를 먼저 실행하고, milestone 완료 시 agent 전체 pytest와 root 검증 명령을 실행한다. 루트 script가 agent 하위 pytest를 자동 발견하지 못하면 agent 디렉토리 pytest 결과를 별도로 보고한다.
