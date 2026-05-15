from __future__ import annotations

import json
from pathlib import Path

from history_manager_agent.config import HistoryManagerConfig
from history_manager_agent.llm import FakeHistoryLLMProvider, LLMProviderError
from history_manager_agent.scripts import run_history_manager
from history_manager_agent.workflow import (
    build_history_manager_workflow,
    run_history_manager_workflow,
)


def _write_input(path: Path, question: str = "그럼 롤백 절차는?") -> None:
    path.write_text(
        json.dumps(
            {
                "conversation_id": "conversation-synthetic",
                "user_id": "user-synthetic",
                "current_question": question,
                "history": [
                    {
                        "turn_id": "turn-1",
                        "role": "user",
                        "content": "IAM 정책 변경 중 장애가 발생했어.",
                        "created_at": "2026-05-15T00:01:00Z",
                    },
                    {
                        "turn_id": "turn-2",
                        "role": "assistant",
                        "content": "영향 범위를 확인하고 이전 정책으로 되돌립니다.",
                        "created_at": "2026-05-15T00:02:00Z",
                    },
                ],
                "metadata": {"locale": "ko-KR"},
            }
        ),
        encoding="utf-8",
    )


def _provider(label: str, confidence: float = 0.84) -> FakeHistoryLLMProvider:
    return FakeHistoryLLMProvider(
        {
            "history_decision": label,
            "confidence": confidence,
            "reason": "Synthetic classification reason.",
        }
    )


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_workflow_runs_full_sequence_with_fake_provider(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "history_decision.json"
    report_path = tmp_path / "history_report.json"
    provider = _provider("follow_up")
    _write_input(input_path)

    result = run_history_manager_workflow(
        input_path=input_path,
        output_path=output_path,
        report_output_path=report_path,
        config=HistoryManagerConfig(),
        provider=provider,
    )

    assert result.status == "success"
    assert result.node_trace == [
        "load_config",
        "load_input",
        "normalize_history",
        "trim_history",
        "classify_history",
        "apply_context_policy",
        "build_contextualized_question",
        "build_routing_input",
        "write_output",
        "write_report",
    ]
    assert provider.requests
    assert output_path.exists()
    assert report_path.exists()


def test_workflow_writes_decision_routing_and_report(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "history_decision.json"
    report_path = tmp_path / "history_report.json"
    _write_input(input_path)

    run_history_manager_workflow(
        input_path=input_path,
        output_path=output_path,
        report_output_path=report_path,
        config=HistoryManagerConfig(),
        provider=_provider("follow_up"),
    )

    output = _read_json(output_path)
    report = _read_json(report_path)

    assert output["decision"]["history_decision"] == "follow_up"
    assert output["routing_input"]["query"] == output["decision"]["contextualized_question"]
    assert report["status"] == "success"
    assert report["decision"] == "follow_up"
    assert report["input_turn_count"] == 2
    assert report["used_turn_count"] == 2


def test_follow_up_fixture_generates_contextualized_question(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    _write_input(input_path)

    run_history_manager_workflow(
        input_path=input_path,
        output_path=output_path,
        config=HistoryManagerConfig(),
        provider=_provider("follow_up"),
    )

    decision = _read_json(output_path)["decision"]
    assert decision["reset_required"] is False
    assert decision["contextualized_question"] != decision["original_question"]
    assert decision["preserved_context"]["summary"]


def test_new_topic_fixture_preserves_original_query(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    _write_input(input_path, question="새 배포 정책은?")

    run_history_manager_workflow(
        input_path=input_path,
        output_path=output_path,
        config=HistoryManagerConfig(),
        provider=_provider("new_topic", confidence=0.91),
    )

    output = _read_json(output_path)
    assert output["decision"]["reset_required"] is True
    assert output["routing_input"]["query"] == "새 배포 정책은?"


def test_ambiguous_fixture_keeps_conservative_warning(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    _write_input(input_path, question="그건 어떻게 해?")

    run_history_manager_workflow(
        input_path=input_path,
        output_path=output_path,
        config=HistoryManagerConfig(),
        provider=_provider("ambiguous", confidence=0.35),
    )

    decision = _read_json(output_path)["decision"]
    assert decision["history_decision"] == "ambiguous"
    assert decision["confidence"] == 0.35
    assert "ambiguous_low_confidence" in decision["warnings"]
    assert "ambiguous_conservative_question" in decision["warnings"]


def test_malformed_input_json_creates_failed_output_and_report(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    report_path = tmp_path / "report.json"
    input_path.write_text("{not-json", encoding="utf-8")

    result = run_history_manager_workflow(
        input_path=input_path,
        output_path=output_path,
        report_output_path=report_path,
        config=HistoryManagerConfig(),
        provider=_provider("follow_up"),
    )

    assert result.status == "failed"
    assert _read_json(output_path)["status"] == "failed"
    assert _read_json(report_path)["status"] == "failed"
    assert result.failed_items


def test_provider_failure_creates_failed_item_without_secret(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    report_path = tmp_path / "report.json"
    _write_input(input_path)

    run_history_manager_workflow(
        input_path=input_path,
        output_path=output_path,
        report_output_path=report_path,
        config=HistoryManagerConfig(),
        provider=FakeHistoryLLMProvider(
            LLMProviderError(
                code="synthetic_provider_error",
                message="OPENAI_API_KEY Authorization API key secret-like",
                retryable=True,
            )
        ),
    )

    serialized = output_path.read_text(encoding="utf-8") + report_path.read_text(
        encoding="utf-8"
    )
    assert "failed_items" in serialized
    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "API key" not in serialized
    assert "secret-like" not in serialized


def test_cli_runs_workflow_with_fake_provider(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    report_path = tmp_path / "report.json"
    _write_input(input_path)

    exit_code = run_history_manager.main(
        [
            "--input",
            str(input_path),
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
    assert "status=success" in captured.out
    assert output_path.exists()
    assert report_path.exists()
    assert "OPENAI_API_KEY" not in captured.out + captured.err
    assert "Authorization" not in captured.out + captured.err


def test_langgraph_missing_uses_sequential_fallback() -> None:
    workflow = build_history_manager_workflow(use_langgraph=True)

    assert workflow.execution_mode in {"langgraph", "sequential_fallback"}


def test_workflow_outputs_do_not_expose_sensitive_terms(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    report_path = tmp_path / "report.json"
    _write_input(input_path)

    run_history_manager_workflow(
        input_path=input_path,
        output_path=output_path,
        report_output_path=report_path,
        config=HistoryManagerConfig(),
        provider=_provider("follow_up"),
    )

    serialized = output_path.read_text(encoding="utf-8") + report_path.read_text(
        encoding="utf-8"
    )
    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "API key" not in serialized
    assert "secret-like" not in serialized
