"""scripts/smoke_ingest_api.py regression tests."""

from __future__ import annotations

import pytest

from scripts.smoke_ingest_api import build_settings, run_smoke


def test_build_settings_forces_local_json_fixture() -> None:
    settings = build_settings(samples_dir="samples")

    assert settings.source_type == "json_fixture"
    assert settings.samples_dir == "samples"
    assert settings.use_real_adapters is False
    assert settings.bff_admin_key_revoke_url == ""


@pytest.mark.asyncio
async def test_run_smoke_completes_full_ingest() -> None:
    result = await run_smoke(samples_dir="samples")

    final = result["final"]
    assert final["status"] == "COMPLETED"
    assert final["totalPages"] > 0
    assert final["processedPages"] > 0
    assert final["failedPages"] == 0
