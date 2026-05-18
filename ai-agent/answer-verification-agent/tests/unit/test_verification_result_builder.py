from __future__ import annotations

import json
from pathlib import Path

from answer_verification_agent.evaluator import SentenceEvaluation
from answer_verification_agent.schemas import (
    QCAQualityLabel,
    SentenceLabel,
    VerificationOverallLabel,
    VerificationReportStatus,
)
from answer_verification_agent.verification.input_normalization import (
    normalize_verification_input,
)
from answer_verification_agent.verification.result_builder import (
    build_failed_item,
    build_verification_result,
)
from answer_verification_agent.verification.rule_based_verifier import (
    RuleVerifierConfig,
    run_rule_based_verification,
)
from answer_verification_agent.verification.sentence_parser import (
    parse_sentences_and_citations,
)
from answer_verification_agent.storage import write_verification_artifacts


def test_all_supported_sentences_create_pass_output() -> None:
    result = _build(_payload())

    assert result.output.overall_label == VerificationOverallLabel.PASS
    assert result.output.overall_score >= 0.9
    assert result.output.sentence_results[0].label == SentenceLabel.SUPPORTED
    assert result.output.ui_warning_required is False
    assert result.output.regeneration_recommended is False
    assert result.qca_output.quality_label == QCAQualityLabel.ACCEPTED


def test_minor_warning_supported_output() -> None:
    payload = _payload()
    payload["answer_output"]["warnings"] = [
        {"code": "generation_minor_warning", "message": "synthetic warning"}
    ]

    result = _build(payload)

    assert result.output.overall_label == VerificationOverallLabel.SUPPORTED
    assert result.output.ui_warning.warning_level == "low"


def test_unsupported_sentence_creates_claims_and_regeneration_request() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0]["text"] = "Restart database immediately."
    evaluator_results = {
        "s1": SentenceEvaluation(
            sentence_id="s1",
            label=SentenceLabel.UNSUPPORTED,
            score=0.2,
            reason="The cited context does not support the claim.",
            unsupported_claims=["Restart database immediately."],
        )
    }

    result = _build(payload, evaluator_results=evaluator_results)

    assert result.output.overall_label == VerificationOverallLabel.UNSUPPORTED
    assert result.output.unsupported_claims[0]["sentence_id"] == "s1"
    assert result.output.regeneration_recommended is True
    assert result.output.regeneration_request is not None
    assert result.output.regeneration_request.unsupported_sentence_ids == ["s1"]
    assert "unsupported" in result.output.regeneration_request.guidance
    assert result.qca_output.quality_label == QCAQualityLabel.REJECTED


def test_evaluator_low_confidence_creates_low_confidence_warning() -> None:
    evaluator_results = {
        "s1": SentenceEvaluation(
            sentence_id="s1",
            label=SentenceLabel.LOW_CONFIDENCE,
            score=0.35,
            reason="Evaluator could not verify the sentence.",
        )
    }

    result = _build(_payload(), evaluator_results=evaluator_results)

    assert result.output.overall_label == VerificationOverallLabel.LOW_CONFIDENCE
    assert result.output.ui_warning_required is True
    assert result.output.ui_warning.warning_level == "medium"
    assert result.qca_output.quality_label == QCAQualityLabel.NEEDS_REVIEW


def test_sentence_result_merges_rule_and_llm_result_without_ignoring_numeric_mismatch() -> None:
    payload = _payload()
    payload["answer_output"]["sentences"][0][
        "text"
    ] = "Rollback version v2.4.1 finished on 2026-05-18 with 99% success."
    payload["contexts"][0][
        "content"
    ] = "Rollback version v2.4.0 finished on 2026-05-17 with 90% success."
    evaluator_results = {
        "s1": SentenceEvaluation(
            sentence_id="s1",
            label=SentenceLabel.SUPPORTED,
            score=0.95,
            reason="Evaluator says supported.",
        )
    }

    result = _build(payload, evaluator_results=evaluator_results)
    sentence = result.output.sentence_results[0]

    assert sentence.llm_evaluation_used is True
    assert sentence.label == SentenceLabel.UNSUPPORTED
    assert "number_date_version_presence" in sentence.failed_rules


def test_report_contains_status_counts_and_label() -> None:
    result = _build(_payload())

    assert result.report.status == VerificationReportStatus.SUCCESS
    assert result.report.overall_label == VerificationOverallLabel.PASS
    assert result.report.sentence_count == 1
    assert result.report.llm_evaluation_count == 0
    assert result.report.warnings_count == 0


def test_qca_json_and_jsonl_writer_creates_files(tmp_path: Path) -> None:
    result = _build(_payload())

    paths = write_verification_artifacts(result, tmp_path)

    assert paths["output"].exists()
    assert paths["report"].exists()
    assert paths["qca_json"].exists()
    assert paths["qca_jsonl"].exists()
    assert paths["failed"].exists()
    qca_json = json.loads(paths["qca_json"].read_text(encoding="utf-8"))
    qca_jsonl = paths["qca_jsonl"].read_text(encoding="utf-8").strip()
    assert qca_json["verification_id"] == result.output.verification_id
    assert json.loads(qca_jsonl)["qca_id"] == result.qca_output.qca_id


def test_writer_redacts_sensitive_values(tmp_path: Path) -> None:
    payload = _payload()
    payload["answer_output"]["answer"] = (
        "OPENAI_API_KEY=synthetic-secret Authorization: Bearer synthetic-token"
    )
    payload["answer_output"]["sentences"][0]["text"] = payload["answer_output"]["answer"]
    result = _build(payload)

    paths = write_verification_artifacts(result, tmp_path)
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in paths.values())

    assert "synthetic-secret" not in rendered
    assert "synthetic-token" not in rendered
    assert "Authorization: Bearer" not in rendered
    assert "OPENAI_API_KEY=" not in rendered


def test_failed_item_helper_redacts_sensitive_error() -> None:
    failed = build_failed_item(
        item_id="s1",
        reason="OPENAI_API_KEY=synthetic-secret Authorization: Bearer synthetic-token",
        error_type="synthetic_error",
        retryable=False,
    )
    rendered = json.dumps(failed.to_dict(), sort_keys=True)

    assert "synthetic-secret" not in rendered
    assert "synthetic-token" not in rendered


def _build(
    payload: dict[str, object],
    *,
    evaluator_results: dict[str, SentenceEvaluation] | None = None,
):
    normalized = normalize_verification_input(payload)
    parsed = parse_sentences_and_citations(normalized)
    rules = run_rule_based_verification(
        parsed,
        normalized.contexts,
        config=RuleVerifierConfig(source_coverage_threshold=0.0),
    )
    return build_verification_result(
        normalized_input=normalized,
        parsed=parsed,
        rule_result=rules,
        evaluator_results=evaluator_results or {},
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
        "metadata": {
            "query": "How should rollback be handled?",
            "locale": "ko-KR",
        },
    }
