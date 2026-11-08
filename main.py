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
        self.master.title("Trading Desktop App")
        self.master.geometry("1200x800")
        self.pack(fill="both", expand=True)

        self.config = MqlConfig()
        self.bot_manager = BotManager()
        self.mt5 = MT5Connection(self.config)

        self.build_ui()

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(top, text="Connect MT5", command=self.connect_mt5).pack(side="left", padx=(0, 8))
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Automatic mode", variable=self.auto_var).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Refresh market", command=self.refresh_market).pack(side="left")

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12, pady=6)

        left = ttk.Frame(body, width=260)
        body.add(left)

        center = ttk.Frame(body)
        body.add(center)

        right = ttk.Frame(body, width=360)
        body.add(right)

        ttk.Label(left, text="Bots", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 6))
        self.bot_tree = ttk.Treeview(left, columns=("bot",), show="tree")
        self.bot_tree.heading("#0", text="Bot")
        self.bot_tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for bot in self.bot_manager.get_bots():
            self.bot_tree.insert("", "end", text=bot.name)

        self.bot_tree.bind("<<TreeviewSelect>>", self.on_bot_selected)

        fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = fig.add_subplot(111)
        self.ax.set_title("XAUUSD live context")
        self.ax.plot([0, 1, 2, 3], [0, 2, 1, 3])

        canvas = FigureCanvasTkAgg(fig, master=center)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=12)

        self.signal_var = tk.StringVar(value="Signal: waiting for analysis")
        ttk.Label(center, textvariable=self.signal_var, wraplength=420, justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        ttk.Label(right, text="Bot details", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 6))
        self.bot_details = tk.Text(right, height=18, wrap="word")
        self.bot_details.pack(fill="both", expand=True, padx=12)

        self.bot_details.insert("end", "Select a bot to inspect its strategy details.\n")

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Label(bottom, text="Activity log").pack(anchor="w")
        self.log = tk.Text(bottom, height=8, wrap="word")
        self.log.pack(fill="x")
        self.log.insert("end", "App started.\n")

    def connect_mt5(self):
        try:
            connected = self.mt5.connect()
            if connected:
                self.log.insert("end", "Connected to MetaTrader 5.\n")
            else:
                self.log.insert("end", "MT5 connection failed. Check credentials and terminal install.\n")
        except Exception as exc:
            self.log.insert("end", f"MT5 error: {exc}\n")

    def refresh_market(self):
        self.log.insert("end", "Refreshing market context and strategy data.\n")
        selected = self.bot_tree.selection()
        if not selected:
            self.signal_var.set("Signal: no bot selected")
            return

        bot_name = self.bot_tree.item(selected[0], "text")
        bot = next((b for b in self.bot_manager.get_bots() if b.name == bot_name), None)
        if not bot:
            return

        sample = {
            "M1": self._sample_candles(30),
            "M5": self._sample_candles(30),
            "M15": self._sample_candles(40),
            "H1": self._sample_candles(40),
            "H4": self._sample_candles(50),
            "D1": self._sample_candles(50),
        }

        signal = self.bot_manager.evaluate(bot.instrument, sample, bot)
        if signal.get("direction") == "neutral":
            direction_text = "waiting"
        else:
            direction_text = signal["direction"]
        self.signal_var.set(f"Signal: {direction_text} | confidence {signal.get('confidence', 0)}%")
        self.bot_details.delete("1.0", "end")
        self.bot_details.insert("end", f"Bot: {bot.name}\n")
        self.bot_details.insert("end", f"Description: {bot.description}\n\n")
        self.bot_details.insert("end", f"Direction: {direction_text}\n")
        self.bot_details.insert("end", f"Confidence: {signal.get('confidence', 0)}%\n")
        self.bot_details.insert("end", f"Risk cap: ${bot.max_risk_usd}\n")
        self.bot_details.insert("end", f"Max size: {bot.max_trade_size_lots} lots\n")
        self.bot_details.insert("end", f"Automatic mode: {self.auto_var.get()}\n\n")
        self.bot_details.insert("end", f"Reason: {signal.get('reason', 'No reason provided')}\n")

    def on_bot_selected(self, event):
        self.refresh_market()

    def _sample_candles(self, count: int):
        candles = []
        base = 2320.0
        for i in range(count):
            base += (i % 5 - 2) * 0.4
            open_price = base
            close_price = base + 0.7 * ((i % 4) - 1.5)
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
    TradingFrame(master=root)
    root.mainloop()
