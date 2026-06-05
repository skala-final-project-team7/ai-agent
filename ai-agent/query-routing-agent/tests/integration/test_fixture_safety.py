from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from query_routing_agent.config import QueryRoutingConfig
from query_routing_agent.llm import FakeRoutingLLMProvider, RoutingProviderError
from query_routing_agent.workflow import run_query_routing_workflow

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "query_routing"
SENSITIVE_MARKERS = (
    "OPENAI_API_KEY",
    "Authorization",
    "Bearer ",
    "api_key",
    "secret",
)


def _fixture(name: str) -> Path:
    return FIXTURE_DIR / name


def _provider(
    intent: str,
    *,
    expanded_queries: list[str] | str | None = None,
) -> FakeRoutingLLMProvider:
    payload: dict[str, Any] = {
        "intent": intent,
        "confidence": 0.83,
        "reason": "Synthetic fixture routing decision.",
    }
    if expanded_queries is not None:
        payload["expanded_queries"] = expanded_queries
    return FakeRoutingLLMProvider(payload)


def _run_fixture(
    tmp_path: Path,
    fixture_name: str,
    provider: FakeRoutingLLMProvider,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    output_dir = tmp_path / fixture_name.replace(".json", "")
    decision_path = output_dir / "routing_decision.json"
    result = run_query_routing_workflow(
        input_path=_fixture(fixture_name),
        output_path=decision_path,
        config=QueryRoutingConfig(),
        provider=provider,
    )

    assert result.status == "success"
    assert result.paths is not None
    decision = json.loads(result.paths.decision_path.read_text(encoding="utf-8"))
    search_request = json.loads(
        result.paths.search_request_path.read_text(encoding="utf-8")
    )
    report = json.loads(result.paths.report_path.read_text(encoding="utf-8"))
    return decision, search_request, report, output_dir


def _assert_common_output_shape(
    decision: dict[str, Any],
    search_request: dict[str, Any],
    report: dict[str, Any],
) -> None:
    for key in (
        "routing_id",
        "conversation_id",
        "user_id",
        "original_question",
        "query",
        "intent",
        "task_prompt_type",
        "expanded_queries",
        "metadata_filters",
        "pool_weights",
        "confidence",
        "reason",
        "warnings",
    ):
        assert key in decision

    for key in (
        "routing_id",
        "conversation_id",
        "user_id",
        "queries",
        "filters",
        "pool_weights",
        "top_k_candidates",
        "rerank_top_k",
        "reranking_required",
    ):
        assert key in search_request

    assert report["status"] == "success"
    assert "intent" in report
    assert "expanded_query_count" in report
    assert "warnings_count" in report
    assert abs(sum(decision["pool_weights"].values()) - 1.0) < 0.000001
    assert search_request["queries"] == decision["expanded_queries"]
    assert search_request["filters"]["acl"]["user_id"] == decision["user_id"]


@pytest.mark.parametrize(
    ("fixture_name", "intent", "task_prompt_type", "expected_weight"),
    [
        (
            "incident_response.json",
            "incident_response",
            "timeline",
            {"title": 0.2, "content": 0.65, "label": 0.15},
        ),
        (
            "operations_guide.json",
            "operations_guide",
            "step_by_step",
            {"title": 0.25, "content": 0.6, "label": 0.15},
        ),
        (
            "policy_procedure.json",
            "policy_procedure",
            "evidence_first",
            {"title": 0.3, "content": 0.6, "label": 0.1},
        ),
        (
            "history_lookup.json",
            "history_lookup",
            "history_summary",
            {"title": 0.2, "content": 0.5, "label": 0.3},
        ),
    ],
)
def test_fixture_full_workflow_intent_boundaries(
    tmp_path: Path,
    fixture_name: str,
    intent: str,
    task_prompt_type: str,
    expected_weight: dict[str, float],
) -> None:
    decision, search_request, report, output_dir = _run_fixture(
        tmp_path,
        fixture_name,
        _provider(
            intent,
            expanded_queries=[
                f"{intent} primary synthetic query",
                f"{intent} secondary synthetic query",
                f"{intent} evidence synthetic query",
            ],
        ),
    )

    _assert_common_output_shape(decision, search_request, report)
    assert decision["intent"] == intent
    assert decision["task_prompt_type"] == task_prompt_type
    assert len(decision["expanded_queries"]) == 3
    assert decision["pool_weights"] == expected_weight
    assert_no_sensitive_markers_in_path(output_dir)
    assert_mvp_excluded_capabilities_not_executed(decision, search_request, report)


def test_history_lookup_fixture_preserves_label_and_date_filters(tmp_path: Path) -> None:
    decision, search_request, _, _ = _run_fixture(
        tmp_path,
        "history_lookup.json",
        _provider(
            "history_lookup",
            expanded_queries=[
                "권한 변경 이력 조회",
                "IAM 변경 날짜 확인",
                "change history audit trail",
            ],
        ),
    )

    filters = search_request["filters"]
    assert "change-history" in filters["labels"]
    assert filters["date_range"] == {"from": "2026-01-01", "to": "2026-05-15"}
    assert decision["pool_weights"]["label"] == 0.3


def test_unknown_intent_fixture_uses_safe_fallback_query(tmp_path: Path) -> None:
    decision, search_request, report, _ = _run_fixture(
        tmp_path,
        "unknown_intent.json",
        _provider("drifted_intent", expanded_queries="not-a-list"),
    )

    _assert_common_output_shape(decision, search_request, report)
    assert decision["intent"] == "unknown"
    assert decision["task_prompt_type"] == "general"
    assert decision["expanded_queries"][0] == decision["query"]
    assert len(decision["expanded_queries"]) == 3
    assert any(
        warning["code"] in {"invalid_intent_fallback", "expanded_queries_invalid"}
        for warning in decision["warnings"]
    )


def test_acl_metadata_fixture_forwards_acl_without_enforcement(tmp_path: Path) -> None:
    decision, search_request, _, _ = _run_fixture(
        tmp_path,
        "acl_metadata.json",
        _provider(
            "operations_guide",
            expanded_queries=[
                "운영 절차 접근 권한",
                "operations guide access groups",
                "restricted runbook search",
            ],
        ),
    )

    acl = search_request["filters"]["acl"]
    assert acl == {"user_id": "user-acl-synthetic", "groups": ["ops-team", "sre"]}
    assert "allowed" not in acl
    assert "denied" not in acl
    assert "enforced" not in acl
    assert decision["metadata_filters"]["acl"] == acl


def test_malformed_input_fixture_writes_safe_failed_outputs(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    failed_path = tmp_path / "failed.json"
    result = run_query_routing_workflow(
        input_path=_fixture("malformed_input.json"),
        output_path=tmp_path / "routing_decision.json",
        report_output_path=report_path,
        failed_output_path=failed_path,
        config=QueryRoutingConfig(),
        provider=_provider("incident_response"),
    )

    assert result.status == "failed"
    assert report_path.exists()
    assert failed_path.exists()
    failed_items = json.loads(failed_path.read_text(encoding="utf-8"))
    assert failed_items[0]["item_id"] == "malformed_input.json"
    assert failed_items[0]["retryable"] is False
    assert_no_sensitive_markers_in_text(
        report_path.read_text(encoding="utf-8")
        + failed_path.read_text(encoding="utf-8")
    )


def test_provider_failure_fixture_writes_safe_failed_outputs(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    failed_path = tmp_path / "failed.json"
    result = run_query_routing_workflow(
        input_path=_fixture("provider_failure.json"),
        output_path=tmp_path / "routing_decision.json",
        report_output_path=report_path,
        failed_output_path=failed_path,
        config=QueryRoutingConfig(),
        provider=FakeRoutingLLMProvider(
            RoutingProviderError(
                code="synthetic_provider_failure",
                message="Synthetic provider failure with redacted sensitive marker.",
                retryable=True,
            )
        ),
    )

    assert result.status == "failed"
    failed_items = json.loads(failed_path.read_text(encoding="utf-8"))
    assert failed_items[0]["retryable"] is True
    assert failed_items[0]["error_type"] == "synthetic_provider_failure"
    assert_no_sensitive_markers_in_text(
        report_path.read_text(encoding="utf-8")
        + failed_path.read_text(encoding="utf-8")
    )


def test_cli_fixture_run_does_not_expose_sensitive_markers(tmp_path: Path) -> None:
    output_path = tmp_path / "routing_decision.json"
    report_path = tmp_path / "routing_report.json"
    failed_path = tmp_path / "failed_items.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_query_router.py",
            "--input",
            str(_fixture("incident_response.json")),
            "--output",
            str(output_path),
            "--report-output",
            str(report_path),
            "--failed-output",
            str(failed_path),
            "--provider",
            "fake",
            "--fake-intent",
            "incident_response",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "status=success" in completed.stdout
    assert output_path.exists()
    assert report_path.exists()
    assert_no_sensitive_markers_in_text(completed.stdout + completed.stderr)
    assert_no_sensitive_markers_in_path(tmp_path)


def assert_no_sensitive_markers_in_path(path: Path) -> None:
    combined = ""
    for output_file in path.rglob("*.json"):
        combined += output_file.read_text(encoding="utf-8")
    assert_no_sensitive_markers_in_text(combined)


def assert_no_sensitive_markers_in_text(text: str) -> None:
    for marker in SENSITIVE_MARKERS:
        assert marker not in text


def assert_mvp_excluded_capabilities_not_executed(*payloads: dict[str, Any]) -> None:
    serialized = json.dumps(payloads, ensure_ascii=False).lower()
    for forbidden in (
        "qdrant_result",
        "embedding_vector",
        "dense_embedding",
        "sparse_embedding",
        "cross_encoder_score",
        "reranking_result",
        "acl_enforced",
        "answer_generation_result",
        "answer_verification_result",
        "bff_response",
        "db_record",
        "sse_event",
    ):
        assert forbidden not in serialized
