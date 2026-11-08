from __future__ import annotations

import csv
import os
import threading
from datetime import datetime, timezone


FIELDS = ("timestamp_utc", "event", "symbol", "bot", "direction", "score", "entry", "stop", "target", "lots", "estimated_risk_usd", "status", "details")


class StrategyJournal:
    """Append-only local CSV journal; records are informational, not audit-proof."""

    def __init__(self, path: str = "strategy_activity.csv"):
        self.path = path
        self._lock = threading.Lock()

    def record(self, **values):
        row = {field: "" for field in FIELDS}
        row.update(values)
        row["timestamp_utc"] = row.get("timestamp_utc") or datetime.now(timezone.utc).isoformat()
        exists = os.path.exists(self.path)
        with self._lock, open(self.path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if not exists:
                writer.writeheader()
            writer.writerow({key: str(row.get(key, "")) for key in FIELDS})

    def read_rows(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with self._lock, open(self.path, newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
