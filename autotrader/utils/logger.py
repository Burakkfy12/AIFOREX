"""Provide a shared logger that falls back to the stdlib when loguru is unavailable."""
from __future__ import annotations

import logging

try:  # pragma: no cover - optional dependency
    from loguru import logger as _logger  # type: ignore
except ImportError:  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    _logger = logging.getLogger("autotrader")

logger = _logger
