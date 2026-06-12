"""ai-agent/answer-generation-agent/tests/integration/test_workflow_cli.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from answer_generation_agent.config import AnswerGenerationConfig
from answer_generation_agent.generation import (
    AnswerProviderError,
    FakeAnswerLLMProvider,
)
from answer_generation_agent.generation.workflow import (
    build_workflow,
    run_answer_generation_workflow,
)


def test_workflow_runs_generation_steps_in_order_with_fake_provider(tmp_path: Path) -> None:
    provider = _fake_provider("Timeline answer.", "timeline")
    result = run_answer_generation_workflow(
        input_path=_write_input(tmp_path, task_prompt_type="timeline"),
        output_path=tmp_path / "answer.json",
        report_output_path=tmp_path / "report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=provider,
    )

    assert result.status == "success"
    assert result.executed_nodes == [
        "load_config",
        "load_input",
        "normalize_generation_input",
        "validate_top_contexts",
        "assess_context_sufficiency",
        "build_task_prompt",
        "generate_answer",
        "map_sentence_citations",
        "build_answer_output",
        "write_output",
        "write_report",
    ]
    assert provider.requests[0].prompt.task_prompt_type == "timeline"
    assert result.answer_output.answer_status == "success"


def test_workflow_writes_answer_output_and_report_json(tmp_path: Path) -> None:
    result = run_answer_generation_workflow(
        input_path=_write_input(tmp_path),
        output_path=tmp_path / "nested" / "answer.json",
        report_output_path=tmp_path / "nested" / "report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=_fake_provider("Supported answer.", "general"),
    )

    assert result.output_path.exists()
    assert result.report_path.exists()
    output_payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    report_payload = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert output_payload["answer_status"] == "success"
    assert output_payload["sentences"][0]["citations"] == ["ctx-001"]
    assert report_payload["answer_status"] == "success"


@pytest.mark.parametrize(
    ("task_prompt_type", "expected_phrase"),
    [
        ("timeline", "timeline"),
        ("step_by_step", "step_by_step"),
        ("evidence_first", "evidence_first"),
        ("history_summary", "history_summary"),
    ],
)
def test_task_prompt_type_fixtures_create_answer_output(
    tmp_path: Path,
    task_prompt_type: str,
    expected_phrase: str,
) -> None:
    result = run_answer_generation_workflow(
        input_path=_write_input(tmp_path, task_prompt_type=task_prompt_type),
        output_path=tmp_path / f"{task_prompt_type}.json",
        report_output_path=tmp_path / f"{task_prompt_type}-report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=_fake_provider(f"Synthetic {expected_phrase} answer.", task_prompt_type),
    )

    assert result.answer_output.routing["task_prompt_type"] == task_prompt_type
    assert result.answer_output.answer_status == "success"
    assert result.answer_output.sources[0].context_id == "ctx-001"


def test_insufficient_context_fixture_creates_insufficient_output(tmp_path: Path) -> None:
    provider = _fake_provider("Should not be called.", "general")
    result = run_answer_generation_workflow(
        input_path=_write_input(tmp_path, contexts=[]),
        output_path=tmp_path / "answer.json",
        report_output_path=tmp_path / "report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=provider,
    )

    assert result.status == "partial_success"
    assert result.answer_output.answer_status == "insufficient_context"
    assert result.answer_output.insufficient_context is True
    assert provider.requests == []


def test_provider_failure_writes_failed_output_report_and_failed_item(tmp_path: Path) -> None:
    provider = FakeAnswerLLMProvider(
        error=AnswerProviderError(
            message="OPENAI_API_KEY Authorization API key secret synthetic-marker",
            retryable=True,
            error_type="server_error",
        )
    )
    result = run_answer_generation_workflow(
        input_path=_write_input(tmp_path),
        output_path=tmp_path / "answer.json",
        report_output_path=tmp_path / "report.json",
        failed_output_path=tmp_path / "failed.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=provider,
    )
    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (result.output_path, result.report_path, result.failed_path)
        if path is not None
    )

    assert result.status == "failed"
    assert result.answer_output.answer_status == "failed"
    assert result.failed_path is not None
    assert result.failed_path.exists()
    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "synthetic-marker" not in serialized
    assert "secret" not in serialized.lower()


def test_cli_runs_workflow_with_input_and_output_arguments(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, task_prompt_type="timeline")
    output_path = tmp_path / "cli-answer.json"
    report_path = tmp_path / "cli-report.json"
    failed_path = tmp_path / "cli-failed.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_answer_generation.py",
            "--input",
            str(input_path),
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
            "--max-contexts",
            "5",
            "--max-answer-sentences",
            "8",
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
    assert "OPENAI_API_KEY" not in combined_output
    assert "Authorization" not in combined_output
    assert "API key" not in combined_output


def test_langgraph_optional_builder_uses_sequential_fallback() -> None:
    workflow = build_workflow()

    assert workflow.engine in {"langgraph", "sequential"}
    assert workflow.engine == "sequential"
    assert "langgraph_optional" in workflow.capabilities


def test_workflow_marks_excluded_external_capabilities(tmp_path: Path) -> None:
    result = run_answer_generation_workflow(
        input_path=_write_input(tmp_path),
        output_path=tmp_path / "answer.json",
        report_output_path=tmp_path / "report.json",
        config=AnswerGenerationConfig(model="synthetic-model"),
        provider=_fake_provider("Supported answer.", "general"),
    )

    assert "qdrant_search" in result.excluded_capabilities
    assert "dense_sparse_embedding" in result.excluded_capabilities
    assert "cross_encoder_reranking" in result.excluded_capabilities
    assert "answer_verification_call" in result.excluded_capabilities
    assert "sse_transport" in result.excluded_capabilities


def _fake_provider(answer: str, task_prompt_type: str) -> FakeAnswerLLMProvider:
    return FakeAnswerLLMProvider(
        response={
            "answer": answer,
            "sentences": [{"text": answer, "citations": ["ctx-001"]}],
            "unsupported_gaps": [],
            "metadata": {"task_prompt_type": task_prompt_type},
        }
    )


def _write_input(
    tmp_path: Path,
    *,
    task_prompt_type: str = "general",
    contexts: list[dict] | None = None,
) -> Path:
    input_path = tmp_path / f"input-{task_prompt_type}.json"
    input_path.write_text(
        json.dumps(
            {
                "conversation_id": "conversation-synthetic",
                "user_id": "user-synthetic",
                "routing_decision": {
                    "routing_id": f"routing-{task_prompt_type}",
                    "original_question": "How should the synthetic issue be handled?",
                    "query": "synthetic issue handling",
                    "intent": "incident_response",
                    "task_prompt_type": task_prompt_type,
                    "expanded_queries": ["synthetic issue handling"],
                    "metadata_filters": {"space_keys": ["OPS"]},
                    "pool_weights": {"title": 0.2, "content": 0.65, "label": 0.15},
                    "confidence": 0.8,
                    "warnings": [],
                },
                "search_results": {
                    "top_contexts": contexts if contexts is not None else [_context()]
                },
                "metadata": {"locale": "ko-KR"},
            }
        ),
        encoding="utf-8",
    )
    return input_path


def _context() -> dict:
    return {
        "context_id": "ctx-001",
        "document_id": "doc-001",
        "chunk_id": "chunk-001",
        "title": "Synthetic Runbook",
        "space_key": "OPS",
        "source_url": "https://example.invalid/synthetic-runbook",
        "content": "Synthetic issue handling uses a documented rollback step.",
        "score": 0.7,
        "rerank_score": 0.9,
        "metadata": {"page_id": "page-001"},
    }
