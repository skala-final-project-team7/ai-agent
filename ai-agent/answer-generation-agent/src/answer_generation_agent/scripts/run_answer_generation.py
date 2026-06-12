"""ai-agent/answer-generation-agent/src/answer_generation_agent/scripts/run_answer_generation.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

"""
--------------------------------------------------
작성자 : 이영훈
작성목적 : Answer Generation Agent CLI entrypoint.
          feature7에서는 local JSON input/output workflow를 실행한다.
작성일 : 2026-05-18
변경사항 내역 (날짜, 변경목적, 변경내용 순)
  - 2026-05-18, 최초 작성, feature1 CLI skeleton 구현
  - 2026-05-18, 입력 정규화, feature2 normalization service 사용
  - 2026-05-18, feature7 workflow 실행 진입점으로 확장
--------------------------------------------------
[호환성]
  - Python 3.11.x 권장
  - 표준 라이브러리 argparse/json/pathlib 기반
--------------------------------------------------
"""

import argparse
from pathlib import Path
from typing import Sequence

from answer_generation_agent.config import AnswerGenerationConfig
from answer_generation_agent.generation import (
    AnswerProviderError,
    run_answer_generation_workflow,
)


def build_parser() -> argparse.ArgumentParser:
    """CLI argument parser를 구성한다."""
    parser = argparse.ArgumentParser(description="Run Answer Generation workflow.")
    parser.add_argument("--input", required=True, help="Generation input JSON path.")
    parser.add_argument("--output", required=True, help="Answer output JSON path.")
    parser.add_argument(
        "--report-output",
        default=None,
        help="Generation report JSON path.",
    )
    parser.add_argument(
        "--failed-output",
        default=None,
        help="Failed item JSON path.",
    )
    parser.add_argument(
        "--provider",
        choices=("fake", "openai"),
        default="fake",
        help="LLM provider. Tests and local fixtures should use fake.",
    )
    parser.add_argument("--model", default="configurable", help="Model name.")
    parser.add_argument(
        "--fallback-model",
        default="configurable",
        help="Fallback model name.",
    )
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-contexts", type=int, default=5)
    parser.add_argument("--max-answer-sentences", type=int, default=8)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI workflow를 실행한다. 검색/reranking/verification/SSE는 수행하지 않는다."""
    args = build_parser().parse_args(argv)
    config = AnswerGenerationConfig(
        model=args.model,
        fallback_model=args.fallback_model,
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        max_contexts=args.max_contexts,
        max_answer_sentences=args.max_answer_sentences,
    )
    try:
        result = run_answer_generation_workflow(
            input_path=Path(args.input),
            output_path=Path(args.output),
            report_output_path=Path(args.report_output) if args.report_output else None,
            failed_output_path=Path(args.failed_output) if args.failed_output else None,
            config=config,
            provider_name=args.provider,
        )
    except (AnswerProviderError, ValueError) as exc:
        print(f"Answer Generation workflow failed: {_safe_cli_message(str(exc))}")
        return 1

    print(
        "Answer Generation input validated and workflow completed: "
        f"status={result.status} "
        f"answer_status={result.answer_output.answer_status} "
        f"output={result.output_path} "
        f"report={result.report_path}"
    )
    return 0


def _safe_cli_message(message: str) -> str:
    redacted = message
    for marker in (
        "OPENAI_API_KEY",
        "Authorization",
        "api key",
        "API key",
        "secret",
        "token",
        "synthetic-marker",
    ):
        redacted = redacted.replace(marker, "<redacted>")
    return redacted


if __name__ == "__main__":
    raise SystemExit(main())
