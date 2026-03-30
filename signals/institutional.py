import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from data.fear_greed import get_fear_greed
from data.fetcher import get_funding_rate
from logs.logger import CryptoLogger

logger = CryptoLogger()

ETF_FLOW_URL = "https://www.theblock.co/api/charts/chart/etfs/bitcoin-etf/spot-bitcoin-etf-total-net-flow"


def _fetch_etf_7day_flow() -> float:
    """Fetch 7-day total net flow (in $M) for BTC spot ETFs from The Block."""
    resp = requests.get(ETF_FLOW_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    series = data["chart"]["jsonFile"]["Series"]["Total Net Flow"]["Data"]
    last7 = series[-7:] if len(series) >= 7 else series
    total = sum(entry["Result"] for entry in last7)
    return total / 1_000_000  # convert to millions


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

    # Step 3: ETF flows from The Block
    try:
        etf_flow = _fetch_etf_7day_flow()
    except Exception as e:
        logger.log_event("ETF_FLOW_FETCH_ERROR", {"error": str(e), "source": ETF_FLOW_URL})
        print(f"  [ETF fetch error] {type(e).__name__}: {e}")
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
