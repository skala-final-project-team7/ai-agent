from __future__ import annotations

import json
from typing import Any

import pytest

from answer_verification_agent.config import AnswerVerificationConfig
from answer_verification_agent.evaluator import (
    EvaluatorProviderError,
    FakeEvaluatorProvider,
    OpenAIEvaluatorProvider,
    OpenAITransportResponse,
    build_evaluator_prompt,
    parse_evaluator_response,
)
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
from answer_verification_agent.verification.suspicious_selector import (
    select_suspicious_sentences,
)


def test_fake_evaluator_returns_deterministic_result() -> None:
    target, normalized = _target()
    provider = FakeEvaluatorProvider(
        {
            "s1": {
                "label": "SUPPORTED",
                "score": 0.91,
                "reason": "Synthetic cited context supports the claim.",
            }
        }
    )

    result = provider.evaluate_sentence(target, normalized.contexts)

    assert result.sentence_id == "s1"
    assert result.label == SentenceLabel.SUPPORTED
    assert result.score == 0.91
    assert result.reason == "Synthetic cited context supports the claim."


def test_prompt_contains_sentence_context_failed_rules_and_reasons() -> None:
    target, normalized = _target()

    prompt = build_evaluator_prompt(target, normalized.contexts)

    rendered = json.dumps(prompt.to_dict(), sort_keys=True)
    assert "Rollback version v2.4.1 finished on 2026-05-18 with 99% success." in rendered
    assert "ctx-001" in rendered
    assert "number_date_version_presence" in rendered
    assert "number_date_version_mismatch" in rendered
    assert "OPENAI_API_KEY=" not in rendered
    assert "Authorization: Bearer" not in rendered


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("SUPPORTED", SentenceLabel.SUPPORTED),
        ("UNSUPPORTED", SentenceLabel.UNSUPPORTED),
        ("LOW_CONFIDENCE", SentenceLabel.LOW_CONFIDENCE),
    ],
)
def test_valid_evaluator_json_response_is_parsed(label: str, expected: SentenceLabel) -> None:
    result = parse_evaluator_response(
        '{"label":"%s","score":0.7,"reason":"checked","unsupported_claims":["claim"]}'
        % label,
        sentence_id="s1",
    )

    assert result.label == expected
    assert result.score == 0.7
    assert result.unsupported_claims == ["claim"]


def test_unknown_label_falls_back_to_low_confidence() -> None:
    result = parse_evaluator_response(
        '{"label":"MAYBE","score":0.8,"reason":"unknown label"}',
        sentence_id="s1",
    )

    assert result.label == SentenceLabel.LOW_CONFIDENCE
    assert result.score == 0.8
    assert "unknown label" in result.reason


def test_invalid_json_response_raises_safe_provider_error() -> None:
    with pytest.raises(EvaluatorProviderError) as exc_info:
        parse_evaluator_response("not-json", sentence_id="s1")

    assert exc_info.value.retryable is False
    assert exc_info.value.error_type == "invalid_response"
    assert "not-json" not in str(exc_info.value)


def test_openai_provider_uses_injected_transport_without_live_call(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def transport(request: dict[str, Any]) -> OpenAITransportResponse:
        captured.update(request)
        return OpenAITransportResponse(
            status_code=200,
            body={
                "choices": [
                    {
                        "message": {
                            "content": '{"label":"UNSUPPORTED","score":0.2,"reason":"missing cited evidence"}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-external-key")
    target, normalized = _target()
    provider = OpenAIEvaluatorProvider(
        config=AnswerVerificationConfig(
            evaluator_model="synthetic-evaluator",
            temperature=0.0,
            timeout_seconds=11,
            max_retries=1,
        ),
        transport=transport,
    )

    result = provider.evaluate_sentence(target, normalized.contexts)
    rendered_request = json.dumps(captured, sort_keys=True)
    rendered_result = json.dumps(result.to_dict(), sort_keys=True)

    assert result.label == SentenceLabel.UNSUPPORTED
    assert captured["model"] == "synthetic-evaluator"
    assert captured["temperature"] == 0.0
    assert captured["timeout_seconds"] == 11
    assert captured["headers"]["Authorization"] == "<redacted>"
    assert "synthetic-external-key" not in rendered_request
    assert "synthetic-external-key" not in rendered_result


def test_openai_provider_requires_external_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(EvaluatorProviderError) as exc_info:
        OpenAIEvaluatorProvider(config=AnswerVerificationConfig(openai_api_key=None))

    assert exc_info.value.retryable is False
    assert exc_info.value.error_type == "configuration_error"


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_openai_retryable_http_errors(status_code: int) -> None:
    def transport(_: dict[str, Any]) -> OpenAITransportResponse:
        return OpenAITransportResponse(
            status_code=status_code,
            body={"error": {"message": "Authorization: Bearer synthetic-token failed"}},
        )

    target, normalized = _target()
    provider = OpenAIEvaluatorProvider(
        config=AnswerVerificationConfig(openai_api_key="synthetic-external-key"),
        transport=transport,
    )

    with pytest.raises(EvaluatorProviderError) as exc_info:
        provider.evaluate_sentence(target, normalized.contexts)

    assert exc_info.value.retryable is True
    assert "synthetic-token" not in str(exc_info.value)
    assert "Authorization: Bearer" not in str(exc_info.value)


@pytest.mark.parametrize("status_code", [401, 403])
def test_openai_auth_errors_are_non_retryable(status_code: int) -> None:
    def transport(_: dict[str, Any]) -> OpenAITransportResponse:
        return OpenAITransportResponse(
            status_code=status_code,
            body={"error": {"message": "invalid credentials"}},
        )

    target, normalized = _target()
    provider = OpenAIEvaluatorProvider(
        config=AnswerVerificationConfig(openai_api_key="synthetic-external-key"),
        transport=transport,
    )

    with pytest.raises(EvaluatorProviderError) as exc_info:
        provider.evaluate_sentence(target, normalized.contexts)

    assert exc_info.value.retryable is False
    assert exc_info.value.error_type == "auth_error"


def test_openai_timeout_is_retryable() -> None:
    def transport(_: dict[str, Any]) -> OpenAITransportResponse:
        raise TimeoutError("Authorization: Bearer synthetic-token timed out")

    target, normalized = _target()
    provider = OpenAIEvaluatorProvider(
        config=AnswerVerificationConfig(openai_api_key="synthetic-external-key"),
        transport=transport,
    )

    with pytest.raises(EvaluatorProviderError) as exc_info:
        provider.evaluate_sentence(target, normalized.contexts)

    assert exc_info.value.retryable is True
    assert exc_info.value.error_type == "timeout"
    assert "synthetic-token" not in str(exc_info.value)


def _target():
    payload = _payload()
    normalized = normalize_verification_input(payload)
    parsed = parse_sentences_and_citations(normalized)
    rules = run_rule_based_verification(
        parsed,
        normalized.contexts,
        config=RuleVerifierConfig(source_coverage_threshold=0.0),
    )
    selection = select_suspicious_sentences(rules, normalized)
    return selection.evaluation_targets[0], normalized


def _payload() -> dict[str, object]:
    return {
        "conversation_id": "conversation-synthetic",
        "user_id": "user-synthetic",
        "answer_output": {
            "generation_id": "generation-synthetic",
            "answer_status": "success",
            "answer": "Rollback version v2.4.1 finished on 2026-05-18 with 99% success.",
            "sentences": [
                {
                    "sentence_id": "s1",
                    "text": "Rollback version v2.4.1 finished on 2026-05-18 with 99% success.",
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
                "content": "Rollback version v2.4.0 finished on 2026-05-17 with 90% success.",
                "score": 0.7,
                "rerank_score": 0.9,
                "metadata": {"page_id": "123"},
            }
        ],
        "metadata": {"locale": "ko-KR"},
    }
