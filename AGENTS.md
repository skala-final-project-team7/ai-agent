# AGENTS.md

이 문서는 Codex, Claude Code 등 Code Agent가 프로젝트에서 따라야 하는 최상위 공통 규칙을 정의한다.  
팀원이 어떤 영역을 담당하더라도 이 파일의 규칙을 우선 적용한다.

---

## 절대 규칙

- 사용자가 요청하지 않은 대규모 리팩토링을 하지 않는다.
- 담당 범위를 벗어난 파일은 수정하지 않는다.
- Public API, DB Schema, 인증/인가 흐름을 변경할 경우 관련 문서를 함께 수정한다.
- Secret, Token, Credential, `.env` 파일을 생성하거나 커밋하지 않는다.
- 테스트 실패 상태로 작업을 완료했다고 보고하지 않는다.
- 임시 코드, 우회 코드, 불필요한 TODO, 디버깅용 로그를 남기지 않는다.
- 기존 아키텍처 의존 방향을 임의로 바꾸지 않는다.
- 다른 팀원의 담당 영역을 수정해야 할 경우, 변경 이유와 영향 범위를 먼저 설명한다.
- 작업 범위가 불명확하면 기존 코드와 문서를 먼저 확인하고, 추측으로 구현하지 않는다.

---

## 프로젝트 문서

작업 전 아래 문서를 확인한다.

- Code Agent 작업 플로우: `docs/ai/workflow.md`
- 팀 공통 프롬프트 템플릿: `docs/ai/prompt-templates.md`
- 아키텍처 문서: `docs/architecture.md`
- 코딩 컨벤션: `docs/conventions.md`
- API 명세: `docs/api-spec.md`
- DB 스키마: `docs/db-schema.md`

> `docs/api-spec.md`, `docs/db-schema.md`가 아직 없는 경우, API 또는 DB 변경 작업 전에 초안을 먼저 생성한다.

---

## 작업 시작 규칙

- 작업 전 반드시 작업 목표와 담당 영역을 확인한다.
- 구현 전 Plan을 먼저 작성한다.
- Plan에는 다음 내용을 포함한다.
  - 작업 목표
  - 수정 대상 파일
  - 수정하지 않을 파일
  - 예상 영향 범위
  - 테스트 방법
  - 완료 기준
  - 문서 수정 필요 여부
- 작업 범위가 커지면 기능을 작은 단위로 나눈다.
- 불확실한 부분은 기존 코드, 문서, 테스트를 먼저 확인한다.

---

## 담당 영역별 확인 규칙

작업 영역에 따라 관련 문서를 확인한다.

### Backend 작업

- `docs/architecture.md`
- `docs/conventions.md`
- `docs/api-spec.md`
- `docs/db-schema.md`

### Frontend 작업

- `docs/architecture.md`
- `docs/conventions.md`
- `docs/api-spec.md`

### RAG Pipeline 작업

- `docs/architecture.md`
- `docs/conventions.md`
- `docs/db-schema.md`

### AI Agent 작업

- `docs/architecture.md`
- `docs/conventions.md`
- `docs/api-spec.md`

---

## 구현 규칙

- 기존 코드 스타일과 폴더 구조를 우선적으로 따른다.
- 새로운 패턴을 도입하기보다 기존 패턴을 확장한다.
- Controller, Service, Repository, Client, DTO의 책임을 섞지 않는다.
- Entity를 API Response로 직접 반환하지 않는다.
- 외부 API 호출, DB 접근, 메시지 큐 처리 등 I/O 작업은 명확한 계층으로 분리한다.
- 비즈니스 로직은 테스트 가능한 형태로 작성한다.
- 예외 처리는 공통 예외 처리 구조를 따른다.
- 로그는 문제 원인 추적에 필요한 정보만 남긴다.
- 민감 정보가 로그에 포함되지 않도록 한다.

---

## 테스트 규칙

- 기능 구현 전 Acceptance Criteria와 Test Case를 먼저 정리한다.
- 핵심 도메인 로직은 Unit Test를 작성한다.
- API 변경 시 Request/Response 검증 테스트를 작성한다.
- 버그 수정 시 재현 테스트를 먼저 작성한다.
- 테스트가 불가능한 구조라면 구현 구조를 먼저 개선한다.
- 테스트 실패 원인을 무시하거나 테스트를 삭제해서 통과시키지 않는다.

---

## 검증 명령

작업 완료 전 아래 명령을 실행한다.

```bash
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/verify.sh
```

일부 명령이 실패하면 실패 원인과 해결 여부를 작업 결과에 기록한다.

---

## 작업 완료 규칙

작업 완료 전 반드시 다음을 확인한다.

- 구현 범위가 요청 범위를 벗어나지 않았는가
- 관련 테스트가 추가 또는 수정되었는가
- lint, format, test가 통과했는가
- API 변경 시 `docs/api-spec.md`가 수정되었는가
- DB 변경 시 `docs/db-schema.md`가 수정되었는가
- 아키텍처 변경 시 `docs/architecture.md`가 수정되었는가
- 불필요한 로그, 주석, 임시 코드가 남아 있지 않은가
- `git diff` 기준으로 의도하지 않은 변경이 없는가

---

## 세션 운영 원칙

- 1 change-set = 1 session을 원칙으로 한다.
- 큰 기능은 milestone 단위로 나누어 작업한다.
- 세션이 길어지면 현재 상태를 요약하고 새 세션에서 이어간다.
- 작업 중 중요한 결정은 문서에 남긴다.
- 내부 추론 과정에 의존하지 말고 Plan, Diff, Test Result, Command Log를 기준으로 검증한다.
