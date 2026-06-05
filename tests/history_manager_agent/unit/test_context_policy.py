from __future__ import annotations

import json
from uuid import uuid4

from history_manager_agent.config import HistoryManagerConfig
from history_manager_agent.context import apply_context_policy
from history_manager_agent.history import normalize_history_input_payload
from history_manager_agent.llm import HistoryClassification
from history_manager_agent.schemas import HistoryDecisionLabel


def _runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _turn(
    turn_id: str,
    role: str = "user",
    content: str = "Synthetic context",
    created_at: str = "2026-05-15T00:00:00Z",
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
    max_context_chars: int = 400,
):
    return normalize_history_input_payload(
        {
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
            "metadata": {"source": "synthetic"},
        },
        HistoryManagerConfig(history_window_turns=5, max_context_chars=max_context_chars),
    )


def _classification(
    label: HistoryDecisionLabel,
    confidence: float = 0.8,
) -> HistoryClassification:
    return HistoryClassification(
        history_decision=label,
        confidence=confidence,
        reason="Synthetic classification reason.",
    )


def test_follow_up_preserves_context_and_reset_is_false() -> None:
    result = apply_context_policy(
        normalized_history=_normalized_history(),
        classification=_classification(HistoryDecisionLabel.FOLLOW_UP),
        max_summary_chars=240,
    )

    assert result.reset_required is False
    assert result.preserved_context.summary
    assert result.preserved_context.turn_refs == ["turn-1", "turn-2"]
    assert "IAM" in result.preserved_context.summary


def test_follow_up_turn_refs_use_recent_trimmed_history() -> None:
    result = apply_context_policy(
        normalized_history=_normalized_history(
            [
                _turn("turn-1", content="First", created_at="2026-05-15T00:01:00Z"),
                _turn("turn-2", content="Second", created_at="2026-05-15T00:02:00Z"),
                _turn("turn-3", content="Third", created_at="2026-05-15T00:03:00Z"),
            ],
            max_context_chars=12,
        ),
        classification=_classification(HistoryDecisionLabel.FOLLOW_UP),
        max_summary_chars=120,
    )

    assert result.preserved_context.turn_refs == ["turn-2", "turn-3"]
    assert "First" not in result.preserved_context.summary


def test_new_topic_resets_and_minimizes_previous_context() -> None:
    result = apply_context_policy(
        normalized_history=_normalized_history(),
        classification=_classification(HistoryDecisionLabel.NEW_TOPIC),
        max_summary_chars=240,
    )

    assert result.reset_required is True
    assert result.preserved_context.summary == ""
    assert result.preserved_context.turn_refs == []
    assert result.preserved_context.entities == []
    assert "context_reset" in result.warnings


def test_ambiguous_preserves_only_minimal_recent_context_and_warning() -> None:
    result = apply_context_policy(
        normalized_history=_normalized_history(
            [
                _turn("turn-1", content="Older context", created_at="2026-05-15T00:01:00Z"),
                _turn("turn-2", content="Recent user", created_at="2026-05-15T00:02:00Z"),
                _turn(
                    "turn-3",
                    "assistant",
                    "Recent answer",
                    "2026-05-15T00:03:00Z",
                ),
            ]
        ),
        classification=_classification(HistoryDecisionLabel.AMBIGUOUS, confidence=0.35),
        max_summary_chars=240,
    )

    assert result.reset_required is False
    assert result.preserved_context.turn_refs == ["turn-2", "turn-3"]
    assert "Older context" not in result.preserved_context.summary
    assert "ambiguous_low_confidence" in result.warnings


def test_preserved_context_does_not_copy_full_history() -> None:
    old_content = "old-content-" + ("x" * 120)
    recent_content = "recent-content"
    result = apply_context_policy(
        normalized_history=_normalized_history(
            [
                _turn("turn-1", content=old_content, created_at="2026-05-15T00:01:00Z"),
                _turn("turn-2", content=recent_content, created_at="2026-05-15T00:02:00Z"),
            ]
        ),
        classification=_classification(HistoryDecisionLabel.FOLLOW_UP),
        max_summary_chars=80,
    )

    serialized = json.dumps(result.to_dict(), ensure_ascii=False)

    assert old_content not in serialized
    assert len(result.preserved_context.summary) <= 80
    assert result.preserved_context.turn_refs == ["turn-1", "turn-2"]


def test_context_length_guard_adds_warning() -> None:
    result = apply_context_policy(
        normalized_history=_normalized_history(
            [
                _turn(
                    "turn-1",
                    content="Long synthetic context " * 20,
                    created_at="2026-05-15T00:01:00Z",
                )
            ]
        ),
        classification=_classification(HistoryDecisionLabel.FOLLOW_UP),
        max_summary_chars=60,
    )

    assert len(result.preserved_context.summary) <= 60
    assert "context_summary_truncated" in result.warnings


def test_empty_normalized_history_is_safe() -> None:
    result = apply_context_policy(
        normalized_history=_normalized_history([]),
        classification=_classification(HistoryDecisionLabel.FOLLOW_UP),
        max_summary_chars=120,
    )

    assert result.reset_required is False
    assert result.preserved_context.summary == ""
    assert result.preserved_context.turn_refs == []
    assert "empty_history_context" in result.warnings


def test_normalization_warnings_are_reflected_in_policy_result() -> None:
    result = apply_context_policy(
        normalized_history=_normalized_history(
            [
                _turn("turn-1", content="Valid", created_at="2026-05-15T00:01:00Z"),
                {"turn_id": "turn-2", "role": "assistant"},
            ]
        ),
        classification=_classification(HistoryDecisionLabel.FOLLOW_UP),
        max_summary_chars=120,
    )

    assert "invalid_turn" in result.warnings


def test_context_policy_result_does_not_expose_sensitive_terms() -> None:
    result = apply_context_policy(
        normalized_history=_normalized_history(),
        classification=_classification(HistoryDecisionLabel.FOLLOW_UP),
        max_summary_chars=240,
    )

    serialized = json.dumps(result.to_dict(), ensure_ascii=False)

    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "Bearer" not in serialized
    assert "secret-like" not in serialized
