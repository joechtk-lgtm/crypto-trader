# Crypto Trader

Institutional-grade paper trading system combining Fear & Greed DCA
with a grid bot for SOL/USDT.

## Overview
Two complementary strategies running simultaneously:
1. **Fear DCA**: 3-step gatekeeper deploys capital only during confirmed
   market capitulation (Fear & Greed < 20 + negative funding rates + positive ETF flows)
2. **Grid Bot**: Captures SOL/USDT price oscillations in the $70-$100 range

## Strategy Design
The 3-step gatekeeper was designed after researching and stress-testing
multiple signal sources. News-based institutional signals were deliberately
excluded after analysis showed 13F filing delays (45 days) make them
unsuitable for tactical DCA timing.

## Tech Stack
- Python + CCXT (OKX) for market data
- alternative.me Fear & Greed API
- Farside Investors ETF flow data (web scraping)
- JSONL event logging
- HTML dashboard (amber terminal aesthetic)

## Capital Allocation
| Bucket | Amount | Purpose |
|--------|--------|---------|
| Grid bot | $500 | 10 levels × $50, SOL/USDT $70-$100 |
| DCA reserve | $450 | Deployed on confirmed extreme fear |
| Buffer | $50 | Never touched |

## Running Locally
```bash
cd crypto_trader
python3 run.py
```

## Example Data
See `examples/` for a simulated 2-month trading history (Jan-Mar 2026)
using real historical price and Fear & Greed data.

## Project Status
Paper trading (live since March 2026). Built as part of USC Marshall MBA
portfolio demonstrating systematic trading system design.

---
*Chayut (Joe) Teeradakorn | USC Marshall MBA 2026*
