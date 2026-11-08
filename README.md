# DR Trading Terminal — XAUUSD

Windows desktop trading research terminal for MetaTrader 5, configured for XAUUSD only. It reads completed broker candles, presents multi-timeframe indicator context, manages a persistent local bot library, and offers manual review plus optional demo-only automatic execution. Scores are heuristic indicator alignment—not win probabilities or claims of profitability.

## Windows installer

The GitHub Actions workflow builds both a portable standalone executable and a Windows setup installer on every push to the feature or main branch.

1. Open the repository's **Actions** tab.
2. Open the latest **Build Windows installer** run.
3. Download the `DRTradingTerminal-Windows` artifact.
4. Run `DRTradingTerminal-Setup.exe` to install, or run `DRTradingTerminal.exe` as a portable application.

The installer creates Start Menu and optional desktop shortcuts. Windows may show a SmartScreen warning because this unsigned community build is not code-signed.

## Run from source (Windows)

Install Python 3.11+ and MetaTrader 5, open MT5, log into a demo account, then:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The app connects to the already-open MT5 terminal. Credentials are not collected or stored. Broker gold symbols with suffixes are resolved from the XAUUSD base symbol where available (for example XAUUSDm).

## Bot Manager

Use **Manage bots** or **Load / manage bots** to open the bot library. It supports:
- Load the saved local bot library at startup.
- Add, edit, duplicate, enable, disable, and delete bots.
- Configure name, default timeframe, minimum heuristic score, stop ATR multiplier, maximum lots, and per-trade risk cap.
- Import and export bot definitions as JSON, and restore the four research defaults.

Bot configurations are stored in the current Windows user's application data directory under `DRTradingTerminal/bots.json`; they persist across app updates and are not stored in the installation folder. The app currently has four starter research bots. A custom bot's description/configuration is saved, but new executable strategy logic still needs to be implemented in the strategy engine.

## Analysis and research

- XAUUSD only; broker suffix resolution through MT5.
- M1/M5/M15/H1/H4/D1 data, RSI, MACD histogram, tick-volume pressure, EMA trend, and confirmed swing-pivot context.
- Signal queue with approve/reject and an order-ticket review tab; approval refreshes broker quote and risk calculations.
- Strategy activity journal in `strategy_activity.csv`, viewable/exportable from Strategy reports.
- Historical backtest with CSV export; simulation outcomes are not forecasts.
- Telegram Desktop JSON export import and Bot API polling for authorized new channel posts. Telegram posts remain unverified, require review, and are never automatically sent to the order engine.


## Signal Hub and external providers

The Signal Hub accepts provider HTTPS RSS/Atom feeds and JSON endpoints. It extracts candidate XAUUSD BUY/SELL messages into a separate review-only list. Feeds must be public or otherwise authorized and use HTTPS; the current adapter has an 8-second timeout and 1 MB response limit. This is a generic feed adapter, not a certified integration with any particular signal vendor. Provider-specific authentication, paid API schemas, webhooks, rate limits, and licensing must be implemented and tested against official provider documentation. Telegram research import/polling remains available separately.

External messages are unverified and never routed to the order queue or execution engine. Verify provider identity, timestamp, symbol, price, stop, target, and market conditions independently. Do not paste provider passwords, API secrets, or account credentials into the feed URL.



Provider configuration is deliberately independent and optional. Add, edit, enable/disable, or remove providers later from the Signal Hub settings panel; the list is stored locally under the current Windows user's AppData (not in the repository). No provider account passwords or API secrets are stored by this settings module. The app can be used without configuring any external provider.

## Appearance

The app applies a shared dark palette to ttk controls, classic Tk text/entry widgets, tables, and the Bot Manager dialog. The Market tab includes compact instrument/signal/score/quote cards, and charts use a matching dark canvas.

## Live order and emergency controls

Demo automatic execution is optional and requires a verified MT5 demo account. Live mode is **manual approval only**: the separate real-orders control displays a risk warning and requires two confirmations; every queued order requires an additional per-order confirmation and broker-based sizing check. Live automatic trading is deliberately disabled.

The $5 risk figure is an estimate, not a guaranteed cap; gaps, spread, commissions, slippage, stop rejection, outages, and execution can produce larger losses. Emergency stop disarms app modes and requests closure/cancellation only for positions and pending orders tagged with this application's magic number. It does not touch unrelated trades and cannot guarantee broker execution. Verify the account state in MT5 immediately. Test with a demo account first. This tool is not financial advice and does not guarantee profitability.
