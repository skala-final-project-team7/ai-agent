from __future__ import annotations

import json
from pathlib import Path

import pytest

from answer_verification_agent.app import build_app_context
from answer_verification_agent.config import AnswerVerificationConfig
from answer_verification_agent.scripts import run_answer_verification
from answer_verification_agent.schemas import (
    CitationCoverage,
    FailedItem,
    QCAOutput,
    QCAQualityLabel,
    RegenerationRequest,
    SentenceLabel,
    SentenceVerificationResult,
    UIWarning,
    VerificationInput,
    VerificationOutput,
    VerificationOverallLabel,
    VerificationReport,
    VerificationReportStatus,
    WarningItem,
)


def test_config_accepts_external_runtime_values_and_redacts_key() -> None:
    config = AnswerVerificationConfig(
        evaluator_model="synthetic-evaluator-model",
        temperature=0.0,
        timeout_seconds=20,
        max_retries=3,
        evaluate_suspicious_only=True,
        min_overall_score=0.72,
        min_sentence_score=0.61,
        qca_output_enabled=True,
        openai_api_key="synthetic-external-key",
    )

    safe = config.to_safe_dict()

    assert config.evaluator_model == "synthetic-evaluator-model"
    assert config.temperature == 0.0
    assert config.timeout_seconds == 20
    assert config.max_retries == 3
    assert config.evaluate_suspicious_only is True
    assert config.min_overall_score == 0.72
    assert config.min_sentence_score == 0.61
    assert config.qca_output_enabled is True
    assert "synthetic-external-key" not in repr(config)
    assert safe["openai_api_key"] == "<redacted>"
    assert "synthetic-external-key" not in json.dumps(safe)
    assert "Authorization" not in json.dumps(safe)


def test_verification_input_schema_contains_answer_output_and_contexts() -> None:
    verification_input = _verification_input()

    payload = verification_input.to_dict()

    assert payload["conversation_id"] == "conversation-synthetic"
    assert payload["user_id"] == "user-synthetic"
    assert payload["answer_output"]["generation_id"] == "generation-synthetic"
    assert payload["answer_output"]["sentences"][0]["citations"] == ["ctx-001"]
    assert payload["contexts"][0]["context_id"] == "ctx-001"
    assert payload["metadata"] == {"locale": "ko-KR"}


def test_sentence_result_and_label_enums_support_mvp_values() -> None:
    assert SentenceLabel.SUPPORTED.value == "SUPPORTED"
    assert SentenceLabel.UNSUPPORTED.value == "UNSUPPORTED"
    assert SentenceLabel.LOW_CONFIDENCE.value == "LOW_CONFIDENCE"
    assert SentenceLabel.NOT_CHECKED.value == "NOT_CHECKED"
    assert VerificationOverallLabel.PASS.value == "PASS"
    assert VerificationOverallLabel.SUPPORTED.value == "SUPPORTED"
    assert VerificationOverallLabel.UNSUPPORTED.value == "UNSUPPORTED"
    assert VerificationOverallLabel.LOW_CONFIDENCE.value == "LOW_CONFIDENCE"

    result = SentenceVerificationResult(
        sentence_id="s1",
        text="Rollback follows the documented runbook.",
        label=SentenceLabel.SUPPORTED,
        score=0.92,
        citations=["ctx-001"],
        matched_context_ids=["ctx-001"],
        failed_rules=[],
        llm_evaluation_used=False,
        reason="Synthetic context supports the sentence.",
    )

    payload = result.to_dict()

    assert payload["sentence_id"] == "s1"
    assert payload["label"] == "SUPPORTED"
    assert payload["citations"] == ["ctx-001"]
    assert payload["matched_context_ids"] == ["ctx-001"]
    assert payload["llm_evaluation_used"] is False


def test_verification_output_schema_contains_qca_ui_and_regeneration_fields() -> None:
    output = VerificationOutput(
        verification_id="verification-synthetic",
        generation_id="generation-synthetic",
        conversation_id="conversation-synthetic",
        user_id="user-synthetic",
        overall_label=VerificationOverallLabel.SUPPORTED,
        overall_score=0.83,
        sentence_results=[
            SentenceVerificationResult(
                sentence_id="s1",
                text="Rollback follows the documented runbook.",
                label=SentenceLabel.SUPPORTED,
                score=0.92,
                citations=["ctx-001"],
                matched_context_ids=["ctx-001"],
                failed_rules=[],
                llm_evaluation_used=False,
                reason="Synthetic support.",
            )
        ],
        unsupported_claims=[],
        citation_coverage=CitationCoverage(
            total_sentences=1,
            sentences_with_citations=1,
            valid_citations=1,
            invalid_citations=0,
            coverage_ratio=1.0,
        ),
        llm_evaluation_used=False,
        ui_warning_required=False,
        ui_warning=UIWarning(warning_level="none", warning_reasons=[]),
        qca_candidate=False,
        qca_output_ref=None,
        regeneration_recommended=False,
        regeneration_request=None,
        warnings=[],
    )

    payload = output.to_dict()

    assert payload["verification_id"] == "verification-synthetic"
    assert payload["overall_label"] == "SUPPORTED"
    assert payload["citation_coverage"]["coverage_ratio"] == 1.0
    assert payload["ui_warning"] == {
        "warning_level": "none",
        "warning_reasons": [],
    }
    assert payload["qca_candidate"] is False
    assert payload["regeneration_recommended"] is False


def test_qca_regeneration_report_failed_and_warning_shapes() -> None:
    qca = QCAOutput(
        qca_id="qca-synthetic",
        conversation_id="conversation-synthetic",
        generation_id="generation-synthetic",
        verification_id="verification-synthetic",
        question="How should rollback be handled?",
        context_refs=["ctx-001"],
        answer="Rollback follows the documented runbook.",
        overall_label=VerificationOverallLabel.PASS,
        overall_score=0.91,
        quality_label=QCAQualityLabel.ACCEPTED,
        created_at="2026-05-18T00:00:00Z",
    )
    regeneration = RegenerationRequest(
        target_generation_id="generation-synthetic",
        unsupported_sentence_ids=["s2"],
        guidance="Regenerate unsupported sentences using cited context only.",
    )
    report = VerificationReport(
        job_id="job-synthetic",
        verification_id="verification-synthetic",
        generation_id="generation-synthetic",
        conversation_id="conversation-synthetic",
        status=VerificationReportStatus.SUCCESS,
        overall_label=VerificationOverallLabel.PASS,
        sentence_count=1,
        unsupported_count=0,
        low_confidence_count=0,
        llm_evaluation_count=0,
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

    assert qca.to_dict()["quality_label"] == "accepted"
    assert regeneration.to_dict()["unsupported_sentence_ids"] == ["s2"]
    assert report.to_dict()["status"] == "success"
    assert report.to_dict()["overall_label"] == "PASS"
    assert failed.to_dict()["retryable"] is False
    assert warning.to_dict() == {
        "code": "synthetic_warning",
        "message": "Synthetic warning.",
    }


def test_required_values_raise_clear_validation_errors() -> None:
    with pytest.raises(ValueError, match="conversation_id is required"):
        VerificationInput(
            conversation_id="",
            user_id="user-synthetic",
            answer_output=_answer_output(),
            contexts=[],
            metadata={},
        )

    with pytest.raises(ValueError, match="sentence_id is required"):
        SentenceVerificationResult(
            sentence_id="",
            text="text",
            label=SentenceLabel.SUPPORTED,
            score=0.8,
            citations=[],
            matched_context_ids=[],
            failed_rules=[],
            llm_evaluation_used=False,
            reason="reason",
        )

    with pytest.raises(ValueError, match="coverage_ratio must be between 0 and 1"):
        CitationCoverage(
            total_sentences=1,
            sentences_with_citations=1,
            valid_citations=1,
            invalid_citations=0,
            coverage_ratio=1.2,
        )


def test_cli_skeleton_validates_input_without_openai_calls(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "verification_input.json"
    output_path = tmp_path / "verification_output.json"
    input_path.write_text(
        json.dumps(_verification_input().to_dict()),
        encoding="utf-8",
    )

    context = build_app_context(
        input_path=input_path,
        output_path=output_path,
        config=AnswerVerificationConfig(evaluator_model="synthetic-evaluator-model"),
    )

    assert context.input_path == input_path
    assert context.output_path == output_path
    assert context.config.evaluator_model == "synthetic-evaluator-model"

    exit_code = run_answer_verification.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "synthetic-evaluator-model",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "validated" in captured.out
    assert "OPENAI_API_KEY" not in captured.out
    assert "Authorization" not in captured.out
    assert "openai" not in captured.out.lower()


def _verification_input() -> VerificationInput:
    return VerificationInput(
        conversation_id="conversation-synthetic",
        user_id="user-synthetic",
        answer_output=_answer_output(),
        contexts=[_context()],
        metadata={"locale": "ko-KR"},
    )


def _answer_output() -> dict[str, object]:
    return {
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
    }


def _context() -> dict[str, object]:
    return {
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
