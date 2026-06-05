from __future__ import annotations

import json
from pathlib import Path

import pytest

from answer_generation_agent.app import build_app_context
from answer_generation_agent.config import AnswerGenerationConfig
from answer_generation_agent.scripts import run_answer_generation
from answer_generation_agent.schemas import (
    AnswerOutput,
    AnswerStatus,
    FailedItem,
    GeneratedSentence,
    GeneratedSource,
    GenerationInput,
    GenerationReport,
    GenerationReportStatus,
    RoutingDecisionInput,
    SearchResults,
    StreamChunk,
    StreamChunkType,
    StreamingOutput,
    TaskPromptType,
    TopContext,
    WarningItem,
)


def test_config_accepts_external_runtime_values_and_redacts_key() -> None:
    config = AnswerGenerationConfig(
        model="synthetic-generation-model",
        fallback_model="synthetic-fallback-model",
        temperature=0.1,
        timeout_seconds=20,
        max_retries=3,
        max_contexts=4,
        max_answer_sentences=6,
        streaming_supported=True,
        openai_api_key="synthetic-external-key",
    )

    safe = config.to_safe_dict()

    assert config.model == "synthetic-generation-model"
    assert config.fallback_model == "synthetic-fallback-model"
    assert config.temperature == 0.1
    assert config.timeout_seconds == 20
    assert config.max_retries == 3
    assert config.max_contexts == 4
    assert config.max_answer_sentences == 6
    assert config.streaming_supported is True
    assert "synthetic-external-key" not in repr(config)
    assert safe["openai_api_key"] == "<redacted>"
    assert "synthetic-external-key" not in json.dumps(safe)
    assert "Authorization" not in json.dumps(safe)


def test_generation_input_schema_contains_routing_and_search_results() -> None:
    generation_input = _generation_input()

    payload = generation_input.to_dict()

    assert payload["conversation_id"] == "conversation-synthetic"
    assert payload["user_id"] == "user-synthetic"
    assert payload["routing_decision"]["routing_id"] == "routing-synthetic"
    assert payload["routing_decision"]["query"] == "IAM rollback procedure"
    assert payload["routing_decision"]["task_prompt_type"] == "timeline"
    assert payload["routing_decision"]["expanded_queries"] == ["IAM rollback"]
    assert payload["routing_decision"]["metadata_filters"] == {"space_keys": ["OPS"]}
    assert payload["routing_decision"]["pool_weights"] == {"content": 1.0}
    assert payload["search_results"]["top_contexts"][0]["context_id"] == "ctx-001"
    assert payload["metadata"] == {"locale": "ko-KR"}


def test_routing_decision_and_task_prompt_enums_support_mvp_values() -> None:
    assert TaskPromptType.TIMELINE.value == "timeline"
    assert TaskPromptType.STEP_BY_STEP.value == "step_by_step"
    assert TaskPromptType.EVIDENCE_FIRST.value == "evidence_first"
    assert TaskPromptType.HISTORY_SUMMARY.value == "history_summary"
    assert TaskPromptType.GENERAL.value == "general"
    assert TaskPromptType.from_value("future_prompt") == "future_prompt"

    routing = _routing_decision()
    assert routing.to_dict()["intent"] == "incident_response"
    assert routing.to_dict()["task_prompt_type"] == "timeline"


def test_top_context_schema_preserves_source_metadata() -> None:
    context = _top_context()
    payload = context.to_dict()

    assert payload["context_id"] == "ctx-001"
    assert payload["document_id"] == "doc-001"
    assert payload["chunk_id"] == "chunk-001"
    assert payload["title"] == "Synthetic IAM Runbook"
    assert payload["space_key"] == "OPS"
    assert payload["source_url"] == "https://example.invalid/confluence/pages/123"
    assert payload["content"] == "Rollback steps are documented in this synthetic context."
    assert payload["score"] == 0.7
    assert payload["rerank_score"] == 0.9
    assert payload["metadata"]["page_id"] == "123"


def test_answer_output_schema_is_verification_agent_compatible() -> None:
    sentence = GeneratedSentence(
        sentence_id="s1",
        text="Rollback should follow the documented runbook.",
        citations=["ctx-001"],
        citation_required=True,
    )
    source = GeneratedSource(
        source_id="ctx-001",
        context_id="ctx-001",
        document_id="doc-001",
        chunk_id="chunk-001",
        title="Synthetic IAM Runbook",
        source_url="https://example.invalid/confluence/pages/123",
        space_key="OPS",
        page_id="123",
        attachment_filename=None,
        score=0.7,
        rerank_score=0.9,
    )
    output = AnswerOutput(
        generation_id="generation-synthetic",
        conversation_id="conversation-synthetic",
        user_id="user-synthetic",
        answer_status=AnswerStatus.SUCCESS,
        answer="Rollback should follow the documented runbook.",
        sentences=[sentence],
        sources=[source],
        used_context_ids=["ctx-001"],
        routing={
            "routing_id": "routing-synthetic",
            "intent": "incident_response",
            "task_prompt_type": "timeline",
        },
        model="synthetic-generation-model",
        confidence=0.8,
        insufficient_context=False,
        unsupported_gaps=[],
        streaming=StreamingOutput(streaming_supported=False, stream_chunks=[]),
        warnings=[WarningItem(code="synthetic_warning", message="Synthetic warning.")],
    )

    payload = output.to_dict()

    assert payload["generation_id"] == "generation-synthetic"
    assert payload["answer_status"] == "success"
    assert payload["sentences"][0]["citations"] == ["ctx-001"]
    assert payload["sources"][0]["context_id"] == "ctx-001"
    assert payload["used_context_ids"] == ["ctx-001"]
    assert payload["routing"]["task_prompt_type"] == "timeline"
    assert payload["streaming"] == {"streaming_supported": False, "stream_chunks": []}


def test_stream_chunk_and_status_enums_support_mvp_values() -> None:
    assert AnswerStatus.SUCCESS.value == "success"
    assert AnswerStatus.INSUFFICIENT_CONTEXT.value == "insufficient_context"
    assert AnswerStatus.FAILED.value == "failed"
    assert AnswerStatus.from_value("future_status") == "future_status"

    chunk = StreamChunk(
        generation_id="generation-synthetic",
        chunk_index=0,
        chunk_type=StreamChunkType.TEXT,
        content="Synthetic chunk",
        metadata={"part": "answer"},
    )

    assert chunk.to_dict() == {
        "generation_id": "generation-synthetic",
        "chunk_index": 0,
        "chunk_type": "text",
        "content": "Synthetic chunk",
        "metadata": {"part": "answer"},
    }


def test_generation_report_failed_item_and_warning_shapes() -> None:
    report = GenerationReport(
        job_id="job-synthetic",
        generation_id="generation-synthetic",
        conversation_id="conversation-synthetic",
        status=GenerationReportStatus.SUCCESS,
        answer_status=AnswerStatus.SUCCESS,
        context_count=2,
        used_context_count=1,
        sentence_count=1,
        citation_count=1,
        warnings_count=0,
        created_at="2026-05-18T00:00:00Z",
    )
    failed = FailedItem(
        item_id="input-synthetic",
        reason="Synthetic failure",
        retryable=False,
        error_type="validation_error",
    )
    warning = WarningItem(code="synthetic_warning", message="Synthetic warning.")

    assert report.to_dict()["status"] == "success"
    assert report.to_dict()["answer_status"] == "success"
    assert failed.to_dict()["retryable"] is False
    assert warning.to_dict() == {
        "code": "synthetic_warning",
        "message": "Synthetic warning.",
    }


def test_required_values_raise_clear_validation_errors() -> None:
    with pytest.raises(ValueError, match="conversation_id is required"):
        GenerationInput(
            conversation_id="",
            user_id="user-synthetic",
            routing_decision=_routing_decision(),
            search_results=SearchResults(top_contexts=[]),
            metadata={},
        )

    with pytest.raises(ValueError, match="context_id is required"):
        TopContext(
            context_id="",
            document_id="doc-001",
            chunk_id="chunk-001",
            title="title",
            space_key="OPS",
            source_url="https://example.invalid",
            content="content",
            score=0.0,
            rerank_score=0.0,
            metadata={},
        )

    with pytest.raises(ValueError, match="answer is required"):
        AnswerOutput(
            generation_id="generation-synthetic",
            conversation_id="conversation-synthetic",
            user_id="user-synthetic",
            answer_status=AnswerStatus.SUCCESS,
            answer="",
            sentences=[],
            sources=[],
            used_context_ids=[],
            routing={"routing_id": "routing-synthetic"},
            model="synthetic-model",
            confidence=0.5,
            insufficient_context=False,
            unsupported_gaps=[],
            streaming=StreamingOutput(),
            warnings=[],
        )


def test_cli_skeleton_validates_input_without_openai_or_search(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "generation_input.json"
    output_path = tmp_path / "answer.json"
    input_path.write_text(json.dumps(_generation_input().to_dict()), encoding="utf-8")

    context = build_app_context(
        input_path=input_path,
        output_path=output_path,
        config=AnswerGenerationConfig(model="synthetic-generation-model"),
    )

    assert context.input_path == input_path
    assert context.output_path == output_path
    assert context.config.model == "synthetic-generation-model"

    exit_code = run_answer_generation.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "synthetic-generation-model",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "validated" in captured.out
    assert "OPENAI_API_KEY" not in captured.out
    assert "Authorization" not in captured.out
    assert "qdrant" not in captured.out.lower()
    assert "embedding" not in captured.out.lower()


def _generation_input() -> GenerationInput:
    return GenerationInput(
        conversation_id="conversation-synthetic",
        user_id="user-synthetic",
        routing_decision=_routing_decision(),
        search_results=SearchResults(top_contexts=[_top_context()]),
        metadata={"locale": "ko-KR"},
    )


def _routing_decision() -> RoutingDecisionInput:
    return RoutingDecisionInput(
        routing_id="routing-synthetic",
        original_question="Rollback?",
        query="IAM rollback procedure",
        intent="incident_response",
        task_prompt_type=TaskPromptType.TIMELINE,
        expanded_queries=["IAM rollback"],
        metadata_filters={"space_keys": ["OPS"]},
        pool_weights={"content": 1.0},
        confidence=0.77,
        warnings=[],
    )


def _top_context() -> TopContext:
    return TopContext(
        context_id="ctx-001",
        document_id="doc-001",
        chunk_id="chunk-001",
        title="Synthetic IAM Runbook",
        space_key="OPS",
        source_url="https://example.invalid/confluence/pages/123",
        content="Rollback steps are documented in this synthetic context.",
        score=0.7,
        rerank_score=0.9,
        metadata={
            "page_id": "123",
            "attachment_filename": None,
            "last_modified_at": "2026-05-18T00:00:00Z",
        },
    )
