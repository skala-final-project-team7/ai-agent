# Answer Verification Agent MVP Plan

## 0. 기존 계획 교체 확인

- [x] 기존 `docs/ai/current-plan.md`가 Answer Generation Agent 계획임을 확인했다.
- [x] `docs/ai/working-log.md`에 Answer Generation Agent feature1-8 완료 및 MVP 완료 기록이 있음을 확인했다.
- [x] 이번 작업을 위해 `docs/ai/current-plan.md`를 Answer Verification Agent 전용 계획으로 교체한다.
- [x] Answer Generation Agent 계획과 Answer Verification Agent 계획을 한 파일에 섞지 않는다.
- [x] 이번 세션에서는 구현 코드, 테스트 코드, 스크립트, 패키지 파일, `.env.example`을 생성하거나 수정하지 않는다.

## 1. 확인한 문서

- [x] `AGENTS.md`
- [x] `docs/ai/workflow.md`
- [x] `docs/ai/prompt-templates.md`
- [x] `docs/conventions.md`
- [x] `docs/architecture.md`
- [x] `ai-agent/AGENTS.md`
- [x] `ai-agent/answer-verification-agent/answer-verification-agent.md`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

## 2. 공통 규칙 및 전용 요구사항 요약

- [x] 프로젝트 root는 `/Users/younghoonlee/workspace_prj/ai-agent-templates`이다.
- [x] 담당 영역은 `ai-agent/answer-verification-agent`이며, 다른 Agent, backend, frontend, rag-pipeline, infra 영역은 수정하지 않는다.
- [x] 구현 전 Plan을 먼저 작성하고, 이후 feature 단위로 테스트를 먼저 작성한 뒤 최소 구현한다.
- [x] Secret, token, credential, 실제 API key, `.env` 파일은 코드, fixture, 로그, output, 문서 예시에 남기지 않는다.
- [x] `OPENAI_API_KEY`는 환경변수, 런타임 secret provider, 테스트용 injection 등 외부 주입 방식으로만 받는다.
- [x] 실제 OpenAI live test는 기본 테스트 suite에 포함하지 않고, 필요 시 별도 opt-in으로 분리한다.
- [x] 기본 테스트는 fake evaluator provider를 사용한다.
- [x] Answer Verification Agent는 Answer Generation Agent output과 Top-5 context를 입력으로 받는다.
- [x] MVP 실행 형태는 CLI 수동 실행, LangGraph workflow, local JSON input/output이다.
- [x] rule-based verification을 항상 먼저 수행한다.
- [x] MVP 기본 정책은 suspicious sentence만 LLM evaluator 대상으로 선정하는 것이며, 향후 all-sentence evaluation mode로 확장 가능해야 한다.
- [x] overall label은 `PASS`, `SUPPORTED`, `UNSUPPORTED`, `LOW_CONFIDENCE`를 사용한다.
- [x] sentence label은 `SUPPORTED`, `UNSUPPORTED`, `LOW_CONFIDENCE`, `NOT_CHECKED`를 사용한다.
- [x] QCA는 MVP에서 local JSON/JSONL 산출물로만 저장하고 DB 저장은 제외한다.
- [x] UI warning metadata는 생성하되 UI 렌더링은 구현하지 않는다.
- [x] regeneration recommendation/request payload는 생성하되 Answer Generation Agent 직접 재호출과 재생성 loop 실행은 제외한다.
- [x] 실제 BFF API, DB, SSE, feedback DB, production dashboard 연동은 MVP 제외다.

## 3. 수정 가능 파일/디렉토리

### 이번 계획 세션

- [x] `docs/ai/current-plan.md`

### 후속 구현 세션에서 수정 가능한 영역

- [x] `ai-agent/answer-verification-agent/pyproject.toml`
- [x] `ai-agent/answer-verification-agent/.env.example`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/**`
- [x] `ai-agent/answer-verification-agent/tests/**`
- [x] `ai-agent/answer-verification-agent/scripts/**`
- [x] `ai-agent/answer-verification-agent/data/input/**`
- [x] `ai-agent/answer-verification-agent/data/output/**`
- [x] `ai-agent/answer-verification-agent/data/reports/**`
- [x] `ai-agent/answer-verification-agent/data/failed/**`
- [x] `ai-agent/answer-verification-agent/data/qca/**`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

## 4. 수정하지 않을 영역

- [x] `ai-agent/answer-generation-agent/**`
- [x] `ai-agent/query-routing-agent/**`
- [x] `ai-agent/history-manager-agent/**`
- [x] `ai-agent/data-sync-agent/**`
- [x] `ai-agent/data-ingestion-agent/**`
- [x] 다른 Agent 디렉토리
- [x] `backend/**`
- [x] `frontend/**`
- [x] `rag-pipeline/**`
- [x] `infra/**`
- [x] `docs/api-spec.md`
- [x] `docs/db-schema.md`
- [x] 실제 `.env` 파일
- [x] Secret, token, credential, 실제 API key를 포함한 파일

## 5. MVP 제외 범위

- [x] Answer Generation Agent 직접 재호출은 구현하지 않는다.
- [x] 실제 재생성 loop 실행은 구현하지 않는다.
- [x] BFF API 직접 호출은 구현하지 않는다.
- [x] DB 직접 조회/저장은 구현하지 않는다.
- [x] QCA DB 저장은 구현하지 않는다.
- [x] feedback DB 저장은 구현하지 않는다.
- [x] UI 렌더링은 구현하지 않는다.
- [x] 실제 SSE streaming 전송은 구현하지 않는다.
- [x] 실제 OpenAI live test는 기본 테스트 suite에 포함하지 않는다.
- [x] production evaluation dashboard 연동은 구현하지 않는다.

## 6. Feature Breakdown 및 테스트 계획

### feature1_project_skeleton_and_schema

구현 목표:

- [x] Python package 구조를 생성한다.
- [x] `pyproject.toml` 설정을 추가한다.
- [x] config schema를 정의한다.
- [x] verification input/output schema를 정의한다.
- [x] sentence verification result schema를 정의한다.
- [x] citation coverage schema를 정의한다.
- [x] QCA output schema를 정의한다.
- [x] regeneration request schema를 정의한다.
- [x] verification report schema를 정의한다.
- [x] CLI skeleton을 작성한다.
- [x] schema/config 단위 테스트를 작성한다.

테스트 케이스 목록:

- [x] config가 evaluator model, temperature, timeout_seconds, max_retries, evaluate_suspicious_only, min_overall_score, min_sentence_score, qca_output_enabled 값을 외부 입력으로 받을 수 있다.
- [x] config 또는 repr/log-safe 표현에서 `OPENAI_API_KEY`, API key, Authorization 값이 노출되지 않는다.
- [x] verification input schema가 `conversation_id`, `user_id`, `answer_output`, `contexts`, `metadata`를 포함한다.
- [x] sentence verification result schema가 sentence_id, text, label, score, citations, matched_context_ids, failed_rules, llm_evaluation_used, reason을 표현한다.
- [x] verification output schema가 verification_id, generation_id, overall_label, overall_score, sentence_results, unsupported_claims, citation_coverage, ui_warning, qca/ref, regeneration fields를 포함한다.
- [x] citation coverage schema가 total_sentences, sentences_with_citations, valid_citations, invalid_citations, coverage_ratio를 표현한다.
- [x] QCA output schema가 qca_id, question, context_refs, answer, verification metadata, quality_label을 포함한다.
- [x] regeneration request schema가 target_generation_id, unsupported_sentence_ids, guidance를 포함한다.
- [x] 필수 값 누락 시 명확한 validation error가 발생한다.
- [x] CLI skeleton이 실제 OpenAI 호출 없이 config/input validation 수준에서 동작 가능하다.

수정 가능 파일 범위:

- [x] `ai-agent/answer-verification-agent/pyproject.toml`
- [x] `ai-agent/answer-verification-agent/.env.example`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/**`
- [x] `ai-agent/answer-verification-agent/tests/unit/test_schema_config.py`
- [x] `ai-agent/answer-verification-agent/scripts/**`
- [x] `ai-agent/answer-verification-agent/data/**`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

구현하지 말아야 할 MVP 제외 범위:

- [x] 실제 OpenAI API 호출
- [x] input normalization, parser, verifier, evaluator, workflow 실제 로직
- [x] QCA DB 저장, BFF/DB/SSE/feedback/dashboard 연동

완료 기준:

- [x] schema/config 테스트가 통과한다.
- [x] package skeleton과 CLI skeleton이 생성된다.
- [x] 실제 secret 또는 `.env` 파일이 생성되지 않는다.

### feature2_verification_input_normalization

구현 목표:

- [x] Answer Generation output + contexts JSON loader를 구현한다.
- [x] input validation을 구현한다.
- [x] answer output normalization을 구현한다.
- [x] context normalization을 구현한다.
- [x] missing contexts 처리를 구현한다.
- [x] generated sentences가 없을 때 sentence fallback 준비 상태를 남긴다.
- [x] normalization 테스트를 작성한다.

테스트 케이스 목록:

- [x] valid verification input JSON을 내부 schema로 로드한다.
- [x] malformed JSON에서 명확한 non-retryable error가 발생한다.
- [x] `answer_output` 누락 시 명확한 validation error가 발생한다.
- [x] `contexts` 누락 또는 빈 contexts를 안전하게 처리하고 low-confidence 후보 상태를 남긴다.
- [x] Answer Generation output의 `sentences`, `sources`, `used_context_ids`, `routing`, `warnings`를 정규화한다.
- [x] Top-5 contexts가 5개를 초과하면 안전하게 제한하거나 warning을 남긴다.
- [x] content가 빈 context는 warning 후 제외하거나 low-confidence 후보로 처리한다.
- [x] duplicate context_id는 deterministic하게 처리된다.
- [x] missing context_id citation을 후속 parser/rule 단계가 검출할 수 있도록 보존한다.
- [x] warning/error/result 문자열에 `OPENAI_API_KEY`, Authorization, secret-like 값이 포함되지 않는다.

수정 가능 파일 범위:

- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/verification/**`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/schemas/**`
- [x] `ai-agent/answer-verification-agent/tests/unit/test_verification_input_normalization.py`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

구현하지 말아야 할 MVP 제외 범위:

- [x] sentence parser, rule verifier, LLM evaluator, workflow full orchestration
- [x] Answer Generation Agent 직접 호출
- [x] 외부 API/DB 호출

완료 기준:

- [x] normalization unit test가 통과한다.
- [x] invalid input은 safe error로 처리된다.
- [x] normalized result가 후속 parser/rule 단계에서 재사용 가능하다.

### feature3_sentence_and_citation_parser

구현 목표:

- [x] answer sentence parsing을 구현한다.
- [x] generated sentence schema를 처리한다.
- [x] citation extraction을 구현한다.
- [x] context id validation을 구현한다.
- [x] citation coverage 계산을 구현한다.
- [x] parser 테스트를 작성한다.

테스트 케이스 목록:

- [x] Answer Generation output의 generated sentences가 있으면 이를 우선 사용한다.
- [x] generated sentences가 비어 있으면 answer text에서 문장을 fallback parsing한다.
- [x] sentence_id가 없거나 중복이면 deterministic하게 정규화한다.
- [x] citations는 context_id list로 정규화된다.
- [x] 존재하는 context_id citation은 valid citation으로 분류된다.
- [x] 존재하지 않는 context_id citation은 invalid citation으로 분류되고 warning 대상이 된다.
- [x] citation이 없는 문장은 missing citation 상태로 보존된다.
- [x] citation coverage count와 ratio가 정확히 계산된다.
- [x] 빈 answer 또는 whitespace answer는 safe low-confidence/not_checked 후보로 처리된다.
- [x] parser result에 API key, Authorization, secret-like 값이 포함되지 않는다.

수정 가능 파일 범위:

- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/verification/**`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/schemas/**`
- [x] `ai-agent/answer-verification-agent/tests/unit/test_sentence_and_citation_parser.py`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

구현하지 말아야 할 MVP 제외 범위:

- [x] rule-based verifier, suspicious selector, LLM evaluator
- [x] QCA output/result builder
- [x] 외부 API/DB 호출

완료 기준:

- [x] parser unit test가 통과한다.
- [x] sentence/citation/citation coverage 구조가 후속 rule verifier에 전달 가능하다.

### feature4_rule_based_verifier

구현 목표:

- [x] citation existence rule을 구현한다.
- [x] valid context citation rule을 구현한다.
- [x] token/entity overlap rule을 구현한다.
- [x] number/date/version presence rule을 구현한다.
- [x] source coverage rule을 구현한다.
- [x] rule result aggregation을 구현한다.
- [x] rule verifier 테스트를 작성한다.

테스트 케이스 목록:

- [x] citation이 있는 문장은 citation existence rule을 통과한다.
- [x] citation이 없는 핵심 문장은 failed rule과 suspicious 후보가 된다.
- [x] invalid context citation은 unsupported 또는 low-confidence rule result로 분류된다.
- [x] sentence 핵심 token/entity가 cited context에 충분히 있으면 overlap rule을 통과한다.
- [x] overlap이 낮으면 low-confidence 또는 suspicious로 분류된다.
- [x] 숫자, 날짜, 버전, 퍼센트, 수치 표현이 cited context에 없으면 failed rule로 기록된다.
- [x] multiple citations가 있을 때 source coverage가 계산된다.
- [x] answer_status가 insufficient_context이면 문장은 NOT_CHECKED 또는 LOW_CONFIDENCE 후보로 처리된다.
- [x] rule aggregation이 sentence별 score와 failed_rules를 deterministic하게 생성한다.
- [x] result/warning/error 문자열에 `OPENAI_API_KEY`, Authorization, secret-like 값이 포함되지 않는다.

수정 가능 파일 범위:

- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/verification/rule_based_verifier.py`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/verification/__init__.py`
- [x] `ai-agent/answer-verification-agent/tests/unit/test_rule_based_verifier.py`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

구현하지 말아야 할 MVP 제외 범위:

- [x] LLM evaluator provider
- [x] final result builder, QCA writer, workflow full orchestration
- [x] 외부 API/DB 호출

완료 기준:

- [x] rule verifier unit test가 통과한다.
- [x] rule 결과가 suspicious selector의 입력으로 재사용 가능하다.

### feature5_suspicious_sentence_selector

구현 목표:

- [x] suspicious sentence 선정 로직을 구현한다.
- [x] citation missing/invalid 기준을 구현한다.
- [x] low overlap 기준을 구현한다.
- [x] insufficient context 기준을 구현한다.
- [x] all-sentence evaluation mode interface를 구현한다.
- [x] selector 테스트를 작성한다.

테스트 케이스 목록:

- [x] missing citation 문장이 suspicious로 선정된다.
- [x] invalid citation 문장이 suspicious로 선정된다.
- [x] low token/entity overlap 문장이 suspicious로 선정된다.
- [x] number/date/version mismatch 문장이 suspicious로 선정된다.
- [x] insufficient context 상태의 문장이 low-confidence evaluation 대상으로 분류된다.
- [x] Answer Generation warning이 있는 문장이 suspicious 후보가 된다.
- [x] 기본 설정에서는 suspicious sentence만 LLM evaluator 대상이 된다.
- [x] all-sentence evaluation mode 설정 시 모든 문장이 evaluator 대상이 된다.
- [x] evaluator 대상이 없는 경우에도 workflow가 정상적으로 rule-only 결과를 만들 수 있다.
- [x] selector result에 API key, Authorization, secret-like 값이 포함되지 않는다.

수정 가능 파일 범위:

- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/verification/**`
- [x] `ai-agent/answer-verification-agent/tests/unit/test_suspicious_sentence_selector.py`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

구현하지 말아야 할 MVP 제외 범위:

- [x] LLM evaluator provider 실제 구현
- [x] final output/QCA/regeneration builder
- [x] 외부 API/DB 호출

완료 기준:

- [x] selector unit test가 통과한다.
- [x] suspicious-only 기본 정책과 all-sentence 확장 interface가 모두 검증된다.

### feature6_llm_evaluator_provider

구현 목표:

- [x] evaluator provider interface를 정의한다.
- [x] OpenAI evaluator provider를 구현한다.
- [x] fake evaluator provider를 구현한다.
- [x] evaluator prompt builder를 구현한다.
- [x] evaluator output parsing을 구현한다.
- [x] safe provider error 처리를 구현한다.
- [x] provider/evaluator 테스트를 작성한다.

테스트 케이스 목록:

- [x] fake evaluator가 SUPPORTED를 반환하면 sentence evaluation result가 올바르게 생성된다.
- [x] fake evaluator가 UNSUPPORTED를 반환하면 unsupported reason과 score가 보존된다.
- [x] fake evaluator가 LOW_CONFIDENCE를 반환하면 low-confidence result가 생성된다.
- [x] invalid evaluator label은 LOW_CONFIDENCE fallback으로 처리된다.
- [x] invalid JSON 또는 schema mismatch evaluator response는 safe warning으로 처리되고 rule result를 유지할 수 있다.
- [x] evaluator prompt에 sentence text, cited context snippets, failed rules가 포함된다.
- [x] evaluator prompt에 원본 전체 answer/context가 과도하게 포함되지 않는다.
- [x] OpenAI provider는 API key를 외부 주입 또는 환경변수에서만 읽는다.
- [x] API key가 없으면 provider configuration error가 발생한다.
- [x] OpenAI timeout/5xx는 retryable safe error로 분류된다.
- [x] OpenAI auth error는 non-retryable auth failure로 분류된다.
- [x] 기본 pytest suite는 실제 OpenAI network call 없이 통과한다.
- [x] error/repr/log-safe 문자열에 `OPENAI_API_KEY`, Authorization, secret-like 값이 포함되지 않는다.

수정 가능 파일 범위:

- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/evaluator/**`
- [x] `ai-agent/answer-verification-agent/tests/unit/test_llm_evaluator_provider.py`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

구현하지 말아야 할 MVP 제외 범위:

- [x] 실제 OpenAI live test를 기본 suite에 포함
- [x] all-sentence evaluation 강제 실행
- [x] Answer Generation 재호출 또는 feedback loop

완료 기준:

- [x] provider/evaluator unit test가 fake provider 기반으로 통과한다.
- [x] OpenAI provider는 interface 뒤에 있고 API key 외부 주입 원칙을 지킨다.

### feature7_verification_result_builder

구현 목표:

- [x] sentence result 병합을 구현한다.
- [x] overall label/score 계산을 구현한다.
- [x] unsupported claims를 생성한다.
- [x] UI warning metadata를 생성한다.
- [x] QCA local output을 생성한다.
- [x] regeneration recommendation/request payload를 생성한다.
- [x] verification report helper를 구현한다.
- [x] local JSON writer를 구현한다.
- [x] result builder 테스트를 작성한다.

테스트 케이스 목록:

- [x] rule result와 LLM evaluator result가 sentence result로 병합된다.
- [x] unsupported 문장이 있으면 overall label이 UNSUPPORTED 또는 LOW_CONFIDENCE로 계산된다.
- [x] 모든 핵심 문장이 근거를 갖고 score가 충분하면 PASS 또는 SUPPORTED가 생성된다.
- [x] insufficient context는 LOW_CONFIDENCE로 처리된다.
- [x] unsupported_claims가 sentence_id, text, reason, citations를 포함한다.
- [x] UI warning metadata가 unsupported/low-confidence 비율에 따라 warning_level과 reasons를 계산한다.
- [x] QCA local output이 accepted, needs_review, rejected quality_label을 생성한다.
- [x] regeneration recommendation이 unsupported claims 기반으로 생성된다.
- [x] regeneration request는 payload만 생성하고 Answer Generation Agent를 직접 호출하지 않는다.
- [x] verification report가 status, counts, llm_evaluation_count, warnings_count를 계산한다.
- [x] local writer가 verification output, report, QCA, failed JSON/JSONL 파일을 생성한다.
- [x] output/report/QCA/failed files에 API key, token, Authorization 값이 포함되지 않는다.

수정 가능 파일 범위:

- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/verification/**`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/qca/**`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/regeneration/**`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/storage/**`
- [x] `ai-agent/answer-verification-agent/tests/unit/test_verification_result_builder.py`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

구현하지 말아야 할 MVP 제외 범위:

- [x] QCA DB 저장
- [x] UI rendering
- [x] Answer Generation Agent 직접 재호출
- [x] production dashboard 연동

완료 기준:

- [x] result builder unit test가 통과한다.
- [x] Verification Output, QCA output, regeneration payload, report가 local file output으로 생성 가능하다.

### feature8_langgraph_workflow_and_cli

구현 목표:

- [x] LangGraph workflow를 구성한다.
- [x] sequential fallback을 구성한다.
- [x] CLI 실행 스크립트를 구현한다.
- [x] local output 저장을 구현한다.
- [x] report/QCA/failed 저장을 구현한다.
- [x] fake evaluator 기반 workflow integration test를 작성한다.

테스트 케이스 목록:

- [x] fake evaluator 기반 workflow가 load_input -> normalize -> parse -> rule verify -> select suspicious -> evaluate suspicious -> aggregate -> warning/QCA/regeneration -> write 순서로 실행된다.
- [x] rule-based verifier가 LLM evaluator보다 먼저 실행된다.
- [x] 기본 설정에서 suspicious sentence만 evaluator provider로 전달된다.
- [x] evaluator failure 시 rule result를 유지하고 LOW_CONFIDENCE warning을 남긴다.
- [x] workflow가 verification output, report, QCA, failed output을 local file로 생성한다.
- [x] CLI가 `--input`, `--output`, `--report-output`, `--qca-output`, `--failed-output`, `--provider`, `--model` 등 필수/옵션 인자를 처리한다.
- [x] CLI summary에 API key, Authorization, secret-like 값이 포함되지 않는다.
- [x] LangGraph가 설치되어 있지 않아도 sequential fallback으로 명확히 실행된다.
- [x] 실제 OpenAI live API, DB, BFF, SSE, Answer Generation 재호출이 실행되지 않는다.

수정 가능 파일 범위:

- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/workflow.py`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/scripts/run_answer_verification.py`
- [x] `ai-agent/answer-verification-agent/src/answer_verification_agent/storage/**`
- [x] `ai-agent/answer-verification-agent/tests/integration/test_workflow_cli.py`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

구현하지 말아야 할 MVP 제외 범위:

- [x] 실제 OpenAI live API 호출 테스트
- [x] Answer Generation Agent 직접 재호출
- [x] DB/QCA DB/BFF/SSE/feedback/dashboard 연동

완료 기준:

- [x] workflow/CLI integration test가 fake evaluator 기반으로 통과한다.
- [x] local output/report/QCA/failed 산출물이 생성된다.
- [x] LangGraph optional fallback 정책이 검증된다.

### feature9_fixture_and_safety_tests

구현 목표:

- [x] synthetic supported fixture를 작성한다.
- [x] synthetic unsupported fixture를 작성한다.
- [x] synthetic low-confidence fixture를 작성한다.
- [x] synthetic invalid citation fixture를 작성한다.
- [x] synthetic numeric mismatch fixture를 작성한다.
- [x] synthetic insufficient context fixture를 작성한다.
- [x] malformed input/provider failure fixture를 작성한다.
- [x] OpenAI API key/token safety test를 작성한다.
- [x] output schema 검증을 작성한다.
- [x] boundary test를 작성한다.

테스트 케이스 목록:

- [x] supported fixture가 PASS 또는 SUPPORTED overall label과 SUPPORTED sentence labels를 생성한다.
- [x] unsupported fixture가 unsupported claims, UI warning, regeneration recommendation을 생성한다.
- [x] low-confidence fixture가 LOW_CONFIDENCE label과 warning metadata를 생성한다.
- [x] invalid citation fixture가 invalid citation coverage와 warning을 생성한다.
- [x] numeric mismatch fixture가 number/date/version rule failure를 생성한다.
- [x] insufficient context fixture가 failed가 아닌 LOW_CONFIDENCE 또는 NOT_CHECKED sentence result로 처리된다.
- [x] malformed input fixture가 safe failed output/report를 생성한다.
- [x] provider failure fixture가 rule result를 유지하고 safe warning/report를 생성한다.
- [x] QCA local JSON/JSONL output shape가 검증된다.
- [x] regeneration request payload가 생성되지만 Answer Generation Agent 직접 호출은 실행되지 않는다.
- [x] output/report/QCA/failed files에 실제 API key, token, Authorization 값이 포함되지 않는다.
- [x] basic test suite가 fake evaluator provider만 사용하고 실제 OpenAI live API를 호출하지 않는다.
- [x] BFF/DB/SSE/feedback DB/production dashboard/UI rendering이 실행되지 않는다.

수정 가능 파일 범위:

- [x] `ai-agent/answer-verification-agent/tests/fixtures/**`
- [x] `ai-agent/answer-verification-agent/tests/integration/test_fixture_safety.py`
- [x] `docs/ai/current-plan.md`
- [x] `docs/ai/working-log.md`

구현하지 말아야 할 MVP 제외 범위:

- [x] 새로운 runtime 기능 확장
- [x] 실제 OpenAI live API 호출
- [x] QCA DB 저장, feedback DB 저장, BFF/SSE/dashboard/UI 연동

완료 기준:

- [x] fixture/safety integration test가 통과한다.
- [x] 전체 test suite와 compile check가 통과한다.
- [x] MVP 제외 기능 boundary가 테스트로 고정된다.
- [x] Answer Verification Agent MVP feature1-9 완료 여부가 working-log에 기록된다.

## 7. 구현 순서

- [x] 1단계: `feature1_project_skeleton_and_schema`
- [x] 2단계: `feature2_verification_input_normalization`
- [x] 3단계: `feature3_sentence_and_citation_parser`
- [x] 4단계: `feature4_rule_based_verifier`
- [x] 5단계: `feature5_suspicious_sentence_selector`
- [x] 6단계: `feature6_llm_evaluator_provider`
- [x] 7단계: `feature7_verification_result_builder`
- [x] 8단계: `feature8_langgraph_workflow_and_cli`
- [x] 9단계: `feature9_fixture_and_safety_tests`

## 8. OpenAI API Key 및 Fake Provider 원칙

- [x] `OPENAI_API_KEY`는 환경변수, runtime secret provider, 테스트용 주입 방식으로만 받는다.
- [x] CLI 기본 인자로 raw API key를 받지 않는다.
- [x] 실제 `.env` 파일은 생성하거나 커밋하지 않는다.
- [x] `.env.example`을 후속 feature에서 만들 경우 placeholder 이름만 기록하고 실제 key 형태의 값은 넣지 않는다.
- [x] OpenAI evaluator provider는 `AnswerEvaluatorProvider` interface 뒤에 둔다.
- [x] 기본 unit/integration test는 fake evaluator provider를 사용한다.
- [x] OpenAI live smoke test는 기본 검증에서 제외하고, 필요 시 별도 opt-in flag 또는 별도 script로 분리한다.
- [x] provider error, prompt, request, response, log-safe 출력에는 API key, Authorization header, secret-like 문자열이 포함되지 않아야 한다.

## 9. 완료 기준

### 이번 계획 세션 완료 기준

- [x] 필수 문서를 읽고 공통 규칙과 Answer Verification Agent 요구사항을 요약했다.
- [x] 기존 `docs/ai/current-plan.md`를 Answer Verification Agent 전용 계획으로 교체했다.
- [x] `docs/ai/working-log.md`에서 이전 Answer Generation Agent MVP 완료 기록을 확인했다.
- [x] Feature Breakdown 기준 feature1-9 구현 계획을 작성했다.
- [x] 각 feature별 구현 목표, 테스트 케이스 목록, 수정 가능 파일 범위, MVP 제외 범위, 완료 기준을 포함했다.
- [x] OpenAI API key 외부 주입 방식과 fake evaluator 기본 테스트 원칙을 명시했다.
- [x] 실제 구현 코드, 테스트 코드, 스크립트, 패키지 파일을 작성하지 않았다.

### 전체 MVP 완료 기준

- [x] CLI로 Answer Verification workflow를 실행할 수 있다.
- [x] Answer Generation Agent output과 Top-5 context JSON을 입력으로 처리할 수 있다.
- [x] OpenAI API key는 외부 주입으로만 사용한다.
- [x] API key가 코드, fixture, log, output file, 문서 예시에 저장되지 않는다.
- [x] 테스트는 기본적으로 fake evaluator provider를 사용한다.
- [x] rule-based verifier가 citation, context id, token/entity, number/date/version 근거를 검증한다.
- [x] suspicious sentence만 LLM evaluator 대상으로 선정된다.
- [x] all-sentence evaluation mode 확장 가능성이 있다.
- [x] sentence-level verification result가 생성된다.
- [x] overall label/score가 생성된다.
- [x] UI warning metadata가 생성된다.
- [x] QCA local JSON/JSONL output이 생성된다.
- [x] regeneration recommendation/request payload가 생성된다.
- [x] 실제 Answer Generation 재호출은 수행하지 않는다.
- [x] 실제 DB 저장, UI 렌더링, SSE 전송은 수행하지 않는다.
- [x] LangGraph workflow가 전체 단계를 orchestration한다.
- [x] fixture 기반 integration test가 통과한다.

## 10. 검증 명령

후속 feature 구현 완료 전 가능한 범위에서 아래 명령을 실행한다.

```bash
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

Answer Verification package가 구성되면 agent 디렉토리에서 다음 명령을 별도로 실행한다.

```bash
python3.11 -m pytest
python3.11 -m compileall src scripts
```

feature별 구현 세션에서는 해당 feature test를 먼저 실행하고, milestone 완료 시 agent 전체 pytest와 root 검증 명령을 실행한다. 루트 script가 agent 하위 pytest를 자동 발견하지 못하면 agent 디렉토리 pytest 결과를 별도로 보고한다.
