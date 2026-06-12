"""ai-agent/query-routing-agent/tests/integration/test_workflow_cli.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from query_routing_agent.config import QueryRoutingConfig
from query_routing_agent.llm import FakeRoutingLLMProvider, RoutingProviderError
from query_routing_agent.workflow import (
    QueryRoutingWorkflowRunner,
    build_query_routing_workflow,
    is_langgraph_available,
    run_query_routing_workflow,
)


def _write_input(path: Path, *, query: str = "IAM 정책 수정 장애 상황에서 롤백 절차는?") -> None:
    path.write_text(
        json.dumps(
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
        ),
        encoding="utf-8",
    )


def _provider(intent: str) -> FakeRoutingLLMProvider:
    return FakeRoutingLLMProvider(
        {
            "intent": intent,
            "confidence": 0.84,
            "reason": "Synthetic routing reason.",
            "expanded_queries": [
                "IAM 정책 수정 장애 롤백 절차",
                "IAM rollback troubleshooting",
                "IAM 권한 변경 실패 대응",
            ],
        }
    )


def test_workflow_runs_sequential_nodes_and_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "routing_decision.json"
    _write_input(input_path)

    result = run_query_routing_workflow(
        input_path=input_path,
        output_path=output_path,
        config=QueryRoutingConfig(),
        provider=_provider("incident_response"),
    )

    assert result.status == "success"
    assert result.node_order == [
        "load_config",
        "load_input",
        "normalize_routing_input",
        "classify_intent_and_rewrite",
        "build_metadata_filters",
        "build_pool_weights",
        "build_task_prompt_type",
        "build_routing_decision",
        "build_search_request",
        "write_output",
        "write_report",
    ]
    assert result.paths is not None
    assert result.paths.decision_path == output_path
    assert result.paths.decision_path.exists()
    assert result.paths.search_request_path.exists()
    assert result.paths.report_path.exists()

    decision = json.loads(result.paths.decision_path.read_text(encoding="utf-8"))
    search_request = json.loads(result.paths.search_request_path.read_text(encoding="utf-8"))
    report = json.loads(result.paths.report_path.read_text(encoding="utf-8"))

    assert decision["intent"] == "incident_response"
    assert decision["task_prompt_type"] == "timeline"
    assert len(decision["expanded_queries"]) == 3
    assert search_request["queries"] == decision["expanded_queries"]
    assert search_request["filters"]["acl"]["groups"] == ["ops-team"]
    assert report["status"] == "success"


@pytest.mark.parametrize(
    ("intent", "expected_prompt_type"),
    [
        ("operations_guide", "step_by_step"),
        ("policy_procedure", "evidence_first"),
        ("history_lookup", "history_summary"),
        ("unknown", "general"),
    ],
)
def test_workflow_maps_supported_intents(
    tmp_path: Path,
    intent: str,
    expected_prompt_type: str,
) -> None:
    input_path = tmp_path / f"{intent}.json"
    output_path = tmp_path / f"{intent}_decision.json"
    _write_input(input_path)

    result = run_query_routing_workflow(
        input_path=input_path,
        output_path=output_path,
        config=QueryRoutingConfig(),
        provider=_provider(intent),
    )

    assert result.status == "success"
    assert result.decision is not None
    assert result.decision.intent == intent
    assert result.decision.task_prompt_type == expected_prompt_type


def test_provider_failure_writes_failed_outputs_without_secret(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "routing_decision.json"
    report_path = tmp_path / "report.json"
    failed_path = tmp_path / "failed.json"
    _write_input(input_path)

    result = run_query_routing_workflow(
        input_path=input_path,
        output_path=output_path,
        report_output_path=report_path,
        failed_output_path=failed_path,
        config=QueryRoutingConfig(),
        provider=FakeRoutingLLMProvider(
            RoutingProviderError(
                code="synthetic_provider_failure",
                message="OPENAI_API_KEY Authorization secret",
                retryable=True,
            )
        ),
    )

    assert result.status == "failed"
    assert output_path.exists() is False
    assert report_path.exists()
    assert failed_path.exists()
    combined = report_path.read_text(encoding="utf-8") + failed_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in combined
    assert "Authorization" not in combined
    assert "secret" not in combined.lower()


def test_malformed_input_writes_safe_failed_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "malformed.json"
    output_path = tmp_path / "routing_decision.json"
    report_path = tmp_path / "report.json"
    failed_path = tmp_path / "failed.json"
    input_path.write_text("{not-json", encoding="utf-8")

    result = run_query_routing_workflow(
        input_path=input_path,
        output_path=output_path,
        report_output_path=report_path,
        failed_output_path=failed_path,
        config=QueryRoutingConfig(),
        provider=_provider("incident_response"),
    )

    assert result.status == "failed"
    assert output_path.exists() is False
    assert report_path.exists()
    assert failed_path.exists()
    combined = report_path.read_text(encoding="utf-8") + failed_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in combined
    assert "Authorization" not in combined


def test_cli_runs_workflow_with_fake_provider(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "routing_decision.json"
    _write_input(input_path)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_query_router.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
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
    assert "OPENAI_API_KEY" not in completed.stdout + completed.stderr
    assert "Authorization" not in completed.stdout + completed.stderr
    decision = json.loads(output_path.read_text(encoding="utf-8"))
    assert decision["intent"] == "incident_response"


def test_langgraph_optional_fallback_is_explicit() -> None:
    workflow = build_query_routing_workflow()

    assert workflow.execution_mode in {"langgraph", "sequential"}
    assert workflow.execution_mode == ("langgraph" if is_langgraph_available() else "sequential")


def test_workflow_does_not_execute_search_embedding_or_reranking(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "routing_decision.json"
    _write_input(input_path)

    runner = QueryRoutingWorkflowRunner(
        config=QueryRoutingConfig(),
        provider=_provider("incident_response"),
    )
    result = runner.run(input_path=input_path, output_path=output_path)

    assert result.status == "success"
    serialized = json.dumps(result.to_safe_dict())
    assert "qdrant" not in serialized.lower()
    assert "embedding" not in serialized.lower()
    assert "reranking_result" not in serialized.lower()
