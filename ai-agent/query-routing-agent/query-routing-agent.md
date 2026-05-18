# Query Routing Agent

공통 규칙은 루트 `AGENTS.md`와 `ai-agent/AGENTS.md`를 따른다. 이 문서는 Query Routing Agent 고유 개발 명세만 정의한다.

---

## Agent 목표

History Manager Agent가 생성한 독립 질의와 보존 컨텍스트를 입력으로 받아, RAG 검색에 필요한 의도 분류, 검색 쿼리 확장, metadata filter, Multi-Pool weight, Answer Generation용 task prompt type을 생성한다.

Query Routing Agent는 RAG 파이프라인에서 History Manager 다음 단계에 위치한다. 출력은 RAG 검색 파이프라인과 Answer Generation Agent가 바로 소비할 수 있어야 한다.

초기 MVP는 **History Manager Agent output JSON을 입력으로 받아 routing decision과 search request payload를 생성하는 CLI 기반 workflow**를 구현한다.

---

## MVP 범위

포함:

- CLI 수동 실행
- LangGraph workflow
- local JSON input/output
- History Manager Agent output 입력 처리
- OpenAI API 직접 호출 provider 구현
- `OPENAI_API_KEY` 외부 주입
- 테스트용 fake LLM provider
- intent classification
- query rewrite
- metadata filter 생성
- ACL filter 전달
- Multi-Pool weight 생성
- Answer Generation용 task prompt type 결정
- RAG 검색 요청 payload 생성
- fixture 기반 테스트
- token/API key 비노출 safety test

제외:

- 실제 Qdrant 검색 실행
- Dense/Sparse embedding 생성
- Cross-Encoder reranking
- ACL 권한 판정 또는 enforcement
- Answer Generation Agent 구현
- Answer Verification Agent 구현
- BFF API 직접 호출
- DB 직접 조회/저장
- SSE streaming
- production prompt tuning 자동화

후속 확장:

- RAG Pipeline search adapter
- Qdrant request adapter
- Cross-Encoder reranking 연동
- intent label taxonomy 확장
- metadata filter taxonomy 확장
- per-tenant routing policy
- dynamic pool weight tuning
- model routing
- live evaluation set 기반 routing prompt regression test

---

## 책임 범위

책임진다:

- History Manager output 입력 schema 검증
- routing input normalization
- intent classification
- query rewrite
- metadata filter 생성
- ACL filter field 전달
- Multi-Pool weight 계산
- task prompt type 결정
- routing decision 생성
- RAG search request payload 생성
- OpenAI LLM provider adapter
- fake LLM provider
- LangGraph workflow와 CLI
- local JSON output
- fixture/safety tests

책임지지 않는다:

- History Manager Agent 구현
- Vector DB 검색 실행
- ACL 권한 판정
- Cross-Encoder reranking 실행
- 답변 생성
- 답변 검증
- UI formatting
- BFF/DB 직접 연동

---

## 실행 모델

MVP는 CLI 기반 단일 routing decision job이다.

```bash
python ai-agent/query-routing-agent/scripts/run_query_router.py \
  --input ai-agent/query-routing-agent/tests/fixtures/history_manager_output.json \
  --output ai-agent/query-routing-agent/data/output/routing_decision.json
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
  "temperature": 0.0,
  "timeout_seconds": 30,
  "max_retries": 2,
  "default_query_count": 3,
  "max_query_count": 5,
  "default_pool_weights": {
    "title": 0.25,
    "content": 0.6,
    "label": 0.15
  }
}
```

모델명, query 개수, pool weight는 config/env로 교체 가능해야 한다.

---

## 외부 연동 계약

### History Manager Input Contract

MVP에서는 History Manager Agent가 아래 형태의 JSON을 Query Routing Agent에 전달한다고 가정한다.

```json
{
  "conversation_id": "string",
  "user_id": "string",
  "original_question": "string",
  "query": "string",
  "history_decision": "follow_up|new_topic|ambiguous",
  "preserved_context": {
    "summary": "string",
    "entities": [],
    "turn_refs": []
  },
  "reset_required": false,
  "metadata": {
    "locale": "ko-KR",
    "timezone": "Asia/Seoul",
    "groups": [],
    "space_keys": []
  }
}
```

규칙:

- `query`는 검색에 사용할 기본 질문이다.
- `original_question`은 UI/로그/추적용 원문 질문이다.
- `history_decision`은 Query Routing 판단의 보조 signal로 사용한다.
- `preserved_context`는 query rewrite와 intent classification에만 제한적으로 사용한다.
- `groups`, `user_id` 등 ACL 관련 값은 filter payload로 전달하되, 권한 판정은 하지 않는다.
- 빈 `preserved_context`도 정상 입력으로 처리한다.

### LLM Provider Contract

MVP에서 실제 OpenAI API 호출 provider를 구현한다. 단, 테스트는 fake provider를 기본으로 사용한다.

```text
RoutingLLMProvider
  -> route_query(input) -> RoutingLLMResult
```

구현 원칙:

- provider interface와 OpenAI provider 구현을 분리한다.
- API key는 환경변수 또는 secret provider에서만 읽는다.
- OpenAI client error는 safe error로 변환한다.
- prompt, request, response logging에서 API key와 Authorization header를 제거한다.
- live OpenAI 호출 테스트는 기본 test suite에 포함하지 않는다.
- 실제 API smoke test가 필요하면 별도 opt-in flag 또는 별도 script로 분리한다.

---

## Intent 및 Task Prompt 기준

MVP intent label:

| Intent | 한국어 의미 | 기본 task prompt type |
| --- | --- | --- |
| `incident_response` | 장애 대응 | `timeline` |
| `operations_guide` | 운영 가이드 | `step_by_step` |
| `policy_procedure` | 정책·절차 | `evidence_first` |
| `history_lookup` | 이력 조회 | `history_summary` |
| `unknown` | 분류 불명 또는 확장 대상 | `general` |

확장 원칙:

- intent enum은 추후 확장 가능해야 한다.
- unknown label을 허용해 LLM output drift를 안전하게 흡수한다.
- task prompt mapping은 config 또는 table 기반으로 교체 가능하게 둔다.
- Answer Generation Agent 입력 계약을 깨지 않도록 backward compatibility를 유지한다.

---

## Query Rewrite 기준

MVP 기본 정책:

- 기본 `3`개 expanded query를 생성한다.
- 최대 `5`개를 초과하지 않는다.
- 첫 번째 query는 원본 `query`와 의미적으로 가까워야 한다.
- 후속 질문에서 넘어온 `preserved_context`는 핵심 entity 보강에만 사용한다.
- 한국어 질문은 한국어 검색 쿼리를 우선 생성하되, 기술 용어는 영어 병기를 허용한다.
- 빈 query나 중복 query는 제거한다.
- 과도하게 긴 query는 제한하거나 warning으로 기록한다.

예시:

```json
{
  "query": "IAM 정책 수정 장애 상황에서 롤백 절차는?",
  "expanded_queries": [
    "IAM 정책 수정 장애 롤백 절차",
    "IAM 권한 변경 실패 대응 방법",
    "IAM policy rollback troubleshooting"
  ]
}
```

---

## Metadata Filter 및 ACL 기준

MVP filter field:

```json
{
  "space_keys": [],
  "labels": [],
  "document_types": [],
  "source_types": [],
  "date_range": {
    "from": null,
    "to": null
  },
  "attachment_required": false,
  "acl": {
    "user_id": "string",
    "groups": []
  }
}
```

규칙:

- Query Routing Agent는 ACL을 판정하지 않는다.
- `user_id`, `groups`는 RAG Pipeline/Vector DB layer가 강제할 수 있도록 filter payload에 전달한다.
- 권한 관련 값이 없으면 빈 filter로 유지하고 warning을 남길 수 있다.
- metadata filter taxonomy는 추후 확장 가능해야 한다.
- 실제 Qdrant filter 문법으로 고정하지 않고, 중립적인 canonical filter schema를 먼저 생성한다.

---

## Multi-Pool Weight 기준

MVP 기본값:

```json
{
  "title": 0.25,
  "content": 0.6,
  "label": 0.15
}
```

Intent별 조정 예:

| Intent | title | content | label | 설명 |
| --- | ---: | ---: | ---: | --- |
| `incident_response` | 0.2 | 0.65 | 0.15 | 장애 대응 본문 근거 우선 |
| `operations_guide` | 0.25 | 0.6 | 0.15 | 절차 본문 중심 |
| `policy_procedure` | 0.3 | 0.6 | 0.1 | 제목/정책 문서 근거 우선 |
| `history_lookup` | 0.2 | 0.5 | 0.3 | label/date signal 활용 |
| `unknown` | 0.25 | 0.6 | 0.15 | 기본값 |

규칙:

- weight 합은 `1.0`이 되도록 normalize한다.
- 음수 weight 또는 모든 weight 0은 허용하지 않는다.
- config 기반 조정 가능성을 유지한다.

---

## Workflow

```text
load_config
  -> load_input
  -> normalize_routing_input
  -> classify_intent_and_rewrite
  -> build_metadata_filters
  -> build_pool_weights
  -> build_task_prompt_type
  -> build_routing_decision
  -> build_search_request
  -> write_output
  -> write_report
```

핵심 규칙:

- 입력 schema validation은 LLM 호출 전 수행한다.
- intent classification, query rewrite, filter hint 생성은 단일 LLM 호출 결과로 받을 수 있게 설계한다.
- metadata filter와 pool weight는 deterministic post-processing으로 검증/정규화한다.
- 실제 검색은 수행하지 않고 search request payload만 생성한다.
- unknown intent는 failure가 아니라 safe fallback으로 처리한다.
- LLM provider 장애 시 safe failure를 반환하고 raw exception에 secret을 포함하지 않는다.

---

## Canonical Schema

### Routing Input

History Manager Agent의 Query Routing input과 호환된다.

```json
{
  "conversation_id": "string",
  "user_id": "string",
  "original_question": "string",
  "query": "string",
  "history_decision": "follow_up|new_topic|ambiguous",
  "preserved_context": {
    "summary": "string",
    "entities": [],
    "turn_refs": []
  },
  "reset_required": false,
  "metadata": {}
}
```

### Routing Decision

```json
{
  "routing_id": "string",
  "conversation_id": "string",
  "user_id": "string",
  "original_question": "string",
  "query": "string",
  "intent": "incident_response|operations_guide|policy_procedure|history_lookup|unknown",
  "task_prompt_type": "timeline|step_by_step|evidence_first|history_summary|general",
  "expanded_queries": [],
  "metadata_filters": {},
  "pool_weights": {
    "title": 0.25,
    "content": 0.6,
    "label": 0.15
  },
  "confidence": 0.0,
  "reason": "string",
  "warnings": []
}
```

### Search Request Payload

```json
{
  "routing_id": "string",
  "conversation_id": "string",
  "user_id": "string",
  "queries": [],
  "filters": {},
  "pool_weights": {},
  "top_k_candidates": 20,
  "rerank_top_k": 5,
  "reranking_required": true
}
```

### Routing Report

```json
{
  "job_id": "string",
  "routing_id": "string",
  "conversation_id": "string",
  "status": "success|partial_success|failed",
  "intent": "string",
  "expanded_query_count": 0,
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
| query/current question 없음 | failed, non-retryable |
| unsupported history_decision | warning 후 safe fallback |
| LLM invalid JSON | fallback 또는 failed item |
| invalid intent label | `unknown` fallback |
| expanded query 없음 | 원본 query fallback |
| expanded query 최대 개수 초과 | max count로 trim |
| invalid metadata filter | warning 후 빈 filter 또는 safe filter |
| invalid pool weight | default weight fallback |
| OpenAI API key 없음 | provider configuration error |
| OpenAI timeout/5xx | retryable safe error |
| OpenAI auth error | non-retryable auth failure |

기본 권장값:

```json
{
  "default_query_count": 3,
  "max_query_count": 5,
  "top_k_candidates": 20,
  "rerank_top_k": 5,
  "max_retries": 2,
  "timeout_seconds": 30,
  "temperature": 0.0
}
```

---

## 권장 구현 구조

```text
ai-agent/query-routing-agent/
  query-routing-agent.md
  src/query_routing_agent/
    app/
    graph/
    routing/
    llm/
    filters/
    weights/
    search/
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
- routing input schema 정의
- routing decision schema 정의
- metadata filter schema 정의
- pool weight schema 정의
- search request payload schema 정의
- routing report schema 정의
- CLI skeleton 작성
- schema/config 단위 테스트 작성

### feature2_routing_input_normalization

- History Manager output loader 구현
- routing input validation 구현
- preserved_context normalization 구현
- metadata/user/groups normalization 구현
- empty preserved_context 처리
- unsupported history_decision warning 처리
- malformed input 처리
- normalization 테스트 작성

### feature3_intent_classification_provider

- LLM provider interface 정의
- OpenAI provider 구현
- fake LLM provider 구현
- routing prompt builder 구현
- intent classification parsing 구현
- confidence/reason parsing 구현
- invalid intent -> `unknown` fallback 구현
- provider/classification 테스트 작성

### feature4_query_rewrite

- expanded query parsing 구현
- 기본 3개, 최대 5개 제한 구현
- 중복 query 제거 구현
- 빈 query fallback 구현
- preserved_context 기반 query enrichment 구현
- query rewrite 테스트 작성

### feature5_filter_and_pool_weight_builder

- metadata filter builder 구현
- ACL filter 전달 구현
- task prompt type mapping 구현
- intent별 pool weight builder 구현
- weight normalization 구현
- invalid weight fallback 구현
- filter/weight 테스트 작성

### feature6_routing_decision_builder

- routing decision 생성
- search request payload 생성
- warning/report helper 구현
- local JSON writer 구현
- Answer Generation 입력 준비 필드 검증
- routing decision/search payload 테스트 작성

### feature7_langgraph_workflow_and_cli

- LangGraph workflow 구성
- sequential fallback 구성
- CLI 실행 스크립트 구현
- local output 저장
- report 저장
- fake provider 기반 workflow integration test 작성

### feature8_fixture_and_safety_tests

- synthetic incident response fixture 작성
- synthetic operations guide fixture 작성
- synthetic policy/procedure fixture 작성
- synthetic history lookup fixture 작성
- unknown intent fixture 작성
- malformed input/provider failure fixture 작성
- OpenAI API key/token safety 테스트
- output schema 검증
- boundary test 작성

---

## 수용 기준

- CLI로 Query Routing workflow를 실행할 수 있다.
- History Manager Agent output JSON을 입력으로 처리할 수 있다.
- OpenAI API key는 외부 주입으로만 사용한다.
- API key가 코드, fixture, log, output file에 저장되지 않는다.
- 테스트는 기본적으로 fake LLM provider를 사용한다.
- 실제 OpenAI provider 구현은 provider interface 뒤에 분리되어 있다.
- intent는 `incident_response`, `operations_guide`, `policy_procedure`, `history_lookup`, `unknown`을 지원한다.
- expanded query는 기본 3개, 최대 5개 정책을 따른다.
- metadata filter와 ACL filter payload가 생성된다.
- Multi-Pool weight가 생성되고 합계가 1.0으로 normalize된다.
- Answer Generation Agent가 사용할 task prompt type이 생성된다.
- 실제 Qdrant 검색은 수행하지 않고 search request payload만 생성한다.
- LangGraph workflow가 전체 단계를 orchestration한다.
- fixture 기반 integration test가 통과한다.

---

## 후속 개발 메모

- RAG Pipeline 검색 API가 확정되면 `search/` 하위에 adapter를 추가한다.
- Qdrant filter syntax가 확정되면 canonical metadata filter를 Qdrant payload filter로 변환하는 mapper를 추가한다.
- intent label 확장 시 Answer Generation Agent의 task prompt mapping과 backward compatibility를 먼저 확인한다.
- pool weight tuning은 provider 내부가 아니라 config/policy 계층에서 처리한다.
- live OpenAI smoke test는 기본 CI에서 제외하고 명시적 opt-in으로만 실행한다.
