# HANN Autotrader XAUUSD

This repository contains the Python service layer for the HANN Autotrader system. The project orchestrates MetaTrader 5 connectivity, strategy execution, contextual bandit selection, risk controls, walk-forward optimisation, and monitoring utilities for trading XAUUSD.

## Key Components
- **configs/** – JSON configuration files for risk, learning, broker, messaging, and optional LLM settings.
- **feeds/** – Interfaces for market data, economic calendars, news feeds, and derived features.
- **strategies/** – Strategy implementations built on a common base class.
- **meta/** – Contextual bandit selector and drift detection utilities.
- **risk/** – Risk-engine guardrails for spread, news blackout, and position sizing.
- **exec/** – Broker execution adapter for MT5.
- **storage/** – Lightweight storage layer with SQLite schemas and helpers.
- **monitor/** – Reporting and messaging services.
- **wf/** – Walk-forward optimisation orchestration.
- **tools/** – Helper scripts for simulations and data inspection.
- **main.py** – Live trading daemon loop.
- **backtest.py** – Backtesting entry-point with purged CV and regime reports.

Refer to `configs/*.json` for sample configuration templates.
