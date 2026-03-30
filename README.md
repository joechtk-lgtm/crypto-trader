# Crypto Trader

Paper trading system combining a **Fear & Greed DCA gatekeeper** with a
**SOL/USDT grid bot**, designed to deploy capital systematically during
confirmed market capitulation while capturing range-bound oscillations.

## Features

### Three-Step DCA Gatekeeper
A sequential signal filter that must clear all three steps before deploying
capital into BTC and ETH:

1. **Fear & Greed Index** — must be in Extreme Fear (below 20)
2. **Funding Rates** — BTC and ETH perp funding must both be negative
   (indicating bearish leverage sentiment)
3. **ETF Flows** — 7-day rolling Bitcoin ETF net flow must be positive
   (institutional accumulation despite retail fear).
   *Data source migrated from Farside Investors HTML scraping to
   [The Block's JSON API](https://www.theblock.co/) after Farside
   added Cloudflare bot protection.*

Depending on how many steps pass and overall conditions, the gatekeeper
recommends FULL, HALF, ENHANCED, or SKIP for each daily check.

### SOL/USDT Grid Bot
Captures price oscillations across a configurable price range with evenly
spaced buy/sell levels. Tracks round-trip fills, realized PnL, and grid ROI.

### Dashboard
An HTML dashboard with an amber terminal aesthetic, featuring:
- **Grid stats summary** — total fills, realized PnL, ROI, and active level count
- **Grid visualization** — ladder view of all levels with fill status
  and per-level PnL
- **Grid range indicator** — visual indicator of current price within the grid range
- **Capital allocation** — real-time breakdown of grid, DCA reserve,
  deployed holdings, and buffer
- **Gatekeeper signal** — step-by-step display of the latest three-step check
- **Gatekeeper history** — table of the last 14 daily checks with all scores
- **Portfolio chart** — daily portfolio value over time (canvas-rendered)
- **Activity log** — filterable, paginated event stream of all system actions
- **DCA funnel** — conversion metrics from checks → step 2 → trades fired

### CLI Menu
Interactive terminal menu for running signal checks, executing DCA trades
(dry-run or live paper), checking grid status, viewing portfolio, and
launching/stopping the dashboard server.

## Tech Stack

- **Python** — core trading logic, CLI interface
- **OKX public API** (via CCXT) — price data, funding rates
- **alternative.me API** — Fear & Greed Index
- **The Block API** — Bitcoin spot ETF net flow data (JSON API)
- **JSONL event logging** — append-only structured log for all system events
- **HTML / CSS / JS dashboard** — single-page dashboard served locally

## Running Locally

```bash
# Clone and install
git clone <repo-url>
cd crypto_trader
pip3 install -r requirements.txt

# Run the CLI
python3 run.py
```

The CLI menu options:
1. Check institutional signal (3-step gatekeeper)
2. Run Fear DCA check (dry run)
3. Run Fear DCA (live paper trade)
4. Check grid bot status
5. View portfolio summary
6. Open / close dashboard

The dashboard starts a local HTTP server and opens in your browser.

## Project Structure

```
config.py                 # Strategy parameters and thresholds
run.py                    # CLI entry point with dashboard server management
data/fear_greed.py        # Fear & Greed API client
data/fetcher.py           # OKX market data (ticker, OHLCV, funding rates)
signals/institutional.py  # 3-step gatekeeper logic
dca/fear_dca.py           # DCA execution engine
grid_bot/engine.py        # Grid bot initialization, fill checking, status
logs/logger.py            # Structured JSONL logger
dashboard/                # HTML/CSS/JS dashboard
examples/                 # Synthetic 2-month trading history for demo
```

## Example Data

The `examples/` directory contains a generated 2-month trading history
(Jan–Mar 2026) using real historical Fear & Greed and price data, useful
for testing the dashboard without live trading data.

## Project Status

Paper trading system. Built as part of portfolio
demonstrating systematic trading system design.


