# Answer Verification Agent

공통 규칙은 루트 `AGENTS.md`와 `ai-agent/AGENTS.md`를 따른다. 이 문서는 Answer Verification Agent 고유 개발 명세만 정의한다.

---

## Agent 목표

Answer Generation Agent가 생성한 답변과 sentence-level citation을 Top-5 context 원문에 대조하여, 답변이 제공된 근거에 의해 지지되는지 검증한다.

Answer Verification Agent는 RAG 파이프라인의 마지막 Agent다. 출력은 UI warning badge, 응답 포맷터, QCA 데이터셋, 후속 재생성 피드백 루프가 소비할 수 있어야 한다.

초기 MVP는 **Answer Generation Agent output과 Top-5 context fixture/input을 받아 rule-based verifier와 fake/OpenAI LLM evaluator 구조로 문장별 검증 결과, 전체 검증 결과, QCA local output, 재생성 권고 payload를 생성하는 CLI 기반 workflow**를 구현한다.

---

## MVP 범위

포함:

- CLI 수동 실행
- LangGraph workflow
- local JSON input/output
- Answer Generation Agent output 입력 처리
- Top-5 context 입력 처리
- rule-based verification 실제 구현
- suspicious sentence selector 구현
- OpenAI API 직접 호출 evaluator provider 구현
- `OPENAI_API_KEY` 외부 주입
- 테스트용 fake evaluator provider
- sentence-level citation validation
- 핵심 token/entity 존재 검증
- 숫자/날짜/버전/수치 존재 검증
- citation coverage 계산
- `PASS`, `SUPPORTED`, `UNSUPPORTED`, `LOW_CONFIDENCE` label 생성
- UI warning metadata 생성
- QCA local JSON/JSONL output 생성
- regeneration recommendation 생성
- fixture 기반 테스트
- token/API key 비노출 safety test

제외:

- Answer Generation Agent 직접 재호출
- 실제 재생성 loop 실행
- BFF API 직접 호출
- DB 직접 저장
- QCA DB 저장
- feedback DB 저장
- UI 렌더링
- 실제 SSE streaming 전송
- 실제 OpenAI live test
- production evaluation dashboard

후속 확장:

- Answer Generation Agent regeneration adapter
- LangGraph feedback loop
- QCA DB repository adapter
- feedback pipeline 연동
- UI warning badge API 연동
- evaluator model routing
- all-sentence LLM evaluation mode
- rule set configuration 관리
- live evaluation / regression dashboard

---

## 책임 범위

책임진다:

- verification input schema 검증
- Answer Generation output 검증
- Top context 원문 검증
- sentence/citation parsing
- rule-based verification
- suspicious sentence selection
- LLM evaluator provider adapter
- fake evaluator provider
- sentence-level verification result 생성
- overall verification result 생성
- citation coverage 계산
- unsupported claims 생성
- UI warning metadata 생성
- QCA local output 생성
- regeneration recommendation 생성
- LangGraph workflow와 CLI
- local JSON output
- fixture/safety tests

책임지지 않는다:

- 답변 재생성 직접 실행
- Answer Generation Agent 구현 또는 직접 호출
- BFF/DB 직접 연동
- UI rendering
- 실제 QCA DB 저장
- feedback 저장
- SSE transport

---

## 실행 모델

MVP는 CLI 기반 단일 answer verification job이다.

```bash
python ai-agent/answer-verification-agent/scripts/run_answer_verification.py \
  --input ai-agent/answer-verification-agent/tests/fixtures/verification_input.json \
  --output ai-agent/answer-verification-agent/data/output/verification_result.json
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
  "default_evaluator_model": "configurable",
  "temperature": 0.0,
  "timeout_seconds": 30,
  "max_retries": 2,
  "evaluate_suspicious_only": true,
  "min_overall_score": 0.7,
  "min_sentence_score": 0.6,
  "qca_output_enabled": true
}
```

기획서상 LLM evaluator는 GPT-4o-mini 계열을 우선 고려한다. 모델명은 config/env로 교체 가능해야 하며, MVP 테스트는 fake evaluator를 기본으로 사용한다.

---

## 외부 연동 계약

### Verification Input Contract

MVP에서는 Answer Generation Agent output과 검증에 필요한 Top-5 context 원문을 함께 입력받는다고 가정한다.

```json
{
  "conversation_id": "string",
  "user_id": "string",
  "answer_output": {
    "generation_id": "string",
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
    "warnings": []
  },
  "contexts": [],
  "metadata": {
    "locale": "ko-KR",
    "timezone": "Asia/Seoul"
  }
}
```

규칙:

- `answer_output`은 Answer Generation Agent output과 호환되어야 한다.
- `contexts`는 답변 생성에 사용된 Top-5 context 원문이다.
- citation은 `contexts[].context_id`만 참조할 수 있다.
- Answer Generation output의 `sentences`가 비어 있으면 sentence parser가 answer text에서 문장을 재구성할 수 있다.
- `answer_status=insufficient_context`이면 검증은 실패가 아니라 low-confidence 계열로 처리한다.

### Context Schema

Answer Generation Agent의 Top Context schema와 호환된다.

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

### LLM Evaluator Provider Contract

MVP에서 실제 OpenAI API 호출 evaluator provider를 구현한다. 단, 테스트는 fake evaluator를 기본으로 사용한다.

```text
AnswerEvaluatorProvider
  -> evaluate_sentence(input) -> SentenceEvaluation
```

구현 원칙:

- provider interface와 OpenAI provider 구현을 분리한다.
- API key는 환경변수 또는 secret provider에서만 읽는다.
- 기본 테스트 suite는 fake evaluator만 사용한다.
- live OpenAI 호출 테스트는 기본 test suite에 포함하지 않는다.
- 실제 API smoke test가 필요하면 별도 opt-in flag 또는 별도 script로 분리한다.
- MVP 기본 모드는 suspicious sentence만 LLM evaluator를 호출한다.
- 후속 확장에서는 all-sentence evaluation mode를 설정으로 허용할 수 있어야 한다.

---

## Verification Label 기준

### Overall Label

| Label | 의미 |
| --- | --- |
| `PASS` | 전체 답변이 충분한 근거와 citation을 갖고 검증 통과 |
| `SUPPORTED` | 대부분의 핵심 문장이 context에 의해 지지됨 |
| `UNSUPPORTED` | 핵심 주장 중 context 근거가 없거나 충돌하는 내용이 있음 |
| `LOW_CONFIDENCE` | 근거가 부족하거나 검증 신뢰도가 낮아 경고가 필요 |

### Sentence Label

| Label | 의미 |
| --- | --- |
| `SUPPORTED` | 해당 문장이 citation/context에 의해 지지됨 |
| `UNSUPPORTED` | 해당 문장이 citation/context에 의해 지지되지 않음 |
| `LOW_CONFIDENCE` | 일부 근거가 있으나 충분하지 않거나 애매함 |
| `NOT_CHECKED` | 오류, insufficient context, 또는 정책상 검증 생략 |

확장 원칙:

- label enum은 추후 확장 가능해야 한다.
- unknown evaluator label은 safe fallback으로 `LOW_CONFIDENCE` 처리한다.
- UI/API 호환성을 위해 기존 label meaning을 깨지 않는다.

---

## Rule-Based Verification 기준

MVP rule:

- sentence에 citation이 존재하는지 확인한다.
- citation context_id가 실제 context에 존재하는지 확인한다.
- sentence 핵심 token/entity가 cited context에 존재하는지 확인한다.
- 숫자, 날짜, 버전, 퍼센트, 수치 표현이 cited context에 존재하는지 확인한다.
- source coverage를 계산한다.
- citation 없는 핵심 문장을 suspicious로 표시한다.
- invalid citation을 unsupported 또는 suspicious로 표시한다.

확장 원칙:

- rule set은 추후 추가/삭제될 수 있어야 한다.
- rule은 독립 함수/service로 분리한다.
- rule 결과는 LLM evaluator 호출 대상 선정에 사용할 수 있어야 한다.
- rule threshold는 config로 조정 가능해야 한다.

---

## Suspicious Sentence Selection 기준

MVP에서는 아래 문장을 suspicious로 표시한다.

- citation이 없는 핵심 문장
- 존재하지 않는 context_id를 citation으로 참조한 문장
- 숫자/날짜/버전이 context에서 확인되지 않는 문장
- 핵심 token/entity overlap이 낮은 문장
- Answer Generation에서 warning이 있는 문장
- insufficient_context 상태에서 생성된 문장

기본 정책:

- suspicious sentence만 LLM evaluator 호출 대상으로 보낸다.
- 이후 필요하면 config로 모든 문장 평가 모드를 켤 수 있도록 설계한다.

---

## QCA 및 UI Warning 기준

MVP에서는 QCA를 DB에 저장하지 않고 local JSON/JSONL 산출물로 생성한다.

QCA candidate:

- question: Answer Generation input 또는 routing query에서 유도
- context: 사용 context 요약 또는 context refs
- answer: generated answer
- verification: overall/sentence results
- quality_label: `accepted|needs_review|rejected`

UI warning metadata:

```json
{
  "ui_warning_required": true,
  "warning_level": "none|low|medium|high",
  "warning_reasons": []
}
```

규칙:

- `UNSUPPORTED`가 하나 이상 있으면 warning을 표시한다.
- `LOW_CONFIDENCE`가 일정 비율 이상이면 warning을 표시한다.
- QCA DB 저장과 UI 렌더링은 MVP에서 수행하지 않는다.
- 후속 단계에서 UI warning badge와 feedback pipeline이 사용할 수 있게 output schema를 안정적으로 유지한다.

---

## Regeneration 기준

MVP에서는 Answer Generation Agent를 직접 호출하거나 재생성 loop를 실행하지 않는다.

대신 아래 metadata를 생성한다.

```json
{
  "regeneration_recommended": true,
  "regeneration_reason": "unsupported_claims_detected",
  "regeneration_request": {
    "target_generation_id": "string",
    "unsupported_sentence_ids": [],
    "guidance": "string"
  }
}
```

후속 확장:

- Answer Generation Agent adapter를 통해 재생성 요청을 보낼 수 있다.
- LangGraph feedback loop에서 verification 실패 시 prompt 수정/재생성을 수행할 수 있다.
- MVP output은 해당 확장을 방해하지 않아야 한다.

---

## Workflow

```text
load_config
  -> load_input
  -> normalize_verification_input
  -> parse_sentences_and_citations
  -> run_rule_based_verification
  -> select_suspicious_sentences
  -> evaluate_suspicious_sentences
  -> aggregate_verification_result
  -> build_ui_warning_metadata
  -> build_qca_output
  -> build_regeneration_recommendation
  -> write_output
  -> write_report
```

핵심 규칙:

- 입력 schema validation은 rule/LLM 평가 전 수행한다.
- rule-based verifier는 항상 먼저 실행한다.
- LLM evaluator는 기본적으로 suspicious sentence에만 호출한다.
- LLM provider 장애 시 rule-based 결과를 유지하고 `LOW_CONFIDENCE` warning을 남긴다.
- 실제 재생성 호출, DB 저장, UI 렌더링은 수행하지 않는다.

---

## Canonical Schema

### Verification Input

```json
{
  "conversation_id": "string",
  "user_id": "string",
  "answer_output": {},
  "contexts": [],
  "metadata": {}
}
```

### Sentence Verification Result

```json
{
  "sentence_id": "s1",
  "text": "string",
  "label": "SUPPORTED|UNSUPPORTED|LOW_CONFIDENCE|NOT_CHECKED",
  "score": 0.0,
  "citations": [],
  "matched_context_ids": [],
  "failed_rules": [],
  "llm_evaluation_used": false,
  "reason": "string"
}
```

### Verification Output

```json
{
  "verification_id": "string",
  "generation_id": "string",
  "conversation_id": "string",
  "user_id": "string",
  "overall_label": "PASS|SUPPORTED|UNSUPPORTED|LOW_CONFIDENCE",
  "overall_score": 0.0,
  "sentence_results": [],
  "unsupported_claims": [],
  "citation_coverage": {
    "total_sentences": 0,
    "sentences_with_citations": 0,
    "valid_citations": 0,
    "invalid_citations": 0,
    "coverage_ratio": 0.0
  },
  "llm_evaluation_used": false,
  "ui_warning_required": false,
  "ui_warning": {
    "warning_level": "none",
    "warning_reasons": []
  },
  "qca_candidate": false,
  "qca_output_ref": null,
  "regeneration_recommended": false,
  "regeneration_request": null,
  "warnings": []
}
```

### QCA Output

```json
{
  "qca_id": "string",
  "conversation_id": "string",
  "generation_id": "string",
  "verification_id": "string",
  "question": "string",
  "context_refs": [],
  "answer": "string",
  "overall_label": "string",
  "overall_score": 0.0,
  "quality_label": "accepted|needs_review|rejected",
  "created_at": "ISO-8601"
}
```

### Verification Report

```json
{
  "job_id": "string",
  "verification_id": "string",
  "generation_id": "string",
  "conversation_id": "string",
  "status": "success|partial_success|failed",
  "overall_label": "string",
  "sentence_count": 0,
  "unsupported_count": 0,
  "low_confidence_count": 0,
  "llm_evaluation_count": 0,
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
| answer_output 없음 | failed, non-retryable |
| contexts 없음 | `LOW_CONFIDENCE` 또는 failed, 상황별 처리 |
| answer sentence 없음 | answer text에서 sentence parsing 시도 |
| citation context 없음 | invalid citation warning |
| rule 결과 불충분 | suspicious sentence로 분류 |
| LLM evaluator invalid JSON | rule result 유지, warning |
| LLM evaluator timeout/5xx | retryable safe error, rule result 유지 |
| OpenAI API key 없음 | provider configuration error |
| OpenAI auth error | non-retryable auth failure |
| QCA output write 실패 | verification output은 유지, report에 warning |

기본 권장값:

```json
{
  "evaluate_suspicious_only": true,
  "min_overall_score": 0.7,
  "min_sentence_score": 0.6,
  "max_retries": 2,
  "timeout_seconds": 30,
  "temperature": 0.0
}
```

---

## 권장 구현 구조

```text
ai-agent/answer-verification-agent/
  answer-verification-agent.md
  src/answer_verification_agent/
    app/
    graph/
    verification/
    rules/
    evaluator/
    qca/
    regeneration/
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
    qca/
  scripts/
```

---

## Feature Breakdown

### feature1_project_skeleton_and_schema

- package 구조 생성
- `pyproject.toml` 설정
- config schema 정의
- verification input schema 정의
- sentence verification result schema 정의
- verification output schema 정의
- citation coverage schema 정의
- QCA output schema 정의
- regeneration request schema 정의
- verification report schema 정의
- CLI skeleton 작성
- schema/config 단위 테스트 작성

### feature2_verification_input_normalization

- Answer Generation output + contexts loader 구현
- verification input validation 구현
- answer output normalization 구현
- context normalization 구현
- missing contexts 처리
- sentence fallback 준비
- normalization 테스트 작성

### feature3_sentence_and_citation_parser

- answer sentence parsing 구현
- generated sentence schema 처리
- citation extraction 구현
- context id validation 구현
- citation coverage 계산 구현
- parser 테스트 작성

### feature4_rule_based_verifier

- citation existence rule 구현
- valid context citation rule 구현
- token/entity overlap rule 구현
- number/date/version presence rule 구현
- source coverage rule 구현
- rule result aggregation 구현
- rule verifier 테스트 작성

### feature5_suspicious_sentence_selector

- suspicious sentence 선정 구현
- citation missing/invalid 기준 구현
- low overlap 기준 구현
- insufficient context 기준 구현
- all-sentence evaluation mode interface 구현
- selector 테스트 작성

### feature6_llm_evaluator_provider

- evaluator provider interface 정의
- OpenAI evaluator provider 구현
- fake evaluator provider 구현
- evaluator prompt builder 구현
- evaluator output parsing 구현
- safe provider error 처리 구현
- provider/evaluator 테스트 작성

### feature7_verification_result_builder

- sentence result 병합
- overall label/score 계산
- unsupported claims 생성
- UI warning metadata 생성
- QCA local output 생성
- regeneration recommendation 생성
- verification report helper 구현
- local JSON writer 구현
- result builder 테스트 작성

### feature8_langgraph_workflow_and_cli

- LangGraph workflow 구성
- sequential fallback 구성
- CLI 실행 스크립트 구현
- local output 저장
- report/QCA/failed 저장
- fake evaluator 기반 workflow integration test 작성

### feature9_fixture_and_safety_tests

- synthetic supported fixture 작성
- synthetic unsupported fixture 작성
- synthetic low-confidence fixture 작성
- synthetic invalid citation fixture 작성
- synthetic numeric mismatch fixture 작성
- synthetic insufficient context fixture 작성
- malformed input/provider failure fixture 작성
- OpenAI API key/token safety 테스트
- output schema 검증
- boundary test 작성

---

## 수용 기준

- CLI로 Answer Verification workflow를 실행할 수 있다.
- Answer Generation Agent output과 Top-5 context JSON을 입력으로 처리할 수 있다.
- OpenAI API key는 외부 주입으로만 사용한다.
- API key가 코드, fixture, log, output file에 저장되지 않는다.
- 테스트는 기본적으로 fake evaluator provider를 사용한다.
- rule-based verifier가 citation, context id, token/entity, number/date/version 근거를 검증한다.
- suspicious sentence만 LLM evaluator 대상으로 선정된다.
- all-sentence evaluation mode 확장 가능성이 있다.
- sentence-level verification result가 생성된다.
- overall label/score가 생성된다.
- UI warning metadata가 생성된다.
- QCA local JSON/JSONL output이 생성된다.
- regeneration recommendation/request payload가 생성된다.
- 실제 Answer Generation 재호출은 수행하지 않는다.
- 실제 DB 저장, UI 렌더링, SSE 전송은 수행하지 않는다.
- LangGraph workflow가 전체 단계를 orchestration한다.
- fixture 기반 integration test가 통과한다.

---

## 후속 개발 메모

- Answer Generation Agent 재생성 loop가 확정되면 `regeneration/` 하위 adapter를 추가한다.
- QCA DB 저장 구조가 확정되면 `qca/` 또는 `storage/` 하위 repository adapter를 추가한다.
- UI warning badge API가 확정되면 verification output mapping을 유지한 채 BFF response formatter와 연결한다.
- rule set은 config 기반으로 enable/disable 가능하게 확장한다.
- all-sentence LLM evaluation mode는 비용/지연을 고려해 opt-in으로 둔다.
- live OpenAI smoke test는 기본 CI에서 제외하고 명시적 opt-in으로만 실행한다.
