# LINA AI Agent Pipeline

척척학사(LINA) Confluence 기반 RAG 챗봇 서비스의 통합 AI Agent 파이프라인.

본 레포는 SKALA Final Project Team 7의 agent 담당 통합 저장소다. 기존 MVP 6종 에이전트와
팀원이 확장한 RAG/ingestion 파이프라인을 하나의 FastAPI 앱으로 묶는다.

현재 통합된 6종 agent package:

- `data_ingestion_agent/`
- `data_sync_agent/`
- `query_routing_agent/`
- `history_manager_agent/`
- `answer_generation_agent/`
- `answer_verification_agent/`

주요 HTTP 계약:

- `POST /ml/query` — RAG 질의 응답 SSE
- `POST /ml/ingest` — Confluence space 수집 트리거
- `GET /ml/ingest/status/{jobId}` — 수집 job 상태 조회
- `GET /ml/rag/health`, `GET /ml/ingest/health`, `GET /healthz` — health check

---

## 빠른 시작

### 사전 요구

- Python **3.11.x** (`pyproject.toml`에 `requires-python = ">=3.11,<3.12"`)
- Git
- (선택) Docker Desktop — Qdrant/MongoDB/MySQL 로컬 실행 시

### 설치 (macOS / Linux, uv 권장)

```bash
uv venv --python 3.11 .venv
uv pip install -e '.[dev,ingestion,embedding]'
PATH="$PWD/.venv/bin:$PATH" ./scripts/verify.sh
```

### 설치 (macOS / Linux, venv/pip)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev,ingestion,embedding]"
./scripts/verify.sh
```

### 설치 (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,ingestion,embedding]"
.\scripts\verify.ps1
```

### 주요 환경 변수

모든 설정은 `RAG_` prefix를 사용한다(`app/config.py`). 기본값만으로도 PoC 테스트는 통과한다.
운영/실연동 시에는 infra/backend 팀이 다음 값을 주입해야 한다.

```bash
RAG_USE_REAL_ADAPTERS=true
RAG_OPENAI_API_KEY=...
RAG_ATLASSIAN_CLOUD_ID=...
RAG_ATLASSIAN_ACCESS_TOKEN=...
RAG_ATLASSIAN_USE_ADMIN_KEY=false
RAG_ATLASSIAN_GROUP_ACL_FIELD_ORDER=id,groupId,name
RAG_ATLASSIAN_GROUP_ACL_PREFIX=
RAG_ATLASSIAN_EMPTY_RESTRICTION_POLICY=mark_missing
RAG_ATLASSIAN_PUBLIC_ACL_GROUP=*
RAG_RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2F
RAG_MONGO_URI=mongodb://localhost:27017
RAG_MONGO_DB=lina_rag
RAG_QDRANT_HOST=localhost
RAG_QDRANT_PORT=6333
RAG_DATA_SYNC_PREVIOUS_SNAPSHOT=data/snapshots/latest_snapshot.json
RAG_ATTACHMENT_DOWNLOAD_DIR=data/attachments
```

### API 서버 실행

```bash
PATH="$PWD/.venv/bin:$PATH" uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

PoC 기본값(`RAG_USE_REAL_ADAPTERS=false`)에서는 외부 OpenAI/Qdrant/MongoDB 없이 샘플 데이터와
fake adapter로 `/ml/query`가 동작한다. 실 adapter 모드는 `RAG_USE_REAL_ADAPTERS=true`와 외부
서비스 연결이 필요하다.

---

## 동작 확인

### 종합 검증

```bash
./scripts/verify.sh
```

Windows:

```powershell
.\scripts\verify.ps1
```

현재 통합 브랜치 기준 전체 검증:

```text
966 passed, 7 warnings
```

### 테스트만 실행

```bash
pytest
```

### 데모 — 데이터 계층 + 청킹

```bash
python -m examples.demo_data_layer
```

`samples/`의 페이지와 첨부 파일을 PageObject로 로드한 뒤 청크로 분할하는 과정을 콘솔에 요약
출력한다. 외부 서비스 없이 동작한다.

### Smoke — 수집 API

```bash
python scripts/smoke_ingest_api.py
```

FastAPI route 기준으로 `GET /ml/ingest/health` → `POST /ml/ingest` → `GET
/ml/ingest/status/{jobId}`를 실행한다. 기본값은 `json_fixture` + fake/in-memory adapter라
Confluence, Qdrant, MongoDB, OpenAI, RabbitMQ completion event 없이 동작한다. 실
Confluence/Admin Key 수집 smoke는 운영 자격증명과 RabbitMQ/credential lookup 구성을 주입한
별도 환경에서 수행한다.

### Smoke — 임시 Confluence Basic Auth/Admin Key

백엔드 OAuth가 준비되기 전 실제 Confluence 응답 형식과 Admin Key ACL 조회 가능성을 확인하는
임시 smoke다. production ingestion 경로는 OAuth access token을 사용하므로, 이 스크립트는 운영
adapter와 분리된 확인 도구로만 사용한다.

```bash
export CONF_BASE_URL="https://<site>.atlassian.net/wiki"
export ATLASSIAN_EMAIL="<admin-email>"
export ATLASSIAN_API_TOKEN="<atlassian-api-token>"

echo "$CONF_BASE_URL"
echo "$ATLASSIAN_EMAIL"
echo ${#ATLASSIAN_API_TOKEN}

python scripts/smoke_confluence_basic.py --limit 250 --sample-page-id "<page-id>"
```

출력은 일반 조회 page 수, Admin Key header 조회 page 수, Admin Key에서만 보이는 page id,
sample page의 일반/Admin Key 조회 HTTP status, read restriction user/group 수를 요약한다.
토큰 값은 출력하지 않으며 Admin Key 말소도 수행하지 않는다. 실제 API Token 값은 문서나
커밋에 남기지 않는다. 노출된 토큰은 Atlassian에서 즉시 폐기하고 재발급한다.

운영 ACL vocabulary는 Confluence `groupId` 기준이다. `allowed_groups=["space:{key}"]`
합성은 JSON fixture 또는 Admin-Key-off PoC fallback에서만 사용한다. Empty restriction은
상위 권한 상속을 해석하기 전까지 기본 `mark_missing`으로 fail-closed 처리하며,
`allow_authenticated`는 공개 sentinel(`*`)을 의도적으로 허용할 때만 opt-in으로 사용한다.

---

## 외부 서비스

통합 파이프라인은 다음 외부 서비스를 사용한다. 기본 PoC 테스트는 fake/in-memory adapter를
사용하므로 외부 서비스를 띄우지 않아도 통과한다.

- **Qdrant** — Multi-Pool Vector Store (`title_pool` / `content_pool` / `label_pool`)
- **MongoDB** — `ingest_job_status` · `ingestion_jobs` · `embedding_cache` · `chunk_lookup`
- **MySQL** — `space_doc_type_cache`
- **RabbitMQ** — attachment/chunking worker queue, ingestion completion event
- **Confluence/Atlassian API** — 실 수집 source
- **OpenAI API** — 운영 LLM provider
- **BFF/Auth Server** — RabbitMQ completion event consume 후 Admin Key deactivate 처리

스키마 상세는 [`docs/db-schema.md`](docs/db-schema.md).

### 로컬 도커 구성

```bash
docker compose up -d
docker compose ps
```

`docker-compose.yml`은 Qdrant, MongoDB, MySQL을 `app/config.py` 기본값과 맞춰 실행한다.
RabbitMQ는 현재 compose에 포함되어 있지 않으므로 infra 구성 또는 별도 로컬 실행이 필요하다.

---

## 레포 구조

```text
app/
  adapters/       데이터 공급원 어댑터 (JSON 픽스처 / Atlassian)
  api/            FastAPI entrypoint + query/ingest route/deps
  ingestion/      수집·청킹·첨부 추출·워커·임베딩·벡터 스토어
  pipeline/       Query/Ingestion 그래프 조립
  query/          ACL · 히스토리 · 검색 · 재순위화 · 검증 · 포맷터
  schemas/        공통 Pydantic 모델 (PageObject, Chunk, RagState 등)
  storage/        Qdrant · MongoDB · MySQL adapter
  llm/            LLM 관련 경계
  config.py       pydantic-settings 기반 환경 설정

data_ingestion_agent/      vendored Data Ingestion Agent
data_sync_agent/           vendored Data Sync Agent
query_routing_agent/       vendored Query Routing Agent
history_manager_agent/     vendored History Manager Agent
answer_generation_agent/   vendored Answer Generation Agent
answer_verification_agent/ vendored Answer Verification Agent

ai-agent/                  기존 MVP reference tree. root 검증 대상에서는 제외한다.

docs/
  architecture.md          전체 아키텍처
  rag-pipeline-design.md   RAG 파이프라인 설계서
  chunking-strategy.md     청킹 전략
  api-spec.md              /ml/query, /ml/ingest 내부 API 명세
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

- 최상위 [`CLAUDE.md`](CLAUDE.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/conventions.md`](docs/conventions.md)
- [`docs/ai/workflow.md`](docs/ai/workflow.md)
- [`docs/ai/current-plan.md`](docs/ai/current-plan.md)

작업 영역에 따라 추가로 다음 문서를 확인한다.

- API: [`docs/api-spec.md`](docs/api-spec.md)
- DB/저장소: [`docs/db-schema.md`](docs/db-schema.md)
- 청킹: [`docs/chunking-strategy.md`](docs/chunking-strategy.md)

---

## 라이선스

내부 프로젝트. 외부 배포 금지.
