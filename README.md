# LINA RAG Pipeline

척척학사(LINA) Confluence 기반 RAG 챗봇 서비스의 RAG 파이프라인.

본 레포는 SKALA Final Project Team 7의 RAG 파이프라인 모듈을 담는다. 답변 생성기·
질의 라우터 등 LLM 호출이 일어나는 Agent 노드는 별도 담당자가 관리하며 본 레포의
`history_manager_agent/`처럼 vendoring 또는 외부 모듈로 통합된다.

---

## 빠른 시작

### 사전 요구

- Python **3.11.x** (`pyproject.toml`에 `requires-python = ">=3.11,<3.12"`)
- Git
- (선택) Docker Desktop — `feature5-B` 이후 외부 서비스가 필요해질 때

### 설치 (Windows PowerShell)

```powershell
# 1) 가상환경 생성 및 활성화
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) 의존성 설치
python -m pip install --upgrade pip
python -m pip install -e ".[embedding,ingestion,dev]"

# 3) 환경 변수 템플릿 복사 후 시크릿 채우기
Copy-Item .env.example .env
# .env 열어서 RAG_OPENAI_API_KEY 등 입력
```

### 설치 (macOS / Linux)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[embedding,ingestion,dev]"
cp .env.example .env
# .env 편집
```

### 사전 진단 (Windows)

```powershell
.\scripts\preflight.ps1
```

Python 버전, 가상환경, 핵심 의존성, `.env`, Docker 설치 여부까지 한 번에 확인한다.

---

## 동작 확인

### 테스트

```powershell
# Windows
.\scripts\test.ps1

# 또는 직접
pytest
```

현재 **262개 테스트** 통과 (RAG 178 + vendored History Manager Agent 76 + 추가 8).

### 데모 — 데이터 계층 + 청킹

```bash
python -m examples.demo_data_layer
```

`samples/` 의 92개 페이지를 PageObject로 로드한 뒤 379개 청크로 분할하는 과정을
콘솔에 요약 출력한다. 외부 서비스 없이 동작한다.

### 종합 검증

```powershell
.\scripts\verify.ps1   # format → lint → test
```

---

## 외부 서비스 (선택)

RAG 파이프라인은 다음 3종의 저장소를 사용한다. 현재 구현 단계에서는 클라이언트
호출 코드가 아직 없어 띄우지 않아도 테스트/데모가 통과한다.

- **Qdrant** — Multi-Pool Vector Store (`title_pool` / `content_pool` / `label_pool`)
- **MongoDB** — `rag_mock.pages` · `rag_mock.attachments` · `ingestion_jobs` · `embedding_cache`
- **MySQL** — `space_doc_type_cache`

스키마 상세는 [`docs/db-schema.md`](docs/db-schema.md).

### 로컬 도커 구성

```bash
docker compose up -d
docker compose ps
```

`docker-compose.yml`이 위 3종을 `app/config.py` 기본값(`localhost:6333`,
`localhost:27017`, `localhost:3306`, DB명 `lina_rag`)과 정합하게 띄운다.

---

## 레포 구조

```
app/
  adapters/       데이터 공급원 어댑터 (JSON 픽스처 / Atlassian)
  ingestion/      청킹·임베딩·벡터 스토어
  query/          ACL · 히스토리 · 검색 · 재순위화 · 검증 · 포맷터
  schemas/        공통 Pydantic 모델 (PageObject, Chunk, RagState 등)
  api/            FastAPI 진입점 (미구현 — feature11)
  pipeline/       LangGraph 그래프 조립 (미구현 — feature11)
  llm/            OpenAI 클라이언트 래퍼 (Agent 담당)
  config.py       pydantic-settings 기반 환경 설정

history_manager_agent/   vendoring한 History Manager Agent 패키지 (외부 모듈)

docs/
  architecture.md          전체 아키텍처
  rag-pipeline-design.md   RAG 파이프라인 설계서
  chunking-strategy.md     청킹 전략
  api-spec.md              API 명세
  db-schema.md             Qdrant / MongoDB / MySQL 스키마
  conventions.md           코딩 컨벤션
  atlassian-api.md         Confluence API 명세
  history-manager-agent.md History Manager 통합
  adr/                     Architecture Decision Records
  ai/                      Claude Code 작업 플로우 · 진행 로그

examples/   데모 entrypoint
samples/    PoC용 Confluence/Datadog JSON 픽스처 + 첨부 파일
scripts/    포맷·린트·테스트·검증 스크립트 (.sh + .ps1)
tests/      pytest
```

---

## 개발 가이드

작업 전 반드시 다음을 확인한다.

- 최상위 [`CLAUDE.md`](CLAUDE.md) — 절대 규칙 및 작업 플로우
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/conventions.md`](docs/conventions.md)
- [`docs/ai/workflow.md`](docs/ai/workflow.md) — Claude Code 사용 시 플로우
- [`docs/ai/current-plan.md`](docs/ai/current-plan.md) — 현재 진행 중인 작업

작업 영역에 따라 추가로 다음 문서를 확인한다.

- RAG Pipeline: `docs/db-schema.md`
- API: `docs/api-spec.md`
- 청킹: `docs/chunking-strategy.md`

---

## 라이선스

내부 프로젝트. 외부 배포 금지.
