from __future__ import annotations

from typing import Dict, Tuple

from autotrader.utils.logger import logger

from .bandit import ThompsonBandit


def choose_strategy(
    bandit: ThompsonBandit,
    contexts: Dict[str, Dict],
    candidates: Dict[str, Dict],
    balance: float,
    risk_engine,
) -> Tuple[str, float]:
    if not candidates:
        return "", 0.0
    for arm in candidates.keys():
        bandit.register_arm(arm)
    default_ctx = contexts.get(next(iter(contexts), ""), {})
    chosen = bandit.select_arm(default_ctx)
    if chosen not in candidates:
        logger.debug("Chosen arm %s not in candidates", chosen)
        return "", 0.0
    lot = risk_engine.calc_lot(balance)
    logger.info("Selected arm %s with lot %.2f", chosen, lot)
    return chosen, lot
