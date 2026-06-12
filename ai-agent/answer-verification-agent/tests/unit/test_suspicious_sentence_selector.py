"""ai-agent/answer-verification-agent/tests/unit/test_suspicious_sentence_selector.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import json

from answer_verification_agent.verification.input_normalization import (
    normalize_verification_input,
)
from answer_verification_agent.verification.rule_based_verifier import (
    RuleVerificationResult,
    RuleVerifierConfig,
    run_rule_based_verification,
)
from answer_verification_agent.verification.sentence_parser import (
    parse_sentences_and_citations,
)
from answer_verification_agent.verification.suspicious_selector import (
    SuspiciousSelectorConfig,
    select_suspicious_sentences,
)


def test_supported_sentence_is_not_selected_in_suspicious_only_mode() -> None:
    normalized, rules = _run_rules(_payload())

    result = select_suspicious_sentences(rules, normalized)

    assert result.evaluation_targets == []
    assert result.suspicious_sentence_ids == []


def test_missing_citation_sentence_is_selected() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0]["citations"] = []
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(rules, normalized)

    assert result.evaluation_targets[0].sentence_id == "s1"
    assert "citation_missing" in result.evaluation_targets[0].reasons


def test_invalid_citation_sentence_is_selected() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0]["citations"] = ["ctx-missing"]
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(rules, normalized)

    assert result.evaluation_targets[0].sentence_id == "s1"
    assert "invalid_citation" in result.evaluation_targets[0].reasons


def test_low_overlap_sentence_is_selected() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0]["text"] = "Restart database now."
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(rules, normalized)

    assert result.evaluation_targets[0].sentence_id == "s1"
    assert "low_token_overlap" in result.evaluation_targets[0].reasons


def test_number_date_version_mismatch_sentence_is_selected() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "Rollback version v2.4.1 finished on 2026-05-18 with 99% success."
    payload["contexts"][0][
        "content"
    ] = "Rollback version v2.4.0 finished on 2026-05-17 with 90% success."
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(rules, normalized)

    assert result.evaluation_targets[0].sentence_id == "s1"
    assert "number_date_version_mismatch" in result.evaluation_targets[0].reasons


def test_insufficient_context_answer_status_selects_sentence() -> None:
    payload = _payload()
    payload["answer_output"]["answer_status"] = "insufficient_context"
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(rules, normalized)

    assert result.evaluation_targets[0].sentence_id == "s1"
    assert "insufficient_context" in result.evaluation_targets[0].reasons


def test_score_below_threshold_selects_sentence() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0]["citations"] = []
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(
        rules,
        normalized,
        config=SuspiciousSelectorConfig(score_threshold=0.99),
    )

    assert result.evaluation_targets[0].sentence_id == "s1"
    assert "score_below_threshold" in result.evaluation_targets[0].reasons


def test_reasons_are_unique_and_stable_order() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "Rollback version v2.4.1 finished on 2026-05-18 with 99% success."
    payload["answer_output"]["sentences"][0]["citations"] = ["ctx-missing"]
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(rules, normalized)

    assert result.evaluation_targets[0].reasons == [
        "invalid_citation",
        "low_token_overlap",
        "number_date_version_mismatch",
        "score_below_threshold",
    ]


def test_suspicious_only_mode_returns_only_suspicious_sentences() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"].append(
        {"sentence_id": "s2", "text": "Uncited claim.", "citations": []}
    )
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(
        rules,
        normalized,
        config=SuspiciousSelectorConfig(evaluate_suspicious_only=True),
    )

    assert [target.sentence_id for target in result.evaluation_targets] == ["s2"]


def test_all_sentence_mode_returns_every_sentence() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"].append(
        {"sentence_id": "s2", "text": "Uncited claim.", "citations": []}
    )
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(
        rules,
        normalized,
        config=SuspiciousSelectorConfig(evaluate_suspicious_only=False),
    )

    assert [target.sentence_id for target in result.evaluation_targets] == ["s1", "s2"]
    assert result.evaluation_targets[0].reasons == ["all_sentence_evaluation"]


def test_selector_result_redacts_sensitive_values() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "OPENAI_API_KEY=synthetic-secret Authorization: Bearer synthetic-token"
    normalized, rules = _run_rules(payload)

    result = select_suspicious_sentences(rules, normalized)
    rendered = json.dumps(result.to_dict(), sort_keys=True)

    assert "synthetic-secret" not in rendered
    assert "synthetic-token" not in rendered
    assert "Authorization: Bearer" not in rendered
    assert "OPENAI_API_KEY=" not in rendered


def _run_rules(payload: dict[str, object]):
    normalized = normalize_verification_input(payload)
    parsed = parse_sentences_and_citations(normalized)
    rules: RuleVerificationResult = run_rule_based_verification(
        parsed,
        normalized.contexts,
        config=RuleVerifierConfig(source_coverage_threshold=0.0),
    )
    return normalized, rules


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
