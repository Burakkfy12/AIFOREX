from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Dict, Iterable, Optional

from autotrader.utils.logger import logger


class ThompsonBandit:
    """Context-free Thompson Sampling bandit with simple persistence."""

    def __init__(
        self,
        arms: Iterable[str],
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
        state_path: Optional[Path] = None,
    ) -> None:
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self.state_path = Path(state_path) if state_path else None
        self.rng = random.Random()
        self.alpha: Dict[str, float] = {}
        self.beta: Dict[str, float] = {}
        self.counts: Dict[str, int] = {}
        for arm in arms:
            self.register_arm(arm)
        if self.state_path:
            self.load_state(self.state_path)

    def register_arm(self, arm: str) -> None:
        if arm not in self.alpha:
            self.alpha[arm] = float(self.prior_alpha)
            self.beta[arm] = float(self.prior_beta)
            self.counts[arm] = 0
            logger.debug("Registered bandit arm %s", arm)

    def select_arm(self, context: Optional[Dict[str, float]] = None) -> str:
        if not self.alpha:
            raise RuntimeError("No arms registered for bandit selection")
        samples = {
            arm: self.rng.betavariate(max(self.alpha[arm], 1e-6), max(self.beta[arm], 1e-6))
            for arm in self.alpha
        }
        chosen = max(samples, key=samples.get)
        logger.debug("Thompson samples %s -> chosen %s", samples, chosen)
        return chosen

    def update(self, arm: str, reward: float, context: Optional[Dict[str, float]] = None) -> None:
        self.register_arm(arm)
        delta = min(1.0, abs(float(reward)))
        if reward >= 0:
            self.alpha[arm] += delta
        else:
            self.beta[arm] += delta
        self.counts[arm] = self.counts.get(arm, 0) + 1
        logger.debug(
            "Updated arm %s -> alpha=%.4f beta=%.4f count=%s",
            arm,
            self.alpha[arm],
            self.beta[arm],
            self.counts[arm],
        )

    def apply_decay(self, half_life_trades: int) -> None:
        if half_life_trades <= 0:
            return
        decay = 0.5 ** (1.0 / half_life_trades)
        for arm in list(self.alpha.keys()):
            self.alpha[arm] = self.prior_alpha + (self.alpha[arm] - self.prior_alpha) * decay
            self.beta[arm] = self.prior_beta + (self.beta[arm] - self.prior_beta) * decay
            self.counts[arm] = int(max(0, math.floor(self.counts.get(arm, 0) * decay)))
            logger.debug(
                "Decayed arm %s -> alpha=%.4f beta=%.4f count=%s",
                arm,
                self.alpha[arm],
                self.beta[arm],
                self.counts[arm],
            )

    def save_state(self, path: Optional[Path] = None) -> None:
        target = Path(path or self.state_path or Path("bandit_state.json"))
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "alpha": self.alpha,
            "beta": self.beta,
            "counts": self.counts,
        }
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Bandit state saved to %s", target)

    def load_state(self, path: Optional[Path] = None) -> None:
        target = Path(path or self.state_path or Path("bandit_state.json"))
        if not target.exists():
            logger.info("Bandit state %s does not exist; starting fresh", target)
            return
        data = json.loads(target.read_text(encoding="utf-8"))
        alpha = data.get("alpha", {})
        beta = data.get("beta", {})
        counts = data.get("counts", {})
        for arm in set(alpha) | set(beta):
            self.alpha[arm] = float(alpha.get(arm, self.prior_alpha))
            self.beta[arm] = float(beta.get(arm, self.prior_beta))
            self.counts[arm] = int(counts.get(arm, 0))
        logger.info("Loaded bandit state from %s with %d arms", target, len(self.alpha))


def build_bandit(config: Dict[str, float], arms: Iterable[str], state_path: Optional[str] = None) -> ThompsonBandit:
    bandit = ThompsonBandit(
        arms=arms,
        prior_alpha=config.get('prior_alpha', 1.0),
        prior_beta=config.get('prior_beta', 1.0),
        state_path=Path(state_path) if state_path else None,
    )
    return bandit
