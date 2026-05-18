from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from query_routing_agent.app import build_app_context
from query_routing_agent.config import QueryRoutingConfig
from query_routing_agent.schemas import (
    AclFilter,
    DateRangeFilter,
    FailedItem,
    HistoryDecisionLabel,
    IntentLabel,
    MetadataFilter,
    PoolWeights,
    PreservedContext,
    QueryRoutingInput,
    RoutingDecision,
    RoutingReport,
    RoutingReportStatus,
    SearchRequestPayload,
    TaskPromptType,
    WarningItem,
)
from query_routing_agent.scripts import run_query_router


def _runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def test_config_accepts_external_values_and_redacts_api_key() -> None:
    api_key = _runtime_value("synthetic-api-key")
    config = QueryRoutingConfig(
        model="synthetic-model",
        temperature=0.2,
        timeout_seconds=12,
        max_retries=4,
        default_query_count=3,
        max_query_count=5,
        top_k_candidates=30,
        rerank_top_k=7,
        default_pool_weights=PoolWeights(title=0.2, content=0.7, label=0.1),
        openai_api_key=api_key,
    )

    safe_config = config.to_safe_dict()

    assert config.model == "synthetic-model"
    assert config.temperature == 0.2
    assert config.timeout_seconds == 12
    assert config.max_retries == 4
    assert config.default_query_count == 3
    assert config.max_query_count == 5
    assert config.default_pool_weights.to_dict() == {
        "title": 0.2,
        "content": 0.7,
        "label": 0.1,
    }
    assert safe_config["openai_api_key"] == "<redacted>"
    assert api_key not in repr(config)
    assert api_key not in json.dumps(safe_config)
    assert "Authorization" not in json.dumps(safe_config)


def test_routing_input_schema_matches_history_manager_output_contract() -> None:
    routing_input = QueryRoutingInput(
        conversation_id=_runtime_value("conversation"),
        user_id=_runtime_value("user"),
        original_question="그럼 롤백은?",
        query="IAM 정책 수정 장애 상황에서 롤백 절차는?",
        history_decision=HistoryDecisionLabel.FOLLOW_UP,
        preserved_context=PreservedContext(
            summary="IAM policy incident context",
            entities=["IAM"],
            turn_refs=["turn-1"],
        ),
        reset_required=False,
        metadata={"locale": "ko-KR", "groups": ["synthetic-group"]},
    )
    serialized = routing_input.to_dict()

    assert serialized["conversation_id"].startswith("conversation-")
    assert serialized["user_id"].startswith("user-")
    assert serialized["original_question"] == "그럼 롤백은?"
    assert serialized["query"] == "IAM 정책 수정 장애 상황에서 롤백 절차는?"
    assert serialized["history_decision"] == "follow_up"
    assert serialized["preserved_context"]["entities"] == ["IAM"]
    assert serialized["reset_required"] is False
    assert serialized["metadata"]["groups"] == ["synthetic-group"]


def test_intent_and_task_prompt_labels_support_mvp_values_and_extension() -> None:
    assert IntentLabel("incident_response") == IntentLabel.INCIDENT_RESPONSE
    assert IntentLabel("operations_guide") == IntentLabel.OPERATIONS_GUIDE
    assert IntentLabel("policy_procedure") == IntentLabel.POLICY_PROCEDURE
    assert IntentLabel("history_lookup") == IntentLabel.HISTORY_LOOKUP
    assert IntentLabel("unknown") == IntentLabel.UNKNOWN
    assert IntentLabel.from_value("future_intent") == "future_intent"

    assert TaskPromptType("timeline") == TaskPromptType.TIMELINE
    assert TaskPromptType("step_by_step") == TaskPromptType.STEP_BY_STEP
    assert TaskPromptType("evidence_first") == TaskPromptType.EVIDENCE_FIRST
    assert TaskPromptType("history_summary") == TaskPromptType.HISTORY_SUMMARY
    assert TaskPromptType("general") == TaskPromptType.GENERAL
    assert TaskPromptType.from_value("future_prompt") == "future_prompt"


def test_metadata_filter_and_acl_schema_do_not_include_enforcement_result() -> None:
    metadata_filter = MetadataFilter(
        space_keys=["OPS"],
        labels=["incident"],
        document_types=["page"],
        source_types=["confluence"],
        date_range=DateRangeFilter(from_date="2026-01-01", to_date="2026-05-15"),
        attachment_required=False,
        acl=AclFilter(user_id="synthetic-user", groups=["synthetic-group"]),
    )
    serialized = metadata_filter.to_dict()

    assert serialized["space_keys"] == ["OPS"]
    assert serialized["labels"] == ["incident"]
    assert serialized["document_types"] == ["page"]
    assert serialized["source_types"] == ["confluence"]
    assert serialized["date_range"] == {
        "from": "2026-01-01",
        "to": "2026-05-15",
    }
    assert serialized["attachment_required"] is False
    assert serialized["acl"] == {
        "user_id": "synthetic-user",
        "groups": ["synthetic-group"],
    }
    assert "allowed" not in serialized["acl"]
    assert "denied" not in serialized["acl"]


def test_pool_weight_schema_contains_expected_pools_and_sum_policy() -> None:
    weights = PoolWeights(title=0.25, content=0.6, label=0.15)

    assert weights.to_dict() == {"title": 0.25, "content": 0.6, "label": 0.15}
    assert weights.total == pytest.approx(1.0)

    with pytest.raises(ValueError, match="pool_weights must sum to 1.0"):
        PoolWeights(title=0.5, content=0.5, label=0.5)


def test_routing_decision_and_search_request_contain_canonical_fields() -> None:
    filters = MetadataFilter(acl=AclFilter(user_id="synthetic-user"))
    weights = PoolWeights()
    decision = RoutingDecision(
        routing_id="routing-1",
        conversation_id="conversation-1",
        user_id="user-1",
        original_question="Original?",
        query="Search query?",
        intent=IntentLabel.INCIDENT_RESPONSE,
        task_prompt_type=TaskPromptType.TIMELINE,
        expanded_queries=["Search query?", "incident rollback", "policy rollback"],
        metadata_filters=filters,
        pool_weights=weights,
        confidence=0.77,
        reason="Synthetic routing reason",
        warnings=[WarningItem(code="synthetic_warning", message="Synthetic warning")],
    )
    payload = SearchRequestPayload(
        routing_id=decision.routing_id,
        conversation_id=decision.conversation_id,
        user_id=decision.user_id,
        queries=decision.expanded_queries,
        filters=filters,
        pool_weights=weights,
        top_k_candidates=20,
        rerank_top_k=5,
        reranking_required=True,
    )

    decision_dict = decision.to_dict()
    payload_dict = payload.to_dict()

    assert decision_dict["intent"] == "incident_response"
    assert decision_dict["task_prompt_type"] == "timeline"
    assert decision_dict["metadata_filters"]["acl"]["user_id"] == "synthetic-user"
    assert decision_dict["pool_weights"]["content"] == 0.6
    assert decision_dict["confidence"] == 0.77
    assert decision_dict["warnings"][0]["code"] == "synthetic_warning"

    assert payload_dict["queries"] == [
        "Search query?",
        "incident rollback",
        "policy rollback",
    ]
    assert payload_dict["filters"]["acl"]["user_id"] == "synthetic-user"
    assert payload_dict["pool_weights"] == weights.to_dict()
    assert payload_dict["top_k_candidates"] == 20
    assert payload_dict["rerank_top_k"] == 5
    assert payload_dict["reranking_required"] is True
    assert "embedding" not in json.dumps(payload_dict).lower()
    assert "qdrant" not in json.dumps(payload_dict).lower()


def test_routing_report_failed_item_and_warnings_are_safe_shapes() -> None:
    report = RoutingReport(
        job_id="job-1",
        routing_id="routing-1",
        conversation_id="conversation-1",
        status=RoutingReportStatus.SUCCESS,
        intent=IntentLabel.UNKNOWN,
        expanded_query_count=3,
        warnings_count=1,
        created_at="2026-05-15T00:00:00Z",
    )
    failed_item = FailedItem(
        item_id="input-1",
        reason="Synthetic validation failure",
        retryable=False,
        error_type="validation_error",
    )

    assert report.to_dict()["status"] == "success"
    assert report.to_dict()["intent"] == "unknown"
    assert report.to_dict()["expanded_query_count"] == 3
    assert report.to_dict()["warnings_count"] == 1
    assert failed_item.to_dict() == {
        "item_id": "input-1",
        "reason": "Synthetic validation failure",
        "retryable": False,
        "error_type": "validation_error",
    }


def test_required_values_raise_clear_validation_errors() -> None:
    with pytest.raises(ValueError, match="query is required"):
        QueryRoutingInput(
            conversation_id="conversation-1",
            user_id="user-1",
            original_question="Original?",
            query="",
            history_decision=HistoryDecisionLabel.NEW_TOPIC,
            preserved_context=PreservedContext(),
            reset_required=True,
        )

    with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
        RoutingDecision(
            routing_id="routing-1",
            conversation_id="conversation-1",
            user_id="user-1",
            original_question="Original?",
            query="Query?",
            intent=IntentLabel.UNKNOWN,
            task_prompt_type=TaskPromptType.GENERAL,
            expanded_queries=["Query?"],
            metadata_filters=MetadataFilter(),
            pool_weights=PoolWeights(),
            confidence=1.2,
            reason="Synthetic reason",
        )


def test_app_context_and_cli_validate_input_without_openai_or_qdrant(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "routing_input.json"
    output_path = tmp_path / "output" / "routing_decision.json"
    input_path.write_text(
        json.dumps(
            {
                "conversation_id": "conversation-1",
                "user_id": "user-1",
                "original_question": "Original?",
                "query": "Search query?",
                "history_decision": "new_topic",
                "preserved_context": {"summary": "", "entities": [], "turn_refs": []},
                "reset_required": True,
                "metadata": {"locale": "ko-KR"},
            }
        ),
        encoding="utf-8",
    )

    context = build_app_context(
        input_path=input_path,
        output_path=output_path,
        config=QueryRoutingConfig(model="synthetic-model"),
    )

    assert context.config.model == "synthetic-model"
    assert context.input_path == input_path
    assert context.output_path == output_path

    exit_code = run_query_router.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "synthetic-model",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "validated" in captured.out
    assert "OPENAI_API_KEY" not in captured.out
    assert "Authorization" not in captured.out
    assert "qdrant" not in captured.out.lower()
