from __future__ import annotations

import json
from pathlib import Path

from answer_verification_agent.evaluator import EvaluatorProviderError
from answer_verification_agent.workflow import run_verification_workflow

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "answer_verification"


def test_supported_fixture_full_workflow(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "supported")

    run_verification_workflow(
        input_path=FIXTURE_DIR / "supported.json",
        **paths,
    )

    output = _read(paths["output_path"])
    report = _read(paths["report_output_path"])
    qca = _read(paths["qca_output_path"])
    assert output["overall_label"] in {"PASS", "SUPPORTED"}
    assert output["sentence_results"][0]["label"] == "SUPPORTED"
    assert report["status"] == "success"
    assert qca["quality_label"] == "accepted"


def test_unsupported_fixture_creates_warning_and_regeneration(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "unsupported")

    run_verification_workflow(
        input_path=FIXTURE_DIR / "unsupported.json",
        **paths,
    )

    output = _read(paths["output_path"])
    assert output["overall_label"] in {"UNSUPPORTED", "LOW_CONFIDENCE"}
    assert output["ui_warning_required"] is True
    assert output["regeneration_recommended"] is True
    assert output["regeneration_request"]["unsupported_sentence_ids"]
    assert output["unsupported_claims"]


def test_low_confidence_fixture_creates_low_confidence_or_warning(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "low-confidence")

    run_verification_workflow(
        input_path=FIXTURE_DIR / "low_confidence.json",
        **paths,
    )

    output = _read(paths["output_path"])
    assert output["overall_label"] in {"LOW_CONFIDENCE", "UNSUPPORTED"}
    assert output["ui_warning_required"] is True


def test_invalid_citation_fixture_marks_invalid_and_warns(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "invalid-citation")

    run_verification_workflow(
        input_path=FIXTURE_DIR / "invalid_citation.json",
        **paths,
    )

    output = _read(paths["output_path"])
    assert output["overall_label"] in {"UNSUPPORTED", "LOW_CONFIDENCE"}
    assert output["citation_coverage"]["invalid_citations"] >= 1
    assert "valid_context_citation" in output["sentence_results"][0]["failed_rules"]


def test_numeric_mismatch_fixture_preserves_numeric_rule_failure(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "numeric-mismatch")

    run_verification_workflow(
        input_path=FIXTURE_DIR / "numeric_mismatch.json",
        **paths,
    )

    output = _read(paths["output_path"])
    assert output["overall_label"] == "UNSUPPORTED"
    assert "number_date_version_presence" in output["sentence_results"][0]["failed_rules"]


def test_insufficient_context_fixture_is_safe_low_confidence(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "insufficient-context")

    result = run_verification_workflow(
        input_path=FIXTURE_DIR / "insufficient_context.json",
        **paths,
    )

    output = _read(paths["output_path"])
    assert result.status in {"success", "partial_success"}
    assert output["overall_label"] == "LOW_CONFIDENCE"
    assert output["ui_warning_required"] is True


def test_malformed_input_fixture_writes_safe_failed_artifacts(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "malformed")

    result = run_verification_workflow(
        input_path=FIXTURE_DIR / "malformed.json",
        **paths,
    )

    report = _read(paths["report_output_path"])
    failed = _read(paths["failed_output_path"])
    assert result.status == "failed"
    assert report["status"] == "failed"
    assert failed[0]["error_type"] == "malformed_json"


def test_provider_failure_fixture_keeps_safe_report(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "provider-failure")

    result = run_verification_workflow(
        input_path=FIXTURE_DIR / "unsupported.json",
        provider=FailingProvider(),
        evaluate_suspicious_only=False,
        **paths,
    )

    output = _read(paths["output_path"])
    failed = _read(paths["failed_output_path"])
    assert result.status == "partial_success"
    assert output["overall_label"] == "LOW_CONFIDENCE"
    assert failed[0]["error_type"] == "provider_failure"


def test_qca_json_and_jsonl_shapes(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "qca")

    run_verification_workflow(
        input_path=FIXTURE_DIR / "supported.json",
        **paths,
    )

    qca_json = _read(paths["qca_output_path"])
    qca_jsonl_path = paths["qca_output_path"].with_suffix(".jsonl")
    qca_jsonl = json.loads(qca_jsonl_path.read_text(encoding="utf-8").strip())
    for payload in (qca_json, qca_jsonl):
        assert payload["qca_id"]
        assert payload["verification_id"]
        assert payload["generation_id"]
        assert payload["context_refs"]
        assert payload["quality_label"] in {"accepted", "needs_review", "rejected"}


def test_output_schema_and_mvp_boundary_markers(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "schema")

    run_verification_workflow(
        input_path=FIXTURE_DIR / "unsupported.json",
        **paths,
    )

    output = _read(paths["output_path"])
    assert "sentence_results" in output
    assert "citation_coverage" in output
    assert "ui_warning" in output
    assert "qca_output_ref" in output
    assert "regeneration_request" in output
    assert output["regeneration_request"] is not None
    assert "unsupported_sentence_ids" in output["regeneration_request"]


def test_output_report_qca_failed_do_not_expose_sensitive_markers(tmp_path: Path) -> None:
    paths = _paths(tmp_path, "safety")

    run_verification_workflow(
        input_path=FIXTURE_DIR / "supported.json",
        provider=FailingProvider(),
        evaluate_suspicious_only=False,
        **paths,
    )

    rendered = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            paths["output_path"],
            paths["report_output_path"],
            paths["qca_output_path"],
            paths["qca_output_path"].with_suffix(".jsonl"),
            paths["failed_output_path"],
        ]
    )
    assert "synthetic-secret" not in rendered
    assert "synthetic-token" not in rendered
    assert "Authorization: Bearer" not in rendered
    assert "OPENAI_API_KEY=" not in rendered


class FailingProvider:
    def evaluate_sentence(self, target, contexts):
        raise EvaluatorProviderError(
            "OPENAI_API_KEY=synthetic-secret Authorization: Bearer synthetic-token",
            error_type="provider_failure",
            retryable=True,
        )


def _paths(tmp_path: Path, name: str) -> dict[str, Path]:
    return {
        "output_path": tmp_path / name / "verification_output.json",
        "report_output_path": tmp_path / name / "verification_report.json",
        "qca_output_path": tmp_path / name / "qca_output.json",
        "failed_output_path": tmp_path / name / "failed_items.json",
    }


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
