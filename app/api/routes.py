"""Backward-compatible module alias for query routes."""

from __future__ import annotations

import sys

from app.api import query_routes as _query_routes

sys.modules[__name__] = _query_routes
