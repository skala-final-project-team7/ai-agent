"""ai-agent/answer-verification-agent/tests/unit/test_sentence_citation_parser.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import json

from answer_verification_agent.verification.input_normalization import (
    normalize_verification_input,
)
from answer_verification_agent.verification.sentence_parser import (
    parse_sentences_and_citations,
)


def test_generated_sentences_are_converted_to_verification_sentences() -> None:
    normalized = normalize_verification_input(_input_payload())

    result = parse_sentences_and_citations(normalized)

    assert len(result.sentences) == 2
    assert result.sentences[0].sentence_id == "provided-s1"
    assert result.sentences[0].text == "Rollback follows the documented runbook."
    assert result.sentences[0].citations == ["ctx-001"]
    assert result.sentences[0].matched_context_ids == ["ctx-001"]
    assert result.sentences[0].invalid_citations == []


def test_missing_sentence_id_and_text_are_normalized() -> None:
    payload = _input_payload()
    payload["answer_output"]["sentences"] = [
        {
            "text": "  Rollback follows the documented runbook.  ",
            "citations": ["ctx-001"],
        }
    ]

    result = parse_sentences_and_citations(normalize_verification_input(payload))

    assert result.sentences[0].sentence_id == "s1"
    assert result.sentences[0].text == "Rollback follows the documented runbook."


def test_citations_are_extracted_and_deduplicated() -> None:
    payload = _input_payload()
    payload["answer_output"]["sentences"][0]["citations"] = [
        "ctx-001",
        "ctx-001",
        "ctx-002",
        "",
    ]

    result = parse_sentences_and_citations(normalize_verification_input(payload))

    assert result.sentences[0].citations == ["ctx-001", "ctx-002"]
    assert result.sentences[0].matched_context_ids == ["ctx-001", "ctx-002"]


def test_invalid_context_id_citation_is_marked() -> None:
    payload = _input_payload()
    payload["answer_output"]["sentences"][0]["citations"] = ["ctx-001", "ctx-missing"]

    result = parse_sentences_and_citations(normalize_verification_input(payload))

    assert result.sentences[0].citations == ["ctx-001", "ctx-missing"]
    assert result.sentences[0].matched_context_ids == ["ctx-001"]
    assert result.sentences[0].invalid_citations == ["ctx-missing"]
    assert any(warning.code == "invalid_citation" for warning in result.warnings)


def test_fallback_parses_korean_and_english_answer_sentences() -> None:
    payload = _input_payload()
    payload["answer_output"]["sentences"] = []
    payload["answer_output"][
        "answer"
    ] = "첫 번째 조치를 확인합니다. Then verify rollback status! 추가 점검이 필요합니다?"

    result = parse_sentences_and_citations(normalize_verification_input(payload))

    assert [sentence.text for sentence in result.sentences] == [
        "첫 번째 조치를 확인합니다.",
        "Then verify rollback status!",
        "추가 점검이 필요합니다?",
    ]
    assert [sentence.sentence_id for sentence in result.sentences] == ["s1", "s2", "s3"]
    assert all(sentence.citations == [] for sentence in result.sentences)
    assert any(warning.code == "fallback_sentence_parsing_used" for warning in result.warnings)


def test_empty_answer_creates_safe_warning() -> None:
    payload = _input_payload()
    payload["answer_output"]["sentences"] = []
    payload["answer_output"]["answer"] = "   "

    result = parse_sentences_and_citations(normalize_verification_input(payload))

    assert result.sentences == []
    assert result.citation_coverage.total_sentences == 0
    assert any(warning.code == "sentence_parse_empty" for warning in result.warnings)


def test_citation_coverage_counts_total_valid_invalid_and_ratio() -> None:
    payload = _input_payload()
    payload["answer_output"]["sentences"] = [
        {"sentence_id": "s1", "text": "One.", "citations": ["ctx-001", "ctx-missing"]},
        {"sentence_id": "s2", "text": "Two.", "citations": []},
        {"sentence_id": "s3", "text": "Three.", "citations": ["ctx-002"]},
    ]

    result = parse_sentences_and_citations(normalize_verification_input(payload))
    coverage = result.citation_coverage

    assert coverage.total_sentences == 3
    assert coverage.sentences_with_citations == 2
    assert coverage.valid_citations == 2
    assert coverage.invalid_citations == 1
    assert coverage.coverage_ratio == 2 / 3


def test_parser_result_redacts_sensitive_values() -> None:
    payload = _input_payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "OPENAI_API_KEY=synthetic-secret Authorization: Bearer synthetic-token"
    payload["answer_output"]["sentences"][0]["citations"] = ["ctx-001"]

    result = parse_sentences_and_citations(normalize_verification_input(payload))
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
                    "sentence_id": "provided-s1",
                    "text": "Rollback follows the documented runbook.",
                    "citations": ["ctx-001"],
                    "citation_required": True,
                },
                {
                    "sentence_id": "provided-s2",
                    "text": "The runbook has a verification step.",
                    "citations": ["ctx-002"],
                    "citation_required": True,
                },
            ],
            "sources": [],
            "used_context_ids": ["ctx-001", "ctx-002"],
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
                "content": "Rollback follows the documented runbook.",
                "score": 0.7,
                "rerank_score": 0.9,
                "metadata": {"page_id": "123"},
            },
            {
                "context_id": "ctx-002",
                "document_id": "doc-002",
                "chunk_id": "chunk-002",
                "title": "Synthetic Verification Step",
                "space_key": "OPS",
                "source_url": "https://example.invalid/confluence/pages/456",
                "content": "The runbook has a verification step.",
                "score": 0.6,
                "rerank_score": 0.8,
                "metadata": {"page_id": "456"},
            },
        ],
        "metadata": {"locale": "ko-KR"},
    }
