from __future__ import annotations

import json
from uuid import uuid4

import pytest

from history_manager_agent.config import HistoryManagerConfig
from history_manager_agent.history import normalize_history_input_payload
from history_manager_agent.llm import (
    ClassificationValidationError,
    FakeHistoryLLMProvider,
    HistoryClassificationRequest,
    LLMProviderError,
    OpenAIHistoryLLMProvider,
    OpenAITransportError,
    classify_history,
)
from history_manager_agent.schemas import HistoryDecisionLabel


def _runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _turn(
    turn_id: str,
    role: str,
    content: str,
    created_at: str,
) -> dict[str, object]:
    return {
        "turn_id": turn_id,
        "role": role,
        "content": content,
        "created_at": created_at,
        "citations": [],
        "metadata": {"source": "synthetic"},
    }


def _normalized_history(
    history: list[dict[str, object]] | None = None,
    config: HistoryManagerConfig | None = None,
):
    payload = {
        "conversation_id": _runtime_value("conversation"),
        "user_id": _runtime_value("user"),
        "current_question": "그럼 롤백 절차는?",
        "history": history
        if history is not None
        else [
            _turn(
                "turn-1",
                "user",
                "IAM 정책 변경 중 장애가 발생했어.",
                "2026-05-15T00:01:00Z",
            ),
            _turn(
                "turn-2",
                "assistant",
                "영향 범위를 확인하고 이전 정책으로 되돌립니다.",
                "2026-05-15T00:02:00Z",
            ),
        ],
        "metadata": {"locale": "ko-KR"},
    }
    return normalize_history_input_payload(
        payload,
        config or HistoryManagerConfig(history_window_turns=5, max_context_chars=500),
    )


@pytest.mark.parametrize(
    ("label", "confidence"),
    [
        ("follow_up", 0.88),
        ("new_topic", 0.91),
        ("ambiguous", 0.42),
    ],
)
def test_fake_provider_classification_labels(label: str, confidence: float) -> None:
    provider = FakeHistoryLLMProvider(
        {
            "history_decision": label,
            "confidence": confidence,
            "reason": "Synthetic reason from fake provider.",
        }
    )

    result = classify_history(
        normalized_history=_normalized_history(),
        config=HistoryManagerConfig(),
        provider=provider,
    )

    assert result.history_decision == HistoryDecisionLabel(label)
    assert result.confidence == confidence
    assert result.reason == "Synthetic reason from fake provider."
    assert provider.requests


def test_confidence_out_of_range_raises_validation_error() -> None:
    provider = FakeHistoryLLMProvider(
        {
            "history_decision": "follow_up",
            "confidence": 1.5,
            "reason": "Synthetic reason.",
        }
    )

    with pytest.raises(
        ClassificationValidationError,
        match="confidence must be between 0 and 1",
    ):
        classify_history(_normalized_history(), HistoryManagerConfig(), provider)


def test_invalid_label_raises_validation_error() -> None:
    provider = FakeHistoryLLMProvider(
        {
            "history_decision": "not_supported",
            "confidence": 0.5,
            "reason": "Synthetic reason.",
        }
    )

    with pytest.raises(ClassificationValidationError, match="unsupported label"):
        classify_history(_normalized_history(), HistoryManagerConfig(), provider)


def test_invalid_json_response_raises_safe_error() -> None:
    provider = FakeHistoryLLMProvider("not-json")

    with pytest.raises(ClassificationValidationError, match="Invalid LLM JSON"):
        classify_history(_normalized_history(), HistoryManagerConfig(), provider)


def test_schema_mismatch_response_raises_safe_error() -> None:
    provider = FakeHistoryLLMProvider(
        {"history_decision": "follow_up", "confidence": 0.8}
    )

    with pytest.raises(ClassificationValidationError, match="reason is required"):
        classify_history(_normalized_history(), HistoryManagerConfig(), provider)


def test_classification_prompt_contains_question_and_trimmed_context() -> None:
    provider = FakeHistoryLLMProvider(
        {
            "history_decision": "follow_up",
            "confidence": 0.8,
            "reason": "Synthetic reason.",
        }
    )
    normalized = _normalized_history(
        [
            _turn("old-turn", "user", "Old synthetic topic", "2026-05-15T00:01:00Z"),
            _turn("system-turn", "system", "System instruction", "2026-05-15T00:02:00Z"),
            _turn("turn-1", "user", "Recent synthetic topic", "2026-05-15T00:03:00Z"),
            _turn("turn-2", "assistant", "Recent answer", "2026-05-15T00:04:00Z"),
        ],
        HistoryManagerConfig(history_window_turns=2, max_context_chars=500),
    )

    classify_history(
        normalized_history=normalized,
        config=HistoryManagerConfig(history_window_turns=2, max_context_chars=500),
        provider=provider,
    )
    request = provider.requests[0]

    assert "그럼 롤백 절차는?" in request.prompt
    assert "Recent synthetic topic" in request.prompt
    assert "Recent answer" in request.prompt
    assert "Old synthetic topic" not in request.prompt
    assert "System instruction" not in request.prompt


def test_openai_provider_reads_api_key_from_external_env_mapping() -> None:
    runtime_key = _runtime_value("runtime-key")
    provider = OpenAIHistoryLLMProvider.from_config(
        HistoryManagerConfig(model="synthetic-model"),
        env={"OPENAI_API_KEY": runtime_key},
        transport=lambda request: json.dumps(
            {
                "history_decision": "new_topic",
                "confidence": 0.9,
                "reason": "Synthetic reason.",
            }
        ),
    )

    assert runtime_key not in repr(provider)
    assert runtime_key not in json.dumps(provider.to_safe_dict())


def test_openai_provider_missing_api_key_is_configuration_error() -> None:
    with pytest.raises(LLMProviderError) as exc_info:
        OpenAIHistoryLLMProvider.from_config(HistoryManagerConfig(), env={})

    error = exc_info.value
    assert error.code == "provider_configuration_error"
    assert error.retryable is False
    assert "OPENAI_API_KEY" not in str(error)
    assert "Authorization" not in str(error)


def test_openai_provider_request_uses_config_without_exposing_key() -> None:
    captured: list[HistoryClassificationRequest] = []
    runtime_key = _runtime_value("runtime-key")

    def transport(request: HistoryClassificationRequest) -> str:
        captured.append(request)
        return json.dumps(
            {
                "history_decision": "ambiguous",
                "confidence": 0.35,
                "reason": "Synthetic reason.",
            }
        )

    provider = OpenAIHistoryLLMProvider.from_config(
        HistoryManagerConfig(
            model="synthetic-model",
            temperature=0.2,
            timeout_seconds=9,
        ),
        env={"OPENAI_API_KEY": runtime_key},
        transport=transport,
    )

    result = classify_history(_normalized_history(), provider.config, provider)

    assert result.history_decision == HistoryDecisionLabel.AMBIGUOUS
    assert captured[0].model == "synthetic-model"
    assert captured[0].temperature == 0.2
    assert captured[0].timeout_seconds == 9
    safe_request = json.dumps(captured[0].to_safe_dict())
    assert runtime_key not in safe_request
    assert "Authorization" not in safe_request


def test_openai_auth_error_is_non_retryable() -> None:
    runtime_key = _runtime_value("runtime-key")
    provider = OpenAIHistoryLLMProvider.from_config(
        HistoryManagerConfig(),
        env={"OPENAI_API_KEY": runtime_key},
        transport=lambda request: (_ for _ in ()).throw(
            OpenAITransportError(status_code=401, message="auth failed")
        ),
    )

    with pytest.raises(LLMProviderError) as exc_info:
        classify_history(_normalized_history(), provider.config, provider)

    assert exc_info.value.code == "openai_auth_error"
    assert exc_info.value.retryable is False
    assert runtime_key not in str(exc_info.value)


@pytest.mark.parametrize(
    "transport_error",
    [
        TimeoutError("timeout"),
        OpenAITransportError(status_code=503, message="service unavailable"),
    ],
)
def test_openai_timeout_and_5xx_are_retryable(transport_error: Exception) -> None:
    runtime_key = _runtime_value("runtime-key")
    provider = OpenAIHistoryLLMProvider.from_config(
        HistoryManagerConfig(),
        env={"OPENAI_API_KEY": runtime_key},
        transport=lambda request: (_ for _ in ()).throw(transport_error),
    )

    with pytest.raises(LLMProviderError) as exc_info:
        classify_history(_normalized_history(), provider.config, provider)

    assert exc_info.value.retryable is True
    assert runtime_key not in str(exc_info.value)


def test_errors_and_safe_representations_do_not_expose_sensitive_terms() -> None:
    provider = FakeHistoryLLMProvider("not-json")

    with pytest.raises(ClassificationValidationError) as exc_info:
        classify_history(_normalized_history(), HistoryManagerConfig(), provider)

    serialized_error = str(exc_info.value)
    assert "OPENAI_API_KEY" not in serialized_error
    assert "Authorization" not in serialized_error
    assert "Bearer" not in serialized_error
    assert "secret-like" not in serialized_error
