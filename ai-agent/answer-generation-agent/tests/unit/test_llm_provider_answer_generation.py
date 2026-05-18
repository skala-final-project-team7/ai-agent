from __future__ import annotations

import json

import pytest

from answer_generation_agent.config import AnswerGenerationConfig
from answer_generation_agent.generation.answer_generation import (
    AnswerGenerationService,
    AnswerProviderError,
    FakeAnswerLLMProvider,
    OpenAIAnswerLLMProvider,
    OpenAITransportError,
    ProviderConfigurationError,
    select_generation_model,
)
from answer_generation_agent.generation.input_normalization import (
    normalize_generation_input,
)


def test_fake_provider_answer_text_creates_generation_result() -> None:
    provider = FakeAnswerLLMProvider(
        response={
            "answer": "Synthetic rollback answer.",
            "sentences": [{"text": "Synthetic rollback answer.", "citations": ["ctx-001"]}],
            "unsupported_gaps": [],
        }
    )
    service = AnswerGenerationService(provider=provider)

    result = service.generate(
        normalized_input=_normalized_result(),
        config=AnswerGenerationConfig(model="synthetic-model"),
    )

    assert result.answer_status == "success"
    assert result.answer_text == "Synthetic rollback answer."
    assert result.model == "synthetic-model"
    assert result.provider_name == "fake"
    assert result.raw_sentence_candidates[0].text == "Synthetic rollback answer."


def test_fake_provider_sentence_citation_candidates_are_preserved() -> None:
    provider = FakeAnswerLLMProvider(
        response={
            "answer": "First synthetic sentence. Second synthetic sentence.",
            "sentences": [
                {"text": "First synthetic sentence.", "citations": ["ctx-001"]},
                {"text": "Second synthetic sentence.", "citations": ["ctx-002"]},
            ],
            "unsupported_gaps": ["Synthetic gap"],
        }
    )
    result = AnswerGenerationService(provider=provider).generate(
        normalized_input=_normalized_result(contexts=[_context("ctx-001"), _context("ctx-002")]),
        config=AnswerGenerationConfig(model="synthetic-model"),
    )

    assert [candidate.citations for candidate in result.raw_sentence_candidates] == [
        ["ctx-001"],
        ["ctx-002"],
    ]
    assert result.unsupported_gaps == ["Synthetic gap"]


def test_empty_top_contexts_returns_insufficient_context_without_provider_call() -> None:
    provider = FakeAnswerLLMProvider(response={"answer": "Should not be called."})

    result = AnswerGenerationService(provider=provider).generate(
        normalized_input=_normalized_result(contexts=[]),
        config=AnswerGenerationConfig(model="synthetic-model"),
    )

    assert result.answer_status == "insufficient_context"
    assert result.answer_text == ""
    assert provider.requests == []
    assert any(warning.code == "insufficient_context" for warning in result.warnings)


def test_usable_context_attempts_answer_generation() -> None:
    provider = FakeAnswerLLMProvider(
        response={"answer": "Synthetic answer.", "sentences": []}
    )

    result = AnswerGenerationService(provider=provider).generate(
        normalized_input=_normalized_result(),
        config=AnswerGenerationConfig(model="synthetic-model"),
    )

    assert result.answer_status == "success"
    assert len(provider.requests) == 1
    assert "Synthetic rollback context." in provider.requests[0].prompt.user_prompt


def test_weak_context_generates_warning_but_still_uses_provider() -> None:
    provider = FakeAnswerLLMProvider(
        response={"answer": "Limited synthetic answer.", "sentences": []}
    )

    result = AnswerGenerationService(provider=provider).generate(
        normalized_input=_normalized_result(
            query="network rollback",
            contexts=[_context("ctx-001", content="Unrelated calendar notes.")],
        ),
        config=AnswerGenerationConfig(model="synthetic-model"),
    )

    assert result.answer_status == "success"
    assert len(provider.requests) == 1
    assert any(warning.code == "weak_context" for warning in result.warnings)


def test_generation_service_passes_prompt_payload_to_provider() -> None:
    provider = FakeAnswerLLMProvider(response={"answer": "Synthetic answer."})

    AnswerGenerationService(provider=provider).generate(
        normalized_input=_normalized_result(task_prompt_type="step_by_step"),
        config=AnswerGenerationConfig(model="synthetic-model"),
    )

    assert provider.requests[0].prompt.task_prompt_type == "step_by_step"
    assert provider.requests[0].prompt.context_count == 1


def test_model_policy_selects_config_model_or_fallback_model() -> None:
    config = AnswerGenerationConfig(
        model="synthetic-primary-model",
        fallback_model="synthetic-fallback-model",
    )

    assert select_generation_model(config, use_fallback=False) == "synthetic-primary-model"
    assert select_generation_model(config, use_fallback=True) == "synthetic-fallback-model"


def test_invalid_llm_json_or_schema_mismatch_raises_safe_error() -> None:
    provider = FakeAnswerLLMProvider(raw_response="not-json")

    with pytest.raises(AnswerProviderError, match="invalid LLM response"):
        AnswerGenerationService(provider=provider).generate(
            normalized_input=_normalized_result(),
            config=AnswerGenerationConfig(model="synthetic-model"),
        )

    provider = FakeAnswerLLMProvider(response={"sentences": []})
    with pytest.raises(AnswerProviderError, match="answer is required"):
        AnswerGenerationService(provider=provider).generate(
            normalized_input=_normalized_result(),
            config=AnswerGenerationConfig(model="synthetic-model"),
        )


def test_openai_provider_reads_api_key_from_environment_or_external_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-external-key")

    env_provider = OpenAIAnswerLLMProvider()
    injected_provider = OpenAIAnswerLLMProvider(api_key="synthetic-injected-key")

    assert env_provider.has_api_key is True
    assert injected_provider.has_api_key is True
    assert "synthetic-external-key" not in repr(env_provider)
    assert "synthetic-injected-key" not in repr(injected_provider)


def test_openai_provider_without_api_key_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderConfigurationError, match="OpenAI credential is required"):
        OpenAIAnswerLLMProvider()


def test_openai_provider_request_reflects_model_temperature_and_timeout() -> None:
    transport = _RecordingTransport(
        response={
            "answer": "Synthetic OpenAI answer.",
            "sentences": [{"text": "Synthetic OpenAI answer.", "citations": ["ctx-001"]}],
        }
    )
    provider = OpenAIAnswerLLMProvider(
        api_key="synthetic-injected-key",
        transport=transport,
    )
    service = AnswerGenerationService(provider=provider)

    service.generate(
        normalized_input=_normalized_result(),
        config=AnswerGenerationConfig(
            model="synthetic-openai-model",
            temperature=0.3,
            timeout_seconds=12,
        ),
    )

    request = transport.requests[0]
    assert request["model"] == "synthetic-openai-model"
    assert request["temperature"] == 0.3
    assert request["timeout_seconds"] == 12
    assert "Authorization" not in json.dumps(request)
    assert "synthetic-injected-key" not in json.dumps(request)


def test_openai_auth_error_is_non_retryable() -> None:
    provider = OpenAIAnswerLLMProvider(
        api_key="synthetic-injected-key",
        transport=_RecordingTransport(
            error=OpenAITransportError(status_code=401, message="Authorization failed")
        ),
    )

    with pytest.raises(AnswerProviderError) as exc_info:
        AnswerGenerationService(provider=provider).generate(
            normalized_input=_normalized_result(),
            config=AnswerGenerationConfig(model="synthetic-openai-model"),
        )

    assert exc_info.value.retryable is False
    assert exc_info.value.error_type == "auth_error"
    assert "Authorization" not in str(exc_info.value)


@pytest.mark.parametrize("status_code", [429, 500, 503, None])
def test_openai_timeout_or_5xx_is_retryable(status_code: int | None) -> None:
    provider = OpenAIAnswerLLMProvider(
        api_key="synthetic-injected-key",
        transport=_RecordingTransport(
            error=OpenAITransportError(
                status_code=status_code,
                message="synthetic timeout" if status_code is None else "server error",
            )
        ),
    )

    with pytest.raises(AnswerProviderError) as exc_info:
        AnswerGenerationService(provider=provider).generate(
            normalized_input=_normalized_result(),
            config=AnswerGenerationConfig(model="synthetic-openai-model"),
        )

    assert exc_info.value.retryable is True
    assert exc_info.value.error_type in {"timeout_error", "rate_limit_error", "server_error"}


def test_error_repr_and_safe_strings_do_not_expose_sensitive_markers() -> None:
    error = AnswerProviderError(
        message="OPENAI_API_KEY Authorization API key secret synthetic-marker",
        retryable=False,
        error_type="provider_error",
    )

    serialized = repr(error) + str(error)

    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "API key" not in serialized
    assert "synthetic-marker" not in serialized
    assert "secret" not in serialized.lower()


def _normalized_result(
    *,
    query: str = "IAM rollback procedure",
    task_prompt_type: str = "timeline",
    contexts: list[dict[str, object]] | None = None,
):
    return normalize_generation_input(
        {
            "conversation_id": "conversation-synthetic",
            "user_id": "user-synthetic",
            "routing_decision": {
                "routing_id": "routing-synthetic",
                "original_question": "Rollback?",
                "query": query,
                "intent": "incident_response",
                "task_prompt_type": task_prompt_type,
                "expanded_queries": ["IAM rollback"],
                "metadata_filters": {"space_keys": ["OPS"]},
                "pool_weights": {"content": 1.0},
                "confidence": 0.8,
                "warnings": [],
            },
            "search_results": {
                "top_contexts": contexts
                if contexts is not None
                else [_context("ctx-001")],
            },
            "metadata": {"locale": "ko-KR"},
        }
    )


def _context(
    context_id: str,
    *,
    content: str = "Synthetic rollback context.",
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
        "metadata": {"page_id": f"page-{context_id}"},
    }


class _RecordingTransport:
    def __init__(
        self,
        *,
        response: dict[str, object] | None = None,
        error: OpenAITransportError | None = None,
    ) -> None:
        self.response = response or {"answer": "Synthetic transport answer."}
        self.error = error
        self.requests: list[dict[str, object]] = []

    def __call__(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response
