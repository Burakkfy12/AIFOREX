from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from autotrader.utils.logger import logger

from autotrader.feeds import calendar_api, features, feeds_mt5, llm_helper, news_api
from autotrader.exec import broker_mt5
from autotrader.meta.bandit import ThompsonBandit, build_bandit
from autotrader.meta.drift import DriftDetector
from autotrader.meta.selector import choose_strategy
from autotrader.risk.risk_engine import RiskEngine, RiskPolicy, load_policy
from autotrader.storage import store
from autotrader.storage.store import BanditState, EquityLog, TradeLog
from autotrader.strategies import breakout_m30, dogu_sar, meanrev_m15, trend_m5
from autotrader.wf.walk_forward import WalkForwardRunner

try:  # pragma: no cover - optional dependency at runtime
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover
    mt5 = None  # type: ignore

CONFIG_DIR = Path(__file__).resolve().parent / "configs"
DATA_DIR = Path(__file__).resolve().parent / "data" / "registry"
LOG_DIR = Path(__file__).resolve().parent / "logs"


def load_json(name: str) -> dict:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


def _build_strategies() -> Dict[str, object]:
    return {
        "trend_M5": trend_m5.get_strategy(),
        "meanrev_M15": meanrev_m15.get_strategy(),
        "breakout_M30": breakout_m30.get_strategy(),
        "dogu_sar_M15": dogu_sar.get_strategy(),
    }


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(LOG_DIR / "app.log", rotation="1 day")
    logger.info("Starting HANN Autotrader daemon")

    risk_cfg = load_json("risk_policy.json")
    broker_cfg = load_json("broker.json")
    learning_cfg = load_json("learning_policy.json")

    risk_policy: RiskPolicy = load_policy(risk_cfg)
    risk_engine = RiskEngine(risk_policy)

    store.initialise()
    feed = feeds_mt5.connect(broker_cfg)
    broker = broker_mt5.connect(broker_cfg, policy=risk_policy)

    strategies = _build_strategies()
    bandit_state_path = DATA_DIR / "bandit_state.json"
    bandit: ThompsonBandit = build_bandit(learning_cfg["bandit"], list(strategies.keys()), state_path=str(bandit_state_path))
    drift = DriftDetector(delta=learning_cfg["drift_detector"]["delta"])
    wf_runner = WalkForwardRunner(learning_cfg["wf_schedule"], learning_cfg["shadow_deploy"])

    trade_counter = 0

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

        symbol = broker_cfg["symbol"]
        df_map = {tf: feed.get_bars(symbol, tf, 250) for tf in broker_cfg["timeframes"]}
        spread_points = feed.get_spread_points(symbol)
        if not risk_engine.spread_ok(spread_points):
            time.sleep(15)
            continue

        upcoming = calendar_api.get_upcoming_events()
        if risk_engine.news_blackout(now, upcoming):
            time.sleep(60)
            continue

        open_positions = 0
        if mt5 is not None and getattr(feed, "connected", False):  # pragma: no cover - requires MT5 terminal
            try:
                open_positions = mt5.positions_total()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - runtime safeguard
                open_positions = 0
        if not risk_engine.max_positions_ok(open_positions):
            time.sleep(10)
            continue

        headlines = news_api.get_recent_headlines()
        llm_bias = 0.0
        uncertainty = 0.0
        if headlines:
            summary = llm_helper.summarize_headline(headlines[0].get("headline", ""))
            bias = summary.get("bias")
            if bias == "bull_gold":
                llm_bias = 1.0
            elif bias == "bear_gold":
                llm_bias = -1.0
            uncertainty = 1.0 if summary.get("uncertainty_flag") else 0.0
        news_state = {
            "llm_bias": llm_bias,
            "uncertainty": uncertainty,
            "calendar_surprise_z": upcoming[0].get("surprise_z", 0.0) if upcoming else 0.0,
        }

        candidates = {}
        contexts = {}
        for name, strat in strategies.items():
            df = df_map.get(strat.timeframe)
            if df is None or df.empty:
                continue
            strat.prepare(df.copy())
            signal = strat.signal(df.copy())
            if signal.direction == "flat":
                continue
            ctx = features.build_context(symbol, df, spread_points, news_state)
            contexts[name] = ctx
            candidates[name] = {"strategy": strat, "signal": signal, "df": df}

        if not candidates:
            time.sleep(10)
            continue

        chosen, lot = choose_strategy(bandit, contexts, candidates, balance, risk_engine)
        if not chosen:
            time.sleep(5)
            continue

        strat = candidates[chosen]["strategy"]
        signal = candidates[chosen]["signal"]
        df_selected = candidates[chosen]["df"]
        sltp = strat.stop_take(df_selected, risk_policy)

        logger.info("Executing %s direction=%s lot=%.2f", chosen, signal.direction, lot)
        order = broker.place_order(
            symbol,
            signal.direction,
            lot,
            sltp.get("sl"),
            sltp.get("tp"),
            int(risk_policy.max_slippage_points),
        )

        if order.get("status") != "filled":
            logger.debug("Order result: %s", order)

        entry_price = df_selected["close"].iloc[-1]
        exit_price = entry_price
        pnl = 0.0
        reward = 0.0
        atr = contexts[chosen]["atr"]
        if atr:
            reward = pnl / max(atr, 1e-6)
        bandit.update(chosen, reward, contexts[chosen])
        trade_counter += 1
        if trade_counter % 20 == 0:
            bandit.save_state(bandit_state_path)

        store.log_trade(
            TradeLog(
                ts_open=now.isoformat(),
                ts_close=now.isoformat(),
                symbol=symbol,
                timeframe=strat.timeframe,
                strategy=chosen,
                context_json=contexts[chosen],
                params_json=sltp,
                direction=signal.direction,
                lot=lot,
                entry=float(entry_price),
                sl=float(sltp.get("sl", 0.0) or 0.0),
                tp=float(sltp.get("tp", 0.0) or 0.0),
                exit=float(exit_price),
                pnl=pnl,
                pnl_atr=reward,
                slippage=float(risk_policy.max_slippage_points),
            )
        )
        store.log_equity(
            EquityLog(
                ts=now.isoformat(),
                balance=balance,
                equity=equity,
                dd_pct=dd_pct,
            )
        )
        store.save_bandit_state(
            [
                BanditState(
                    ts=now.isoformat(),
                    arm=chosen,
                    reward=reward,
                    context_json=contexts[chosen],
                    alpha=bandit.alpha[chosen],
                    beta=bandit.beta[chosen],
                )
            ]
        )

        if drift.update(reward):
            bandit.apply_decay(learning_cfg["decay"]["half_life_trades"])

        if now.weekday() == 0 and now.hour == 0:
            candidate_id = wf_runner.run_weekly_wf()
            decision = wf_runner.shadow_compare(candidate_id, 0)
            if decision == "promote":
                wf_runner.promote_to_prod(candidate_id)

        time.sleep(5)


if __name__ == "__main__":
    main()
