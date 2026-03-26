import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime, timezone

from config import GRID_PAIR, GRID_LOWER, GRID_UPPER, GRID_LEVELS, GRID_CAPITAL_USD
from data.fetcher import get_ticker
from logs.logger import CryptoLogger

GRID_PATH = "data/crypto_grid.json"
logger = CryptoLogger()

LEVEL_CAPITAL = GRID_CAPITAL_USD / GRID_LEVELS  # $50 per level


def _load_grid():
    with open(GRID_PATH, "r") as f:
        return json.load(f)


def _save_grid(grid):
    with open(GRID_PATH, "w") as f:
        json.dump(grid, f, indent=2)


def initialize_grid():
    step = (GRID_UPPER - GRID_LOWER) / (GRID_LEVELS - 1)
    levels = []
    for i in range(GRID_LEVELS):
        price = round(GRID_LOWER + i * step, 4)
        levels.append({
            "price": price,
            "buy_filled": False,
            "sell_filled": False,
            "units": 0.0,
        })
    grid = {
        "active": True,
        "levels": levels,
        "previous_price": None,
        "filled_buys": [],
        "pnl_usd": 0.0,
        "consecutive_below_floor": 0,
    }
    _save_grid(grid)
    print(f"Grid initialized: {GRID_LEVELS} levels from ${GRID_LOWER} to ${GRID_UPPER}, all unfilled.")
    return grid


def check_grid(dry_run=False):
    grid = _load_grid()

    if not grid.get("active", True):
        print("Grid bot is PAUSED (price was below floor for 2+ consecutive checks).")
        return

    ticker = get_ticker(GRID_PAIR)
    if ticker is None:
        print("Could not fetch SOL price.")
        return

    current_price = ticker["last"]
    grid["current_price"] = current_price

    # Hard stop logic
    if current_price < GRID_LOWER:
        grid["consecutive_below_floor"] = grid.get("consecutive_below_floor", 0) + 1
        if grid["consecutive_below_floor"] >= 2:
            grid["active"] = False
            if not dry_run:
                _save_grid(grid)
                logger.log_event("CRYPTO_GRID_PAUSED", {
                    "reason": f"Price ${current_price:.2f} below floor ${GRID_LOWER} for 2 consecutive checks",
                    "price": current_price,
                })
            print(f"GRID PAUSED: SOL at ${current_price:.2f} below floor ${GRID_LOWER} for 2 checks.")
            return
    else:
        grid["consecutive_below_floor"] = 0

    step = (GRID_UPPER - GRID_LOWER) / (GRID_LEVELS - 1)

    new_fills = []
    new_sells = []

    prev_price = grid.get("previous_price")

    if prev_price is not None:
        for level in grid["levels"]:
            lp = level["price"]

            # Buy: price fell through this level since last check
            if prev_price > lp and current_price <= lp and not level["buy_filled"]:
                units = LEVEL_CAPITAL / lp
                level["buy_filled"] = True
                level["units"] = round(units, 6)
                new_fills.append(level)
                logger.log_event("CRYPTO_GRID_TRADE", {
                    "type": "BUY",
                    "symbol": GRID_PAIR,
                    "price": lp,
                    "units": level["units"],
                    "current_price": current_price,
                    "dry_run": dry_run,
                })

            # Sell: price rose through this level since last check, and buy was filled
            elif prev_price < lp and current_price >= lp and level["buy_filled"] and not level["sell_filled"]:
                sell_value = level["units"] * lp
                buy_value = level["units"] * (lp - step)
                profit = sell_value - buy_value
                level["sell_filled"] = True
                grid["pnl_usd"] = round(grid["pnl_usd"] + profit, 4)
                new_sells.append((level, profit))
                logger.log_event("CRYPTO_GRID_TRADE", {
                    "type": "SELL",
                    "symbol": GRID_PAIR,
                    "price": lp,
                    "units": level["units"],
                    "profit_usd": round(profit, 4),
                    "current_price": current_price,
                    "dry_run": dry_run,
                })
    else:
        print("  First check — no previous price recorded. Tracking starts now, no fills triggered.")

    grid["previous_price"] = current_price

    if not dry_run:
        _save_grid(grid)

    print(f"\n--- Grid Bot Status ({GRID_PAIR}) ---")
    print(f"  Current price : ${current_price:.2f}")
    print(f"  Prev price    : ${prev_price:.2f}" if prev_price else "  Prev price    : none")
    print(f"  Grid active   : {grid['active']}")
    print(f"  Total PnL     : ${grid['pnl_usd']:.4f}")
    if new_fills:
        print(f"  New buys      : {len(new_fills)} level(s) filled")
    if new_sells:
        print(f"  New sells     : {len(new_sells)} level(s) filled")
    print()
    grid_status(grid, current_price)


def grid_status(grid=None, current_price=None):
    if grid is None:
        grid = _load_grid()
    if current_price is None:
        ticker = get_ticker(GRID_PAIR)
        current_price = ticker["last"] if ticker else None

    print(f"  {'Level':>7}  {'Status':<14}  {'Units':>10}")
    print(f"  {'-'*38}")
    for level in reversed(grid["levels"]):
        lp = level["price"]
        marker = " <-- current" if current_price and abs(lp - current_price) < (GRID_UPPER - GRID_LOWER) / GRID_LEVELS / 2 else ""
        if level["sell_filled"]:
            status = "SELL filled"
        elif level["buy_filled"]:
            status = "BUY filled"
        else:
            status = "unfilled"
        print(f"  ${lp:>6.2f}  {status:<14}  {level['units']:>10.4f}{marker}")
    print(f"\n  Total PnL: ${grid['pnl_usd']:.4f}\n")
