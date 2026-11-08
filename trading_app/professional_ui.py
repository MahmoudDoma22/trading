from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .ui import TradingFrame
from .theme import PALETTE, apply_dark_theme
from .signal_sources import fetch_signal_feed
from .account_profiles import load_profiles, save_profiles, save_password, get_password, delete_password


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
        header = self.winfo_children()[0]
        ttk.Button(header, text='Login / Accounts', command=self.open_account_login).pack(side='left', padx=6)
        self._add_market_cards()
        self._add_order_ticket()
        self._add_real_money_warning()
        self._style_text_widgets(self)
        self._style_queue_rows()
        self._add_signal_hub()
        self._add_manual_trading_tab()
        apply_dark_theme(self)



    def open_account_login(self):
        win = tk.Toplevel(self)
        win.title("Broker & MT5 account login")
        win.geometry("720x620")
        win.transient(self)
        win.grab_set()
        apply_dark_theme(win)
        profiles = load_profiles()

        ttk.Label(win, text="CONNECT TO A BROKER", style="Header.TLabel").pack(anchor="w", padx=18, pady=(16, 3))
        ttk.Label(win, text="Use the MT5 account login number and exact server name supplied by your broker. Email is optional contact/reference information.").pack(anchor="w", padx=18, pady=(0, 12))

        form = ttk.LabelFrame(win, text="Account credentials", padding=12)
        form.pack(fill="x", padx=18, pady=5)
        broker_var, email_var, login_var, password_var, server_var = (tk.StringVar() for _ in range(5))
        save_var = tk.BooleanVar(value=False)
        fields = [
            ("Broker name", broker_var, False),
            ("Email (optional)", email_var, False),
            ("MT5 account login / ID", login_var, False),
            ("Password", password_var, True),
            ("MT5 server (exact)", server_var, False),
        ]
        for i, (label, var, secret) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=4)
            entry = ttk.Entry(form, textvariable=var, show="•" if secret else "")
            entry.grid(row=i, column=1, sticky="ew", padx=8, pady=4)
        form.columnconfigure(1, weight=1)
        ttk.Checkbutton(form, text="Save password in Windows Credential Manager (optional)", variable=save_var).grid(row=5, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(form, text="Passwords are never written to the profile file or GitHub.").grid(row=6, column=1, sticky="w", padx=8)

        ttk.Label(win, text="SEARCH SAVED BROKER / ACCOUNT PROFILES", style="Header.TLabel").pack(anchor="w", padx=18, pady=(12, 3))
        search_var = tk.StringVar()
        ttk.Entry(win, textvariable=search_var).pack(fill="x", padx=18)
        tree = ttk.Treeview(win, columns=("broker", "email", "login", "server"), show="headings", height=6)
        for col, title, width in (("broker", "Broker", 145), ("email", "Email", 165), ("login", "Account login", 110), ("server", "Server", 260)):
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=18, pady=8)

        def refresh_profiles(*_):
            for iid in tree.get_children():
                tree.delete(iid)
            term = search_var.get().strip().casefold()
            for idx, profile in enumerate(profiles):
                haystack = " ".join(str(profile.get(k, "")) for k in ("broker", "email", "login", "server")).casefold()
                if not term or term in haystack:
                    tree.insert("", "end", iid=str(idx), values=(profile["broker"], profile.get("email", ""), profile["login"], profile["server"]))

        def choose_profile(_event=None):
            selected = tree.selection()
            if not selected:
                return
            p = profiles[int(selected[0])]
            broker_var.set(p["broker"])
            email_var.set(p.get("email", ""))
            login_var.set(p["login"])
            server_var.set(p["server"])
            saved = get_password(p["broker"], p["login"], p["server"])
            if saved:
                password_var.set(saved)
                save_var.set(True)

        tree.bind("<<TreeviewSelect>>", choose_profile)
        search_var.trace_add("write", refresh_profiles)
        refresh_profiles()

        status_var = tk.StringVar(value="No account connected through this login form yet.")
        ttk.Label(win, textvariable=status_var).pack(anchor="w", padx=18, pady=4)
        buttons = ttk.Frame(win)
        buttons.pack(fill="x", padx=18, pady=(4, 16))

        def connect_account():
            broker = broker_var.get().strip()
            login = login_var.get().strip()
            password = password_var.get()
            server = server_var.get().strip()
            if not broker or not login.isdigit() or not password or not server:
                messagebox.showwarning("Missing details", "Enter broker, numeric MT5 account login, password and exact server.", parent=win)
                return
            try:
                status_var.set("Connecting to MetaTrader 5…")
                win.update_idletasks()
                if not self.mt5.connect(login=int(login), password=password, server=server):
                    raise RuntimeError("MT5 login failed. Check account number, password, server and terminal installation.")
                account = self.mt5.get_account_info()
                if int(account.login) != int(login) or account.server != server:
                    self.mt5.disconnect()
                    raise RuntimeError("Connected MT5 account does not match the selected login/server.")
                profile = {"broker": broker, "email": email_var.get().strip(), "login": login, "server": server}
                profiles[:] = [p for p in profiles if (p.get("broker"), p.get("login"), p.get("server")) != (broker, login, server)]
                profiles.append(profile)
                save_profiles(profiles)
                password_saved = False
                if save_var.get():
                    try:
                        save_password(broker, login, server, password)
                        password_saved = True
                    except Exception as credential_error:
                        messagebox.showwarning("Password not saved", str(credential_error) + "\n\nThe MT5 session is connected, but the password was not stored.", parent=win)
                self.live_armed = False
                self.mode_var.set("MANUAL • NOT ARMED")
                mode = "DEMO" if self.mt5.is_demo_account() else "REAL"
                self.connection_var.set(f"Connected | {mode} | {account.server} | {account.login}")
                self._log(f"Connected to selected MT5 broker/account {account.login} ({mode}).")
                status_var.set(f"Connected: {account.server} / {account.login} ({mode}). " + ("Password saved securely." if password_saved else "Password not saved."))
                refresh_profiles()
                self.refresh_market()
                if messagebox.askyesno("Connected", "MT5 account connected. Close account manager?", parent=win):
                    win.destroy()
            except Exception as exc:
                status_var.set("Connection failed.")
                messagebox.showerror("MT5 login failed", str(exc), parent=win)

        def remove_profile():
            selected = tree.selection()
            if not selected:
                return
            p = profiles[int(selected[0])]
            if not messagebox.askyesno("Remove saved account", "Remove this saved profile and its stored Windows credential, if present?", parent=win):
                return
            profiles.remove(p)
            save_profiles(profiles)
            delete_password(p["broker"], p["login"], p["server"])
            refresh_profiles()
            status_var.set("Saved profile and its stored Windows credential were removed.")

        ttk.Button(buttons, text="Connect account", command=connect_account).pack(side="left")
        ttk.Button(buttons, text="Remove saved profile", command=remove_profile).pack(side="left", padx=8)
        ttk.Button(buttons, text="Close", command=win.destroy).pack(side="right")


    def _add_manual_trading_tab(self):
        tab = ttk.Frame(self.nb, padding=14)
        self.nb.add(tab, text="Manual Trading")
        ttk.Label(tab, text="MANUAL ORDER TICKET", style="Header.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Gold only • fresh MT5 quote • $5 estimated risk cap • every order requires confirmation.").pack(anchor="w", pady=(3, 10))
        ticket = ttk.LabelFrame(tab, text="Buy / Sell", padding=12)
        ticket.pack(fill="x", pady=(0, 12))
        self.manual_lots_var = tk.StringVar(value="0.01")
        self.manual_sl_var = tk.StringVar()
        self.manual_tp_var = tk.StringVar()
        for col, (label, var) in enumerate((("Volume (lots)", self.manual_lots_var), ("Stop Loss price", self.manual_sl_var), ("Take Profit price", self.manual_tp_var))):
            ttk.Label(ticket, text=label).grid(row=0, column=col, sticky="w", padx=5)
            ttk.Entry(ticket, textvariable=var, width=18).grid(row=1, column=col, sticky="ew", padx=5, pady=5)
        for col in range(3):
            ticket.columnconfigure(col, weight=1)
        ttk.Button(ticket, text="BUY XAUUSD", style="Approve.TButton", command=lambda: self.submit_manual_order("long")).grid(row=2, column=0, sticky="ew", padx=5, pady=(8, 0))
        ttk.Button(ticket, text="SELL XAUUSD", style="Reject.TButton", command=lambda: self.submit_manual_order("short")).grid(row=2, column=1, sticky="ew", padx=5, pady=(8, 0))
        ttk.Button(ticket, text="Refresh positions", command=self.refresh_manual_positions).grid(row=2, column=2, sticky="ew", padx=5, pady=(8, 0))
        positions = ttk.LabelFrame(tab, text="Open positions managed by this app", padding=10)
        positions.pack(fill="both", expand=True)
        self.manual_positions_tree = ttk.Treeview(positions, columns=("ticket", "symbol", "side", "volume", "open", "sl", "tp", "profit"), show="headings", height=9)
        for col, label, width in (("ticket", "Ticket", 100), ("symbol", "Symbol", 100), ("side", "Side", 80), ("volume", "Lots", 80), ("open", "Open price", 110), ("sl", "Stop Loss", 110), ("tp", "Take Profit", 110), ("profit", "P/L", 100)):
            self.manual_positions_tree.heading(col, text=label)
            self.manual_positions_tree.column(col, width=width, anchor="center")
        self.manual_positions_tree.pack(fill="both", expand=True)
        self.manual_positions_tree.bind("<<TreeviewSelect>>", self._select_manual_position)
        modify = ttk.Frame(positions)
        modify.pack(fill="x", pady=8)
        self.position_sl_var = tk.StringVar()
        self.position_tp_var = tk.StringVar()
        ttk.Label(modify, text="New SL").pack(side="left")
        ttk.Entry(modify, textvariable=self.position_sl_var, width=14).pack(side="left", padx=5)
        ttk.Label(modify, text="New TP").pack(side="left")
        ttk.Entry(modify, textvariable=self.position_tp_var, width=14).pack(side="left", padx=5)
        ttk.Button(modify, text="Modify SL / TP", command=self.modify_selected_position).pack(side="left", padx=8)
        ttk.Button(modify, text="Close selected position", command=self.close_selected_position).pack(side="left")
        self.manual_status = tk.StringVar(value="Connect to an MT5 account to use manual trading.")
        ttk.Label(tab, textvariable=self.manual_status).pack(anchor="w", pady=(8, 0))

    def submit_manual_order(self, direction: str):
        if not self.mt5.connected:
            messagebox.showwarning("Not connected", "Connect to an MT5 account first.")
            return
        try:
            if not self.mt5.is_demo_account() and not (self.live_armed and self.mt5.is_real_account()):
                raise RuntimeError("Live orders are disarmed. Arm manual live orders first; automatic live trading is disabled.")
            symbol = self.mt5.symbol
            info = self.mt5.get_symbol_info(symbol)
            tick = self.mt5.get_tick(symbol)
            if info is None or tick is None:
                raise RuntimeError("Gold symbol or current broker quote is unavailable.")
            entry = tick.ask if direction == "long" else tick.bid
            stop = float(self.manual_sl_var.get())
            target = float(self.manual_tp_var.get())
            requested = float(self.manual_lots_var.get())
            if requested <= 0:
                raise ValueError("Volume must be greater than zero.")
            if direction == "long" and not (stop < entry < target):
                raise ValueError("For BUY, Stop Loss must be below current Ask and Take Profit above it.")
            if direction == "short" and not (target < entry < stop):
                raise ValueError("For SELL, Take Profit must be below current Bid and Stop Loss above it.")
            sizing = self.risk_manager.size_position(symbol, direction, entry, stop, requested, requested, self.config.max_risk_usd)
            if not sizing["ok"]:
                raise RuntimeError(sizing["reason"])
            real = self.mt5.is_real_account()
            warning = f"{direction.upper()} {symbol} at current quote {entry:.{info.digits}f}\\nVolume: {sizing['volume']} lots\\nSL: {stop}\\nTP: {target}\\nEstimated buffered risk: USD {sizing['buffered_loss']:.2f} (cap USD {sizing['risk_cap']:.2f})\\n\\nActual loss may exceed this estimate. " + ("REAL MONEY ORDER." if real else "Demo account order.")
            if not messagebox.askyesno("Confirm manual order", warning, icon="warning"):
                return
            result = self.mt5.send_approved_order(symbol, direction, sizing["volume"], round(stop, info.digits), round(target, info.digits), allow_real=bool(real and self.live_armed), comment="Manual ticket")
            self.manual_status.set(f"Order accepted by broker. Ticket #{result.order}.")
            self._log(f"Manual {direction.upper()} submitted: ticket {result.order}, {sizing['volume']} lots.")
            self.refresh_manual_positions()
        except Exception as exc:
            self.manual_status.set("Order blocked or failed.")
            messagebox.showerror("Manual order not submitted", str(exc), parent=self)

    def refresh_manual_positions(self):
        if not self.mt5.connected:
            self.manual_status.set("Connect to MT5 first.")
            return
        for iid in self.manual_positions_tree.get_children():
            self.manual_positions_tree.delete(iid)
        try:
            positions = self.mt5.get_app_positions()
            for position in positions:
                side = "BUY" if position.type == 0 else "SELL"
                self.manual_positions_tree.insert("", "end", iid=str(position.ticket), values=(
                    position.ticket, position.symbol, side, position.volume,
                    position.price_open, position.sl, position.tp, position.profit))
            self.manual_status.set(f"{len(positions)} app-managed open position(s). Unrelated MT5 positions are intentionally excluded.")
        except Exception as exc:
            self.manual_status.set("Could not refresh positions: " + str(exc))

    def _select_manual_position(self, _event=None):
        selected = self.manual_positions_tree.selection()
        if not selected:
            return
        values = self.manual_positions_tree.item(selected[0], "values")
        self.position_sl_var.set(str(values[5]))
        self.position_tp_var.set(str(values[6]))

    def close_selected_position(self):
        selected = self.manual_positions_tree.selection()
        if not selected:
            messagebox.showinfo("Select a position", "Select an app-managed position first.")
            return
        ticket = int(selected[0])
        if not messagebox.askyesno("Confirm close", f"Close app-managed position #{ticket}? Check the current quote and result in MT5.", icon="warning"):
            return
        try:
            self.mt5.close_app_position(ticket)
            self.manual_status.set(f"Close request accepted for position #{ticket}.")
            self._log(f"Manual close submitted for app-managed position #{ticket}.")
            self.refresh_manual_positions()
        except Exception as exc:
            messagebox.showerror("Close failed", str(exc), parent=self)

    def modify_selected_position(self):
        selected = self.manual_positions_tree.selection()
        if not selected:
            messagebox.showinfo("Select a position", "Select an app-managed position first.")
            return
        ticket = int(selected[0])
        try:
            sl, tp = float(self.position_sl_var.get()), float(self.position_tp_var.get())
            if not messagebox.askyesno("Confirm SL / TP change", f"Modify position #{ticket}?\\nNew SL: {sl}\\nNew TP: {tp}", icon="warning"):
                return
            self.mt5.modify_app_position(ticket, sl, tp)
            self.manual_status.set(f"Stop Loss / Take Profit updated for #{ticket}.")
            self._log(f"SL/TP modification submitted for app-managed position #{ticket}.")
            self.refresh_manual_positions()
        except Exception as exc:
            messagebox.showerror("Modify failed", str(exc), parent=self)

    def _add_signal_hub(self):
        from .signal_source_settings import load_signal_sources, save_signal_sources

        tab = ttk.Frame(self.nb, padding=12)
        self.nb.add(tab, text="Signal Hub")
        ttk.Label(tab, text="External signal providers — independent settings", style="Header.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Configure providers now or later. HTTPS RSS/JSON only; candidates are unverified and review-only.").pack(anchor="w", pady=(3, 8))

        settings = ttk.LabelFrame(tab, text="Provider settings (saved locally on this Windows user)", padding=8)
        settings.pack(fill="x", pady=(0, 8))
        self.signal_sources = load_signal_sources()
        self.source_name_var = tk.StringVar()
        self.source_url_var = tk.StringVar()
        self.source_enabled_var = tk.BooleanVar(value=True)
        fields = ttk.Frame(settings)
        fields.pack(fill="x")
        ttk.Label(fields, text="Provider name").grid(row=0, column=0, sticky="w")
        ttk.Entry(fields, textvariable=self.source_name_var, width=24).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(fields, text="HTTPS feed/API URL").grid(row=0, column=1, sticky="w")
        ttk.Entry(fields, textvariable=self.source_url_var).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        ttk.Checkbutton(fields, text="Enabled", variable=self.source_enabled_var).grid(row=1, column=2, sticky="w")
        fields.columnconfigure(1, weight=1)
        actions = ttk.Frame(settings)
        actions.pack(fill="x", pady=(7, 3))
        ttk.Button(actions, text="Add / update provider", command=self._save_signal_source).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Remove selected", command=self._remove_signal_source).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Clear fields", command=self._clear_signal_source_fields).pack(side="left")
        self.source_tree = ttk.Treeview(settings, columns=("name", "url", "enabled"), show="headings", height=3)
        for col, label, width in (("name", "Provider", 180), ("url", "Feed URL", 600), ("enabled", "Enabled", 80)):
            self.source_tree.heading(col, text=label)
            self.source_tree.column(col, width=width, anchor="w")
        self.source_tree.pack(fill="x", pady=(6, 0))
        self.source_tree.bind("<<TreeviewSelect>>", self._select_signal_source)
        self._refresh_signal_source_list()

        fetch_row = ttk.Frame(tab)
        fetch_row.pack(fill="x", pady=4)
        ttk.Button(fetch_row, text="Fetch enabled providers", command=self._fetch_external_signals).pack(side="left")
        self.feed_status = tk.StringVar(value="No providers configured. Add them here whenever you're ready.")
        ttk.Label(fetch_row, textvariable=self.feed_status).pack(side="left", padx=10)
        self.feed_tree = ttk.Treeview(tab, columns=("source", "published", "side", "entry", "stop", "target", "status"), show="headings", height=8)
        for col, label, width in (("source", "Source", 190), ("published", "Published", 140), ("side", "Direction", 80), ("entry", "Entry", 80), ("stop", "Stop", 80), ("target", "Target", 80), ("status", "Review status", 170)):
            self.feed_tree.heading(col, text=label)
            self.feed_tree.column(col, width=width, anchor="center")
        self.feed_tree.pack(fill="both", expand=True, pady=6)
        self.feed_detail = tk.Text(tab, height=5, wrap="word")
        self.feed_detail.pack(fill="x")
        self.feed_tree.bind("<<TreeviewSelect>>", self._show_external_signal)
        self.external_signals = []

    def _refresh_signal_source_list(self):
        for iid in self.source_tree.get_children():
            self.source_tree.delete(iid)
        for index, source in enumerate(self.signal_sources):
            self.source_tree.insert("", "end", iid=str(index), values=(source["name"], source["url"], "Yes" if source.get("enabled", True) else "No"))

    def _select_signal_source(self, _event=None):
        selected = self.source_tree.selection()
        if not selected:
            return
        source = self.signal_sources[int(selected[0])]
        self.source_name_var.set(source["name"])
        self.source_url_var.set(source["url"])
        self.source_enabled_var.set(bool(source.get("enabled", True)))

    def _clear_signal_source_fields(self):
        self.source_tree.selection_remove(self.source_tree.selection())
        self.source_name_var.set("")
        self.source_url_var.set("")
        self.source_enabled_var.set(True)

    def _save_signal_source(self):
        name = self.source_name_var.get().strip()
        url = self.source_url_var.get().strip()
        if not name or not url.startswith("https://"):
            messagebox.showwarning("Provider settings", "Enter a provider name and a valid HTTPS URL.", parent=self)
            return
        selected = self.source_tree.selection()
        item = {"name": name[:80], "url": url, "enabled": bool(self.source_enabled_var.get())}
        if selected:
            self.signal_sources[int(selected[0])] = item
        else:
            self.signal_sources.append(item)
        save_signal_sources(self.signal_sources)
        self._refresh_signal_source_list()
        self._clear_signal_source_fields()
        self.feed_status.set("Provider settings saved locally. No provider credentials are stored.")

    def _remove_signal_source(self):
        selected = self.source_tree.selection()
        if not selected:
            return
        del self.signal_sources[int(selected[0])]
        save_signal_sources(self.signal_sources)
        self._refresh_signal_source_list()
        self._clear_signal_source_fields()
        self.feed_status.set("Selected provider removed from local settings.")

    def _fetch_external_signals(self):
        enabled = [source for source in self.signal_sources if source.get("enabled", True)]
        if not enabled:
            self.feed_status.set("No enabled providers. Add or enable one in Provider settings.")
            return
        items = []
        errors = []
        for source in enabled:
            try:
                rows = fetch_signal_feed(source["url"])
                for row in rows:
                    row["source"] = source["name"]
                items.extend(rows)
            except Exception as exc:
                errors.append(source["name"] + ": " + str(exc))
        self.external_signals = items
        for iid in self.feed_tree.get_children():
            self.feed_tree.delete(iid)
        for index, item in enumerate(items):
            self.feed_tree.insert("", "end", iid=str(index), values=(
                item["source"], item.get("published") or "—", item["direction"].upper(),
                item.get("entry") if item.get("entry") is not None else "—",
                item.get("stop") if item.get("stop") is not None else "—",
                item.get("target") if item.get("target") is not None else "—",
                "UNVERIFIED • REVIEW ONLY"))
        self.feed_status.set(str(len(items)) + " candidate(s) received. None are validated or executable.")
        if errors:
            messagebox.showwarning("Some providers failed", "\\n".join(errors), parent=self)
        elif not items:
            self.feed_status.set("Feeds checked; no recognizable XAUUSD BUY/SELL candidates found.")

    def _show_external_signal(self, _event=None):
        selection = self.feed_tree.selection()
        if not selection:
            return
        item = self.external_signals[int(selection[0])]
        self.feed_detail.delete("1.0", "end")
        self.feed_detail.insert("end", item.get("raw_text", "") + "\n\nParsed candidate only — verify source, timestamp, symbol, price and risk independently. No order action is available from this panel.")

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
