from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .strategy_engine import StrategyEngine, normalize_candles


@dataclass
class TradeRecord:
    symbol: str
    timeframe: str
    direction: str
    signal_time: str
    entry_time: str
    exit_time: str
    entry: float
    stop_loss: float
    take_profit: float
    exit_price: float
    exit_reason: str
    volume_lots: float
    gross_pnl_usd: float
    costs_usd: float
    net_pnl_usd: float


class Backtester:
    """Simple, conservative single-symbol research backtest; signals use only bars closed before entry."""

    def __init__(self):
        self.engine = StrategyEngine()

    def run(self, candles: Any, symbol: str, timeframe: str, volume_lots: float = 0.01,
            tick_size: float = 0.01, tick_value: float = 1.0, spread_price: float = 0.0,
            commission_per_lot: float = 0.0, max_bars_in_trade: int = 100,
            minimum_score: float = 18.0) -> tuple[list[dict], dict]:
        df = normalize_candles(candles)
        if "time" in df:
            time_values = df["time"].tolist()
        else:
            time_values = list(range(len(df)))
        if len(df) < 80:
            raise ValueError("Backtest requires at least 80 valid historical candles.")
        if volume_lots <= 0 or tick_size <= 0 or tick_value <= 0:
            raise ValueError("Volume, tick size and tick value must be positive.")

        trades: list[dict] = []
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        i = 60
        while i < len(df) - 2:
            # Score data ending at i (closed candle only); enter at next bar open.
            result = self.engine.analyze_timeframe(symbol, timeframe, df.iloc[:i + 1])
            if not result.get("valid") or result["score"] < minimum_score or result["direction"] == "neutral":
                i += 1
                continue
            direction = result["direction"]
            entry_bar = i + 1
            entry = float(df.iloc[entry_bar]["open"])
            atr = float(result.get("atr") or 0)
            if atr <= 0:
                i += 1
                continue
            distance = max(1.5 * atr, entry * 0.0005)
            stop = entry - distance if direction == "long" else entry + distance
            target = entry + 1.5 * distance if direction == "long" else entry - 1.5 * distance
            # Adverse half-spread entry model; costs are also reported as round-turn commission.
            entry += spread_price / 2 if direction == "long" else -spread_price / 2
            exit_price, exit_index, reason = float(df.iloc[-1]["close"]), min(len(df) - 1, entry_bar + max_bars_in_trade), "time_exit"
            for j in range(entry_bar, min(len(df), entry_bar + max_bars_in_trade + 1)):
                bar = df.iloc[j]
                if direction == "long":
                    stop_hit = float(bar["low"]) <= stop
                    target_hit = float(bar["high"]) >= target
                else:
                    stop_hit = float(bar["high"]) >= stop
                    target_hit = float(bar["low"]) <= target
                # Conservative ambiguity resolution: if both levels hit inside a bar, assume stop first.
                if stop_hit:
                    exit_price, exit_index, reason = stop, j, "stop_loss"
                    break
                if target_hit:
                    exit_price, exit_index, reason = target, j, "take_profit"
                    break
                if j == min(len(df) - 1, entry_bar + max_bars_in_trade):
                    exit_price, exit_index = float(bar["close"]), j
            exit_price -= spread_price / 2 if direction == "long" else -spread_price / 2
            move = exit_price - entry if direction == "long" else entry - exit_price
            gross = move / tick_size * tick_value * volume_lots
            commission = commission_per_lot * volume_lots * 2
            net = gross - commission
            signal_time = str(time_values[i])
            entry_time = str(time_values[entry_bar])
            exit_time = str(time_values[exit_index])
            trade = asdict(TradeRecord(symbol, timeframe, direction, signal_time, entry_time, exit_time,
                                       entry, stop, target, exit_price, reason, volume_lots,
                                       gross, commission, net))
            trades.append(trade)
            equity += net
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
            i = exit_index + 1

        wins = sum(1 for trade in trades if trade["net_pnl_usd"] > 0)
        losses = sum(1 for trade in trades if trade["net_pnl_usd"] <= 0)
        total = len(trades)
        net_total = sum(trade["net_pnl_usd"] for trade in trades)
        summary = {
            "symbol": symbol, "timeframe": timeframe, "trades": total,
            "wins": wins, "losses": losses,
            "win_rate_pct": (100 * wins / total) if total else 0.0,
            "net_pnl_usd": net_total,
            "expectancy_usd": (net_total / total) if total else 0.0,
            "max_drawdown_usd": max_drawdown,
            "disclaimer": "Historical simulation only. Results depend on feed quality and cost assumptions; not a forecast or guarantee.",
        }
        return trades, summary

    @staticmethod
    def export_csv(trades: list[dict], path: str):
        columns = list(TradeRecord.__dataclass_fields__.keys())
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(trades)
