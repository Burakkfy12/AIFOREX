from __future__ import annotations

from autotrader.meta.bandit import ThompsonBandit


def test_bandit_prefers_profitable_arm(tmp_path):
    state_file = tmp_path / "bandit.json"
    bandit = ThompsonBandit(["trend", "meanrev"], state_path=state_file)

    for _ in range(30):
        bandit.update("trend", reward=1.0, context={})
        bandit.update("meanrev", reward=-0.5, context={})

    selections = {"trend": 0, "meanrev": 0}
    for _ in range(200):
        arm = bandit.select_arm({})
        selections[arm] += 1

    assert selections["trend"] > selections["meanrev"]

    bandit.save_state(state_file)
    restored = ThompsonBandit([], state_path=state_file)

    assert restored.alpha["trend"] >= bandit.alpha["trend"] - 1e-6
    assert restored.beta["meanrev"] >= bandit.beta["meanrev"] - 1e-6
