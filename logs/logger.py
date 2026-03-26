import json
import os
from datetime import datetime, timezone


class CryptoLogger:
    def __init__(self, log_path="logs/trading.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log_event(self, event_type: str, data: dict):
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event_type,
            "data": data,
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
