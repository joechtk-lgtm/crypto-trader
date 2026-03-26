"""
examples/generate_examples.py
Generates 59 days of simulated crypto trader history (Jan 13 - Mar 12, 2026)
using real historical price data and Fear & Greed values.

Grid bot runs on SOL/USDT; DCA fires on extreme fear conditions.
"""

import sys
import os
import json
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ccxt
import requests

from config import (
    GRID_LOWER, GRID_UPPER, GRID_LEVELS, GRID_CAPITAL_USD,
    DCA_AMOUNT_FULL, DCA_AMOUNT_HALF, DCA_AMOUNT_ENHANCED,
    DCA_ALLOCATION, DCA_RESERVE_USD,
)

# ── Configuration ────────────────────────────────────────────────────────────

START_DATE = datetime(2026, 1, 13)
NUM_DAYS = 59
LEVEL_CAPITAL = GRID_CAPITAL_USD / GRID_LEVELS  # $50 per level
SEED = 42

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(OUTPUT_DIR, "trading_example.jsonl")
PORTFOLIO_PATH = os.path.join(OUTPUT_DIR, "portfolio_example.json")
GRID_PATH = os.path.join(OUTPUT_DIR, "grid_example.json")


# ── Data Fetching ────────────────────────────────────────────────────────────

def fetch_ohlcv(symbol: str, days: int = 90) -> list:
    """Fetch daily OHLCV from OKX via ccxt."""
    exchange = ccxt.okx({"enableRateLimit": True})
    since = exchange.parse8601((START_DATE - timedelta(days=5)).strftime("%Y-%m-%dT00:00:00Z"))
    all_data = []
    print(f"  Fetching {symbol}...", end=" ")
    try:
        data = exchange.fetch_ohlcv(symbol, "1d", since=since, limit=days + 10)
        all_data = data
        print(f"{len(all_data)} candles")
    except Exception as e:
        print(f"FAILED: {e}")
    return all_data


def fetch_fear_greed() -> dict:
    """Fetch historical Fear & Greed data. Returns {date_str: value}."""
    print("  Fetching Fear & Greed index...", end=" ")
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=120&format=json", timeout=15)
        resp.raise_for_status()
        data = resp.json()["data"]
        result = {}
        for item in data:
            ts = int(item["timestamp"])
            date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            result[date_str] = int(item["value"])
        print(f"{len(result)} days")
        return result
    except Exception as e:
        print(f"FAILED: {e}")
        return {}


def build_price_map(ohlcv_data: list) -> dict:
    """Convert OHLCV list to {date_str: close_price}."""
    result = {}
    for candle in ohlcv_data:
        ts_ms = candle[0]
        close = candle[4]
        date_str = datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")
        result[date_str] = close
    return result


# ── Event Writer ─────────────────────────────────────────────────────────────

def write_event(f, event_type: str, ts: str, data: dict):
    entry = {"timestamp": ts, "event": event_type, "data": data}
    f.write(json.dumps(entry, default=str) + "\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    rng = random.Random(SEED)

    print("=" * 60)
    print("  Crypto Trader — Example Data Generator")
    print(f"  Period: {START_DATE.strftime('%Y-%m-%d')} to "
          f"{(START_DATE + timedelta(days=NUM_DAYS-1)).strftime('%Y-%m-%d')}")
    print("=" * 60)

    # Phase 1: Fetch data
    print("\nPhase 1: Fetching historical data...\n")
    sol_ohlcv = fetch_ohlcv("SOL/USDT", days=NUM_DAYS + 10)
    btc_ohlcv = fetch_ohlcv("BTC/USDT", days=NUM_DAYS + 10)
    eth_ohlcv = fetch_ohlcv("ETH/USDT", days=NUM_DAYS + 10)
    fear_greed = fetch_fear_greed()

    sol_prices = build_price_map(sol_ohlcv)
    btc_prices = build_price_map(btc_ohlcv)
    eth_prices = build_price_map(eth_ohlcv)

    if not sol_prices or not btc_prices or not eth_prices:
        print("\nERROR: Could not fetch sufficient price data. Aborting.")
        return

    # Phase 2: Initialize state
    print(f"\nPhase 2: Simulating {NUM_DAYS} days...\n")

    # Grid state
    step = (GRID_UPPER - GRID_LOWER) / (GRID_LEVELS - 1)
    grid_levels = []
    for i in range(GRID_LEVELS):
        price = round(GRID_LOWER + i * step, 4)
        grid_levels.append({
            "price": price,
            "buy_filled": False,
            "sell_filled": False,
            "units": 0.0,
        })

    grid = {
        "active": True,
        "levels": grid_levels,
        "previous_price": None,
        "pnl_usd": 0.0,
        "consecutive_below_floor": 0,
    }

    # DCA portfolio
    portfolio = {
        "dca_reserve": DCA_RESERVE_USD,
        "grid_capital": GRID_CAPITAL_USD,
        "buffer": 50.0,
        "holdings": {"BTC": 0.0, "ETH": 0.0},
        "trades": [],
    }

    # Counters
    grid_buys = 0
    grid_sells = 0
    dca_triggers = 0
    total_grid_pnl = 0.0

    log_file = open(LOG_PATH, "w")

    prev_sol_price = None

    for day_idx in range(NUM_DAYS):
        current_date = START_DATE + timedelta(days=day_idx)
        date_str = current_date.strftime("%Y-%m-%d")
        ts = current_date.replace(hour=12, minute=0, tzinfo=timezone.utc).isoformat()

        sol_price = sol_prices.get(date_str)
        btc_price = btc_prices.get(date_str)
        eth_price = eth_prices.get(date_str)
        fg_value = fear_greed.get(date_str)

        # Skip if no SOL price (weekend/missing)
        if sol_price is None:
            continue

        # ── Gatekeeper Signal Check ──────────────────────────────────────

        # Step 1: Fear & Greed
        if fg_value is not None and fg_value < 20:
            step1_pass = True
        else:
            step1_pass = False

        # Step 2: Funding rates (simulated)
        if fg_value is not None:
            if fg_value < 15:
                btc_funding = -0.001 * rng.uniform(0.5, 2.0) if rng.random() < 0.7 else 0.0005
                eth_funding = -0.001 * rng.uniform(0.5, 2.0) if rng.random() < 0.7 else 0.0003
            elif fg_value < 25:
                btc_funding = -0.0005 * rng.uniform(0.5, 1.5) if rng.random() < 0.4 else 0.0003
                eth_funding = 0.0002 * rng.uniform(0.5, 1.5) if rng.random() < 0.6 else -0.0004
            else:
                btc_funding = 0.0003 * rng.uniform(0.5, 2.0)
                eth_funding = 0.0002 * rng.uniform(0.5, 2.0)
        else:
            btc_funding = 0.0001
            eth_funding = 0.0001

        step2_pass = btc_funding < 0 and eth_funding < 0

        # Step 3: ETF flow (simulated)
        etf_flow = None
        if step1_pass and step2_pass:
            if fg_value < 15:
                etf_flow = 150.0
            else:
                etf_flow = 150.0 if rng.random() < 0.5 else -50.0

        # Determine action
        gatekeeper_action = "SKIP"
        gatekeeper_reason = ""
        step_reached = 1

        if not step1_pass:
            fg_display = fg_value if fg_value is not None else "N/A"
            gatekeeper_reason = f"Fear & Greed not extreme ({fg_display})"
            step_reached = 1
        elif not step2_pass:
            gatekeeper_reason = "Funding rates not both negative"
            step_reached = 2
        elif etf_flow is not None and etf_flow > 0:
            if fg_value < 10:
                gatekeeper_action = "ENHANCED"
                gatekeeper_reason = f"Extreme fear ({fg_value}) + negative funding + positive ETF"
            else:
                gatekeeper_action = "FULL"
                gatekeeper_reason = f"Fear ({fg_value}) + negative funding + positive ETF ${etf_flow:.0f}M"
            step_reached = 3
        elif etf_flow is not None and etf_flow >= -200:
            gatekeeper_action = "HALF"
            gatekeeper_reason = f"Fear ({fg_value}) + negative funding + ETF slightly negative"
            step_reached = 3
        else:
            gatekeeper_reason = "ETF flow too negative"
            step_reached = 3

        write_event(log_file, "CRYPTO_INSTITUTIONAL_SIGNAL", ts, {
            "action": gatekeeper_action,
            "reason": gatekeeper_reason,
            "step_reached": step_reached,
            "scores": {
                "fear_greed": fg_value,
                "btc_funding": round(btc_funding, 6),
                "eth_funding": round(eth_funding, 6),
                "etf_7day_flow": etf_flow,
            },
        })

        # ── DCA Execution ────────────────────────────────────────────────

        if gatekeeper_action != "SKIP":
            if gatekeeper_action == "ENHANCED":
                dca_amount = DCA_AMOUNT_ENHANCED
            elif gatekeeper_action == "FULL":
                dca_amount = DCA_AMOUNT_FULL
            else:
                dca_amount = DCA_AMOUNT_HALF

            if portfolio["dca_reserve"] >= dca_amount and btc_price and eth_price:
                dca_triggers += 1
                prices_map = {"BTC": btc_price, "ETH": eth_price}

                for coin, allocation in DCA_ALLOCATION.items():
                    usd = round(dca_amount * allocation, 2)
                    price = prices_map[coin]
                    units = usd / price

                    portfolio["dca_reserve"] = round(portfolio["dca_reserve"] - usd, 4)
                    portfolio["holdings"][coin] = round(portfolio["holdings"].get(coin, 0) + units, 8)
                    trade = {
                        "symbol": coin,
                        "usd_amount": usd,
                        "price": price,
                        "units_bought": round(units, 8),
                        "signal": gatekeeper_action,
                        "date": date_str,
                    }
                    portfolio["trades"].append(trade)
                    write_event(log_file, "CRYPTO_DCA_BUY", ts, {
                        "symbol": coin,
                        "usd_amount": usd,
                        "price": price,
                        "units_bought": round(units, 8),
                        "signal": gatekeeper_action,
                    })

                print(f"  {date_str}: DCA {gatekeeper_action} ${dca_amount} "
                      f"(F&G={fg_value}, reserve=${portfolio['dca_reserve']:.0f})")

        # ── Grid Bot ─────────────────────────────────────────────────────

        if grid["active"]:
            # Check floor breach
            if sol_price < GRID_LOWER:
                grid["consecutive_below_floor"] += 1
                if grid["consecutive_below_floor"] >= 2:
                    grid["active"] = False
                    write_event(log_file, "CRYPTO_GRID_PAUSED", ts, {
                        "reason": f"Price ${sol_price:.2f} below floor ${GRID_LOWER} for 2 days",
                        "price": sol_price,
                    })
                    print(f"  {date_str}: GRID PAUSED — SOL ${sol_price:.2f} below floor")
            else:
                grid["consecutive_below_floor"] = 0

            # Check grid fills
            if prev_sol_price is not None and grid["active"]:
                for level in grid["levels"]:
                    lp = level["price"]

                    # Buy fill: price dropped through level
                    if prev_sol_price > lp >= sol_price and not level["buy_filled"]:
                        units = LEVEL_CAPITAL / lp
                        level["buy_filled"] = True
                        level["units"] = round(units, 6)
                        grid_buys += 1
                        write_event(log_file, "CRYPTO_GRID_TRADE", ts, {
                            "type": "BUY",
                            "symbol": "SOL/USDT",
                            "price": lp,
                            "units": level["units"],
                            "current_price": sol_price,
                        })
                        print(f"  {date_str}: GRID BUY SOL @ ${lp:.2f} "
                              f"({level['units']:.4f} units, SOL=${sol_price:.2f})")

                    # Sell fill: price rose through level where buy was filled
                    elif prev_sol_price < lp <= sol_price and level["buy_filled"] and not level["sell_filled"]:
                        buy_price = lp - step
                        profit = level["units"] * (lp - buy_price)
                        level["sell_filled"] = True
                        grid["pnl_usd"] = round(grid["pnl_usd"] + profit, 4)
                        total_grid_pnl += profit
                        grid_sells += 1
                        write_event(log_file, "CRYPTO_GRID_TRADE", ts, {
                            "type": "SELL",
                            "symbol": "SOL/USDT",
                            "price": lp,
                            "units": level["units"],
                            "profit_usd": round(profit, 4),
                            "current_price": sol_price,
                        })
                        print(f"  {date_str}: GRID SELL SOL @ ${lp:.2f} "
                              f"(profit ${profit:.2f}, total PnL ${grid['pnl_usd']:.2f})")

        prev_sol_price = sol_price

    log_file.close()

    # Save final state
    grid["current_price"] = sol_price
    with open(GRID_PATH, "w") as f:
        json.dump(grid, f, indent=2)

    with open(PORTFOLIO_PATH, "w") as f:
        json.dump(portfolio, f, indent=2)

    # Calculate DCA portfolio value at final prices
    last_btc = btc_price or 0
    last_eth = eth_price or 0
    dca_value = (portfolio["holdings"]["BTC"] * last_btc +
                 portfolio["holdings"]["ETH"] * last_eth)
    dca_cost = DCA_RESERVE_USD - portfolio["dca_reserve"]

    # Summary
    print("\n" + "=" * 60)
    print("  SIMULATION COMPLETE")
    print("=" * 60)
    print(f"  Days simulated  : {NUM_DAYS}")
    print(f"\n  Grid Bot (SOL/USDT ${GRID_LOWER}-${GRID_UPPER}):")
    print(f"    Buy fills     : {grid_buys}")
    print(f"    Sell fills    : {grid_sells}")
    print(f"    Total PnL     : ${total_grid_pnl:.2f}")
    print(f"    Grid active   : {grid['active']}")
    print(f"\n  Fear DCA:")
    print(f"    Triggers      : {dca_triggers}")
    print(f"    Capital deployed: ${dca_cost:.2f}")
    print(f"    Reserve left  : ${portfolio['dca_reserve']:.2f}")
    print(f"    BTC held      : {portfolio['holdings']['BTC']:.8f}")
    print(f"    ETH held      : {portfolio['holdings']['ETH']:.8f}")
    print(f"    Current value : ${dca_value:.2f}")
    if dca_cost > 0:
        dca_return = (dca_value - dca_cost) / dca_cost * 100
        print(f"    DCA return    : {dca_return:+.2f}%")
    print(f"\n  Output files:")
    print(f"    {LOG_PATH}")
    print(f"    {PORTFOLIO_PATH}")
    print(f"    {GRID_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
