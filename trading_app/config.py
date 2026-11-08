from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MqlConfig:
    symbol: str = "XAUUSD"
    max_risk_usd: float = 5.0
    demo_only: bool = True
    auto_trade_enabled: bool = False
    candle_count: int = 250
    refresh_ms: int = 5000


@dataclass
class BotDefinition:
    name: str
    description: str
    instrument: str = "XAUUSD"
    trade_direction: str = "both"
    default_timeframe: str = "M15"
    min_confidence: float = 18.0
    max_risk_usd: float = 5.0
    max_trade_size_lots: float = 0.10
    auto_trade_enabled: bool = False
    settings: dict = field(default_factory=dict)
