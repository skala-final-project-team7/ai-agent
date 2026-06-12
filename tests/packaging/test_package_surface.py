"""lina-ai-agents 패키징 surface 회귀 테스트.

작성자 : 이영훈
담당 영역 : ai-agent

deploy 레포는 이 저장소를 설치한 뒤 6개 top-level agent 패키지를 그대로 import한다.
루트 통합 앱 패키지(`app*`)가 배포 산출물에 섞이면 rag-deploy/ingestion-deploy의 `app`
패키지와 충돌하므로, pyproject metadata와 setuptools package discovery를 함께 고정한다.
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

from setuptools import find_packages

ROOT_DIR = Path(__file__).resolve().parents[2]

EXPECTED_AGENT_PATTERNS = [
    "data_ingestion_agent*",
    "data_sync_agent*",
    "history_manager_agent*",
    "query_routing_agent*",
    "answer_generation_agent*",
    "answer_verification_agent*",
]

EXPECTED_TOP_LEVEL_PACKAGES = {
    "data_ingestion_agent",
    "data_sync_agent",
    "history_manager_agent",
    "query_routing_agent",
    "answer_generation_agent",
    "answer_verification_agent",
}

CONSUMER_IMPORTS = [
    # ingestion-deploy app usage
    ("data_ingestion_agent.config", "DataIngestionConfig"),
    ("data_ingestion_agent.workflow", "run_full_crawl_workflow"),
    ("data_ingestion_agent.confluence", "ConfluenceClient"),
    ("data_sync_agent.config", "DataSyncConfig"),
    ("data_sync_agent.workflow", "run_data_sync_workflow"),
    # rag-deploy app usage
    ("history_manager_agent.config", "HistoryManagerConfig"),
    ("history_manager_agent.history", "normalize_history_input_payload"),
    ("query_routing_agent.config", "QueryRoutingConfig"),
    ("query_routing_agent.llm", "FakeRoutingLLMProvider"),
    ("answer_generation_agent.config", "AnswerGenerationConfig"),
    ("answer_generation_agent.generation.answer_generation", "OpenAIAnswerLLMProvider"),
    ("answer_verification_agent.config", "AnswerVerificationConfig"),
    ("answer_verification_agent.evaluator.providers", "FakeEvaluatorProvider"),
]


def _pyproject() -> dict:
    with (ROOT_DIR / "pyproject.toml").open("rb") as fp:
        return tomllib.load(fp)


def test_project_distribution_name_is_lina_ai_agents() -> None:
    assert _pyproject()["project"]["name"] == "lina-ai-agents"


def test_setuptools_include_only_exposes_agent_packages() -> None:
    include = _pyproject()["tool"]["setuptools"]["packages"]["find"]["include"]

    assert include == EXPECTED_AGENT_PATTERNS
    assert "app*" not in include


def test_find_packages_discovers_six_agent_top_level_packages_only() -> None:
    packages = find_packages(where=str(ROOT_DIR), include=EXPECTED_AGENT_PATTERNS)
    top_level = {package.split(".", maxsplit=1)[0] for package in packages}

    assert top_level == EXPECTED_TOP_LEVEL_PACKAGES
    assert "app" not in top_level


def test_deploy_consumer_import_contract_is_stable() -> None:
    for module_name, attribute_name in CONSUMER_IMPORTS:
        module = importlib.import_module(module_name)
        assert getattr(module, attribute_name) is not None
