from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .bot_manager import BotManager
from .config import MqlConfig
from .mt5_client import MT5Connection


logger = logging.getLogger(__name__)


class TradingFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master.title("DR Trading Desktop App")
        self.master.geometry("1300x850")
        self.pack(fill="both", expand=True)

        self.config = MqlConfig()
        self.bot_manager = BotManager()
        self.mt5 = MT5Connection(self.config)

        self.build_ui()
        self.select_first_bot()

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(top, text="Connect MT5", command=self.connect_mt5).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Refresh market", command=self.refresh_market).pack(side="left", padx=(0, 8))
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Automatic mode", variable=self.auto_var).pack(side="left")

        main = ttk.Notebook(self)
        main.pack(fill="both", expand=True, padx=12, pady=6)

        market_tab = ttk.Frame(main)
        bot_tab = ttk.Frame(main)
        risk_tab = ttk.Frame(main)

        main.add(market_tab, text="Market")
        main.add(bot_tab, text="Bots")
        main.add(risk_tab, text="Risk")

        left = ttk.Frame(bot_tab, width=290)
        left.pack(side="left", fill="y", padx=(0, 8), pady=8)

        ttk.Label(left, text="Bots", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 6))
        self.bot_tree = ttk.Treeview(left, columns=("bot",), show="tree")
        self.bot_tree.heading("#0", text="Bot")
        self.bot_tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for bot in self.bot_manager.get_bots():
            self.bot_tree.insert("", "end", text=bot.name)
        self.bot_tree.bind("<<TreeviewSelect>>", self.on_bot_selected)

        market_content = ttk.Frame(market_tab)
        market_content.pack(fill="both", expand=True, padx=12, pady=12)

        fig = Figure(figsize=(9, 5), dpi=100)
        self.ax = fig.add_subplot(111)
        self.ax.set_title("XAUUSD multi-timeframe context")
        self.ax.plot([0, 1, 2, 3, 4], [2.1, 2.3, 2.2, 2.5, 2.4], linewidth=2)
        self.ax.grid(True, alpha=0.3)

        canvas = FigureCanvasTkAgg(fig, master=market_content)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        self.signal_var = tk.StringVar(value="Signal: waiting for analysis")
        ttk.Label(market_content, textvariable=self.signal_var, wraplength=650, justify="left").pack(anchor="w", pady=(12, 0))

        details_panel = ttk.Frame(bot_tab)
        details_panel.pack(fill="both", expand=True, padx=12, pady=8)

        ttk.Label(details_panel, text="Strategy details", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(8, 6))
        self.bot_details = tk.Text(details_panel, height=20, wrap="word")
        self.bot_details.pack(fill="both", expand=True)
        self.bot_details.insert("end", "Select a bot to inspect its strategy details.\n")

        self.risk_text = tk.Text(risk_tab, height=20, wrap="word")
        self.risk_text.pack(fill="both", expand=True, padx=12, pady=12)
        self.risk_text.insert("end", "Risk rules:\n- Max risk per trade: $5\n- Automatic mode stays disabled until the bot has been validated in demo mode\n- Stop loss is adjustable and must respect the configured risk cap\n- Profit target should be reviewed with market structure and not assumed\n")

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Label(bottom, text="Activity log").pack(anchor="w")
        self.log = tk.Text(bottom, height=8, wrap="word")
        self.log.pack(fill="x")
        self.log.insert("end", "App started.\n")

    def select_first_bot(self):
        if self.bot_tree.get_children():
            self.bot_tree.selection_set(self.bot_tree.get_children()[0])
            self.on_bot_selected(None)

    def connect_mt5(self):
        try:
            connected = self.mt5.connect()
            if connected:
                self.log.insert("end", "Connected to MetaTrader 5.\n")
                self.risk_text.insert("end", "\nMT5 account connected successfully.\n")
            else:
                self.log.insert("end", "MT5 connection failed. Check credentials and terminal installation.\n")
                self.risk_text.insert("end", "\nMT5 connection failed. Please enter credentials and ensure the terminal is installed.\n")
        except Exception as exc:
            self.log.insert("end", f"MT5 error: {exc}\n")

    def refresh_market(self):
        self.log.insert("end", "Refreshing market context and strategy evaluation.\n")
        selected = self.bot_tree.selection()
        if not selected:
            self.signal_var.set("Signal: no bot selected")
            return

        bot_name = self.bot_tree.item(selected[0], "text")
        bot = next((b for b in self.bot_manager.get_bots() if b.name == bot_name), None)
        if not bot:
            return

        sample = {
            "M1": self._sample_candles(28),
            "M5": self._sample_candles(32),
            "M15": self._sample_candles(40),
            "H1": self._sample_candles(44),
            "H4": self._sample_candles(52),
            "D1": self._sample_candles(54),
        }

        signal = self.bot_manager.evaluate(bot.instrument, sample, bot)
        direction_text = signal.get("direction", "neutral") if signal.get("direction") != "neutral" else "waiting"
        self.signal_var.set(f"Signal: {direction_text} | confidence {signal.get('confidence', 0)}%")

        self.bot_details.delete("1.0", "end")
        self.bot_details.insert("end", f"Bot: {bot.name}\n")
        self.bot_details.insert("end", f"Description: {bot.description}\n\n")
        self.bot_details.insert("end", f"Direction: {direction_text}\n")
        self.bot_details.insert("end", f"Confidence: {signal.get('confidence', 0)}%\n")
        self.bot_details.insert("end", f"Risk cap: ${bot.max_risk_usd}\n")
        self.bot_details.insert("end", f"Max size: {bot.max_trade_size_lots} lots\n")
        self.bot_details.insert("end", f"Automatic mode: {self.auto_var.get()}\n\n")
        self.bot_details.insert("end", signal.get("reason", "No reason provided"))

        self.ax.clear()
        prices = [2.12, 2.17, 2.14, 2.22, 2.25, 2.24, 2.29, 2.34, 2.31, 2.38]
        self.ax.plot(range(len(prices)), prices, color="#4c78a8", linewidth=2)
        self.ax.set_title(f"{bot.instrument} context - {bot.name}")
        self.ax.grid(True, alpha=0.3)
        self.ax.figure.canvas.draw_idle()

    def on_bot_selected(self, event):
        self.refresh_market()

    def _sample_candles(self, count: int):
        candles = []
        base = 2325.0
        for i in range(count):
            base += (i % 5 - 2) * 0.25
            open_price = base
            close_price = base + 0.8 * ((i % 4) - 1.5)
            high = max(open_price, close_price) + 0.9
            low = min(open_price, close_price) - 0.9
            candles.append({
                "time": i,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close_price,
                "tick_volume": 250 + (i % 6) * 40,
                "spread": 0,
                "real_volume": 250 + (i % 6) * 40,
            })
        return candles


def run_app():
    root = tk.Tk()
    TradingFrame(root)
    root.mainloop()
