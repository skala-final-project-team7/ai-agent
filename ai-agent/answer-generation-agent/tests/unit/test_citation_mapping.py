"""ai-agent/answer-generation-agent/tests/unit/test_citation_mapping.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import json

from answer_generation_agent.generation.answer_generation import (
    AnswerGenerationResult,
    RawSentenceCandidate,
)
from answer_generation_agent.generation.citation_mapping import map_citations
from answer_generation_agent.generation.input_normalization import normalize_generation_input
from answer_generation_agent.generation.prompt_template import build_prompt_payload


def test_raw_answer_is_split_into_multiple_sentences() -> None:
    result = map_citations(
        generation_result=_generation_result(
            answer_text="First synthetic answer. Second synthetic answer."
        ),
        normalized_input=_normalized_result(contexts=[_context("ctx-001")]),
    )

    assert [sentence.text for sentence in result.sentences] == [
        "First synthetic answer.",
        "Second synthetic answer.",
    ]


def test_sentence_ids_are_deterministic() -> None:
    result = map_citations(
        generation_result=_generation_result(
            answer_text="First synthetic answer. Second synthetic answer."
        ),
        normalized_input=_normalized_result(contexts=[_context("ctx-001")]),
    )

    assert [sentence.sentence_id for sentence in result.sentences] == ["s1", "s2"]


def test_valid_raw_citation_candidates_are_preserved() -> None:
    result = map_citations(
        generation_result=_generation_result(
            answer_text="First synthetic answer.",
            candidates=[
                RawSentenceCandidate(
                    text="First synthetic answer.",
                    citations=["ctx-001"],
                )
            ],
        ),
        normalized_input=_normalized_result(contexts=[_context("ctx-001")]),
    )

    assert result.sentences[0].citations == ["ctx-001"]
    assert result.warnings == []


def test_invalid_context_id_citation_is_removed_with_warning() -> None:
    result = map_citations(
        generation_result=_generation_result(
            answer_text="First synthetic answer.",
            candidates=[
                RawSentenceCandidate(
                    text="First synthetic answer.",
                    citations=["ctx-missing", "ctx-001"],
                )
            ],
        ),
        normalized_input=_normalized_result(contexts=[_context("ctx-001")]),
    )

    assert result.sentences[0].citations == ["ctx-001"]
    assert any(warning.code == "invalid_citation_removed" for warning in result.warnings)


def test_single_context_fallback_citation_is_applied_when_candidate_is_missing() -> None:
    result = map_citations(
        generation_result=_generation_result(answer_text="Only supported sentence."),
        normalized_input=_normalized_result(contexts=[_context("ctx-001")]),
    )

    assert result.sentences[0].citations == ["ctx-001"]
    assert any(warning.code == "fallback_citation_applied" for warning in result.warnings)


def test_multiple_contexts_without_candidate_keep_missing_citation_warning() -> None:
    result = map_citations(
        generation_result=_generation_result(answer_text="Ambiguous supported sentence."),
        normalized_input=_normalized_result(
            contexts=[_context("ctx-001"), _context("ctx-002")]
        ),
    )

    assert result.sentences[0].citations == []
    assert any(warning.code == "missing_citation" for warning in result.warnings)


def test_source_list_is_created_from_context_metadata() -> None:
    result = map_citations(
        generation_result=_generation_result(
            answer_text="First synthetic answer.",
            candidates=[RawSentenceCandidate(text="First synthetic answer.", citations=["ctx-001"])],
        ),
        normalized_input=_normalized_result(
            contexts=[
                _context(
                    "ctx-001",
                    metadata={
                        "page_id": "page-synthetic",
                        "attachment_filename": "synthetic-runbook.pdf",
                    },
                )
            ]
        ),
    )

    source = result.sources[0]

    assert source.context_id == "ctx-001"
    assert source.document_id == "doc-ctx-001"
    assert source.chunk_id == "chunk-ctx-001"
    assert source.title == "Synthetic Runbook"
    assert source.source_url == "https://example.invalid/pages/ctx-001"
    assert source.space_key == "OPS"
    assert source.page_id == "page-synthetic"
    assert source.attachment_filename == "synthetic-runbook.pdf"
    assert source.score == 0.7
    assert source.rerank_score == 0.9


def test_duplicate_citations_and_sources_are_removed() -> None:
    result = map_citations(
        generation_result=_generation_result(
            answer_text="First synthetic answer. Second synthetic answer.",
            candidates=[
                RawSentenceCandidate(
                    text="First synthetic answer.",
                    citations=["ctx-001", "ctx-001"],
                ),
                RawSentenceCandidate(
                    text="Second synthetic answer.",
                    citations=["ctx-001"],
                ),
            ],
        ),
        normalized_input=_normalized_result(contexts=[_context("ctx-001")]),
    )

    assert result.sentences[0].citations == ["ctx-001"]
    assert result.used_context_ids == ["ctx-001"]
    assert [source.context_id for source in result.sources] == ["ctx-001"]


def test_used_context_ids_are_calculated_from_sentence_citations() -> None:
    result = map_citations(
        generation_result=_generation_result(
            answer_text="First synthetic answer. Second synthetic answer.",
            candidates=[
                RawSentenceCandidate(text="First synthetic answer.", citations=["ctx-002"]),
                RawSentenceCandidate(text="Second synthetic answer.", citations=["ctx-001"]),
            ],
        ),
        normalized_input=_normalized_result(
            contexts=[_context("ctx-001"), _context("ctx-002")]
        ),
    )

    assert result.used_context_ids == ["ctx-002", "ctx-001"]


def test_empty_or_whitespace_answer_is_handled_safely() -> None:
    result = map_citations(
        generation_result=_generation_result(answer_text="   "),
        normalized_input=_normalized_result(contexts=[_context("ctx-001")]),
    )

    assert result.sentences == []
    assert result.sources == []
    assert result.used_context_ids == []
    assert any(warning.code == "empty_answer" for warning in result.warnings)


def test_result_warning_and_error_strings_do_not_expose_sensitive_markers() -> None:
    result = map_citations(
        generation_result=_generation_result(
            answer_text="OPENAI_API_KEY Authorization API key secret synthetic-marker.",
            candidates=[
                RawSentenceCandidate(
                    text="OPENAI_API_KEY Authorization API key secret synthetic-marker.",
                    citations=["ctx-001", "missing-secret"],
                )
            ],
        ),
        normalized_input=_normalized_result(contexts=[_context("ctx-001")]),
    )

    serialized = json.dumps(result.to_dict())

    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "API key" not in serialized
    assert "synthetic-marker" not in serialized
    assert "secret" not in serialized.lower()


def test_sentence_text_and_citations_are_separate_for_verification() -> None:
    result = map_citations(
        generation_result=_generation_result(
            answer_text="First synthetic answer.",
            candidates=[RawSentenceCandidate(text="First synthetic answer.", citations=["ctx-001"])],
        ),
        normalized_input=_normalized_result(contexts=[_context("ctx-001")]),
    )

    payload = result.sentences[0].to_dict()

    assert payload["text"] == "First synthetic answer."
    assert payload["citations"] == ["ctx-001"]
    assert "ctx-001" not in payload["text"]


def _generation_result(
    *,
    answer_text: str,
    candidates: list[RawSentenceCandidate] | None = None,
) -> AnswerGenerationResult:
    return AnswerGenerationResult(
        answer_status="success",
        answer_text=answer_text,
        model="synthetic-model",
        provider_name="fake",
        prompt=build_prompt_payload(_normalized_result(contexts=[_context("ctx-001")])),
        raw_sentence_candidates=candidates or [],
        unsupported_gaps=[],
        warnings=[],
    )


def _normalized_result(*, contexts: list[dict[str, object]]):
    return normalize_generation_input(
        {
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
            "search_results": {"top_contexts": contexts},
            "metadata": {"locale": "ko-KR"},
        }
    )


def _context(
    context_id: str,
    *,
    content: str = "Synthetic rollback context.",
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "context_id": context_id,
        "document_id": f"doc-{context_id}",
        "chunk_id": f"chunk-{context_id}",
        "title": "Synthetic Runbook",
        "space_key": "OPS",
        "source_url": f"https://example.invalid/pages/{context_id}",
        "content": content,
        "score": 0.7,
        "rerank_score": 0.9,
        "metadata": metadata or {"page_id": f"page-{context_id}"},
    }
