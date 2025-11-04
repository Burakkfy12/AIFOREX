CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY,
  ts_open TEXT, ts_close TEXT,
  symbol TEXT, timeframe TEXT, strategy TEXT,
  context_json TEXT, params_json TEXT,
  direction TEXT, lot REAL,
  entry REAL, sl REAL, tp REAL,
  exit REAL, pnl REAL, pnl_atr REAL, slippage REAL
);

CREATE TABLE IF NOT EXISTS equity_curve (
  ts TEXT PRIMARY KEY,
  balance REAL, equity REAL, dd_pct REAL
);

CREATE TABLE IF NOT EXISTS bandit_stats (
  ts TEXT,
  arm TEXT,
  reward REAL,
  context_json TEXT,
  alpha REAL, beta REAL
);

CREATE TABLE IF NOT EXISTS wf_registry (
  id INTEGER PRIMARY KEY,
  ts TEXT, window_train TEXT, window_test TEXT,
  config_json TEXT, metrics_json TEXT, status TEXT
);

CREATE TABLE IF NOT EXISTS news_events (
  ts TEXT, source TEXT, event TEXT,
  sentiment TEXT, confidence REAL, uncertainty INTEGER
);
