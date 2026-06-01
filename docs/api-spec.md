# API Spec

이 문서는 RAG 파이프라인이 BFF에 노출하는 **내부 API 계약(BFF → ML 서버)**을 정의한다.
BE 통합 API 스펙(`api-spec-BE-adjust.md`, 2026-05-21 전달) §2-1 `/ml/query` 및 §1-1
SSE 이벤트 형식과 정합한다. API 변경 시 이 문서를 함께 수정한다(루트 `CLAUDE.md` 규칙).

> 인증/JWT 발급·Gateway 라우팅·대화/메시지 영속화·피드백·미리보기 등 FE↔BFF 외부 API는
> BFF/BE 담당 영역이다(`api-spec-BE-adjust.md` §1 참조). 본 파이프라인은 BFF가 전달한
> `userId`/`groups`로 ACL 필터를 만들고 `spaceKey`로 검색 범위를 제한한다.

> **변경 이력**
> - 2026-05-22, feature13 — BE 통합 스펙 반영(문서). 엔드포인트 `/api/v1/rag/query` → `/ml/query`,
>   요청 본문 재정의, SSE 이벤트 형식 변경(token=`{content}`, sources 래핑+필드 변경,
>   verification 집계, done=`{}`, error 신규).
> - 2026-05-26, feature13 — **코드 마이그레이션 완료.** 위 목표 계약을 `app/api/routes.py`·
>   `app/schemas/response.py`·`app/schemas/enums.py`·`app/schemas/rag_state.py` 에 반영해
>   구현 엔드포인트가 `/ml/query` 로 전환됨. `spaceKey` 는 RagState passthrough(검색 필터
>   반영은 후속). PDF #3(ACL 컬럼 정합)은 BE 확정 대기로 별도.
> - 2026-05-26, feature13 — **api-spec v2.2.0 대조 정합.** (1) `meta` 이벤트 유지(현재 구현
>   호환용 — 05-21 BE-adjust 의 'meta 제거'는 아직 *예정* 단계라 되돌림, `title` 은 ML 미생성
>   으로 생략), (2) sources 필드명 `updatedAt` → `sourceUpdatedAt`, (3) `accessToken`/`cloudId`
>   는 v2.2.0 에서 `/ml/query` 가 아닌 수집(`/ml/ingest`)으로 이관됨 — 요청 본문에서 제거.
> - 2026-05-29, **api-spec v2.2.0(문서 버전) 코드 정합 보강.** 업로드된 v2.2.0 대조 후 다음
>   코드 변경을 반영: (1) 요청 `spaceKey` 를 실제 검색 **하드 스코프**(Qdrant `space_key`
>   AND, 0건 fallback 에서도 미완화)로 적용 — 기존 RagState passthrough 해소
>   (`app/query/search_node.py`). (2) 챗 엔드포인트 **항상 스트리밍** — 클라이언트 `stream`
>   요청 필드 제거(비-스트리밍 모드 미제공), 스트리밍/비-streaming 선택은 서버 내부 PoC
>   가용성으로만 결정(`app/api/routes.py`). (3) SSE 이벤트 순서 불변식 #2 — 검증 차단 분기의
>   대체 `token` 을 `verifying` status **이전**에 송신하도록 재배치. (4) SSE 응답 헤더
>   `Cache-Control: no-cache` 명시. (5) `history[].role` 을 Enum 정책의 UPPER(`USER`/
>   `ASSISTANT`)로 정규화(`app/schemas/rag_state.py`). (6) `ErrorResponse` 를 공통 Wrapper
>   4필드 봉투(`isSuccess`/`code`/`errorCode`/`message`)로 재정의(`app/api/errors.py`).

---

## POST /ml/query  (BFF → ML)

사용자 질의를 받아 ACL 기반 검색 → 답변 생성 → 출처 검증을 수행하고 답변·출처를 SSE로
스트리밍한다. BFF는 이 응답을 FE의 `POST /api/conversations/{conversationId}/chat` 으로
그대로 중계하며, `done` 이벤트에 DB 메시지 UUID(`messageId`)를 주입한다.

- 응답 방식: `text/event-stream` (SSE). **Common Response Wrapper 미적용**(BE 스펙 §Common 예외).
- 인증: BFF가 JWT에서 `userId`/`groups`를 추출해 본문으로 전달한다. **ML은 JWT를 직접 검증하지 않는다.**
- Gateway 타임아웃: SSE 특성상 60초 별도 설정(BE 스펙 §1-1).

### Request Body

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `question` | string | Y | 사용자 자연어 질문 |
| `conversationId` | string | N | 대화 컨텍스트 ID |
| `history` | array | N | 이전 대화 이력 `[{ "role": "USER"\|"ASSISTANT", "content": "..." }]`. BFF가 DB에서 조회해 전달(멀티턴). `role` 값은 Enum 정책의 UPPER(`USER`/`ASSISTANT`) |
| `userId` | string | Y | ACL Pre-filtering 사용자 식별자(BFF가 JWT에서 추출, 2단계 데모는 고정값) |
| `groups` | string[] | Y | 사용자 그룹 — ACL `should`-OR 필터 |
| `spaceKey` | string | Y | 검색 대상 Confluence 스페이스. 2단계는 고정값(`lina.demo.fixed-space-key`) |

```json
{
  "question": "지난번 S3 버킷 권한 오류 때 어떻게 해결했어?",
  "conversationId": "conv-uuid-001",
  "history": [
    { "role": "USER", "content": "S3 관련 장애 이력 알려줘" },
    { "role": "ASSISTANT", "content": "최근 S3 관련 장애는 3건이 있었습니다..." }
  ],
  "userId": "user-001",
  "groups": ["Cloud-Control-Center"],
  "spaceKey": "CPC"
}
```

> **`accessToken`/`cloudId` 미수신 (api-spec v2.2.0, 2026-05-22 변경)** — 권한은 수집 시 Qdrant
> payload(`allowed_groups`/`allowed_users`)에 ACL로 저장되고 질의 시 `userId`/`groups`로
> 필터링한다. `/ml/query` 는 라이브 Confluence 호출이 없어 토큰이 불필요하며, 토큰은 수집
> 단계(`/ml/ingest`)에서만 전달한다. (현재 `QueryRequest` 는 두 필드를 받지 않는다.)

### SSE 이벤트 순서

1. `token` 이벤트 (n회) — 답변 텍스트 청크
2. `sources` 이벤트 (1회) — 출처 카드 배열
3. `verification` 이벤트 (1회) — 답변 신뢰도 검증(집계)
4. `meta` 이벤트 (1회) — 현재 구현 호환용 메타데이터(아래 참고)
5. `done` 이벤트 (1회) — 스트림 종료 마커
- 오류 시: 위 순서 대신 `error` 이벤트로 전달하고 스트림을 종료한다.
- **순서 불변식 (v2.2.0 §1-1 #2)**: 모든 `token` 은 `verifying` phase **이전에 연속** 송신되며
  이후에는 `token` 이 오지 않는다. 본문 종료 후 `sources` → `verification` → `meta` → `done`
  순으로 각 최대 1회. 검증 차단으로 답변이 대체되는 경우에도 대체 `token` 은 `verifying`
  status 이전에 송신한다(`app/api/routes.py` 스트리밍 경로).
- 진행 표시용 `status` 이벤트(아래 "진행 status 이벤트")가 위 이벤트들 사이사이에 추가로
  송신될 수 있다. `status`는 *추가 전용* 이벤트이므로, 이를 무시하는 클라이언트는 위 5종
  이벤트만으로 기존과 동일하게 동작한다.

> **`meta` 이벤트 (현재 구현 호환용, api-spec v2.2.0 §1-1)** — `intent` / `used_llm` /
> `feedback_enabled` / `latency_ms` (+ optional `title`)를 `done` 직전 1회 송신한다. FE는 현재
> `title`만 대화 제목 갱신에 사용한다. **본 ML 구현은 `title`을 생성하지 않으므로 생략**한다
> (스펙상 optional). BE 통합 목표 계약에서는 추후 제거 예정이며, 그때 `intent`/`used_llm`/
> `latency_ms`는 ML 내부 메트릭으로, 저신뢰 신호는 `verification.confidenceScore`로 대체한다.

#### `token`
```
event: token
data: {"content": "S3 권한 오류는"}
```
- `data`는 JSON 객체 `{"content": "<청크 텍스트>"}`. 프론트는 `content`를 누적 렌더링한다.

#### `sources`
```jsonc
event: sources
data: {
  "sources": [
    {
      "title": "page_title > section_header",
      "pageId": "12345",
      "spaceId": "98310",
      "spaceName": "Cloud Control Center",
      "url": "https://confluence.example.com/pages/12345#anchor",
      "sourceUpdatedAt": "2026-04-15T18:30:00+09:00",   // KST(+09:00)
      "relevanceScore": 0.92                            // 0~1 (Cross-Encoder score/100)
    }
  ]
}
```
- 배열은 `{"sources": [...]}`로 래핑된다.
- `relevanceScore`는 0~1 float(기존 0~100 정수 `score`를 100으로 나눈 값).
- `sourceUpdatedAt`은 KST(`+09:00`) 절대 전환(BE 스펙 §시간 표기 정책, api-spec v2.2.0 필드명).
- 첨부 출처(`sourceType="attachment"`)는 `attachmentFilename`, `attachmentMime`, `downloadUrl`
  을 추가로 포함한다. 본문 출처는 기존 필드만 포함한다.

#### `verification`
```jsonc
event: verification
data: { "confidenceScore": 0.85, "verificationResult": "SUPPORTED" }
```
- `verificationResult`: `SUPPORTED` | `PARTIALLY_SUPPORTED` | `NOT_SUPPORTED`
- **집계 규칙** (문장별 1+2단계 결과 → 단일 값):
  - `NOT_SUPPORTED` 비율 > 0.5 → `NOT_SUPPORTED` (답변 차단 분기와 동일 임계)
  - 그 외 `NOT_SUPPORTED` 문장이 1개 이상 존재 → `PARTIALLY_SUPPORTED`
  - 전 문장이 `PASS`/`SUPPORTED` → `SUPPORTED`
- **`confidenceScore`(0~1)**: `(PASS+SUPPORTED 문장 수) / (전체 문장 수)`. 문장 0개면 `0.0`.
  (휴리스틱 — 운영 튜닝 가능. 저신뢰 경고 배지의 기준값으로 FE가 사용)

#### `meta`
```jsonc
event: meta
data: {"intent": "운영가이드", "used_llm": "gpt-4o", "feedback_enabled": true, "latency_ms": 1234}
```
- 현재 구현 호환용(api-spec v2.2.0 §1-1). `verification` 직후 `done` 직전 1회 송신.
- 필드: `intent` / `used_llm` / `feedback_enabled` / `latency_ms`. 스펙상 optional 인 `title`은
  **본 ML 구현이 생성하지 않아 생략**한다(FE는 `title` 부재 시 대화 제목을 갱신하지 않는다).
- 추후 BE 통합 목표 계약에서 제거 예정 — 그때 값은 ML 내부 메트릭/`confidenceScore`로 대체.

#### `done`
```
event: done
data: {}
```
- ML은 `done`을 빈 객체 `{}`로 emit한다. **`messageId`는 BFF가 DB 메시지 UUID로 주입**해
  FE에 `{"messageId": "msg-uuid-001"}` 형태로 중계한다(ML은 messageId를 생성하지 않는다).

#### `error`
```
event: error
data: {"errorCode": "ML_SERVER_ERROR", "message": "답변 생성 중 오류가 발생했습니다"}
```
- 오류는 HTTP 에러 응답이 아니라 **SSE `error` 이벤트**로 전달하고 스트림을 종료한다.
- `data`는 `{"errorCode": string, "message": string}` (api-spec v2.2.0 §1-1). 필드명은
  `errorCode`다 — 공통 Wrapper 의 정수 `code`와 혼동 금지(SSE 에는 HTTP 정수 code 가 없다).
- `errorCode`: `ML_SERVER_ERROR`(ML 5xx·내부 처리 오류) | `ML_TIMEOUT`(응답/스트림 타임아웃,
  `lina.rag.sse-timeout-ms`) | `ML_CONNECTION_ERROR`(연결 실패·스트림 중단). 구현은
  `app/api/routes.py` `_classify_ml_error` 가 상류 예외를 이 3종으로 분류한다.
- `RETRIEVAL_EMPTY` / `LOW_CONFIDENCE` / `VERIFICATION_BLOCKED`는 `error` 이벤트가 아니라 아래
  "표준 분기 응답"처럼 정상 200 SSE 흐름 내부에서 처리한다(`error` 는 본격 오류에만 사용).

### 진행 status 이벤트 (feature19)

답변 토큰 전/중에 RAG 라이프사이클 단계(연결 → 검색 → 답변 → 검증 …) 진입을 프론트에 push하는
진행 표시용 이벤트다. **기존 `token`/`sources`/`verification`/`meta`/`done` 이벤트와 별개로 *추가*되며,
이름·순서·형식은 무변경이다.** `status`를 무시하는 클라이언트는 기존과 동일하게 동작한다.

```
event: status
data: {"phase": "searching", "message": "관련 문서를 검색하고 있어요"}
```

- `data`는 JSON 객체 `{"phase": "<phase>", "message": "<한국어 진행 메시지>"}` (다른 JSON
  이벤트와 동일하게 `ensure_ascii=False` 직렬화).
- 각 phase는 해당 단계 진입 시 1회 송신된다.
- **운영 streaming 경로(OpenAI 가용)에만 적용**된다. 챗 엔드포인트는 항상 스트리밍이지만
  (클라이언트 `stream` 필드 없음), PoC 환경(OpenAI 키/generator_provider 없음)은 그래프를 단일
  블로킹 호출로 실행한 뒤 모든 이벤트를 한꺼번에 flush 하므로(phase 동시 발사 — 진행 표시 가치
  없음) `status` 를 송신하지 않는다.

| phase | message(예) | 송신 시점 |
|---|---|---|
| `connecting` | 연결 중이에요 | 스트림 진입 |
| `acl_filtering` | 접근 권한을 확인하고 있어요 | ACL 필터 확인 단계 |
| `searching` | 관련 문서를 검색하고 있어요 | 그래프 검색(history/router/search/rerank 통합) 직전 |
| `answering` | 답변을 준비하고 있어요 | LLM 답변 생성 호출 직전 |
| `streaming` | 답변을 작성하고 있어요 | 첫 `token` chunk 송신 직전 |
| `verifying` | 답변 근거를 검증하고 있어요 | 답변 검증(1+2단계) 직전 |
| `formatting` | 답변을 정리하고 있어요 | 응답 포맷팅 → `sources`/`verification` 송신 직전 |

- 정상 흐름 순서: `connecting` → `acl_filtering` → `searching` → `answering` → `streaming` →
  `verifying` → `formatting`.
- 검색 0건(`RETRIEVAL_EMPTY`) 분기는 `answering`/`streaming`/`verifying`을 건너뛰고 `searching`
  다음 `formatting`으로 직행한다.
- `done`/`error`는 별도 status phase로 만들지 않는다 — 기존 `done` 이벤트와 에러 처리(SSE
  `error` 이벤트 / HTTP 에러)로 표현한다. 즉 `status`로는 진행 phase(`connecting`~`formatting`)만
  송신한다.

> **참고**: 그래프 내부 4단계(history/router/search/rerank)는 현재 단일 블로킹 호출 안에서
> 실행되므로 절충안으로 `searching` 단일 phase로 통합해 송신한다. 4단계 세분화가 필요해지면
> 그래프 호출을 노드 단위 스트리밍으로 전환하는 별도 작업으로 다룬다.

### 표준 분기 응답 (정상 SSE 흐름 내부)

| 상황 | 처리 |
|---|---|
| ACL 결과 후보 0건 | "권한 범위 내에서 참고할 수 있는 문서를 찾지 못했습니다" 표준 응답을 `token`으로 송신, LLM 미호출. `verification.confidenceScore`를 낮게, `verificationResult=NOT_SUPPORTED`로 보고 |
| Cross-Encoder Top-5 최고 score < 55 (0.55) | 저신뢰 분기 — 출처를 '참고용'으로 제시. `confidenceScore`를 낮게 반영(FE가 경고 배지 표시) |
| `verification` 중 `NOT_SUPPORTED` 비율 > 50% | 답변 차단, 저신뢰 응답으로 대체, `verificationResult=NOT_SUPPORTED`, 운영 긴급 알림 |

---

## 내부 인터페이스 (참고)

다음은 외부 API는 아니지만 파이프라인 경계에서 동결되는 계약이다.

- **PageObject** — Document Source Adapter → Ingestion 파이프라인 입력. `docs/rag-pipeline-design.md` §7.1
- **DocumentSourceAdapter** — `fetch_pages()` / `list_active_ids()` / `watch_changes()`. 구현은 백엔드 책임

> 데이터 수집 트리거/상태/헬스체크(`/ml/ingest`, `/ml/ingest/status/{jobId}`,
> `/ml/rag/health`, `/ml/ingest/health`)는 `api-spec-BE-adjust.md` §2-2~§2-4 정합으로
> 별도 정의한다(Ingestion 파이프라인 영역).

---

## 변경 규칙

- 엔드포인트·요청/응답 필드 변경 시 이 문서와 `api-spec-BE-adjust.md`(BE 통합 스펙) 정합을 유지한다.
- 응답에서 출처(`sources`)·검증(`verification`)은 제거하지 않는다(출처 기반·검증 가능성 원칙).
- SSE 이벤트 순서·이름·`data` 형식 변경은 BFF/프론트 영향이 있으므로 Plan에 영향 범위를 명시하고
  사전 협의한다.
