from __future__ import annotations

import logging
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .backtest import Backtester
from .bot_manager_dialog import BotManagerDialog
from .bot_manager import BotManager
from .config import MqlConfig
from .mt5_client import MT5Connection
from .risk_manager import RiskManager
from .strategy_engine import TIMEFRAMES
from .strategy_journal import StrategyJournal
from .telegram_ingest import CHANNEL_LINK, parse_telegram_export, poll_authorized_channel_updates

logger = logging.getLogger(__name__)
SYMBOL_PRESETS = ("XAUUSD",)


class TradingFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master.title("DR Trading Terminal | MT5 Research")
        self.master.geometry("1500x980")
        self.pack(fill="both", expand=True)
        self.config = MqlConfig()
        self.bot_manager = BotManager()
        self.mt5 = MT5Connection(self.config)
        self.risk_manager = RiskManager(self.mt5, self.config.max_risk_usd)
        self.backtester = Backtester()
        self.journal = StrategyJournal()
        self.market_data, self.last_signal = {}, None
        self.last_auto_key = None
        self.telegram_offset, self.telegram_messages = None, []
        self.queue = {}
        self.live_armed = False
        self.auto_var = tk.BooleanVar(value=False)
        self._build_ui()
        self._select_first_bot()
        self.master.protocol("WM_DELETE_WINDOW", self.close_app)

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Emergency.TButton", foreground="white", background="#a00000", font=("Segoe UI", 10, "bold"))
        header = ttk.Frame(self, padding=8)
        header.pack(fill="x")
        ttk.Label(header, text="DR TERMINAL  |  Research / execution", style="Header.TLabel").pack(side="left", padx=5)
        ttk.Button(header, text="Connect MT5", command=self.connect_mt5).pack(side="left", padx=8)
        ttk.Button(header, text="Refresh", command=self.refresh_market).pack(side="left", padx=4)
        ttk.Button(header, text="Manage bots", command=self.open_bot_manager).pack(side="left", padx=4)
        self.connection_var = tk.StringVar(value="Disconnected")
        ttk.Label(header, textvariable=self.connection_var).pack(side="left", padx=10)
        ttk.Button(header, text="Enable REAL orders…", command=self.enable_live).pack(side="right", padx=5)
        ttk.Button(header, text="EMERGENCY STOP — APP TRADES", style="Emergency.TButton", command=self.emergency_stop).pack(side="right", padx=5)
        self.mode_var = tk.StringVar(value="MANUAL • NOT ARMED")
        ttk.Label(header, textvariable=self.mode_var, style="Header.TLabel").pack(side="right", padx=10)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=4)
        tabs = {}
        for key, title in (("market", "Market"), ("bots", "Bot editor"), ("queue", "Signal queue"), ("reports", "Strategy reports"), ("risk", "Risk / modes"), ("telegram", "Telegram research"), ("backtest", "Backtest / CSV")):
            tabs[key] = ttk.Frame(self.nb)
            self.nb.add(tabs[key], text=title)
        self._build_market(tabs["market"])
        self._build_bots(tabs["bots"])
        self._build_queue(tabs["queue"])
        self._build_reports(tabs["reports"])
        self._build_risk(tabs["risk"])
        self._build_telegram(tabs["telegram"])
        self._build_backtest(tabs["backtest"])
        log_frame = ttk.LabelFrame(self, text="Terminal activity", padding=4)
        log_frame.pack(fill="x", padx=8, pady=5)
        self.log = tk.Text(log_frame, height=4, wrap="word")
        self.log.pack(fill="x")
        self._log("Manual review is the default. Live orders require a separate arm action and per-signal approval.")

    def _build_market(self, parent):
        bar = ttk.Frame(parent, padding=5)
        bar.pack(fill="x")
        ttk.Label(bar, text="Instrument").pack(side="left")
        self.symbol_var = tk.StringVar(value="XAUUSD")
        self.symbol_box = ttk.Combobox(bar, textvariable=self.symbol_var, values=SYMBOL_PRESETS, width=12, state="readonly")
        self.symbol_box.pack(side="left", padx=5)
        self.symbol_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_market())
        ttk.Label(bar, text="Chart TF").pack(side="left", padx=(12, 0))
        self.chart_tf_var = tk.StringVar(value="M15")
        ttk.Combobox(bar, textvariable=self.chart_tf_var, values=TIMEFRAMES, width=8, state="readonly").pack(side="left", padx=5)
        ttk.Button(bar, text="Update chart", command=self.refresh_market).pack(side="left", padx=5)
        self.quote_var = tk.StringVar(value="Bid / Ask —")
        ttk.Label(bar, textvariable=self.quote_var).pack(side="right", padx=8)
        self.figure = Figure(figsize=(12, 7), dpi=95, facecolor="#f7f8fa")
        grid = self.figure.add_gridspec(4, 1, height_ratios=(3, 1, 1, 1), hspace=.12)
        self.ax_price = self.figure.add_subplot(grid[0])
        self.ax_rsi = self.figure.add_subplot(grid[1], sharex=self.ax_price)
        self.ax_macd = self.figure.add_subplot(grid[2], sharex=self.ax_price)
        self.ax_volume = self.figure.add_subplot(grid[3], sharex=self.ax_price)
        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=4)
        self.signal_var = tk.StringVar(value="Connect to MT5 to load completed broker candles. No synthetic data.")
        ttk.Label(parent, textvariable=self.signal_var, wraplength=1350, padding=5).pack(fill="x")

    def _build_bots(self, parent):
        left = ttk.Frame(parent, padding=8)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Bots", style="Header.TLabel").pack(anchor="w")
        self.bot_tree = ttk.Treeview(left, show="tree", height=14)
        self.bot_tree.pack(fill="y", expand=True)
        for bot in self.bot_manager.get_bots():
            self.bot_tree.insert("", "end", text=bot.name)
        self.bot_tree.bind("<<TreeviewSelect>>", self.on_bot_selected)
        ttk.Button(left, text="Load / manage bots…", command=self.open_bot_manager).pack(fill="x", pady=5)
        right = ttk.Frame(parent, padding=8)
        right.pack(side="left", fill="both", expand=True)
        editor = ttk.LabelFrame(right, text="Selected bot configuration", padding=8)
        editor.pack(fill="x")
        self.bot_lots_var, self.stop_atr_var = tk.StringVar(value="0.01"), tk.StringVar(value="1.5")
        for i, (label, var) in enumerate((("Max lots", self.bot_lots_var), ("Stop distance (ATR multiplier)", self.stop_atr_var))):
            ttk.Label(editor, text=label).grid(row=0, column=i*2, padx=5)
            ttk.Entry(editor, textvariable=var, width=12).grid(row=0, column=i*2+1, padx=5)
        ttk.Button(editor, text="Apply", command=self.apply_bot_editor).grid(row=0, column=4, padx=12)
        self.bot_details = tk.Text(right, wrap="word", height=8)
        self.bot_details.pack(fill="both", expand=True, pady=6)
        ttk.Label(right, text="Indicator alignment score 0–100; not a win probability").pack(anchor="w")
        self.score_tree = ttk.Treeview(right, columns=("tf", "score", "bias", "rsi", "macd", "vol", "trend"), show="headings", height=6)
        for col, title, width in (("tf", "TF", 55), ("score", "Score", 70), ("bias", "Direction", 90), ("rsi", "RSI", 70), ("macd", "MACD hist", 100), ("vol", "Vol press", 90), ("trend", "EMA trend", 90)):
            self.score_tree.heading(col, text=title); self.score_tree.column(col, width=width, anchor="center")
        self.score_tree.pack(fill="x")

    def _build_queue(self, parent):
        ttk.Label(parent, text="Signals await your review. Approve performs a fresh quote and risk check; Telegram items are never routed here automatically.", wraplength=1300).pack(anchor="w", padx=10, pady=8)
        self.queue_tree = ttk.Treeview(parent, columns=("time", "symbol", "bot", "side", "score", "entry", "stop", "target", "status"), show="headings", height=14)
        for col, title, width in (("time", "Created", 145), ("symbol", "Symbol", 85), ("bot", "Strategy", 210), ("side", "Direction", 80), ("score", "Score", 65), ("entry", "Entry ref", 90), ("stop", "Stop", 90), ("target", "Target", 90), ("status", "Status", 130)):
            self.queue_tree.heading(col, text=title); self.queue_tree.column(col, width=width, anchor="center")
        self.queue_tree.pack(fill="both", expand=True, padx=10, pady=6)
        actions = ttk.Frame(parent, padding=8); actions.pack(fill="x")
        ttk.Button(actions, text="Approve selected (review + risk check)", command=self.approve_signal).pack(side="left", padx=4)
        ttk.Button(actions, text="Reject selected", command=self.reject_signal).pack(side="left", padx=4)

    def _build_reports(self, parent):
        bar = ttk.Frame(parent, padding=8); bar.pack(fill="x")
        ttk.Button(bar, text="Refresh report", command=self.refresh_report).pack(side="left")
        ttk.Button(bar, text="Export report CSV…", command=self.export_report).pack(side="left", padx=6)
        self.report_summary = tk.StringVar(value="Signal and action log is stored locally in strategy_activity.csv.")
        ttk.Label(parent, textvariable=self.report_summary, wraplength=1300).pack(anchor="w", padx=10)
        self.report_tree = ttk.Treeview(parent, columns=("time", "event", "symbol", "bot", "side", "score", "status", "detail"), show="headings", height=17)
        for col, title, width in (("time", "UTC time", 180), ("event", "Event", 100), ("symbol", "Symbol", 85), ("bot", "Bot", 190), ("side", "Side", 75), ("score", "Score", 70), ("status", "Status", 100), ("detail", "Details", 400)):
            self.report_tree.heading(col, text=title); self.report_tree.column(col, width=width, anchor="w")
        self.report_tree.pack(fill="both", expand=True, padx=10, pady=8)

    def _build_risk(self, parent):
        box = ttk.LabelFrame(parent, text="Execution guardrails", padding=10); box.pack(fill="x", padx=12, pady=12)
        self.lots_var = tk.StringVar(value="0.01")
        ttk.Label(box, text="Default requested lots").grid(row=0, column=0, padx=5, pady=6)
        ttk.Entry(box, textvariable=self.lots_var, width=10).grid(row=0, column=1, padx=5)
        ttk.Label(box, text="Risk cap: $5 estimated buffered loss; actual fills can exceed estimate.").grid(row=0, column=2, padx=12)
        self.demo_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Demo-only auto mode (never live auto)", variable=self.demo_var, command=self.toggle_demo_auto).grid(row=1, column=0, columnspan=2, sticky="w", padx=5)
        ttk.Label(box, text="Live mode is manual signal approval only; app-managed positions only are affected by emergency stop.", wraplength=900).grid(row=1, column=2, padx=8, sticky="w")
        self.risk_text = tk.Text(parent, wrap="word", height=18)
        self.risk_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.risk_text.insert("end", "Order volume is sized from broker order_calc_profit/order_calc_margin with a 10% buffer. The $5 limit is an estimate, not guaranteed maximum realized loss. Stop-market execution, gaps, spread, commissions and slippage may cause greater loss. Live mode requires a separate warning confirmation and each signal still requires approval. Emergency stop cancels/closes only orders/positions tagged with this app's magic number; it cannot guarantee broker execution and does not affect unrelated trades.\n")

    def _build_telegram(self, parent):
        ttk.Label(parent, text=f"Research source: {CHANNEL_LINK}\nMessages are unverified, require human review, and are never auto-executed. Import only content you may use.", wraplength=1300).pack(anchor="w", padx=10, pady=8)
        bar = ttk.Frame(parent); bar.pack(fill="x", padx=10)
        ttk.Button(bar, text="Import Telegram Desktop JSON export", command=self.import_telegram_export).pack(side="left", padx=4)
        ttk.Button(bar, text="Poll authorized bot updates", command=self.poll_telegram).pack(side="left", padx=4)
        self.telegram_status = tk.StringVar(value="Set TELEGRAM_BOT_TOKEN locally and add your bot as channel admin. Polling gets new updates only; it does not fetch channel history.")
        ttk.Label(parent, textvariable=self.telegram_status, wraplength=1300).pack(anchor="w", padx=10, pady=6)
        self.telegram_tree = ttk.Treeview(parent, columns=("date", "symbol", "side", "entry", "stop", "target", "status"), show="headings", height=10)
        for col, title in (("date", "Date"), ("symbol", "Candidate"), ("side", "Direction"), ("entry", "Entry"), ("stop", "Stop"), ("target", "Target"), ("status", "Review")):
            self.telegram_tree.heading(col, text=title); self.telegram_tree.column(col, width=130, anchor="center")
        self.telegram_tree.pack(fill="both", expand=True, padx=10, pady=6)
        self.telegram_text = tk.Text(parent, height=6, wrap="word"); self.telegram_text.pack(fill="x", padx=10, pady=6)
        self.telegram_tree.bind("<<TreeviewSelect>>", self.show_telegram_message)

    def _build_backtest(self, parent):
        bar = ttk.Frame(parent, padding=8); bar.pack(fill="x")
        self.bt_symbol_var, self.bt_tf_var, self.bt_lots_var = tk.StringVar(value="XAUUSD"), tk.StringVar(value="M15"), tk.StringVar(value="0.01")
        ttk.Combobox(bar, textvariable=self.bt_symbol_var, values=SYMBOL_PRESETS, width=10, state="readonly").pack(side="left", padx=4)
        ttk.Combobox(bar, textvariable=self.bt_tf_var, values=TIMEFRAMES, width=8, state="readonly").pack(side="left", padx=4)
        ttk.Entry(bar, textvariable=self.bt_lots_var, width=8).pack(side="left", padx=4)
        ttk.Button(bar, text="Run backtest", command=self.run_backtest).pack(side="left", padx=5)
        ttk.Button(bar, text="Export trades CSV…", command=self.export_backtest).pack(side="left", padx=5)
        self.bt_summary = tk.StringVar(value="Historical simulation only — not a forecast.")
        ttk.Label(parent, textvariable=self.bt_summary, wraplength=1300).pack(anchor="w", padx=10)
        self.bt_tree = ttk.Treeview(parent, columns=("time", "side", "entry", "exit", "reason", "net"), show="headings", height=15)
        for col, title in (("time", "Entry time"), ("side", "Side"), ("entry", "Entry"), ("exit", "Exit"), ("reason", "Reason"), ("net", "Net P/L estimate")):
            self.bt_tree.heading(col, text=title); self.bt_tree.column(col, width=160, anchor="center")
        self.bt_tree.pack(fill="both", expand=True, padx=10, pady=8)
        self.backtest_trades = []

    def _log(self, text):
        if hasattr(self, "log"):
            self.log.insert("end", f"{time.strftime('%H:%M:%S')}  {text}\n"); self.log.see("end")

    def open_bot_manager(self):
        BotManagerDialog(self, self.bot_manager, on_change=self._on_bot_library_changed)

    def _on_bot_library_changed(self, preferred_name=None):
        for iid in self.bot_tree.get_children():
            self.bot_tree.delete(iid)
        for bot in self.bot_manager.get_bots():
            label = bot.name if self.bot_manager.is_enabled(bot) else f"{bot.name} [DISABLED]"
            self.bot_tree.insert("", "end", text=label)
        if preferred_name:
            for iid in self.bot_tree.get_children():
                if self.bot_tree.item(iid, "text").replace(" [DISABLED]", "") == preferred_name:
                    self.bot_tree.selection_set(iid)
                    self.on_bot_selected(None)
                    break

    def _selected_bot(self):
        selection = self.bot_tree.selection()
        name = self.bot_tree.item(selection[0], "text").replace(" [DISABLED]", "") if selection else None
        return next((b for b in self.bot_manager.get_bots() if b.name == name), None)

    def _select_first_bot(self):
        children = self.bot_tree.get_children()
        if children:
            self.bot_tree.selection_set(children[0]); self.on_bot_selected(None)

    def connect_mt5(self):
        try:
            if not self.mt5.connect():
                self.connection_var.set("Could not connect — open/log in to MT5 first"); return
            account = self.mt5.get_account_info()
            mode = "DEMO" if self.mt5.is_demo_account() else "REAL/OTHER"
            self.connection_var.set(f"Connected | {mode} | {account.server}")
            self._log(f"Connected to {mode}; credentials remain in MT5.")
            self.refresh_market()
        except Exception as exc:
            self._log(f"Connection error: {exc}")

    def apply_bot_editor(self):
        bot = self._selected_bot()
        if not bot: return
        try:
            lots, mult = float(self.bot_lots_var.get()), float(self.stop_atr_var.get())
            if not 0 < lots <= 10 or not .1 <= mult <= 10: raise ValueError("Lots must be 0–10 and ATR multiplier 0.1–10.")
            bot.max_trade_size_lots = lots; bot.settings["stop_atr_multiplier"] = mult
            self._log(f"Bot settings applied: {bot.name}, max {lots} lots, SL {mult} ATR.")
            self.refresh_market()
        except ValueError as exc: messagebox.showerror("Invalid settings", str(exc))

    def on_bot_selected(self, _event):
        bot = self._selected_bot()
        if bot:
            self.bot_lots_var.set(str(bot.max_trade_size_lots)); self.stop_atr_var.set(str(bot.settings.get("stop_atr_multiplier", 1.5)))
            if self.mt5.connected: self.refresh_market()
            else: self.bot_details.delete("1.0", "end"); self.bot_details.insert("end", f"{bot.name}\n{bot.description}\nConnect MT5 for live broker candles.\n")

    def enable_live(self):
        if self.live_armed:
            self.live_armed = False; self.mode_var.set("MANUAL • LIVE DISARMED"); self._log("Live order permission disarmed."); return
        if not self.mt5.connected or not self.mt5.is_real_account():
            messagebox.showwarning("Real account not detected", "Connect the intended MT5 account first. This control only arms explicit, manually approved orders; no live automatic trading.")
            return
        warning = ("REAL MONEY RISK WARNING\n\nTrading can result in rapid and total loss of capital. Signals are heuristic and unverified; past tests and scores do not predict outcomes. The $5 estimate is not a guaranteed maximum. Slippage, gaps, spread, rejected stops, outages and broker execution can cause larger losses.\n\nLive automation remains disabled. Each queued order requires an individual approval and a fresh broker risk check. Emergency stop only targets orders/positions opened by this app and cannot guarantee a fill.\n\nArm manual live approvals for this session?")
        if not messagebox.askyesno("Enable REAL account orders?", warning, icon="warning"):
            return
        if not messagebox.askyesno("Confirm live mode", "I understand this can lose real money. Enable manual live order approvals now?", icon="warning"):
            return
        self.live_armed = True; self.mode_var.set("LIVE ARMED • MANUAL APPROVAL ONLY")
        self._log("Live manual approval mode armed after two confirmations; auto trading remains disabled.")

    def toggle_demo_auto(self):
        if not self.demo_var.get(): return
        if not self.mt5.connected or not self.mt5.is_demo_account():
            self.demo_var.set(False); messagebox.showwarning("Demo required", "Demo automatic mode requires a verified MT5 demo account."); return
        if not messagebox.askyesno("Arm demo auto?", "Demo automation submits simulated broker orders. Live automatic execution is not supported. Continue?"):
            self.demo_var.set(False)

    def refresh_market(self):
        if not self.mt5.connected:
            self.signal_var.set("No feed. Connect to MT5; sample prices are not used."); return
        bot = self._selected_bot()
        if not bot: return
        if not self.bot_manager.is_enabled(bot):
            self.signal_var.set(f"{bot.name} is disabled. Enable it in Manage bots to resume analysis.")
            return
        try:
            symbol, data = self.mt5.get_market_data(self.symbol_var.get(), TIMEFRAMES, self.config.candle_count)
            self.market_data = data
            signal = self.bot_manager.evaluate(symbol, data, bot); self.last_signal = signal
            self._render_signal(bot, signal); self._render_scores(signal); self._render_chart(signal)
            tick = self.mt5.get_tick(symbol)
            if tick: self.quote_var.set(f"Bid {tick.bid:.3f} / Ask {tick.ask:.3f}")
            if signal.get("direction") in ("long", "short"):
                self._enqueue_signal(bot, signal, data)
            if self.demo_var.get() and not self.mt5.is_real_account(): self._maybe_demo_order(bot, signal)
        except Exception as exc:
            self.signal_var.set(f"Market data error: {exc}"); self._log(f"Refresh failed: {exc}")

    def _render_signal(self, bot, signal):
        self.signal_var.set(f"{signal['symbol']} | {bot.name} | {signal.get('direction','neutral').upper()} | score {signal.get('confidence',0)} / 100 (not probability) | entry {signal.get('entry',0):.3f} | SL {signal.get('stop_loss')} | TP {signal.get('take_profit')}")
        self.bot_details.delete("1.0", "end")
        self.bot_details.insert("end", f"{bot.name}\n{bot.description}\nScore is a technical heuristic, not success probability.\nEntry {signal.get('entry')} | stop {signal.get('stop_loss')} | target {signal.get('take_profit')}\n\n")
        for tf in TIMEFRAMES:
            result = signal.get("timeframes", {}).get(tf, {})
            if result.get("valid"): self.bot_details.insert("end", f"{tf}: {result['direction']} {result['score']} — {'; '.join(result['reasons'])}\n")

    def _render_scores(self, signal):
        for child in self.score_tree.get_children(): self.score_tree.delete(child)
        for tf in TIMEFRAMES:
            r = signal.get("timeframes", {}).get(tf, {})
            if r.get("valid"): self.score_tree.insert("", "end", values=(tf, r["score"], r["direction"], f"{r['rsi']:.1f}", f"{r['macd_hist']:.5f}", f"{r['volume_pressure']:.2f}", "up" if r["ema20"] > r["ema50"] else "down"))

    def _render_chart(self, signal):
        tf = self.chart_tf_var.get(); r = signal.get("timeframes", {}).get(tf)
        if not r or not r.get("valid"): return
        df = r["dataframe"].tail(150).reset_index(drop=True); offset = len(r["dataframe"]) - len(df); x = np.arange(len(df))
        for ax in (self.ax_price, self.ax_rsi, self.ax_macd, self.ax_volume): ax.clear(); ax.grid(True, alpha=.2)
        self.ax_price.plot(x, df["close"], label="Close", color="#1f4e79")
        self.ax_price.plot(x, r["ema20_series"].tail(len(df)), label="EMA20", color="#f28e2b")
        self.ax_price.plot(x, df["close"].ewm(span=50, adjust=False).mean(), label="EMA50", color="#59a14f")
        for idx, price in r["zigzag_highs"] + r["zigzag_lows"]:
            if offset <= idx < offset + len(df): self.ax_price.scatter(idx-offset, price, s=22, color="#b07aa1")
        self.ax_price.set_title(f"{signal['symbol']} {tf} | completed bars; confirmed pivot points lag")
        self.ax_price.legend(loc="upper left", ncol=3, fontsize=8)
        self.ax_rsi.plot(x, r["rsi_series"].tail(len(df)), color="#e15759"); self.ax_rsi.axhline(70, ls="--", c="gray"); self.ax_rsi.axhline(30, ls="--", c="gray"); self.ax_rsi.set_ylabel("RSI")
        hist = r["macd_hist_series"].tail(len(df)).to_numpy(); self.ax_macd.bar(x, hist, color=np.where(hist >= 0, "#59a14f", "#e15759")); self.ax_macd.set_ylabel("MACD hist")
        vp = r["volume_pressure_series"].tail(len(df)).to_numpy(); self.ax_volume.bar(x, vp, color=np.where(vp >= 0, "#59a14f", "#e15759")); self.ax_volume.set_ylabel("Vol pressure")
        self.figure.tight_layout(); self.canvas.draw_idle()

    def _enqueue_signal(self, bot, signal, data):
        bars = data.get(bot.default_timeframe) or data.get("M15") or []
        if not len(bars): return
        key = (bot.name, signal["symbol"], signal["direction"], int(bars[-1]["time"]))
        if key in self.queue: return
        self.queue[key] = {"bot": bot, "signal": signal, "key": key, "status": "PENDING REVIEW"}
        iid = f"q{len(self.queue)}"
        self.queue[key]["iid"] = iid
        self.queue_tree.insert("", "end", iid=iid, values=(time.strftime("%Y-%m-%d %H:%M:%S"), signal["symbol"], bot.name, signal["direction"], signal.get("confidence"), f"{signal.get('entry',0):.3f}", signal.get("stop_loss"), signal.get("take_profit"), "PENDING REVIEW"))
        self.journal.record(event="signal", symbol=signal["symbol"], bot=bot.name, direction=signal["direction"], score=signal.get("confidence"), entry=signal.get("entry"), stop=signal.get("stop_loss"), target=signal.get("take_profit"), status="PENDING REVIEW", details="Indicator heuristic; not probability")
        self._log(f"Signal queued for review: {signal['symbol']} {signal['direction']} ({bot.name}).")

    def _selected_queue(self):
        selected = self.queue_tree.selection()
        if not selected: return None, None
        iid = selected[0]
        for key, item in self.queue.items():
            if item.get("iid") == iid: return key, item
        return None, None

    def reject_signal(self):
        key, item = self._selected_queue()
        if not item or item["status"] != "PENDING REVIEW": return
        item["status"] = "REJECTED"
        self.queue_tree.set(item["iid"], "status", "REJECTED")
        s, b = item["signal"], item["bot"]
        self.journal.record(event="signal", symbol=s["symbol"], bot=b.name, direction=s["direction"], score=s.get("confidence"), status="REJECTED")
        self._log(f"Signal rejected: {b.name} {s['symbol']}."); self.refresh_report()

    def approve_signal(self):
        key, item = self._selected_queue()
        if not item or item["status"] != "PENDING REVIEW": return
        bot, signal = item["bot"], item["signal"]
        if not self.mt5.connected:
            messagebox.showwarning("Not connected", "Connect to MT5 before approving an order."); return
        try:
            if not self.mt5.is_demo_account() and not (self.live_armed and self.mt5.is_real_account()):
                raise RuntimeError("Real account mode is not armed. Use Enable REAL orders and accept both warnings.")
            symbol = signal["symbol"]; tick = self.mt5.get_tick(symbol); info = self.mt5.get_symbol_info(symbol)
            if not tick or not info: raise RuntimeError("Current quote/symbol specifications unavailable.")
            direction = signal["direction"]; entry = tick.ask if direction == "long" else tick.bid
            distance = float(signal.get("stop_distance") or 0)
            if distance <= 0: raise RuntimeError("Signal has no valid stop distance.")
            stop = entry-distance if direction == "long" else entry+distance
            target = entry+1.5*distance if direction == "long" else entry-1.5*distance
            requested = min(float(self.lots_var.get()), bot.max_trade_size_lots)
            sizing = self.risk_manager.size_position(symbol, direction, entry, stop, requested, bot.max_trade_size_lots)
            if not sizing["ok"]: raise RuntimeError(sizing["reason"])
            is_real = self.mt5.is_real_account()
            warning = f"Submit {direction.upper()} {symbol}, {sizing['volume']} lots?\n\nSL {stop:.{info.digits}f}; TP {target:.{info.digits}f}; buffered risk estimate ${sizing['buffered_loss']:.2f} (cap ${sizing['risk_cap']:.2f}); margin est ${sizing['margin_estimate']:.2f}.\n\nActual loss can exceed estimate. " + ("THIS USES REAL MONEY." if is_real else "Demo account order.")
            if not messagebox.askyesno("Confirm order", warning, icon="warning"): return
            result = self.mt5.send_approved_order(symbol, direction, sizing["volume"], round(stop, info.digits), round(target, info.digits), allow_real=bool(is_real and self.live_armed), comment=bot.name)
            item["status"] = f"SUBMITTED #{result.order}"; self.queue_tree.set(item["iid"], "status", item["status"])
            self.journal.record(event="approved_order", symbol=symbol, bot=bot.name, direction=direction, score=signal.get("confidence"), entry=entry, stop=stop, target=target, lots=sizing["volume"], estimated_risk_usd=sizing["buffered_loss"], status=item["status"], details="Broker submission accepted; fill/outcome can differ")
            self._log(f"Order submitted after manual approval. Ticket {result.order}; est buffered risk ${sizing['buffered_loss']:.2f}.")
            self.refresh_report()
        except Exception as exc:
            self._log(f"Approval blocked/failed: {exc}"); messagebox.showerror("Order not submitted", str(exc))

    def emergency_stop(self):
        self.auto_var.set(False); self.demo_var.set(False); self.live_armed = False
        self.mode_var.set("EMERGENCY STOP • DISARMED")
        if not self.mt5.connected:
            self._log("Emergency stop: all app modes disarmed; MT5 disconnected, positions could not be queried."); return
        try:
            result = self.mt5.emergency_stop_app_trades()
            self._log(f"Emergency stop: closed app positions {result['closed']}; canceled app pending orders {result['cancelled']}; errors {result['errors']}.")
            messagebox.showwarning("Emergency stop complete", f"App modes disarmed. Closed {len(result['closed'])} app-tagged position(s); canceled {len(result['cancelled'])} app-tagged pending order(s).\nErrors: {result['errors'] or 'None reported'}\nUnrelated trades were not touched. Verify state in MT5 immediately.")
        except Exception as exc:
            self._log(f"Emergency stop could not complete: {exc}"); messagebox.showerror("Emergency stop error", f"Modes disarmed, but broker action failed: {exc}. Check MT5 immediately.")

    def _maybe_demo_order(self, bot, signal):
        # Auto execution remains a demo-only optional feature; live mode never routes automatically.
        if not self.demo_var.get() or signal.get("direction") not in ("long", "short") or not self.mt5.is_demo_account(): return
        try:
            import MetaTrader5 as mt5
            bars = self.market_data.get(bot.default_timeframe, [])
            if not len(bars): return
            key = (bot.name, signal["symbol"], int(bars[-1]["time"]))
            if key == self.last_auto_key or mt5.positions_get(symbol=signal["symbol"]): return
            tick, info = self.mt5.get_tick(signal["symbol"]), self.mt5.get_symbol_info(signal["symbol"])
            direction = signal["direction"]; entry = tick.ask if direction == "long" else tick.bid
            dist = float(signal.get("stop_distance") or 0)
            if dist <= 0: return
            stop = entry-dist if direction == "long" else entry+dist; target = entry+1.5*dist if direction == "long" else entry-1.5*dist
            sizing = self.risk_manager.size_position(signal["symbol"], direction, entry, stop, min(float(self.lots_var.get()), bot.max_trade_size_lots), bot.max_trade_size_lots)
            if not sizing["ok"]: self._log(f"Demo risk block: {sizing['reason']}"); self.last_auto_key = key; return
            result = self.mt5.send_approved_order(signal["symbol"], direction, sizing["volume"], round(stop, info.digits), round(target, info.digits), comment=bot.name)
            self._log(f"Demo auto order submitted {result.order}; estimated buffered risk ${sizing['buffered_loss']:.2f}."); self.last_auto_key = key
        except Exception as exc: self._log(f"Demo auto order blocked: {exc}")

    def refresh_report(self):
        rows = self.journal.read_rows()
        for child in self.report_tree.get_children(): self.report_tree.delete(child)
        for row in rows[-500:]: self.report_tree.insert("", "end", values=(row.get("timestamp_utc"), row.get("event"), row.get("symbol"), row.get("bot"), row.get("direction"), row.get("score"), row.get("status"), row.get("details")))
        self.report_summary.set(f"{len(rows)} recorded events | local CSV: strategy_activity.csv | signal scores are not win probabilities.")

    def export_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=(("CSV", "*.csv"),), initialfile="strategy_activity.csv")
        if path:
            import csv
            rows = self.journal.read_rows()
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    if rows:
                        writer = csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
                self._log(f"Strategy activity report exported: {path}")
            except Exception as exc: messagebox.showerror("Report export failed", str(exc))

    def import_telegram_export(self):
        path = filedialog.askopenfilename(filetypes=(("Telegram Desktop JSON", "*.json"),))
        if not path: return
        try:
            messages = parse_telegram_export(path); self._add_telegram_messages(messages)
            self.telegram_status.set(f"Imported {len(messages)} candidate message(s); unverified and review-only.")
        except Exception as exc: messagebox.showerror("Import failed", str(exc))

    def poll_telegram(self):
        try:
            messages, self.telegram_offset = poll_authorized_channel_updates(offset=self.telegram_offset)
            self._add_telegram_messages(messages); self.telegram_status.set(f"Loaded {len(messages)} authorized new post(s); no historical fetch.")
        except Exception as exc: self.telegram_status.set(str(exc)); self._log(f"Telegram polling unavailable: {exc}")

    def _add_telegram_messages(self, messages):
        for msg in messages:
            self.telegram_messages.append(msg); c = msg["candidate"]; iid = f"tg{len(self.telegram_messages)}"
            self.telegram_tree.insert("", "end", iid=iid, values=(msg.get("date"), c.get("candidate_symbol") or "—", c.get("candidate_direction"), c.get("candidate_entry") or "—", c.get("candidate_stop") or "—", c.get("candidate_target") or "—", "UNVERIFIED / REVIEW"))

    def show_telegram_message(self, _event):
        selected = self.telegram_tree.selection()
        if selected:
            msg = self.telegram_messages[int(selected[0][2:])-1]
            self.telegram_text.delete("1.0", "end"); self.telegram_text.insert("end", f"{msg['source']} | {msg.get('date')}\n{msg['candidate']}\n\n{msg['text']}\n\nUNVERIFIED. Never auto-executed.")

    def run_backtest(self):
        if not self.mt5.connected: messagebox.showwarning("MT5 required", "Connect to MT5 first."); return
        try:
            symbol = self.mt5.resolve_symbol(self.bt_symbol_var.get()); tf = self.bt_tf_var.get()
            if not symbol: raise RuntimeError("Broker symbol unavailable.")
            bars = self.mt5.get_candles(symbol, tf, 5000); info = self.mt5.get_symbol_info(symbol)
            self.backtest_trades, summary = self.backtester.run(bars, symbol, tf, float(self.bt_lots_var.get()), float(info.trade_tick_size), float(info.trade_tick_value), float(info.spread*info.point))
            for row in self.bt_tree.get_children(): self.bt_tree.delete(row)
            for t in self.backtest_trades: self.bt_tree.insert("", "end", values=(t["entry_time"], t["direction"], f"{t['entry']:.3f}", f"{t['exit_price']:.3f}", t["exit_reason"], f"{t['net_pnl_usd']:.2f}"))
            self.bt_summary.set(f"{symbol} {tf} | trades {summary['trades']} | win rate {summary['win_rate_pct']:.1f}% | net est ${summary['net_pnl_usd']:.2f} | max DD est ${summary['max_drawdown_usd']:.2f}. Historical only.")
        except Exception as exc: messagebox.showerror("Backtest failed", str(exc))

    def export_backtest(self):
        if not self.backtest_trades: messagebox.showinfo("No results", "Run a backtest first."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=(("CSV", "*.csv"),), initialfile="backtest.csv")
        if path:
            try: self.backtester.export_csv(self.backtest_trades, path); self._log(f"Backtest CSV exported: {path}")
            except Exception as exc: messagebox.showerror("Export failed", str(exc))

    def close_app(self):
        self.live_armed = False; self.auto_var.set(False)
        if self.mt5.connected: self.mt5.disconnect()
        self.master.destroy()


def run_app():
    root = tk.Tk(); TradingFrame(root); root.mainloop()
