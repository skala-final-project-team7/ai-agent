from __future__ import annotations

import json
from pathlib import Path

import pytest

from answer_generation_agent.generation.input_normalization import (
    GenerationInputLoadError,
    GenerationInputNormalizationError,
    load_generation_input_json,
    normalize_generation_input,
)
from answer_generation_agent.schemas import TaskPromptType


def test_loads_valid_generation_input_json() -> None:
    payload = _valid_payload(top_contexts=[_context("ctx-001", rerank_score=0.9)])

    result = normalize_generation_input(payload)

    assert result.generation_input.conversation_id == "conversation-synthetic"
    assert result.generation_input.user_id == "user-synthetic"
    assert result.generation_input.routing_decision.routing_id == "routing-synthetic"
    assert result.generation_input.routing_decision.query == "IAM rollback procedure"
    assert result.used_context_count == 1
    assert result.insufficient_context_candidate is False


def test_file_loader_rejects_malformed_json(tmp_path: Path) -> None:
    input_path = tmp_path / "generation_input.json"
    input_path.write_text("{invalid-json", encoding="utf-8")

    with pytest.raises(GenerationInputLoadError, match="malformed JSON"):
        load_generation_input_json(input_path)


@pytest.mark.parametrize(
    ("mutation", "expected_message"),
    [
        (lambda payload: payload.pop("routing_decision"), "routing_decision is required"),
        (
            lambda payload: payload["routing_decision"].pop("query"),
            "query is required",
        ),
        (lambda payload: payload.pop("search_results"), "search_results is required"),
    ],
)
def test_required_generation_input_fields_raise_clear_errors(
    mutation: object,
    expected_message: str,
) -> None:
    payload = _valid_payload(top_contexts=[_context("ctx-001")])
    mutation(payload)

    with pytest.raises(GenerationInputNormalizationError, match=expected_message):
        normalize_generation_input(payload)


def test_supported_task_prompt_type_is_preserved() -> None:
    payload = _valid_payload(top_contexts=[_context("ctx-001")])
    payload["routing_decision"]["task_prompt_type"] = "evidence_first"

    result = normalize_generation_input(payload)

    assert result.generation_input.routing_decision.task_prompt_type == (
        TaskPromptType.EVIDENCE_FIRST
    )
    assert result.warnings == []


def test_unsupported_task_prompt_type_falls_back_to_general_with_warning() -> None:
    payload = _valid_payload(top_contexts=[_context("ctx-001")])
    payload["routing_decision"]["task_prompt_type"] = "future_prompt"

    result = normalize_generation_input(payload)

    assert result.generation_input.routing_decision.task_prompt_type == (
        TaskPromptType.GENERAL
    )
    assert any(
        warning.code == "unsupported_task_prompt_type"
        for warning in result.warnings
    )


def test_top_contexts_are_limited_to_top_five_by_rerank_score() -> None:
    contexts = [
        _context(f"ctx-{index}", rerank_score=score)
        for index, score in enumerate([0.2, 0.95, 0.4, 0.7, 0.6, 0.8], start=1)
    ]
    payload = _valid_payload(top_contexts=contexts)

    result = normalize_generation_input(payload, max_contexts=5)

    assert [context.context_id for context in result.normalized_contexts] == [
        "ctx-2",
        "ctx-6",
        "ctx-4",
        "ctx-5",
        "ctx-3",
    ]
    assert result.input_context_count == 6
    assert result.used_context_count == 5


def test_score_sorting_is_used_when_rerank_score_is_missing() -> None:
    payload = _valid_payload(
        top_contexts=[
            _context("ctx-low", score=0.2, include_rerank=False),
            _context("ctx-high", score=0.9, include_rerank=False),
            _context("ctx-mid", score=0.5, include_rerank=False),
        ]
    )

    result = normalize_generation_input(payload)

    assert [context.context_id for context in result.normalized_contexts] == [
        "ctx-high",
        "ctx-mid",
        "ctx-low",
    ]


def test_empty_content_context_is_excluded_with_warning() -> None:
    payload = _valid_payload(
        top_contexts=[
            _context("ctx-empty", content="   ", rerank_score=1.0),
            _context("ctx-usable", content="Usable synthetic context.", rerank_score=0.8),
        ]
    )

    result = normalize_generation_input(payload)

    assert [context.context_id for context in result.normalized_contexts] == [
        "ctx-usable"
    ]
    assert any(warning.code == "empty_context_content" for warning in result.warnings)


def test_duplicate_context_id_is_handled_deterministically() -> None:
    payload = _valid_payload(
        top_contexts=[
            _context("ctx-duplicate", content="Lower ranked content.", rerank_score=0.2),
            _context("ctx-duplicate", content="Higher ranked content.", rerank_score=0.9),
            _context("ctx-other", content="Other content.", rerank_score=0.8),
        ]
    )

    result = normalize_generation_input(payload)

    assert [context.context_id for context in result.normalized_contexts] == [
        "ctx-duplicate",
        "ctx-other",
    ]
    assert result.normalized_contexts[0].content == "Higher ranked content."
    assert any(warning.code == "duplicate_context_id" for warning in result.warnings)


def test_empty_top_contexts_keeps_insufficient_context_candidate() -> None:
    payload = _valid_payload(top_contexts=[])

    result = normalize_generation_input(payload)

    assert result.normalized_contexts == []
    assert result.used_context_count == 0
    assert result.insufficient_context_candidate is True


def test_source_metadata_is_preserved_for_canonical_source_creation() -> None:
    payload = _valid_payload(
        top_contexts=[
            _context(
                "ctx-001",
                metadata={
                    "page_id": "page-synthetic",
                    "attachment_filename": None,
                    "last_modified_at": "2026-05-18T00:00:00Z",
                },
            )
        ]
    )

    result = normalize_generation_input(payload)

    assert result.normalized_contexts[0].metadata == {
        "page_id": "page-synthetic",
        "attachment_filename": None,
        "last_modified_at": "2026-05-18T00:00:00Z",
    }


def test_warning_error_and_result_strings_do_not_expose_sensitive_markers() -> None:
    payload = _valid_payload(top_contexts=[_context("ctx-001")])
    payload["metadata"] = {
        "OPENAI_API_KEY": "synthetic-marker",
        "Authorization": "synthetic-marker",
        "safe_value": "kept",
    }
    payload["routing_decision"]["task_prompt_type"] = "future_prompt"

    result = normalize_generation_input(payload)
    serialized = json.dumps(result.to_dict())

    assert "synthetic-marker" not in serialized
    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "secret" not in serialized.lower()


def _valid_payload(top_contexts: list[dict[str, object]]) -> dict[str, object]:
    return {
        "conversation_id": "conversation-synthetic",
        "user_id": "user-synthetic",
        "routing_decision": {
            "routing_id": "routing-synthetic",
            "original_question": "Rollback?",
            "query": "IAM rollback procedure",
            "intent": "incident_response",
            "task_prompt_type": "timeline",
            "expanded_queries": ["IAM rollback"],
            "metadata_filters": {"space_keys": ["OPS"]},
            "pool_weights": {"content": 1.0},
            "confidence": 0.8,
            "warnings": [],
        },
        "search_results": {"top_contexts": top_contexts},
        "metadata": {"locale": "ko-KR"},
    }


def _context(
    context_id: str,
    *,
    content: str = "Synthetic context content.",
    score: float = 0.5,
    rerank_score: float = 0.5,
    include_rerank: bool = True,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "context_id": context_id,
        "document_id": f"doc-{context_id}",
        "chunk_id": f"chunk-{context_id}",
        "title": f"Title {context_id}",
        "space_key": "OPS",
        "source_url": f"https://example.invalid/{context_id}",
        "content": content,
        "score": score,
        "metadata": metadata or {"page_id": f"page-{context_id}"},
    }
    if include_rerank:
        payload["rerank_score"] = rerank_score
    return payload
