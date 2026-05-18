# Answer Generation Agent

공통 규칙은 루트 `AGENTS.md`와 `ai-agent/AGENTS.md`를 따른다. 이 문서는 Answer Generation Agent 고유 개발 명세만 정의한다.

---

## Agent 목표

Query Routing Agent의 routing decision과 RAG Pipeline이 선별한 Top-5 context를 입력으로 받아, 의도별 task prompt를 조립하고 컨텍스트에 근거한 자연어 답변을 생성한다.

Answer Generation Agent는 RAG 파이프라인에서 Query Routing 및 검색/재순위화 이후 단계에 위치한다. 출력은 Answer Verification Agent가 바로 소비할 수 있어야 한다.

초기 MVP는 **Query Routing Agent output과 Top-5 context fixture/input을 받아 citation-aware answer output을 생성하는 CLI 기반 workflow**를 구현한다.

---

## MVP 범위

포함:

- CLI 수동 실행
- LangGraph workflow
- local JSON input/output
- Query Routing Agent output 입력 처리
- Top-5 context 입력 처리
- OpenAI API 직접 호출 provider 구현
- `OPENAI_API_KEY` 외부 주입
- 테스트용 fake LLM provider
- task prompt type별 prompt template 조립
- 컨텍스트 기반 답변 생성
- context insufficiency 판단
- sentence-level citation schema 생성
- source list 생성
- Answer Verification Agent 입력 호환 output 생성
- streaming interface 또는 stream chunk schema 준비
- fixture 기반 테스트
- token/API key 비노출 safety test

제외:

- 실제 Qdrant 검색 실행
- Dense/Sparse embedding 생성
- Cross-Encoder reranking 실행
- Query Routing Agent 구현
- Answer Verification Agent 직접 호출
- 실제 SSE streaming 전송
- BFF API 직접 호출
- DB 직접 조회/저장
- QCA 저장
- feedback 저장
- UI response formatting
- production prompt tuning 자동화

후속 확장:

- RAG Pipeline search/rerank adapter
- 실제 SSE streaming adapter
- Answer Verification Agent 호출 adapter
- model routing policy 고도화
- response formatter 연동
- QCA dataset 저장 adapter
- feedback pipeline 연동
- live evaluation set 기반 prompt regression test

---

## 책임 범위

책임진다:

- generation input schema 검증
- Query Routing decision 입력 검증
- Top-5 context 입력 검증
- task prompt type별 prompt template 조립
- OpenAI LLM provider adapter
- fake LLM provider
- context-aware answer generation
- insufficient context handling
- sentence-level citation mapping
- source list 생성
- answer output 생성
- stream chunk interface/schema 정의
- LangGraph workflow와 CLI
- local JSON output
- fixture/safety tests

책임지지 않는다:

- Vector DB 검색
- Cross-Encoder reranking
- ACL 권한 판정
- Query Routing Agent 구현
- Answer Verification Agent 구현 또는 호출
- SSE transport 실제 전송
- BFF/DB 직접 연동
- UI rendering
- feedback/QCA 저장

---

## 실행 모델

MVP는 CLI 기반 단일 answer generation job이다.

```bash
python ai-agent/answer-generation-agent/scripts/run_answer_generation.py \
  --input ai-agent/answer-generation-agent/tests/fixtures/generation_input.json \
  --output ai-agent/answer-generation-agent/data/output/generated_answer.json
```

실행 전 `OPENAI_API_KEY`는 로컬 shell environment, 로컬 `.env`, 또는 런타임 secret provider로 주입한다.

OpenAI API key 처리 방식:

- 개발자는 로컬에서 `.env` 또는 shell environment로 `OPENAI_API_KEY`를 주입할 수 있다.
- 실제 `.env` 파일은 생성하거나 커밋하지 않는다.
- 필요한 경우 `.env.example`만 생성하며 실제 key 값은 포함하지 않는다.
- CLI 인자로 raw API key를 직접 받는 방식은 shell history/process 노출 위험이 있으므로 기본 방식으로 사용하지 않는다.
- code, fixture, log, output, docs 예시에 실제 API key를 저장하지 않는다.

MVP 기본값:

```json
{
  "default_model": "configurable",
  "fallback_model": "configurable",
  "temperature": 0.2,
  "timeout_seconds": 45,
  "max_retries": 2,
  "max_contexts": 5,
  "max_answer_sentences": 8,
  "streaming_supported": false
}
```

모델명은 config/env로 교체 가능해야 한다. 기획서상 GPT-4o / GPT-4o-mini 동적 라우팅을 고려하되, MVP에서는 provider interface와 simple model policy만 준비하고 복잡도 기반 동적 모델 선택은 후속 확장으로 둔다.

---

## 외부 연동 계약

### Query Routing + Top Context Input Contract

MVP에서는 Query Routing Agent output과 RAG Pipeline/Cross-Encoder가 이미 선별한 Top-5 context를 함께 입력받는다고 가정한다.

```json
{
  "conversation_id": "string",
  "user_id": "string",
  "routing_decision": {
    "routing_id": "string",
    "original_question": "string",
    "query": "string",
    "intent": "incident_response|operations_guide|policy_procedure|history_lookup|unknown",
    "task_prompt_type": "timeline|step_by_step|evidence_first|history_summary|general",
    "expanded_queries": [],
    "metadata_filters": {},
    "pool_weights": {},
    "confidence": 0.0,
    "warnings": []
  },
  "search_results": {
    "top_contexts": []
  },
  "metadata": {
    "locale": "ko-KR",
    "timezone": "Asia/Seoul"
  }
}
```

규칙:

- `routing_decision`은 Query Routing Agent의 output과 호환되어야 한다.
- `top_contexts`는 검색/재순위화가 완료된 Top-5 context로 간주한다.
- Top context가 5개를 초과하면 `rerank_score` 또는 입력 순서를 기준으로 상위 5개만 사용한다.
- 검색과 reranking은 MVP에서 수행하지 않는다.
- 입력 context가 비어 있으면 최대한 답변을 시도하지 않고 `insufficient_context`로 처리한다.

### Top Context Schema

```json
{
  "context_id": "string",
  "document_id": "string",
  "chunk_id": "string",
  "title": "string",
  "space_key": "string",
  "source_url": "string",
  "content": "string",
  "score": 0.0,
  "rerank_score": 0.0,
  "metadata": {
    "page_id": "string",
    "attachment_filename": null,
    "last_modified_at": "ISO-8601"
  }
}
```

규칙:

- `context_id`는 sentence citation의 기본 참조 단위다.
- `content`가 비어 있는 context는 warning 후 제외한다.
- source metadata는 답변 출처 카드와 Verification Agent 검증에 사용할 수 있어야 한다.
- 실제 회사 문서나 개인정보는 fixture에 포함하지 않는다.

### LLM Provider Contract

MVP에서 실제 OpenAI API 호출 provider를 구현한다. 단, 테스트는 fake provider를 기본으로 사용한다.

```text
AnswerLLMProvider
  -> generate_answer(input) -> AnswerLLMResult
```

구현 원칙:

- provider interface와 OpenAI provider 구현을 분리한다.
- API key는 환경변수 또는 secret provider에서만 읽는다.
- OpenAI client error는 safe error로 변환한다.
- prompt, request, response logging에서 API key와 Authorization header를 제거한다.
- live OpenAI 호출 테스트는 기본 test suite에 포함하지 않는다.
- 실제 API smoke test가 필요하면 별도 opt-in flag 또는 별도 script로 분리한다.

---

## Task Prompt 기준

Query Routing Agent가 생성한 `task_prompt_type`을 그대로 사용한다.

| Task Prompt Type | 목적 | 답변 형식 |
| --- | --- | --- |
| `timeline` | 장애 대응 | 상황 요약, 시간/단계 흐름, 조치 순서, 근거 |
| `step_by_step` | 운영 가이드 | 단계별 절차, 주의사항, 확인 방법 |
| `evidence_first` | 정책·절차 | 근거 문서/조항 우선, 결론, 예외/주의사항 |
| `history_summary` | 이력 조회 | 변경/처리 이력 요약, 날짜/대상/결과 |
| `general` | 일반 질문 | 간결한 직접 답변, 근거 출처 |

공통 system prompt 규칙:

- 제공된 context 밖의 사실을 단정하지 않는다.
- 가능한 한 입력 context 안에서 답변을 구성한다.
- 근거가 부족한 부분은 추정하지 않고 제한 사항으로 표시한다.
- 모든 핵심 문장에는 citation을 연결한다.
- citation은 context id 기반으로 구조화한다.
- 사용자가 원본을 확인할 수 있도록 source metadata를 보존한다.

---

## Context Sufficiency 기준

MVP 기본 정책:

| 조건 | 처리 |
| --- | --- |
| Top context가 없음 | `answer_status=insufficient_context` |
| context는 있으나 질문과 거의 무관함 | 가능한 답변 대신 근거 부족 안내 |
| 일부 근거만 있음 | 근거가 있는 범위에서 최대한 답변하고 warning 기록 |
| 충분한 근거가 있음 | `answer_status=success` |

중요:

- 무조건적으로 "모른다"고 답하지 않는다.
- 입력 context가 존재하면 그 범위 안에서 최대한 유용한 답변을 생성한다.
- 단, context에 없는 절차/수치/정책을 새로 만들어내지 않는다.
- 부족한 부분은 `warnings`와 `unsupported_gaps`에 기록한다.

---

## Citation 기준

문장별 citation schema:

```json
{
  "sentence_id": "s1",
  "text": "IAM 정책 변경 전 영향 범위를 확인해야 합니다.",
  "citations": ["ctx-001"]
}
```

source list schema:

```json
{
  "source_id": "ctx-001",
  "context_id": "ctx-001",
  "document_id": "doc-001",
  "chunk_id": "chunk-001",
  "title": "IAM 운영 가이드",
  "source_url": "https://example.invalid/confluence/pages/123",
  "space_key": "OPS",
  "page_id": "123",
  "attachment_filename": null,
  "score": 0.0,
  "rerank_score": 0.0
}
```

규칙:

- citation은 Top context의 `context_id`만 참조한다.
- 존재하지 않는 context id를 citation으로 만들지 않는다.
- citation이 없는 핵심 문장은 warning 대상으로 남긴다.
- Answer Verification Agent가 sentence별 citation을 검증할 수 있어야 한다.

---

## Streaming 기준

MVP에서는 실제 SSE streaming을 구현하지 않는다.

대신 후속 통합을 위해 stream chunk schema/interface만 준비한다.

```json
{
  "generation_id": "string",
  "chunk_index": 0,
  "chunk_type": "text|citation|done|error",
  "content": "string",
  "metadata": {}
}
```

규칙:

- `streaming_supported`는 MVP에서 기본 `false`다.
- 실제 SSE 전송은 BFF/통합 단계에서 구현한다.
- Answer output은 향후 streaming으로 분해 가능해야 한다.

---

## Workflow

```text
load_config
  -> load_input
  -> normalize_generation_input
  -> validate_top_contexts
  -> assess_context_sufficiency
  -> build_task_prompt
  -> generate_answer
  -> map_sentence_citations
  -> build_answer_output
  -> write_output
  -> write_report
```

핵심 규칙:

- 입력 schema validation은 LLM 호출 전 수행한다.
- prompt builder는 task prompt type별로 분리한다.
- LLM provider 장애 시 safe failure를 반환하고 raw exception에 secret을 포함하지 않는다.
- context가 부족해도 가능한 근거 범위 내 답변 생성을 우선하되, 근거 없는 단정은 금지한다.
- 실제 검색, reranking, verification 호출은 수행하지 않는다.

---

## Canonical Schema

### Generation Input

```json
{
  "conversation_id": "string",
  "user_id": "string",
  "routing_decision": {},
  "search_results": {
    "top_contexts": []
  },
  "metadata": {}
}
```

### Generated Sentence

```json
{
  "sentence_id": "s1",
  "text": "string",
  "citations": ["ctx-001"],
  "citation_required": true
}
```

### Generated Source

```json
{
  "source_id": "ctx-001",
  "context_id": "ctx-001",
  "document_id": "string",
  "chunk_id": "string",
  "title": "string",
  "source_url": "string",
  "space_key": "string",
  "page_id": "string",
  "attachment_filename": null,
  "score": 0.0,
  "rerank_score": 0.0
}
```

### Answer Output

Answer Verification Agent가 바로 소비할 수 있는 output이다.

```json
{
  "generation_id": "string",
  "conversation_id": "string",
  "user_id": "string",
  "answer_status": "success|insufficient_context|failed",
  "answer": "string",
  "sentences": [],
  "sources": [],
  "used_context_ids": [],
  "routing": {
    "routing_id": "string",
    "intent": "string",
    "task_prompt_type": "string"
  },
  "model": "string",
  "confidence": 0.0,
  "insufficient_context": false,
  "unsupported_gaps": [],
  "streaming": {
    "streaming_supported": false,
    "stream_chunks": []
  },
  "warnings": []
}
```

### Generation Report

```json
{
  "job_id": "string",
  "generation_id": "string",
  "conversation_id": "string",
  "status": "success|partial_success|failed",
  "answer_status": "success|insufficient_context|failed",
  "context_count": 0,
  "used_context_count": 0,
  "sentence_count": 0,
  "citation_count": 0,
  "warnings_count": 0,
  "created_at": "ISO-8601"
}
```

---

## Error Handling

| 상황 | 처리 |
| --- | --- |
| input JSON 없음 | failed, non-retryable |
| malformed JSON | failed, non-retryable |
| routing_decision 없음 | failed, non-retryable |
| query/task_prompt_type 없음 | failed, non-retryable |
| top_contexts 없음 | `insufficient_context` |
| context content 비어 있음 | warning 후 제외 |
| context 5개 초과 | 상위 5개로 trim |
| unsupported task_prompt_type | `general` fallback |
| LLM invalid JSON | fallback 또는 failed item |
| LLM answer에 citation 없음 | citation mapping fallback 또는 warning |
| citation이 없는 context id 참조 | warning 후 제거 |
| OpenAI API key 없음 | provider configuration error |
| OpenAI timeout/5xx | retryable safe error |
| OpenAI auth error | non-retryable auth failure |

기본 권장값:

```json
{
  "max_contexts": 5,
  "max_answer_sentences": 8,
  "max_retries": 2,
  "timeout_seconds": 45,
  "temperature": 0.2
}
```

---

## 권장 구현 구조

```text
ai-agent/answer-generation-agent/
  answer-generation-agent.md
  src/answer_generation_agent/
    app/
    graph/
    generation/
    prompts/
    llm/
    citations/
    streaming/
    storage/
    schemas/
    config/
    utils/
  tests/
    fixtures/
    unit/
    integration/
  data/
    input/
    output/
    reports/
    failed/
  scripts/
```

---

## Feature Breakdown

### feature1_project_skeleton_and_schema

- package 구조 생성
- `pyproject.toml` 설정
- config schema 정의
- generation input schema 정의
- top context schema 정의
- generated sentence/source schema 정의
- answer output schema 정의
- stream chunk schema 정의
- generation report schema 정의
- CLI skeleton 작성
- schema/config 단위 테스트 작성

### feature2_generation_input_normalization

- Query Routing output + Top-5 context loader 구현
- generation input validation 구현
- routing decision normalization 구현
- top context normalization 구현
- context 5개 제한 구현
- empty/invalid context warning 처리
- unsupported task prompt type fallback 구현
- normalization 테스트 작성

### feature3_prompt_template_builder

- task prompt type별 prompt template 구현
- `timeline` prompt 구현
- `step_by_step` prompt 구현
- `evidence_first` prompt 구현
- `history_summary` prompt 구현
- `general` prompt 구현
- context-only answer rule 포함
- citation instruction 포함
- prompt builder 테스트 작성

### feature4_llm_provider_and_answer_generation

- LLM provider interface 정의
- OpenAI provider 구현
- fake LLM provider 구현
- answer generation service 구현
- context sufficiency handling 구현
- model policy interface 구현
- safe provider error 처리 구현
- provider/generation 테스트 작성

### feature5_citation_mapping

- LLM answer sentence parsing 구현
- citation extraction 구현
- context id validation 구현
- source list builder 구현
- missing citation warning 구현
- citation mapping fallback 구현
- citation 테스트 작성

### feature6_answer_output_builder

- Answer Verification Agent 입력 호환 output 생성
- answer status 결정
- confidence/warnings/unsupported_gaps 병합
- streaming chunk schema/interface 생성
- generation report helper 구현
- local JSON writer 구현
- output builder 테스트 작성

### feature7_langgraph_workflow_and_cli

- LangGraph workflow 구성
- sequential fallback 구성
- CLI 실행 스크립트 구현
- local output 저장
- report 저장
- fake provider 기반 workflow integration test 작성

### feature8_fixture_and_safety_tests

- synthetic timeline fixture 작성
- synthetic step-by-step fixture 작성
- synthetic evidence-first fixture 작성
- synthetic history-summary fixture 작성
- insufficient context fixture 작성
- malformed input/provider failure fixture 작성
- OpenAI API key/token safety 테스트
- output schema 검증
- boundary test 작성

---

## 수용 기준

- CLI로 Answer Generation workflow를 실행할 수 있다.
- Query Routing Agent output과 Top-5 context JSON을 입력으로 처리할 수 있다.
- OpenAI API key는 외부 주입으로만 사용한다.
- API key가 코드, fixture, log, output file에 저장되지 않는다.
- 테스트는 기본적으로 fake LLM provider를 사용한다.
- 실제 OpenAI provider 구현은 provider interface 뒤에 분리되어 있다.
- 직접 Qdrant 검색, embedding, Cross-Encoder reranking을 수행하지 않는다.
- task prompt type별 prompt가 생성된다.
- context 밖의 사실을 단정하지 않는 prompt rule이 포함된다.
- context가 부족하면 `insufficient_context`를 표시하되, 가능한 근거 범위 내 답변 생성을 우선한다.
- 문장별 citation과 source list가 생성된다.
- Answer Verification Agent가 소비 가능한 output schema가 생성된다.
- 실제 SSE streaming은 수행하지 않고 stream chunk interface/schema만 제공한다.
- LangGraph workflow가 전체 단계를 orchestration한다.
- fixture 기반 integration test가 통과한다.

---

## 후속 개발 메모

- 실제 RAG Pipeline search/rerank API가 확정되면 input adapter 또는 workflow 상위 단계에서 연결한다.
- Answer Verification Agent가 완성되면 output schema와 sentence/citation field 호환성을 검증한다.
- SSE streaming 통합 시 `streaming/` 하위 adapter를 추가하고 BFF transport와 연결한다.
- model routing은 provider 내부가 아니라 model policy/config 계층에서 처리한다.
- live OpenAI smoke test는 기본 CI에서 제외하고 명시적 opt-in으로만 실행한다.
