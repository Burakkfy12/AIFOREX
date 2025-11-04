from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional

from autotrader.utils.logger import logger


@dataclass
class ArmState:
    alpha: float
    beta: float
    pulls: int = 0
    reward_sum: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "pulls": self.pulls,
            "reward_sum": self.reward_sum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "ArmState":
        return cls(
            alpha=float(data.get("alpha", 1.0)),
            beta=float(data.get("beta", 1.0)),
            pulls=int(data.get("pulls", 0)),
            reward_sum=float(data.get("reward_sum", 0.0)),
        )


@dataclass
class ContextualBandit:
    algo: str
    prior_alpha: float
    prior_beta: float
    state_path: Optional[Path] = None
    arms: Dict[str, ArmState] = field(default_factory=dict)
    rng: random.Random = field(default_factory=random.Random)

    def register_arm(self, arm_name: str) -> None:
        if arm_name not in self.arms:
            self.arms[arm_name] = ArmState(self.prior_alpha, self.prior_beta)
            logger.debug("Registered new arm %s", arm_name)

    def select_arm(self, context: Dict[str, float]) -> str:
        if not self.arms:
            raise RuntimeError("No arms registered for bandit selection")
        if self.algo == "ucb1":
            return self._ucb1()
        return self._thompson()

    def update(self, arm_name: str, reward: float, context: Dict[str, float]) -> None:
        self.register_arm(arm_name)
        arm = self.arms[arm_name]
        arm.pulls += 1
        arm.reward_sum += reward
        arm.alpha = max(self.prior_alpha, arm.alpha + max(reward, 0.0))
        arm.beta = max(self.prior_beta, arm.beta + max(-reward, 0.0))
        logger.debug("Updated arm %s -> alpha=%.4f beta=%.4f pulls=%s", arm_name, arm.alpha, arm.beta, arm.pulls)

    def apply_decay(self, half_life_trades: int = 200) -> None:
        if half_life_trades <= 0:
            return
        decay = math.exp(math.log(0.5) / half_life_trades)
        for arm_name, arm in self.arms.items():
            arm.pulls = max(1, int(arm.pulls * decay))
            arm.reward_sum *= decay
            arm.alpha = self.prior_alpha + (arm.alpha - self.prior_alpha) * decay
            arm.beta = self.prior_beta + (arm.beta - self.prior_beta) * decay
            logger.debug("Decayed arm %s -> alpha=%.4f beta=%.4f pulls=%s", arm_name, arm.alpha, arm.beta, arm.pulls)

    def save_state(self, path: Optional[Path] = None) -> None:
        target = Path(path or self.state_path or Path("bandit_state.json"))
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: arm.to_dict() for name, arm in self.arms.items()}
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Bandit state saved to %s", target)

    def load_state(self, path: Optional[Path] = None) -> None:
        target = Path(path or self.state_path or Path("bandit_state.json"))
        if not target.exists():
            logger.warning("Bandit state %s does not exist; starting fresh", target)
            return
        data = json.loads(target.read_text(encoding="utf-8"))
        self.arms = {name: ArmState.from_dict(values) for name, values in data.items()}
        logger.info("Loaded bandit state from %s with %d arms", target, len(self.arms))

    # Thompson Sampling implementation
    def _thompson(self) -> str:
        samples = {
            arm_name: self.rng.betavariate(max(arm.alpha, 1e-3), max(arm.beta, 1e-3))
            for arm_name, arm in self.arms.items()
        }
        chosen = max(samples, key=samples.get)
        logger.debug("Thompson samples %s -> chosen %s", samples, chosen)
        return chosen

    # UCB1 implementation
    def _ucb1(self) -> str:
        total_pulls = sum(max(arm.pulls, 1) for arm in self.arms.values())
        scores = {}
        for arm_name, arm in self.arms.items():
            mean_reward = arm.reward_sum / max(arm.pulls, 1)
            bonus = math.sqrt(2 * math.log(total_pulls) / max(arm.pulls, 1))
            scores[arm_name] = mean_reward + bonus
        chosen = max(scores, key=scores.get)
        logger.debug("UCB1 scores %s -> chosen %s", scores, chosen)
        return chosen


def build_bandit(config: Dict[str, float], arms: Iterable[str], state_path: Optional[str] = None) -> ContextualBandit:
    bandit = ContextualBandit(
        algo=config.get("algo", "thompson"),
        prior_alpha=config.get("prior_alpha", 1.0),
        prior_beta=config.get("prior_beta", 1.0),
        state_path=Path(state_path) if state_path else None,
    )
    if bandit.state_path:
        bandit.load_state()
    for arm in arms:
        bandit.register_arm(arm)
    return bandit
