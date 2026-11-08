from __future__ import annotations

import logging
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .backtest import Backtester
from .bot_manager import BotManager
from .config import MqlConfig
from .mt5_client import MT5Connection
from .risk_manager import RiskManager
from .strategy_engine import TIMEFRAMES
from .telegram_ingest import CHANNEL_LINK, parse_telegram_export, poll_authorized_channel_updates

logger = logging.getLogger(__name__)


class TradingFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master.title("DR Gold Research — MT5")
        self.master.geometry("1450x960")
        self.pack(fill="both", expand=True)
        self.config = MqlConfig()
        self.bot_manager = BotManager()
        self.mt5 = MT5Connection(self.config)
        self.risk_manager = RiskManager(self.mt5, self.config.max_risk_usd)
        self.backtester = Backtester()
        self.market_data = {}
        self.last_signal = None
        self.last_auto_key = None
        self.telegram_offset = None
        self.telegram_messages = []
        self._build_ui()
        self._select_first_bot()
        self.master.protocol("WM_DELETE_WINDOW", self.close_app)

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Button(top, text="Connect to open MT5 terminal", command=self.connect_mt5).pack(side="left", padx=4)
        ttk.Button(top, text="Refresh now", command=self.refresh_market).pack(side="left", padx=4)
        self.connection_var = tk.StringVar(value="Disconnected — signals require live MT5 data")
        ttk.Label(top, textvariable=self.connection_var).pack(side="left", padx=12)
        self.mode_var = tk.StringVar(value="MANUAL / SIGNALS ONLY")
        ttk.Label(top, textvariable=self.mode_var, foreground="#a33").pack(side="right", padx=8)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=4)
        market, bots, risk, telegram, backtest = (ttk.Frame(self.nb) for _ in range(5))
        self.nb.add(market, text="Market dashboard")
        self.nb.add(bots, text="Bot editor & scores")
        self.nb.add(risk, text="Risk & execution")
        self.nb.add(telegram, text="Telegram research")
        self.nb.add(backtest, text="Backtest & CSV")
        self._build_market_tab(market)
        self._build_bots_tab(bots)
        self._build_risk_tab(risk)
        self._build_telegram_tab(telegram)
        self._build_backtest_tab(backtest)

        bottom = ttk.LabelFrame(self, text="Activity log")
        bottom.pack(fill="x", padx=10, pady=(2, 8))
        self.log = tk.Text(bottom, height=4, wrap="word")
        self.log.pack(fill="x", padx=5, pady=5)
        self._log("Ready. Telegram signals are research inputs only; no external signal is auto-traded.")

    def _build_market_tab(self, parent):
        controls = ttk.Frame(parent)
        controls.pack(fill="x", padx=6, pady=5)
        ttk.Label(controls, text="Symbol").pack(side="left")
        self.symbol_var = tk.StringVar(value="XAUUSD")
        self.symbol_box = ttk.Combobox(controls, textvariable=self.symbol_var, values=("XAUUSD", "XAGUSD", "EURUSD"), width=12, state="readonly")
        self.symbol_box.pack(side="left", padx=5)
        self.symbol_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_market())
        ttk.Label(controls, text="Chart timeframe").pack(side="left", padx=(12, 0))
        self.chart_tf_var = tk.StringVar(value="M15")
        self.chart_tf_box = ttk.Combobox(controls, textvariable=self.chart_tf_var, values=TIMEFRAMES, width=8, state="readonly")
        self.chart_tf_box.pack(side="left", padx=5)
        self.chart_tf_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_market())
        self.quote_var = tk.StringVar(value="Bid/ask: —")
        ttk.Label(controls, textvariable=self.quote_var).pack(side="right", padx=6)
        self.figure = Figure(figsize=(12, 7), dpi=95)
        grid = self.figure.add_gridspec(4, 1, height_ratios=[3, 1, 1, 1], hspace=0.12)
        self.ax_price = self.figure.add_subplot(grid[0])
        self.ax_rsi = self.figure.add_subplot(grid[1], sharex=self.ax_price)
        self.ax_macd = self.figure.add_subplot(grid[2], sharex=self.ax_price)
        self.ax_volume = self.figure.add_subplot(grid[3], sharex=self.ax_price)
        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=4)
        self.signal_var = tk.StringVar(value="Connect to MT5 and refresh to load completed candles. No synthetic data is used.")
        ttk.Label(parent, textvariable=self.signal_var, wraplength=1300).pack(fill="x", padx=10, pady=6)

    def _build_bots_tab(self, parent):
        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=8, pady=8)
        ttk.Label(left, text="Strategy modules").pack(anchor="w")
        self.bot_tree = ttk.Treeview(left, show="tree", height=12)
        self.bot_tree.pack(fill="y", expand=True)
        for bot in self.bot_manager.get_bots():
            self.bot_tree.insert("", "end", text=bot.name)
        self.bot_tree.bind("<<TreeviewSelect>>", self.on_bot_selected)
        right = ttk.Frame(parent)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        editor = ttk.LabelFrame(right, text="Selected bot controls")
        editor.pack(fill="x", pady=(0, 6))
        ttk.Label(editor, text="Max lots").grid(row=0, column=0, padx=6, pady=6)
        self.bot_lots_var = tk.StringVar(value="0.01")
        ttk.Entry(editor, textvariable=self.bot_lots_var, width=10).grid(row=0, column=1, padx=6)
        ttk.Label(editor, text="Stop distance (ATR multiplier)").grid(row=0, column=2, padx=6)
        self.stop_atr_var = tk.StringVar(value="1.5")
        ttk.Entry(editor, textvariable=self.stop_atr_var, width=8).grid(row=0, column=3, padx=6)
        ttk.Button(editor, text="Apply to selected bot", command=self.apply_bot_editor).grid(row=0, column=4, padx=8)
        self.bot_details = tk.Text(right, wrap="word", height=9)
        self.bot_details.pack(fill="both", expand=True)
        ttk.Label(right, text="Per-timeframe score 0–100 (heuristic; not a win probability)").pack(anchor="w", pady=(6, 2))
        self.score_tree = ttk.Treeview(right, columns=("tf", "score", "direction", "rsi", "macd", "volume", "trend"), show="headings", height=6)
        for col, title, width in [("tf", "TF", 55), ("score", "Score", 70), ("direction", "Bias", 90), ("rsi", "RSI", 70), ("macd", "MACD hist", 100), ("volume", "Vol pressure", 100), ("trend", "EMA trend", 90)]:
            self.score_tree.heading(col, text=title)
            self.score_tree.column(col, width=width, anchor="center")
        self.score_tree.pack(fill="x")

    def _build_risk_tab(self, parent):
        controls = ttk.LabelFrame(parent, text="Safety-first controls")
        controls.pack(fill="x", padx=12, pady=12)
        ttk.Label(controls, text="Order size ceiling (lots)").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.lots_var = tk.StringVar(value="0.01")
        ttk.Entry(controls, textvariable=self.lots_var, width=12).grid(row=0, column=1, padx=8, pady=8)
        ttk.Label(controls, text="Hard estimated-loss cap: $5 per trade (buffered; realized loss can exceed this)").grid(row=0, column=2, sticky="w", padx=8)
        self.demo_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Demo-only guard (required)", variable=self.demo_var, state="disabled").grid(row=1, column=0, columnspan=2, sticky="w", padx=8)
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Automatic execution (demo only; confirm to arm)", variable=self.auto_var, command=self.toggle_auto).grid(row=1, column=2, sticky="w", padx=8)
        ttk.Label(controls, text="Real-account orders are blocked. MT5 credentials remain in terminal and are not stored.").grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=8)
        self.risk_text = tk.Text(parent, wrap="word", height=16)
        self.risk_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.risk_text.insert("end", "Sizing uses broker order_calc_profit/order_calc_margin plus 10% cost buffer. Estimated cap is not guaranteed under gaps, spread, commissions or slippage. Demo only.\n")

    def _build_telegram_tab(self, parent):
        ttk.Label(parent, text=f"Configured channel: {CHANNEL_LINK}\nMessages are unverified research material. Import only content you are authorized to use. Candidate signals are never sent to the order engine.", justify="left", wraplength=1250).pack(anchor="w", padx=12, pady=10)
        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=12)
        ttk.Button(actions, text="Import Telegram Desktop JSON export", command=self.import_telegram_export).pack(side="left", padx=4)
        ttk.Button(actions, text="Poll new posts (authorized channel bot)", command=self.poll_telegram).pack(side="left", padx=4)
        self.telegram_status = tk.StringVar(value="For Bot API polling, create your own bot, add it as channel admin, then set TELEGRAM_BOT_TOKEN in your local environment. Public-channel history is not fetched.")
        ttk.Label(parent, textvariable=self.telegram_status, wraplength=1250).pack(anchor="w", padx=12, pady=8)
        self.telegram_tree = ttk.Treeview(parent, columns=("date", "symbol", "side", "entry", "stop", "target", "review"), show="headings", height=12)
        for col, title, width in [("date", "Date", 150), ("symbol", "Candidate", 90), ("side", "Direction", 90), ("entry", "Entry", 80), ("stop", "Stop", 80), ("target", "Target", 80), ("review", "Review status", 180)]:
            self.telegram_tree.heading(col, text=title)
            self.telegram_tree.column(col, width=width, anchor="center")
        self.telegram_tree.pack(fill="both", expand=True, padx=12, pady=8)
        self.telegram_text = tk.Text(parent, height=7, wrap="word")
        self.telegram_text.pack(fill="x", padx=12, pady=(0, 12))
        self.telegram_tree.bind("<<TreeviewSelect>>", self.show_telegram_message)

    def _build_backtest_tab(self, parent):
        controls = ttk.Frame(parent)
        controls.pack(fill="x", padx=12, pady=10)
        ttk.Label(controls, text="Symbol").pack(side="left")
        self.bt_symbol_var = tk.StringVar(value="XAUUSD")
        ttk.Combobox(controls, textvariable=self.bt_symbol_var, values=("XAUUSD", "XAGUSD", "EURUSD"), width=10, state="readonly").pack(side="left", padx=5)
        ttk.Label(controls, text="Timeframe").pack(side="left", padx=(10, 0))
        self.bt_tf_var = tk.StringVar(value="M15")
        ttk.Combobox(controls, textvariable=self.bt_tf_var, values=TIMEFRAMES, width=7, state="readonly").pack(side="left", padx=5)
        ttk.Label(controls, text="Lots").pack(side="left", padx=(10, 0))
        self.bt_lots_var = tk.StringVar(value="0.01")
        ttk.Entry(controls, textvariable=self.bt_lots_var, width=8).pack(side="left", padx=5)
        ttk.Button(controls, text="Run on loaded MT5 history", command=self.run_backtest).pack(side="left", padx=8)
        ttk.Button(controls, text="Export trades CSV", command=self.export_backtest).pack(side="left", padx=4)
        self.bt_summary = tk.StringVar(value="Connect to MT5, then run a backtest. Historical results are not a forecast.")
        ttk.Label(parent, textvariable=self.bt_summary, wraplength=1300).pack(anchor="w", padx=12, pady=6)
        self.bt_tree = ttk.Treeview(parent, columns=("time", "direction", "entry", "exit", "reason", "net"), show="headings", height=16)
        for col, title, width in [("time", "Entry time", 180), ("direction", "Side", 90), ("entry", "Entry", 100), ("exit", "Exit", 100), ("reason", "Exit reason", 120), ("net", "Net P/L estimate USD", 150)]:
            self.bt_tree.heading(col, text=title)
            self.bt_tree.column(col, width=width, anchor="center")
        self.bt_tree.pack(fill="both", expand=True, padx=12, pady=8)
        self.backtest_trades = []
        ttk.Label(parent, text="Simulation enters at the next bar open, applies estimated spread/commission inputs (default zero where unavailable), and assumes stop first if stop and target touch in one bar.", wraplength=1250).pack(anchor="w", padx=12, pady=6)

    def _log(self, text):
        if hasattr(self, "log"):
            self.log.insert("end", f"{time.strftime('%H:%M:%S')}  {text}\n")
            self.log.see("end")

    def _selected_bot(self):
        selected = self.bot_tree.selection()
        name = self.bot_tree.item(selected[0], "text") if selected else None
        return next((bot for bot in self.bot_manager.get_bots() if bot.name == name), None)

    def _select_first_bot(self):
        items = self.bot_tree.get_children()
        if items:
            self.bot_tree.selection_set(items[0])
            self.on_bot_selected(None)

    def connect_mt5(self):
        try:
            if self.mt5.connect():
                account = self.mt5.get_account_info()
                label = "DEMO" if self.mt5.is_demo_account() else "REAL/OTHER"
                self.connection_var.set(f"Connected | {label} | {account.server}")
                self._log(f"MT5 connected ({label}); credentials not stored.")
                self.refresh_market()
            else:
                self.connection_var.set("Could not connect — open and log in to MT5 first")
        except Exception as exc:
            self._log(f"MT5 connection error: {exc}")

    def apply_bot_editor(self):
        bot = self._selected_bot()
        if not bot:
            return
        try:
            lots, atr_mult = float(self.bot_lots_var.get()), float(self.stop_atr_var.get())
            if lots <= 0 or not 0.1 <= atr_mult <= 10:
                raise ValueError("Lots must be positive and ATR multiplier between 0.1 and 10.")
            bot.max_trade_size_lots = lots
            bot.settings["stop_atr_multiplier"] = atr_mult
            self._log(f"Updated {bot.name}: size ceiling {lots} lots, stop {atr_mult} ATR.")
            if self.mt5.connected:
                self.refresh_market()
        except ValueError as exc:
            messagebox.showerror("Invalid bot settings", str(exc))

    def on_bot_selected(self, _event):
        bot = self._selected_bot()
        if bot:
            self.bot_lots_var.set(str(bot.max_trade_size_lots))
            self.stop_atr_var.set(str(bot.settings.get("stop_atr_multiplier", 1.5)))
            if self.mt5.connected:
                self.refresh_market()
            else:
                self.bot_details.delete("1.0", "end")
                self.bot_details.insert("end", f"{bot.name}\n{bot.description}\nConnect MT5 to obtain broker candles. No synthetic prices are used.\n")

    def toggle_auto(self):
        if not self.auto_var.get():
            self.mode_var.set("MANUAL / SIGNALS ONLY")
            return
        if not self.mt5.connected or not self.demo_var.get() or not self.mt5.is_demo_account():
            self.auto_var.set(False)
            messagebox.showwarning("Demo required", "Automatic orders are restricted to a verified MT5 demo account.")
            return
        if not messagebox.askyesno("Arm demo automation?", "Only the selected strategy can submit demo orders. Telegram messages are never auto-traded. Continue?"):
            self.auto_var.set(False)
            return
        self.mode_var.set("DEMO AUTO — LIVE ACCOUNTS BLOCKED")

    def refresh_market(self):
        if not self.mt5.connected:
            self.signal_var.set("No live feed. Connect to the open MT5 terminal; synthetic data is never substituted.")
            return
        bot = self._selected_bot()
        if not bot:
            return
        requested_symbol = self.symbol_var.get()
        try:
            symbol, data = self.mt5.get_market_data(requested_symbol, TIMEFRAMES, self.config.candle_count)
            self.market_data = data
            signal = self.bot_manager.evaluate(symbol, data, bot)
            self.last_signal = signal
            self._render_signal(bot, signal)
            self._render_scores(signal)
            self._render_chart(signal)
            tick = self.mt5.get_tick(symbol)
            if tick:
                self.quote_var.set(f"Bid {tick.bid:.3f} / Ask {tick.ask:.3f}")
            if self.auto_var.get() and symbol.startswith("XAU"):
                self._maybe_demo_order(bot, signal)
        except Exception as exc:
            self.signal_var.set(f"Market data error: {exc}")
            self._log(f"Refresh failed: {exc}")

    def _render_signal(self, bot, signal):
        stop, target = signal.get("stop_loss"), signal.get("take_profit")
        self.signal_var.set(f"{signal['symbol']} | {bot.name} | {signal.get('direction','neutral').upper()} | score {signal.get('confidence',0)} (not probability) | entry {signal.get('entry',0):.3f} | SL {stop} | TP {target}")
        self.bot_details.delete("1.0", "end")
        self.bot_details.insert("end", f"{bot.name}\n{bot.description}\n\nDirection: {signal.get('direction')}\nAlignment score: {signal.get('confidence')} (heuristic, not win probability)\nTF agreement: {signal.get('alignment')}%\nEntry reference: {signal.get('entry')}\nATR stop: {stop}\nTarget: {target}\n\n{signal.get('reason')}\n")
        for tf in TIMEFRAMES:
            item = signal.get("timeframes", {}).get(tf, {})
            if item.get("valid"):
                self.bot_details.insert("end", f"{tf}: {item['direction']} {item['score']} — {'; '.join(item['reasons'])}\n")

    def _render_scores(self, signal):
        for child in self.score_tree.get_children():
            self.score_tree.delete(child)
        for tf in TIMEFRAMES:
            item = signal.get("timeframes", {}).get(tf, {})
            if item.get("valid"):
                self.score_tree.insert("", "end", values=(tf, item["score"], item["direction"], f"{item['rsi']:.1f}", f"{item['macd_hist']:.5f}", f"{item['volume_pressure']:.2f}", "up" if item["ema20"] > item["ema50"] else "down"))

    def _render_chart(self, signal):
        tf = self.chart_tf_var.get()
        result = signal.get("timeframes", {}).get(tf)
        if not result or not result.get("valid"):
            return
        df = result["dataframe"].tail(150).reset_index(drop=True)
        offset = len(result["dataframe"]) - len(df)
        x = np.arange(len(df))
        for ax in (self.ax_price, self.ax_rsi, self.ax_macd, self.ax_volume):
            ax.clear()
            ax.grid(True, alpha=.2)
        self.ax_price.plot(x, df["close"], label="Close", color="#4c78a8")
        self.ax_price.plot(x, result["ema20_series"].tail(len(df)).to_numpy(), label="EMA20", color="#f58518")
        self.ax_price.plot(x, df["close"].ewm(span=50, adjust=False).mean(), label="EMA50", color="#54a24b")
        for idx, price in result["zigzag_highs"] + result["zigzag_lows"]:
            if offset <= idx < offset + len(df):
                self.ax_price.scatter(idx-offset, price, s=24, color="#b279a2")
        self.ax_price.set_title(f"{signal['symbol']} {tf} | closed bars, confirmed pivots may lag")
        self.ax_price.legend(loc="upper left", ncol=3, fontsize=8)
        self.ax_rsi.plot(x, result["rsi_series"].tail(len(df)).to_numpy(), color="#e45756")
        self.ax_rsi.axhline(70, linestyle="--", linewidth=.8, color="gray")
        self.ax_rsi.axhline(30, linestyle="--", linewidth=.8, color="gray")
        self.ax_rsi.set_ylabel("RSI")
        hist = result["macd_hist_series"].tail(len(df)).to_numpy()
        self.ax_macd.bar(x, hist, color=np.where(hist >= 0, "#54a24b", "#e45756"), width=.8)
        self.ax_macd.set_ylabel("MACD")
        pressure = result["volume_pressure_series"].tail(len(df)).to_numpy()
        self.ax_volume.bar(x, pressure, color=np.where(pressure >= 0, "#54a24b", "#e45756"), width=.8)
        self.ax_volume.axhline(0, color="gray", linewidth=.8)
        self.ax_volume.set_ylabel("Vol pressure")
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _maybe_demo_order(self, bot, signal):
        if signal.get("direction") not in ("long", "short") or not self.mt5.is_demo_account():
            return
        try:
            import MetaTrader5 as mt5
            bars = self.market_data.get(bot.default_timeframe, [])
            if len(bars) == 0:
                return
            key = (bot.name, signal["symbol"], int(bars[-1]["time"]))
            if key == self.last_auto_key or mt5.positions_get(symbol=signal["symbol"]):
                return
            tick = self.mt5.get_tick(signal["symbol"])
            info = self.mt5.get_symbol_info(signal["symbol"])
            if not tick or not info:
                return
            entry = tick.ask if signal["direction"] == "long" else tick.bid
            dist = float(signal.get("stop_distance") or 0)
            if dist <= 0:
                return
            stop = entry - dist if signal["direction"] == "long" else entry + dist
            target = entry + 1.5*dist if signal["direction"] == "long" else entry - 1.5*dist
            lots = min(float(self.lots_var.get()), bot.max_trade_size_lots)
            sized = self.risk_manager.size_position(signal["symbol"], signal["direction"], entry, stop, lots, bot.max_trade_size_lots)
            if not sized["ok"]:
                self._log(f"Risk blocked demo order: {sized['reason']}")
                self.last_auto_key = key
                return
            result = self.mt5.send_market_order(signal["symbol"], signal["direction"], sized["volume"], round(stop, info.digits), round(target, info.digits), bot.name)
            self._log(f"Demo order {result.order}, estimated buffered risk ${sized['buffered_loss']:.2f}.")
            self.last_auto_key = key
        except Exception as exc:
            self._log(f"Demo order blocked/failed: {exc}")

    def import_telegram_export(self):
        path = filedialog.askopenfilename(title="Select authorized Telegram Desktop export", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            messages = parse_telegram_export(path)
            self._add_telegram_messages(messages)
            self.telegram_status.set(f"Imported {len(messages)} messages from local export. Candidate parsing is unverified and requires human review.")
        except Exception as exc:
            messagebox.showerror("Telegram import failed", str(exc))

    def poll_telegram(self):
        try:
            messages, self.telegram_offset = poll_authorized_channel_updates(offset=self.telegram_offset)
            self._add_telegram_messages(messages)
            self.telegram_status.set(f"Received {len(messages)} new channel posts from authorized Bot API updates. Historical posts are not fetched.")
        except Exception as exc:
            self.telegram_status.set(str(exc))
            self._log(f"Telegram polling unavailable: {exc}")

    def _add_telegram_messages(self, messages):
        for message in messages:
            self.telegram_messages.append(message)
            candidate = message["candidate"]
            self.telegram_tree.insert("", "end", iid=f"tg{len(self.telegram_messages)}", values=(message.get("date"), candidate.get("candidate_symbol") or "—", candidate.get("candidate_direction"), candidate.get("candidate_entry") or "—", candidate.get("candidate_stop") or "—", candidate.get("candidate_target") or "—", "UNVERIFIED — review"))

    def show_telegram_message(self, _event):
        selected = self.telegram_tree.selection()
        if not selected:
            return
        index = int(selected[0][2:]) - 1
        if 0 <= index < len(self.telegram_messages):
            item = self.telegram_messages[index]
            self.telegram_text.delete("1.0", "end")
            self.telegram_text.insert("end", f"Source: {item['source']}\nDate: {item.get('date')}\nCandidate extraction: {item['candidate']}\n\n{item['text']}\n\nUNVERIFIED. Not a trade recommendation; never auto-executed.")

    def run_backtest(self):
        if not self.mt5.connected:
            messagebox.showwarning("MT5 required", "Connect to MT5 to load broker history first.")
            return
        symbol_req, tf = self.bt_symbol_var.get(), self.bt_tf_var.get()
        try:
            symbol = self.mt5.resolve_symbol(symbol_req)
            if not symbol:
                raise RuntimeError(f"Broker symbol {symbol_req} not found.")
            bars = self.mt5.get_candles(symbol, tf, count=5000, closed_only=True)
            info = self.mt5.get_symbol_info(symbol)
            if info is None:
                raise RuntimeError("Could not read broker symbol specification.")
            self.backtest_trades, summary = self.backtester.run(bars, symbol, tf, volume_lots=float(self.bt_lots_var.get()), tick_size=float(info.trade_tick_size), tick_value=float(info.trade_tick_value), spread_price=float(info.spread * info.point))
            for row in self.bt_tree.get_children():
                self.bt_tree.delete(row)
            for trade in self.backtest_trades:
                self.bt_tree.insert("", "end", values=(trade["entry_time"], trade["direction"], f"{trade['entry']:.3f}", f"{trade['exit_price']:.3f}", trade["exit_reason"], f"{trade['net_pnl_usd']:.2f}"))
            self.bt_summary.set(f"{symbol} {tf} | trades {summary['trades']} | wins {summary['wins']} | losses {summary['losses']} | win rate {summary['win_rate_pct']:.1f}% | net estimate ${summary['net_pnl_usd']:.2f} | expectancy ${summary['expectancy_usd']:.2f} | max DD ${summary['max_drawdown_usd']:.2f}. Historical simulation, not a forecast.")
            self._log(f"Backtest completed on {len(bars)} closed broker bars; {summary['trades']} simulated trades.")
        except Exception as exc:
            messagebox.showerror("Backtest failed", str(exc))

    def export_backtest(self):
        if not self.backtest_trades:
            messagebox.showinfo("No results", "Run a backtest before exporting.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="trading_backtest.csv")
        if path:
            try:
                self.backtester.export_csv(self.backtest_trades, path)
                self._log(f"Exported backtest CSV: {path}")
            except Exception as exc:
                messagebox.showerror("Export failed", str(exc))

    def close_app(self):
        if self.mt5.connected:
            self.mt5.disconnect()
        self.master.destroy()


def run_app():
    root = tk.Tk()
    TradingFrame(root)
    root.mainloop()
