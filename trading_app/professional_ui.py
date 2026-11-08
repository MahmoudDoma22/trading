from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .ui import TradingFrame


PALETTE = {
    "window": "#10151d",
    "panel": "#18212c",
    "panel_alt": "#202b38",
    "text": "#e6edf3",
    "muted": "#9aa9b8",
    "border": "#334155",
    "green": "#12b886",
    "green_dark": "#14372f",
    "red": "#ff5b61",
    "red_dark": "#402329",
    "amber": "#f0b429",
    "blue": "#5aa9ff",
}


class ProfessionalTradingFrame(TradingFrame):
    """Dark terminal presentation layered over the existing reviewed-order workflow."""

    def _build_ui(self):
        super()._build_ui()
        self.configure(background=PALETTE["window"])
        self._configure_dark_styles()
        self._add_market_cards()
        self._add_order_ticket()
        self._add_real_money_warning()
        self._style_text_widgets(self)
        self._style_queue_rows()

    def _configure_dark_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=PALETTE["window"], foreground=PALETTE["text"], font=("Segoe UI", 9))
        style.configure("TFrame", background=PALETTE["window"])
        style.configure("TLabel", background=PALETTE["window"], foreground=PALETTE["text"])
        style.configure("Header.TLabel", background=PALETTE["window"], foreground=PALETTE["blue"], font=("Segoe UI", 11, "bold"))
        style.configure("TButton", background=PALETTE["panel_alt"], foreground=PALETTE["text"], bordercolor=PALETTE["border"], padding=(9, 5))
        style.map("TButton", background=[("active", "#314155"), ("pressed", "#263447")])
        style.configure("TCheckbutton", background=PALETTE["panel"], foreground=PALETTE["text"])
        style.configure("TNotebook", background=PALETTE["window"], bordercolor=PALETTE["border"])
        style.configure("TNotebook.Tab", background=PALETTE["panel"], foreground=PALETTE["muted"], padding=(12, 7))
        style.map("TNotebook.Tab", background=[("selected", PALETTE["panel_alt"])], foreground=[("selected", PALETTE["text"])])
        style.configure("TLabelframe", background=PALETTE["panel"], foreground=PALETTE["text"], bordercolor=PALETTE["border"])
        style.configure("TLabelframe.Label", background=PALETTE["panel"], foreground=PALETTE["blue"], font=("Segoe UI", 9, "bold"))
        style.configure("Treeview", background=PALETTE["panel"], fieldbackground=PALETTE["panel"], foreground=PALETTE["text"], rowheight=25, bordercolor=PALETTE["border"])
        style.configure("Treeview.Heading", background=PALETTE["panel_alt"], foreground=PALETTE["text"], relief="flat")
        style.map("Treeview", background=[("selected", "#254c70")], foreground=[("selected", "#ffffff")])
        style.configure("Emergency.TButton", background="#9b1c28", foreground="#ffffff", font=("Segoe UI", 10, "bold"), padding=(10, 7))
        style.map("Emergency.TButton", background=[("active", "#c92a39")])
        style.configure("LiveRisk.TButton", background="#7f1d1d", foreground="#ffffff", font=("Segoe UI", 9, "bold"), padding=(9, 6))
        style.configure("Approve.TButton", background="#087f5b", foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        style.configure("Reject.TButton", background="#8b2635", foreground="#ffffff", font=("Segoe UI", 9, "bold"))

    def _style_text_widgets(self, parent):
        for child in parent.winfo_children():
            if isinstance(child, tk.Text):
                child.configure(background=PALETTE["panel"], foreground=PALETTE["text"], insertbackground=PALETTE["text"], selectbackground="#254c70", relief="flat", padx=7, pady=5)
            elif isinstance(child, tk.Frame):
                try:
                    child.configure(background=PALETTE["window"])
                except tk.TclError:
                    pass
            try:
                self._style_text_widgets(child)
            except (AttributeError, tk.TclError):
                continue

    def _card(self, parent, title, variable, color):
        frame = tk.Frame(parent, bg=PALETTE["panel"], highlightbackground=PALETTE["border"], highlightthickness=1, padx=12, pady=7)
        tk.Label(frame, text=title.upper(), bg=PALETTE["panel"], fg=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        value = tk.Label(frame, textvariable=variable, bg=PALETTE["panel"], fg=color, font=("Segoe UI", 12, "bold"), anchor="w")
        value.pack(fill="x", pady=(3, 0))
        return frame, value

    def _add_market_cards(self):
        market_tab = self.nb.nametowidget(self.nb.tabs()[0])
        self.cards_frame = tk.Frame(market_tab, bg=PALETTE["window"])
        self.cards_frame.pack(fill="x", padx=8, pady=(4, 0), before=self.canvas.get_tk_widget())
        self.card_symbol = tk.StringVar(value="XAUUSD")
        self.card_direction = tk.StringVar(value="WAITING")
        self.card_score = tk.StringVar(value="—")
        self.card_quote = tk.StringVar(value="Awaiting MT5")
        for title, var, color in (("Instrument", self.card_symbol, PALETTE["blue"]), ("Signal", self.card_direction, PALETTE["muted"]), ("Alignment score", self.card_score, PALETTE["amber"]), ("Quote", self.card_quote, PALETTE["text"])):
            card, _ = self._card(self.cards_frame, title, var, color)
            card.pack(side="left", fill="x", expand=True, padx=4)

    def _add_order_ticket(self):
        ticket = ttk.Frame(self.nb, padding=12)
        self.nb.add(ticket, text="Order ticket")
        ttk.Label(ticket, text="REVIEW TICKET — no order is submitted until you approve it", style="Header.TLabel").pack(anchor="w", pady=(0, 8))
        self.ticket_status = tk.StringVar(value="Select a pending signal from the Signal queue tab.")
        self.ticket_direction = tk.StringVar(value="PENDING / NO SIDE")
        self.ticket_detail = tk.Text(ticket, height=12, wrap="word")
        self.ticket_detail.pack(fill="both", expand=True, pady=6)
        self.ticket_detail.insert("end", "A fresh broker quote, margin check and $5 buffered risk check are required when approving. Price can change between review and execution. This is not a guaranteed maximum-loss amount.")
        ttk.Label(ticket, textvariable=self.ticket_status).pack(anchor="w", pady=5)
        actions = ttk.Frame(ticket)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="APPROVE SELECTED", style="Approve.TButton", command=self.approve_signal).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="REJECT SELECTED", style="Reject.TButton", command=self.reject_signal).pack(side="left")
        self.queue_tree.bind("<<TreeviewSelect>>", self._update_ticket, add=True)

    def _add_real_money_warning(self):
        risk_tab = None
        for tab_id in self.nb.tabs():
            frame = self.nb.nametowidget(tab_id)
            if self.nb.tab(tab_id, "text") == "Risk / modes":
                risk_tab = frame
                break
        if risk_tab is None:
            return
        banner = tk.Frame(risk_tab, bg=PALETTE["red_dark"], highlightbackground=PALETTE["red"], highlightthickness=2, padx=12, pady=10)
        banner.pack(fill="x", padx=12, pady=(0, 8), before=self.risk_text)
        tk.Label(banner, text="REAL-MONEY RISK — LIVE MODE IS MANUAL ONLY", bg=PALETTE["red_dark"], fg="#ffb4b8", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(banner, text="Losses can exceed the estimate. Emergency stop only targets this app's tagged trades; verify all actions in MT5.", bg=PALETTE["red_dark"], fg=PALETTE["text"], wraplength=1100, justify="left").pack(anchor="w", pady=(4, 0))
        # Emphasize the existing live-order and emergency buttons without changing their safety callbacks.
        for child in self.winfo_children():
            self._style_header_buttons(child)

    def _style_header_buttons(self, parent):
        for child in parent.winfo_children():
            if isinstance(child, ttk.Button):
                text = child.cget("text")
                if "REAL" in text:
                    child.configure(style="LiveRisk.TButton")
                elif "EMERGENCY" in text:
                    child.configure(style="Emergency.TButton")
            self._style_header_buttons(child)

    def _style_queue_rows(self):
        self.queue_tree.tag_configure("long", foreground="#6ee7b7", background=PALETTE["green_dark"])
        self.queue_tree.tag_configure("short", foreground="#ff9aa2", background=PALETTE["red_dark"])

    def _update_ticket(self, _event=None):
        _key, item = self._selected_queue()
        if not item:
            return
        signal, bot = item["signal"], item["bot"]
        direction = signal.get("direction", "neutral").upper()
        self.ticket_direction.set(direction)
        self.ticket_status.set(f"Queue status: {item['status']}  |  {signal['symbol']}  |  {bot.name}")
        self.ticket_detail.delete("1.0", "end")
        self.ticket_detail.insert("end", f"{signal['symbol']}  {direction}\nStrategy: {bot.name}\nHeuristic alignment score: {signal.get('confidence')} / 100 — NOT a win probability\n\nSignal reference entry: {signal.get('entry')}\nProposed stop: {signal.get('stop_loss')}\nProposed target: {signal.get('take_profit')}\n\nApproval refreshes the quote and recomputes permitted size and estimated risk. The approved price/SL/TP may differ from these displayed references. No Telegram signal is directly orderable.")

    def _enqueue_signal(self, bot, signal, data):
        previous = set(self.queue)
        super()._enqueue_signal(bot, signal, data)
        for key in set(self.queue) - previous:
            item = self.queue[key]
            self.queue_tree.item(item["iid"], tags=("long" if signal.get("direction") == "long" else "short",))
        self._style_queue_rows()

    def _render_signal(self, bot, signal):
        super()._render_signal(bot, signal)
        if hasattr(self, "card_symbol"):
            self.card_symbol.set(signal.get("symbol", "—"))
            side = signal.get("direction", "neutral").upper()
            self.card_direction.set(side)
            self.card_score.set(f"{signal.get('confidence', 0)} / 100")
            color = PALETTE["green"] if side == "LONG" else PALETTE["red"] if side == "SHORT" else PALETTE["muted"]
            for widget in self.cards_frame.winfo_children():
                labels = widget.winfo_children()
                if len(labels) > 1 and str(labels[0].cget("text")).lower() == "signal":
                    labels[1].configure(fg=color)

    def refresh_market(self):
        super().refresh_market()
        if hasattr(self, "card_quote") and self.mt5.connected:
            try:
                tick = self.mt5.get_tick(self.mt5.symbol)
                if tick:
                    self.card_quote.set(f"{tick.bid:.3f} / {tick.ask:.3f}")
            except Exception:
                pass

    def _render_chart(self, signal):
        super()._render_chart(signal)
        for axis in (self.ax_price, self.ax_rsi, self.ax_macd, self.ax_volume):
            axis.set_facecolor(PALETTE["panel"])
            axis.tick_params(colors=PALETTE["muted"], labelcolor=PALETTE["muted"])
            axis.xaxis.label.set_color(PALETTE["muted"])
            axis.yaxis.label.set_color(PALETTE["muted"])
            axis.title.set_color(PALETTE["text"])
            for spine in axis.spines.values():
                spine.set_color(PALETTE["border"])
        self.figure.set_facecolor(PALETTE["window"])
        self.canvas.draw_idle()


def run_app():
    root = tk.Tk()
    ProfessionalTradingFrame(root)
    root.mainloop()
