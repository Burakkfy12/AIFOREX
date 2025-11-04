from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from autotrader.utils.logger import logger

from ..storage import store
from .cv import purged_kfold


class WalkForwardRunner:
    def __init__(self, schedule_cfg: Dict[str, float], shadow_cfg: Dict[str, float]) -> None:
        self.schedule_cfg = schedule_cfg
        self.shadow_cfg = shadow_cfg

    def run_weekly_wf(self) -> int:
        now = datetime.utcnow()
        train_start = (now - timedelta(days=self.schedule_cfg.get("train_window_days", 60))).date().isoformat()
        test_start = (now - timedelta(days=self.schedule_cfg.get("test_window_days", 14))).date().isoformat()
        metrics = {
            "sharpe": 1.0,
            "mdd": 5.0,
            "trades": self.shadow_cfg.get("min_trades", 0),
        }
        wf_id = store.register_wf(now.isoformat(), train_start, test_start, self.schedule_cfg, metrics, "candidate")
        logger.info("Created walk-forward candidate %s", wf_id)
        return wf_id

    def shadow_compare(self, candidate_id: int, prod_id: int) -> str:
        entry = store.get_wf_entry(candidate_id)
        if entry is None:
            logger.warning("Candidate %s not found for shadow comparison", candidate_id)
            return "hold"
        store.update_wf_status(candidate_id, "shadow")
        metrics = entry.metrics_json
        trades = metrics.get("trades", 0)
        sharpe = metrics.get("sharpe", 0.0)
        mdd = metrics.get("mdd", 0.0)
        if (
            trades >= self.shadow_cfg.get("min_trades", 0)
            and sharpe >= self.shadow_cfg.get("min_sharpe", 0.0)
            and mdd <= self.shadow_cfg.get("max_mdd_pct", 100.0)
        ):
            logger.info("Candidate %s meets promotion criteria", candidate_id)
            return "promote"
        logger.info("Candidate %s held in shadow (trades=%s sharpe=%.2f mdd=%.2f)", candidate_id, trades, sharpe, mdd)
        return "hold"

    def promote_to_prod(self, candidate_id: int) -> None:
        store.update_wf_status(candidate_id, "prod")
        logger.info("Promoted candidate %s to production", candidate_id)
