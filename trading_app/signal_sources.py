from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


def _candidate(text: str, source: str, published: str = "") -> dict | None:
    upper = text.upper()
    symbol = re.search(r"\b(XAUUSD|GOLD)\b", upper)
    side = re.search(r"\b(BUY|LONG|SELL|SHORT)\b", upper)
    if not symbol or not side:
        return None
    direction = "long" if side.group(1) in ("BUY", "LONG") else "short"
    def number(pattern):
        match = re.search(pattern, upper)
        return float(match.group(1)) if match else None
    entry = number(r"\b(?:ENTRY|ENTER|AT)\s*[:=@-]?\s*(\d+(?:\.\d+)?)")
    stop = number(r"\b(?:SL|STOP(?:\s*LOSS)?)\s*[:=@-]?\s*(\d+(?:\.\d+)?)")
    target = number(r"\b(?:TP\s*\d*|TARGET)\s*[:=@-]?\s*(\d+(?:\.\d+)?)")
    return {
        "source": source, "published": published, "symbol": "XAUUSD",
        "direction": direction, "entry": entry, "stop": stop, "target": target,
        "raw_text": text[:4000], "status": "UNVERIFIED • REVIEW ONLY",
        "review_required": True,
    }


def parse_signal_payload(payload, source: str) -> list[dict]:
    """Parse a JSON list/object or RSS/Atom XML into unverified XAUUSD candidates."""
    rows = []
    if isinstance(payload, (dict, list)):
        items = payload if isinstance(payload, list) else payload.get("signals", payload.get("items", [payload]))
        if not isinstance(items, list):
            items = [items]
        for item in items:
            if isinstance(item, str):
                text, published = item, ""
            elif isinstance(item, dict):
                text = " ".join(str(item.get(k, "")) for k in
                                ("text", "message", "description", "signal", "title",
                                 "direction", "side", "symbol", "entry", "stop", "sl", "target", "tp"))
                published = str(item.get("published", item.get("date", item.get("time", ""))))
            else:
                continue
            candidate = _candidate(text, source, published)
            if candidate:
                rows.append(candidate)
        return rows
    if isinstance(payload, str):
        root = ET.fromstring(payload)
        for node in root.iter():
            tag = node.tag.rsplit("}", 1)[-1].lower()
            if tag not in ("item", "entry"):
                continue
            fields = {}
            for child in node:
                fields[child.tag.rsplit("}", 1)[-1].lower()] = "".join(child.itertext()).strip()
            text = " ".join(fields.get(k, "") for k in ("title", "summary", "description", "content"))
            candidate = _candidate(text, source, fields.get("pubdate", fields.get("published", fields.get("updated", ""))))
            if candidate:
                rows.append(candidate)
        return rows
    raise ValueError("Unsupported feed payload. Expected JSON or RSS/Atom XML.")


def fetch_signal_feed(url: str, timeout: int = 8) -> list[dict]:
    """Fetch an explicitly configured HTTPS JSON/RSS feed; never places trades."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Signal feed URL must use HTTPS.")
    request = urllib.request.Request(url, headers={"User-Agent": "DRTradingTerminal/0.3"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ValueError("Feed is larger than the 1 MB safety limit.")
        content_type = response.headers.get("Content-Type", "").lower()
    text = body.decode("utf-8-sig")
    if "json" in content_type or text.lstrip().startswith(("{", "[")):
        return parse_signal_payload(json.loads(text), url)
    return parse_signal_payload(text, url)
