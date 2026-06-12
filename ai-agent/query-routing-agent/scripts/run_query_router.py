"""ai-agent/query-routing-agent/scripts/run_query_router.py 모듈.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from query_routing_agent.scripts.run_query_router import main


if __name__ == "__main__":
    raise SystemExit(main())
