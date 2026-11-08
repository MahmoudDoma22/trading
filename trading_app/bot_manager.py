from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path

from .config import BotDefinition
from .strategy_engine import StrategyEngine


BOT_LIBRARY = [
    BotDefinition("DR Trend Momentum Bot", "EMA trend alignment with RSI and MACD momentum confirmation.", default_timeframe="M15", min_confidence=18, max_risk_usd=5, max_trade_size_lots=0.10, settings={"timeframes": ["M15", "H1", "H4"], "stop_atr_multiplier": 1.5}),
    BotDefinition("DR Range / Breakout Research Bot", "Context-only breakout research using confirmed structure and volume expansion; not a profitability claim.", default_timeframe="M15", min_confidence=20, max_risk_usd=5, max_trade_size_lots=0.08, settings={"timeframes": ["M5", "M15", "H1"], "stop_atr_multiplier": 1.5}),
    BotDefinition("DR Scalping Research Bot", "Short timeframe signal context across M1/M5/M15; spread and execution costs require demo validation.", default_timeframe="M5", min_confidence=20, max_risk_usd=5, max_trade_size_lots=0.05, settings={"timeframes": ["M1", "M5", "M15"], "stop_atr_multiplier": 1.2}),
    BotDefinition("DR Swing Pullback Research Bot", "Higher-timeframe trend and pullback context using RSI, MACD, EMA and confirmed swing pivots.", default_timeframe="H1", min_confidence=20, max_risk_usd=5, max_trade_size_lots=0.06, settings={"timeframes": ["M15", "H1", "H4", "D1"], "stop_atr_multiplier": 2.0}),
]


def _default_store_path() -> Path:
    root = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    base = Path(root) if root else Path.home() / ".config"
    return base / "DRTradingTerminal" / "bots.json"


class BotManager:
    """Persistent, editable XAUUSD bot library. Bot scores remain heuristic, not probabilities."""

    def __init__(self, store_path: str | Path | None = None):
        self.store_path = Path(store_path) if store_path else _default_store_path()
        self.engine = StrategyEngine()
        self.bots: list[BotDefinition] = []
        self.load_warning = None
        self.load()

    def get_bots(self) -> list[BotDefinition]:
        return self.bots

    def is_enabled(self, bot: BotDefinition) -> bool:
        return bool(bot.settings.get("enabled", True))

    def _to_dict(self, bot: BotDefinition) -> dict:
        return {
            "name": bot.name, "description": bot.description, "instrument": "XAUUSD",
            "trade_direction": bot.trade_direction, "default_timeframe": bot.default_timeframe,
            "min_confidence": float(bot.min_confidence), "max_risk_usd": min(float(bot.max_risk_usd), 5.0),
            "max_trade_size_lots": float(bot.max_trade_size_lots),
            "auto_trade_enabled": False, "settings": {**bot.settings, "enabled": self.is_enabled(bot)},
        }

    def _from_dict(self, data: dict) -> BotDefinition:
        if not isinstance(data, dict):
            raise ValueError("Each bot must be a JSON object.")
        name = str(data.get("name", "")).strip()
        if not name or len(name) > 80:
            raise ValueError("Bot name must contain 1–80 characters.")
        timeframe = str(data.get("default_timeframe", "M15")).upper()
        allowed = {"M1", "M5", "M15", "H1", "H4", "D1"}
        if timeframe not in allowed:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        confidence = float(data.get("min_confidence", 20))
        risk = float(data.get("max_risk_usd", 5))
        lots = float(data.get("max_trade_size_lots", 0.01))
        multiplier = float((data.get("settings") or {}).get("stop_atr_multiplier", 1.5))
        if not 0 <= confidence <= 100:
            raise ValueError("Minimum confidence must be between 0 and 100.")
        if not 0 < risk <= 5:
            raise ValueError("Per-trade risk must be greater than 0 and no more than $5.")
        if not 0 < lots <= 10:
            raise ValueError("Maximum lot size must be greater than 0 and no more than 10.")
        if not 0.1 <= multiplier <= 10:
            raise ValueError("ATR stop multiplier must be between 0.1 and 10.")
        settings = dict(data.get("settings") or {})
        settings["stop_atr_multiplier"] = multiplier
        settings["timeframes"] = [tf for tf in settings.get("timeframes", [timeframe]) if tf in allowed]
        settings["enabled"] = bool(settings.get("enabled", True))
        return BotDefinition(name=name, description=str(data.get("description", ""))[:500],
            instrument="XAUUSD", trade_direction=str(data.get("trade_direction", "both")),
            default_timeframe=timeframe, min_confidence=confidence, max_risk_usd=min(risk, 5.0),
            max_trade_size_lots=lots, auto_trade_enabled=False, settings=settings)

    def load(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self.bots = deepcopy(BOT_LIBRARY)
            self.save()
            return
        try:
            raw = json.loads(self.store_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("Bot library file must contain a JSON list.")
            loaded = [self._from_dict(item) for item in raw]
            if not loaded:
                raise ValueError("Bot library cannot be empty.")
            self._assert_unique_names(loaded)
            self.bots = loaded
        except Exception as exc:
            backup = self.store_path.with_suffix(".invalid.json")
            try:
                self.store_path.replace(backup)
            except OSError:
                pass
            self.bots = deepcopy(BOT_LIBRARY)
            self.load_warning = f"Saved bot library was invalid; defaults were restored. Backup: {backup}. Details: {exc}"
            self.save()

    def save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [self._to_dict(bot) for bot in self.bots]
        fd, temp_name = tempfile.mkstemp(prefix="bots_", suffix=".tmp", dir=str(self.store_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.store_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _assert_unique_names(self, bots: list[BotDefinition]) -> None:
        names = [bot.name.casefold() for bot in bots]
        if len(names) != len(set(names)):
            raise ValueError("Bot names must be unique.")

    def add_bot(self, bot: BotDefinition) -> None:
        candidate = self._from_dict(self._to_dict(bot))
        self._assert_unique_names([*self.bots, candidate])
        self.bots.append(candidate)
        self.save()

    def update_bot(self, original_name: str, bot: BotDefinition) -> None:
        candidate = self._from_dict(self._to_dict(bot))
        index = next((i for i, item in enumerate(self.bots) if item.name == original_name), None)
        if index is None:
            raise ValueError("The selected bot no longer exists.")
        updated = list(self.bots)
        updated[index] = candidate
        self._assert_unique_names(updated)
        self.bots[index] = candidate
        self.save()

    def delete_bot(self, name: str) -> None:
        if len(self.bots) <= 1:
            raise ValueError("Keep at least one bot in the library.")
        self.bots = [bot for bot in self.bots if bot.name != name]
        self.save()

    def duplicate_bot(self, name: str) -> BotDefinition:
        source = next((bot for bot in self.bots if bot.name == name), None)
        if source is None:
            raise ValueError("The selected bot no longer exists.")
        clone = deepcopy(source)
        clone.name = f"{source.name} Copy"
        suffix = 2
        while any(bot.name.casefold() == clone.name.casefold() for bot in self.bots):
            clone.name = f"{source.name} Copy {suffix}"
            suffix += 1
        self.add_bot(clone)
        return clone

    def set_enabled(self, name: str, enabled: bool) -> None:
        bot = next((item for item in self.bots if item.name == name), None)
        if bot is None:
            raise ValueError("The selected bot no longer exists.")
        bot.settings["enabled"] = bool(enabled)
        self.save()

    def reset_defaults(self) -> None:
        self.bots = deepcopy(BOT_LIBRARY)
        self.save()

    def export_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps([self._to_dict(bot) for bot in self.bots], indent=2, ensure_ascii=False), encoding="utf-8")

    def import_json(self, path: str | Path, replace: bool = False) -> int:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not raw:
            raise ValueError("Import file must contain a non-empty list of bots.")
        incoming = [self._from_dict(item) for item in raw]
        combined = incoming if replace else [*self.bots, *incoming]
        self._assert_unique_names(combined)
        self.bots = combined
        self.save()
        return len(incoming)

    def evaluate(self, symbol: str, candles_by_tf: dict, bot: BotDefinition) -> dict:
        if not str(symbol).upper().startswith("XAUUSD"):
            raise ValueError("This application is configured for XAUUSD only.")
        selected_timeframes = bot.settings.get("timeframes") or [bot.default_timeframe]
        selected_data = {tf: candles_by_tf[tf] for tf in selected_timeframes if tf in candles_by_tf}
        signal = self.engine.generate_signal(symbol, selected_data, {
            "min_confidence": bot.min_confidence,
            "stop_atr_multiplier": bot.settings.get("stop_atr_multiplier", 1.5),
        })
        signal.update({"symbol": symbol, "bot_name": bot.name, "description": bot.description,
                      "max_risk_usd": min(bot.max_risk_usd, 5.0),
                      "max_trade_size_lots": bot.max_trade_size_lots,
                      "strategy_timeframes": bot.settings.get("timeframes", [])})
        return signal
