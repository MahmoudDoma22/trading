from __future__ import annotations

from . import __version__


class RiskManager:
    """Broker-calculated position sizing. Fails closed if risk cannot be estimated."""

    def __init__(self, mt5_connection, hard_cap: float = 5.0):
        self.mt5 = mt5_connection
        self.hard_cap = min(float(hard_cap), 5.0)

    def size_position(self, symbol: str, direction: str, entry: float, stop_loss: float, requested_lots: float, bot_max_lots: float) -> dict:
        if direction not in ("long", "short") or entry <= 0 or stop_loss <= 0 or requested_lots <= 0:
            return {"ok": False, "reason": "Invalid direction, price, stop, or requested lot size."}
        cap = min(self.hard_cap, float(requested_lots) and self.hard_cap)
        info = self.mt5.get_symbol_info(symbol)
        account = self.mt5.get_account_info()
        tick = self.mt5.get_tick(symbol)
        if info is None or account is None or tick is None:
            return {"ok": False, "reason": "Missing symbol, account, or tick information."}
        is_long = direction == "long"
        if (is_long and stop_loss >= entry) or (not is_long and stop_loss <= entry):
            return {"ok": False, "reason": "Stop loss is on the wrong side of entry."}
        order_type = 0 if is_long else 1  # MT5 ORDER_TYPE_BUY / ORDER_TYPE_SELL values
        max_volume = min(float(requested_lots), float(bot_max_lots), float(info.volume_max))
        min_volume = float(info.volume_min)
        step = float(info.volume_step)
        if step <= 0 or max_volume < min_volume:
            return {"ok": False, "reason": "Requested volume is below the broker minimum or invalid."}
        max_steps = int((max_volume - min_volume) / step + 1e-8)
        for index in range(max_steps, -1, -1):
            volume = round(min_volume + index * step, 8)
            profit = self.mt5.calculate_profit(order_type, symbol, volume, entry, stop_loss)
            if profit is None or profit >= 0:
                continue
            estimated_loss = abs(float(profit))
            # Include an extra 10% execution-cost buffer; broker slippage can still exceed estimates.
            buffered_loss = estimated_loss * 1.10
            if buffered_loss > cap + 1e-8:
                continue
            margin = self.mt5.calculate_margin(order_type, symbol, volume, entry)
            if margin is None or margin <= 0 or margin > float(account.margin_free) * 0.80:
                continue
            return {
                "ok": True, "volume": volume, "estimated_loss": estimated_loss,
                "buffered_loss": buffered_loss, "risk_cap": cap,
                "margin_estimate": float(margin),
                "warning": "Loss estimate excludes unpredictable gaps/slippage; the $5 cap cannot guarantee a maximum realized loss.",
            }
        return {"ok": False, "reason": "No broker-valid volume fits the $5 risk and free-margin guards."}
