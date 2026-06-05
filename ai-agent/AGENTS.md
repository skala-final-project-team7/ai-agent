# AI Agent 작업 규칙

이 문서는 LINA 팀 프로젝트의 `ai-agent` 영역에서 6개 AI Agent를 개발할 때 적용하는 전용 규칙이다.

루트 `AGENTS.md`가 최상위 공통 규칙이며, 이 문서는 AI Agent 영역에만 필요한 규칙을 추가한다. 개별 Agent md는 이 문서를 참조하고, 각 Agent 고유의 목표/계약/feature만 정의한다.

---

## 담당 영역

`ai-agent` 영역은 LINA의 Agent 단위 기능을 독립적으로 개발하고, 이후 Backend / RAG Pipeline / Infra 작업물과 통합 가능하도록 만드는 책임을 가진다.

| 디렉토리 | Agent |
| --- | --- |
| `history-manager-agent/` | History Manager Agent |
| `query-routing-agent/` | Query Routing Agent |
| `answer-generation-agent/` | Answer Generation Agent |
| `answer-verification-agent/` | Answer Verification Agent |
| `data-ingestion-agent/` | Data Ingestion Agent |
| `data-sync-agent/` | Data Sync Agent |

---

## 디렉토리 원칙

각 Agent는 `ai-agent` 하위의 독립 디렉토리에서 개발한다.

```text
ai-agent/
  AGENTS.md
  <agent-name>/
    <agent-name>.md
    src/
    tests/
    data/
    scripts/
```

규칙:

- Agent별 코드, 테스트, fixture, local data, script는 해당 Agent 디렉토리 안에 둔다.
- 다른 Agent 디렉토리를 임의로 수정하지 않는다.
- Backend, Frontend, RAG Pipeline, Infra 영역은 수정하지 않는다.
- 공통화가 필요하면 먼저 이유와 영향 범위를 문서화하고 합의 후 진행한다.

---

## 작업 전 확인 문서

AI Agent 작업 전 아래 문서를 확인한다.

- 루트 `AGENTS.md`
- `docs/architecture.md`
- `docs/conventions.md`
- `docs/ai/workflow.md`
- `docs/ai/prompt-templates.md`
- `ai-agent/AGENTS.md`
- 작업 대상 Agent의 `<agent-name>/<agent-name>.md`

API/DB 계약을 건드리는 경우:

- `docs/api-spec.md`
- `docs/db-schema.md`

---

## 구현 원칙

- Agent는 하나의 명확한 책임을 가진다.
- Agent 간 입력과 출력 schema를 명확히 정의한다.
- schema/interface를 먼저 고정하고, feature 단위로 구현한다.
- LangGraph node는 orchestration에 집중하고, 핵심 로직은 테스트 가능한 일반 함수/서비스로 작성한다.
- 외부 API 호출, DB 접근, 메시지 큐 처리는 adapter/client/repository 계층으로 분리한다.
- MVP 범위를 넘어서는 기능은 `planned`, `interface_only`, `not_supported_in_mvp` 상태로 명시한다.
- 실제 통합 지점이 미정인 경우 local file, fixture, mock adapter를 우선 사용한다.

---

## 보안 규칙

- Secret, Token, Credential, `.env` 파일을 생성하거나 커밋하지 않는다.
- Access Token, Refresh Token, Authorization Header, API Key를 코드, fixture, 로그, 산출물, 문서 예시에 저장하지 않는다.
- 민감값은 환경변수, CLI 인자, 런타임 secret provider 등 외부 주입 방식으로만 받는다.
- 실제 회사 문서 본문, 개인정보, 실제 token, 실제 cloud id를 테스트 fixture에 넣지 않는다.
- 외부 API client는 Authorization header 전체를 로그에 남기지 않는다.

---

## 테스트 원칙

- 구현 전 Acceptance Criteria와 Test Case를 먼저 정리한다.
- feature 단위로 테스트를 먼저 작성하고, 실패 확인 후 최소 구현으로 통과시킨다.
- 외부 API 호출은 mock 또는 synthetic fixture로 검증한다.
- 핵심 분류/파싱/매핑/검증 로직은 Unit Test를 작성한다.
- workflow는 fixture 기반 Integration Test를 작성한다.
- 테스트 실패를 무시하거나 테스트를 삭제해서 통과시키지 않는다.

---

## Feature 단위 작업 방식

1. 개별 Agent md의 `Feature Breakdown`을 읽는다.
2. 구현할 feature 목록을 `docs/ai/current-plan.md`에 체크리스트로 작성한다.
3. 한 세션에서는 하나의 feature만 구현한다.
4. feature 구현 순서:
   - 요구사항 요약
   - 테스트 케이스 작성
   - 실패 테스트 확인
   - 최소 구현
   - 테스트 통과 확인
   - lint/format/check 실행
   - `docs/ai/current-plan.md` 체크 처리
   - `docs/ai/working-log.md` 업데이트

---

## 개별 Agent md 작성 원칙

개별 Agent md에는 공통 규칙을 반복하지 않는다. 아래 Agent 고유 정보만 작성한다.

- Agent 목표
- MVP 범위
- 책임 범위
- 실행 모델
- 외부 연동 계약
- Workflow
- Canonical Schema
- Error Handling
- 권장 구현 구조
- Feature Breakdown
- 수용 기준
- 후속 개발 메모

