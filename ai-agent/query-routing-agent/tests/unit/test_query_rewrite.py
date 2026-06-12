"""ai-agent/query-routing-agent/tests/unit/test_query_rewrite.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import json

from query_routing_agent.config import QueryRoutingConfig
from query_routing_agent.llm import IntentClassificationResult
from query_routing_agent.routing import normalize_routing_input, rewrite_queries
from query_routing_agent.schemas import IntentLabel


def _normalized_input(
    *,
    query: str = "IAM 정책 수정 장애 상황에서 롤백 절차는?",
):
    return normalize_routing_input(
        {
            "conversation_id": "conversation-synthetic",
            "user_id": "user-synthetic",
            "original_question": "그럼 롤백은?",
            "query": query,
            "history_decision": "follow_up",
            "preserved_context": {
                "summary": "IAM policy incident context",
                "entities": ["IAM", "rollback"],
                "turn_refs": ["turn-1", "turn-2"],
            },
            "reset_required": False,
            "metadata": {"groups": ["ops-team"], "space_keys": ["OPS"]},
            "history": [
                {"role": "user", "content": "raw full conversation must not pass"}
            ],
        }
    )


def _classification(
    intent: IntentLabel,
    expanded_queries: list[object] | None = None,
) -> IntentClassificationResult:
    raw_hints = {}
    if expanded_queries is not None:
        raw_hints["expanded_queries"] = expanded_queries
    return IntentClassificationResult(
        intent=intent,
        confidence=0.82,
        reason="Synthetic routing reason.",
        raw_hints=raw_hints,
    )


def test_llm_expanded_queries_are_normalized_to_three_queries() -> None:
    result = rewrite_queries(
        normalized_input=_normalized_input(),
        classification=_classification(
            IntentLabel.INCIDENT_RESPONSE,
            [
                " IAM 정책 수정 장애 롤백 절차 ",
                "",
                "IAM 정책 수정 장애 롤백 절차",
                "IAM policy rollback troubleshooting",
                42,
            ],
        ),
        config=QueryRoutingConfig(),
    )

    assert result.expanded_queries[0] == "IAM 정책 수정 장애 롤백 절차"
    assert len(result.expanded_queries) == 3
    assert result.expanded_queries.count("IAM 정책 수정 장애 롤백 절차") == 1
    assert "IAM policy rollback troubleshooting" in result.expanded_queries
    assert any(warning.code == "expanded_queries_normalized" for warning in result.warnings)


def test_expanded_queries_are_trimmed_to_max_query_count() -> None:
    result = rewrite_queries(
        normalized_input=_normalized_input(),
        classification=_classification(
            IntentLabel.OPERATIONS_GUIDE,
            [
                "query one",
                "query two",
                "query three",
                "query four",
                "query five",
                "query six",
            ],
        ),
        config=QueryRoutingConfig(default_query_count=3, max_query_count=5),
    )

    assert result.expanded_queries == [
        "query one",
        "query two",
        "query three",
        "query four",
        "query five",
    ]
    assert any(warning.code == "expanded_queries_trimmed" for warning in result.warnings)


def test_all_invalid_queries_fall_back_to_original_query() -> None:
    result = rewrite_queries(
        normalized_input=_normalized_input(),
        classification=_classification(IntentLabel.UNKNOWN, ["", None, "   "]),
        config=QueryRoutingConfig(),
    )

    assert result.expanded_queries[0] == "IAM 정책 수정 장애 상황에서 롤백 절차는?"
    assert len(result.expanded_queries) == 3
    assert any(warning.code == "expanded_queries_fallback" for warning in result.warnings)


def test_preserved_context_is_used_for_query_enrichment() -> None:
    result = rewrite_queries(
        normalized_input=_normalized_input(query="롤백 절차는?"),
        classification=_classification(IntentLabel.INCIDENT_RESPONSE),
        config=QueryRoutingConfig(),
    )

    joined = " ".join(result.expanded_queries)
    assert "IAM" in joined
    assert "rollback" in joined
    assert "IAM policy incident context" not in joined
    assert "raw full conversation" not in json.dumps(result.to_safe_dict())


def test_intent_specific_hints_are_applied() -> None:
    scenarios = [
        (IntentLabel.INCIDENT_RESPONSE, ("장애", "롤백", "troubleshooting")),
        (IntentLabel.OPERATIONS_GUIDE, ("절차", "가이드")),
        (IntentLabel.POLICY_PROCEDURE, ("정책", "절차", "근거")),
        (IntentLabel.HISTORY_LOOKUP, ("이력", "변경", "날짜")),
    ]

    for intent, expected_terms in scenarios:
        result = rewrite_queries(
            normalized_input=_normalized_input(),
            classification=_classification(intent),
            config=QueryRoutingConfig(),
        )

        joined = " ".join(result.expanded_queries)
        assert any(term in joined for term in expected_terms)


def test_unknown_intent_keeps_original_query_centered_fallback() -> None:
    result = rewrite_queries(
        normalized_input=_normalized_input(),
        classification=_classification(IntentLabel.UNKNOWN),
        config=QueryRoutingConfig(),
    )

    assert result.expanded_queries[0] == "IAM 정책 수정 장애 상황에서 롤백 절차는?"
    assert len(result.expanded_queries) == 3
    assert any("IAM" in query for query in result.expanded_queries)


def test_too_long_query_is_limited_with_warning() -> None:
    long_query = "긴검색어 " * 80

    result = rewrite_queries(
        normalized_input=_normalized_input(query="기본 질문"),
        classification=_classification(IntentLabel.UNKNOWN, [long_query]),
        config=QueryRoutingConfig(),
    )

    assert len(result.expanded_queries[0]) <= 180
    assert any(warning.code == "expanded_query_truncated" for warning in result.warnings)


def test_rewrite_result_does_not_expose_sensitive_values() -> None:
    result = rewrite_queries(
        normalized_input=_normalized_input(query="OPENAI_API_KEY Authorization secret"),
        classification=_classification(
            IntentLabel.UNKNOWN,
            ["OPENAI_API_KEY Authorization secret"],
        ),
        config=QueryRoutingConfig(),
    )

    serialized = json.dumps(result.to_safe_dict())
    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "secret" not in serialized.lower()
