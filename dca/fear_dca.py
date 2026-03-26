import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime, timezone

from config import DCA_AMOUNT_FULL, DCA_AMOUNT_HALF, DCA_AMOUNT_ENHANCED, DCA_ALLOCATION
from data.fetcher import get_ticker
from logs.logger import CryptoLogger
from signals.institutional import run_signal_check

PORTFOLIO_PATH = "data/crypto_portfolio.json"
logger = CryptoLogger()


def _load_portfolio():
    with open(PORTFOLIO_PATH, "r") as f:
        return json.load(f)


def _save_portfolio(portfolio):
    with open(PORTFOLIO_PATH, "w") as f:
        json.dump(portfolio, f, indent=2)


def run_dca_check(dry_run=False):
    signal = run_signal_check()

    if signal["action"] == "SKIP":
        print(f"DCA skipped: {signal['reason']}")
        print("⏭  SIGNAL: SKIP — Conditions not met. Check again tomorrow.")
        print()
        return

    if signal["action"] == "ENHANCED":
        dca_amount = DCA_AMOUNT_ENHANCED
    elif signal["action"] == "FULL":
        dca_amount = DCA_AMOUNT_FULL
    else:
        dca_amount = DCA_AMOUNT_HALF

    portfolio = _load_portfolio()

    # Guard: ensure DCA reserve has enough capital
    if portfolio["dca_reserve"] < dca_amount:
        print(f"DCA reserve depleted — need ${dca_amount}, have ${portfolio['dca_reserve']:.2f}")
        logger.log_event("CRYPTO_DCA_SKIPPED", {
            "reason": "DCA reserve depleted",
            "dca_reserve": portfolio["dca_reserve"],
            "dca_amount": dca_amount,
        })
        return

    symbols = {coin: f"{coin}/USDT" for coin in DCA_ALLOCATION}
    prices = {}
    for coin, sym in symbols.items():
        ticker = get_ticker(sym)
        if ticker:
            prices[coin] = ticker["last"]
        else:
            print(f"  WARNING: Could not fetch price for {sym}")

    print(f"\n--- Fear DCA {'(DRY RUN) ' if dry_run else ''}---")
    print(f"  Signal : {signal['action']}")
    print(f"  Total  : ${dca_amount}")
    print(f"  {'Coin':<5} {'Alloc':>6} {'USD':>7} {'Price':>12} {'Units':>12}")
    print(f"  {'-'*50}")

    for coin, allocation in DCA_ALLOCATION.items():
        usd_amount = round(dca_amount * allocation, 2)
        price = prices.get(coin)
        if price is None:
            print(f"  {coin:<5} {allocation*100:>5.0f}% ${usd_amount:>6.2f}  price unavailable")
            continue

        units = usd_amount / price
        print(f"  {coin:<5} {allocation*100:>5.0f}% ${usd_amount:>6.2f}  ${price:>10.2f}  {units:>12.6f}")

        if not dry_run:
            if portfolio["dca_reserve"] >= usd_amount:
                portfolio["dca_reserve"] = round(portfolio["dca_reserve"] - usd_amount, 4)
                portfolio["holdings"][coin] = round(portfolio["holdings"].get(coin, 0) + units, 8)
                trade = {
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "symbol": coin,
                    "usd_amount": usd_amount,
                    "price": price,
                    "units_bought": units,
                    "signal": signal["action"],
                }
                portfolio["trades"].append(trade)
                logger.log_event("CRYPTO_DCA_BUY", {
                    "symbol": coin,
                    "usd_amount": usd_amount,
                    "price": price,
                    "units_bought": units,
                    "signal": signal["action"],
                })
            else:
                print(f"  WARNING: Not enough DCA reserve for {coin} (need ${usd_amount}, have ${portfolio['dca_reserve']:.2f})")

    if not dry_run:
        _save_portfolio(portfolio)
        print(f"\n  DCA reserve remaining: ${portfolio['dca_reserve']:.2f}")

    print("--------------------------------\n")

    if signal["action"] == "ENHANCED":
        print("🚨 SIGNAL: ENHANCED DCA ($75) — F&G below 10, maximum fear.")
        print("   Run option 3 to execute. Split: BTC $52.50 / ETH $22.50")
    elif signal["action"] == "FULL":
        print("✅ SIGNAL: FULL DCA ($50) — Run option 3 to execute")
        print("   Split: BTC $35 / ETH $15")
    elif signal["action"] == "HALF":
        print("⚠️  SIGNAL: HALF DCA ($25) — Run option 3 to execute")
        print("   Split: BTC $17.50 / ETH $7.50")
    print()
