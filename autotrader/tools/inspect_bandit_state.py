from __future__ import annotations

from autotrader.storage import store


if __name__ == "__main__":
    state = store.load_bandit_state()
    for row in state:
        print(row)
