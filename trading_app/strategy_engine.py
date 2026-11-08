from __future__ import annotations

import logging
from typing import Optional

import MetaTrader5 as mt5


logger = logging.getLogger(__name__)


class MT5Connection:
    def __init__(self, config):
        self.config = config
        self.connected = False

    def connect(self) -> bool:
        if self.config.path:
            mt5.initialize(path=self.config.path, login=self.config.login, password=self.config.password, server=self.config.server)
        else:
            mt5.initialize(login=self.config.login, password=self.config.password, server=self.config.server)

        self.connected = mt5.terminal_info() is not None
        return self.connected

    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def get_symbol_info(self, symbol: str):
        return mt5.symbol_info(symbol)

    def get_candles(self, symbol: str, timeframe: str, count: int = 200):
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        if timeframe not in tf_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        candles = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, count)
        return candles

    def get_account_info(self):
        return mt5.account_info()

    def place_order(self, symbol: str, action: int, volume: float, price: float, stoploss: Optional[float] = None, takeprofit: Optional[float] = None, comment: str = "Bot trade"):
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": action,
            "price": price,
            "sl": stoploss,
            "tp": takeprofit,
            "comment": comment,
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        return mt5.order_send(request)
