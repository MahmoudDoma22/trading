from __future__ import annotations

import logging
from typing import Optional

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

logger = logging.getLogger(__name__)
TIMEFRAMES = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1"}
APP_MAGIC = 270811


class MT5Connection:
    """Adapter for the already-authenticated local MT5 terminal."""

    def __init__(self, config):
        self.config = config
        self.connected = False
        self.symbol = config.symbol

    @staticmethod
    def _require_package():
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable; install on Windows with the MT5 terminal.")

    def connect(self) -> bool:
        self._require_package()
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
            raise RuntimeError("Connect to the open MetaTrader 5 terminal first.")

    def resolve_symbol(self, requested: str) -> Optional[str]:
        self._ensure_connected()
        info = mt5.symbol_info(requested)
        if info:
            if not info.visible:
                mt5.symbol_select(requested, True)
            return requested
        for item in mt5.symbols_get(request=f"*{requested}*") or ():
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
        rates = mt5.copy_rates_from_pos(symbol, getattr(mt5, constant), 0, count + int(closed_only))
        if rates is None:
            logger.warning("No rates for %s/%s: %s", symbol, timeframe, mt5.last_error())
            return []
        return rates[:-1] if closed_only and len(rates) else rates

    def get_market_data(self, symbol: str, timeframes: tuple[str, ...], count: int = 250):
        self._ensure_connected()
        resolved = self.resolve_symbol(symbol)
        if not resolved:
            raise RuntimeError(f"Broker symbol {symbol!r} is unavailable in Market Watch.")
        return resolved, {tf: self.get_candles(resolved, tf, count) for tf in timeframes}

    def get_account_info(self):
        self._ensure_connected()
        return mt5.account_info()

    def is_demo_account(self) -> bool:
        account = self.get_account_info()
        return bool(account and account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO)

    def is_real_account(self) -> bool:
        account = self.get_account_info()
        return bool(account and account.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL)

    def calculate_profit(self, order_type: int, symbol: str, volume: float, entry: float, stop: float):
        self._ensure_connected()
        return mt5.order_calc_profit(order_type, symbol, volume, entry, stop)

    def calculate_margin(self, order_type: int, symbol: str, volume: float, price: float):
        self._ensure_connected()
        return mt5.order_calc_margin(order_type, symbol, volume, price)

    def send_approved_order(self, symbol: str, direction: str, volume: float, stop_loss: float, take_profit: float, allow_real: bool = False, comment: str = "Human-approved signal"):
        """Send only after an explicit UI approval; live mode must be separately armed."""
        self._ensure_connected()
        demo = self.is_demo_account()
        if not demo and not (self.is_real_account() and allow_real):
            raise RuntimeError("Order blocked: account is neither demo nor explicitly armed real account.")
        info, tick = mt5.symbol_info(symbol), mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            raise RuntimeError("Symbol specification or current quote is unavailable.")
        buy = direction == "long"
        price = tick.ask if buy else tick.bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 30,
            "magic": APP_MAGIC,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"Order rejected: {getattr(result, 'comment', mt5.last_error())}")
        return result

    def emergency_stop_app_trades(self) -> dict:
        """Cancel this app's pending orders and close its own positions; leaves unrelated positions untouched."""
        self._ensure_connected()
        closed, cancelled, errors = [], [], []
        for position in mt5.positions_get() or ():
            if int(getattr(position, "magic", -1)) != APP_MAGIC:
                continue
            tick = mt5.symbol_info_tick(position.symbol)
            if not tick:
                errors.append(f"No quote for position {position.ticket}")
                continue
            buy_to_close = position.type == mt5.POSITION_TYPE_SELL
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "position": position.ticket,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_BUY if buy_to_close else mt5.ORDER_TYPE_SELL,
                "price": tick.ask if buy_to_close else tick.bid,
                "deviation": 50,
                "magic": APP_MAGIC,
                "comment": "Emergency stop app position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                closed.append(int(position.ticket))
            else:
                errors.append(f"Close {position.ticket}: {getattr(result, 'comment', mt5.last_error())}")
        for order in mt5.orders_get() or ():
            if int(getattr(order, "magic", -1)) != APP_MAGIC:
                continue
            result = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket, "magic": APP_MAGIC, "comment": "Emergency stop app order"})
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                cancelled.append(int(order.ticket))
            else:
                errors.append(f"Cancel {order.ticket}: {getattr(result, 'comment', mt5.last_error())}")
        return {"closed": closed, "cancelled": cancelled, "errors": errors}
