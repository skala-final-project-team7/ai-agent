# AI Agent Integration Test Plan - 2026-06-10

## Scope

This plan is limited to `/Users/younghoonlee/workspace_git/ai-agent`.

Other repositories (`backend-template`, `frontend`, `ingestion`, `rag`, `ingestion-deploy`,
`rag-deploy`) are read-only references for integration contracts. Do not modify them from this
workstream.

## Current Baseline

- Git state: `main...origin/main`, clean.
- Package name: `lina-ai-agents`.
- Published tag already available: `v0.1.0`.
- `setuptools.find_packages` exposure:
  - `data_ingestion_agent`
  - `data_sync_agent`
  - `history_manager_agent`
  - `query_routing_agent`
  - `answer_generation_agent`
  - `answer_verification_agent`
- Top-level `app*` is intentionally not part of the installable package surface.
- Local `.venv` has `pytest`, `ruff`, `mypy`, `setuptools`.
- Local `.venv` does not currently have `build` or `wheel`.
- `pytest --collect-only -q` collected 1017 tests.

## Integration Consumers

Deployment repositories expect these imports after installing `lina-ai-agents@v0.1.0`.

| Consumer | Expected top-level agent packages |
| --- | --- |
| `ingestion-deploy` | `data_ingestion_agent`, `data_sync_agent` |
| `rag-deploy` | `history_manager_agent`, `query_routing_agent`, `answer_generation_agent`, `answer_verification_agent` |

The deploy repositories remove in-repo vendored agent directories and keep application imports
unchanged, so the installed package must preserve the exact top-level package names.

## Risks To Cover

1. Package surface drift:
   - `app` accidentally re-enters `packages.find`.
   - one of the six agent packages disappears from the wheel/sdist.
   - package name regresses to `lina-rag-pipeline`.

2. Import surface drift:
   - deploy app imports fail after installing `lina-ai-agents`.
   - lazy imports in RAG adapters fail because a submodule is missing.
   - optional dependencies make module import too eager.

3. Credential leakage:
   - agent outputs, reports, message payloads, or errors include `access_token`.
   - routing/generation/verifier sanitizers regress on token-like keys.

4. ACL vocabulary drift:
   - ingestion-side ACL group values fall back to group names in production mode.
   - `space:{space_key}` leaks into production `allowed_groups`.
   - RAG query path receives `groups` but tests only cover PoC `space:*` groups.

5. Docs/config drift inside ai-agent:
   - `README.md` still recommends `allow_authenticated` as the empty restriction policy, while code default is `mark_missing`.
   - install/test instructions do not include package-surface verification.

## Work Plan

### Phase 1 - Baseline Verification

- Run current fast checks:
  - `./.venv/bin/python -m pytest --collect-only -q`
  - `./.venv/bin/python -m pytest tests/test_smoke.py tests/data_ingestion_agent/tests/integration tests/data_sync_agent/tests/integration tests/history_manager_agent/integration`
  - `./.venv/bin/python -m pytest tests/query/test_history.py tests/query/test_router.py tests/query/test_generator.py tests/query/test_verifier_evaluator.py`
- Run package surface check with `setuptools.find_packages`.
- Record any failures before editing.

Completion criteria:

- Existing tests collect successfully.
- Six top-level agent packages are detected.
- `app` is not detected in installable package set.

### Phase 2 - Add ai-agent Package Surface Tests

Add tests under `tests/packaging/`.

Test cases:

- `pyproject.toml` project name is exactly `lina-ai-agents`.
- `packages.find.include` is exactly the six agent package patterns.
- `packages.find.include` does not include `app*`.
- `setuptools.find_packages(...)` returns all six top-level agent packages.
- `setuptools.find_packages(...)` returns no top-level `app`.
- important consumer import paths can be imported without external services:
  - `data_ingestion_agent.config`
  - `data_ingestion_agent.workflow`
  - `data_sync_agent.config`
  - `data_sync_agent.workflow`
  - `history_manager_agent.workflow`
  - `query_routing_agent.routing`
  - `answer_generation_agent.generation`
  - `answer_verification_agent.verification`

Completion criteria:

- New tests fail if package metadata regresses.
- Tests run without network or real OpenAI/Confluence/Qdrant/Mongo/RabbitMQ.

### Phase 3 - Add Consumer Import Contract Tests

Add a focused import-contract test that mirrors deploy repository usage without modifying deploy repos.

Test cases:

- Import the specific modules used by `ingestion-deploy/app`:
  - `data_ingestion_agent.config.DataIngestionConfig`
  - `data_ingestion_agent.workflow.run_full_crawl_workflow`
  - `data_ingestion_agent.confluence.ConfluenceClient`
  - `data_sync_agent.config.DataSyncConfig`
  - `data_sync_agent.workflow.run_data_sync_workflow`
- Import the specific modules used by `rag-deploy/app`:
  - `history_manager_agent.config.HistoryManagerConfig`
  - `history_manager_agent.history.normalize_history_input_payload`
  - `query_routing_agent.config.QueryRoutingConfig`
  - `query_routing_agent.llm.FakeRoutingLLMProvider`
  - `answer_generation_agent.config.AnswerGenerationConfig`
  - `answer_generation_agent.generation.answer_generation.OpenAIAnswerLLMProvider`
  - `answer_verification_agent.config.AnswerVerificationConfig`
  - `answer_verification_agent.evaluator.providers.FakeEvaluatorProvider`

Completion criteria:

- Deploy-facing imports remain stable.
- Optional provider imports do not require credentials at import time.

### Phase 4 - ACL GroupId Regression Tests

Add/adjust ai-agent-owned tests around `app/adapters/atlassian.py`.

Test cases:

- When a Confluence restriction group includes both `id` and `name`, `parse_read_restrictions_acl`
  stores `id` by default.
- When `groupId` exists but `id` does not, it stores `groupId`.
- In Admin Key/page-level mode, explicit restrictions do not emit `space:{space_key}`.
- `space:{space_key}` remains covered only by explicit PoC fallback tests.

Completion criteria:

- Production path proves group id vocabulary.
- PoC fallback remains isolated and named as fallback in tests.

### Phase 5 - Documentation Cleanup Inside ai-agent

Update ai-agent-owned docs only.

Files:

- `README.md`
- `docs/ai/current-plan.md`
- any ai-agent docs that still call `allow_authenticated` the default after code changed to `mark_missing`.

Required changes:

- State `RAG_ATLASSIAN_EMPTY_RESTRICTION_POLICY=mark_missing` as the default recommended value.
- Explain `allow_authenticated` as opt-in only until inherited restrictions are handled safely.
- Explain production `allowed_groups` vocabulary: Confluence `groupId`.
- Keep `space:{key}` documented as fixture/Admin-Key-off fallback only.

Completion criteria:

- Docs match `app/config.py`.
- Docs do not imply group names are production ACL identifiers.

### Phase 6 - Optional Isolated Install Test

If allowed to install local build tooling, add an isolated install verification script.

Preferred command:

```bash
python3.11 -m pip install build wheel
python3.11 -m build --sdist --wheel
python3.11 -m venv /tmp/lina-ai-agents-install-check
/tmp/lina-ai-agents-install-check/bin/python -m pip install dist/lina_ai_agents-0.1.0-py3-none-any.whl
/tmp/lina-ai-agents-install-check/bin/python -c "import data_ingestion_agent, data_sync_agent, history_manager_agent, query_routing_agent, answer_generation_agent, answer_verification_agent; import importlib.util; assert importlib.util.find_spec('app') is None"
```

Fallback without `build`:

- use `pip install . --no-deps` into a temporary venv and run the same import check.

Completion criteria:

- Installed artifact exposes only the six top-level agent packages.
- Installed artifact does not expose root `app`.

## Validation Commands

Run before completion:

```bash
./.venv/bin/python -m pytest tests/packaging
./.venv/bin/python -m pytest tests/data_ingestion_agent/tests/integration tests/data_sync_agent/tests/integration tests/history_manager_agent/integration
./.venv/bin/python -m pytest tests/query/test_history.py tests/query/test_router.py tests/query/test_generator.py tests/query/test_verifier_evaluator.py
./.venv/bin/python -m pytest tests/adapters/test_atlassian.py tests/test_config.py
./.venv/bin/ruff check .
./.venv/bin/mypy app
```

Run if time permits:

```bash
./scripts/verify.sh
```

## Out Of Scope

- No edits to `backend-template`, `frontend`, `ingestion`, `rag`, `ingestion-deploy`, or `rag-deploy`.
- No infra changes.
- No dependency pin changes outside `ai-agent`.
- No secret, token, or `.env` file creation.
