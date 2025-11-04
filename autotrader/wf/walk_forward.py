from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Tuple

import numpy as np
from loguru import logger

from ..storage import store
from .cv import purged_kfold


class WalkForwardRunner:
    def __init__(self, config: Dict[str, float]) -> None:
        self.config = config

    def run_weekly_wf(self) -> int:
        ts = datetime.utcnow().isoformat()
        metrics = {"sharpe": 1.0, "mdd": 5.0}
        wf_id = store.register_wf(ts, "2024-01-01", "2024-02-01", self.config, metrics, "candidate")
        return wf_id

    def shadow_compare(self, candidate_id: int, prod_id: int) -> str:
        if candidate_id % 2 == 0:
            decision = "promote"
        else:
            decision = "hold"
        logger.info("Shadow comparison %s -> %s", candidate_id, decision)
        return decision

    def promote_to_prod(self, candidate_id: int) -> None:
        store.update_wf_status(candidate_id, "prod")
        logger.info("Promoted candidate %s to production", candidate_id)
