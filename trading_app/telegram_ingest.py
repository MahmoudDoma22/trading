from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


CHANNEL_USERNAME = "kingxauusd1"
CHANNEL_LINK = "https://t.me/kingxauusd1"


def _flatten_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_flatten_text(item.get("text", "") if isinstance(item, dict) else item) for item in value)
    return ""


def classify_signal(text: str) -> dict:
    """Extract candidate signal fields for review; does not validate or issue trade instructions."""
    upper = text.upper()
    symbol_match = re.search(r"\b(XAUUSD|GOLD|XAGUSD|EURUSD)\b", upper)
    direction_match = re.search(r"\b(BUY|LONG|SELL|SHORT)\b", upper)
    entry_match = re.search(r"\b(?:ENTRY|ENTER|AT)\s*[:=@-]?\s*(\d+(?:\.\d+)?)", upper)
    stop_match = re.search(r"\b(?:SL|STOP(?:\s*LOSS)?)\s*[:=@-]?\s*(\d+(?:\.\d+)?)", upper)
    target_match = re.search(r"\b(?:TP\s*\d*|TARGET)\s*[:=@-]?\s*(\d+(?:\.\d+)?)", upper)
    direction = direction_match.group(1).lower() if direction_match else "unspecified"
    if direction in ("buy", "long"):
        direction = "long"
    elif direction in ("sell", "short"):
        direction = "short"
    return {
        "candidate_symbol": symbol_match.group(1) if symbol_match else None,
        "candidate_direction": direction,
        "candidate_entry": float(entry_match.group(1)) if entry_match else None,
        "candidate_stop": float(stop_match.group(1)) if stop_match else None,
        "candidate_target": float(target_match.group(1)) if target_match else None,
        "review_required": True,
    }


def parse_telegram_export(path: str) -> list[dict]:
    """Parse a Telegram Desktop JSON export supplied by the user, preserving message provenance."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    messages = payload.get("messages", []) if isinstance(payload, dict) else []
    results = []
    for item in messages:
        text = _flatten_text(item.get("text", ""))
        if not text.strip():
            continue
        results.append({
            "source": CHANNEL_LINK,
            "message_id": item.get("id"),
            "date": item.get("date"),
            "text": text,
            "candidate": classify_signal(text),
            "trusted": False,
        })
    return results


def poll_authorized_channel_updates(token: str | None = None, offset: int | None = None, timeout: int = 10) -> tuple[list[dict], int | None]:
    """Poll Bot API updates. Bot must be added as an admin to the channel; only new updates are available."""
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in your environment. Never paste the token into chat or commit it.")
    query = {"timeout": min(max(int(timeout), 0), 30), "allowed_updates": json.dumps(["channel_post"])}
    if offset is not None:
        query["offset"] = offset
    url = f"https://api.telegram.org/bot{token}/getUpdates?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"User-Agent": "TradingResearchApp/0.1"})
    with urllib.request.urlopen(request, timeout=timeout + 5) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError("Telegram Bot API returned an unsuccessful response.")
    items, next_offset = [], offset
    for update in body.get("result", []):
        next_offset = max(next_offset or 0, int(update["update_id"]) + 1)
        post = update.get("channel_post")
        chat = (post or {}).get("chat", {})
        if not post or chat.get("username", "").lower() != CHANNEL_USERNAME:
            continue
        text = _flatten_text(post.get("text", post.get("caption", "")))
        if text.strip():
            items.append({
                "source": CHANNEL_LINK, "message_id": post.get("message_id"),
                "date": post.get("date"), "text": text,
                "candidate": classify_signal(text), "trusted": False,
            })
    return items, next_offset
