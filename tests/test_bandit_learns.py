from __future__ import annotations

from autotrader.meta.bandit import ContextualBandit


def test_bandit_prefers_profitable_arm(tmp_path):
    import random

    rng = random.Random(123)
    state_file = tmp_path / "bandit.json"
    bandit = ContextualBandit(algo="thompson", prior_alpha=1.0, prior_beta=1.0, state_path=state_file, rng=rng)
    bandit.register_arm("trend")
    bandit.register_arm("meanrev")

    for _ in range(30):
        bandit.update("trend", reward=1.0, context={})
        bandit.update("meanrev", reward=-0.5, context={})

    selections = {"trend": 0, "meanrev": 0}
    for _ in range(200):
        arm = bandit.select_arm(context={})
        selections[arm] += 1

    assert selections["trend"] > selections["meanrev"] * 2

    bandit.save_state()
    restored = ContextualBandit(algo="thompson", prior_alpha=1.0, prior_beta=1.0, state_path=state_file, rng=random.Random(456))
    restored.load_state()

    assert restored.arms["trend"].alpha >= bandit.arms["trend"].alpha - 1e-6
    assert restored.arms["meanrev"].beta >= bandit.arms["meanrev"].beta - 1e-6
