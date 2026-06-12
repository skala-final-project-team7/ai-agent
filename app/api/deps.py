"""Backward-compatible module alias for query dependency wiring.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from __future__ import annotations

import sys

from app.api import query_deps as _query_deps

sys.modules[__name__] = _query_deps
