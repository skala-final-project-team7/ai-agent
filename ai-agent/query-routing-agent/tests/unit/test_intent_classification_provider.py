from __future__ import annotations

import json
from uuid import uuid4

import pytest

from query_routing_agent.config import QueryRoutingConfig
from query_routing_agent.llm import (
    ClassificationValidationError,
    FakeRoutingLLMProvider,
    OpenAIRoutingLLMProvider,
    OpenAITransportError,
    RoutingClassificationRequest,
    RoutingProviderError,
    build_routing_prompt,
    classify_intent,
)
from query_routing_agent.routing import normalize_routing_input
from query_routing_agent.schemas import IntentLabel


def _runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _normalized_input():
    return normalize_routing_input(
        {
            "conversation_id": "conversation-synthetic",
            "user_id": "user-synthetic",
            "original_question": "그럼 롤백은?",
            "query": "IAM 정책 수정 장애 상황에서 롤백 절차는?",
            "history_decision": "follow_up",
            "preserved_context": {
                "summary": "IAM policy incident context",
                "entities": ["IAM", "rollback"],
                "turn_refs": ["turn-1", "turn-2"],
            },
            "reset_required": False,
            "metadata": {
                "locale": "ko-KR",
                "groups": ["ops-team"],
                "space_keys": ["OPS"],
            },
        }
    )


@pytest.mark.parametrize(
    ("intent", "confidence"),
    [
        ("incident_response", 0.88),
        ("operations_guide", 0.82),
        ("policy_procedure", 0.79),
        ("history_lookup", 0.76),
        ("unknown", 0.41),
    ],
)
def test_fake_provider_classifies_supported_intents(
    intent: str,
    confidence: float,
) -> None:
    provider = FakeRoutingLLMProvider(
        {
            "intent": intent,
            "confidence": confidence,
            "reason": "Synthetic routing reason.",
        }
    )

    result = classify_intent(
        normalized_input=_normalized_input(),
        config=QueryRoutingConfig(),
        provider=provider,
    )

    assert result.intent == IntentLabel(intent)
    assert result.confidence == confidence
    assert result.reason == "Synthetic routing reason."
    assert result.warnings == []
    assert provider.requests


def test_invalid_intent_falls_back_to_unknown_with_warning() -> None:
    provider = FakeRoutingLLMProvider(
        {
            "intent": "future_intent",
            "confidence": 0.65,
            "reason": "Synthetic routing reason.",
        }
    )

    result = classify_intent(_normalized_input(), QueryRoutingConfig(), provider)

    assert result.intent == IntentLabel.UNKNOWN
    assert result.confidence == 0.65
    assert result.warnings[0].code == "invalid_intent_fallback"
    assert "future_intent" not in json.dumps(result.to_safe_dict())


def test_confidence_out_of_range_raises_validation_error() -> None:
    provider = FakeRoutingLLMProvider(
        {
            "intent": "incident_response",
            "confidence": 1.5,
            "reason": "Synthetic routing reason.",
        }
    )

    with pytest.raises(
        ClassificationValidationError,
        match="confidence must be between 0 and 1",
    ):
        classify_intent(_normalized_input(), QueryRoutingConfig(), provider)


def test_invalid_json_response_raises_safe_error() -> None:
    provider = FakeRoutingLLMProvider("not-json")

    with pytest.raises(ClassificationValidationError, match="Invalid LLM JSON"):
        classify_intent(_normalized_input(), QueryRoutingConfig(), provider)


def test_schema_mismatch_response_raises_safe_error() -> None:
    provider = FakeRoutingLLMProvider({"intent": "incident_response", "confidence": 0.8})

    with pytest.raises(ClassificationValidationError, match="reason is required"):
        classify_intent(_normalized_input(), QueryRoutingConfig(), provider)


def test_routing_prompt_contains_limited_context_without_full_history() -> None:
    normalized = _normalized_input()
    prompt = build_routing_prompt(normalized.routing_input)

    assert "IAM 정책 수정 장애 상황에서 롤백 절차는?" in prompt
    assert "그럼 롤백은?" in prompt
    assert "follow_up" in prompt
    assert "IAM policy incident context" in prompt
    assert "IAM" in prompt
    assert "history" not in prompt.lower()
    assert "turn-1" in prompt


def test_openai_provider_reads_api_key_from_external_config_or_env_mapping() -> None:
    runtime_key = _runtime_value("runtime-key")
    provider = OpenAIRoutingLLMProvider.from_config(
        QueryRoutingConfig(model="synthetic-model"),
        env={"OPENAI_API_KEY": runtime_key},
        transport=lambda request: json.dumps(
            {
                "intent": "operations_guide",
                "confidence": 0.9,
                "reason": "Synthetic routing reason.",
            }
        ),
    )

    assert runtime_key not in repr(provider)
    assert runtime_key not in json.dumps(provider.to_safe_dict())


def test_openai_provider_missing_api_key_is_configuration_error() -> None:
    with pytest.raises(RoutingProviderError) as exc_info:
        OpenAIRoutingLLMProvider.from_config(QueryRoutingConfig(), env={})

    error = exc_info.value
    assert error.code == "provider_configuration_error"
    assert error.retryable is False
    assert "OPENAI_API_KEY" not in str(error)
    assert "Authorization" not in str(error)


def test_openai_provider_request_uses_config_without_exposing_key() -> None:
    captured: list[RoutingClassificationRequest] = []
    runtime_key = _runtime_value("runtime-key")

    def transport(request: RoutingClassificationRequest) -> str:
        captured.append(request)
        return json.dumps(
            {
                "intent": "history_lookup",
                "confidence": 0.7,
                "reason": "Synthetic routing reason.",
            }
        )

    provider = OpenAIRoutingLLMProvider.from_config(
        QueryRoutingConfig(
            model="synthetic-model",
            temperature=0.3,
            timeout_seconds=9,
            openai_api_key=runtime_key,
        ),
        env={},
        transport=transport,
    )

    result = classify_intent(_normalized_input(), provider.config, provider)

    assert result.intent == IntentLabel.HISTORY_LOOKUP
    assert captured[0].model == "synthetic-model"
    assert captured[0].temperature == 0.3
    assert captured[0].timeout_seconds == 9
    assert runtime_key not in json.dumps(captured[0].to_safe_dict())


def test_openai_auth_error_is_non_retryable() -> None:
    provider = OpenAIRoutingLLMProvider.from_config(
        QueryRoutingConfig(openai_api_key=_runtime_value("runtime-key")),
        env={},
        transport=lambda request: (_ for _ in ()).throw(
            OpenAITransportError(401, "Synthetic auth failure")
        ),
    )

    with pytest.raises(RoutingProviderError) as exc_info:
        classify_intent(_normalized_input(), provider.config, provider)

    assert exc_info.value.code == "openai_auth_error"
    assert exc_info.value.retryable is False


@pytest.mark.parametrize("status_code", [500, 503, 429])
def test_openai_timeout_and_5xx_are_retryable(status_code: int) -> None:
    provider = OpenAIRoutingLLMProvider.from_config(
        QueryRoutingConfig(openai_api_key=_runtime_value("runtime-key")),
        env={},
        transport=lambda request: (_ for _ in ()).throw(
            OpenAITransportError(status_code, "Synthetic transient failure")
        ),
    )

    with pytest.raises(RoutingProviderError) as exc_info:
        classify_intent(_normalized_input(), provider.config, provider)

    assert exc_info.value.retryable is True


def test_error_repr_and_safe_output_do_not_expose_sensitive_values() -> None:
    runtime_key = _runtime_value("runtime-key")
    provider = OpenAIRoutingLLMProvider.from_config(
        QueryRoutingConfig(openai_api_key=runtime_key),
        env={},
        transport=lambda request: (_ for _ in ()).throw(
            OpenAITransportError(
                500,
                f"Authorization Bearer {runtime_key} OPENAI_API_KEY",
            )
        ),
    )

    with pytest.raises(RoutingProviderError) as exc_info:
        classify_intent(_normalized_input(), provider.config, provider)

    error_text = str(exc_info.value)
    safe_text = json.dumps(provider.to_safe_dict())
    assert runtime_key not in error_text
    assert runtime_key not in safe_text
    assert "OPENAI_API_KEY" not in error_text
    assert "Authorization" not in error_text
