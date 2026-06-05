# Atlassian / Confluence API (구현 참조)

이 문서는 `Atlassian API 명세서`를 RAG 파이프라인 구현 관점에서 정리한 참조 문서다.
백엔드(BFF)가 아직 구축되지 않아, PoC에서는 **ML 파이프라인(본 저장소)이 Atlassian REST API를
`atlassian-python-api` 라이브러리로 직접 호출**한다. OAuth 인증·토큰 관리는 Authorization Server
(Spring Security OAuth2 Client)가 담당하며, 본 저장소는 발급된 `access_token`을 전달받아 사용한다.

---

## 책임 경계

| 영역 | 담당 | API |
|---|---|---|
| 인증 (OAuth 2.0 3LO) | Authorization Server (Spring) | `AUTH-01~04` — 로그인 리다이렉트 / 토큰 교환 / 토큰 갱신 / accessible-resources |
| 데이터 수집 | **ML 파이프라인 (본 저장소)** | `DATA-01~04` — 페이지 목록 / CQL 검색 / Space 목록 / content restriction 조회 |

본 저장소는 `access_token` + `cloudid`를 입력으로 받아 데이터 수집 API를 호출한다.
모든 데이터 수집 요청에 `Authorization: Bearer {access_token}` 헤더가 필요하다.

## 임시 Confluence Basic Auth smoke

백엔드 OAuth 구현 전에는 production ingestion adapter에 API Token Basic Auth를 섞지 않고,
별도 확인 스크립트로 실제 Confluence/Admin Key 동작만 검증한다.

```bash
export CONF_BASE_URL="https://<site>.atlassian.net/wiki"
export ATLASSIAN_EMAIL="<admin-email>"
export ATLASSIAN_API_TOKEN="<atlassian-api-token>"

echo "$CONF_BASE_URL"
echo "$ATLASSIAN_EMAIL"
echo ${#ATLASSIAN_API_TOKEN}

python scripts/smoke_confluence_basic.py --limit 250 --sample-page-id "<restricted-page-id>"
```

이 smoke가 확인하는 항목:

- `/api/v2/pages?limit={n}&body-format=storage` 일반 호출 결과 수
- 같은 API에 `Atl-Confluence-With-Admin-Key: true` header를 붙인 결과 수
- Admin Key header에서만 보이는 page id 목록
- sample page의 일반 호출 HTTP status와 Admin Key 호출 HTTP status
- `/rest/api/content/{pageId}/restriction/byOperation/read`의 user/group restriction 개수

이 스크립트는 read-only 확인 도구다. Admin Key 발급/말소는 수행하지 않는다. 운영 경로에서는
BFF/Auth Server가 OAuth access token과 Admin Key 수명주기를 관리하고, Data Ingestion Worker는
`adminUserId`로 auth-server 내부 credential API를 호출해 admin OAuth access token과 `cloudId`를
조회한다. RabbitMQ job/completion payload에는 credential set을 포함하지 않는다.

실제 API Token 값은 문서·코드·커밋에 남기지 않는다. 회의/채팅/로그에 노출된 token은
Atlassian에서 폐기하고 재발급한 뒤 환경변수로만 주입한다.

## 데이터 수집 API

API URL 형식: `https://api.atlassian.com/ex/confluence/{cloudid}/rest/api/...`
(`cloudid`는 `AUTH-04 accessible-resources` 응답의 `id`)

### DATA-01. 페이지 목록 조회 (Full Crawl)

`GET /content?type=page&spaceKey={key}&start={n}&limit={≤100}&expand=space,version,body.storage`

서비스 최초 구동 시 전체 문서를 Vector DB에 적재하기 위해 사용. `limit` 최대 100,
초과 시 `start`를 증가시키며 반복 호출(또는 `get_all_pages_from_space_as_generator()`).

### DATA-02. CQL 검색 (Delta Sync)

`GET /content/search?cql={query}&limit={≤100}&expand=body.storage,version,space`

1시간 주기 델타 싱크에 사용. 예: `space="ENG" AND type=page AND lastModified >= "2026-04-29 00:00"`.
`_links.next`가 있으면 커서 기반 다음 페이지 존재.

### DATA-03. Space 목록 조회 (사용자 권한 필터링)

`GET /space?start={n}&limit={≤500}`

로그인 사용자가 **접근 가능한 Space만** 반환된다(Confluence 권한 자동 적용).
PoC 단계의 스페이스 단위 ACL 합성(`space:{space_key}`)에 사용한다.

### DATA-04. Page read restriction 조회 (운영 ACL)

`GET /rest/api/content/{pageId}/restriction/byOperation/read`

Admin Key 테스트(2026-06-02)로 확인한 page-level read restriction 조회 API다.
페이지 본문 조회 응답(`/api/v2/pages`)에는 권한 정보가 직접 포함되지 않으므로,
페이지별 `allowed_users` / `allowed_groups`를 구성하려면 본 API를 별도 호출해야 한다.

Admin Key 사용 시 요청 header:

```text
Atl-Confluence-With-Admin-Key: true
```

응답 요약 형태:

```json
{
  "operation": "read",
  "restrictions": {
    "user": {
      "results": [
        {
          "accountId": "712020:...",
          "displayName": "신유진",
          "accountStatus": "active"
        }
      ],
      "size": 1
    },
    "group": {
      "results": [],
      "size": 0
    }
  }
}
```

단, page-level restriction이 비어 있어도 상위 folder/page restriction 또는 space permission 때문에
일반 사용자 조회에서 제외될 수 있다. 따라서 운영 ACL은 page restriction만으로 완결된다고
가정하지 않는다.

## 페이지 객체 → PageObject 매핑

`DATA-01/02` 응답의 페이지 객체는 `samples/confluence_sample_data.json`과 동일한 형식이다.

| Atlassian 필드 | PageObject 필드 | 비고 |
|---|---|---|
| `id` | `page_id` | Qdrant 문서 식별자 |
| `title` | `title` | |
| `body.storage.value` | `body_html` | HTML — BeautifulSoup 파싱 필요 |
| `version.number` | `version_number` | 멱등성 검사 |
| `version.when` | `last_modified` | ISO 8601 |
| `space.key` | `space_key` | |
| `metadata.labels.results[].name` | `labels[]` | |
| `ancestors[].{id,title}` | `ancestors[]` | |
| `_links.webui` | `webui_link` | 출처 카드 원본 링크 |
| `attachments[]` | `attachments[]` | 샘플 데이터에 메타만 존재 — 실제 다운로드/추출은 별도 |
| `restriction/byOperation/read.restrictions.group.results[]` | `allowed_groups[]` | 운영 ACL. PoC는 `["space:{space_key}"]` 합성 |
| `restriction/byOperation/read.restrictions.user.results[].accountId` | `allowed_users[]` | 운영 ACL. PoC는 빈 배열 |

## ACL 결정 (PoC A 유지, 운영 B 전환 준비 — ADR 0003 개정)

설계서·기획서 §6.6은 ACL을 청크별 `allowed_groups`/`allowed_users` Payload로 정의한다.
초기 PoC에서는 샘플 데이터와 기존 API 정리 문서에 page-level ACL 출처가 없어
`space_key` 기반 합성을 채택했다.

2026-06-02 Admin Key 실측 결과:

- 일반 API Token 조회: 232 pages
- Admin Key header 조회: 237 pages
- Admin Key에서만 보인 pages: 5개
- `7798794 | 영훈없음`: 일반 호출 `404`, Admin Key 호출 `200`
- 같은 page의 `restriction/byOperation/read` 응답에서 read 허용 user 3명 확인

따라서 현재 결정은 다음과 같이 정리한다.

- **PoC/샘플 경로:** 기존 `space_key` 기반 합성을 유지한다.
  - `allowed_groups=["space:{space_key}"]`
  - `allowed_users=[]`
- **운영 Confluence/Admin Key 경로:** page restriction API를 도입해 `allowed_users` /
  `allowed_groups`를 채우는 방향으로 전환한다.
- **restriction empty 정책:** page-level restriction이 비어 있을 때 기본값은
  `RAG_ATLASSIAN_EMPTY_RESTRICTION_POLICY=allow_authenticated`이다. 이 정책은
  `allowed_groups=[RAG_ATLASSIAN_PUBLIC_ACL_GROUP]`(기본 `"*"`)를 부여하고, RAG 검색은 동일
  sentinel을 모든 principal의 group 조건에 주입한다. 보수 운영이 필요하면 `mark_missing`으로
  바꿔 빈 ACL을 색인 단계에서 `INVALID_ACL`로 차단할 수 있다. PoC/데모에서 스페이스 단위
  접근을 허용하려면 `space_fallback`으로 바꿔 `allowed_groups=["space:{space_key}"]`를 합성할 수 있다.
- **미결:** 상위 folder/page restriction 또는 space permission을 실제로 추가 조회해 ACL을
  계산하는 운영 강화 로직은 별도 endpoint 명세와 BE/infra 협의 후 구현한다.

검색 필터(`app/query/acl.py:build_acl_filter`)는 이미 `allowed_groups OR allowed_users` 구조이므로,
수집 단계에서 ACL payload만 정확히 채우면 RAG 검색 계층은 추가 변경 없이 동작한다.

## Cloud ↔ Server/DC 전환

URL 3개(인증 요청 / 토큰 교환 / API 호출)만 환경 변수로 관리하면 코드 수정 없이 전환 가능
(`app/config.py`에서 관리).

## 공식 문서

- OAuth 2.0 3LO: https://developer.atlassian.com/cloud/confluence/oauth-2-3lo-apps/
- REST API v1: https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content/
- Admin Key / restrictions: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-admin-key/
- CQL: https://developer.atlassian.com/cloud/confluence/advanced-searching-using-cql/
