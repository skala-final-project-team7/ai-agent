from __future__ import annotations

import json

import pytest

from query_routing_agent.config import QueryRoutingConfig
from query_routing_agent.routing import (
    build_filter_and_pool_weights,
    build_pool_weights,
    map_task_prompt_type,
    normalize_pool_weights,
    normalize_routing_input,
)
from query_routing_agent.schemas import IntentLabel, TaskPromptType


def _normalized_input(metadata: dict | None = None):
    return normalize_routing_input(
        {
            "conversation_id": "conversation-synthetic",
            "user_id": "user-synthetic",
            "original_question": "그럼 롤백은?",
            "query": "IAM 정책 수정 장애 상황에서 롤백 절차는?",
            "history_decision": "follow_up",
            "preserved_context": {},
            "reset_required": False,
            "metadata": metadata or {},
        }
    )


def test_metadata_and_acl_values_are_mapped_to_canonical_filter() -> None:
    normalized = _normalized_input(
        {
            "space_keys": ["OPS", "RUNBOOK"],
            "groups": ["ops-team", "platform-team"],
            "labels": ["incident", "rollback"],
            "document_types": ["page"],
            "source_types": ["confluence"],
            "date_range": {"from": "2026-01-01", "to": "2026-05-15"},
            "attachment_required": True,
        }
    )

    result = build_filter_and_pool_weights(
        normalized_input=normalized,
        intent=IntentLabel.INCIDENT_RESPONSE,
        config=QueryRoutingConfig(),
    )

    filters = result.metadata_filter.to_dict()
    assert filters["space_keys"] == ["OPS", "RUNBOOK"]
    assert filters["labels"] == ["incident", "rollback"]
    assert filters["document_types"] == ["page"]
    assert filters["source_types"] == ["confluence"]
    assert filters["date_range"] == {"from": "2026-01-01", "to": "2026-05-15"}
    assert filters["attachment_required"] is True
    assert filters["acl"] == {
        "user_id": "user-synthetic",
        "groups": ["ops-team", "platform-team"],
    }
    assert "allowed" not in filters["acl"]
    assert "denied" not in filters["acl"]


def test_missing_acl_groups_warns_without_enforcement() -> None:
    result = build_filter_and_pool_weights(
        normalized_input=_normalized_input({"space_keys": ["OPS"]}),
        intent=IntentLabel.UNKNOWN,
        config=QueryRoutingConfig(),
    )

    acl = result.metadata_filter.to_dict()["acl"]
    assert acl == {"user_id": "user-synthetic", "groups": []}
    assert any(warning.code == "acl_groups_missing" for warning in result.warnings)
    assert "enforcement" not in json.dumps(result.to_safe_dict()).lower()


def test_invalid_metadata_filter_values_fall_back_safely() -> None:
    result = build_filter_and_pool_weights(
        normalized_input=_normalized_input(
            {
                "labels": {"invalid": "shape"},
                "document_types": 123,
                "source_types": None,
                "date_range": "not-a-date-range",
                "attachment_required": "yes",
            }
        ),
        intent=IntentLabel.OPERATIONS_GUIDE,
        config=QueryRoutingConfig(),
    )

    filters = result.metadata_filter.to_dict()
    assert filters["labels"] == []
    assert filters["document_types"] == []
    assert filters["source_types"] == []
    assert filters["date_range"] == {"from": None, "to": None}
    assert filters["attachment_required"] is False
    assert {warning.code for warning in result.warnings} >= {
        "metadata_labels_dropped",
        "metadata_document_types_dropped",
        "metadata_date_range_dropped",
        "metadata_attachment_required_dropped",
    }


@pytest.mark.parametrize(
    ("intent", "expected_prompt_type"),
    [
        (IntentLabel.INCIDENT_RESPONSE, TaskPromptType.TIMELINE),
        (IntentLabel.OPERATIONS_GUIDE, TaskPromptType.STEP_BY_STEP),
        (IntentLabel.POLICY_PROCEDURE, TaskPromptType.EVIDENCE_FIRST),
        (IntentLabel.HISTORY_LOOKUP, TaskPromptType.HISTORY_SUMMARY),
        (IntentLabel.UNKNOWN, TaskPromptType.GENERAL),
    ],
)
def test_intent_maps_to_task_prompt_type(
    intent: IntentLabel,
    expected_prompt_type: TaskPromptType,
) -> None:
    assert map_task_prompt_type(intent) == expected_prompt_type


@pytest.mark.parametrize(
    ("intent", "expected_weights"),
    [
        (IntentLabel.INCIDENT_RESPONSE, {"title": 0.2, "content": 0.65, "label": 0.15}),
        (IntentLabel.OPERATIONS_GUIDE, {"title": 0.25, "content": 0.6, "label": 0.15}),
        (IntentLabel.POLICY_PROCEDURE, {"title": 0.3, "content": 0.6, "label": 0.1}),
        (IntentLabel.HISTORY_LOOKUP, {"title": 0.2, "content": 0.5, "label": 0.3}),
        (IntentLabel.UNKNOWN, {"title": 0.25, "content": 0.6, "label": 0.15}),
    ],
)
def test_intent_builds_expected_pool_weights(
    intent: IntentLabel,
    expected_weights: dict[str, float],
) -> None:
    weights, warnings = build_pool_weights(intent, QueryRoutingConfig())

    assert warnings == []
    assert weights.to_dict() == expected_weights
    assert weights.total == pytest.approx(1.0)


def test_pool_weights_are_normalized_to_sum_one() -> None:
    weights, warnings = normalize_pool_weights({"title": 2, "content": 6, "label": 2})

    assert weights.to_dict() == {"title": 0.2, "content": 0.6, "label": 0.2}
    assert weights.total == pytest.approx(1.0)
    assert any(warning.code == "pool_weights_normalized" for warning in warnings)


@pytest.mark.parametrize(
    "raw_weights",
    [
        {"title": -1, "content": 1, "label": 0},
        {"title": 0, "content": 0, "label": 0},
        {"title": "invalid", "content": 1, "label": 1},
    ],
)
def test_invalid_pool_weights_fall_back_to_default(raw_weights: dict) -> None:
    weights, warnings = normalize_pool_weights(raw_weights)

    assert weights.to_dict() == {"title": 0.25, "content": 0.6, "label": 0.15}
    assert any(warning.code == "pool_weights_defaulted" for warning in warnings)


def test_result_warning_and_error_strings_do_not_expose_sensitive_values() -> None:
    result = build_filter_and_pool_weights(
        normalized_input=_normalized_input(
            {
                "labels": ["OPENAI_API_KEY"],
                "groups": ["Authorization"],
                "space_keys": ["secret"],
            }
        ),
        intent=IntentLabel.UNKNOWN,
        config=QueryRoutingConfig(),
    )

    serialized = json.dumps(result.to_safe_dict())
    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "secret" not in serialized.lower()
