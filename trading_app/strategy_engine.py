from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


TIMEFRAMES = ("M1", "M5", "M15", "H1", "H4", "D1")
# Higher timeframes receive more weight as context; this is a heuristic, not a probability.
TF_WEIGHTS = {"M1": 0.7, "M5": 0.9, "M15": 1.2, "H1": 1.5, "H4": 1.8, "D1": 2.0}


def _series_last(series: pd.Series, default: float = 0.0) -> float:
    if series is None or len(series) == 0:
        return default
    value = series.iloc[-1]
    return float(value) if pd.notna(value) and np.isfinite(value) else default


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    signal_line = line.ewm(span=signal, adjust=False).mean()
    return line, signal_line, line - signal_line


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    previous = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous).abs(),
        (df["low"] - previous).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def normalize_candles(candles: Any) -> pd.DataFrame:
    if candles is None or len(candles) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(candles)
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    volume_col = "tick_volume" if "tick_volume" in df else "real_volume"
    df["volume"] = pd.to_numeric(df[volume_col], errors="coerce") if volume_col in df else 0.0
    if "time" in df:
        df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    return df


def _confirmed_pivots(df: pd.DataFrame, radius: int = 3):
    """Return confirmed local extrema; last radius candles are intentionally not pivot-confirmed."""
    highs, lows = [], []
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    for i in range(radius, max(radius, len(df) - radius)):
        left, right = i - radius, i + radius + 1
        if high[i] >= np.max(high[left:right]) and np.count_nonzero(high[i] == high[left:right]) == 1:
            highs.append((i, float(high[i])))
        if low[i] <= np.min(low[left:right]) and np.count_nonzero(low[i] == low[left:right]) == 1:
            lows.append((i, float(low[i])))
    return highs, lows


class StrategyEngine:
    """Explainable indicator scoring for research/signals; scores are not win probabilities."""

    def analyze_timeframe(self, symbol: str, timeframe: str, candles: Any) -> dict:
        df = normalize_candles(candles)
        if len(df) < 30:
            return {"symbol": symbol, "timeframe": timeframe, "valid": False, "reason": "Need at least 30 closed candles."}

        close = df["close"]
        rsi = compute_rsi(close)
        macd, macd_signal, macd_hist = compute_macd(close)
        ema_fast = close.ewm(span=20, adjust=False).mean()
        ema_slow = close.ewm(span=50, adjust=False).mean()
        vol_avg = df["volume"].rolling(20, min_periods=5).mean()
        vol_pressure = (df["volume"] / vol_avg.replace(0, np.nan) - 1).replace([np.inf, -np.inf], np.nan).fillna(0)
        atr = compute_atr(df)
        price = float(close.iloc[-1])
        previous = float(close.iloc[-2])
        rsi_value = _series_last(rsi, 50)
        macd_value = _series_last(macd_hist)
        pressure = _series_last(vol_pressure)
        fast_value = _series_last(ema_fast, price)
        slow_value = _series_last(ema_slow, price)
        fast_slope = fast_value - _series_last(ema_fast.iloc[:-3], fast_value)

        # Signed component points, centered at 50. RSI is used as momentum confirmation, not a standalone reversal trigger.
        points = 0.0
        reasons = []
        if price > slow_value:
            points += 14
            reasons.append("price above EMA50")
        else:
            points -= 14
            reasons.append("price below EMA50")
        if fast_value > slow_value:
            points += 10
        else:
            points -= 10
        if fast_slope > 0:
            points += 6
        elif fast_slope < 0:
            points -= 6
        if rsi_value >= 55:
            points += 9
            reasons.append(f"RSI momentum {rsi_value:.1f} bullish")
        elif rsi_value <= 45:
            points -= 9
            reasons.append(f"RSI momentum {rsi_value:.1f} bearish")
        if macd_value > 0:
            points += 10
            reasons.append("MACD histogram positive")
        elif macd_value < 0:
            points -= 10
            reasons.append("MACD histogram negative")
        candle_direction = 1 if price > previous else -1 if price < previous else 0
        if pressure > 0.10 and candle_direction:
            points += 7 * candle_direction
            reasons.append("tick-volume expansion")
        highs, lows = _confirmed_pivots(df)
        pivot_context = "no confirmed recent pivot"
        if highs and lows:
            latest_high = highs[-1][1]
            latest_low = lows[-1][1]
            if latest_low > (lows[-2][1] if len(lows) > 1 else latest_low):
                points += 5
                pivot_context = "higher confirmed swing low"
            elif latest_high < (highs[-2][1] if len(highs) > 1 else latest_high):
                points -= 5
                pivot_context = "lower confirmed swing high"
        score = int(round(max(0, min(100, 50 + points))))
        direction = "long" if score >= 60 else "short" if score <= 40 else "neutral"
        return {
            "symbol": symbol, "timeframe": timeframe, "valid": True,
            "score": score, "direction": direction, "price": price,
            "rsi": rsi_value, "macd": _series_last(macd), "macd_signal": _series_last(macd_signal),
            "macd_hist": macd_value, "volume_pressure": pressure,
            "ema20": fast_value, "ema50": slow_value, "atr": _series_last(atr),
            "zigzag_highs": highs[-8:], "zigzag_lows": lows[-8:],
            "pivot_context": pivot_context, "reasons": reasons,
            "close_series": close, "ema20_series": ema_fast,
            "rsi_series": rsi, "macd_hist_series": macd_hist,
            "volume_pressure_series": vol_pressure, "dataframe": df,
        }

    def analyze_symbol(self, symbol: str, candles_by_tf: dict[str, Any]) -> dict[str, dict]:
        return {tf: self.analyze_timeframe(symbol, tf, candles_by_tf.get(tf)) for tf in TIMEFRAMES if candles_by_tf.get(tf) is not None and len(candles_by_tf[tf])}

    def generate_signal(self, symbol: str, candles_by_tf: dict[str, Any], bot_settings: dict | None = None) -> dict:
        results = self.analyze_symbol(symbol, candles_by_tf)
        valid = {tf: result for tf, result in results.items() if result.get("valid")}
        if not valid:
            return {"symbol": symbol, "direction": "neutral", "confidence": 0, "reason": "Not enough valid closed candle data.", "timeframes": results}
        weights = {tf: TF_WEIGHTS.get(tf, 1.0) for tf in valid}
        weighted_bias = sum(weights[tf] * (valid[tf]["score"] - 50) for tf in valid) / sum(weights.values())
        alignment = sum(weights[tf] for tf in valid if (valid[tf]["score"] - 50) * weighted_bias > 0) / sum(weights.values())
        direction = "long" if weighted_bias >= 8 else "short" if weighted_bias <= -8 else "neutral"
        confidence = round(min(100, abs(weighted_bias) * 2) * (0.65 + 0.35 * alignment), 1)
        settings = bot_settings or {}
        min_score = float(settings.get("min_confidence", 18))
        if confidence < min_score:
            direction = "neutral"

        # Set an ATR-based research stop/target from closed M15 data. This is only a proposal.
        anchor = valid.get("M15") or valid.get("M5") or next(iter(valid.values()))
        entry = anchor["price"]
        distance = max(anchor["atr"] * 1.5, entry * 0.0005) if anchor["atr"] > 0 else 0.0
        stop = entry - distance if direction == "long" else entry + distance if direction == "short" else None
        target = entry + distance * 1.5 if direction == "long" else entry - distance * 1.5 if direction == "short" else None
        reason = "Weighted multi-timeframe indicator alignment; score is a heuristic, not a probability."
        if direction == "neutral":
            reason = "No sufficiently aligned directional setup; wait. The score is not a win probability."
        return {
            "symbol": symbol, "direction": direction, "confidence": confidence,
            "alignment": round(alignment * 100, 1), "weighted_bias": round(weighted_bias, 2),
            "reason": reason, "timeframes": results, "entry": entry,
            "stop_loss": stop, "take_profit": target, "stop_distance": distance,
        }
