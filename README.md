# Trading research desktop app

Windows desktop research dashboard for MetaTrader 5. It reads completed broker candles, presents multi-timeframe indicator context, and offers manual review workflow. Scores are heuristic indicator alignment—not win probabilities or claims of profitability.

## Run (Windows)

Install Python 3.11+ and MetaTrader 5, open MT5, log into a demo account, then:

```powershell
py -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

The app connects to the already-open MT5 terminal. Credentials are not collected or stored. Broker symbols may have suffixes; use Market Watch and the supported symbol presets XAUUSD, XAGUSD, EURUSD, GBPUSD.

## Features

- M1/M5/M15/H1/H4/D1 data, multi-symbol chart, RSI, MACD histogram, tick-volume pressure, EMA trend, confirmed swing pivot context.
- Per-bot lot and ATR stop-distance editor.
- Signal queue with approve/reject; approval rechecks broker quote, margin and estimated risk.
- Local strategy activity report in `strategy_activity.csv`, viewable/exportable from Strategy reports.
- Historical backtest with CSV export; simulation outcomes are not forecasts.
- Telegram Desktop JSON export import and Bot API polling for authorized new channel posts. The configured research channel is https://t.me/kingxauusd1. Telegram posts are unverified, require review, and are never automatically sent to the order engine. For polling, create your own bot, add it as channel admin, then set `TELEGRAM_BOT_TOKEN` locally. Never share/commit the token. The Bot API does not retrieve old channel history.

## Trading safety

Manual signal review is the default. The `Enable REAL orders` control presents two risk confirmations and arms **manual, per-signal approval only** for the session; live automatic trading remains disabled. Every approved order has another confirmation and broker-based sizing check. Stop estimate is not a guaranteed loss cap: gaps, spread, commission, slippage, rejected stops, connectivity and execution may cause larger losses.

The emergency-stop control disarms modes and requests closure/cancellation only for positions and pending orders tagged with this application's magic number. It does not touch unrelated manual trades and cannot guarantee broker execution. Verify the account state in MT5 immediately. This is software tooling, not financial advice or a profitability guarantee. Test on demo first.
