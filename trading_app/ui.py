from __future__ import annotations

import logging
import time
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .bot_manager import BotManager
from .config import MqlConfig
from .mt5_client import MT5Connection
from .risk_manager import RiskManager
from .strategy_engine import TIMEFRAMES


logger = logging.getLogger(__name__)


class TradingFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master.title("DR Gold Research — MT5")
        self.master.geometry("1380x900")
        self.pack(fill="both", expand=True)
        self.config = MqlConfig()
        self.bot_manager = BotManager()
        self.mt5 = MT5Connection(self.config)
        self.risk_manager = RiskManager(self.mt5, self.config.max_risk_usd)
        self.market_data = {}
        self.last_signal = None
        self.last_auto_key = None
        self._closing = False
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

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=4)
        market = ttk.Frame(nb)
        bots = ttk.Frame(nb)
        risk = ttk.Frame(nb)
        nb.add(market, text="Live market & indicators")
        nb.add(bots, text="Bots & timeframe scores")
        nb.add(risk, text="Risk & execution controls")

        self.figure = Figure(figsize=(11, 7), dpi=95)
        grid = self.figure.add_gridspec(4, 1, height_ratios=[3, 1, 1, 1], hspace=0.12)
        self.ax_price = self.figure.add_subplot(grid[0])
        self.ax_rsi = self.figure.add_subplot(grid[1], sharex=self.ax_price)
        self.ax_macd = self.figure.add_subplot(grid[2], sharex=self.ax_price)
        self.ax_volume = self.figure.add_subplot(grid[3], sharex=self.ax_price)
        self.canvas = FigureCanvasTkAgg(self.figure, master=market)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)
        self.signal_var = tk.StringVar(value="Connect to MT5 and refresh to load completed candles. No synthetic data is used.")
        ttk.Label(market, textvariable=self.signal_var, wraplength=1200).pack(fill="x", padx=10, pady=6)

        bot_left = ttk.Frame(bots)
        bot_left.pack(side="left", fill="y", padx=8, pady=8)
        ttk.Label(bot_left, text="Strategy modules").pack(anchor="w")
        self.bot_tree = ttk.Treeview(bot_left, show="tree", height=12)
        self.bot_tree.pack(fill="y", expand=True)
        for bot in self.bot_manager.get_bots():
            self.bot_tree.insert("", "end", text=bot.name)
        self.bot_tree.bind("<<TreeviewSelect>>", self.on_bot_selected)
        bot_right = ttk.Frame(bots)
        bot_right.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.bot_details = tk.Text(bot_right, wrap="word", height=10)
        self.bot_details.pack(fill="both", expand=True)
        ttk.Label(bot_right, text="Per-timeframe indicator score (0–100; not probability)").pack(anchor="w", pady=(8, 2))
        self.score_tree = ttk.Treeview(bot_right, columns=("score", "direction", "rsi", "macd", "volume", "trend"), show="headings", height=7)
        for col, title, width in [("score", "Score", 70), ("direction", "Bias", 90), ("rsi", "RSI", 80), ("macd", "MACD hist", 100), ("volume", "Vol pressure", 100), ("trend", "EMA trend", 100)]:
            self.score_tree.heading(col, text=title)
            self.score_tree.column(col, width=width, anchor="center")
        self.score_tree.pack(fill="x")

        controls = ttk.LabelFrame(risk, text="Safety-first controls")
        controls.pack(fill="x", padx=12, pady=12)
        ttk.Label(controls, text="Order size ceiling (lots)").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.lots_var = tk.StringVar(value="0.01")
        ttk.Entry(controls, textvariable=self.lots_var, width=12).grid(row=0, column=1, padx=8, pady=8)
        ttk.Label(controls, text="Hard estimated-loss cap: $5 per trade (buffered; realized loss may exceed this)").grid(row=0, column=2, sticky="w", padx=8, pady=8)
        self.demo_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Demo-only order guard (required)", variable=self.demo_var, state="disabled").grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Automatic execution (demo account only; explicit confirmation)", variable=self.auto_var, command=self.toggle_auto).grid(row=1, column=2, sticky="w", padx=8, pady=8)
        ttk.Label(controls, text="Live-account orders are blocked in this build. MT5 account login stays in the terminal; credentials are not stored here.").grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=8)
        self.risk_text = tk.Text(risk, wrap="word", height=18)
        self.risk_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.risk_text.insert("end", "Risk sizing uses the broker's order_calc_profit and order_calc_margin for the selected symbol, plus a 10% execution-cost buffer. Trades are rejected if the estimate exceeds $5, broker minimum volume is too large, or required margin exceeds 80% of free margin. Gaps, spread changes, rejection and slippage mean a $5 maximum realized loss cannot be guaranteed.\n\nAutomatic execution is disabled by default and demo-only. Strategy scores are technical alignment heuristics, not win probabilities or evidence of profitability. Validate on historical data and an MT5 demo account.\n")

        bottom = ttk.LabelFrame(self, text="Activity log")
        bottom.pack(fill="x", padx=10, pady=(2, 8))
        self.log = tk.Text(bottom, height=5, wrap="word")
        self.log.pack(fill="x", padx=5, pady=5)
        self._log("Ready. No orders are sent unless demo automatic mode is explicitly armed.")

    def _log(self, text: str):
        if hasattr(self, "log"):
            self.log.insert("end", f"{time.strftime('%H:%M:%S')}  {text}\n")
            self.log.see("end")

    def _select_first_bot(self):
        children = self.bot_tree.get_children()
        if children:
            self.bot_tree.selection_set(children[0])
            self.on_bot_selected(None)

    def _selected_bot(self):
        selected = self.bot_tree.selection()
        name = self.bot_tree.item(selected[0], "text") if selected else None
        return next((bot for bot in self.bot_manager.get_bots() if bot.name == name), None)

    def connect_mt5(self):
        try:
            if self.mt5.connect():
                account = self.mt5.get_account_info()
                label = "DEMO" if self.mt5.is_demo_account() else "REAL/OTHER"
                self.connection_var.set(f"Connected | {label} | {account.server} | {self.mt5.symbol}")
                self._log(f"Connected to terminal account mode: {label}. Account data is not persisted.")
                self.refresh_market()
            else:
                self.connection_var.set("Could not connect — open and log in to MT5 first")
                self._log("MT5 initialize failed; open the terminal and log in, then retry.")
        except Exception as exc:
            self.connection_var.set("MT5 unavailable")
            self._log(f"MT5 connection error: {exc}")

    def toggle_auto(self):
        if not self.auto_var.get():
            self.mode_var.set("MANUAL / SIGNALS ONLY")
            self._log("Automatic execution disabled.")
            return
        if not self.mt5.connected or not self.demo_var.get():
            self.auto_var.set(False)
            messagebox.showwarning("Demo account required", "Connect to MT5 and confirm the account is demo. Live-account trading is blocked.")
            return
        try:
            if not self.mt5.is_demo_account():
                self.auto_var.set(False)
                self.mode_var.set("MANUAL / SIGNALS ONLY")
                messagebox.showwarning("Live account blocked", "Automatic orders are restricted to a verified MT5 demo account.")
                return
        except Exception as exc:
            self.auto_var.set(False)
            messagebox.showerror("Account check failed", str(exc))
            return
        if not messagebox.askyesno("Arm demo automation?", "This enables the selected research bot to submit orders on the connected DEMO account when you press Refresh. It does not guarantee outcomes. Continue?"):
            self.auto_var.set(False)
            return
        self.mode_var.set("DEMO AUTO — LIVE ACCOUNTS BLOCKED")
        self._log("Demo automatic execution armed. Each signal bar is deduplicated; one open position per symbol is allowed.")

    def refresh_market(self):
        if not self.mt5.connected:
            self.signal_var.set("No live feed. Connect to the open MT5 terminal; synthetic candles are not used.")
            return
        bot = self._selected_bot()
        if bot is None:
            return
        try:
            symbol, data = self.mt5.get_market_data(bot.instrument, TIMEFRAMES, self.config.candle_count)
            self.market_data = data
            signal = self.bot_manager.evaluate(symbol, data, bot)
            self.last_signal = signal
            self._render_signal(bot, signal)
            self._render_chart(signal)
            self._render_scores(signal)
            if self.auto_var.get():
                self._maybe_demo_order(bot, signal)
        except Exception as exc:
            self.signal_var.set(f"Feed/analysis error: {exc}")
            self._log(f"Market refresh failed: {exc}")

    def _render_signal(self, bot, signal):
        direction = signal.get("direction", "neutral").upper()
        stop = signal.get("stop_loss")
        target = signal.get("take_profit")
        self.signal_var.set(f"{signal['symbol']} | {bot.name} | {direction} | alignment score {signal.get('confidence', 0)} (NOT probability) | entry {signal.get('entry', 0):.3f} | SL {stop if stop is not None else '—'} | TP {target if target is not None else '—'}")
        self.bot_details.delete("1.0", "end")
        self.bot_details.insert("end", f"{bot.name}\n{bot.description}\n\n")
        self.bot_details.insert("end", f"Direction: {direction}\nAlignment score: {signal.get('confidence', 0)} / 100 (heuristic; not a success percentage)\nTF agreement: {signal.get('alignment', 0)}% weighted agreement\nEntry reference: {signal.get('entry', 0):.3f}\nProposed ATR stop: {stop}\nProposed 1.5R target: {target}\n\n{signal.get('reason', '')}\n\n")
        for tf in TIMEFRAMES:
            result = signal.get("timeframes", {}).get(tf, {})
            if result.get("valid"):
                self.bot_details.insert("end", f"{tf}: {result['direction']} score {result['score']} — {'; '.join(result['reasons'])}\n")
            else:
                self.bot_details.insert("end", f"{tf}: unavailable/insufficient closed bars\n")

    def _render_scores(self, signal):
        for item in self.score_tree.get_children():
            self.score_tree.delete(item)
        for tf in TIMEFRAMES:
            result = signal.get("timeframes", {}).get(tf, {})
            if result.get("valid"):
                trend = "up" if result["ema20"] > result["ema50"] else "down"
                self.score_tree.insert("", "end", values=(result["score"], result["direction"], f"{result['rsi']:.1f}", f"{result['macd_hist']:.5f}", f"{result['volume_pressure']:.2f}", trend), text=tf)

    def _render_chart(self, signal):
        result = signal.get("timeframes", {}).get("M15")
        if not result or not result.get("valid"):
            result = next((signal.get("timeframes", {}).get(tf) for tf in ("M5", "H1") if signal.get("timeframes", {}).get(tf, {}).get("valid")), None)
        if not result:
            return
        df = result["dataframe"].tail(120).reset_index(drop=True)
        offset = len(result["dataframe"]) - len(df)
        x = np.arange(len(df))
        for ax in (self.ax_price, self.ax_rsi, self.ax_macd, self.ax_volume):
            ax.clear()
            ax.grid(True, alpha=0.2)
        self.ax_price.plot(x, df["close"], label="Close", color="#4c78a8")
        self.ax_price.plot(x, result["ema20_series"].tail(len(df)).to_numpy(), label="EMA20", color="#f58518")
        # Reconstruct EMA50 from the same timeframe candles.
        ema50 = df["close"].ewm(span=50, adjust=False).mean()
        self.ax_price.plot(x, ema50, label="EMA50", color="#54a24b")
        for idx, price in result["zigzag_highs"] + result["zigzag_lows"]:
            if offset <= idx < offset + len(df):
                self.ax_price.scatter(idx - offset, price, s=22, color="#b279a2")
        self.ax_price.set_title(f"{signal['symbol']} — M15 (completed candles); confirmed pivots can lag")
        self.ax_price.legend(loc="upper left", ncol=3, fontsize=8)
        self.ax_rsi.plot(x, result["rsi_series"].tail(len(df)).to_numpy(), color="#e45756")
        self.ax_rsi.axhline(70, linestyle="--", linewidth=0.8, color="gray")
        self.ax_rsi.axhline(30, linestyle="--", linewidth=0.8, color="gray")
        self.ax_rsi.set_ylabel("RSI")
        hist = result["macd_hist_series"].tail(len(df)).to_numpy()
        self.ax_macd.bar(x, hist, color=np.where(hist >= 0, "#54a24b", "#e45756"), width=0.8)
        self.ax_macd.set_ylabel("MACD hist")
        pressure = result["volume_pressure_series"].tail(len(df)).to_numpy()
        self.ax_volume.bar(x, pressure, color=np.where(pressure >= 0, "#54a24b", "#e45756"), width=0.8)
        self.ax_volume.axhline(0, color="gray", linewidth=0.8)
        self.ax_volume.set_ylabel("Vol pressure")
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _maybe_demo_order(self, bot, signal):
        if signal.get("direction") not in ("long", "short"):
            return
        try:
            if not self.mt5.is_demo_account():
                self.auto_var.set(False)
                raise RuntimeError("Account is no longer demo; auto mode disarmed.")
            tf = bot.default_timeframe
            bars = self.market_data.get(tf, [])
            if bars is None or len(bars) == 0:
                return
            last_bar_time = int(bars[-1]["time"])
            key = (bot.name, signal["symbol"], tf, last_bar_time)
            if key == self.last_auto_key:
                return
            account = self.mt5.get_account_info()
            if account is None:
                return
            import MetaTrader5 as mt5
            positions = mt5.positions_get(symbol=signal["symbol"]) or ()
            if positions:
                self._log("Demo auto skipped: an open position already exists on this symbol.")
                self.last_auto_key = key
                return
            info = self.mt5.get_symbol_info(signal["symbol"])
            tick = self.mt5.get_tick(signal["symbol"])
            if info is None or tick is None or signal.get("stop_loss") is None:
                return
            entry = tick.ask if signal["direction"] == "long" else tick.bid
            # Re-anchor the ATR-distance stop to the current quote to avoid stale chart-price entries.
            distance = float(signal.get("stop_distance") or 0)
            if distance <= 0:
                return
            stop = entry - distance if signal["direction"] == "long" else entry + distance
            target = entry + 1.5 * distance if signal["direction"] == "long" else entry - 1.5 * distance
            requested = min(float(self.lots_var.get()), bot.max_trade_size_lots)
            sizing = self.risk_manager.size_position(signal["symbol"], signal["direction"], entry, stop, requested, bot.max_trade_size_lots)
            if not sizing["ok"]:
                self._log(f"Order blocked by risk guard: {sizing['reason']}")
                self.last_auto_key = key
                return
            result = self.mt5.send_market_order(signal["symbol"], signal["direction"], sizing["volume"], round(stop, info.digits), round(target, info.digits), bot.name)
            self._log(f"DEMO order placed: {signal['direction']} {sizing['volume']} lots; estimated buffered risk ${sizing['buffered_loss']:.2f}; ticket {result.order}.")
            self.last_auto_key = key
        except Exception as exc:
            self._log(f"Demo order blocked/failed: {exc}")

    def on_bot_selected(self, event):
        if self.mt5.connected:
            self.refresh_market()
        else:
            bot = self._selected_bot()
            if bot:
                self.bot_details.delete("1.0", "end")
                self.bot_details.insert("end", f"{bot.name}\n{bot.description}\n\nConnect MT5 to load real broker candles. Synthetic/sample data is never substituted for live feed.\n")

    def close_app(self):
        self._closing = True
        if self.mt5.connected:
            self.mt5.disconnect()
        self.master.destroy()


def run_app():
    root = tk.Tk()
    TradingFrame(root)
    root.mainloop()
