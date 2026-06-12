"""app.adapters — Document Source Adapter [Pipeline 경계].

작성자 : 이영훈
담당 영역 : ai-agent

RAG 파이프라인이 데이터 공급원에 직접 결합하지 않도록 하는 추상 인터페이스.
공급원이 무엇이든 동일한 표준 PageObject 스트림을 반환하도록 강제하며,
공급원 전환 시 어댑터 1개 클래스 + config의 source.type 1줄만 바뀐다.

백엔드(BFF)가 아직 없어, PoC에서는 본 저장소가 Atlassian REST API를 직접 호출한다.
운영 수집 경로는 ``adminUserId``로 auth-server 내부 credential API를 조회해
콘텐츠 조회용 ``accessToken``/``cloudId``와 출처 URL 정규화용 ``siteUrl``을 내부
request에 주입한다. Admin API Token은 auth-server의 Admin Key 활성화/말소 내부 용도이며
본 모듈의 §2-5 credential 결과로 전달되지 않는다.
상세: docs/atlassian-api.md.

모듈:
- base.py          DocumentSourceAdapter 추상 인터페이스 + ActiveIds / ChangeEvent
- json_fixture.py  JsonFixtureSourceAdapter — samples/*.json 읽기 (로컬 개발·테스트용) [구현 완료]
- factory.py       build_source_adapter — Settings.source_type 기반 어댑터 생성 [구현 완료]
- atlassian.py     AtlassianSourceAdapter — vendored Data Ingestion Agent workflow 연결 +
                   Confluence read restriction ACL provider seam
"""

from app.adapters.atlassian import (
    AtlassianSourceAdapter,
    ConfluenceRestrictionAclProvider,
    parse_empty_restriction_policy,
    parse_group_identifier_fields,
    parse_read_restrictions_acl,
)
from app.adapters.base import ActiveIds, ChangeEvent, DocumentSourceAdapter
from app.adapters.factory import (
    MissingAtlassianCredentialsError,
    UnsupportedSourceTypeError,
    build_source_adapter,
)
from app.adapters.json_fixture import JsonFixtureSourceAdapter

__all__ = [
    "ActiveIds",
    "AtlassianSourceAdapter",
    "ChangeEvent",
    "ConfluenceRestrictionAclProvider",
    "DocumentSourceAdapter",
    "JsonFixtureSourceAdapter",
    "MissingAtlassianCredentialsError",
    "UnsupportedSourceTypeError",
    "build_source_adapter",
    "parse_empty_restriction_policy",
    "parse_group_identifier_fields",
    "parse_read_restrictions_acl",
]
