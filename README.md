# Trading research desktop app

Windows desktop research dashboard for MetaTrader 5. It reads completed broker candles, presents multi-timeframe indicator context, and offers a manual review workflow. Scores are heuristic indicator alignment—not win probabilities or claims of profitability.

## Run (Windows)

Install Python 3.11+ and MetaTrader 5, open MT5, log into a demo account, then:

```powershell
py -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

The app connects to the already-open MT5 terminal. Credentials are not collected or stored. Broker symbols may have suffixes; presets include XAUUSD, XAGUSD, EURUSD, and GBPUSD.

## Features

- M1/M5/M15/H1/H4/D1 data, multi-symbol chart, RSI, MACD histogram, tick-volume pressure, EMA trend, and confirmed swing-pivot context.
- Per-bot lot and ATR stop-distance editor.
- Signal queue with approve/reject and an order-ticket review tab; approval rechecks broker quote, margin, and estimated risk.
- Dark terminal UI, compact market cards, and buy/sell color-coded signal rows.
- Local strategy activity report in `strategy_activity.csv`, viewable/exportable from Strategy reports.
- Historical backtest with CSV export; simulation outcomes are not forecasts.
- Telegram Desktop JSON export import and Bot API polling for authorized new channel posts. Research channel: https://t.me/kingxauusd1. Telegram posts remain unverified, require review, and are never automatically sent to the order engine.

## Live order and emergency controls

Live mode is **manual approval only**: the separate real-orders control displays a risk warning and requires two confirmations; every queued order requires an additional per-order confirmation and broker-based sizing check. Live automatic trading is not supported. The $5 risk figure is an estimate, not a guaranteed cap; gaps, spread, commissions, slippage, stop rejection, outages, and execution can produce larger losses.

Emergency stop disarms app modes and requests closure/cancellation only for positions and pending orders tagged with this application's magic number. It does not touch unrelated trades and cannot guarantee broker execution. Verify the account state in MT5 immediately. Test with a demo account first. This tool is not financial advice and does not guarantee profitability.
