from __future__ import annotations

from .config import BotDefinition
from .strategy_engine import StrategyEngine


BOT_LIBRARY = [
    BotDefinition("DR Trend Momentum Bot", "EMA trend alignment with RSI and MACD momentum confirmation.", default_timeframe="M15", min_confidence=18, max_risk_usd=5, max_trade_size_lots=0.10, settings={"timeframes": ["M15", "H1", "H4"]}),
    BotDefinition("DR Range / Breakout Research Bot", "Context-only breakout research using confirmed structure and volume expansion; not a profitability claim.", default_timeframe="M15", min_confidence=20, max_risk_usd=5, max_trade_size_lots=0.08, settings={"timeframes": ["M5", "M15", "H1"]}),
    BotDefinition("DR Scalping Research Bot", "Short timeframe signal context across M1/M5/M15; spread and execution costs require demo validation.", default_timeframe="M5", min_confidence=20, max_risk_usd=5, max_trade_size_lots=0.05, settings={"timeframes": ["M1", "M5", "M15"]}),
    BotDefinition("DR Swing Pullback Research Bot", "Higher-timeframe trend and pullback context using RSI, MACD, EMA and confirmed swing pivots.", default_timeframe="H1", min_confidence=20, max_risk_usd=5, max_trade_size_lots=0.06, settings={"timeframes": ["M15", "H1", "H4", "D1"]}),
]


class BotManager:
    def __init__(self):
        self.bots = BOT_LIBRARY
        self.engine = StrategyEngine()

    def get_bots(self):
        return self.bots

    def evaluate(self, symbol: str, candles_by_tf: dict, bot: BotDefinition) -> dict:
        signal = self.engine.generate_signal(symbol, candles_by_tf, {"min_confidence": bot.min_confidence})
        signal.update({
            "bot_name": bot.name,
            "description": bot.description,
            "max_risk_usd": min(bot.max_risk_usd, 5.0),
            "max_trade_size_lots": bot.max_trade_size_lots,
            "strategy_timeframes": bot.settings.get("timeframes", []),
        })
        return signal
