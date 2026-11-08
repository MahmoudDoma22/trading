from __future__ import annotations

from typing import Dict, List

from .config import BotDefinition
from .strategy_engine import StrategyEngine


BOT_LIBRARY = [
    BotDefinition(
        name="DR Trend Momentum Bot",
        description="Uses trend alignment and MACD confirmation across M15/H1/H4 with volume emphasis.",
        instrument="XAUUSD",
        trade_direction="both",
        default_timeframe="M15",
        min_confidence=60.0,
        max_risk_usd=5.0,
        max_trade_size_lots=0.10,
        settings={"strategy_type": "trend"},
    ),
    BotDefinition(
        name="DR Range Breakout Bot",
        description="Waits for a breakout after volume expansion and a clean directional move.",
        instrument="XAUUSD",
        trade_direction="both",
        default_timeframe="M15",
        min_confidence=62.0,
        max_risk_usd=5.0,
        max_trade_size_lots=0.08,
        settings={"strategy_type": "breakout"},
    ),
    BotDefinition(
        name="DR Swing Scalper Bot",
        description="Scalp direction from M1/M5/M15 structure with quick profit targets and strict risk control.",
        instrument="XAUUSD",
        trade_direction="both",
        default_timeframe="M5",
        min_confidence=58.0,
        max_risk_usd=5.0,
        max_trade_size_lots=0.05,
        settings={"strategy_type": "scalp"},
    ),
    BotDefinition(
        name="DR Safe Pullback Bot",
        description="Waits for pullbacks inside a stronger trend and only advances when momentum remains supportive.",
        instrument="XAUUSD",
        trade_direction="both",
        default_timeframe="H1",
        min_confidence=65.0,
        max_risk_usd=5.0,
        max_trade_size_lots=0.06,
        settings={"strategy_type": "pullback"},
    ),
]


class BotManager:
    def __init__(self):
        self.bots = BOT_LIBRARY
        self.engine = StrategyEngine()

    def get_bots(self):
        return self.bots

    def evaluate(self, symbol: str, candles_by_tf: Dict[str, list], bot: BotDefinition):
        signal = self.engine.generate_signal(symbol, candles_by_tf, {"min_confidence": bot.min_confidence})
        signal["bot_name"] = bot.name
        signal["description"] = bot.description
        signal["max_risk_usd"] = bot.max_risk_usd
        signal["max_trade_size_lots"] = bot.max_trade_size_lots
        signal["auto_trade_enabled"] = bot.auto_trade_enabled
        return signal
