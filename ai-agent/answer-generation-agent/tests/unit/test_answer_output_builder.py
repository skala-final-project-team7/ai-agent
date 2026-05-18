from __future__ import annotations

import json

from answer_generation_agent.generation.answer_generation import (
    AnswerGenerationResult,
    AnswerProviderError,
    RawSentenceCandidate,
)
from answer_generation_agent.generation.answer_output_builder import (
    build_answer_output,
    build_failed_answer_output,
    build_failed_item,
    build_generation_id,
    build_generation_report,
    write_answer_outputs,
)
from answer_generation_agent.generation.citation_mapping import map_citations
from answer_generation_agent.generation.input_normalization import normalize_generation_input
from answer_generation_agent.generation.prompt_template import build_prompt_payload
from answer_generation_agent.schemas import AnswerStatus, GenerationReportStatus, WarningItem


def test_answer_output_contains_canonical_required_fields() -> None:
    normalized_input = _normalized_result()
    generation_result = _generation_result()
    citation_result = map_citations(
        generation_result=generation_result,
        normalized_input=normalized_input,
    )

    output = build_answer_output(
        normalized_input=normalized_input,
        generation_result=generation_result,
        citation_result=citation_result,
    )
    payload = output.to_dict()

    assert payload["generation_id"].startswith("generation-")
    assert payload["answer_status"] == "success"
    assert payload["answer"]
    assert payload["sentences"][0]["text"] == "Synthetic rollback step is documented."
    assert payload["sentences"][0]["citations"] == ["ctx-001"]
    assert payload["sources"][0]["context_id"] == "ctx-001"
    assert payload["used_context_ids"] == ["ctx-001"]
    assert payload["routing"]["routing_id"] == "routing-synthetic"
    assert payload["routing"]["intent"] == "incident_response"
    assert payload["routing"]["task_prompt_type"] == "timeline"
    assert payload["model"] == "synthetic-model"
    assert payload["confidence"] == 0.82
    assert payload["insufficient_context"] is False
    assert payload["streaming"]["streaming_supported"] is False


def test_generation_id_is_deterministic_and_traceable() -> None:
    normalized_input = _normalized_result()

    first = build_generation_id(normalized_input)
    second = build_generation_id(normalized_input)

    assert first == second
    assert first.startswith("generation-")


def test_success_result_maps_to_success_status() -> None:
    output = build_answer_output(
        normalized_input=_normalized_result(),
        generation_result=_generation_result(),
        citation_result=_citation_result(),
    )

    assert output.answer_status == AnswerStatus.SUCCESS
    assert output.insufficient_context is False


def test_insufficient_context_result_maps_to_insufficient_context_status() -> None:
    normalized_input = _normalized_result(contexts=[])
    generation_result = _generation_result(
        answer_status="insufficient_context",
        answer_text="",
        warnings=[
            WarningItem(
                code="insufficient_context",
                message="No usable context is available.",
            )
        ],
    )

    output = build_answer_output(
        normalized_input=normalized_input,
        generation_result=generation_result,
        citation_result=_empty_citation_result(),
    )

    assert output.answer_status == AnswerStatus.INSUFFICIENT_CONTEXT
    assert output.insufficient_context is True
    assert output.answer
    assert output.sentences == []
    assert any(warning.code == "insufficient_context" for warning in output.warnings)


def test_failed_generation_result_maps_to_failed_answer_output() -> None:
    output = build_failed_answer_output(
        normalized_input=_normalized_result(),
        error=AnswerProviderError(
            message="OPENAI_API_KEY Authorization API key secret synthetic-marker",
            retryable=True,
            error_type="server_error",
        ),
        model="synthetic-model",
    )
    serialized = json.dumps(output.to_dict())

    assert output.answer_status == AnswerStatus.FAILED
    assert output.insufficient_context is False
    assert output.answer
    assert output.model == "synthetic-model"
    assert any(warning.code == "answer_generation_failed" for warning in output.warnings)
    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "synthetic-marker" not in serialized
    assert "secret" not in serialized.lower()


def test_sentences_sources_and_used_context_ids_are_preserved() -> None:
    output = build_answer_output(
        normalized_input=_normalized_result(),
        generation_result=_generation_result(),
        citation_result=_citation_result(),
    )

    assert [sentence.sentence_id for sentence in output.sentences] == ["s1"]
    assert [source.context_id for source in output.sources] == ["ctx-001"]
    assert output.used_context_ids == ["ctx-001"]


def test_model_confidence_warnings_and_unsupported_gaps_are_merged() -> None:
    normalized_input = _normalized_result()
    generation_result = _generation_result(
        unsupported_gaps=["Synthetic unsupported gap."],
        warnings=[
            WarningItem(code="weak_context", message="Synthetic weak context warning.")
        ],
    )
    citation_result = map_citations(
        generation_result=generation_result,
        normalized_input=normalized_input,
    )

    output = build_answer_output(
        normalized_input=normalized_input,
        generation_result=generation_result,
        citation_result=citation_result,
    )

    assert output.model == "synthetic-model"
    assert output.confidence == 0.82
    assert output.unsupported_gaps == ["Synthetic unsupported gap."]
    warning_codes = {warning.code for warning in output.warnings}
    assert "normalization_warning" not in warning_codes
    assert "weak_context" in warning_codes


def test_streaming_schema_is_interface_only_and_chunkable() -> None:
    output = build_answer_output(
        normalized_input=_normalized_result(),
        generation_result=_generation_result(),
        citation_result=_citation_result(),
    )
    streaming = output.streaming.to_dict()

    assert streaming["streaming_supported"] is False
    assert streaming["stream_chunks"][0]["chunk_type"] == "text"
    assert streaming["stream_chunks"][0]["content"] == output.answer
    assert streaming["stream_chunks"][0]["metadata"]["interface_only"] is True


def test_generation_report_calculates_counts() -> None:
    output = build_answer_output(
        normalized_input=_normalized_result(),
        generation_result=_generation_result(),
        citation_result=_citation_result(),
    )

    report = build_generation_report(
        answer_output=output,
        normalized_input=_normalized_result(),
        created_at="2026-05-18T00:00:00Z",
    )

    assert report.status == GenerationReportStatus.SUCCESS
    assert report.answer_status == AnswerStatus.SUCCESS
    assert report.context_count == 1
    assert report.used_context_count == 1
    assert report.sentence_count == 1
    assert report.citation_count == 1
    assert report.warnings_count == len(output.warnings)


def test_failed_item_helper_generates_safe_error_shape() -> None:
    failed_item = build_failed_item(
        item_id="generation-synthetic",
        error=AnswerProviderError(
            message="Authorization failed with synthetic-marker secret",
            retryable=False,
            error_type="auth_error",
        ),
    )
    payload = failed_item.to_dict()

    assert payload["item_id"] == "generation-synthetic"
    assert payload["retryable"] is False
    assert payload["error_type"] == "auth_error"
    assert "Authorization" not in payload["reason"]
    assert "synthetic-marker" not in payload["reason"]
    assert "secret" not in payload["reason"].lower()


def test_local_json_writer_creates_output_report_and_failed_files(tmp_path) -> None:
    output = build_answer_output(
        normalized_input=_normalized_result(),
        generation_result=_generation_result(),
        citation_result=_citation_result(),
    )
    report = build_generation_report(
        answer_output=output,
        normalized_input=_normalized_result(),
        created_at="2026-05-18T00:00:00Z",
    )
    failed_item = build_failed_item(
        item_id=output.generation_id,
        error=AnswerProviderError(
            message="OPENAI_API_KEY Authorization API key secret synthetic-marker",
            retryable=True,
            error_type="server_error",
        ),
    )

    write_result = write_answer_outputs(
        output_dir=tmp_path / "missing" / "nested",
        answer_output=output,
        report=report,
        failed_item=failed_item,
    )

    assert write_result.output_path.exists()
    assert write_result.report_path.exists()
    assert write_result.failed_path is not None
    assert write_result.failed_path.exists()
    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            write_result.output_path,
            write_result.report_path,
            write_result.failed_path,
        )
    )
    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "synthetic-marker" not in serialized
    assert "secret" not in serialized.lower()


def test_sentence_text_and_citations_remain_separated_for_verification() -> None:
    output = build_answer_output(
        normalized_input=_normalized_result(),
        generation_result=_generation_result(),
        citation_result=_citation_result(),
    )
    sentence_payload = output.to_dict()["sentences"][0]

    assert sentence_payload["text"] == "Synthetic rollback step is documented."
    assert sentence_payload["citations"] == ["ctx-001"]
    assert "ctx-001" not in sentence_payload["text"]


def _generation_result(
    *,
    answer_status: str = "success",
    answer_text: str = "Synthetic rollback step is documented.",
    unsupported_gaps: list[str] | None = None,
    warnings: list[WarningItem] | None = None,
) -> AnswerGenerationResult:
    return AnswerGenerationResult(
        answer_status=answer_status,
        answer_text=answer_text,
        model="synthetic-model",
        provider_name="fake",
        prompt=build_prompt_payload(_normalized_result()),
        raw_sentence_candidates=[
            RawSentenceCandidate(
                text="Synthetic rollback step is documented.",
                citations=["ctx-001"],
            )
        ]
        if answer_text
        else [],
        unsupported_gaps=unsupported_gaps or [],
        warnings=warnings or [],
    )


def _citation_result():
    generation_result = _generation_result()
    return map_citations(
        generation_result=generation_result,
        normalized_input=_normalized_result(),
    )


def _empty_citation_result():
    generation_result = _generation_result(answer_status="insufficient_context", answer_text="")
    return map_citations(
        generation_result=generation_result,
        normalized_input=_normalized_result(contexts=[]),
    )


def _normalized_result(*, contexts: list[dict] | None = None):
    payload = {
        "conversation_id": "conversation-synthetic",
        "user_id": "user-synthetic",
        "routing_decision": {
            "routing_id": "routing-synthetic",
            "original_question": "What is the rollback step?",
            "query": "rollback step",
            "intent": "incident_response",
            "task_prompt_type": "timeline",
            "expanded_queries": ["rollback step"],
            "metadata_filters": {"space_keys": ["OPS"]},
            "pool_weights": {"title": 0.2, "content": 0.65, "label": 0.15},
            "confidence": 0.82,
            "warnings": [],
        },
        "search_results": {"top_contexts": contexts if contexts is not None else [_context()]},
        "metadata": {"locale": "ko-KR"},
    }
    return normalize_generation_input(payload)


def _context(context_id: str = "ctx-001") -> dict:
    return {
        "context_id": context_id,
        "document_id": f"doc-{context_id}",
        "chunk_id": f"chunk-{context_id}",
        "title": "Synthetic Runbook",
        "space_key": "OPS",
        "source_url": f"https://example.invalid/{context_id}",
        "content": "Synthetic rollback context.",
        "score": 0.7,
        "rerank_score": 0.9,
        "metadata": {"page_id": f"page-{context_id}"},
    }
