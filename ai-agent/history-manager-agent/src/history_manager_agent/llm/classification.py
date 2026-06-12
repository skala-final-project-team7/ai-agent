"""ai-agent/history-manager-agent/src/history_manager_agent/llm/classification.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

"""
--------------------------------------------------
작성자 : 이영훈
작성목적 : History Manager Agent의 history classification prompt/응답 검증 서비스.
작성일 : 2026-05-15
변경사항 내역 (날짜, 변경목적, 변경내용 순)
  - 2026-05-15, 최초 작성, feature3 LLM classification 구현
--------------------------------------------------
[호환성]
  - Python 3.11.x 권장
  - 표준 라이브러리 dataclasses/json 기반
--------------------------------------------------
"""

import json
from dataclasses import dataclass
from typing import Any

from history_manager_agent.config import HistoryManagerConfig
from history_manager_agent.history import NormalizedHistoryResult
from history_manager_agent.llm.providers import (
    HistoryClassificationRequest,
    HistoryLLMProvider,
)
from history_manager_agent.schemas import HistoryDecisionLabel


class ClassificationValidationError(ValueError):
    """LLM classification 응답이 MVP schema를 만족하지 않을 때 발생한다."""


@dataclass(slots=True)
class HistoryClassification:
    """LLM provider classification 결과."""

    history_decision: HistoryDecisionLabel
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        self.history_decision = HistoryDecisionLabel(self.history_decision)
        self.validate()

    def validate(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ClassificationValidationError(
                "confidence must be between 0 and 1"
            )
        if not self.reason:
            raise ClassificationValidationError("reason is required")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "history_decision": self.history_decision.value,
            "confidence": self.confidence,
            "reason": self.reason,
        }


def classify_history(
    normalized_history: NormalizedHistoryResult,
    config: HistoryManagerConfig,
    provider: HistoryLLMProvider,
) -> HistoryClassification:
    """정규화된 history를 provider로 분류하고 schema validation을 수행한다."""
    prompt = build_classification_prompt(normalized_history)
    request = HistoryClassificationRequest(
        current_question=normalized_history.history_input.current_question,
        prompt=prompt,
        history_context=[
            turn.to_dict()
            for turn in normalized_history.to_llm_context_turns(include_system=False)
        ],
        model=config.model,
        temperature=config.temperature,
        timeout_seconds=config.timeout_seconds,
    )
    response = provider.classify_history(request)
    return parse_classification_response(response.content)


def build_classification_prompt(normalized_history: NormalizedHistoryResult) -> str:
    """classification 전용 prompt를 구성한다.

    feature3에서는 label/confidence/reason만 요구하고, context policy와 question
    rewriting은 후속 feature에 맡긴다.
    """
    history_lines = []
    for turn in normalized_history.to_llm_context_turns(include_system=False):
        history_lines.append(
            f"- turn_id={turn.turn_id}; role={turn.role.value}; content={turn.content}"
        )
    history_block = "\n".join(history_lines) if history_lines else "(empty history)"
    return "\n".join(
        [
            "Classify whether the current question depends on recent history.",
            "Return JSON only with keys: history_decision, confidence, reason.",
            "Allowed history_decision values: follow_up, new_topic, ambiguous.",
            "",
            f"Current question: {normalized_history.history_input.current_question}",
            "Trimmed history context:",
            history_block,
        ]
    )


def parse_classification_response(raw_content: str) -> HistoryClassification:
    """LLM JSON string을 HistoryClassification으로 검증/변환한다."""
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ClassificationValidationError("Invalid LLM JSON") from exc

    if not isinstance(payload, dict):
        raise ClassificationValidationError("LLM response must be a JSON object")

    label = str(payload.get("history_decision") or "")
    if label not in {item.value for item in HistoryDecisionLabel}:
        raise ClassificationValidationError("unsupported label")

    if "confidence" not in payload:
        raise ClassificationValidationError("confidence is required")
    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError) as exc:
        raise ClassificationValidationError("confidence must be a number") from exc

    reason = str(payload.get("reason") or "")
    return HistoryClassification(
        history_decision=HistoryDecisionLabel(label),
        confidence=confidence,
        reason=reason,
    )
