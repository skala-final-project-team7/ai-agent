from __future__ import annotations

import json
from uuid import uuid4

from history_manager_agent.context import ContextPolicyResult
from history_manager_agent.question import (
    ContextualizedQuestionRequest,
    FakeQuestionRewriter,
    build_history_decision,
    build_query_routing_input,
    build_question_result,
)
from history_manager_agent.schemas import HistoryDecisionLabel, PreservedContext


def _runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _policy_result(
    label: HistoryDecisionLabel,
    preserved_context: PreservedContext | None = None,
    reset_required: bool | None = None,
    warnings: list[str] | None = None,
) -> ContextPolicyResult:
    return ContextPolicyResult(
        history_decision=label,
        reset_required=label == HistoryDecisionLabel.NEW_TOPIC
        if reset_required is None
        else reset_required,
        preserved_context=preserved_context or PreservedContext(),
        confidence=0.82 if label != HistoryDecisionLabel.AMBIGUOUS else 0.35,
        reason="Synthetic classification reason.",
        warnings=warnings or [],
    )


def test_follow_up_contextualized_question_uses_preserved_context() -> None:
    result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="그럼 롤백 절차는?",
        policy_result=_policy_result(
            HistoryDecisionLabel.FOLLOW_UP,
            PreservedContext(
                summary="IAM 정책 수정 장애 상황",
                entities=["IAM"],
                turn_refs=["turn-1", "turn-2"],
            ),
        ),
    )

    assert result.contextualized_question == "IAM 정책 수정 장애 상황에서 그럼 롤백 절차는?"
    assert result.warnings == []


def test_new_topic_keeps_current_question() -> None:
    result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="새 배포 정책은?",
        policy_result=_policy_result(HistoryDecisionLabel.NEW_TOPIC),
    )

    assert result.contextualized_question == "새 배포 정책은?"
    assert result.reset_required is True


def test_ambiguous_uses_conservative_current_question_with_warning() -> None:
    result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="그건 어떻게 해?",
        policy_result=_policy_result(
            HistoryDecisionLabel.AMBIGUOUS,
            PreservedContext(summary="최근 최소 맥락", turn_refs=["turn-3"]),
            reset_required=False,
            warnings=["ambiguous_low_confidence"],
        ),
    )

    assert result.contextualized_question == "그건 어떻게 해?"
    assert "ambiguous_low_confidence" in result.warnings
    assert "ambiguous_conservative_question" in result.warnings


def test_empty_rewriter_output_falls_back_to_current_question() -> None:
    result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="원문 질문?",
        policy_result=_policy_result(
            HistoryDecisionLabel.FOLLOW_UP,
            PreservedContext(summary="이전 맥락", turn_refs=["turn-1"]),
        ),
        rewriter=FakeQuestionRewriter(""),
    )

    assert result.contextualized_question == "원문 질문?"
    assert "question_rewrite_empty" in result.warnings


def test_too_long_rewriter_output_falls_back_to_current_question() -> None:
    result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="짧은 원문?",
        policy_result=_policy_result(
            HistoryDecisionLabel.FOLLOW_UP,
            PreservedContext(summary="이전 맥락", turn_refs=["turn-1"]),
        ),
        rewriter=FakeQuestionRewriter("너무 긴 질문 " * 50),
        max_question_chars=60,
    )

    assert result.contextualized_question == "짧은 원문?"
    assert "question_rewrite_too_long" in result.warnings


def test_rewriter_failure_falls_back_and_records_warning() -> None:
    result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="원문 질문?",
        policy_result=_policy_result(
            HistoryDecisionLabel.FOLLOW_UP,
            PreservedContext(summary="이전 맥락", turn_refs=["turn-1"]),
        ),
        rewriter=FakeQuestionRewriter(RuntimeError("synthetic failure")),
    )

    assert result.contextualized_question == "원문 질문?"
    assert "question_rewrite_failed" in result.warnings


def test_query_routing_input_uses_contextualized_question() -> None:
    question_result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="그럼 롤백 절차는?",
        policy_result=_policy_result(
            HistoryDecisionLabel.FOLLOW_UP,
            PreservedContext(summary="IAM 정책 수정 장애 상황", turn_refs=["turn-1"]),
        ),
    )

    routing_input = build_query_routing_input(
        question_result,
        metadata={"locale": "ko-KR"},
    )

    assert routing_input.query == question_result.contextualized_question
    assert routing_input.history_decision == HistoryDecisionLabel.FOLLOW_UP
    assert routing_input.preserved_context == question_result.preserved_context
    assert routing_input.reset_required is False
    assert routing_input.metadata["locale"] == "ko-KR"


def test_history_decision_schema_is_built_consistently() -> None:
    question_result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="새 정책은?",
        policy_result=_policy_result(HistoryDecisionLabel.NEW_TOPIC),
    )

    decision = build_history_decision(question_result)
    serialized = decision.to_dict()

    assert serialized["original_question"] == "새 정책은?"
    assert serialized["contextualized_question"] == "새 정책은?"
    assert serialized["history_decision"] == "new_topic"
    assert serialized["reset_required"] is True


def test_routing_input_does_not_include_full_history() -> None:
    full_history_content = "full-history-content-" + ("x" * 100)
    question_result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="그럼 롤백?",
        policy_result=_policy_result(
            HistoryDecisionLabel.FOLLOW_UP,
            PreservedContext(
                summary="짧은 요약",
                entities=["IAM"],
                turn_refs=["turn-1", "turn-2"],
            ),
        ),
        metadata={"raw_history": full_history_content},
    )

    routing_input = build_query_routing_input(question_result)
    serialized = json.dumps(routing_input.to_dict(), ensure_ascii=False)

    assert full_history_content not in serialized
    assert "raw_history" not in serialized
    assert routing_input.preserved_context.turn_refs == ["turn-1", "turn-2"]


def test_output_does_not_expose_sensitive_terms() -> None:
    policy_result = _policy_result(
        HistoryDecisionLabel.FOLLOW_UP,
        PreservedContext(summary="이전 맥락", turn_refs=["turn-1"]),
    )
    question_result = build_question_result(
        conversation_id="conversation-1",
        user_id="user-1",
        current_question="원문 질문?",
        policy_result=policy_result,
        rewriter=FakeQuestionRewriter(RuntimeError("OPENAI_API_KEY Authorization Bearer")),
    )
    request = ContextualizedQuestionRequest(
        original_question="원문 질문?",
        policy_result=policy_result,
    )

    serialized = json.dumps(
        {
            "question_result": question_result.to_dict(),
            "routing_input": build_query_routing_input(question_result).to_dict(),
            "request": request.to_safe_dict(),
        },
        ensure_ascii=False,
    )

    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "Bearer" not in serialized
    assert "secret-like" not in serialized
