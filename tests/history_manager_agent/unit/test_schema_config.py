from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from history_manager_agent.app import build_app_context
from history_manager_agent.config import HistoryManagerConfig
from history_manager_agent.schemas import (
    ConversationRole,
    ConversationTurn,
    HistoryDecision,
    HistoryDecisionLabel,
    HistoryManagerInput,
    HistoryReport,
    HistoryReportStatus,
    PreservedContext,
    QueryRoutingInput,
)
from history_manager_agent.scripts import run_history_manager


def _runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _turn(role: ConversationRole = ConversationRole.USER) -> ConversationTurn:
    return ConversationTurn(
        turn_id=_runtime_value("turn"),
        role=role,
        content="Synthetic conversation content",
        created_at="2026-05-15T00:00:00Z",
        citations=[],
        metadata={"source": "synthetic"},
    )


def test_config_accepts_external_runtime_values_and_redacts_key() -> None:
    api_key = _runtime_value("synthetic-api-key")
    config = HistoryManagerConfig(
        history_window_turns=7,
        max_context_chars=1200,
        model="synthetic-model",
        temperature=0.1,
        timeout_seconds=11,
        max_retries=4,
        openai_api_key=api_key,
    )

    safe_config = config.to_safe_dict()

    assert config.history_window_turns == 7
    assert config.max_context_chars == 1200
    assert config.model == "synthetic-model"
    assert config.temperature == 0.1
    assert config.timeout_seconds == 11
    assert config.max_retries == 4
    assert safe_config["openai_api_key"] == "<redacted>"
    assert api_key not in repr(config)
    assert api_key not in json.dumps(safe_config)
    assert "Authorization" not in json.dumps(safe_config)


def test_conversation_turn_schema_supports_roles_citations_and_metadata() -> None:
    for role in (
        ConversationRole.USER,
        ConversationRole.ASSISTANT,
        ConversationRole.SYSTEM,
    ):
        turn = _turn(role)
        serialized = turn.to_dict()

        assert serialized["turn_id"]
        assert serialized["role"] == role
        assert serialized["content"] == "Synthetic conversation content"
        assert serialized["created_at"] == "2026-05-15T00:00:00Z"
        assert serialized["citations"] == []
        assert serialized["metadata"] == {"source": "synthetic"}


def test_history_manager_input_contains_required_contract_fields() -> None:
    history_input = HistoryManagerInput(
        conversation_id=_runtime_value("conversation"),
        user_id=_runtime_value("user"),
        current_question="Synthetic current question?",
        history=[_turn()],
        metadata={"locale": "ko-KR", "timezone": "Asia/Seoul"},
    )
    serialized = history_input.to_dict()

    assert serialized["conversation_id"].startswith("conversation-")
    assert serialized["user_id"].startswith("user-")
    assert serialized["current_question"] == "Synthetic current question?"
    assert len(serialized["history"]) == 1
    assert serialized["metadata"]["locale"] == "ko-KR"


def test_history_decision_output_contains_canonical_fields() -> None:
    preserved_context = PreservedContext(
        summary="Synthetic summary",
        entities=["synthetic-system"],
        turn_refs=["turn-1"],
    )
    decision = HistoryDecision(
        conversation_id="conversation-1",
        user_id="user-1",
        original_question="What about rollback?",
        contextualized_question="What is the rollback process for the previous topic?",
        history_decision=HistoryDecisionLabel.FOLLOW_UP,
        reset_required=False,
        confidence=0.82,
        reason="The question refers to previous context.",
        preserved_context=preserved_context,
        warnings=[],
    )
    serialized = decision.to_dict()

    assert serialized["original_question"] == "What about rollback?"
    assert serialized["contextualized_question"].startswith("What is")
    assert serialized["history_decision"] == "follow_up"
    assert serialized["reset_required"] is False
    assert serialized["confidence"] == 0.82
    assert serialized["reason"]
    assert serialized["preserved_context"]["summary"] == "Synthetic summary"
    assert serialized["warnings"] == []


def test_query_routing_input_is_compatible_with_history_decision() -> None:
    preserved_context = PreservedContext(
        summary="Synthetic summary",
        entities=[],
        turn_refs=[],
    )
    routing_input = QueryRoutingInput(
        conversation_id="conversation-1",
        user_id="user-1",
        original_question="Original?",
        query="Contextualized?",
        history_decision=HistoryDecisionLabel.AMBIGUOUS,
        preserved_context=preserved_context,
        reset_required=False,
        metadata={"locale": "ko-KR"},
    )
    serialized = routing_input.to_dict()

    assert serialized["query"] == "Contextualized?"
    assert serialized["history_decision"] == "ambiguous"
    assert serialized["preserved_context"] == preserved_context.to_dict()
    assert serialized["reset_required"] is False


def test_decision_labels_support_mvp_values_and_unknown_safe_extension() -> None:
    assert HistoryDecisionLabel("follow_up") == HistoryDecisionLabel.FOLLOW_UP
    assert HistoryDecisionLabel("new_topic") == HistoryDecisionLabel.NEW_TOPIC
    assert HistoryDecisionLabel("ambiguous") == HistoryDecisionLabel.AMBIGUOUS
    assert HistoryDecisionLabel.from_value("future_label") == "future_label"


def test_history_report_schema_tracks_status_counts_and_decision() -> None:
    report = HistoryReport(
        job_id="job-1",
        conversation_id="conversation-1",
        status=HistoryReportStatus.SUCCESS,
        decision=HistoryDecisionLabel.NEW_TOPIC,
        input_turn_count=3,
        used_turn_count=0,
        warnings_count=0,
        created_at="2026-05-15T00:00:00Z",
    )
    serialized = report.to_dict()

    assert serialized["job_id"] == "job-1"
    assert serialized["status"] == "success"
    assert serialized["decision"] == "new_topic"
    assert serialized["input_turn_count"] == 3
    assert serialized["used_turn_count"] == 0
    assert serialized["warnings_count"] == 0


def test_required_values_raise_clear_validation_errors() -> None:
    with pytest.raises(ValueError, match="current_question is required"):
        HistoryManagerInput(
            conversation_id="conversation-1",
            user_id="user-1",
            current_question="",
            history=[],
        )

    with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
        HistoryDecision(
            conversation_id="conversation-1",
            user_id="user-1",
            original_question="Original?",
            contextualized_question="Contextualized?",
            history_decision=HistoryDecisionLabel.NEW_TOPIC,
            reset_required=True,
            confidence=1.2,
            reason="Synthetic reason",
            preserved_context=PreservedContext(),
        )


def test_app_context_and_cli_runs_workflow_without_openai_call(
    tmp_path: Path,
    capsys,
) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output" / "history_decision.json"
    input_path.write_text(
        json.dumps(
            {
                "conversation_id": "conversation-1",
                "user_id": "user-1",
                "current_question": "Synthetic question?",
                "history": [],
                "metadata": {"locale": "ko-KR"},
            }
        ),
        encoding="utf-8",
    )
    context = build_app_context(
        HistoryManagerConfig(
            history_window_turns=5,
            max_context_chars=4000,
            model="synthetic-model",
            temperature=0.0,
            timeout_seconds=30,
            max_retries=2,
        )
    )

    exit_code = run_history_manager.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "synthetic-model",
        ]
    )
    captured = capsys.readouterr()

    assert context.config.model == "synthetic-model"
    assert exit_code == 0
    assert "workflow completed" in captured.out
    assert "status=success" in captured.out
    assert "OPENAI_API_KEY" not in captured.out
    assert "Authorization" not in captured.out
    assert output_path.exists()
