from __future__ import annotations

import json
from pathlib import Path

import pytest

from answer_verification_agent.verification.input_normalization import (
    VerificationInputNormalizationError,
    load_verification_input,
    normalize_verification_input,
)


def test_loads_valid_input_json_and_returns_normalized_input(tmp_path: Path) -> None:
    input_path = tmp_path / "verification_input.json"
    input_path.write_text(json.dumps(_input_payload()), encoding="utf-8")

    result = load_verification_input(input_path)

    assert result.verification_input.conversation_id == "conversation-synthetic"
    assert result.verification_input.user_id == "user-synthetic"
    assert result.answer_output.generation_id == "generation-synthetic"
    assert result.contexts[0].context_id == "ctx-001"
    assert result.warnings == []


def test_normalizes_answer_output_core_fields() -> None:
    result = normalize_verification_input(_input_payload())

    answer = result.answer_output

    assert answer.generation_id == "generation-synthetic"
    assert answer.answer == "Rollback follows the documented runbook."
    assert answer.sentences[0]["sentence_id"] == "s1"
    assert answer.sentences[0]["citations"] == ["ctx-001"]
    assert answer.sources[0]["context_id"] == "ctx-001"
    assert answer.used_context_ids == ["ctx-001"]
    assert answer.routing == {
        "routing_id": "routing-synthetic",
        "intent": "incident_response",
        "task_prompt_type": "timeline",
    }
    assert answer.extra["custom_answer_field"] == "preserved"


def test_normalizes_top_contexts_and_preserves_metadata_and_extra_fields() -> None:
    payload = _input_payload()
    payload["contexts"][0]["extra_context_field"] = {"kept": True}
    payload["metadata"]["request_scope"] = {"trace": "synthetic-trace"}

    result = normalize_verification_input(payload)
    context = result.contexts[0]

    assert context.context_id == "ctx-001"
    assert context.document_id == "doc-001"
    assert context.chunk_id == "chunk-001"
    assert context.title == "Synthetic IAM Runbook"
    assert context.source_url == "https://example.invalid/confluence/pages/123"
    assert context.content == "Rollback follows the documented runbook."
    assert context.score == 0.7
    assert context.rerank_score == 0.9
    assert context.metadata["page_id"] == "123"
    assert context.extra["extra_context_field"] == {"kept": True}
    assert result.metadata["request_scope"] == {"trace": "synthetic-trace"}


def test_empty_sentences_create_fallback_warning_without_parsing() -> None:
    payload = _input_payload()
    payload["answer_output"]["sentences"] = []

    result = normalize_verification_input(payload)

    assert result.requires_sentence_fallback is True
    assert result.answer_output.sentences == []
    assert any(warning.code == "sentence_fallback_required" for warning in result.warnings)
    assert result.to_dict()["requires_sentence_fallback"] is True


def test_empty_contexts_create_low_confidence_warning() -> None:
    payload = _input_payload()
    payload["contexts"] = []

    result = normalize_verification_input(payload)

    assert result.has_contexts is False
    assert result.low_confidence_ready is True
    assert result.contexts == []
    assert any(warning.code == "contexts_empty" for warning in result.warnings)


def test_malformed_json_is_safe_non_retryable_error(tmp_path: Path) -> None:
    input_path = tmp_path / "bad.json"
    input_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(VerificationInputNormalizationError) as error_info:
        load_verification_input(input_path)

    error = error_info.value
    assert error.retryable is False
    assert error.error_type == "malformed_json"
    assert "OPENAI_API_KEY" not in str(error)
    assert "Authorization" not in str(error)


def test_missing_answer_output_raises_validation_error() -> None:
    payload = _input_payload()
    payload.pop("answer_output")

    with pytest.raises(VerificationInputNormalizationError) as error_info:
        normalize_verification_input(payload)

    error = error_info.value
    assert error.retryable is False
    assert error.error_type == "validation_error"
    assert "answer_output is required" in str(error)


def test_context_without_context_id_is_dropped_with_warning() -> None:
    payload = _input_payload()
    payload["contexts"].append(
        {
            "document_id": "doc-missing",
            "chunk_id": "chunk-missing",
            "title": "Missing Context Id",
            "source_url": "https://example.invalid/missing",
            "content": "This context has no id.",
        }
    )

    result = normalize_verification_input(payload)

    assert [context.context_id for context in result.contexts] == ["ctx-001"]
    assert any(warning.code == "context_id_missing" for warning in result.warnings)


def test_errors_and_warnings_redact_sensitive_values() -> None:
    payload = _input_payload()
    payload["answer_output"]["sentences"] = []
    payload["metadata"]["debug"] = "OPENAI_API_KEY=synthetic-secret Authorization: Bearer synthetic-token"

    result = normalize_verification_input(payload)
    rendered = json.dumps(result.to_dict(), sort_keys=True)

    assert "synthetic-secret" not in rendered
    assert "synthetic-token" not in rendered
    assert "Authorization: Bearer" not in rendered
    assert "OPENAI_API_KEY=" not in rendered


def _input_payload() -> dict[str, object]:
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
            "sources": [
                {
                    "source_id": "ctx-001",
                    "context_id": "ctx-001",
                    "document_id": "doc-001",
                    "chunk_id": "chunk-001",
                    "title": "Synthetic IAM Runbook",
                    "source_url": "https://example.invalid/confluence/pages/123",
                    "space_key": "OPS",
                }
            ],
            "used_context_ids": ["ctx-001"],
            "routing": {
                "routing_id": "routing-synthetic",
                "intent": "incident_response",
                "task_prompt_type": "timeline",
            },
            "model": "synthetic-generation-model",
            "confidence": 0.8,
            "warnings": [],
            "custom_answer_field": "preserved",
        },
        "contexts": [
            {
                "context_id": "ctx-001",
                "document_id": "doc-001",
                "chunk_id": "chunk-001",
                "title": "Synthetic IAM Runbook",
                "space_key": "OPS",
                "source_url": "https://example.invalid/confluence/pages/123",
                "content": "Rollback follows the documented runbook.",
                "score": 0.7,
                "rerank_score": 0.9,
                "metadata": {
                    "page_id": "123",
                    "attachment_filename": None,
                    "last_modified_at": "2026-05-18T00:00:00Z",
                },
            }
        ],
        "metadata": {"locale": "ko-KR"},
    }
