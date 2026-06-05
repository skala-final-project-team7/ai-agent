from __future__ import annotations

import json

import pytest

from query_routing_agent.config import QueryRoutingConfig
from query_routing_agent.llm import IntentClassificationResult
from query_routing_agent.routing import (
    build_filter_and_pool_weights,
    build_routing_decision,
    build_routing_id,
    build_routing_report,
    build_search_request_payload,
    make_failed_item,
    normalize_routing_input,
    rewrite_queries,
    write_routing_outputs,
)
from query_routing_agent.schemas import (
    IntentLabel,
    RoutingReportStatus,
    SearchRequestPayload,
    WarningItem,
)


def _normalized_input(query: str = "IAM 정책 수정 장애 상황에서 롤백 절차는?"):
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
                "turn_refs": ["turn-1"],
            },
            "reset_required": False,
            "metadata": {
                "space_keys": ["OPS"],
                "groups": ["ops-team"],
                "labels": ["incident"],
            },
        }
    )


def _classification(intent: IntentLabel = IntentLabel.INCIDENT_RESPONSE):
    return IntentClassificationResult(
        intent=intent,
        confidence=0.83,
        reason="Synthetic routing reason.",
        warnings=[WarningItem(code="classification_warning", message="Classification warning.")],
        raw_hints={
            "expanded_queries": [
                "IAM 정책 수정 장애 롤백 절차",
                "IAM rollback troubleshooting",
                "IAM 권한 변경 실패 대응",
            ]
        },
    )


def _build_inputs():
    config = QueryRoutingConfig()
    normalized = _normalized_input()
    classification = _classification()
    rewrite = rewrite_queries(normalized, classification, config)
    filter_result = build_filter_and_pool_weights(
        normalized_input=normalized,
        intent=classification.intent,
        config=config,
    )
    return config, normalized, classification, rewrite, filter_result


def test_routing_decision_contains_canonical_required_fields() -> None:
    config, normalized, classification, rewrite, filter_result = _build_inputs()

    decision = build_routing_decision(
        normalized_input=normalized,
        classification=classification,
        rewrite_result=rewrite,
        filter_result=filter_result,
        config=config,
    )
    serialized = decision.to_dict()

    assert serialized["routing_id"].startswith("routing-")
    assert serialized["conversation_id"] == "conversation-synthetic"
    assert serialized["user_id"] == "user-synthetic"
    assert serialized["original_question"] == "그럼 롤백은?"
    assert serialized["query"] == "IAM 정책 수정 장애 상황에서 롤백 절차는?"
    assert serialized["intent"] == "incident_response"
    assert serialized["task_prompt_type"] == "timeline"
    assert serialized["expanded_queries"] == rewrite.expanded_queries
    assert serialized["metadata_filters"]["acl"] == {
        "user_id": "user-synthetic",
        "groups": ["ops-team"],
    }
    assert serialized["pool_weights"] == {"title": 0.2, "content": 0.65, "label": 0.15}
    assert serialized["confidence"] == 0.83
    assert serialized["reason"] == "Synthetic routing reason."


def test_routing_id_is_deterministic_and_traceable() -> None:
    normalized = _normalized_input()

    first_id = build_routing_id(normalized.routing_input)
    second_id = build_routing_id(normalized.routing_input)

    assert first_id == second_id
    assert first_id.startswith("routing-conversation-synthetic-")


def test_decision_merges_warnings_from_all_stages() -> None:
    config, normalized, classification, rewrite, filter_result = _build_inputs()
    rewrite.warnings.append(WarningItem(code="rewrite_warning", message="Rewrite warning."))
    filter_result.warnings.append(WarningItem(code="filter_warning", message="Filter warning."))

    decision = build_routing_decision(
        normalized_input=normalized,
        classification=classification,
        rewrite_result=rewrite,
        filter_result=filter_result,
        config=config,
    )

    warning_codes = {warning.code for warning in decision.warnings}
    assert {
        "classification_warning",
        "rewrite_warning",
        "filter_warning",
    }.issubset(warning_codes)


def test_search_request_payload_contains_only_search_payload_fields() -> None:
    config, normalized, classification, rewrite, filter_result = _build_inputs()
    decision = build_routing_decision(
        normalized_input=normalized,
        classification=classification,
        rewrite_result=rewrite,
        filter_result=filter_result,
        config=config,
    )

    payload = build_search_request_payload(decision, config)
    serialized = payload.to_dict()

    assert isinstance(payload, SearchRequestPayload)
    assert serialized["routing_id"] == decision.routing_id
    assert serialized["queries"] == decision.expanded_queries
    assert serialized["filters"]["acl"]["user_id"] == "user-synthetic"
    assert serialized["filters"]["acl"]["groups"] == ["ops-team"]
    assert serialized["pool_weights"] == decision.pool_weights.to_dict()
    assert serialized["top_k_candidates"] == config.top_k_candidates
    assert serialized["rerank_top_k"] == config.rerank_top_k
    assert serialized["reranking_required"] is True
    assert "qdrant" not in json.dumps(serialized).lower()
    assert "embedding" not in json.dumps(serialized).lower()


def test_missing_answer_generation_ready_fields_raise_validation_error() -> None:
    config, normalized, classification, rewrite, filter_result = _build_inputs()
    rewrite.expanded_queries.clear()

    with pytest.raises(ValueError, match="expanded_queries is required"):
        build_routing_decision(
            normalized_input=normalized,
            classification=classification,
            rewrite_result=rewrite,
            filter_result=filter_result,
            config=config,
        )


def test_routing_report_helper_calculates_counts() -> None:
    config, normalized, classification, rewrite, filter_result = _build_inputs()
    decision = build_routing_decision(
        normalized_input=normalized,
        classification=classification,
        rewrite_result=rewrite,
        filter_result=filter_result,
        config=config,
    )

    report = build_routing_report(
        decision,
        status=RoutingReportStatus.SUCCESS,
        job_id="job-synthetic",
        created_at="2026-05-15T00:00:00Z",
    )
    serialized = report.to_dict()

    assert serialized["status"] == "success"
    assert serialized["intent"] == "incident_response"
    assert serialized["expanded_query_count"] == len(decision.expanded_queries)
    assert serialized["warnings_count"] == len(decision.warnings)


def test_failed_item_helper_creates_safe_shape() -> None:
    failed_item = make_failed_item(
        item_id="input-synthetic",
        reason="Synthetic validation failure",
        retryable=False,
        error_type="validation_error",
    )

    assert failed_item.to_dict() == {
        "item_id": "input-synthetic",
        "reason": "Synthetic validation failure",
        "retryable": False,
        "error_type": "validation_error",
    }


def test_local_json_writer_creates_output_report_and_failed_files(tmp_path) -> None:
    config, normalized, classification, rewrite, filter_result = _build_inputs()
    decision = build_routing_decision(
        normalized_input=normalized,
        classification=classification,
        rewrite_result=rewrite,
        filter_result=filter_result,
        config=config,
    )
    payload = build_search_request_payload(decision, config)
    report = build_routing_report(
        decision,
        status=RoutingReportStatus.SUCCESS,
        job_id="job-synthetic",
        created_at="2026-05-15T00:00:00Z",
    )
    failed_item = make_failed_item(
        item_id="input-synthetic",
        reason="Synthetic skipped item",
        retryable=False,
        error_type="skipped",
    )

    paths = write_routing_outputs(
        output_dir=tmp_path / "missing" / "outputs",
        decision=decision,
        search_request=payload,
        report=report,
        failed_items=[failed_item],
    )

    assert paths.decision_path.exists()
    assert paths.search_request_path.exists()
    assert paths.report_path.exists()
    assert paths.failed_items_path.exists()
    assert json.loads(paths.decision_path.read_text(encoding="utf-8"))["routing_id"]
    assert json.loads(paths.search_request_path.read_text(encoding="utf-8"))["queries"]
    assert json.loads(paths.report_path.read_text(encoding="utf-8"))["status"] == "success"
    assert json.loads(paths.failed_items_path.read_text(encoding="utf-8"))[0]["item_id"]


def test_writer_redacts_sensitive_values_from_files(tmp_path) -> None:
    config, normalized, classification, rewrite, filter_result = _build_inputs()
    normalized.routing_input.query = "OPENAI_API_KEY Authorization secret"
    classification.reason = "OPENAI_API_KEY Authorization secret"
    decision = build_routing_decision(
        normalized_input=normalized,
        classification=classification,
        rewrite_result=rewrite,
        filter_result=filter_result,
        config=config,
    )
    payload = build_search_request_payload(decision, config)
    report = build_routing_report(
        decision,
        status=RoutingReportStatus.SUCCESS,
        job_id="job-synthetic",
        created_at="2026-05-15T00:00:00Z",
    )
    failed_item = make_failed_item(
        item_id="input-synthetic",
        reason="OPENAI_API_KEY Authorization secret",
        retryable=False,
        error_type="validation_error",
    )

    paths = write_routing_outputs(
        output_dir=tmp_path,
        decision=decision,
        search_request=payload,
        report=report,
        failed_items=[failed_item],
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            paths.decision_path,
            paths.search_request_path,
            paths.report_path,
            paths.failed_items_path,
        )
    )

    assert "OPENAI_API_KEY" not in combined
    assert "Authorization" not in combined
    assert "secret" not in combined.lower()
