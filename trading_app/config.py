from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class MqlConfig:
    login: int = 0
    password: str = ""
    server: str = ""
    path: str = ""
    symbol: str = "XAUUSD"
    max_risk_usd: float = 5.0
    auto_trade_enabled: bool = False


@dataclass
class Signal:
    symbol: str
    direction: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_usd: float
    reward_usd: float
    analysis: dict
    timeframe: str = "M15"


@dataclass
class BotDefinition:
    name: str
    description: str
    instrument: str = "XAUUSD"
    trade_direction: str = "both"
    default_timeframe: str = "M15"
    min_confidence: float = 55.0
    max_risk_usd: float = 5.0
    max_trade_size_lots: float = 0.10
    auto_trade_enabled: bool = False
    settings: dict = field(default_factory=dict)
