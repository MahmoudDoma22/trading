from __future__ import annotations
import json, re, urllib.request, xml.etree.ElementTree as ET
from urllib.parse import urlparse

def _candidate(text: str, source: str, published: str = "") -> dict | None:
    upper=text.upper()
    if not re.search(r"\b(XAUUSD|GOLD)\b",upper): return None
    side=re.search(r"\b(BUY|LONG|SELL|SHORT)\b",upper)
    if not side: return None
    def number(pattern):
        m=re.search(pattern,upper); return float(m.group(1)) if m else None
    return {"source":source,"published":published,"symbol":"XAUUSD",
      "direction":"long" if side.group(1) in ("BUY","LONG") else "short",
      "entry":number(r"\b(?:ENTRY|ENTER|AT)\s*[:=@-]?\s*(\d+(?:\.\d+)?)"),
      "stop":number(r"\b(?:SL|STOP(?:\s*LOSS)?)\s*[:=@-]?\s*(\d+(?:\.\d+)?)"),
      "target":number(r"\bTP\s*[:=@-]\s*(\d+(?:\.\d+)?)") or number(r"\bTP\s+(\d+(?:\.\d+)?)") or number(r"\bTARGET\s*[:=@-]?\s*(\d+(?:\.\d+)?)"),
      "raw_text":text[:4000],"status":"UNVERIFIED • REVIEW ONLY","review_required":True}

def parse_signal_payload(payload, source: str) -> list[dict]:
    rows=[]
    if isinstance(payload,(dict,list)):
        items=payload if isinstance(payload,list) else payload.get("signals",payload.get("items",[payload]))
        if not isinstance(items,list): items=[items]
        for item in items:
            if isinstance(item,str): text,published=item,""
            elif isinstance(item,dict):
                text=" ".join([str(item.get(k,"")) for k in ("text","message","description","signal","title","direction","side","symbol")] + (["ENTRY " + str(item.get("entry"))] if item.get("entry") is not None else []) + (["SL " + str(item.get("stop", item.get("sl")))] if item.get("stop", item.get("sl")) is not None else []) + (["TP " + str(item.get("target", item.get("tp")))] if item.get("target", item.get("tp")) is not None else []))
                published=str(item.get("published",item.get("date",item.get("time",""))))
            else: continue
            row=_candidate(text,source,published)
            if row: rows.append(row)
        return rows
    if isinstance(payload,str):
        root=ET.fromstring(payload)
        for node in root.iter():
            if node.tag.rsplit("}",1)[-1].lower() not in ("item","entry"): continue
            fields={c.tag.rsplit("}",1)[-1].lower():"".join(c.itertext()).strip() for c in node}
            text=" ".join(fields.get(k,"") for k in ("title","summary","description","content"))
            row=_candidate(text,source,fields.get("pubdate",fields.get("published",fields.get("updated",""))))
            if row: rows.append(row)
        return rows
    raise ValueError("Unsupported feed payload. Expected JSON or RSS/Atom XML.")

def fetch_signal_feed(url: str, timeout: int = 8) -> list[dict]:
    parsed=urlparse(url.strip())
    if parsed.scheme!="https" or not parsed.netloc: raise ValueError("Signal feed URL must use HTTPS.")
    request=urllib.request.Request(url,headers={"User-Agent":"DRTradingTerminal/0.3"})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        body=response.read(1_000_001); content_type=response.headers.get("Content-Type","").lower()
    if len(body)>1_000_000: raise ValueError("Feed is larger than the 1 MB safety limit.")
    payload=body.decode("utf-8-sig")
    return parse_signal_payload(json.loads(payload),url) if "json" in content_type or payload.lstrip().startswith(("{","[")) else parse_signal_payload(payload,url)
