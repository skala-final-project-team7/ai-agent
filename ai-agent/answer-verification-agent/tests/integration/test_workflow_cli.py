from __future__ import annotations

import json
from pathlib import Path

from answer_verification_agent.evaluator import EvaluatorProviderError, SentenceEvaluation
from answer_verification_agent.schemas import SentenceLabel
from answer_verification_agent.scripts.run_answer_verification import main
from answer_verification_agent.workflow import run_verification_workflow


def test_workflow_writes_supported_output_report_and_qca(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, _payload())
    paths = _paths(tmp_path)

    result = run_verification_workflow(input_path=input_path, **paths)

    assert result.status == "success"
    output = json.loads(paths["output_path"].read_text(encoding="utf-8"))
    report = json.loads(paths["report_output_path"].read_text(encoding="utf-8"))
    qca = json.loads(paths["qca_output_path"].read_text(encoding="utf-8"))
    assert output["overall_label"] == "PASS"
    assert report["status"] == "success"
    assert qca["quality_label"] == "accepted"
    assert json.loads(paths["failed_output_path"].read_text(encoding="utf-8")) == []


def test_workflow_unsupported_input_creates_warning_and_regeneration(tmp_path: Path) -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "Rollback version v2.4.1 finished on 2026-05-18 with 99% success."
    payload["contexts"][0][
        "content"
    ] = "Rollback version v2.4.0 finished on 2026-05-17 with 90% success."
    input_path = _write_input(tmp_path, payload)
    paths = _paths(tmp_path)

    result = run_verification_workflow(input_path=input_path, **paths)

    output = json.loads(paths["output_path"].read_text(encoding="utf-8"))
    assert result.status == "success"
    assert output["overall_label"] == "UNSUPPORTED"
    assert output["ui_warning_required"] is True
    assert output["regeneration_recommended"] is True
    assert output["regeneration_request"]["unsupported_sentence_ids"] == ["s1"]


def test_workflow_malformed_input_writes_failed_report(tmp_path: Path) -> None:
    input_path = tmp_path / "malformed.json"
    input_path.write_text("{not-json", encoding="utf-8")
    paths = _paths(tmp_path)

    result = run_verification_workflow(input_path=input_path, **paths)

    failed = json.loads(paths["failed_output_path"].read_text(encoding="utf-8"))
    report = json.loads(paths["report_output_path"].read_text(encoding="utf-8"))
    assert result.status == "failed"
    assert failed[0]["error_type"] == "malformed_json"
    assert report["status"] == "failed"


def test_provider_failure_keeps_workflow_low_confidence(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, _payload())
    paths = _paths(tmp_path)

    result = run_verification_workflow(
        input_path=input_path,
        provider=FailingProvider(),
        evaluate_suspicious_only=False,
        **paths,
    )

    output = json.loads(paths["output_path"].read_text(encoding="utf-8"))
    failed = json.loads(paths["failed_output_path"].read_text(encoding="utf-8"))
    assert result.status == "partial_success"
    assert output["overall_label"] == "LOW_CONFIDENCE"
    assert failed[0]["error_type"] == "provider_failure"


def test_cli_writes_requested_files_without_secret_output(
    tmp_path: Path,
    capsys,
) -> None:
    input_path = _write_input(tmp_path, _payload())
    paths = _paths(tmp_path)

    exit_code = main(
        [
            "--input",
            str(input_path),
            "--output",
            str(paths["output_path"]),
            "--report-output",
            str(paths["report_output_path"]),
            "--qca-output",
            str(paths["qca_output_path"]),
            "--failed-output",
            str(paths["failed_output_path"]),
            "--provider",
            "fake",
            "--model",
            "synthetic-model",
            "--pretty",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    for path in paths.values():
        assert path.exists()
    assert "OPENAI_API_KEY" not in captured.out
    assert "Authorization" not in captured.out


def test_openai_provider_mode_can_avoid_live_call_with_injected_provider(
    tmp_path: Path,
) -> None:
    input_path = _write_input(tmp_path, _payload())
    paths = _paths(tmp_path)
    provider = StaticProvider()

    result = run_verification_workflow(
        input_path=input_path,
        provider_mode="openai",
        provider=provider,
        evaluate_suspicious_only=False,
        **paths,
    )

    output = json.loads(paths["output_path"].read_text(encoding="utf-8"))
    assert result.status == "success"
    assert provider.called is True
    assert output["llm_evaluation_used"] is True


def test_workflow_uses_sequential_fallback_without_langgraph(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, _payload())
    paths = _paths(tmp_path)

    result = run_verification_workflow(input_path=input_path, **paths)

    assert result.execution_mode in {"sequential_fallback", "langgraph"}
    assert result.execution_mode == "sequential_fallback"


def test_output_files_do_not_contain_secret_like_values(tmp_path: Path) -> None:
    payload = _payload()
    payload["answer_output"]["answer"] = (
        "OPENAI_API_KEY=synthetic-secret Authorization: Bearer synthetic-token"
    )
    payload["answer_output"]["sentences"][0]["text"] = payload["answer_output"]["answer"]
    input_path = _write_input(tmp_path, payload)
    paths = _paths(tmp_path)

    run_verification_workflow(input_path=input_path, **paths)

    rendered = "\n".join(path.read_text(encoding="utf-8") for path in paths.values())
    assert "synthetic-secret" not in rendered
    assert "synthetic-token" not in rendered
    assert "Authorization: Bearer" not in rendered


class StaticProvider:
    def __init__(self) -> None:
        self.called = False

    def evaluate_sentence(self, target, contexts):
        self.called = True
        return SentenceEvaluation(
            sentence_id=target.sentence_id,
            label=SentenceLabel.SUPPORTED,
            score=0.9,
            reason="Static injected provider result.",
        )


class FailingProvider:
    def evaluate_sentence(self, target, contexts):
        raise EvaluatorProviderError(
            "Authorization: Bearer synthetic-token provider failed",
            error_type="provider_failure",
            retryable=True,
        )


def _write_input(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "output_path": tmp_path / "out" / "verification_output.json",
        "report_output_path": tmp_path / "reports" / "verification_report.json",
        "qca_output_path": tmp_path / "qca" / "qca_output.json",
        "failed_output_path": tmp_path / "failed" / "failed_items.json",
    }


def _payload() -> dict[str, object]:
    return {
        "conversation_id": "conversation-synthetic",
        "user_id": "user-synthetic",
        "answer_output": {
            "generation_id": "generation-synthetic",
            "answer_status": "success",
            "answer": "Rollback follows the documented runbook.",
            "sentences": [
                {
                    "sentence_id": "s1",
                    "text": "Rollback follows the documented runbook.",
                    "citations": ["ctx-001"],
                    "citation_required": True,
                }
            ],
            "sources": [],
            "used_context_ids": ["ctx-001"],
            "routing": {
                "routing_id": "routing-synthetic",
                "intent": "incident_response",
                "task_prompt_type": "timeline",
            },
            "model": "synthetic-generation-model",
            "confidence": 0.8,
            "warnings": [],
        },
        "contexts": [
            {
                "context_id": "ctx-001",
                "document_id": "doc-001",
                "chunk_id": "chunk-001",
                "title": "Synthetic IAM Runbook",
                "space_key": "OPS",
                "source_url": "https://example.invalid/confluence/pages/123",
                "content": "Rollback follows the documented runbook and includes verification evidence.",
                "score": 0.7,
                "rerank_score": 0.9,
                "metadata": {"page_id": "123"},
            }
        ],
        "metadata": {"query": "How should rollback be handled?"},
    }
