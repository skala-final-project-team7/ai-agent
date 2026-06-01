from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from history_manager_agent.config import HistoryManagerConfig
from history_manager_agent.history.normalization import (
    HistoryInputLoaderError,
    load_and_normalize_history_input,
    load_history_input,
    normalize_history_input_payload,
)
from history_manager_agent.schemas import ConversationRole, HistoryManagerInput


def _runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _payload(history: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "conversation_id": _runtime_value("conversation"),
        "user_id": _runtime_value("user"),
        "current_question": "Synthetic current question?",
        "history": history or [],
        "metadata": {"source": "synthetic"},
    }


def _turn(
    turn_id: str,
    role: str = "user",
    content: str = "Synthetic content",
    created_at: str | None = "2026-05-15T00:00:00Z",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "turn_id": turn_id,
        "role": role,
        "content": content,
        "citations": [],
        "metadata": {"source": "synthetic"},
    }
    if created_at is not None:
        payload["created_at"] = created_at
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_history_input_reads_valid_input_json(tmp_path: Path) -> None:
    input_path = tmp_path / "history_input.json"
    _write_json(
        input_path,
        _payload([_turn("turn-1", "user"), _turn("turn-2", "assistant")]),
    )

    history_input = load_history_input(input_path)

    assert isinstance(history_input, HistoryManagerInput)
    assert history_input.current_question == "Synthetic current question?"
    assert [turn.role for turn in history_input.history] == [
        ConversationRole.USER,
        ConversationRole.ASSISTANT,
    ]


def test_load_history_input_raises_clear_error_for_malformed_json(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "history_input.json"
    input_path.write_text("{not-valid-json", encoding="utf-8")

    with pytest.raises(HistoryInputLoaderError, match="Malformed input JSON"):
        load_history_input(input_path)


def test_load_history_input_validates_current_question(tmp_path: Path) -> None:
    input_path = tmp_path / "history_input.json"
    payload = _payload()
    payload.pop("current_question")
    _write_json(input_path, payload)

    with pytest.raises(ValueError, match="current_question is required"):
        load_history_input(input_path)


def test_normalization_allows_known_roles_and_sorts_by_created_at() -> None:
    result = normalize_history_input_payload(
        _payload(
            [
                _turn("turn-3", "system", created_at="2026-05-15T00:03:00Z"),
                _turn("turn-1", "user", created_at="2026-05-15T00:01:00Z"),
                _turn("turn-2", "assistant", created_at="2026-05-15T00:02:00Z"),
            ]
        ),
        HistoryManagerConfig(history_window_turns=10),
    )

    assert [turn.turn_id for turn in result.normalized_history] == [
        "turn-1",
        "turn-2",
        "turn-3",
    ]
    assert [turn.role for turn in result.normalized_history] == [
        ConversationRole.USER,
        ConversationRole.ASSISTANT,
        ConversationRole.SYSTEM,
    ]
    assert result.input_turn_count == 3
    assert result.used_turn_count == 3
    assert [turn.turn_id for turn in result.to_llm_context_turns()] == [
        "turn-1",
        "turn-2",
    ]


def test_unknown_role_turn_is_warned_and_excluded() -> None:
    result = normalize_history_input_payload(
        _payload([_turn("turn-1", "user"), _turn("turn-2", "tool")]),
        HistoryManagerConfig(history_window_turns=10),
    )

    assert [turn.turn_id for turn in result.normalized_history] == ["turn-1"]
    assert result.used_turn_count == 1
    assert [warning.code for warning in result.warnings] == ["invalid_role"]


def test_missing_created_at_uses_deterministic_fallback_and_warning() -> None:
    result = normalize_history_input_payload(
        _payload(
            [
                _turn("turn-2", created_at="2026-05-15T00:02:00Z"),
                _turn("turn-1", created_at=None),
            ]
        ),
        HistoryManagerConfig(history_window_turns=10),
    )

    assert [turn.turn_id for turn in result.normalized_history] == [
        "turn-1",
        "turn-2",
    ]
    assert result.normalized_history[0].created_at == "0001-01-01T00:00:00Z"
    assert [warning.code for warning in result.warnings] == ["missing_created_at"]


def test_empty_history_returns_empty_normalized_history() -> None:
    result = normalize_history_input_payload(
        _payload([]),
        HistoryManagerConfig(history_window_turns=10),
    )

    assert result.normalized_history == []
    assert result.input_turn_count == 0
    assert result.used_turn_count == 0
    assert result.warnings == []


def test_malformed_turn_is_warned_and_valid_turns_remain() -> None:
    result = normalize_history_input_payload(
        _payload(
            [
                _turn("turn-1"),
                {"turn_id": "turn-2", "role": "assistant"},
                "not-an-object",
            ]
        ),
        HistoryManagerConfig(history_window_turns=10),
    )

    assert [turn.turn_id for turn in result.normalized_history] == ["turn-1"]
    assert result.input_turn_count == 3
    assert result.used_turn_count == 1
    assert [warning.code for warning in result.warnings] == [
        "invalid_turn",
        "invalid_turn",
    ]


def test_history_window_trimming_keeps_recent_turns() -> None:
    result = normalize_history_input_payload(
        _payload(
            [
                _turn(f"turn-{index}", created_at=f"2026-05-15T00:0{index}:00Z")
                for index in range(1, 8)
            ]
        ),
        HistoryManagerConfig(history_window_turns=5, max_context_chars=1000),
    )

    assert [turn.turn_id for turn in result.normalized_history] == [
        "turn-3",
        "turn-4",
        "turn-5",
        "turn-6",
        "turn-7",
    ]
    assert result.input_turn_count == 7
    assert result.used_turn_count == 5
    assert [warning.code for warning in result.warnings] == [
        "history_window_trimmed"
    ]


def test_max_context_chars_trimming_drops_oldest_turns() -> None:
    result = normalize_history_input_payload(
        _payload(
            [
                _turn("turn-1", content="aaaaa", created_at="2026-05-15T00:01:00Z"),
                _turn("turn-2", content="bbbbb", created_at="2026-05-15T00:02:00Z"),
                _turn("turn-3", content="ccccc", created_at="2026-05-15T00:03:00Z"),
            ]
        ),
        HistoryManagerConfig(history_window_turns=10, max_context_chars=10),
    )

    assert [turn.turn_id for turn in result.normalized_history] == [
        "turn-2",
        "turn-3",
    ]
    assert result.used_turn_count == 2
    assert [warning.code for warning in result.warnings] == [
        "max_context_chars_trimmed"
    ]


def test_load_and_normalize_result_reports_counts_and_warnings(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "history_input.json"
    _write_json(
        input_path,
        _payload([_turn("turn-1"), _turn("turn-2", "invalid")]),
    )

    result = load_and_normalize_history_input(
        input_path,
        HistoryManagerConfig(history_window_turns=10),
    )
    serialized = result.to_dict()

    assert serialized["input_turn_count"] == 2
    assert serialized["used_turn_count"] == 1
    assert serialized["warnings"][0]["code"] == "invalid_role"
    assert "history_input" not in serialized


def test_normalization_result_does_not_expose_sensitive_terms() -> None:
    result = normalize_history_input_payload(
        _payload([_turn("turn-1"), _turn("turn-2", "invalid")]),
        HistoryManagerConfig(history_window_turns=10),
    )

    serialized = json.dumps(result.to_dict())

    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "Bearer" not in serialized
    assert "secret-like" not in serialized
