from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np


@dataclass
class ArmState:
    alpha: float = 1.0
    beta: float = 1.0
    pulls: int = 0
    reward_sum: float = 0.0


@dataclass
class ContextualBandit:
    algo: str
    prior_alpha: float
    prior_beta: float
    arms: Dict[str, ArmState] = field(default_factory=lambda: defaultdict(ArmState))

    def register_arm(self, arm_name: str) -> None:
        self.arms.setdefault(arm_name, ArmState(self.prior_alpha, self.prior_beta, 0, 0.0))

    def select_arm(self, context: Dict[str, float]) -> str:
        if self.algo == "ucb1":
            return self._ucb1()
        return self._thompson()

    def update(self, arm_name: str, reward: float, context: Dict[str, float]) -> None:
        arm = self.arms.setdefault(arm_name, ArmState(self.prior_alpha, self.prior_beta, 0, 0.0))
        arm.pulls += 1
        arm.reward_sum += reward
        arm.alpha = max(self.prior_alpha, arm.alpha + max(reward, 0))
        arm.beta = max(self.prior_beta, arm.beta + max(-reward, 0))

    def apply_decay(self, half_life_trades: int = 200) -> None:
        decay = math.exp(math.log(0.5) / max(half_life_trades, 1))
        for arm in self.arms.values():
            arm.pulls = int(arm.pulls * decay)
            arm.reward_sum *= decay
            arm.alpha = self.prior_alpha + (arm.alpha - self.prior_alpha) * decay
            arm.beta = self.prior_beta + (arm.beta - self.prior_beta) * decay

    def _thompson(self) -> str:
        samples = {
            arm_name: np.random.beta(max(arm.alpha, 1e-3), max(arm.beta, 1e-3))
            for arm_name, arm in self.arms.items()
        }
        return max(samples, key=samples.get)

    def _ucb1(self) -> str:
        total_pulls = sum(max(arm.pulls, 1) for arm in self.arms.values())
        scores = {}
        for arm_name, arm in self.arms.items():
            mean_reward = arm.reward_sum / max(arm.pulls, 1)
            bonus = math.sqrt(2 * math.log(total_pulls) / max(arm.pulls, 1))
            scores[arm_name] = mean_reward + bonus
        return max(scores, key=scores.get)


def build_bandit(config: Dict[str, float], arms: List[str]) -> ContextualBandit:
    bandit = ContextualBandit(
        algo=config.get("algo", "thompson"),
        prior_alpha=config.get("prior_alpha", 1.0),
        prior_beta=config.get("prior_beta", 1.0),
    )
    for arm in arms:
        bandit.register_arm(arm)
    return bandit
