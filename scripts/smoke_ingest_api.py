"""Local smoke test for /ml/ingest.

Runs the FastAPI route through ASGITransport with json_fixture + fake/in-memory ingestion
dependencies. No external Confluence, Qdrant, MongoDB, OpenAI, or BFF callback is required.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx
from httpx import ASGITransport

from app.api.ingest_deps import build_ingest_deps
from app.api.ingest_routes import get_deps
from app.api.main import create_app
from app.config import Settings


def build_settings(*, samples_dir: str) -> Settings:
    """Build deterministic local-smoke settings.

    The smoke intentionally ignores `.env` and live env values so it cannot accidentally call
    Atlassian or BFF while validating the ML ingestion API path.
    """
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        source_type="json_fixture",
        samples_dir=samples_dir,
        use_real_adapters=False,
        bff_admin_key_revoke_url="",
    )


async def run_smoke(*, samples_dir: str, mode: str = "full") -> dict[str, Any]:
    """POST /ml/ingest and read back final status through the real FastAPI routes."""
    settings = build_settings(samples_dir=samples_dir)
    deps = build_ingest_deps(settings)
    app = create_app()
    app.dependency_overrides[get_deps] = lambda: deps

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://smoke.local",
    ) as client:
        health = await client.get("/ml/ingest/health")
        health.raise_for_status()
        if health.json() != {"status": "UP"}:
            raise RuntimeError(f"unexpected health response: {health.json()!r}")

        response = await client.post(
            "/ml/ingest",
            json={
                "mode": mode,
                "accessToken": "smoke-token-not-persisted",
                "cloudId": "smoke-cloud",
            },
        )
        response.raise_for_status()
        started = response.json()
        job_id = started["jobId"]

        status_response = await client.get(f"/ml/ingest/status/{job_id}")
        status_response.raise_for_status()
        final = status_response.json()

    if final["status"] != "COMPLETED":
        raise RuntimeError(f"ingestion smoke failed: {final!r}")
    if final["processedPages"] <= 0:
        raise RuntimeError(f"ingestion smoke processed no pages: {final!r}")

    return {"started": started, "final": final}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local /ml/ingest smoke with json_fixture + fake adapters.",
    )
    parser.add_argument(
        "--samples-dir",
        default="samples",
        help="Sample fixture directory. Default: samples",
    )
    parser.add_argument(
        "--mode",
        default="full",
        choices=("full",),
        help="Smoke mode. Only full is supported for deterministic local smoke.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    samples_dir = str(Path(args.samples_dir))
    result = asyncio.run(run_smoke(samples_dir=samples_dir, mode=args.mode))
    final = result["final"]
    print("[smoke] /ml/ingest completed")
    print(f"[smoke] jobId={final['jobId']}")
    print(
        "[smoke] pages="
        f"total:{final['totalPages']} "
        f"processed:{final['processedPages']} "
        f"failed:{final['failedPages']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
