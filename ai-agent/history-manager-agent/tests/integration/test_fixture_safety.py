from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path

from history_manager_agent.config import HistoryManagerConfig
from history_manager_agent.llm import FakeHistoryLLMProvider, LLMProviderError
from history_manager_agent.scripts import run_history_manager
from history_manager_agent.workflow import run_history_manager_workflow

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "history"
FORBIDDEN_TERMS = [
    "OPENAI_API_KEY",
    "Authorization",
    "API key",
    "Bearer",
    "secret-like",
]


def _fixture(name: str) -> Path:
    return FIXTURE_DIR / name


def _provider(label: str, confidence: float = 0.85) -> FakeHistoryLLMProvider:
    return FakeHistoryLLMProvider(
        {
            "history_decision": label,
            "confidence": confidence,
            "reason": "Synthetic fixture classification reason.",
        }
    )


def _run_fixture(
    tmp_path: Path,
    fixture_name: str,
    label: str,
    confidence: float = 0.85,
    config: HistoryManagerConfig | None = None,
):
    output_path = tmp_path / f"{fixture_name}.output.json"
    report_path = tmp_path / f"{fixture_name}.report.json"
    result = run_history_manager_workflow(
        input_path=_fixture(fixture_name),
        output_path=output_path,
        report_output_path=report_path,
        config=config or HistoryManagerConfig(),
        provider=_provider(label, confidence),
    )
    return result, _read_json(output_path), _read_json(report_path), output_path, report_path


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_no_sensitive_terms(*values: str) -> None:
    combined = "\n".join(values)
    for forbidden in FORBIDDEN_TERMS:
        assert forbidden not in combined


def test_fixtures_are_synthetic_and_do_not_contain_sensitive_terms() -> None:
    fixture_text = "\n".join(
        path.read_text(encoding="utf-8") for path in FIXTURE_DIR.glob("*.json")
    )

    _assert_no_sensitive_terms(fixture_text)
    assert "synthetic" in fixture_text


def test_follow_up_fixture_full_workflow_outputs_canonical_shape(
    tmp_path: Path,
) -> None:
    result, output, report, _, _ = _run_fixture(
        tmp_path,
        "follow_up_input.json",
        "follow_up",
        confidence=0.88,
    )
    decision = output["decision"]
    routing_input = output["routing_input"]

    assert result.status == "success"
    assert decision["history_decision"] == "follow_up"
    assert decision["reset_required"] is False
    assert decision["contextualized_question"]
    assert decision["contextualized_question"] != decision["original_question"]
    assert decision["preserved_context"]["summary"]
    assert routing_input["query"] == decision["contextualized_question"]
    assert routing_input["history_decision"] == "follow_up"
    assert routing_input["preserved_context"] == decision["preserved_context"]
    assert routing_input["reset_required"] is False
    assert report["status"] == "success"
    assert report["decision"] == "follow_up"


def test_new_topic_fixture_resets_context_and_keeps_original_query(
    tmp_path: Path,
) -> None:
    _, output, report, _, _ = _run_fixture(
        tmp_path,
        "new_topic_input.json",
        "new_topic",
        confidence=0.93,
    )

    assert output["decision"]["history_decision"] == "new_topic"
    assert output["decision"]["reset_required"] is True
    assert output["decision"]["preserved_context"]["summary"] == ""
    assert output["routing_input"]["query"] == output["decision"]["original_question"]
    assert report["decision"] == "new_topic"


def test_ambiguous_fixture_keeps_conservative_context_and_warning(
    tmp_path: Path,
) -> None:
    _, output, report, _, _ = _run_fixture(
        tmp_path,
        "ambiguous_input.json",
        "ambiguous",
        confidence=0.35,
    )
    warnings = output["decision"]["warnings"]

    assert output["decision"]["history_decision"] == "ambiguous"
    assert output["decision"]["confidence"] == 0.35
    assert output["decision"]["reset_required"] is False
    assert "ambiguous_low_confidence" in warnings
    assert "ambiguous_conservative_question" in warnings
    assert len(output["decision"]["preserved_context"]["turn_refs"]) <= 2
    assert report["warnings_count"] >= 2


def test_empty_history_fixture_is_new_topic_without_provider_call(
    tmp_path: Path,
) -> None:
    provider = _provider("follow_up")
    output_path = tmp_path / "empty.output.json"
    report_path = tmp_path / "empty.report.json"

    result = run_history_manager_workflow(
        input_path=_fixture("empty_history_input.json"),
        output_path=output_path,
        report_output_path=report_path,
        config=HistoryManagerConfig(),
        provider=provider,
    )
    output = _read_json(output_path)
    report = _read_json(report_path)

    assert result.status == "success"
    assert output["decision"]["history_decision"] == "new_topic"
    assert output["routing_input"]["query"] == output["decision"]["original_question"]
    assert report["input_turn_count"] == 0
    assert report["used_turn_count"] == 0
    assert provider.requests == []


def test_long_history_fixture_applies_window_and_context_trimming(
    tmp_path: Path,
) -> None:
    _, output, report, _, _ = _run_fixture(
        tmp_path,
        "long_history_input.json",
        "follow_up",
        config=HistoryManagerConfig(history_window_turns=5, max_context_chars=32),
    )
    turn_refs = output["decision"]["preserved_context"]["turn_refs"]

    assert report["input_turn_count"] == 7
    assert report["used_turn_count"] < 7
    assert "turn-001" not in turn_refs
    assert "turn-002" not in turn_refs
    assert "history_window_trimmed" in output["decision"]["warnings"]


def test_malformed_history_fixture_keeps_valid_turn_and_reports_warnings(
    tmp_path: Path,
) -> None:
    _, output, report, _, _ = _run_fixture(
        tmp_path,
        "malformed_history_input.json",
        "follow_up",
    )
    warnings = output["decision"]["warnings"]

    assert output["decision"]["history_decision"] == "follow_up"
    assert output["decision"]["preserved_context"]["turn_refs"] == ["turn-001"]
    assert "invalid_role" in warnings
    assert "invalid_turn" in warnings
    assert report["input_turn_count"] == 3
    assert report["used_turn_count"] == 1
    assert report["warnings_count"] >= 2


def test_provider_failure_fixture_creates_failed_output_without_secret(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "failed.output.json"
    report_path = tmp_path / "failed.report.json"

    result = run_history_manager_workflow(
        input_path=_fixture("provider_failure_input.json"),
        output_path=output_path,
        report_output_path=report_path,
        config=HistoryManagerConfig(),
        provider=FakeHistoryLLMProvider(
            LLMProviderError(
                code="synthetic_provider_failure",
                message="OPENAI_API_KEY Authorization API key secret-like",
                retryable=True,
            )
        ),
    )
    output_text = output_path.read_text(encoding="utf-8")
    report_text = report_path.read_text(encoding="utf-8")
    output = json.loads(output_text)
    report = json.loads(report_text)

    assert result.status == "failed"
    assert output["status"] == "failed"
    assert output["failed_items"][0]["retryable"] is True
    assert report["status"] == "failed"
    _assert_no_sensitive_terms(output_text, report_text)


def test_cli_fixture_run_does_not_expose_sensitive_terms(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "cli.output.json"
    report_path = tmp_path / "cli.report.json"

    exit_code = run_history_manager.main(
        [
            "--input",
            str(_fixture("follow_up_input.json")),
            "--output",
            str(output_path),
            "--report-output",
            str(report_path),
            "--provider",
            "fake",
            "--fake-decision",
            "follow_up",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.exists()
    assert report_path.exists()
    _assert_no_sensitive_terms(
        captured.out,
        captured.err,
        output_path.read_text(encoding="utf-8"),
        report_path.read_text(encoding="utf-8"),
    )


def test_outputs_do_not_copy_full_history_or_excluded_runtime_boundaries(
    tmp_path: Path,
) -> None:
    _, output, report, output_path, report_path = _run_fixture(
        tmp_path,
        "follow_up_input.json",
        "follow_up",
    )
    serialized = json.dumps(output, ensure_ascii=False) + json.dumps(
        report,
        ensure_ascii=False,
    )

    assert "history" not in output["routing_input"]["metadata"]
    assert "history" not in output["decision"]
    assert "database" not in serialized.lower()
    assert find_spec("history_manager_agent.bff") is None
    assert find_spec("history_manager_agent.db") is None
    assert find_spec("history_manager_agent.rag") is None
    _assert_no_sensitive_terms(
        output_path.read_text(encoding="utf-8"),
        report_path.read_text(encoding="utf-8"),
    )


def test_mvp_excluded_capabilities_are_marked_not_executed(tmp_path: Path) -> None:
    _, output, report, _, _ = _run_fixture(
        tmp_path,
        "follow_up_input.json",
        "follow_up",
    )

    excluded = output["mvp_scope"]["excluded_capabilities"]
    report_excluded = report["mvp_scope"]["excluded_capabilities"]

    assert excluded == report_excluded
    assert excluded["bff_api_adapter"] == "not_supported_in_mvp"
    assert excluded["conversation_db_repository"] == "not_supported_in_mvp"
    assert excluded["rag_search"] == "not_supported_in_mvp"
    assert excluded["query_routing_agent"] == "not_supported_in_mvp"
    assert excluded["answer_generation_agent"] == "not_supported_in_mvp"
    assert excluded["answer_verification_agent"] == "not_supported_in_mvp"
    assert excluded["sse_streaming"] == "not_supported_in_mvp"
