# Trading research desktop app

Windows desktop research dashboard for MetaTrader 5. The app reads closed-bar broker data and presents indicator context and heuristic multi-timeframe scores for XAUUSD. Scores are not win probabilities and do not imply profitability.

## Run (Windows)

1. Install Python 3.11+ and MetaTrader 5. Open MT5 and log in to a DEMO account for testing.
2. Create and activate a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\activate
```

3. Install and launch:

```powershell
pip install -r requirements.txt
python main.py
```

The app connects to the already-open MT5 terminal; credentials are not collected or stored. Ensure XAUUSD (or your broker's suffixed gold symbol) is visible in Market Watch.

## Included

- MT5 closed-bar feed for M1, M5, M15, H1, H4, D1.
- Indicator view: RSI, MACD histogram, tick-volume pressure, EMA20/EMA50, and confirmed swing pivots (ZigZag-like context, not a predictive signal).
- Explainable weighted timeframe scoring; it is a technical alignment heuristic, not a success percentage.
- Broker-based position sizing through `order_calc_profit` / `order_calc_margin`, with a hard estimated-loss cap of $5 and 10% cost buffer.
- Manual signals by default; optional automation is restricted in code to verified MT5 demo accounts, asks for confirmation, deduplicates per signal bar, and allows one open position per symbol.

## Safety limitations

The app does not guarantee a maximum realized loss. Gaps, spread, commissions, execution failures, and slippage may cause losses above an estimated cap. Automatic mode can submit demo orders; it is not evidence that a strategy is profitable. Validate with historical out-of-sample data and demo trading before considering any other use. This build blocks automatic orders on real accounts.
