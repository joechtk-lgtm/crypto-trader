import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import signal
import subprocess
import webbrowser

from data.fear_greed import get_fear_greed
from data.fetcher import get_ticker
from signals.institutional import run_signal_check
from dca.fear_dca import run_dca_check
from grid_bot.engine import check_grid, grid_status, initialize_grid


PORTFOLIO_PATH = "data/crypto_portfolio.json"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_PID_FILE = os.path.join(PROJECT_DIR, ".dashboard.pid")
DASHBOARD_PORT = 8081
DASHBOARD_URL = f"http://localhost:{DASHBOARD_PORT}/dashboard/"


def _pid_alive(pid):
    """Check if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def open_dashboard():
    """Start the dashboard server (or re-open if already running)."""
    if os.path.exists(DASHBOARD_PID_FILE):
        with open(DASHBOARD_PID_FILE) as f:
            pid = int(f.read().strip())
        if _pid_alive(pid):
            print(f"\n  Dashboard already running (PID {pid}). Opening browser...")
            webbrowser.open(DASHBOARD_URL)
            return
        else:
            os.remove(DASHBOARD_PID_FILE)

    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(DASHBOARD_PORT)],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with open(DASHBOARD_PID_FILE, "w") as f:
        f.write(str(proc.pid))
    print(f"\n  Dashboard server started on port {DASHBOARD_PORT} (PID {proc.pid})")
    webbrowser.open(DASHBOARD_URL)


def close_dashboard():
    """Stop the dashboard server."""
    if not os.path.exists(DASHBOARD_PID_FILE):
        print("\n  Dashboard is not running.")
        return
    with open(DASHBOARD_PID_FILE) as f:
        pid = int(f.read().strip())
    if _pid_alive(pid):
        os.kill(pid, signal.SIGTERM)
        print(f"\n  Dashboard server stopped (PID {pid}).")
    else:
        print("\n  Dashboard process was already dead.")
    os.remove(DASHBOARD_PID_FILE)


def view_portfolio():
    try:
        with open(PORTFOLIO_PATH, "r") as f:
            p = json.load(f)
    except Exception:
        print("Could not load portfolio.")
        return

    print("\n--- Portfolio Summary ---")
    print(f"  Grid capital : ${p['grid_capital']:.2f}")
    print(f"  DCA reserve  : ${p['dca_reserve']:.2f}")
    print(f"  Buffer       : ${p['buffer']:.2f}")
    print()

    tickers = {
        "BTC": get_ticker("BTC/USDT"),
        "ETH": get_ticker("ETH/USDT"),
        "SOL": get_ticker("SOL/USDT"),
    }

    total_value = p["grid_capital"] + p["dca_reserve"] + p["buffer"]
    print(f"  {'Coin':<5} {'Holdings':>14} {'Price':>12} {'Value USD':>12}")
    print(f"  {'-'*48}")
    for coin, holdings in p["holdings"].items():
        price = tickers[coin]["last"] if tickers.get(coin) else None
        if price and holdings > 0:
            value = holdings * price
            total_value += value
            print(f"  {coin:<5} {holdings:>14.6f} ${price:>11.2f} ${value:>11.2f}")
        else:
            print(f"  {coin:<5} {holdings:>14.6f} {'N/A':>12} {'N/A':>12}")

    print(f"  {'-'*48}")
    print(f"  {'TOTAL':>5}                            ${total_value:>11.2f}")
    print(f"\n  Trades executed: {len(p.get('trades', []))}")
    print("-------------------------\n")


def print_startup_info():
    print()
    fg = get_fear_greed()
    if fg:
        print(f"  Fear & Greed: {fg['value']} ({fg['classification']})")
    else:
        print("  Fear & Greed: unavailable")

    sol = get_ticker("SOL/USDT")
    if sol:
        print(f"  SOL price   : ${sol['last']:.2f}")
    else:
        print("  SOL price   : unavailable")
    print()


def main():
    print("=== Crypto Trader ===")
    print_startup_info()

    while True:
        print("1. Check institutional signal (3-step gatekeeper)")
        print("2. Run Fear DCA check")
        print("3. Run Fear DCA (live paper trade)")
        print("4. Check grid bot status")
        print("5. View portfolio summary")
        print("d. Open Dashboard")
        print("c. Close Dashboard")
        print("6. Exit")
        print()

        choice = input("Select option: ").strip()

        if choice == "1":
            run_signal_check()
        elif choice == "2":
            run_dca_check(dry_run=True)
        elif choice == "3":
            run_dca_check(dry_run=False)
        elif choice == "4":
            check_grid(dry_run=False)
        elif choice == "5":
            view_portfolio()
        elif choice.lower() == "d":
            open_dashboard()
        elif choice.lower() == "c":
            close_dashboard()
        elif choice == "6":
            print("Goodbye.")
            break
        else:
            print("Invalid option.\n")


if __name__ == "__main__":
    main()
