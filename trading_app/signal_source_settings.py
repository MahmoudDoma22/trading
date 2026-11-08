from __future__ import annotations

import json
import os
from pathlib import Path


def settings_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return base / "DRTradingTerminal" / "signal_sources.json"


def load_signal_sources() -> list[dict]:
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sources = data.get("sources", []) if isinstance(data, dict) else []
        return [item for item in sources if isinstance(item, dict) and item.get("url")]
    except (OSError, ValueError, TypeError):
        return []


def save_signal_sources(sources: list[dict]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = []
    for item in sources:
        name = str(item.get("name", "")).strip()[:80]
        url = str(item.get("url", "")).strip()
        if name and url.startswith("https://"):
            clean.append({"name": name, "url": url, "enabled": bool(item.get("enabled", True))})
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 1, "sources": clean}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
