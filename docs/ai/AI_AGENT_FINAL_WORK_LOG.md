# AI Agent 최종 통합 작업 로그

작성일: 2026-06-05  
작업 루트: `/Users/younghoonlee/workspace_git`  
최종 대상 레포: `/Users/younghoonlee/workspace_git/ai-agent`  
최종 기준 브랜치: `main`
최근 갱신: 2026-06-05, backend api-spec v2.5.0 회의 결과 반영

## 1. 문서 목적

이 문서는 AI Agent 담당 개발 과정에서 남긴 다음 세 작업 로그를 분석해 하나로 통합한 최종 기록이다.

- `/Users/younghoonlee/workspace_git/work_notes/AI_AGENT_INTEGRATION_STRATEGY.md`
- `/Users/younghoonlee/workspace_git/work_notes/AGENT_INTEGRATION_PROGRESS.md`
- `/Users/younghoonlee/workspace_git/AI_AGENT_V2_4_ALIGNMENT_LOG.md`

목적은 다음과 같다.

- MVP 6종 에이전트 구현 이후 팀원 작업물을 분석하고 `ai-agent`로 통합한 전체 흐름을 한 파일에서 확인한다.
- 추후 문제가 생겼을 때 어떤 판단으로 어떤 파일을 바꿨는지 추적한다.
- backend, frontend, ingestion, rag 담당자와 협업할 때 Agent/ML 영역의 현재 상태와 남은 의사결정을 빠르게 공유한다.

원본 로그는 삭제하지 않고 보존한다. 이 파일은 중복을 제거한 통합본이다.

## 2. 최종 요약

최종적으로 `ai-agent`는 최초 MVP 6종 에이전트 저장소에서 다음 형태로 확장되었다.

- 6종 에이전트 패키지 보존 및 통합:
  - `data_ingestion_agent`
  - `data_sync_agent`
  - `query_routing_agent`
  - `history_manager_agent`
  - `answer_generation_agent`
  - `answer_verification_agent`
- 통합 FastAPI 앱 추가:
  - `/ml/query`
  - `/ml/ingest`
  - `/ml/ingest/status/{jobId}`
  - `/ml/ingest/health`
  - `/ml/confluence/webhook`
- RAG pipeline 통합:
  - query routing
  - history manager
  - search/rerank
  - answer generation
  - answer verification
  - SSE 응답 계약
- Ingestion pipeline 통합:
  - full crawl
  - delta sync
  - document analyzer
  - attachment extraction worker 경계
  - soft delete
  - webhook/trash 기반 삭제 동기화
- Confluence/Admin Key ACL 경계 구현:
  - Admin Key header 사용 seam
  - page read restriction 조회
  - restriction user/group -> `allowed_users`/`allowed_groups` 매핑
  - group identifier field order 설정
  - empty restriction 정책 설정
  - public ACL sentinel 정책
- backend/frontend 최신 API 계약 반영:
  - api-spec v2.3.0 반영
  - api-spec v2.4.0 반영
  - api-spec v2.5.0 반영 시작
  - `spaceKey` 제거
  - cross-space search + ACL filter 구조
  - Admin Key revoke는 ML 직접 말소가 아니며, 최신 결정은 RabbitMQ completion event 기반
    BFF/Auth Server deactivate 방식
- smoke/검증 도구 추가:
  - local `/ml/ingest` smoke
  - 임시 Confluence Basic Auth/Admin Key smoke

최종 PR 상태:

- PR 1: `feat/agent-integration-pipeline` -> `main` merge 완료
- PR 2: `feat/sync-latest-ingestion-rag` -> `main` merge 완료
- 현재 `main` 최신 커밋:
  - `4c76933 Merge pull request #2 from skala-final-project-team7/feat/sync-latest-ingestion-rag`

현재 로컬 브랜치 상태:

```text
main
feat/#1/data-ingestion
origin/main
origin/feat/#1/data-ingestion
```

`feat/#1/data-ingestion`은 최초 MVP 구현 기준점으로 보존 중이다.

## 3. 초기 상황과 레포 구성

초기 상황은 다음과 같았다.

1. 사용자는 기존 다른 디렉토리에서 MVP 단계 6종 에이전트를 구현했다.
2. 해당 내용은 `ai-agent` repository의 `feat/#1/data-ingestion` 브랜치에 커밋되어 있었다.
3. RAG 담당 팀원은 그 내용을 본인 환경에 clone한 뒤 기능을 확장했다.
4. 팀원은 확장 구현을 별도 두 repository에 나눠 커밋했다.
   - `ingestion`
   - `rag`
5. 사용자는 `/Users/younghoonlee/workspace_git`에 다음 레포들을 새로 clone했다.
   - `ai-agent`
   - `ingestion`
   - `rag`
   - 이후 최신화 과정에서 `backend-template`, `frontend`도 함께 참조했다.

초기 분석 당시 각 레포의 성격은 다음과 같았다.

### 3.1 ai-agent

- 브랜치: `feat/#1/data-ingestion`
- 성격:
  - MVP 단계 6종 에이전트 원본 저장소
  - 초기에는 루트 `app/`, 루트 `pyproject.toml`, 통합 FastAPI 앱이 없었다.
  - 각 에이전트가 독립 패키지 형태로 존재했다.
- 포함 에이전트:
  - `data-ingestion-agent`
  - `data-sync-agent`
  - `answer-generation-agent`
  - `answer-verification-agent`
  - `history-manager-agent`
  - `query-routing-agent`

### 3.2 ingestion

- 브랜치: `main`
- 성격:
  - `data_ingestion_agent`, `data_sync_agent`를 루트 패키지로 포함
  - ingestion API, crawler, delta sync, chunking, attachment extraction, worker, storage 계층 구현
  - 독립 `pyproject.toml`, `scripts/verify.sh` 기준으로 테스트 가능
- 주요 기능:
  - `/ml/ingest` full/delta
  - Data Sync Agent 기반 delta ingestion
  - deleted candidate 처리
  - RabbitMQ chunking worker
  - attachment download/extraction worker
  - Mongo 기반 ingest job lifecycle store

### 3.3 rag

- 브랜치: `main`
- 성격:
  - `answer_generation_agent`
  - `answer_verification_agent`
  - `history_manager_agent`
  - `query_routing_agent`
  - FastAPI query API, RAG graph, search/rerank/generator/verifier, SSE 응답 계약 구현
- 주요 기능:
  - `/ml/query` SSE API
  - RAG graph
  - streaming/non-streaming 분기
  - Qdrant 3-pool 검색
  - chunk lookup
  - rerank
  - attachment source의 `downloadUrl` 보존

## 4. 초기 통합 전략

초기 전략 문서의 핵심 판단은 다음과 같다.

`ai-agent`는 MVP 원본이고, `ingestion`과 `rag`는 실제 서비스 파이프라인으로 확장된 상태였다. 따라서 `ai-agent`를 그대로 확장하기보다, 팀원이 확장한 `ingestion`/`rag` 구조를 기준으로 최종 통합하는 것이 적절하다고 판단했다.

중요한 구조 차이는 다음과 같았다.

- `ingestion`과 `rag`는 모두 루트 `app/` 패키지를 가지고 있었다.
- 같은 경로의 파일이 서로 다른 역할을 했다.
- 단순 복사나 덮어쓰기를 하면 한쪽 기능이 사라질 위험이 컸다.

주요 수동 병합 대상:

- `app/api/routes.py`
- `app/api/deps.py`
- `app/api/main.py`
- `app/config.py`
- `app/schemas/enums.py`
- `app/storage/__init__.py`
- `app/ingestion/sync.py`
- `pyproject.toml`
- `README.md`
- `docs/db-schema.md`

권장 구조:

- `app/api/query_routes.py`
- `app/api/ingest_routes.py`
- `app/api/query_deps.py`
- `app/api/ingest_deps.py`
- `app/api/main.py`에서 두 router를 모두 include

통합 base는 `rag`를 기준으로 삼는 것이 낫다고 판단했다. 이유는 `/ml/query`와 SSE 계약이 더 복잡하고 사용자 응답 경로이기 때문이다. 그 위에 ingestion 기능을 수동 병합하는 방식을 추천했다.

## 5. 테스트 환경 구축과 baseline

초기 테스트 환경 구성에서 로컬 Homebrew Python 문제가 발견되었다.

문제:

- `/opt/homebrew/bin/python3.11`에서 `pyexpat` 로딩 시 `libexpat` 심볼 충돌
- `venv` 생성과 `ensurepip`가 실패
- 프로젝트 코드 문제가 아니라 로컬 Python 런타임/동적 라이브러리 문제로 판단

해결:

```bash
uv python install 3.11
```

이후 각 레포에 `.venv`를 새로 구성했다.

```bash
cd /Users/younghoonlee/workspace_git/ingestion
uv venv --python 3.11 --clear .venv
uv pip install -e '.[ingestion,dev,agents]'
uv pip install -e '.[embedding]'

cd /Users/younghoonlee/workspace_git/rag
uv venv --python 3.11 --clear .venv
uv pip install -e '.[ingestion,dev]'
uv pip install -e '.[embedding]'
```

baseline 결과:

- `ingestion`: `200 passed, 6 warnings`
- `rag`: `755 passed, 7 warnings`

이 시점부터 이후 변경은 baseline 대비 회귀 여부를 판단할 수 있게 되었다.

## 6. ingestion 레포 선행 보강

초기에는 `ingestion` 독립 레포에서 다음 작업을 먼저 진행했다.

### 6.1 `/ml/ingest mode=delta` 실제 배선

배경:

- 기존 `/ml/ingest`는 `full`, `delta` mode를 모두 허용했지만 실제 실행은 full crawl뿐이었다.
- `app/ingestion/sync.py`에는 이미 vendored `data_sync_agent` wrapper가 존재했다.

변경:

- `Settings.data_sync_previous_snapshot` 추가
- `IngestDeps`에 `run_delta`, `previous_snapshot_path` 추가
- `build_ingest_deps()`에서 delta runner 연결
- `/ml/ingest` route에서 `mode=full`/`mode=delta` 분기

의미:

- API 명세상 delta sync 기능이 실제로 실행 경로를 갖게 되었다.
- 운영에서는 raw store, queue publisher를 Mongo/RabbitMQ 구현으로 교체할 수 있게 seam을 좁혔다.

### 6.2 deleted candidate -> soft delete helper

배경:

- Data Sync Agent가 삭제 후보를 산출하더라도 실제 Qdrant payload를 삭제 상태로 바꾸는 공통 경로가 필요했다.

구현 방향:

- 삭제 후보를 즉시 hard delete하지 않고 `is_deleted=true` 식의 soft delete로 처리
- page/attachment id 단위 실패를 격리
- 빈 입력은 no-op
- Qdrant fake store 기반 테스트 추가

### 6.3 RabbitMQ chunking worker 실행 경계

목적:

- chunking을 API process 내부에서만 수행하지 않고 worker loop로 분리할 준비
- ack/nack, retry/DLQ 경계를 명시

주요 구현:

- worker runner/CLI
- queue consumer/publisher seam
- 실패 시 재시도 또는 DLQ로 보낼 수 있는 구조

### 6.4 Attachment download/extraction worker

목적:

- Confluence attachment를 다운로드하고 PDF/DOCX/XLSX 등에서 텍스트를 추출하는 worker 경계 구현

주요 구현:

- attachment downloader
- extractor base/pdf/docx/spreadsheet
- attachment worker
- in-process PoC pipeline에서 attachment extraction까지 drain

### 6.5 API job 상태 저장소 Mongo 구현

목적:

- `/ml/ingest` job lifecycle을 in-memory가 아니라 Mongo로 저장할 수 있게 함

주요 구현:

- `IngestJobStore`
- Mongo 기반 job status repository
- job status route 테스트

### 6.6 RAG source/attachment 계약 점검

목적:

- RAG 응답 source card에서 attachment download URL이 사라지지 않도록 계약 점검

주요 확인:

- source metadata에 `downloadUrl` 보존
- BFF/SSE payload 확장 방향 정리

## 7. ai-agent 통합 브랜치 생성과 1차 통합

통합 브랜치:

```text
feat/agent-integration-pipeline
```

통합 방향:

- `rag`를 base skeleton으로 사용
- `ingestion` 기능을 수동 병합
- 기존 MVP 6종 agent package를 루트 패키지로 vendoring
- 루트 `pyproject.toml`, `app/`, `docs/`, `tests/`, `scripts/`를 통합

주요 커밋:

```text
73bb55a Integrate RAG Pipeline skeleton into ai-agent
e634309 Exclude legacy MVP tree from root verification
62e6247 Integrate ingestion pipeline into ai-agent
af04036 Document unified query and ingestion pipeline
```

### 7.1 RAG skeleton 통합

추가/통합된 주요 영역:

- `answer_generation_agent/`
- `answer_verification_agent/`
- `history_manager_agent/`
- `query_routing_agent/`
- `app/query/*`
- `app/pipeline/query_graph.py`
- `app/api/query_routes.py`
- `app/api/query_deps.py`
- `app/schemas/rag_state.py`
- `tests/query/*`
- `tests/api/test_query_route.py`

검증:

- ai-agent 전용 `.venv` 구성
- root verification에서 legacy MVP tree 제외
- 전체 테스트 통과 상태 확보

### 7.2 ingestion pipeline 통합

추가/통합된 주요 영역:

- `data_ingestion_agent/`
- `data_sync_agent/`
- `app/adapters/atlassian.py`
- `app/api/ingest_routes.py`
- `app/api/ingest_deps.py`
- `app/ingestion/bootstrap.py`
- `app/ingestion/crawler.py`
- `app/ingestion/document_analyzer.py`
- `app/ingestion/extractor/*`
- `app/ingestion/workers/*`
- `app/storage/ingest_jobs.py`
- `app/storage/raw_store.py`
- `app/storage/qdrant_fake.py`
- `app/storage/space_doc_type_cache.py`

검증:

- ingestion tests 추가
- API route tests 추가
- 통합 FastAPI wiring 확인

### 7.3 문서 정리

수정 문서:

- `README.md`
- `docs/api-spec.md`
- `docs/db-schema.md`

정리 내용:

- 통합 query/ingestion pipeline 설명
- 환경변수 설명
- DB schema 설명
- smoke/test 실행 방법

## 8. api-spec v2.3.0 반영

팀원으로부터 다음 파일을 전달받아 분석했다.

- `/Users/younghoonlee/workspace_git/api-spec.md`
- `/Users/younghoonlee/workspace_git/evaluation_set.json`

### 8.1 evaluation_set 분석

확인 결과:

- RAG 품질 평가용 golden set으로 사용 가능
- query, expected answer, expected sources 계열 정보 포함
- 이후 `samples/evaluation_set.json` 또는 평가 script 입력으로 활용 가능

### 8.2 api-spec v2.3.0 분석

주요 차이:

- `/ml/query` request의 `stream` 필드 처리
- `history[].role` 표기
- `groups`와 `spaceKey` fail-closed 책임
- SSE error payload key

반영 커밋:

```text
b3f92f1 Align query contract with api spec v2.3
```

변경:

- `QueryRequest` 변경
- `HistoryTurn.role` 변경
- query route 테스트 갱신
- history 테스트 갱신
- `docs/api-spec.md` 갱신
- `docs/sse-frontend-contract.md` 갱신

검증:

- 관련 테스트 통과
- 전체 테스트 통과

## 9. Confluence Admin Key 수동 테스트와 ACL 설계 반영

사용자는 실제 Confluence Premium 환경에서 Admin Key를 활성화하고 수동 API 호출을 수행했다.

### 9.1 수동 테스트 결과

일반 API Token Basic Auth 조회:

```text
normal_pages=232
```

Admin Key header 조회:

```text
admin_key_pages=237
```

Admin Key에서만 보인 page id:

```text
7798785
7798794
8454146
8519682
8781825
```

sample page:

```text
pageId=7798794
title=영훈없음
normal GET /api/v2/pages/{id}: 404
admin-key GET /api/v2/pages/{id}: 200
```

read restriction API:

```text
GET /rest/api/content/7798794/restriction/byOperation/read
```

결과:

- user restriction: 3명
- group restriction: 0개

확인된 사실:

- Admin Key header를 붙이면 일반 사용자 권한으로 안 보이는 페이지도 조회 가능
- 페이지 본문 응답에는 ACL 정보가 직접 포함되지 않음
- ACL metadata는 `restriction/byOperation/read`를 별도 호출해야 얻을 수 있음
- page-level restriction이 비어 있어도 일반 조회에서 안 보이는 페이지가 존재할 수 있음

### 9.2 Admin Key ACL 문서 정합화

반영 커밋:

```text
9c6f359 Document Confluence admin key ACL findings
```

수정:

- `docs/atlassian-api.md`
- `docs/db-schema.md`
- `docs/adr/0002-acl-prefix-convention.md`
- `docs/adr/0003-ingestion-rag-shared-contracts.md`
- `docs/rag-pipeline-design.md`
- `docs/ai/current-plan.md`
- `app/CLAUDE.md`
- `app/adapters/atlassian.py`

의미:

- Admin Key 실측 결과를 문서와 설계에 반영
- page restriction 기반 운영 ACL 수집 방향 확정
- 상위 folder/page/space permission은 추가 협의 필요 사항으로 남김

### 9.3 Admin Key ACL seam 구현

반영 커밋:

```text
c38d028 Add Confluence admin key ACL seam
```

구현:

- `DataIngestionConfig`에 Admin Key 사용 옵션 추가
- Confluence client에 Admin Key header 처리 추가
- read restriction 조회 메서드 추가
- `RAG_ATLASSIAN_USE_ADMIN_KEY` 설정 추가
- `AtlassianSourceAdapter`에 ACL provider seam 추가
- `ConfluenceRestrictionAclProvider` 구현
- restriction parser 구현

검증:

- Confluence client 단위 테스트
- Atlassian adapter 단위 테스트
- full verification 통과

### 9.4 Confluence group ACL mapping seam

반영 커밋:

```text
01de6d2 Add configurable Confluence group ACL mapping
```

구현:

- `RAG_ATLASSIAN_GROUP_ACL_FIELD_ORDER`
- `RAG_ATLASSIAN_GROUP_ACL_PREFIX`
- group restriction 결과에서 어떤 필드를 BFF JWT `groups` claim과 맞출지 설정 가능

지원 예:

```text
name
id
groupId
```

의미:

- Confluence group id/name과 BFF JWT groups claim 형식이 아직 확정되지 않은 상태에서도 adapter 변경 없이 설정으로 맞출 수 있게 됨

### 9.5 Confluence empty restriction 정책

반영 커밋:

```text
f5de594 Add Confluence empty restriction ACL policy
```

초기 정책:

- `mark_missing`
- `space_fallback`

이후 api-spec v2.4.0 정합 과정에서 최신 ingestion/rag 계약에 맞춰 기본값이 다음으로 바뀌었다.

```text
RAG_ATLASSIAN_EMPTY_RESTRICTION_POLICY=allow_authenticated
RAG_ATLASSIAN_PUBLIC_ACL_GROUP=*
```

현재 의미:

- page-level restriction이 비어 있는 경우 기본적으로 인증 사용자 전체 접근 가능 sentinel `*`를 부여
- RAG 검색에서는 모든 principal의 group 조건에 `*`를 추가해 public ACL 문서를 검색 가능하게 함
- 더 보수적인 운영이 필요하면 `mark_missing`으로 전환 가능

## 10. 최신 팀원 레포 재동기화와 api-spec v2.4.0 반영

사용자는 backend, frontend, ingestion, rag 최신 작업물을 다시 clone했다. 이후 `ai-agent`를 최신 팀원 스펙에 맞추는 작업을 시작했다.

작업 로그:

- `/Users/younghoonlee/workspace_git/AI_AGENT_V2_4_ALIGNMENT_LOG.md`

### 10.1 최신 스펙 분석

참조:

- `backend-template/docs/api-spec.md` v2.4.0
- 최신 `frontend`
- 최신 `ingestion`
- 최신 `rag`

주요 결정:

- LINA API 표면에서 `spaceKey` 제거
- `/ml/query`는 userId/groups 기반 ACL만 사용해 cross-space 검색
- `/ml/ingest`는 `mode`, `accessToken`, `cloudId`만 받음
- Admin Key로 접근 가능한 전체 스페이스를 수집
- Admin Key deactivate 책임은 ML이 아니라 BFF/Auth Server

ai-agent와의 차이:

- `QueryRequest`에 `spaceKey` 존재
- `RagState.space_key` 존재
- `build_acl_filter`가 public sentinel을 추가하지 않음
- `IngestRequest`에 `spaceKey` 존재
- `CrawlRequest.space_key`가 필수
- empty restriction 기본값이 최신 ingestion과 다름

### 10.2 api-spec v2.4.0 구현

반영 커밋:

```text
03d8d87 Align ai-agent with api spec v2.4
```

원래 별도 브랜치 커밋:

```text
e177a85 Align ai-agent with api spec v2.4
```

후속 통합 브랜치에 cherry-pick되며 해시가 `03d8d87`로 바뀌었다.

변경:

- `/ml/query` request에서 `spaceKey` 제거
- `/ml/ingest` request에서 `spaceKey` 제거
- `RagState.space_key` 제거
- `search_node`의 hard space scope 제거
- cross-space search + ACL filter 구조로 전환
- `PUBLIC_ACL_GROUP="*"` 추가
- `build_acl_filter`가 모든 principal 조건에 `*` 추가
- `atlassian_empty_restriction_policy` 기본값을 `allow_authenticated`로 변경
- `atlassian_public_acl_group="*"` 설정 추가

검증:

```text
대상 테스트: 94 passed, 7 warnings
Ruff: All checks passed
전체 테스트: 989 passed, 7 warnings
```

## 11. 최신 ingestion/rag 동기화 작업

후속 브랜치:

```text
feat/sync-latest-ingestion-rag
```

### 11.1 soft delete/webhook 동기화

반영 커밋:

```text
52d4d3d Sync ingestion soft delete webhook flow
```

추가:

- `app/ingestion/soft_delete.py`
- `app/adapters/confluence_trash.py`
- `app/ingestion/workers/sync_worker.py`
- `app/api/webhook_routes.py`

수정:

- `app/api/main.py`
- `app/api/ingest_deps.py`
- `app/ingestion/bootstrap.py`

테스트:

- `tests/ingestion/test_soft_delete.py`
- `tests/ingestion/test_sync_worker.py`
- `tests/adapters/test_confluence_trash.py`
- `tests/api/test_webhook_route.py`

의미:

- Delta 삭제 후보 confirm gate
- Confluence Trash source
- Webhook deletion event
- 모든 삭제 경로를 공통 soft-delete funnel로 수렴

검증:

```text
신규/관련 테스트: 44 passed
Ruff: All checks passed
전체 테스트: 1004 passed, 7 warnings
```

### 11.2 DocumentAnalyzer ingestion graph 연결

반영 커밋:

```text
86fcd06 Wire document analyzer into ingestion graph
b3cf7bc Update documentation for document analyzer integration
```

변경:

- `manage_document_analyzer` 노드 추가
- real deps에서 OpenAI document type classifier + MySQL `space_doc_type_cache` 연결
- fake/in-memory 경로는 기존 테스트 가능성 유지
- `app/pipeline/ingestion_graph.py`
- `app/api/query_deps.py`
- 관련 테스트 갱신

의미:

- 수집된 문서가 chunking/indexing 전에 문서 유형 분석 단계를 통과할 수 있게 됨
- 운영에서는 MySQL cache를 통해 space별 문서 유형 판단 결과를 재사용 가능

검증:

```text
관련 테스트: 18 passed
Ruff: All checks passed
전체 테스트: 1007 passed, 7 warnings
```

### 11.3 문서/주석 정합성 최신화

반영 커밋:

```text
b3cf7bc Update documentation for document analyzer integration
```

수정:

- `README.md`
- `docs/api-spec.md`
- `docs/ai/current-plan.md`
- package export 문서

의미:

- 실제 graph에 document analyzer가 연결된 상태를 문서에 반영

## 12. Admin Key revoke 흐름 변경 이력

v2.4 시점 결정:

- ML이 Atlassian Admin Key를 직접 말소하지 않는다.
- ML은 ingestion job이 terminal 상태에 도달하면 BFF에 revoke 요청 callback을 보낸다.
- 실제 Admin Key deactivate는 BFF/Auth Server가 수행한다.

반영 커밋:

```text
63b8e93 Request BFF admin key revoke after ingestion
43c1364 Request BFF admin key revoke after ingestion
```

구현:

- `app/api/admin_key_revoke.py`
- `RAG_BFF_ADMIN_KEY_REVOKE_URL`
- `/ml/ingest` full/delta job이 `COMPLETED` 또는 `FAILED`가 되면 callback 전송
- callback payload:
  - `jobId`
  - `mode`
  - `status`
  - `cloudId`
  - `finishedAt`
  - `error`
- `accessToken`은 callback payload에 포함하지 않음
- callback 실패는 job status를 덮어쓰지 않고 로그만 남김

테스트:

- `tests/api/test_admin_key_revoke.py`
- `tests/api/test_ingest_route.py`
- `tests/test_config.py`

검증:

```text
신규/관련 테스트: 25 passed, 6 warnings
Ruff: All checks passed
전체 테스트: 1013 passed, 7 warnings
```

남은 협의:

- BFF callback endpoint URL
- callback 인증 방식
- BFF가 추가 식별자(`adminUserId`, `connectionId` 등)를 요구하는지 여부
- retry queue/alerting 정책

### 12.1 v2.5.0 갱신 — RabbitMQ completion event 방식

2026-06-05 backend 최신 문서(`backend-template/docs/api-spec.md` v2.5.0,
`docs/adr/0001-page-level-acl-source.md`) 기준으로 위 HTTP callback 방식은 최신 운영 방향이
아니다. 최신 결정은 다음과 같다.

- BFF polling watcher와 ML -> BFF HTTP revoke callback 방식은 RabbitMQ completion event로 대체한다.
- BFF 또는 Data Ingestion Pipeline이 발행하는 ingest job payload에는 `jobId`, `adminUserId`,
  `mode`, `requestedAt` 등 식별 정보만 포함한다.
- RabbitMQ job/completion payload에는 `accessToken`, `refreshToken`, `cloudId`를 포함하지 않는다.
- Data Ingestion Worker는 job consume 후 `adminUserId`로 auth-server 내부 credential API를 호출해
  admin OAuth `accessToken` + `cloudId`를 조회한다.
- Data Ingestion Worker는 Confluence 호출 시 `Authorization: Bearer {admin accessToken}` +
  `Atl-Confluence-With-Admin-Key: true` header를 사용한다.
- 수집 완료/실패 시 ML/Data Ingestion은 completion event를 발행한다.
- BFF consumer가 completion event를 consume하고 auth-server
  `POST /internal/admin/key/deactivate`를 호출한다.
- deactivate 대상은 OAuth token이 아니라 Atlassian Admin Key 활성 상태다.
- completion event는 `jobId` 기준 idempotent하게 처리해야 한다.

ai-agent 반영 방향:

- `/ml/ingest` request에 `adminUserId`를 preferred 식별자로 추가한다.
- 기존 `accessToken`/`cloudId` optional 필드는 backend OAuth/RabbitMQ가 완성되기 전 local/PoC
  호환용 legacy 필드로만 유지한다.
- terminal 상태 처리에서 HTTP revoke callback 대신 credential 없는 completion event seam을 사용한다.
- 기존 `app/api/admin_key_revoke.py`와 `tests/api/test_admin_key_revoke.py`는 최신 경로에서 제거한다.
- 기존 `RAG_BFF_ADMIN_KEY_REVOKE_URL` 계열 설정은 deprecated compatibility로만 남긴다.

### 12.2 v2.5.0 ai-agent 실제 반영 작업

작업 브랜치:

```text
feat/api-spec-v2-5-ingest-completion
```

작업 배경:

- backend 담당자의 최신 작업물(`/Users/younghoonlee/workspace_git/backend-template`)을 확인한 결과
  API 문서 버전이 v2.5.0으로 갱신되어 있었다.
- v2.5.0의 핵심 변경은 Admin Key 말소 흐름이 기존 BFF polling watcher 또는 ML HTTP callback이
  아니라 RabbitMQ completion event 기반으로 바뀐 것이다.
- 또한 `/ml/ingest` 또는 RabbitMQ job payload에 `accessToken`/`refreshToken`/`cloudId` 같은
  Confluence credential set을 포함하지 않고, Data Ingestion Worker가 `adminUserId`로 auth-server
  내부 credential 조회 API를 호출하는 것이 최신 원칙이다.
- 회의 중 공유된 Atlassian API Token은 실제 secret이므로 코드/문서/커밋에 남기지 않았다. 해당
  token은 노출된 것으로 보고 Atlassian에서 폐기 후 재발급해야 한다.

추가한 파일:

- `app/api/ingest_completion.py`
  - `IngestCompletionEvent`
  - `IngestCompletionPublisher`
  - `NoopIngestCompletionPublisher`
  - `QueueIngestCompletionPublisher`
  - `publish_ingest_completion_safely()`
  - completion event payload는 `jobId`, `adminUserId`, `mode`, `status`, `completedAt`,
    `errorCode`, `message`만 포함한다.
  - `accessToken`, `refreshToken`, `cloudId`는 의도적으로 포함하지 않는다.

- `tests/api/test_ingest_completion.py`
  - completion event payload에 credential이 없는지 검증.
  - `QueueIngestCompletionPublisher`가 routing key와 payload를 `QueuePublisher`에 전달하는지 검증.
  - no-op publisher와 publisher 실패 격리 동작 검증.

삭제한 파일:

- `app/api/admin_key_revoke.py`
  - 기존 ML -> BFF HTTP revoke callback client.
  - v2.5.0 정본 경로가 RabbitMQ completion event로 바뀌었으므로 제거했다.

- `tests/api/test_admin_key_revoke.py`
  - 제거된 HTTP callback client 테스트.

수정한 주요 파일:

- `app/api/ingest_routes.py`
  - `IngestRequest`에 `adminUserId`를 추가했다.
  - `accessToken`/`cloudId`는 legacy PoC/smoke 호환 필드로만 유지했다.
  - full/delta job terminal 상태에서 `_publish_ingest_completion()`을 호출하도록 변경했다.
  - completion event 발행 실패는 job terminal status를 덮어쓰지 않도록 안전하게 격리했다.

- `app/api/ingest_deps.py`
  - `admin_key_revoke_notifier` 의존성을 제거하고 `completion_publisher` 의존성을 추가했다.
  - 기본값은 local/PoC 안전성을 위해 `NoopIngestCompletionPublisher()`다.
  - 실제 RabbitMQ 발행 wiring은 infra/worker 운영 진입점에서 주입해야 한다.

- `app/ingestion/crawler.py`
  - `CrawlRequest.admin_user_id` 추가.
  - credential이 아닌 관리자 식별자로 completion event에 포함 가능하다는 의미를 문서화했다.

- `app/ingestion/sync.py`
  - `DeltaSyncRequest.admin_user_id` 추가.

- `app/config.py`
  - `ingest_completion_routing_key="ingestion.completed"` 설정 추가.
  - 기존 `bff_admin_key_revoke_*` 설정은 v2.5.0 기준 deprecated compatibility로 문서화했다.

- `tests/api/test_ingest_route.py`
  - full/delta 완료 시 BFF callback이 아니라 completion event가 발행되는지 검증하도록 수정.
  - completion event payload에 `accessToken`/`cloudId`가 포함되지 않는지 검증.
  - completion event 발행 실패가 job status를 덮어쓰지 않는지 검증.

- `README.md`
  - local ingestion smoke가 RabbitMQ completion event를 호출하지 않는다고 정정.
  - 임시 Confluence Basic Auth smoke 절차에 환경변수 확인 명령을 추가.
  - 실제 API Token 값은 문서/커밋에 남기지 않고, 노출 시 폐기/재발급해야 한다고 명시.

- `docs/api-spec.md`
  - `/ml/ingest`를 v2.5.0 기준으로 갱신.
  - `adminUserId`를 preferred field로 명시.
  - `accessToken`/`cloudId`는 legacy PoC-only field로 정리.
  - Admin Key deactivate trigger를 RabbitMQ completion event로 정정.

- `docs/atlassian-api.md`
  - 임시 smoke는 read-only 확인 도구임을 유지.
  - 운영 경로에서는 worker가 `adminUserId`로 auth-server 내부 credential API를 조회한다고 정정.
  - 실제 API Token 값은 문서/코드/커밋에 남기지 않는다고 명시.

- `docs/ai/current-plan.md`
  - Admin Key 수명주기 최신 결정을 v2.5.0 RabbitMQ completion event 방식으로 갱신.

검증 결과:

```bash
.venv/bin/python -m pytest tests/api/test_ingest_completion.py tests/api/test_ingest_route.py tests/test_config.py tests/scripts/test_smoke_ingest_api.py -q
.venv/bin/ruff check app tests scripts
.venv/bin/python -m pytest -q
```

결과:

```text
관련 테스트: 26 passed, 6 warnings
Ruff: All checks passed
전체 테스트: 1017 passed, 7 warnings
```

현재 호환성 판단:

- backend api-spec v2.5.0의 문서/계약 방향과 정합한다.
- credential을 RabbitMQ payload에 넣지 않는 보안 원칙과 정합한다.
- ML이 Admin Key를 직접 말소하지 않는 책임 분리와 정합한다.
- BFF/Auth Server가 deactivate를 수행하는 구조와 정합한다.
- 단, 실제 운영 RabbitMQ publisher wiring과 auth-server 내부 credential 조회 client는 아직 후속 작업이다.
  현재는 seam과 payload 계약을 먼저 맞춘 상태다.

남은 후속 작업:

- `QueueIngestCompletionPublisher`를 운영 RabbitMQ connection/channel과 실제로 연결하는 worker/infra wiring.
- Data Ingestion Worker가 `adminUserId`로 auth-server 내부 credential API를 호출하는 client 구현.
- RabbitMQ ingest job consume 경로와 `/ml/ingest` HTTP 위임 경로 중 운영 entrypoint 최종 확정.
- BFF completion event consumer의 idempotency, retry, DLQ 정책과 event schema 최종 고정.

## 13. Smoke 도구 추가와 실제 검증

### 13.1 Local ingestion API smoke

반영 커밋:

```text
250d89f Add local ingestion API smoke
```

추가:

- `scripts/smoke_ingest_api.py`
- `tests/scripts/test_smoke_ingest_api.py`

동작:

- `httpx.ASGITransport`로 FastAPI app 직접 호출
- `GET /ml/ingest/health`
- `POST /ml/ingest`
- `GET /ml/ingest/status/{jobId}`
- `json_fixture` + fake/in-memory adapter 사용
- 외부 Confluence, Qdrant, MongoDB, OpenAI, RabbitMQ completion event 호출 없음

실행 결과:

```text
[smoke] /ml/ingest completed
[smoke] jobId=job-ca0f9eb6-53ef-4928-81f0-5f8b5cd9c3c9
[smoke] pages=total:92 processed:92 failed:0
```

검증:

```text
신규/관련 테스트: 18 passed, 6 warnings
Ruff: All checks passed
전체 테스트: 1015 passed, 7 warnings
```

### 13.2 임시 Confluence Basic Auth/Admin Key smoke

배경:

- backend OAuth 개발이 아직 완료되지 않아 production 방식의 OAuth access token을 받을 수 없었다.
- 사용자는 Atlassian API Token + 이메일 + Admin Key header로 수동 확인이 가능했다.
- production adapter에 Basic Auth를 섞지 않고, 임시 확인 도구로만 분리했다.

반영 커밋:

```text
e46d7f7 Add temporary Confluence basic auth smoke
```

추가:

- `scripts/smoke_confluence_basic.py`
- `tests/scripts/test_smoke_confluence_basic.py`

환경변수:

```bash
export CONF_BASE_URL="https://<site>.atlassian.net/wiki"
export ATLASSIAN_EMAIL="<admin-email>"
export ATLASSIAN_API_TOKEN="<atlassian-api-token>"
```

실행:

```bash
.venv/bin/python scripts/smoke_confluence_basic.py --limit 250 --sample-page-id "7798794"
```

실제 실행 결과:

```text
[confluence-smoke] completed
[confluence-smoke] normal_pages=232
[confluence-smoke] admin_key_pages=237
[confluence-smoke] admin_only_pages=5
[confluence-smoke] admin_only_page_ids=7798785,7798794,8454146,8519682,8781825
[confluence-smoke] sample=id:7798794 title:영훈없음 normal_status:404 admin_status:200 read_users:3 read_groups:0
```

확인된 사실:

- 일반 Basic Auth 호출에서는 232개 page 조회
- Admin Key header 추가 시 237개 page 조회
- Admin Key에서만 추가로 보이는 page 5개 존재
- sample page `7798794`는 일반 호출 `404`, Admin Key 호출 `200`
- 해당 page의 read restriction API에서 user restriction 3개, group restriction 0개 확인

검증:

```text
tests/scripts/test_smoke_confluence_basic.py: 3 passed
Ruff: All checks passed
전체 테스트: 1018 passed, 7 warnings
```

## 14. PR 정리와 main 반영

최종 PR은 변경량과 의존 관계를 고려해 2개로 나눴다.

### 14.1 PR 1

브랜치:

```text
base: main
compare: feat/agent-integration-pipeline
```

목적:

- MVP 6종 에이전트와 unified RAG/ingestion pipeline foundation을 main에 반영
- Confluence ACL 기초 구조와 v2.3 기반 계약까지 포함

결과:

```text
04cbd28 Merge pull request #1 from skala-final-project-team7/feat/agent-integration-pipeline
```

merge 후 GitHub 원격 branch delete 완료.

### 14.2 PR 2

브랜치:

```text
base: main
compare: feat/sync-latest-ingestion-rag
```

목적:

- api-spec v2.4.0 정합
- soft delete/webhook
- document analyzer graph 연결
- RabbitMQ completion event 기반 Admin Key deactivate trigger
- local ingestion smoke
- temporary Confluence Basic Auth smoke

결과:

```text
4c76933 Merge pull request #2 from skala-final-project-team7/feat/sync-latest-ingestion-rag
```

merge 후 GitHub 원격 branch delete 완료.

## 15. 로컬 브랜치 정리

PR merge 후 수행한 정리:

```bash
git switch main
git pull
git fetch --prune
git branch -d feat/agent-integration-pipeline
git branch -d feat/sync-latest-ingestion-rag
```

추가로 중간 브랜치 `feat/api-spec-v2-4-alignment`는 main보다 뒤처진 상태임을 확인했다.

확인 명령:

```bash
git diff --stat main..feat/api-spec-v2-4-alignment
```

결과는 PR 2에서 추가된 최신 파일들이 해당 브랜치로 가면 삭제되는 형태였으므로, 오래된 중간 브랜치로 판단했다.

삭제:

```bash
git branch -D feat/api-spec-v2-4-alignment
git push origin --delete feat/api-spec-v2-4-alignment
```

현재 남은 브랜치:

```text
feat/#1/data-ingestion
main
remotes/origin/HEAD -> origin/main
remotes/origin/feat/#1/data-ingestion
remotes/origin/main
```

`origin/HEAD`는 `origin/main`으로 정상화했다.

## 16. 현재 시스템 흐름

최종 설계 기준 액터:

- 관리자
- 일반 사용자

### 16.1 관리자 흐름

1. 관리자 로그인은 frontend/BFF/Auth Server의 Confluence OAuth 흐름을 통해 처리된다.
2. 관리자 페이지에서 Admin Key 활성화, ingestion, sync 작업을 수행한다.
3. BFF/Auth Server가 Admin Key lifecycle을 관리한다.
4. ML/Data Ingestion Worker는 `adminUserId`로 auth-server 내부 credential API를 호출해
   admin OAuth `accessToken` + `cloudId`를 조회한다. legacy HTTP smoke에서만 직접
   `accessToken`/`cloudId` 입력을 허용한다.
5. 수집 과정에서 Confluence page content와 read restriction metadata를 함께 수집한다.
6. ACL 정보는 `allowed_users`, `allowed_groups`로 chunk payload에 저장된다.
7. ingestion job 종료 후 ML/Data Ingestion은 RabbitMQ completion event를 발행한다.
8. BFF consumer가 completion event를 consume하고 auth-server deactivate 내부 API를 호출한다.

### 16.2 일반 사용자 흐름

1. 일반 사용자는 Confluence OAuth 로그인 후 채팅 페이지에 진입한다.
2. 사용자는 별도 ingestion/sync 작업을 수행하지 않는다.
3. BFF는 사용자의 `userId`, `groups`를 ML `/ml/query`에 전달한다.
4. ML은 cross-space 검색을 수행하되, `allowed_users`/`allowed_groups` ACL filter로 접근 가능한 chunk만 검색한다.
5. Query Routing, History Manager, Answer Generation, Answer Verification을 거쳐 답변을 생성한다.
6. SSE event로 token/source/verification/meta/done/error를 frontend/BFF로 전달한다.

## 17. 중요 설계 결정

### 17.1 `spaceKey` 제거

api-spec v2.4.0 기준으로 외부 API request에서 `spaceKey`를 제거했다.

- `/ml/query`: cross-space search
- `/ml/ingest`: Admin Key로 접근 가능한 전체 스페이스 수집
- 권한 경계는 `spaceKey`가 아니라 ACL payload로 강제

### 17.2 ACL 필터

RAG 검색 권한 필터는 다음 구조다.

```text
allowed_users contains userId
OR
allowed_groups intersects user groups + public sentinel "*"
```

### 17.3 public ACL sentinel

`allow_authenticated` 정책의 sentinel:

```text
RAG_ATLASSIAN_PUBLIC_ACL_GROUP=*
```

의미:

- page-level restriction이 비어 있고 정책이 `allow_authenticated`일 때 `allowed_groups=["*"]` 저장
- 모든 인증 사용자의 검색 principal에 `*`를 추가해 검색 가능하게 함

### 17.4 Admin Key lifecycle

최종 결정:

- 발급/말소 주체: BFF/Auth Server
- 수집 수행: ML
- 수집 완료 알림: ML/Data Ingestion -> RabbitMQ completion event
- completion event consume 및 deactivate 호출: BFF consumer -> auth-server
- ML은 Atlassian Admin Key DELETE API를 직접 호출하지 않음
- RabbitMQ payload에는 Confluence credential set을 포함하지 않음

### 17.5 임시 Basic Auth smoke의 위치

`scripts/smoke_confluence_basic.py`는 production code path가 아니다.

사용 목적:

- backend OAuth가 준비되기 전 실제 Confluence/Admin Key 응답 shape 확인
- 일반 호출과 Admin Key 호출의 page visibility 차이 확인
- restriction metadata 확인

금지/주의:

- production adapter에 Basic Auth를 섞지 않음
- Admin Key 발급/말소를 수행하지 않음
- secret을 출력하지 않음
- 실제 API Token 값은 문서·코드·커밋에 남기지 않음
- 회의/채팅/로그에 노출된 token은 Atlassian에서 폐기하고 재발급해야 함

## 18. 검증 이력 요약

중요 검증 결과:

```text
ingestion baseline: 200 passed, 6 warnings
rag baseline: 755 passed, 7 warnings
api-spec v2.4 targeted: 94 passed, 7 warnings
api-spec v2.4 full: 989 passed, 7 warnings
soft-delete/webhook full: 1004 passed, 7 warnings
document analyzer full: 1007 passed, 7 warnings
admin key revoke full: 1013 passed, 7 warnings
local ingestion smoke full: 1015 passed, 7 warnings
temporary confluence smoke final full: 1018 passed, 7 warnings
```

최종 실제 smoke:

```text
local /ml/ingest smoke:
total:92 processed:92 failed:0

Confluence Basic Auth/Admin Key smoke:
normal_pages=232
admin_key_pages=237
admin_only_pages=5
sample 7798794: normal 404, admin 200, read_users 3, read_groups 0
```

## 19. 남은 과제와 협업 필요 사항

### 19.1 backend/BFF/Auth Server

남은 항목:

- Confluence OAuth 3LO 구현
- auth-server 내부 credential 조회 API 구현:
  - `GET /internal/auth/admin-confluence-credential?adminUserId={adminUserId}`
  - 응답: `accessToken`, `cloudId`, `expiresAt`
- Admin Key activate/deactivate 내부 API 구현
- RabbitMQ completion event consumer 구현
- completion event idempotency/DLQ/retry 정책 구현
- JWT 또는 ML request의 `groups` claim 형식 확정
- 관리자 페이지에서 Admin Key 활성화/만료/재활성화 UX 구현

주의:

- 최신 v2.5.0 흐름에서는 ML HTTP callback이 아니라 RabbitMQ completion event가 deactivate
  트리거다.
- 기존 `RAG_BFF_ADMIN_KEY_REVOKE_URL` 계열 설정은 legacy compatibility로만 취급한다.

### 19.2 infra

남은 항목:

- Qdrant 운영 endpoint
- MongoDB 운영 URI
- MySQL 운영 URI
- RabbitMQ 운영 URL
- OpenAI API Key secret 주입
- worker process 배포 위치
- `/metrics` 수집 설정

### 19.3 Confluence ACL 강화

남은 항목:

- page-level restriction이 비어 있는 경우 상위 folder/page/space permission 조회 여부 결정
- 상위 권한과 page restriction 결합 방식 결정
  - union
  - intersection
  - inherited permission model
- Confluence group id/name과 BFF `groups` claim 매핑 최종 확정

### 19.4 실제 운영 smoke

backend OAuth가 준비된 뒤 수행할 항목:

- production `AtlassianSourceAdapter` 경로로 실 Confluence ingestion smoke
- Admin Key 활성화 -> RabbitMQ ingest job 또는 `/ml/ingest` 위임 -> completion event -> BFF
  consumer -> auth-server deactivate -> Admin Key 말소 확인
- Qdrant/Mongo/MySQL/RabbitMQ 실 adapter 연결 확인
- 일반 사용자 query에서 권한 없는 문서가 검색되지 않는지 확인

### 19.5 평가

남은 항목:

- `evaluation_set.json`을 최종 평가 set으로 반영
- Precision@K, citation accuracy, hallucination/faithfulness 지표 실행
- LLM custom metric 운영화

## 20. 이후 작업 시작 규칙

앞으로 새 작업은 항상 최신 `main`에서 시작한다.

```bash
cd /Users/younghoonlee/workspace_git/ai-agent
git switch main
git pull
git switch -c feat/<작업명>
```

기존 참고 브랜치:

```text
feat/#1/data-ingestion
```

이 브랜치는 최초 MVP 구현 기준점이다. 당장 삭제하지 않고 보존 중이며, 초기 구현 대비 비교가 필요할 때 사용할 수 있다.

## 21. 원본 로그와의 관계

이 파일은 세 원본 로그의 통합 정리본이다.

원본별 역할:

- `AI_AGENT_INTEGRATION_STRATEGY.md`
  - 최초 ai-agent/ingestion/rag 구조 비교
  - 통합 전략과 충돌 지점 분석
  - rag base + ingestion 수동 병합 전략 제안

- `AGENT_INTEGRATION_PROGRESS.md`
  - 2026-05-29~2026-06-02 사이 실제 통합 진행 로그
  - 테스트 환경 구성
  - ingestion/rag baseline
  - ai-agent 통합 브랜치 작업
  - api-spec v2.3.0 반영
  - Confluence Admin Key/ACL seam 구현

- `AI_AGENT_V2_4_ALIGNMENT_LOG.md`
  - 2026-06-05 최신 팀원 레포 기준 정합 작업
  - api-spec v2.4.0 반영
  - soft-delete/webhook
  - document analyzer
  - BFF revoke callback
  - smoke scripts

이 최종 로그는 작업 흐름 파악용이다. 세부 코드 diff나 원문 수준의 명령 출력이 필요하면 원본 로그와 Git commit history를 함께 확인한다.
