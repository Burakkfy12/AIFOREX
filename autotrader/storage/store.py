"""Lightweight storage helper for the HANN Autotrader system."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from autotrader.utils.logger import logger

DB_FILE = Path(__file__).resolve().parent / "autotrader.db"
SCHEMA_FILE = Path(__file__).resolve().parent / "schemas.sql"


@dataclass
class TradeLog:
    ts_open: str
    ts_close: str
    symbol: str
    timeframe: str
    strategy: str
    context_json: Dict[str, Any]
    params_json: Dict[str, Any]
    direction: str
    lot: float
    entry: float
    sl: float
    tp: float
    exit: float
    pnl: float
    pnl_atr: float
    slippage: float


@dataclass
class EquityLog:
    ts: str
    balance: float
    equity: float
    dd_pct: float


@dataclass
class BanditState:
    ts: str
    arm: str
    reward: float
    context_json: Dict[str, Any]
    alpha: float
    beta: float


@dataclass
class WFEntry:
    id: int
    ts: str
    window_train: str
    window_test: str
    config_json: Dict[str, Any]
    metrics_json: Dict[str, Any]
    status: str


def initialise() -> None:
    """Initialise the SQLite database if required."""
    logger.debug("Initialising storage layer at %s", DB_FILE)
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with connection() as conn, SCHEMA_FILE.open("r", encoding="utf-8") as fh:
        conn.executescript(fh.read())
    logger.info("Database initialised with schemas from %s", SCHEMA_FILE)


@contextmanager
def connection():
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Database error, transaction rolled back")
        raise
    finally:
        conn.close()


def log_trade(trade: TradeLog) -> None:
    payload = trade.__dict__.copy()
    payload["context_json"] = json.dumps(trade.context_json)
    payload["params_json"] = json.dumps(trade.params_json)
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO trades (
                ts_open, ts_close, symbol, timeframe, strategy,
                context_json, params_json, direction, lot, entry, sl, tp,
                exit, pnl, pnl_atr, slippage
            ) VALUES (:ts_open, :ts_close, :symbol, :timeframe, :strategy,
                :context_json, :params_json, :direction, :lot, :entry, :sl, :tp,
                :exit, :pnl, :pnl_atr, :slippage)
            """,
            payload,
        )
    logger.debug("Logged trade for %s/%s", trade.symbol, trade.strategy)


def log_equity(log: EquityLog) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO equity_curve (ts, balance, equity, dd_pct)
            VALUES (:ts, :balance, :equity, :dd_pct)
            """,
            log.__dict__,
        )
    logger.debug("Logged equity snapshot at %s", log.ts)


def save_bandit_state(state: Iterable[BanditState]) -> None:
    rows = [
        (
            s.ts,
            s.arm,
            s.reward,
            json.dumps(s.context_json),
            s.alpha,
            s.beta,
        )
        for s in state
    ]
    with connection() as conn:
        conn.executemany(
            """
            INSERT INTO bandit_stats (ts, arm, reward, context_json, alpha, beta)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    logger.info("Persisted %d bandit state rows", len(rows))


def load_bandit_state(limit: int = 200) -> list[BanditState]:
    with connection() as conn:
        cur = conn.execute(
            "SELECT ts, arm, reward, context_json, alpha, beta FROM bandit_stats ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        results = [
            BanditState(
                ts=row[0],
                arm=row[1],
                reward=row[2],
                context_json=json.loads(row[3] or "{}"),
                alpha=row[4],
                beta=row[5],
            )
            for row in cur.fetchall()
        ]
    logger.debug("Loaded %d bandit state rows", len(results))
    return results


def register_wf(ts: str, window_train: str, window_test: str, config: Dict[str, Any], metrics: Dict[str, Any], status: str) -> int:
    with connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO wf_registry (ts, window_train, window_test, config_json, metrics_json, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ts, window_train, window_test, json.dumps(config), json.dumps(metrics), status),
        )
        wf_id = cur.lastrowid
    logger.info("Registered WF entry %s with status %s", wf_id, status)
    return wf_id


def update_wf_status(wf_id: int, status: str) -> None:
    with connection() as conn:
        conn.execute("UPDATE wf_registry SET status=? WHERE id=?", (status, wf_id))
    logger.info("Updated WF %s to status %s", wf_id, status)


def get_wf_entry(wf_id: int) -> Optional[WFEntry]:
    with connection() as conn:
        cur = conn.execute("SELECT id, ts, window_train, window_test, config_json, metrics_json, status FROM wf_registry WHERE id=?", (wf_id,))
        row = cur.fetchone()
    if not row:
        return None
    return WFEntry(
        id=row[0],
        ts=row[1],
        window_train=row[2],
        window_test=row[3],
        config_json=json.loads(row[4] or '{}'),
        metrics_json=json.loads(row[5] or '{}'),
        status=row[6],
    )


def get_latest_equity() -> Optional[EquityLog]:
    with connection() as conn:
        cur = conn.execute("SELECT ts, balance, equity, dd_pct FROM equity_curve ORDER BY ts DESC LIMIT 1")
        row = cur.fetchone()
    if not row:
        return None
    return EquityLog(ts=row[0], balance=row[1], equity=row[2], dd_pct=row[3])
