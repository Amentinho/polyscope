# Polyscope

AI-powered Polymarket analyst and paper trader. Ingests global news, uses Claude to find mispriced prediction markets, and simulates trades in paper mode.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and optionally NEWSAPI_KEY
```

## Usage

```bash
# Scan news + markets, show opportunities
python main.py scan

# Scan and auto-open paper positions on top opportunities
python main.py scan --trade

# Adjust thresholds
python main.py scan --min-edge 0.08 --min-liquidity 10000 --trade

# View paper portfolio
python main.py portfolio

# Close a position after it resolves
python main.py close p_0001 1.0 --won
python main.py close p_0002 0.0 --lost
```

## Architecture

```
ingester/sources.py      — RSS + NewsAPI ingestion
polymarket/client.py     — Polymarket Gamma/CLOB API (read-only)
analyst/analyst.py       — Claude triage (Haiku) + deep analysis (Opus)
trader/paper_trader.py   — Paper trading ledger + Kelly sizing
dashboard/display.py     — Rich terminal UI
main.py                  — CLI entry point
```

## Paper Trading

All positions are simulated. No real funds are used unless you configure a `POLYMARKET_PRIVATE_KEY` in `.env` (live trading — not implemented yet).
