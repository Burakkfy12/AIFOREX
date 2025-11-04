from __future__ import annotations

from typing import Dict, List, Tuple

from loguru import logger

from .bandit import ContextualBandit


def choose_strategy(
    bandit: ContextualBandit,
    context: Dict[str, float],
    candidates: Dict[str, Dict],
    balance: float,
    risk_engine,
) -> Tuple[str, float]:
    if not candidates:
        return "", 0.0
    for arm in candidates.keys():
        bandit.register_arm(arm)
    chosen = bandit.select_arm(context)
    if chosen not in candidates:
        logger.debug("Chosen arm %s not in candidates", chosen)
        return "", 0.0
    lot = risk_engine.calc_lot(balance)
    logger.info("Selected arm %s with lot %.2f", chosen, lot)
    return chosen, lot
