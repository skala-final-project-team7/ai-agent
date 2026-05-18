# Working Log

## 2026-05-18 - Answer Generation Agent feature8_fixture_and_safety_tests

### 작업 목표

- Answer Generation Agent MVP 전체를 synthetic fixture 기반으로 검증한다.
- 민감정보 비노출, Answer Verification Agent 입력 호환성, sentence-level citation, source/report/failed output shape, MVP 제외 기능 boundary를 테스트로 고정한다.
- 새로운 runtime 기능 확장은 하지 않고 feature1-7 구현을 검증/보강하는 범위로만 작업한다.

### 테스트 우선 진행

- synthetic fixture 디렉토리 `ai-agent/answer-generation-agent/tests/fixtures/answer_generation/`를 추가했다.
- timeline, step_by_step, evidence_first, history_summary, general, insufficient_context, malformed_input, attachment_source fixture를 작성했다.
- `ai-agent/answer-generation-agent/tests/integration/test_fixture_safety.py`를 먼저 작성했다.
- 최초 실행에서 malformed input fixture가 `GenerationInputNormalizationError`를 직접 발생시켜 failed output/report/failed item을 생성하지 못하는 것을 확인했다.

### 구현 내용

- `ai-agent/answer-generation-agent/src/answer_generation_agent/generation/workflow.py`를 보강했다.
- malformed/invalid input처럼 normalization이 불가능한 경우도 safe failed AnswerOutput, GenerationReport, FailedItem으로 기록하도록 처리했다.
- failed artifact에는 synthetic input에서 가능한 `conversation_id`, `user_id`, `routing_id`만 보존하고, reason/error_type은 safe redaction된 `input_error`로 남긴다.
- 실제 Qdrant 검색, embedding, Cross-Encoder reranking, Answer Verification 호출, SSE transport, BFF/DB/QCA/feedback/UI formatting은 실행하지 않고 `excluded_capabilities` marker로 검증한다.

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

- `python3.11 -m pytest tests/integration/test_fixture_safety.py`: 최초 1 failed 후 workflow safe failed artifact 보강, 최종 13 passed.
- `python3.11 -m pytest`: 101 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### MVP 완료 여부

- Answer Generation Agent MVP feature1-8이 모두 완료되었다.
- 남은 항목은 MVP 제외 후속 확장이다: 실제 Qdrant/RAG adapter, Dense/Sparse embedding, Cross-Encoder reranking, Answer Verification Agent 호출 adapter, 실제 SSE transport, BFF/DB/QCA/feedback/UI response formatting, live evaluation/prompt regression.

## 2026-05-18 - Answer Generation Agent feature7_langgraph_workflow_and_cli

### 작업 목표

- feature2-6에서 구현한 input normalization, prompt template builder, answer generation service, citation mapping, answer output builder를 workflow와 CLI 수동 실행 흐름으로 연결한다.
- fake provider/injected provider 기반으로 workflow를 실행하고 local JSON output/report/failed 파일을 생성한다.
- 실제 OpenAI live API 호출, Qdrant 검색, Dense/Sparse embedding, Cross-Encoder reranking, Answer Verification 직접 호출, 실제 SSE 전송, BFF/DB/QCA/feedback/UI formatting은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/answer-generation-agent/tests/integration/test_workflow_cli.py`를 먼저 작성했다.
- 최초 실행에서 `answer_generation_agent.generation.workflow` 모듈이 없어 `ModuleNotFoundError`가 발생하는 것을 확인했다.
- 테스트 케이스에는 workflow node 실행 순서, answer/report JSON 생성, timeline/step_by_step/evidence_first/history_summary fixture, insufficient context, provider failure safe output/failed item, CLI 실행, secret 비노출, LangGraph optional fallback, MVP 제외 기능 비실행 marker 검증을 포함했다.

### 구현 내용

- `ai-agent/answer-generation-agent/src/answer_generation_agent/generation/workflow.py`를 추가했다.
- `AnswerGenerationWorkflowState`, `AnswerGenerationWorkflowResult`, `AnswerGenerationWorkflow`를 구현했다.
- sequential workflow는 `load_config -> load_input -> normalize_generation_input -> validate_top_contexts -> assess_context_sufficiency -> build_task_prompt -> generate_answer -> map_sentence_citations -> build_answer_output -> write_output -> write_report` 순서로 기존 service/helper를 호출한다.
- LangGraph는 optional capability로 감지하고, MVP 실행은 명확한 sequential fallback으로 수행한다.
- `FakeAnswerLLMProvider` 또는 주입 provider로 workflow를 실행할 수 있게 했다.
- provider failure는 safe failed AnswerOutput, report, failed item JSON으로 처리한다.
- workflow result에는 후속 feature8에서 검증할 수 있도록 output/report/failed path, executed nodes, engine, excluded capabilities를 남긴다.
- `ai-agent/answer-generation-agent/src/answer_generation_agent/scripts/run_answer_generation.py`를 workflow 실행 CLI로 확장했다.
- CLI는 `--input`, `--output`, `--report-output`, `--failed-output`, `--provider`, `--model`, `--max-contexts`, `--max-answer-sentences`를 처리하고 safe summary만 출력한다.
- `ai-agent/answer-generation-agent/src/answer_generation_agent/generation/__init__.py`에 feature7 workflow helper를 export했다.

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

- `python3.11 -m pytest tests/integration/test_workflow_cli.py`: 최초 import 실패 확인 후 11 passed.
- `python3.11 -m pytest`: 최초 1건 실패 후 CLI 호환 summary 문구를 조정했고, 최종 88 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature8_fixture_and_safety_tests`: synthetic fixture 기반 end-to-end/safety 검증과 MVP boundary test를 보강한다.

## 2026-05-18 - Answer Generation Agent feature6_answer_output_builder

### 작업 목표

- feature1-5에서 생성한 normalized input, raw generation result, citation mapping result를 조립해 Answer Verification Agent가 소비 가능한 canonical `AnswerOutput`을 생성한다.
- `GenerationReport`, safe `FailedItem`, local JSON writer를 구현한다.
- LangGraph workflow, CLI full orchestration, 실제 OpenAI live API 호출, Qdrant/embedding/reranking, Answer Verification 직접 호출, SSE 전송, BFF/DB/QCA/feedback/UI formatting은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/answer-generation-agent/tests/unit/test_answer_output_builder.py`를 먼저 작성했다.
- 최초 실행에서 `answer_generation_agent.generation.answer_output_builder` 모듈이 없어 `ModuleNotFoundError`가 발생하는 것을 확인했다.
- 테스트 케이스에는 canonical AnswerOutput 필드, deterministic generation_id, success/insufficient/failed status 매핑, citation mapping 결과 보존, routing/model/confidence 보존, warnings/unsupported_gaps 병합, streaming interface-only chunk, report count, failed item safe shape, local JSON writer, output/report/failed 민감정보 비노출, sentence text/citations 분리 검증을 포함했다.

### 구현 내용

- `ai-agent/answer-generation-agent/src/answer_generation_agent/generation/answer_output_builder.py`를 추가했다.
- `build_generation_id()`, `build_answer_output()`, `build_failed_answer_output()`, `build_generation_report()`, `build_failed_item()`, `write_answer_outputs()`를 구현했다.
- `AnswerOutput`은 success, insufficient_context, failed 상태를 canonical schema로 조립하고 routing metadata, model, confidence, unsupported_gaps, warnings를 보존한다.
- sentence/source/used_context_ids는 feature5 `CitationMappingResult`를 그대로 사용해 Answer Verification Agent가 문장별 citation을 검증할 수 있게 했다.
- MVP streaming은 `streaming_supported=false`로 유지하고, 후속 adapter가 answer text를 chunk로 분해할 수 있는 interface-only text chunk를 생성한다.
- local writer는 `answer_output.json`, `generation_report.json`, `failed_items.json`을 생성하며 저장 디렉토리를 자동 생성한다.
- output/report/failed serialization에서 API key, Authorization, token/secret-like marker를 redaction한다.
- `ai-agent/answer-generation-agent/src/answer_generation_agent/generation/__init__.py`에 feature6 public helper를 export했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_answer_output_builder.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_answer_output_builder.py`: 최초 import 실패 확인 후 12 passed.
- `python3.11 -m pytest`: 77 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature7_langgraph_workflow_and_cli`: feature2-6 서비스를 LangGraph/sequential workflow와 CLI full orchestration으로 연결한다.
- `feature8_fixture_and_safety_tests`: fixture 기반 end-to-end/safety 검증과 MVP 제외 기능 boundary test를 보강한다.

## 2026-05-18 - Answer Generation Agent feature5_citation_mapping

### 작업 목표

- LLM raw answer와 Top context를 기반으로 sentence-level citation 후보를 검증/정규화한다.
- Answer Verification Agent가 검증할 수 있도록 `GeneratedSentence`, `GeneratedSource`, `used_context_ids`, warning 구조를 생성한다.
- 최종 AnswerOutput builder, LangGraph workflow, local output pipeline, 실제 OpenAI live API 호출, Qdrant/embedding/reranking, Answer Verification 직접 호출, SSE 전송은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/answer-generation-agent/tests/unit/test_citation_mapping.py`를 먼저 작성했다.
- 최초 실행에서 `answer_generation_agent.generation.citation_mapping` 모듈이 없어 `ModuleNotFoundError`가 발생하는 것을 확인했다.
- 테스트 케이스에는 raw answer 문장 분리, deterministic sentence_id, valid citation 보존, invalid citation 제거와 warning, 단일 context fallback citation, 다중 context missing citation warning, source metadata 보존, duplicate citation/source 제거, used_context_ids 계산, attachment filename 보존, empty answer safe handling, 민감정보 비노출, sentence text/citations 분리 검증을 포함했다.

### 구현 내용

- `ai-agent/answer-generation-agent/src/answer_generation_agent/generation/citation_mapping.py`를 추가했다.
- `CitationMappingResult`와 `map_citations()`를 구현했다.
- raw sentence candidate가 있으면 candidate text를 우선 사용하고, 없으면 answer text를 문장 단위로 분리한다.
- sentence id는 `s1`, `s2` 형식으로 deterministic하게 생성한다.
- citation은 normalized Top context의 `context_id`만 허용하며, 존재하지 않는 citation은 warning 후 제거한다.
- citation 후보가 없고 Top context가 하나뿐이면 fallback citation을 적용하고, 여러 context면 missing citation warning을 남긴다.
- source list는 사용된 context 기준으로 생성하고 context/source metadata를 보존한다.
- duplicate citation/source는 제거하고, `used_context_ids`는 sentence citation 순서 기준으로 계산한다.
- sentence/source/warning/result serialization에서 API key, Authorization, token/secret-like marker를 redaction한다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_citation_mapping.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_citation_mapping.py`: 최초 import 실패 확인 후 12 passed.
- `python3.11 -m pytest`: 65 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature6_answer_output_builder`: Answer Verification Agent 입력 호환 output builder, report/helper, local JSON writer를 구현한다.
- `feature7_langgraph_workflow_and_cli` 이후 항목은 후속 세션에서 feature 단위로 진행한다.

## 2026-05-18 - Answer Generation Agent feature4_llm_provider_and_answer_generation

### 작업 목표

- Answer Generation Agent의 `AnswerLLMProvider` interface, fake provider, OpenAI provider adapter shell, answer generation request/result schema, context sufficiency handling, answer generation service를 구현한다.
- 기본 테스트 suite는 fake provider와 injected fake transport만 사용하고 실제 OpenAI live API 호출은 수행하지 않는다.
- feature4에서는 raw answer text와 sentence/citation 후보까지만 보존하며 최종 citation mapping, AnswerOutput 조립, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/answer-generation-agent/tests/unit/test_llm_provider_answer_generation.py`를 먼저 작성했다.
- 최초 실행에서 `answer_generation_agent.generation.answer_generation` 모듈이 없어 `ModuleNotFoundError`가 발생하는 것을 확인했다.
- 테스트 케이스에는 fake provider answer parsing, raw sentence/citation 후보 보존, empty context insufficient 처리, usable/weak context 처리, prompt 전달, model/fallback policy, invalid LLM response safe error, OpenAI provider API key 외부 주입, request 구성, auth/timeout/5xx error 분류, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/answer-generation-agent/src/answer_generation_agent/generation/answer_generation.py`를 추가했다.
- `AnswerLLMProvider` protocol, `FakeAnswerLLMProvider`, `OpenAIAnswerLLMProvider`, `AnswerGenerationService`를 구현했다.
- `AnswerGenerationRequest`, `AnswerLLMResult`, `RawSentenceCandidate`, `AnswerGenerationResult`를 추가했다.
- `parse_llm_response()`는 LLM output JSON/object를 검증하고 answer text, raw sentence/citation 후보, unsupported gaps를 파싱한다.
- context가 없으면 provider를 호출하지 않고 `answer_status=insufficient_context` 결과와 warning을 반환한다.
- context가 있으면 prompt builder 결과를 provider에 전달하고, weak lexical overlap context에는 `weak_context` warning을 추가한다.
- simple model policy `select_generation_model()`은 config model 또는 fallback model을 선택한다.
- OpenAI provider는 API key를 외부 주입 또는 `OPENAI_API_KEY` 환경변수에서만 읽고, 기본 테스트에서는 injectable transport만 사용한다.
- OpenAI auth/configuration error는 non-retryable로, timeout/rate limit/5xx는 retryable safe error로 분류한다.
- provider request/error/repr/safe serialization에서 API key, Authorization, token/secret-like marker를 redaction한다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_llm_provider_answer_generation.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_llm_provider_answer_generation.py`: 최초 import 실패 확인 후 17 passed.
- `python3.11 -m pytest`: 53 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature5_citation_mapping`: LLM output sentence parsing/citation 후보를 최종 `GeneratedSentence`와 source list로 매핑한다.
- `feature6_answer_output_builder` 이후 항목은 후속 세션에서 feature 단위로 진행한다.

## 2026-05-18 - Answer Generation Agent feature3_prompt_template_builder

### 작업 목표

- feature2 normalized generation input과 Top context를 LLM provider가 사용할 prompt payload로 조립한다.
- `timeline`, `step_by_step`, `evidence_first`, `history_summary`, `general` task prompt type별 답변 지시를 구현한다.
- 공통 context-only rule, sentence-level citation instruction, Answer Verification Agent 검증 가능한 JSON/schema 출력 지시, Top context formatting, prompt length guard를 구현한다.
- 실제 OpenAI API 호출, answer generation service, citation mapping, answer output builder, LangGraph workflow, local output pipeline, Qdrant/embedding/reranking, Answer Verification 호출, SSE 전송은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/answer-generation-agent/tests/unit/test_prompt_template_builder.py`를 먼저 작성했다.
- 최초 실행에서 `answer_generation_agent.generation.prompt_template` 모듈이 없어 `ModuleNotFoundError`가 발생하는 것을 확인했다.
- 테스트 케이스에는 task prompt type별 지시문, unsupported task prompt fallback, context 밖 사실 단정 금지, context가 있으면 근거 있는 범위에서 최대한 답변하는 원칙, sentence-level citation instruction, Answer Verification JSON/schema 출력 지시, Top context metadata formatting, empty context prompt, Top-5 제한 유지, context truncation, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/answer-generation-agent/src/answer_generation_agent/generation/prompt_template.py`를 추가했다.
- `PromptPayload`와 `build_prompt_payload()`를 구현했다.
- 공통 system prompt에는 제공된 context 밖 사실 단정 금지, context 기반 답변, 근거 부족 시 제한 사항 표시, sentence-level citation과 context_id 참조 규칙을 포함했다.
- task prompt type별 developer prompt는 장애 대응 timeline, 운영 가이드 step-by-step, 정책·절차 evidence-first, 이력 조회 history-summary, 일반 답변 general 지시를 포함한다.
- Answer Verification Agent가 검증 가능한 JSON/schema output instruction을 포함했다.
- Top context는 `context_id`, `title`, `space_key`, `source_url`, `score`, `rerank_score`, `content` 중심으로 포맷팅한다.
- unsupported task prompt type은 `general`로 fallback하고 warning을 남긴다.
- prompt length guard는 context content를 제한하고 `context_truncated` warning을 남긴다.
- prompt payload serialization에서 API key, Authorization, token/secret-like marker를 redaction한다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_prompt_template_builder.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_prompt_template_builder.py`: 최초 import 실패 확인 후 13 passed.
- `python3.11 -m pytest`: 36 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature4_llm_provider_and_answer_generation`: provider interface, fake/OpenAI provider, answer generation request/result, context sufficiency handling을 구현한다.
- `feature5_citation_mapping` 이후 항목은 후속 세션에서 feature 단위로 진행한다.

## 2026-05-18 - Answer Generation Agent feature2_generation_input_normalization

### 작업 목표

- Query Routing Agent output과 Top-5 context를 포함한 generation input JSON을 로드, 검증, 정규화한다.
- top context 5개 제한, rerank/score/input order 기반 정렬, empty content 제외, duplicate context 처리, unsupported task prompt fallback을 구현한다.
- 실제 OpenAI API 호출, prompt template builder, answer generation, citation mapping, workflow, local output pipeline, Qdrant/embedding/reranking, Answer Verification 호출, SSE 전송은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/answer-generation-agent/tests/unit/test_generation_input_normalization.py`를 먼저 작성했다.
- 최초 실행에서 `answer_generation_agent.generation` package가 없어 `ModuleNotFoundError`가 발생하는 것을 확인했다.
- 테스트 케이스에는 valid JSON load, malformed JSON error, 필수값 validation, supported/unsupported task prompt type, top context 5개 제한, rerank/score 정렬, empty content 제외, duplicate context 처리, insufficient context 후보 상태, source metadata 보존, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/answer-generation-agent/src/answer_generation_agent/generation/input_normalization.py`를 추가했다.
- `load_generation_input_json()`은 JSON 파일을 object payload로 로드하고 malformed JSON을 safe `GenerationInputLoadError`로 분류한다.
- `normalize_generation_input()`은 필수 generation/routing/search field를 검증하고 `GenerationInput` 내부 schema로 변환한다.
- unsupported `task_prompt_type`은 `general`로 fallback하고 warning을 남긴다.
- top context는 `rerank_score`, `score`, 입력 순서 기준으로 deterministic하게 정렬한 뒤 최대 5개만 유지한다.
- content가 비어 있는 context와 duplicate `context_id`는 warning 후 제외한다.
- context가 하나도 남지 않으면 이후 단계에서 `insufficient_context`로 처리할 수 있도록 `insufficient_context_candidate=true`를 남긴다.
- metadata와 warning/result serialization에서 API key, Authorization, token/secret-like marker를 노출하지 않도록 sanitization을 적용했다.
- CLI skeleton은 feature2 normalization service를 사용해 input validation과 normalization만 수행하도록 갱신했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_generation_input_normalization.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_generation_input_normalization.py`: 최초 import 실패 확인 후 14 passed.
- `python3.11 -m pytest`: 23 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature3_prompt_template_builder`: task prompt type별 prompt template과 context-only answer/citation instruction을 구현한다.
- `feature4_llm_provider_and_answer_generation` 이후 항목은 후속 세션에서 feature 단위로 진행한다.

## 2026-05-18 - Answer Generation Agent feature1_project_skeleton_and_schema

### 작업 목표

- Answer Generation Agent의 기본 Python package 골격과 schema/config 기반을 만든다.
- Query Routing Agent output과 Top-5 context 입력, Answer Verification Agent가 소비할 sentence-level citation 기반 output 방향을 schema로 준비한다.
- 실제 OpenAI API 호출, Qdrant 검색, embedding, reranking, Answer Verification 호출, SSE 전송, BFF/DB/QCA/feedback/UI formatting은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/answer-generation-agent/tests/unit/test_schema_config.py`를 먼저 작성했다.
- 최초 실행에서 `answer_generation_agent` package가 없어 `ModuleNotFoundError`가 발생하는 것을 확인했다.
- 테스트 케이스에는 config 외부 주입과 secret redaction, generation/routing/context/sentence/source/output/stream/report/failed schema, enum, 필수값 validation, CLI skeleton validation을 포함했다.

### 구현 내용

- `ai-agent/answer-generation-agent/pyproject.toml`과 `src/answer_generation_agent` package skeleton을 추가했다.
- `AnswerGenerationConfig`를 추가하고 `OPENAI_API_KEY`는 외부 주입 가능한 값으로만 보관하며 safe dict/repr에 노출되지 않게 했다.
- generation input, routing decision input, top context, generated sentence/source, answer output, stream chunk, generation report, failed/warning schema를 추가했다.
- `scripts/run_answer_generation.py` CLI skeleton을 추가해 실제 OpenAI 호출이나 검색 없이 config/input validation만 수행하게 했다.
- fixture/data input/output/reports/failed 기본 디렉토리를 `.gitkeep`으로 준비했다.
- 실제 `.env` 파일은 만들지 않았고, 값 없는 `.env.example`만 추가했다.

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

- `python3.11 -m pytest tests/unit/test_schema_config.py`: 최초 import 실패 확인 후 9 passed.
- `python3.11 -m pytest`: 9 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature2_generation_input_normalization`: Query Routing output + Top-5 context JSON loader와 normalization을 구현한다.
- `feature3_prompt_template_builder` 이후 항목은 후속 세션에서 feature 단위로 진행한다.

## 2026-05-15 - Query Routing Agent MVP 마감 정리

- `docs/ai/current-plan.md`에서 Query Routing Agent feature1-8과 전체 MVP 완료 기준이 모두 완료 체크되어 있음을 확인했다.
- `docs/ai/current-plan.md`에 남은 미체크 `[ ]` 항목이 없음을 확인했다.
- `ai-agent/query-routing-agent` 내부 `.pytest_cache`, `__pycache__`, `*.pyc` 캐시를 삭제했다.
- 실제 OpenAI live API 호출은 수행하지 않았다.
- 실제 Qdrant 검색, embedding 생성, Cross-Encoder reranking, ACL enforcement, Answer Generation/Verification, BFF/DB/SSE 연동은 MVP 제외 후속 확장 범위로 유지한다.

검증 결과:

- `python3.11 -m pytest`: 102 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공.
- `./scripts/verify.sh`: 성공.

## 2026-05-15 - Query Routing Agent feature8_fixture_and_safety_tests

### 작업 목표

- Query Routing Agent MVP 전체를 synthetic fixture 기반으로 검증한다.
- routing decision/search request/report/failed output shape, intent별 mapping, ACL filter 전달, pool weight, safety redaction, MVP 제외 기능 boundary를 테스트로 고정한다.
- 실제 OpenAI live API 호출, Qdrant 검색, embedding 생성, Cross-Encoder reranking, ACL enforcement, Answer Generation/Verification, BFF/DB/SSE는 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/query-routing-agent/tests/integration/test_fixture_safety.py`를 먼저 작성했다.
- 최초 실행에서 synthetic fixture 부재로 실패를 확인했다.
- 테스트 케이스에는 incident/operations/policy/history/unknown fixture full workflow, history date/label filter, ACL payload 전달과 enforcement 미수행, malformed input, provider failure, CLI safety, MVP 제외 기능 미실행 검증을 포함했다.

### 구현 내용

- `ai-agent/query-routing-agent/tests/fixtures/query_routing/`에 synthetic fixture를 추가했다.
  - `incident_response.json`
  - `operations_guide.json`
  - `policy_procedure.json`
  - `history_lookup.json`
  - `unknown_intent.json`
  - `acl_metadata.json`
  - `provider_failure.json`
  - `malformed_input.json`
- feature8 safety test 중 unknown intent fallback에서 query rewrite padding이 중복 query 때문에 종료되지 않는 경계 버그를 발견했다.
- `ai-agent/query-routing-agent/src/query_routing_agent/routing/query_rewrite.py`에서 fallback padding query가 항상 unique하게 추가되도록 최소 보강했다.
- 테스트 fixture와 출력물에는 실제 token, API key, secret, credential을 넣지 않았다.

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

- `python3.11 -m pytest tests/integration/test_fixture_safety.py`: 최초 fixture 부재 실패 확인 후 10 passed.
- `python3.11 -m pytest`: 102 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- Query Routing Agent MVP feature1-8 구현과 fixture/safety 검증을 완료했다.
- 남은 범위는 실제 Qdrant search adapter, embedding, Cross-Encoder reranking, ACL enforcement, Answer Generation/Verification 연동, BFF/DB/SSE 연동, production prompt tuning과 live evaluation regression 등 MVP 제외 후속 확장이다.

## 2026-05-15 - Query Routing Agent feature7_langgraph_workflow_and_cli

### 작업 목표

- Query Routing Agent feature1-6 산출물인 routing input normalization, intent classification, query rewrite, filter/weight builder, routing decision/search request builder를 workflow와 CLI 수동 실행 흐름으로 연결한다.
- LangGraph optional wrapper와 sequential fallback을 제공하되, node는 orchestration에 집중하고 기존 service/helper를 재사용한다.
- 실제 Qdrant 검색, embedding 생성, Cross-Encoder reranking, ACL enforcement, Answer Generation/Verification, BFF/DB/SSE는 구현하지 않고 search request payload 생성까지만 유지한다.

### 테스트 우선 진행

- `ai-agent/query-routing-agent/tests/integration/test_workflow_cli.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `query_routing_agent.workflow` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 fake provider 기반 node 순서 실행, routing decision/report/search request 파일 생성, intent별 task prompt mapping, provider failure safe failed output, malformed input safe failed output, CLI 실행, LangGraph optional fallback, Qdrant/embedding/reranking 미실행 검증을 포함했다.

### 구현 내용

- `ai-agent/query-routing-agent/src/query_routing_agent/workflow.py`를 추가했다.
- `QueryRoutingWorkflowState`, `QueryRoutingWorkflowResult`, `QueryRoutingWorkflowRunner`, `build_query_routing_workflow()`, `run_query_routing_workflow()`를 구현했다.
- workflow는 `load_config -> load_input -> normalize_routing_input -> classify_intent_and_rewrite -> build_metadata_filters -> build_pool_weights -> build_task_prompt_type -> build_routing_decision -> build_search_request -> write_output -> write_report` 순서로 실행된다.
- LangGraph 설치 여부를 확인해 `execution_mode`를 `langgraph` 또는 `sequential`로 명시하고, 미설치 환경에서는 sequential fallback으로 실행된다.
- provider failure 또는 malformed input은 safe failed item/report 파일로 기록하고 decision output은 생성하지 않는다.
- `write_routing_outputs()`는 기존 디렉토리 기반 파일명 방식에 더해 CLI `--output` 경로를 decision 파일로 사용할 수 있도록 명시 경로 옵션을 지원한다.
- `scripts/run_query_router.py`를 실제 workflow CLI 진입점으로 확장했다.
- CLI는 `--input`, `--output`, `--report-output`, `--failed-output`, `--provider`, `--model`, `--default-query-count`, `--max-query-count` 등을 처리하며 기본 provider는 fake로 두어 live OpenAI 호출을 opt-in으로 유지한다.
- CLI wrapper는 직접 실행 시 `src` package 경로를 안전하게 찾도록 조정했다.

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

- `python3.11 -m pytest tests/integration/test_workflow_cli.py`: 최초 import 실패 확인 후 10 passed.
- `python3.11 -m pytest`: 92 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature8_fixture_and_safety_tests`: synthetic fixture 기반 end-to-end style safety 검증, output shape, 민감정보 비노출, MVP 제외 기능 boundary를 고정한다.

## 2026-05-15 - Query Routing Agent feature2_routing_input_normalization

### 작업 목표

- History Manager Agent output JSON을 Query Routing Agent 내부 routing input schema에 맞게 로드, 검증, 정규화한다.
- optional `preserved_context`/`metadata` 문제는 warning과 safe fallback으로 처리하고, job 자체가 불가능한 필수값 누락이나 malformed JSON은 명확한 오류로 처리한다.
- 실제 OpenAI API 호출, intent classification, query rewrite, filter/weight builder, routing decision builder, LangGraph workflow, Qdrant 검색, embedding, reranking, ACL enforcement는 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/query-routing-agent/tests/unit/test_routing_input_normalization.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `query_routing_agent.routing` normalization API 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 valid JSON load, malformed JSON error, 필수값 validation, supported/unsupported `history_decision`, empty/malformed `preserved_context`, `groups`/`space_keys` canonical list 정규화, ACL 전달값 준비, raw history 제거, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `src/query_routing_agent/routing/normalization.py`와 package export를 추가했다.
- `load_history_manager_output()`은 JSON 파일을 읽고 malformed JSON 또는 object가 아닌 payload를 `RoutingInputLoadError`로 분류한다.
- `normalize_routing_input()`은 `conversation_id`, `user_id`, `original_question`, `query` 필수값을 검증하고 `QueryRoutingInput`으로 변환한다.
- unsupported `history_decision`은 `ambiguous`로 safe fallback하고 warning을 남긴다.
- `preserved_context`의 optional field는 안전하게 기본값/list로 정규화하고, 잘못된 타입은 warning으로 기록한다.
- metadata의 `groups`, `space_keys`는 문자열/배열/누락 케이스를 canonical list로 정규화한다.
- ACL filter 전달용 `AclFilter(user_id, groups)`를 normalization result에 포함하되 권한 판정 결과는 만들지 않는다.
- 입력에 포함된 raw/full history 계열 필드와 민감 metadata key는 normalized output에서 제거하고 safe warning만 남긴다.
- CLI skeleton은 feature2 loader/normalizer를 사용해 input validation을 수행하도록 갱신했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_routing_input_normalization.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_routing_input_normalization.py`: 구현 전 import 실패 확인 후, 구현 후 20 passed.
- `python3.11 -m pytest`: 29 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature3_intent_classification_provider`: LLM provider interface, fake/OpenAI provider, routing prompt, intent classification parsing과 safe fallback을 테스트 우선으로 구현한다.

## 2026-05-15 - Query Routing Agent feature1_project_skeleton_and_schema

### 작업 목표

- Query Routing Agent의 기본 Python package 골격과 config/schema 기반을 만든다.
- History Manager Agent output과 RAG search request/Answer Generation task prompt 방향을 고려한 canonical schema를 정의한다.
- 실제 OpenAI API 호출, Qdrant 검색, embedding 생성, Cross-Encoder reranking, ACL enforcement, 다른 Agent 구현은 하지 않는다.

### 테스트 우선 진행

- `ai-agent/query-routing-agent/tests/unit/test_schema_config.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `query_routing_agent` package 미구현으로 `ModuleNotFoundError` 실패를 확인했다.
- 테스트 케이스에는 config 외부 주입 및 redaction, routing input schema, intent/task prompt enum, metadata/ACL filter, pool weight 합계 정책, routing decision/search request payload, report/failed item, 필수값 validation, CLI skeleton validation을 포함했다.

### 구현 내용

- `ai-agent/query-routing-agent/pyproject.toml`을 추가해 Python package와 pytest 설정을 정의했다.
- `src/query_routing_agent` package 골격과 `config`, `schemas`, `app`, `scripts` 하위 모듈을 추가했다.
- `QueryRoutingConfig`는 model, temperature, timeout, retry, query count, top-k, pool weight, `openai_api_key` 외부 주입 field를 제공하고 safe serialization에서 key를 redaction한다.
- routing input, routing decision, metadata filter, ACL filter payload, pool weight, search request payload, routing report, warning, failed item schema를 dataclass/enum 기반으로 정의했다.
- ACL filter는 `user_id`, `groups` 전달만 표현하고 권한 판정 결과는 포함하지 않는다.
- CLI skeleton은 input JSON과 config validation만 수행하며 OpenAI 호출, Qdrant 검색, workflow 실행은 하지 않는다.
- `.env.example`은 placeholder key 이름만 포함하고 실제 key 값은 포함하지 않았다.
- fixture/data input/output/reports/failed 기본 디렉토리를 `.gitkeep`으로 추가했다.

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

- `python3.11 -m pytest tests/unit/test_schema_config.py`: 구현 전 import 실패 확인 후, 구현 후 9 passed.
- `python3.11 -m pytest`: 9 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature2_routing_input_normalization`: History Manager output loader, malformed input 처리, preserved_context/metadata 정규화, unsupported history_decision warning 처리를 테스트 우선으로 구현한다.

## 2026-05-15 - History Manager Agent MVP 마감 정리

- `docs/ai/current-plan.md`에서 feature1-7, 전체 MVP 완료 기준, OpenAI live smoke test opt-in 원칙, 수정/미수정 영역 표현을 마감 상태로 정리했다.
- 기존 feature7 기록에 MVP 완료 여부가 이미 남아 있어 구현 완료 기록은 중복하지 않았다.
- 불필요한 macOS `.DS_Store` 파일을 삭제했고, 기능 코드 변경은 하지 않았다.
- 검증 결과: `python3.11 -m pytest` 76 passed, `python3.11 -m compileall src scripts` 성공, `./scripts/format.sh` 성공, `./scripts/lint.sh` 성공, `./scripts/test.sh` 성공, `./scripts/verify.sh` 성공.
- 민감정보 패턴 점검 결과 실제 OpenAI API key 형태, raw Authorization header 값, secret-like credential literal은 발견되지 않았다.
- 남은 항목은 MVP 제외 후속 확장이다: BFF adapter, conversation DB/cache adapter, RAG 검색 실행, Query Routing Agent, Answer Generation Agent, Answer Verification Agent, SSE streaming, live evaluation/prompt regression 자동화.

## 2026-05-15 - History Manager Agent feature7_fixture_and_safety_tests

### 작업 목표

- History Manager Agent MVP 전체를 synthetic fixture 기반으로 검증한다.
- CLI stdout/stderr, output JSON, report, failed output의 민감정보 비노출을 테스트로 고정한다.
- 실제 OpenAI live API 호출, BFF/DB/RAG/다른 Agent/SSE 구현은 하지 않고 MVP 범위 경계를 명시한다.

### 테스트 우선 진행

- `ai-agent/history-manager-agent/tests/fixtures/history/*.json` synthetic fixture를 추가했다.
- `ai-agent/history-manager-agent/tests/integration/test_fixture_safety.py`를 먼저 작성했다.
- 최초 fixture/safety 테스트 10개는 feature1-6 구현만으로 통과했다.
- MVP 제외 기능 명시를 고정하는 테스트를 추가했고, `mvp_scope` 미구현으로 `KeyError: 'mvp_scope'` 실패를 확인했다.
- 테스트 케이스에는 fixture 민감정보 검사, follow-up/new-topic/ambiguous full workflow, empty history, long history trimming, malformed history warning, provider failure failed output, CLI redaction, output shape, 원본 history 과다 복제 방지, MVP 제외 기능 marker 검증을 포함했다.

### 구현 내용

- `follow_up_input.json`, `new_topic_input.json`, `ambiguous_input.json`, `empty_history_input.json`, `long_history_input.json`, `malformed_history_input.json`, `provider_failure_input.json` fixture를 추가했다.
- fixture는 모두 synthetic 값만 사용하고 실제 회사 문서, 개인정보, 실제 API key, token, secret 값을 포함하지 않았다.
- `workflow.py`에 `MVP_EXCLUDED_CAPABILITIES` marker를 추가했다.
- success output, failed output, report에 `mvp_scope.excluded_capabilities`를 포함해 BFF API adapter, conversation DB repository, RAG search, Query Routing Agent, Answer Generation Agent, Answer Verification Agent, SSE streaming이 `not_supported_in_mvp`임을 명시했다.
- 기능 확장은 하지 않고 feature1-6 구현을 fixture/safety 관점에서 검증했다.

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

- `python3.11 -m pytest tests/integration/test_fixture_safety.py`: 구현 전 `mvp_scope` 실패 확인 후, 구현 후 11 passed.
- `python3.11 -m pytest`: 76 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### MVP 완료 여부

- History Manager Agent MVP feature1-7 구현과 fixture/safety 검증을 완료했다.
- 남은 항목은 MVP 제외 범위의 후속 확장이다: BFF adapter, conversation DB repository/cache adapter, RAG 검색 실행, Query Routing Agent 구현, Answer Generation Agent 구현, Answer Verification Agent 구현, SSE streaming, live evaluation/prompt regression 자동화.

## 2026-05-15 - History Manager Agent feature6_langgraph_workflow_and_cli

### 작업 목표

- input normalization, LLM classification, context policy, contextualized question, Query Routing input builder를 workflow와 CLI 수동 실행 흐름으로 연결한다.
- LangGraph optional wrapper와 sequential fallback을 제공한다.
- 실제 OpenAI live API 호출 테스트, BFF/DB/RAG/다른 Agent/SSE 구현은 하지 않는다.

### 테스트 우선 진행

- `ai-agent/history-manager-agent/tests/integration/test_workflow_cli.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `history_manager_agent.workflow` package 미구현으로 `ModuleNotFoundError` 실패를 확인했다.
- 전체 suite 실행 중 feature1 시절 CLI skeleton 기대값이 feature6 실제 workflow 동작과 충돌하는 것을 확인하고, CLI workflow 실행 기대값으로 테스트를 조정했다.
- 테스트 케이스에는 fake provider 기반 full workflow node trace, decision/routing/report output 파일 생성, follow-up/new-topic/ambiguous fixture 처리, malformed input safe failed output/report, provider failure failed item/report, CLI 실행, LangGraph fallback, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/history-manager-agent/src/history_manager_agent/workflow.py`를 추가했다.
- `HistoryManagerWorkflowState`, `HistoryManagerWorkflowResult`, `HistoryManagerWorkflow`, `build_history_manager_workflow()`, `run_history_manager_workflow()`를 구현했다.
- node 흐름은 `load_config -> load_input -> normalize_history -> trim_history -> classify_history -> apply_context_policy -> build_contextualized_question -> build_routing_input -> write_output -> write_report` 순서로 기록된다.
- LangGraph는 optional import로만 확인하고, 미설치 환경에서는 `sequential_fallback` 실행 모드로 동작한다.
- success output은 `decision`, `routing_input`, execution trace를 local JSON으로 저장한다.
- report output은 `HistoryReport` schema 기반 count/status/decision과 execution trace를 저장한다.
- malformed input 또는 provider failure는 safe failed output/report와 failed item을 생성한다.
- 빈 history는 workflow에서 `new_topic`으로 처리해 provider 호출 없이 종료한다.
- package CLI `src/history_manager_agent/scripts/run_history_manager.py`를 workflow 실행 진입점으로 확장했다.
- CLI는 `--input`, `--output`, `--report-output`, `--provider`, `--fake-decision`, config 관련 인자를 처리한다.

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

- `python3.11 -m pytest tests/integration/test_workflow_cli.py`: 구현 전 import 실패 확인 후, 구현 후 10 passed.
- `python3.11 -m pytest`: 65 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature7_fixture_and_safety_tests`: synthetic fixture와 end-to-end safety test를 보강하고 MVP 제외 범위를 테스트로 고정한다.

## 2026-05-15 - History Manager Agent feature5_contextualized_question

### 작업 목표

- classification/context policy 결과를 바탕으로 Query Routing Agent가 검색에 사용할 `contextualized_question`을 생성한다.
- History Manager canonical decision과 Query Routing Agent input payload를 생성하는 helper를 구현한다.
- LangGraph workflow, CLI full orchestration, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/history-manager-agent/tests/unit/test_contextualized_question.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `history_manager_agent.question` package 미구현으로 `ModuleNotFoundError` 실패를 확인했다.
- 테스트 케이스에는 follow-up context 반영 재작성, new-topic 원문 유지, ambiguous 보수적 fallback, 빈 rewriter output fallback, 길이 초과 fallback, rewriter 실패 fallback/warning, Query Routing input 생성, History Decision schema 생성, full history 복제 방지, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/history-manager-agent/src/history_manager_agent/question` package를 추가했다.
- `ContextualizedQuestionProvider` protocol과 `FakeQuestionRewriter`를 추가했다.
- `ContextualizedQuestionRequest`와 `ContextualizedQuestionResult`를 구현했다.
- `build_question_result()`는 `follow_up`에서 provider가 없으면 preserved context summary와 current question을 조합한 deterministic 독립 질문을 만든다.
- `new_topic`은 current question 원문을 유지하고, `ambiguous`는 과도한 추론 없이 원문을 유지하며 conservative warning을 추가한다.
- rewriter가 실패하거나 빈 문자열/길이 초과 후보를 반환하면 current question으로 fallback하고 warning을 남긴다.
- `build_history_decision()`은 feature1의 `HistoryDecision` canonical schema를 생성한다.
- `build_query_routing_input()`은 feature1의 `QueryRoutingInput` schema로 Query Routing Agent 입력 payload를 만든다.
- routing metadata에서는 raw/full history 계열 key를 제외해 원본 history 전체가 output으로 복제되지 않도록 했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_contextualized_question.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_contextualized_question.py`: 구현 전 import 실패 확인 후, 구현 후 10 passed.
- `python3.11 -m pytest`: 55 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature6_langgraph_workflow_and_cli`: 지금까지 구현한 loader/normalization/classification/context/question/routing helper를 workflow와 CLI 수동 실행 흐름으로 연결한다.

## 2026-05-15 - History Manager Agent feature4_context_policy

### 작업 목표

- History classification 결과에 따라 context를 보존하거나 초기화하는 deterministic context policy를 구현한다.
- `follow_up`, `new_topic`, `ambiguous` decision별 `preserved_context`, `reset_required`, warnings를 생성한다.
- contextualized question 생성, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/history-manager-agent/tests/unit/test_context_policy.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `history_manager_agent.context` package 미구현으로 `ModuleNotFoundError` 실패를 확인했다.
- 테스트 케이스에는 follow-up reset false/context 보존, trimmed turn_refs, new-topic reset/minimized context, ambiguous minimal context/low confidence warning, full history 복제 방지, summary length guard, empty history safety, normalization warning propagation, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/history-manager-agent/src/history_manager_agent/context` package를 추가했다.
- `ContextPolicyResult`와 `apply_context_policy()`를 구현했다.
- `follow_up`은 feature2의 trimmed non-system history를 기반으로 summary, entities, turn_refs를 생성하고 `reset_required=false`를 반환한다.
- `new_topic`은 previous context를 비우고 `reset_required=true`와 `context_reset` warning을 반환한다.
- `ambiguous`는 최근 1-2개 turn만 보존하고 낮은 confidence일 때 `ambiguous_low_confidence` warning을 유지한다.
- summary는 deterministic short summary로 제한하고, 원본 history 전체를 output에 복제하지 않도록 length guard와 truncation warning을 추가했다.
- entity extraction은 MVP용 deterministic uppercase-token heuristic으로 구현했다.
- normalization warning code는 policy result warnings로 전달한다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_context_policy.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_context_policy.py`: 구현 전 import 실패 확인 후, 구현 후 9 passed.
- `python3.11 -m pytest`: 45 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature5_contextualized_question`: decision별 contextualized question 생성과 Query Routing Agent input builder를 테스트 우선으로 구현한다.

## 2026-05-15 - History Manager Agent feature3_llm_provider_and_classification

### 작업 목표

- History Manager Agent의 LLM provider interface, fake provider, OpenAI provider, classification service를 구현한다.
- `follow_up`, `new_topic`, `ambiguous` label과 confidence/reason parsing을 schema validation으로 고정한다.
- context policy, contextualized question, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/history-manager-agent/tests/unit/test_llm_provider_classification.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `history_manager_agent.llm` package 미구현으로 `ModuleNotFoundError` 실패를 확인했다.
- prompt trimming 테스트에서 feature2 normalized result를 잘못 구성한 테스트 경계를 확인하고, classification service가 이미 trimming된 normalized history를 소비하도록 테스트를 정리했다.
- 테스트 케이스에는 fake provider의 3개 label 분류, confidence/label/schema validation, invalid JSON, prompt에 current question과 trimmed context 포함, raw history 과다 포함 방지, OpenAI provider 외부 key 주입, missing key configuration error, request config 반영, auth/timeout/5xx error 분류, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/history-manager-agent/src/history_manager_agent/llm` package를 추가했다.
- `HistoryLLMProvider` protocol과 `HistoryClassificationRequest`, `LLMProviderResponse`를 정의했다.
- `FakeHistoryLLMProvider`를 추가해 기본 테스트 suite가 실제 OpenAI 네트워크를 호출하지 않도록 했다.
- `OpenAIHistoryLLMProvider`를 추가하고 API key를 config 또는 환경변수 mapping에서만 읽도록 했다.
- OpenAI provider는 injected transport로 테스트 가능하며, 기본 transport는 Chat Completions JSON request를 구성한다.
- provider repr/safe dict와 error message에는 API key, Authorization header, Bearer 값이 포함되지 않게 했다.
- `build_classification_prompt()`, `parse_classification_response()`, `classify_history()`를 구현했다.
- classification service는 feature2의 `to_llm_context_turns()` helper를 재사용해 system turn을 기본 판단 입력에서 제외한다.
- OpenAI auth error는 non-retryable, timeout/5xx/429는 retryable safe error로 분류한다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_llm_provider_classification.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_llm_provider_classification.py`: 구현 전 import 실패 확인 후, 구현 후 15 passed.
- `python3.11 -m pytest`: 36 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature4_context_policy`: decision별 preserved context/reset policy/warnings 처리를 테스트 우선으로 구현한다.

## 2026-05-15 - History Manager Agent feature2_history_input_normalization

### 작업 목표

- BFF가 전달한 conversation history JSON을 History Manager Agent 내부 schema에 맞게 로드, 정규화, 정렬, trimming한다.
- malformed turn은 warning으로 기록하고 가능한 valid turn만 유지한다.
- 실제 OpenAI API 호출, LLM classification, context policy, contextualized question, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/history-manager-agent/tests/unit/test_history_input_normalization.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `history_manager_agent.history` package 미구현으로 `ModuleNotFoundError` 실패를 확인했다.
- 추가로 system role 판단 입력 제한 helper 테스트를 먼저 추가했고, `NormalizedHistoryResult.to_llm_context_turns()` 미구현 실패를 확인했다.
- 테스트 케이스에는 valid JSON loader, malformed JSON loader error, `current_question` validation, role validation, `created_at` sorting/fallback, empty history, malformed turn warning, 최근 N개 turn trimming, `max_context_chars` trimming, count/warning serialization, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/history-manager-agent/src/history_manager_agent/history/normalization.py`를 추가했다.
- `load_history_input()`은 strict schema loader로 유지하고 malformed JSON을 명확한 `HistoryInputLoaderError`로 분류한다.
- `load_and_normalize_history_input()`과 `normalize_history_input_payload()`는 top-level input contract를 검증하면서 malformed turn은 warning으로 처리한다.
- `user`, `assistant`, `system` role을 허용하고 unknown role은 `invalid_role` warning 후 제외한다.
- `created_at` 기준 deterministic sorting과 missing `created_at` fallback을 구현했다.
- `history_window_turns`와 `max_context_chars` 기준 trimming을 구현했다.
- `NormalizedHistoryResult.to_dict()`는 전체 raw input history를 복제하지 않고 normalized history와 counts/warnings만 반환한다.
- `NormalizedHistoryResult.to_llm_context_turns()`는 system turn을 normalized history에는 보존하되 LLM 판단 입력에서는 기본 제외한다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_history_input_normalization.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_history_input_normalization.py`: 구현 전 import 실패와 helper 미구현 실패를 확인 후, 구현 후 12 passed.
- `python3.11 -m pytest`: 21 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature3_llm_provider_and_classification`: provider interface, OpenAI provider, fake provider, classification parsing/retry/safe error 처리를 테스트 우선으로 구현한다.

## 2026-05-15 - History Manager Agent feature1_project_skeleton_and_schema

### 작업 목표

- History Manager Agent의 Python package 기본 구조와 schema/config 기반을 만든다.
- `OPENAI_API_KEY`는 외부 주입 가능한 config field로만 정의하고, safe serialization과 CLI 출력에서 노출하지 않는다.
- 실제 OpenAI API 호출, history normalization, LLM classification, context policy, contextualized question, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/history-manager-agent/tests/unit/test_schema_config.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, package 미구현으로 `ModuleNotFoundError: No module named 'history_manager_agent'` 실패를 확인했다.
- 테스트 케이스에는 config 외부 입력과 key redaction, conversation turn role/schema, History Manager input, History Decision, Query Routing input 호환 schema, label enum 확장성, report schema, 필수값 validation, CLI skeleton input validation을 포함했다.

### 구현 내용

- `ai-agent/history-manager-agent/pyproject.toml`을 추가했다.
- `src/history_manager_agent` package 기본 구조를 추가했다.
- `HistoryManagerConfig`를 추가하고 `history_window_turns`, `max_context_chars`, model, temperature, timeout, retry, optional `openai_api_key` 검증 및 safe serialization을 구현했다.
- conversation turn, History Manager input, preserved context, History Decision, Query Routing input, warning, failed item, History Report schema를 추가했다.
- `HistoryDecisionLabel`은 `follow_up`, `new_topic`, `ambiguous`를 지원하고 `from_value()`로 unknown-safe 확장 경로를 제공한다.
- `scripts/run_history_manager.py`와 package CLI module은 config/input validation skeleton까지만 수행하고 OpenAI provider나 workflow는 실행하지 않는다.
- `.env.example`은 placeholder 변수명만 포함하고 실제 key 값은 포함하지 않았다.
- `tests/fixtures`, `data/input`, `data/output`, `data/reports`, `data/failed` placeholder 디렉토리를 추가했다.

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

- `python3.11 -m pytest tests/unit/test_schema_config.py`: 구현 전 `ModuleNotFoundError` 실패 확인 후, 구현 후 9 passed.
- `python3.11 -m pytest`: 9 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 출력상 루트 스크립트는 agent 하위 pytest 상세를 표시하지 않으므로 agent 디렉토리에서 `python3.11 -m pytest`를 별도로 실행했다.
- `./scripts/verify.sh`: 성공.

### 남은 작업

- `feature2_history_input_normalization`: input JSON loader, turn normalization, role validation, sorting, warning, trimming 테스트 우선 구현.

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

## 2026-05-15 - Query Routing Agent feature3_intent_classification_provider

### 작업 목표

- Query Routing Agent의 intent classification provider 계층을 구현한다.
- `RoutingLLMProvider` interface, fake provider, OpenAI provider adapter, routing prompt builder, LLM output validation/classification service를 추가한다.
- 기본 테스트는 fake provider와 injected transport만 사용하고 실제 OpenAI live API 호출은 수행하지 않는다.
- query rewrite, metadata filter builder, pool weight builder, routing decision builder, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/query-routing-agent/tests/unit/test_intent_classification_provider.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `query_routing_agent.llm` 모듈 import 실패를 확인했다.
- 테스트 케이스에는 supported intent 분류, invalid intent의 `unknown` fallback, confidence validation, invalid JSON/schema mismatch safe error, prompt context 제한, OpenAI provider 외부 key 주입, config 반영, auth/non-retryable error, timeout/5xx retryable error, 민감정보 비노출을 포함했다.

### 구현 내용

- `ai-agent/query-routing-agent/src/query_routing_agent/llm/providers.py`를 추가/보강했다.
- `RoutingLLMProvider`, `FakeRoutingLLMProvider`, `OpenAIRoutingLLMProvider`, `RoutingClassificationRequest`, provider safe error 타입을 구현했다.
- OpenAI provider는 config 또는 environment mapping으로만 API key를 주입받고, `repr`, `to_safe_dict`, error message에 key/Authorization marker를 노출하지 않도록 했다.
- `ai-agent/query-routing-agent/src/query_routing_agent/llm/classification.py`를 추가/보강했다.
- routing prompt builder, intent classification result, LLM JSON parsing, confidence/reason validation, invalid intent `unknown` fallback, future hint 보존 구조를 구현했다.
- `ai-agent/query-routing-agent/src/query_routing_agent/llm/__init__.py`에서 feature3 public API를 export했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_intent_classification_provider.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_intent_classification_provider.py`: 최초 import 실패 확인 후 18 passed.
- `python3.11 -m pytest`: 47 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature4_query_rewrite`: expanded query parsing, query count/length/dedup 정책, preserved context 기반 enrichment.
- `feature5_filter_and_pool_weight_builder` 이후 항목은 후속 세션에서 진행한다.

## 2026-05-15 - Query Routing Agent feature4_query_rewrite

### 작업 목표

- Query Routing Agent가 검색에 사용할 expanded query 목록을 생성, 검증, 정규화한다.
- LLM/fake provider output의 `expanded_queries` hint를 사용하되, 없거나 invalid하면 deterministic fallback을 적용한다.
- 기본 3개, 최대 5개, 중복/빈 query 제거, preserved context 기반 enrichment, intent별 rewrite hint, 긴 query 제한, 민감정보 비노출을 보장한다.
- metadata filter builder, pool weight builder, routing decision builder, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/query-routing-agent/tests/unit/test_query_rewrite.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `query_routing_agent.routing.rewrite_queries` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 LLM expanded query 정규화, 기본 3개 생성, 최대 5개 trim, 중복/빈 값 제거, 전부 invalid 시 원본 fallback, preserved context enrichment, intent별 hint, 긴 query warning, raw history 및 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/query-routing-agent/src/query_routing_agent/routing/query_rewrite.py`를 추가했다.
- `QueryRewriteResult`와 `rewrite_queries()`를 구현했다.
- classification result의 `raw_hints.expanded_queries`를 정규화하고, LLM hint가 없거나 정규화 후 비어 있으면 deterministic fallback을 생성한다.
- fallback은 원본 query를 첫 번째 query로 유지하고 preserved context entity를 제한적으로 보강한다.
- intent별로 `incident_response`, `operations_guide`, `policy_procedure`, `history_lookup`, `unknown`에 맞는 검색 hint를 추가한다.
- query는 whitespace 정규화, 중복 제거, 최대 길이 제한, 민감 marker 제거를 거친다.
- `ai-agent/query-routing-agent/src/query_routing_agent/routing/__init__.py`에서 feature4 public API를 export했다.
- feature1-3 공개 API는 불필요하게 변경하지 않았다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_query_rewrite.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_query_rewrite.py`: 최초 import 실패 확인 후 8 passed.
- `python3.11 -m pytest`: 55 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature5_filter_and_pool_weight_builder`: metadata/ACL filter builder, task prompt type mapping, intent별 pool weight 및 weight normalization.
- `feature6_routing_decision_builder` 이후 항목은 후속 세션에서 진행한다.

## 2026-05-15 - Query Routing Agent feature5_filter_and_pool_weight_builder

### 작업 목표

- Query Routing Agent가 intent와 routing input metadata를 기반으로 canonical metadata filter, ACL filter payload, Answer Generation용 task prompt type, Multi-Pool weight를 생성한다.
- ACL은 `user_id`, `groups`를 filter payload로 전달하는 수준으로만 처리하고 권한 판정/enforcement는 수행하지 않는다.
- routing decision builder, search request payload builder, LangGraph workflow, local output pipeline은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/query-routing-agent/tests/unit/test_filter_and_pool_weight_builder.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `build_filter_and_pool_weights` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 metadata `space_keys`/labels/document_types/source_types/date_range/attachment_required 매핑, ACL user/groups 전달, missing ACL groups warning, invalid metadata safe fallback, intent별 task prompt type, intent별 pool weight, weight normalization/default fallback, 민감정보 비노출 검증을 포함했다.

### 구현 내용

- `ai-agent/query-routing-agent/src/query_routing_agent/routing/filter_builder.py`를 추가했다.
- `FilterAndWeightResult`, `build_filter_and_pool_weights()`, `build_metadata_filter()`, `map_task_prompt_type()`, `build_pool_weights()`, `normalize_pool_weights()`를 구현했다.
- metadata filter는 `MetadataFilter`, `DateRangeFilter`, `AclFilter` canonical schema를 재사용한다.
- ACL payload는 `user_id`, `groups`만 포함하고 `allowed`/`denied` 같은 enforcement 결과를 만들지 않는다.
- intent별 task prompt type mapping은 `incident_response -> timeline`, `operations_guide -> step_by_step`, `policy_procedure -> evidence_first`, `history_lookup -> history_summary`, `unknown -> general`로 구현했다.
- intent별 pool weight는 명세의 title/content/label 비율을 적용하고, raw weight는 합계 1.0으로 normalize한다.
- 음수, all-zero, invalid weight는 default weight로 fallback하고 warning을 남긴다.
- metadata/filter/weight 결과와 warning에서 API key, Authorization, secret-like marker를 제거한다.
- `ai-agent/query-routing-agent/src/query_routing_agent/routing/__init__.py`에서 feature5 public API를 export했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_filter_and_pool_weight_builder.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_filter_and_pool_weight_builder.py`: 최초 import 실패 확인 후 18 passed.
- `python3.11 -m pytest`: 73 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature6_routing_decision_builder`: normalized input, classification, rewritten queries, filters, weights를 routing decision/search request payload로 조립한다.
- `feature7_langgraph_workflow_and_cli` 이후 항목은 후속 세션에서 진행한다.

## 2026-05-15 - Query Routing Agent feature6_routing_decision_builder

### 작업 목표

- feature1-5 산출물인 normalized input, intent classification, expanded queries, metadata filters, task prompt type, pool weights를 조립해 canonical `RoutingDecision`과 `SearchRequestPayload`를 생성한다.
- routing report, failed item helper, local JSON writer를 구현한다.
- 실제 Qdrant 검색, embedding 생성, Cross-Encoder reranking, LangGraph workflow, CLI full orchestration은 구현하지 않는다.

### 테스트 우선 진행

- `ai-agent/query-routing-agent/tests/unit/test_routing_decision_builder.py`를 먼저 작성했다.
- 최초 테스트 실행 결과, `build_routing_decision` 미구현으로 import 실패를 확인했다.
- 테스트 케이스에는 canonical routing decision 필드, deterministic routing_id, warning 병합, search request payload, ACL filter 전달, Answer Generation 준비 필드 validation, report count, failed item shape, local JSON writer, output redaction 검증을 포함했다.

### 구현 내용

- `ai-agent/query-routing-agent/src/query_routing_agent/routing/decision_builder.py`를 추가했다.
- `build_routing_id()`는 conversation/user/query 기반 deterministic routing id를 생성한다.
- `build_routing_decision()`은 normalized input, classification, query rewrite result, filter/weight result를 `RoutingDecision` schema로 조립한다.
- `build_search_request_payload()`는 `RoutingDecision`에서 RAG search request payload만 생성하며 실제 검색 실행 정보는 포함하지 않는다.
- `build_routing_report()`는 status, intent, expanded query count, warning count를 계산한다.
- `make_failed_item()`은 safe failed item schema를 생성한다.
- `write_routing_outputs()`는 `routing_decision.json`, `search_request.json`, `routing_report.json`, `failed_items.json`을 생성하고 저장 디렉토리를 자동 생성한다.
- local writer는 API key, Authorization, token, secret-like marker를 파일 출력에서 redaction한다.
- `ai-agent/query-routing-agent/src/query_routing_agent/routing/__init__.py`에서 feature6 public API를 export했다.

### 검증 명령

```bash
python3.11 -m pytest tests/unit/test_routing_decision_builder.py
python3.11 -m pytest
python3.11 -m compileall src scripts
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

### 검증 결과

- `python3.11 -m pytest tests/unit/test_routing_decision_builder.py`: 최초 import 실패 확인 후 9 passed.
- `python3.11 -m pytest`: 82 passed.
- `python3.11 -m compileall src scripts`: 성공.
- `./scripts/format.sh`: 성공.
- `./scripts/lint.sh`: 성공.
- `./scripts/test.sh`: 성공. 루트 스크립트 출력은 agent 하위 pytest 상세를 표시하지 않아 agent 디렉토리 pytest 결과를 별도로 확인했다.
- `./scripts/verify.sh`: 성공. 위와 동일하게 agent 디렉토리 pytest 결과를 별도로 확인했다.

### 남은 작업

- `feature7_langgraph_workflow_and_cli`: feature1-6 service/helper를 LangGraph workflow와 CLI 수동 실행 흐름으로 연결한다.
- `feature8_fixture_and_safety_tests`: fixture 기반 end-to-end style safety 검증을 보강한다.
