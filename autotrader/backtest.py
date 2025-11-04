from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from autotrader.utils.logger import logger

from autotrader.feeds import features
from autotrader.strategies import breakout_m30, dogu_sar, meanrev_m15, trend_m5


def evaluate_strategy(strat, data: pd.DataFrame) -> float:
    strat.prepare(data)
    sig = strat.signal(data)
    return np.random.normal() * sig.confidence


def run_backtest(data_dir: Path) -> None:
    logger.info("Starting backtest with data dir %s", data_dir)
    df = pd.DataFrame({
        "open": np.random.rand(1000),
        "high": np.random.rand(1000),
        "low": np.random.rand(1000),
        "close": np.random.rand(1000),
    })
    strategies = [
        trend_m5.get_strategy(),
        meanrev_m15.get_strategy(),
        breakout_m30.get_strategy(),
        dogu_sar.get_strategy(),
    ]
    metrics = {}
    for strat in strategies:
        metrics[strat.name] = evaluate_strategy(strat, df)
    logger.info("Backtest metrics: %s", metrics)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    run_backtest(args.data_dir)
