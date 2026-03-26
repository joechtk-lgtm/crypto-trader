import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup

from data.fear_greed import get_fear_greed
from data.fetcher import get_funding_rate
from logs.logger import CryptoLogger

logger = CryptoLogger()


def _parse_etf_flow(html: str) -> float:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return None

    rows = table.find_all("tr")
    data_rows = [r for r in rows if r.find("td")]

    last7 = data_rows[-7:] if len(data_rows) >= 7 else data_rows

    total = 0.0
    for row in last7:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        # Last cell is typically the "Total" column
        # Try the last numeric cell
        for cell in reversed(cells):
            text = cell.get_text(strip=True).replace(",", "").replace("$", "").replace("(", "-").replace(")", "")
            try:
                total += float(text)
                break
            except ValueError:
                continue

    return total


def run_gatekeeper():
    # Step 1: Fear and Greed
    fg = get_fear_greed()
    if fg is None:
        return {
            "action": "SKIP",
            "reason": "Fear and Greed data unavailable",
            "step_reached": 1,
            "scores": {"fear_greed": None, "btc_funding": None, "eth_funding": None, "etf_7day_flow": None},
        }
    if fg["value"] >= 20:
        return {
            "action": "SKIP",
            "reason": f"Fear and Greed not in extreme fear (value={fg['value']})",
            "step_reached": 1,
            "scores": {"fear_greed": fg["value"], "btc_funding": None, "eth_funding": None, "etf_7day_flow": None},
        }

    # Step 2: Funding rates
    btc_funding = get_funding_rate("BTC/USDT")
    eth_funding = get_funding_rate("ETH/USDT")

    if btc_funding is None or eth_funding is None or btc_funding >= 0 or eth_funding >= 0:
        return {
            "action": "SKIP",
            "reason": "Funding rates not both negative",
            "step_reached": 2,
            "scores": {"fear_greed": fg["value"], "btc_funding": btc_funding, "eth_funding": eth_funding, "etf_7day_flow": None},
        }

    # Step 3: ETF flows from farside
    try:
        resp = requests.get("https://farside.co.uk/btc/", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        etf_flow = _parse_etf_flow(resp.text)
    except Exception:
        etf_flow = None

    if etf_flow is None:
        return {
            "action": "SKIP",
            "reason": "Could not fetch ETF flow data",
            "step_reached": 3,
            "scores": {
                "fear_greed": fg["value"],
                "btc_funding": btc_funding,
                "eth_funding": eth_funding,
                "etf_7day_flow": None,
            },
        }

    if etf_flow > 0:
        if fg["value"] < 10:
            action = "ENHANCED"
            reason = f"ETF 7-day net flow positive: ${etf_flow:.0f}M, F&G extreme fear ({fg['value']})"
        else:
            action = "FULL"
            reason = f"ETF 7-day net flow positive: ${etf_flow:.0f}M"
    elif etf_flow >= -200:
        action = "HALF"
        reason = f"ETF 7-day net flow slightly negative: ${etf_flow:.0f}M"
    else:
        action = "SKIP"
        reason = f"ETF 7-day net flow too negative: ${etf_flow:.0f}M"

    return {
        "action": action,
        "reason": reason,
        "step_reached": 3,
        "scores": {
            "fear_greed": fg["value"],
            "btc_funding": btc_funding,
            "eth_funding": eth_funding,
            "etf_7day_flow": etf_flow,
        },
    }


def run_signal_check():
    result = run_gatekeeper()
    logger.log_event("CRYPTO_INSTITUTIONAL_SIGNAL", result)

    print("\n--- Institutional Signal Check ---")
    print(f"  Action     : {result['action']}")
    print(f"  Reason     : {result['reason']}")
    print(f"  Step reached: {result['step_reached']}")
    if "scores" in result:
        s = result["scores"]
        print(f"  Fear/Greed : {s['fear_greed']}")
        print(f"  BTC funding: {s['btc_funding']}")
        print(f"  ETH funding: {s['eth_funding']}")
        print(f"  ETF 7d flow: {s['etf_7day_flow']}")
    print("----------------------------------\n")

    if result["action"] == "FULL":
        print("✅ SIGNAL: FULL DCA ($50) — Run option 3 to execute")
        print("   Split: BTC $35 / ETH $15")
    elif result["action"] == "HALF":
        print("⚠️  SIGNAL: HALF DCA ($25) — Run option 3 to execute")
        print("   Split: BTC $17.50 / ETH $7.50")
    elif result["action"] == "ENHANCED":
        print("🚨 SIGNAL: ENHANCED DCA ($75) — F&G below 10, maximum fear.")
        print("   Run option 3 to execute. Split: BTC $52.50 / ETH $22.50")
    else:
        print("⏭  SIGNAL: SKIP — Conditions not met. Check again tomorrow.")
    print()

    return result
