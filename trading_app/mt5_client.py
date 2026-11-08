from __future__ import annotations

import logging
from typing import Optional

try:
    import MetaTrader5 as mt5
except ImportError:  # Keep the UI importable on systems without the MT5 package.
    mt5 = None

logger = logging.getLogger(__name__)

TIMEFRAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


class MT5Connection:
    """Thin, defensive adapter around the locally installed MT5 terminal."""

    def __init__(self, config):
        self.config = config
        self.connected = False
        self.symbol = config.symbol

    @staticmethod
    def _require_package():
        if mt5 is None:
            raise RuntimeError("MetaTrader5 Python package is missing. Install requirements on Windows with MT5 installed.")

    def connect(self) -> bool:
        self._require_package()
        # Prefer the terminal already opened and authenticated by the user. No credentials are stored by this app.
        if not mt5.initialize():
            logger.error("MT5 initialize failed: %s", mt5.last_error())
            self.connected = False
            return False
        self.connected = mt5.terminal_info() is not None and mt5.account_info() is not None
        if self.connected:
            self.symbol = self.resolve_symbol(self.config.symbol) or self.config.symbol
        return self.connected

    def disconnect(self):
        if mt5 is not None:
            mt5.shutdown()
        self.connected = False

    def _ensure_connected(self):
        self._require_package()
        if not self.connected:
            raise RuntimeError("Connect to the MetaTrader 5 terminal first.")

    def resolve_symbol(self, requested: str) -> Optional[str]:
        self._ensure_connected()
        info = mt5.symbol_info(requested)
        if info is not None:
            if not info.visible:
                mt5.symbol_select(requested, True)
            return requested
        matches = mt5.symbols_get(request=f"*{requested}*") or ()
        for item in matches:
            if item.name.upper().startswith(requested.upper()):
                mt5.symbol_select(item.name, True)
                return item.name
        return None

    def get_symbol_info(self, symbol: str):
        self._ensure_connected()
        return mt5.symbol_info(symbol)

    def get_tick(self, symbol: str):
        self._ensure_connected()
        return mt5.symbol_info_tick(symbol)

    def get_candles(self, symbol: str, timeframe: str, count: int = 250, closed_only: bool = True):
        self._ensure_connected()
        constant = TIMEFRAMES.get(timeframe)
        if constant is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        rates = mt5.copy_rates_from_pos(symbol, getattr(mt5, constant), 0, count + (1 if closed_only else 0))
        if rates is None:
            logger.warning("No rates for %s %s: %s", symbol, timeframe, mt5.last_error())
            return []
        # MT5 position zero is the currently forming candle; exclude it for stable signal calculations.
        if closed_only and len(rates):
            rates = rates[:-1]
        return rates

    def get_market_data(self, symbol: str, timeframes: tuple[str, ...], count: int = 250):
        self._ensure_connected()
        resolved = self.resolve_symbol(symbol)
        if not resolved:
            raise RuntimeError(f"Symbol {symbol!r} is not available in this broker's Market Watch.")
        data = {tf: self.get_candles(resolved, tf, count=count, closed_only=True) for tf in timeframes}
        return resolved, data

    def get_account_info(self):
        self._ensure_connected()
        return mt5.account_info()

    def is_demo_account(self) -> bool:
        account = self.get_account_info()
        return account is not None and account.trade_mode == mt5_ACCOUNT_DEMO()

    def calculate_profit(self, order_type: int, symbol: str, volume: float, entry: float, stop: float):
        self._ensure_connected()
        return mt5.order_calc_profit(order_type, symbol, volume, entry, stop)

    def calculate_margin(self, order_type: int, symbol: str, volume: float, price: float):
        self._ensure_connected()
        return mt5.order_calc_margin(order_type, symbol, volume, price)

    def send_market_order(self, symbol: str, direction: str, volume: float, stop_loss: float, take_profit: float, comment: str = "DR demo strategy"):
        self._ensure_connected()
        if not self.is_demo_account():
            raise RuntimeError("Order blocked: automatic order submission is restricted to MT5 demo accounts.")
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            raise RuntimeError("Could not read symbol specification or current tick.")
        is_buy = direction == "long"
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = tick.ask if is_buy else tick.bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 30,
            "magic": 270811,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"MT5 order_send returned no result: {mt5.last_error()}")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 rejected the order (retcode {result.retcode}): {result.comment}")
        return result


def mt5_ACCOUNT_DEMO():
    if mt5 is None:
        return -1
    return mt5.ACCOUNT_TRADE_MODE_DEMO
