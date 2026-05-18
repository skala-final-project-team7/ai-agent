from __future__ import annotations

import json

from answer_verification_agent.schemas import SentenceLabel
from answer_verification_agent.verification.input_normalization import (
    normalize_verification_input,
)
from answer_verification_agent.verification.rule_based_verifier import (
    RuleVerifierConfig,
    run_rule_based_verification,
)
from answer_verification_agent.verification.sentence_parser import (
    parse_sentences_and_citations,
)


def test_supported_sentence_passes_citation_context_and_overlap_rules() -> None:
    result = _verify(_payload())
    sentence = result.sentence_results[0]

    assert sentence.sentence_id == "s1"
    assert sentence.preliminary_label == SentenceLabel.SUPPORTED
    assert sentence.score >= 0.8
    assert sentence.failed_rules == []
    assert "citation_exists" in sentence.passed_rules
    assert "valid_context_citation" in sentence.passed_rules
    assert "token_overlap" in sentence.passed_rules


def test_missing_citation_fails_citation_existence_rule() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0]["citations"] = []

    result = _verify(payload)
    sentence = result.sentence_results[0]

    assert "citation_exists" in sentence.failed_rules
    assert sentence.preliminary_label in {
        SentenceLabel.LOW_CONFIDENCE,
        SentenceLabel.UNSUPPORTED,
    }


def test_invalid_context_id_fails_valid_context_rule() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0]["citations"] = ["ctx-missing"]

    result = _verify(payload)
    sentence = result.sentence_results[0]

    assert "valid_context_citation" in sentence.failed_rules
    assert sentence.preliminary_label == SentenceLabel.UNSUPPORTED


def test_numeric_date_version_percent_mismatch_fails_presence_rule() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "Runbook version v2.4.1 completed on 2026-05-18 with 99% success."
    payload["contexts"][0][
        "content"
    ] = "Runbook version v2.4.0 completed on 2026-05-17 with 90% success."

    result = _verify(payload)
    sentence = result.sentence_results[0]

    assert "number_date_version_presence" in sentence.failed_rules
    assert sentence.preliminary_label in {
        SentenceLabel.LOW_CONFIDENCE,
        SentenceLabel.UNSUPPORTED,
    }


def test_low_token_overlap_marks_low_confidence_or_unsupported() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "Restart the database service immediately."

    result = _verify(payload)
    sentence = result.sentence_results[0]

    assert "token_overlap" in sentence.failed_rules
    assert sentence.preliminary_label in {
        SentenceLabel.LOW_CONFIDENCE,
        SentenceLabel.UNSUPPORTED,
    }


def test_low_source_coverage_adds_warning() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"].append(
        {"sentence_id": "s2", "text": "Uncited operational claim.", "citations": []}
    )

    result = _verify(payload, source_coverage_threshold=0.8)

    assert "source_coverage" in result.failed_rules
    assert any(warning.code == "source_coverage_low" for warning in result.warnings)


def test_rule_threshold_can_be_adjusted() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "Rollback runbook unrelated alpha beta."

    strict = _verify(payload, min_token_overlap=0.95)
    relaxed = _verify(payload, min_token_overlap=0.2)

    assert "token_overlap" in strict.sentence_results[0].failed_rules
    assert "token_overlap" not in relaxed.sentence_results[0].failed_rules


def test_rule_result_redacts_sensitive_values() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "OPENAI_API_KEY=synthetic-secret Authorization: Bearer synthetic-token"

    result = _verify(payload)
    rendered = json.dumps(result.to_dict(), sort_keys=True)

    assert "synthetic-secret" not in rendered
    assert "synthetic-token" not in rendered
    assert "Authorization: Bearer" not in rendered
    assert "OPENAI_API_KEY=" not in rendered


def _verify(
    payload: dict[str, object],
    *,
    min_token_overlap: float = 0.5,
    source_coverage_threshold: float = 0.6,
):
    normalized = normalize_verification_input(payload)
    parsed = parse_sentences_and_citations(normalized)
    return run_rule_based_verification(
        parsed,
        normalized.contexts,
        config=RuleVerifierConfig(
            min_token_overlap=min_token_overlap,
            source_coverage_threshold=source_coverage_threshold,
        ),
    )


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
        "metadata": {"locale": "ko-KR"},
    }
