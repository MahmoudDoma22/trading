from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .config import BotDefinition
from .strategy_engine import TIMEFRAMES


class BotManagerDialog(tk.Toplevel):
    """Visual bot library editor. It edits strategy definitions only, never sends orders."""

    def __init__(self, master, manager, on_change=None):
        super().__init__(master)
        self.manager = manager
        self.on_change = on_change
        self.title("DR Trading Terminal | Bot Manager")
        self.geometry("980x610")
        self.transient(master)
        self.grab_set()

        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="BOT LIBRARY", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.tree = ttk.Treeview(left, columns=("state", "tf"), show="tree headings", height=22)
        self.tree.heading("#0", text="Bot")
        self.tree.heading("state", text="Status")
        self.tree.heading("tf", text="Timeframe")
        self.tree.column("#0", width=250)
        self.tree.column("state", width=85, anchor="center")
        self.tree.column("tf", width=75, anchor="center")
        self.tree.pack(fill="y", expand=True, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._select)

        right = ttk.Frame(self, padding=12)
        right.pack(side="left", fill="both", expand=True)
        self.vars = {key: tk.StringVar() for key in ("name", "timeframe", "confidence", "risk", "lots", "atr", "description")}
        self.enabled_var = tk.BooleanVar(value=True)
        fields = (("Bot name", "name"), ("Default timeframe", "timeframe"), ("Minimum signal score (0–100)", "confidence"), ("Risk cap per trade (USD, max $5)", "risk"), ("Maximum lots", "lots"), ("Stop distance (ATR multiplier)", "atr"))
        for row, (label, key) in enumerate(fields):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=5)
            if key == "timeframe":
                widget = ttk.Combobox(right, textvariable=self.vars[key], values=TIMEFRAMES, state="readonly", width=18)
            else:
                widget = ttk.Entry(right, textvariable=self.vars[key], width=22)
            widget.grid(row=row, column=1, sticky="w", pady=5)
        ttk.Label(right, text="Description").grid(row=6, column=0, sticky="nw", pady=5)
        self.description = tk.Text(right, height=5, width=58, wrap="word")
        self.description.grid(row=6, column=1, sticky="w", pady=5)
        ttk.Checkbutton(right, text="Enabled for signal analysis", variable=self.enabled_var).grid(row=7, column=1, sticky="w", pady=5)
        ttk.Label(right, text="XAUUSD only • $5 maximum risk cap • strategy score is not win probability", foreground="#9b5b00").grid(row=8, column=0, columnspan=2, sticky="w", pady=8)

        actions = ttk.Frame(right)
        actions.grid(row=9, column=0, columnspan=2, sticky="ew", pady=8)
        for label, command in (("New bot", self._new), ("Save changes", self._save), ("Duplicate", self._duplicate), ("Delete", self._delete), ("Enable / disable", self._toggle)):
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=3)
        files = ttk.Frame(right)
        files.grid(row=10, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(files, text="Import bots…", command=self._import).pack(side="left", padx=3)
        ttk.Button(files, text="Export bots…", command=self._export).pack(side="left", padx=3)
        ttk.Button(files, text="Restore defaults", command=self._reset).pack(side="left", padx=3)
        self.selected_name = None
        self._refresh()

    def _refresh(self, select_name=None):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for index, bot in enumerate(self.manager.get_bots()):
            enabled = self.manager.is_enabled(bot)
            self.tree.insert("", "end", iid=str(index), text=bot.name,
                             values=("ENABLED" if enabled else "DISABLED", bot.default_timeframe))
        if select_name:
            for iid in self.tree.get_children():
                if self.tree.item(iid, "text") == select_name:
                    self.tree.selection_set(iid)
                    self.tree.focus(iid)
                    self._select()
                    break

    def _selected(self):
        selected = self.tree.selection()
        if not selected:
            return None
        index = int(selected[0])
        bots = self.manager.get_bots()
        return bots[index] if index < len(bots) else None

    def _select(self, _event=None):
        bot = self._selected()
        if not bot:
            return
        self.selected_name = bot.name
        for key, value in (("name", bot.name), ("timeframe", bot.default_timeframe),
                           ("confidence", bot.min_confidence), ("risk", bot.max_risk_usd),
                           ("lots", bot.max_trade_size_lots), ("atr", bot.settings.get("stop_atr_multiplier", 1.5))):
            self.vars[key].set(str(value))
        self.description.delete("1.0", "end")
        self.description.insert("1.0", bot.description)
        self.enabled_var.set(self.manager.is_enabled(bot))

    def _read_form(self):
        return BotDefinition(
            name=self.vars["name"].get().strip(),
            description=self.description.get("1.0", "end").strip(),
            instrument="XAUUSD",
            default_timeframe=self.vars["timeframe"].get().strip(),
            min_confidence=float(self.vars["confidence"].get()),
            max_risk_usd=float(self.vars["risk"].get()),
            max_trade_size_lots=float(self.vars["lots"].get()),
            auto_trade_enabled=False,
            settings={"timeframes": [self.vars["timeframe"].get().strip()],
                      "stop_atr_multiplier": float(self.vars["atr"].get()),
                      "enabled": self.enabled_var.get()},
        )

    def _save(self):
        try:
            bot = self._read_form()
            if self.selected_name:
                self.manager.update_bot(self.selected_name, bot)
            else:
                self.manager.add_bot(bot)
            self.selected_name = bot.name
            self._refresh(bot.name)
            if self.on_change:
                self.on_change(bot.name)
            messagebox.showinfo("Bot saved", "Bot configuration saved locally.", parent=self)
        except Exception as exc:
            messagebox.showerror("Cannot save bot", str(exc), parent=self)

    def _new(self):
        self.selected_name = None
        for key, value in (("name", "New XAUUSD Bot"), ("timeframe", "M15"), ("confidence", "20"), ("risk", "5"), ("lots", "0.01"), ("atr", "1.5")):
            self.vars[key].set(value)
        self.description.delete("1.0", "end")
        self.description.insert("1.0", "Describe the strategy and its entry conditions.")
        self.enabled_var.set(True)
        self.tree.selection_remove(self.tree.selection())

    def _duplicate(self):
        bot = self._selected()
        if not bot:
            messagebox.showwarning("Select a bot", "Select a bot to duplicate.", parent=self)
            return
        try:
            clone = self.manager.duplicate_bot(bot.name)
            self._refresh(clone.name)
            if self.on_change:
                self.on_change(clone.name)
        except Exception as exc:
            messagebox.showerror("Duplicate failed", str(exc), parent=self)

    def _delete(self):
        bot = self._selected()
        if not bot:
            return
        if not messagebox.askyesno("Delete bot", f"Delete '{bot.name}' from the local library?", parent=self):
            return
        try:
            self.manager.delete_bot(bot.name)
            self.selected_name = None
            self._refresh()
            if self.on_change:
                self.on_change(None)
        except Exception as exc:
            messagebox.showerror("Delete failed", str(exc), parent=self)

    def _toggle(self):
        bot = self._selected()
        if not bot:
            return
        try:
            self.manager.set_enabled(bot.name, not self.manager.is_enabled(bot))
            self._refresh(bot.name)
            if self.on_change:
                self.on_change(bot.name)
        except Exception as exc:
            messagebox.showerror("Update failed", str(exc), parent=self)

    def _import(self):
        path = filedialog.askopenfilename(parent=self, filetypes=(("Bot JSON", "*.json"),))
        if not path:
            return
        try:
            count = self.manager.import_json(path)
            self._refresh()
            if self.on_change:
                self.on_change(None)
            messagebox.showinfo("Import complete", f"Imported {count} bot(s).", parent=self)
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)

    def _export(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=(("Bot JSON", "*.json"),), initialfile="dr_bots.json")
        if not path:
            return
        try:
            self.manager.export_json(path)
            messagebox.showinfo("Export complete", "Bot library exported.", parent=self)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    def _reset(self):
        if not messagebox.askyesno("Restore defaults", "Replace your current bot library with the four original research bots?", parent=self):
            return
        try:
            self.manager.reset_defaults()
            self.selected_name = None
            self._refresh()
            if self.on_change:
                self.on_change(None)
        except Exception as exc:
            messagebox.showerror("Restore failed", str(exc), parent=self)
