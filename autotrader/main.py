from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from autotrader.utils.logger import logger

from autotrader.feeds import calendar_api, features, feeds_mt5, llm_helper, news_api
from autotrader.meta.bandit import build_bandit
from autotrader.meta.drift import DriftDetector
from autotrader.meta.selector import choose_strategy
from autotrader.risk.risk_engine import RiskEngine, load_policy
from autotrader.storage import store
from autotrader.strategies import breakout_m30, dogu_sar, meanrev_m15, trend_m5
from autotrader.wf.walk_forward import WalkForwardRunner

CONFIG_DIR = Path(__file__).resolve().parent / "configs"
LOG_DIR = Path(__file__).resolve().parent / "logs"


def load_json(name: str) -> dict:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(LOG_DIR / "app.log", rotation="1 day")
    logger.info("Starting HANN Autotrader daemon")
    risk_policy = load_policy(load_json("risk_policy.json"))
    broker_cfg = load_json("broker.json")
    learning_cfg = load_json("learning_policy.json")
    news_cfg = load_json("news_sources.json")
    telegram_cfg = load_json("telegram.json")

    store.initialise()
    feed = feeds_mt5.connect(broker_cfg)
    strategies = {
        "trend_M5": trend_m5.get_strategy(),
        "meanrev_M15": meanrev_m15.get_strategy(),
        "breakout_M30": breakout_m30.get_strategy(),
        "dogu_sar_M15": dogu_sar.get_strategy(),
    }
    bandit_state_path = Path(__file__).resolve().parent / "data" / "registry" / "bandit_state.json"
    bandit = build_bandit(learning_cfg["bandit"], list(strategies.keys()), state_path=str(bandit_state_path))
    drift = DriftDetector(delta=learning_cfg["drift_detector"]["delta"])
    risk_engine = RiskEngine(
        risk_policy,
        lot_min=broker_cfg.get("lot_min", risk_policy.lot_min),
        lot_step=broker_cfg.get("lot_step", risk_policy.lot_step),
    )
    wf_runner = WalkForwardRunner(learning_cfg["wf_schedule"])

    logger.info("Daemon initialised; entering loop")
    while True:
        now = datetime.now(timezone.utc)
        account = feed.get_account_info()
        balance = account.get("balance", 0.0)
        equity = account.get("equity", balance)
        latest_equity = store.get_latest_equity()
        dd_pct = latest_equity.dd_pct if latest_equity else 0.0

        if risk_engine.check_daily_dd(dd_pct):
            time.sleep(60)
            continue

        df_map = {tf: feed.get_bars(broker_cfg["symbol"], tf, 250) for tf in broker_cfg["timeframes"]}
        spread = feed.get_spread(broker_cfg["symbol"])
        if not risk_engine.spread_ok(spread):
            time.sleep(15)
            continue

        upcoming = calendar_api.get_upcoming_events()
        news = news_api.get_recent_headlines()
        llm_bias = 0.0
        uncertainty = 0.0
        if news:
            summary = llm_helper.summarize_headline(news[0]["headline"])
            llm_bias = 1.0 if summary["bias"] == "bull_gold" else -1.0 if summary["bias"] == "bear_gold" else 0.0
            uncertainty = 1.0 if summary.get("uncertainty_flag") else 0.0
        news_state = {
            "spread": spread,
            "calendar": upcoming,
            "headlines": news,
            "llm_bias": llm_bias,
            "uncertainty": uncertainty,
            "calendar_surprise_z": upcoming[0].get("surprise_z", 0.0) if upcoming else 0.0,
        }
        if risk_engine.news_blackout(now, upcoming):
            time.sleep(60)
            continue

        candidates = {}
        for name, strat in strategies.items():
            df = df_map.get(strat.timeframe, pd.DataFrame())
            if df.empty:
                continue
            strat.prepare(df)
            sig = strat.signal(df)
            if sig.direction != "flat":
                candidates[name] = {"strategy": strat, "signal": sig, "df": df}

        if not candidates:
            time.sleep(10)
            continue

        primary_tf = next(iter(candidates.values()))["strategy"].timeframe
        ctx_df = df_map[primary_tf]
        context = features.build_context(broker_cfg["symbol"], primary_tf, ctx_df, news_state)
        chosen, lot = choose_strategy(bandit, context, candidates, balance, risk_engine)
        if not chosen:
            time.sleep(5)
            continue

        strat = candidates[chosen]["strategy"]
        signal = candidates[chosen]["signal"]
        sltp = strat.stop_take(candidates[chosen]["df"], risk_policy)
        logger.info("Executing %s direction=%s lot=%.2f", chosen, signal.direction, lot)

        order = {"status": "simulated", "ticket": 0}
        reward = 0.0
        bandit.update(chosen, reward, context)
        bandit.save_state(bandit_state_path)

        if drift.update(reward):
            bandit.apply_decay(learning_cfg["decay"]["half_life_trades"])

        if now.weekday() == 0 and now.hour == 0:
            cand = wf_runner.run_weekly_wf()
            if wf_runner.shadow_compare(cand, 0) == "promote":
                wf_runner.promote_to_prod(cand)

        time.sleep(5)


if __name__ == "__main__":
    main()
