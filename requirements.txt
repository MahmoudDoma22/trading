# trading

This repository contains an initial desktop trading app prototype for MetaTrader 5 (MT5) with modular strategy bots for XAUUSD and multi-timeframe analysis.

## What is included

- Windows desktop app in Python (Tkinter + Matplotlib)
- MT5 connector wrapper using `MetaTrader5`
- Multi-timeframe strategy engine
- Bot definitions with configurable trade size and risk limits
- Manual and automatic mode toggle
- Signal scoring and trade logs
- Demo / paper-trading friendly defaults

## Important notes

- This is not a guarantee of profitability.
- Live automated trading is disabled by default.
- All strategy outputs should be validated on demo accounts first.
- Risk is controlled with a per-bot max loss and trade-size guardrails.

## Project structure

```text
trading_app/
  __init__.py
  config.py
  mt5_client.py
  strategy_engine.py
  bot_manager.py
  ui.py
main.py
requirements.txt
README.md
.gitignore
```

## Setup on Windows

1. Install Python 3.11+
2. Create a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Start the app:

```powershell
python main.py
```

## MT5 setup

1. Install MetaTrader 5 on your Windows machine.
2. Ensure your broker account is present and you have the right `login`, `password`, and `server`.
3. In the app, choose `Connect to MT5` and fill in your broker settings.
4. Keep automatic trading disabled until your strategy has been backtested and demo validated.

## Strategy design

The app includes indicators such as:

- RSI
- MACD
- Volume trend
- EMA/SMA trend filter
- ZigZag / pivot context
- Multi-timeframe trend alignment (M1, M5, M15, H1, H4, D1)

The app names the custom indicator layer as:

- `DR Built-in RSI, MACD, Volumes`

## Bot configuration

Each bot can be configured with:

- instrument (`XAUUSD`)
- direction (`long`, `short`, or both)
- trade size in lots or USD-equivalent
- max risk per trade in USD
- automatic / manual mode
- confidence score thresholds
- stop-loss / take-profit rules

## Example bot list

- DR Trend Momentum Bot
- DR Range Breakout Bot
- DR Swing Scalper Bot
- DR Safe Pullback Bot

## Future enhancements

- Multi-chart panel
- More advanced signal scoring
- Telegram signal ingestion
- News calendar integration
- Market context from EURUSD/XAGUSD
- Real-time risk engine and order management
- Backtest results viewer

## License

This project is an initial development scaffold for personal and research use. It is not financial advice.
