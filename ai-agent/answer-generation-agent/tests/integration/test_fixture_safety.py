from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from answer_generation_agent.config import AnswerGenerationConfig
from answer_generation_agent.generation import AnswerProviderError, FakeAnswerLLMProvider
from answer_generation_agent.generation.workflow import run_answer_generation_workflow

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "answer_generation"
SENSITIVE_MARKERS = (
    "OPENAI_API_KEY",
    "Authorization",
    "API key",
    "synthetic-marker",
)


@pytest.mark.parametrize(
    ("fixture_name", "task_prompt_type", "context_id"),
    [
        ("timeline.json", "timeline", "ctx-timeline"),
        ("step_by_step.json", "step_by_step", "ctx-step"),
        ("evidence_first.json", "evidence_first", "ctx-evidence"),
        ("history_summary.json", "history_summary", "ctx-history"),
        ("general.json", "general", "ctx-general"),
    ],
)
def test_task_prompt_fixture_full_workflow_outputs_verification_shape(
    tmp_path: Path,
    fixture_name: str,
    task_prompt_type: str,
    context_id: str,
) -> None:
    result = run_answer_generation_workflow(
        input_path=FIXTURE_DIR / fixture_name,
        output_path=tmp_path / f"{task_prompt_type}-answer.json",
        report_output_path=tmp_path / f"{task_prompt_type}-report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=_provider_for(context_id, f"Synthetic {task_prompt_type} answer."),
    )
    output = json.loads(result.output_path.read_text(encoding="utf-8"))
    report = json.loads(result.report_path.read_text(encoding="utf-8"))

    assert output["answer_status"] == "success"
    assert output["routing"]["task_prompt_type"] == task_prompt_type
    assert output["sentences"][0]["citations"] == [context_id]
    assert output["sources"][0]["context_id"] == context_id
    assert output["used_context_ids"] == [context_id]
    assert output["streaming"]["streaming_supported"] is False
    _assert_answer_output_shape(output)
    _assert_report_shape(report)
    _assert_sentence_citations_reference_sources(output)


def test_insufficient_context_fixture_outputs_warning_without_provider_call(tmp_path: Path) -> None:
    provider = _provider_for("ctx-unused", "Should not be called.")

    result = run_answer_generation_workflow(
        input_path=FIXTURE_DIR / "insufficient_context.json",
        output_path=tmp_path / "answer.json",
        report_output_path=tmp_path / "report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=provider,
    )
    output = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert output["answer_status"] == "insufficient_context"
    assert output["insufficient_context"] is True
    assert any(warning["code"] == "insufficient_context" for warning in output["warnings"])
    assert provider.requests == []


def test_citation_fallback_and_missing_citation_warnings_are_safe(tmp_path: Path) -> None:
    fallback_result = run_answer_generation_workflow(
        input_path=FIXTURE_DIR / "general.json",
        output_path=tmp_path / "fallback-answer.json",
        report_output_path=tmp_path / "fallback-report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=FakeAnswerLLMProvider(
            response={
                "answer": "Synthetic answer without explicit citation.",
                "sentences": [],
                "unsupported_gaps": [],
            }
        ),
    )
    fallback_output = json.loads(fallback_result.output_path.read_text(encoding="utf-8"))

    assert fallback_output["sentences"][0]["citations"] == ["ctx-general"]
    assert any(
        warning["code"] == "fallback_citation_applied"
        for warning in fallback_output["warnings"]
    )

    two_context_input = _write_two_context_input(tmp_path)
    missing_result = run_answer_generation_workflow(
        input_path=two_context_input,
        output_path=tmp_path / "missing-answer.json",
        report_output_path=tmp_path / "missing-report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=FakeAnswerLLMProvider(
            response={
                "answer": "Synthetic answer without reliable citation.",
                "sentences": [],
                "unsupported_gaps": [],
            }
        ),
    )
    missing_output = json.loads(missing_result.output_path.read_text(encoding="utf-8"))

    assert missing_output["sentences"][0]["citations"] == []
    assert any(warning["code"] == "missing_citation" for warning in missing_output["warnings"])


def test_attachment_source_fixture_preserves_attachment_filename(tmp_path: Path) -> None:
    result = run_answer_generation_workflow(
        input_path=FIXTURE_DIR / "attachment_source.json",
        output_path=tmp_path / "answer.json",
        report_output_path=tmp_path / "report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=_provider_for("ctx-attachment", "Synthetic attachment answer."),
    )
    output = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert output["sources"][0]["attachment_filename"] == "synthetic-checklist.pdf"
    assert output["sources"][0]["page_id"] == "page-attachment"


def test_malformed_input_fixture_creates_failed_output_report_and_failed_item(
    tmp_path: Path,
) -> None:
    result = run_answer_generation_workflow(
        input_path=FIXTURE_DIR / "malformed_input.json",
        output_path=tmp_path / "malformed-answer.json",
        report_output_path=tmp_path / "malformed-report.json",
        failed_output_path=tmp_path / "malformed-failed.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=_provider_for("ctx-unused", "Should not be called."),
    )
    output = json.loads(result.output_path.read_text(encoding="utf-8"))
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    failed = json.loads(result.failed_path.read_text(encoding="utf-8"))

    assert result.status == "failed"
    assert output["answer_status"] == "failed"
    assert report["status"] == "failed"
    assert failed["failed_items"][0]["error_type"] == "input_error"
    _assert_no_sensitive_markers_in_files(
        result.output_path,
        result.report_path,
        result.failed_path,
    )


def test_provider_failure_fixture_creates_safe_failed_artifacts(tmp_path: Path) -> None:
    result = run_answer_generation_workflow(
        input_path=FIXTURE_DIR / "timeline.json",
        output_path=tmp_path / "provider-answer.json",
        report_output_path=tmp_path / "provider-report.json",
        failed_output_path=tmp_path / "provider-failed.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=FakeAnswerLLMProvider(
            error=AnswerProviderError(
                message="OPENAI_API_KEY Authorization API key secret synthetic-marker",
                retryable=True,
                error_type="server_error",
            )
        ),
    )

    assert result.status == "failed"
    assert result.failed_path is not None
    _assert_no_sensitive_markers_in_files(
        result.output_path,
        result.report_path,
        result.failed_path,
    )


def test_cli_fixture_run_does_not_expose_sensitive_markers(tmp_path: Path) -> None:
    output_path = tmp_path / "cli-answer.json"
    report_path = tmp_path / "cli-report.json"
    failed_path = tmp_path / "cli-failed.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_answer_generation.py",
            "--input",
            str(FIXTURE_DIR / "timeline.json"),
            "--output",
            str(output_path),
            "--report-output",
            str(report_path),
            "--failed-output",
            str(failed_path),
            "--provider",
            "fake",
            "--model",
            "synthetic-model",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    combined_output = completed.stdout + completed.stderr

    assert completed.returncode == 0
    assert output_path.exists()
    assert report_path.exists()
    assert "answer_status=success" in completed.stdout
    for marker in SENSITIVE_MARKERS:
        assert marker not in combined_output
    _assert_no_sensitive_markers_in_files(output_path, report_path)


def test_mvp_excluded_capabilities_are_not_executed(tmp_path: Path) -> None:
    result = run_answer_generation_workflow(
        input_path=FIXTURE_DIR / "general.json",
        output_path=tmp_path / "answer.json",
        report_output_path=tmp_path / "report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=_provider_for("ctx-general", "Synthetic general answer."),
    )

    assert "qdrant_search" in result.excluded_capabilities
    assert "dense_sparse_embedding" in result.excluded_capabilities
    assert "cross_encoder_reranking" in result.excluded_capabilities
    assert "answer_verification_call" in result.excluded_capabilities
    assert "sse_transport" in result.excluded_capabilities
    assert result.answer_output.streaming.streaming_supported is False


def test_fixture_files_do_not_contain_sensitive_markers() -> None:
    for fixture_path in FIXTURE_DIR.glob("*.json"):
        serialized = fixture_path.read_text(encoding="utf-8")
        for marker in SENSITIVE_MARKERS:
            assert marker not in serialized
        assert "secret" not in serialized.lower()


def _provider_for(context_id: str, answer: str) -> FakeAnswerLLMProvider:
    return FakeAnswerLLMProvider(
        response={
            "answer": answer,
            "sentences": [{"text": answer, "citations": [context_id]}],
            "unsupported_gaps": [],
        }
    )


def _assert_answer_output_shape(output: dict) -> None:
    required_fields = {
        "generation_id",
        "conversation_id",
        "user_id",
        "answer_status",
        "answer",
        "sentences",
        "sources",
        "used_context_ids",
        "routing",
        "model",
        "confidence",
        "insufficient_context",
        "unsupported_gaps",
        "streaming",
        "warnings",
    }
    assert required_fields.issubset(output)
    assert {"sentence_id", "text", "citations", "citation_required"}.issubset(
        output["sentences"][0]
    )
    assert "citations" not in output["sentences"][0]["text"]


def _assert_report_shape(report: dict) -> None:
    assert {
        "status",
        "answer_status",
        "context_count",
        "used_context_count",
        "sentence_count",
        "citation_count",
        "warnings_count",
    }.issubset(report)


def _assert_sentence_citations_reference_sources(output: dict) -> None:
    source_context_ids = {source["context_id"] for source in output["sources"]}
    for sentence in output["sentences"]:
        for citation in sentence["citations"]:
            assert citation in source_context_ids


def _assert_no_sensitive_markers_in_files(*paths: Path | None) -> None:
    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in paths
        if path is not None and path.exists()
    )
    for marker in SENSITIVE_MARKERS:
        assert marker not in serialized
    assert "secret" not in serialized.lower()


def _write_two_context_input(tmp_path: Path) -> Path:
    payload = json.loads((FIXTURE_DIR / "general.json").read_text(encoding="utf-8"))
    payload["search_results"]["top_contexts"].append(
        {
            "context_id": "ctx-general-2",
            "document_id": "doc-general-2",
            "chunk_id": "chunk-general-2",
            "title": "Synthetic Secondary Note",
            "space_key": "OPS",
            "source_url": "https://example.invalid/general-2",
            "content": "A second synthetic note creates ambiguous citation fallback.",
            "score": 0.66,
            "rerank_score": 0.87,
            "metadata": {"page_id": "page-general-2"},
        }
    )
    input_path = tmp_path / "two-contexts.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    return input_path
