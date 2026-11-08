from __future__ import annotations

import math
from typing import Dict, List

import numpy as np
import pandas as pd


TIMEFRAME_PRIORITY = ["M1", "M5", "M15", "H1", "H4", "D1"]


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_rsi(series: pd.Series, periods: int = 14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=periods, min_periods=periods).mean()
    avg_loss = loss.rolling(window=periods, min_periods=periods).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist


def compute_volume_pressure(volume: pd.Series, lookback: int = 20):
    avg = volume.rolling(lookback).mean()
    return (volume - avg) / avg.replace(0, np.nan)


def compute_trend(series: pd.Series, periods: int = 20):
    sma_fast = series.rolling(periods).mean()
    ema_fast = series.ewm(span=max(5, periods // 2), adjust=False).mean()
    return sma_fast, ema_fast


def compute_zigzag(series: pd.Series, threshold: float = 0.02):
    diffs = series.pct_change().fillna(0.0)
    local = diffs.abs() > threshold
    return local


class StrategyEngine:
    def __init__(self):
        self.timeframes = TIMEFRAME_PRIORITY

    def analyze_symbol(self, symbol: str, candles_by_tf: Dict[str, list]) -> Dict[str, dict]:
        results = {}
        for tf, candles in candles_by_tf.items():
            if not candles:
                continue
            df = pd.DataFrame(candles)
            if "close" not in df.columns:
                df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"])
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df["volume"] = pd.to_numeric(df.get("tick_volume", df.get("real_volume", 0)), errors="coerce").fillna(0)
            df = df.dropna(subset=["close"]).reset_index(drop=True)
            if df.empty:
                continue

            rsi = compute_rsi(df["close"])
            macd, macd_signal, macd_hist = compute_macd(df["close"])
            volume_pressure = compute_volume_pressure(df["volume"])
            sma, ema = compute_trend(df["close"])
            zigzag = compute_zigzag(df["close"])

            last_close = float(df["close"].iloc[-1])
            last_rsi = float(rsi.iloc[-1])
            last_macd = float(macd_hist.iloc[-1])
            last_volume_pressure = float(volume_pressure.iloc[-1])
            last_sma = float(sma.iloc[-1])
            last_ema = float(ema.iloc[-1])
            trend_bias = "bullish" if last_close >= last_ema else "bearish"

            if last_rsi > 70:
                momentum = "overbought"
            elif last_rsi < 30:
                momentum = "oversold"
            else:
                momentum = "neutral"

            if last_macd > 0 and last_volume_pressure > 0:
                signal_strength = "bullish"
            elif last_macd < 0 and last_volume_pressure < 0:
                signal_strength = "bearish"
            else:
                signal_strength = "neutral"

            score = 50
            if trend_bias == "bullish":
                score += 15
            else:
                score -= 15

            if momentum == "overbought":
                score -= 12
            elif momentum == "oversold":
                score += 12

            if signal_strength == "bullish":
                score += 10
            elif signal_strength == "bearish":
                score -= 10

            if last_volume_pressure > 0.1:
                score += 10
            elif last_volume_pressure < -0.1:
                score -= 10

            score = max(0, min(100, round(score)))

            if score >= 60:
                direction = "long"
            elif score <= 40:
                direction = "short"
            else:
                direction = "neutral"

            results[tf] = {
                "symbol": symbol,
                "timeframe": tf,
                "score": score,
                "direction": direction,
                "trend_bias": trend_bias,
                "momentum": momentum,
                "signal_strength": signal_strength,
                "last_close": last_close,
                "last_rsi": last_rsi,
                "last_macd": last_macd,
                "last_volume_pressure": last_volume_pressure,
                "last_sma": last_sma,
                "last_ema": last_ema,
                "zigzag": bool(zigzag.iloc[-1]) if len(zigzag) else False,
                "analysis": {
                    "price": last_close,
                    "rsi": last_rsi,
                    "macd_hist": last_macd,
                    "volume_pressure": last_volume_pressure,
                    "ema": last_ema,
                },
            }

        return results

    def generate_signal(self, symbol: str, candles_by_tf: Dict[str, list], bot_settings: dict) -> dict:
        timeframes = self.analyze_symbol(symbol, candles_by_tf)
        directional_votes = {"long": 0, "short": 0, "neutral": 0}
        confidence_total = 0

        for tf, result in timeframes.items():
            if result["direction"] == "long":
                directional_votes["long"] += 1
            elif result["direction"] == "short":
                directional_votes["short"] += 1
            else:
                directional_votes["neutral"] += 1
            confidence_total += result["score"]

        if directional_votes["long"] > directional_votes["short"]:
            direction = "long"
        elif directional_votes["short"] > directional_votes["long"]:
            direction = "short"
        else:
            direction = "neutral"

        confidence = round(confidence_total / max(len(timeframes), 1), 2)
        min_confidence = bot_settings.get("min_confidence", 55.0)

        if direction == "neutral" and confidence < min_confidence:
            return {
                "symbol": symbol,
                "direction": "neutral",
                "confidence": confidence,
                "reason": "No clear multi-timeframe direction; waiting for stronger confirmation.",
                "timeframes": timeframes,
            }

        if direction == "long" and confidence < min_confidence:
            direction = "neutral"

        if direction == "short" and confidence < min_confidence:
            direction = "neutral"

        return {
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "reason": "Aggregated multi-timeframe structure from DR Built-in RSI, MACD, Volumes.",
            "timeframes": timeframes,
        }

    def estimate_risk_levels(self, price: float, stop_distance_points: float, point_value: float = 1.0):
        risk_per_unit = stop_distance_points * point_value
        return risk_per_unit
