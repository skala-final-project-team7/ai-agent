"""ai-agent/answer-generation-agent/tests/unit/test_prompt_template_builder.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import json

from answer_generation_agent.generation.input_normalization import (
    normalize_generation_input,
)
from answer_generation_agent.generation.prompt_template import build_prompt_payload


def test_timeline_prompt_contains_incident_timeline_and_action_order() -> None:
    payload = _normalized_result("timeline")

    prompt = build_prompt_payload(payload)
    combined_prompt = prompt.combined_text()

    assert prompt.task_prompt_type == "timeline"
    assert "장애 대응" in combined_prompt
    assert "상황 요약" in combined_prompt
    assert "시간/단계 흐름" in combined_prompt
    assert "조치 순서" in combined_prompt


def test_step_by_step_prompt_contains_procedure_and_cautions() -> None:
    prompt = build_prompt_payload(_normalized_result("step_by_step"))

    combined_prompt = prompt.combined_text()

    assert prompt.task_prompt_type == "step_by_step"
    assert "운영 가이드" in combined_prompt
    assert "단계별 절차" in combined_prompt
    assert "주의사항" in combined_prompt
    assert "확인 방법" in combined_prompt


def test_evidence_first_prompt_contains_policy_and_evidence_first_instruction() -> None:
    prompt = build_prompt_payload(_normalized_result("evidence_first"))

    combined_prompt = prompt.combined_text()

    assert prompt.task_prompt_type == "evidence_first"
    assert "정책·절차" in combined_prompt
    assert "근거 문서/조항 우선" in combined_prompt
    assert "결론" in combined_prompt
    assert "예외/주의사항" in combined_prompt


def test_history_summary_prompt_contains_history_change_and_date_focus() -> None:
    prompt = build_prompt_payload(_normalized_result("history_summary"))

    combined_prompt = prompt.combined_text()

    assert prompt.task_prompt_type == "history_summary"
    assert "이력 조회" in combined_prompt
    assert "변경/처리 이력" in combined_prompt
    assert "날짜/대상/결과" in combined_prompt


def test_general_prompt_contains_direct_answer_instruction() -> None:
    prompt = build_prompt_payload(_normalized_result("general"))

    combined_prompt = prompt.combined_text()

    assert prompt.task_prompt_type == "general"
    assert "일반 질문" in combined_prompt
    assert "간결한 직접 답변" in combined_prompt
    assert "근거 출처" in combined_prompt


def test_unsupported_task_prompt_type_falls_back_to_general_with_warning() -> None:
    normalized = _normalized_result("timeline")
    normalized.generation_input.routing_decision.task_prompt_type = "future_prompt"

    prompt = build_prompt_payload(normalized)

    assert prompt.task_prompt_type == "general"
    assert any(warning.code == "unsupported_task_prompt_type" for warning in prompt.warnings)
    assert "일반 질문" in prompt.combined_text()


def test_common_system_prompt_contains_context_only_answer_rules() -> None:
    prompt = build_prompt_payload(_normalized_result("timeline"))

    assert "제공된 context 밖의 사실을 단정하지 않는다" in prompt.system_prompt
    assert "근거가 부족한 부분은 제한 사항으로 표시한다" in prompt.system_prompt
    assert "context가 존재하면 근거 있는 범위에서 최대한 답변한다" in (
        prompt.system_prompt
    )


def test_prompt_contains_sentence_level_citation_and_verification_json_instruction() -> None:
    prompt = build_prompt_payload(_normalized_result("timeline"))

    combined_prompt = prompt.combined_text()

    assert "sentence-level citation" in combined_prompt
    assert "context_id" in combined_prompt
    assert "Answer Verification Agent" in combined_prompt
    assert '"sentences"' in combined_prompt
    assert '"citations"' in combined_prompt
    assert '"unsupported_gaps"' in combined_prompt


def test_top_context_is_formatted_with_context_id_content_and_source_metadata() -> None:
    prompt = build_prompt_payload(_normalized_result("timeline"))

    user_prompt = prompt.user_prompt

    assert "ctx-001" in user_prompt
    assert "Synthetic rollback context." in user_prompt
    assert "Synthetic Runbook" in user_prompt
    assert "OPS" in user_prompt
    assert "https://example.invalid/pages/ctx-001" in user_prompt
    assert "score=0.7" in user_prompt
    assert "rerank_score=0.9" in user_prompt


def test_empty_context_builds_safe_insufficient_context_prompt() -> None:
    prompt = build_prompt_payload(_normalized_result("timeline", contexts=[]))

    assert prompt.context_count == 0
    assert "사용 가능한 context가 없다" in prompt.user_prompt
    assert any(warning.code == "insufficient_context_candidate" for warning in prompt.warnings)


def test_prompt_uses_normalized_top_contexts_without_copying_all_search_results() -> None:
    contexts = [
        _context(f"ctx-{index}", content=f"Synthetic context {index}.", rerank_score=1.0 - index / 10)
        for index in range(1, 8)
    ]
    prompt = build_prompt_payload(_normalized_result("timeline", contexts=contexts))

    combined_prompt = prompt.combined_text()

    assert prompt.context_count == 5
    assert "ctx-1" in combined_prompt
    assert "ctx-5" in combined_prompt
    assert "ctx-6" not in combined_prompt
    assert "search_results" not in combined_prompt
    assert "top_contexts" not in combined_prompt


def test_context_truncation_adds_warning_and_keeps_prompt_safe() -> None:
    prompt = build_prompt_payload(
        _normalized_result(
            "timeline",
            contexts=[_context("ctx-long", content="A" * 200)],
        ),
        max_context_chars=40,
    )

    assert "A" * 40 in prompt.user_prompt
    assert "A" * 80 not in prompt.user_prompt
    assert any(warning.code == "context_truncated" for warning in prompt.warnings)


def test_prompt_payload_does_not_expose_sensitive_markers() -> None:
    normalized = _normalized_result(
        "timeline",
        contexts=[
            _context(
                "ctx-001",
                content="Synthetic context with OPENAI_API_KEY and Authorization markers.",
                metadata={"safe": "kept", "api_key": "synthetic-marker"},
            )
        ],
    )

    prompt = build_prompt_payload(normalized)
    serialized = json.dumps(prompt.to_dict())

    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "synthetic-marker" not in serialized
    assert "secret" not in serialized.lower()


def _normalized_result(
    task_prompt_type: str,
    *,
    contexts: list[dict[str, object]] | None = None,
):
    return normalize_generation_input(
        {
            "conversation_id": "conversation-synthetic",
            "user_id": "user-synthetic",
            "routing_decision": {
                "routing_id": "routing-synthetic",
                "original_question": "Rollback?",
                "query": "IAM rollback procedure",
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
    rerank_score: float = 0.9,
    metadata: dict[str, object] | None = None,
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
        "rerank_score": rerank_score,
        "metadata": metadata or {"page_id": f"page-{context_id}"},
    }
