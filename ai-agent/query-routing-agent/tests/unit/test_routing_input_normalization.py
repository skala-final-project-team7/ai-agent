from __future__ import annotations

import json
from pathlib import Path

import pytest

from query_routing_agent.routing import (
    RoutingInputLoadError,
    RoutingInputValidationError,
    load_history_manager_output,
    load_and_normalize_routing_input,
    normalize_routing_input,
)
from query_routing_agent.schemas import HistoryDecisionLabel


def _valid_payload() -> dict[str, object]:
    return {
        "conversation_id": "conversation-synthetic",
        "user_id": "user-synthetic",
        "original_question": "그럼 롤백은?",
        "query": "IAM 정책 수정 장애 상황에서 롤백 절차는?",
        "history_decision": "follow_up",
        "preserved_context": {
            "summary": "IAM policy incident context",
            "entities": ["IAM"],
            "turn_refs": ["turn-1"],
        },
        "reset_required": False,
        "metadata": {
            "locale": "ko-KR",
            "groups": ["ops-team"],
            "space_keys": ["OPS"],
        },
    }


def test_loads_valid_history_manager_output_json(tmp_path: Path) -> None:
    input_path = tmp_path / "history_manager_output.json"
    input_path.write_text(json.dumps(_valid_payload()), encoding="utf-8")

    result = load_and_normalize_routing_input(input_path)

    assert result.routing_input.conversation_id == "conversation-synthetic"
    assert result.routing_input.query == "IAM 정책 수정 장애 상황에서 롤백 절차는?"
    assert result.routing_input.history_decision == HistoryDecisionLabel.FOLLOW_UP
    assert result.routing_input.preserved_context.entities == ["IAM"]
    assert result.acl_filter.to_dict() == {
        "user_id": "user-synthetic",
        "groups": ["ops-team"],
    }
    assert result.warnings == []


def test_malformed_json_raises_clear_loader_error(tmp_path: Path) -> None:
    input_path = tmp_path / "malformed.json"
    input_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(RoutingInputLoadError, match="malformed JSON"):
        load_history_manager_output(input_path)


@pytest.mark.parametrize(
    ("field_name", "expected_message"),
    [
        ("query", "query is required"),
        ("conversation_id", "conversation_id is required"),
        ("user_id", "user_id is required"),
        ("original_question", "original_question is required"),
    ],
)
def test_required_fields_raise_validation_error(
    field_name: str,
    expected_message: str,
) -> None:
    payload = _valid_payload()
    payload[field_name] = ""

    with pytest.raises(RoutingInputValidationError, match=expected_message):
        normalize_routing_input(payload)


@pytest.mark.parametrize(
    "history_decision",
    ["follow_up", "new_topic", "ambiguous"],
)
def test_supported_history_decision_values_are_preserved(
    history_decision: str,
) -> None:
    payload = _valid_payload()
    payload["history_decision"] = history_decision

    result = normalize_routing_input(payload)

    assert result.routing_input.history_decision == HistoryDecisionLabel(history_decision)
    assert result.warnings == []


def test_unsupported_history_decision_uses_safe_fallback_with_warning() -> None:
    payload = _valid_payload()
    payload["history_decision"] = "future-history-label"

    result = normalize_routing_input(payload)

    assert result.routing_input.history_decision == HistoryDecisionLabel.AMBIGUOUS
    assert [warning.code for warning in result.warnings] == [
        "unsupported_history_decision"
    ]
    assert "future-history-label" not in json.dumps(result.to_safe_dict())


def test_empty_preserved_context_is_safe_default() -> None:
    payload = _valid_payload()
    payload["preserved_context"] = {}

    result = normalize_routing_input(payload)

    assert result.routing_input.preserved_context.to_dict() == {
        "summary": "",
        "entities": [],
        "turn_refs": [],
    }
    assert result.warnings == []


def test_malformed_preserved_context_fields_are_normalized_with_warnings() -> None:
    payload = _valid_payload()
    payload["preserved_context"] = {
        "summary": 123,
        "entities": "IAM",
        "turn_refs": {"turn": "1"},
    }

    result = normalize_routing_input(payload)

    assert result.routing_input.preserved_context.summary == "123"
    assert result.routing_input.preserved_context.entities == ["IAM"]
    assert result.routing_input.preserved_context.turn_refs == []
    assert {warning.code for warning in result.warnings} == {
        "preserved_context_entities_normalized",
        "preserved_context_turn_refs_dropped",
    }


@pytest.mark.parametrize(
    ("groups_value", "expected_groups"),
    [
        ("ops-team", ["ops-team"]),
        (["ops-team", "platform-team"], ["ops-team", "platform-team"]),
        (None, []),
    ],
)
def test_metadata_groups_are_normalized_to_canonical_list(
    groups_value: object,
    expected_groups: list[str],
) -> None:
    payload = _valid_payload()
    metadata = dict(payload["metadata"])  # type: ignore[arg-type]
    if groups_value is None:
        metadata.pop("groups", None)
    else:
        metadata["groups"] = groups_value
    payload["metadata"] = metadata

    result = normalize_routing_input(payload)

    assert result.routing_input.metadata["groups"] == expected_groups
    assert result.acl_filter.groups == expected_groups


@pytest.mark.parametrize(
    ("space_keys_value", "expected_space_keys"),
    [
        ("OPS", ["OPS"]),
        (["OPS", "ENG"], ["OPS", "ENG"]),
        (None, []),
    ],
)
def test_metadata_space_keys_are_normalized_to_canonical_list(
    space_keys_value: object,
    expected_space_keys: list[str],
) -> None:
    payload = _valid_payload()
    metadata = dict(payload["metadata"])  # type: ignore[arg-type]
    if space_keys_value is None:
        metadata.pop("space_keys", None)
    else:
        metadata["space_keys"] = space_keys_value
    payload["metadata"] = metadata

    result = normalize_routing_input(payload)

    assert result.routing_input.metadata["space_keys"] == expected_space_keys


def test_full_history_is_removed_from_normalized_input_with_warning() -> None:
    payload = _valid_payload()
    payload["history"] = [
        {"turn_id": "turn-1", "content": "Synthetic historical content"},
        {"turn_id": "turn-2", "content": "Synthetic historical content"},
    ]
    metadata = dict(payload["metadata"])  # type: ignore[arg-type]
    metadata["raw_history"] = [{"content": "Synthetic historical content"}]
    payload["metadata"] = metadata

    result = normalize_routing_input(payload)
    serialized = result.routing_input.to_dict()

    assert "history" not in serialized
    assert "raw_history" not in serialized["metadata"]
    assert {warning.code for warning in result.warnings} == {
        "raw_history_dropped",
        "metadata_raw_history_dropped",
    }


def test_warning_error_and_result_strings_do_not_expose_sensitive_values() -> None:
    payload = _valid_payload()
    payload["history_decision"] = "OPENAI_API_KEY"
    metadata = dict(payload["metadata"])  # type: ignore[arg-type]
    metadata["Authorization"] = "synthetic-sensitive-value"
    metadata["api_key"] = "synthetic-sensitive-value"
    metadata["safe_value"] = "kept"
    payload["metadata"] = metadata

    result = normalize_routing_input(payload)
    result_text = json.dumps(result.to_safe_dict(), ensure_ascii=False)

    assert result.routing_input.metadata["safe_value"] == "kept"
    assert "synthetic-sensitive-value" not in result_text
    assert "OPENAI_API_KEY" not in result_text
    assert "Authorization" not in result_text
    assert "api_key" not in result_text
