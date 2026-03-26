import requests
from datetime import datetime, timezone


def get_fear_greed():
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        resp.raise_for_status()
        item = resp.json()["data"][0]
        return {
            "value": int(item["value"]),
            "classification": item["value_classification"],
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except Exception:
        return None
