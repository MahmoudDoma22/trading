from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PALETTE = {
    "window": "#10151d", "panel": "#18212c", "panel_alt": "#202b38",
    "text": "#e6edf3", "muted": "#9aa9b8", "border": "#334155",
    "green": "#12b886", "red": "#ff5b61", "amber": "#f0b429", "blue": "#5aa9ff",
}


def apply_dark_theme(root: tk.Misc) -> None:
    """Apply consistent dark colors to ttk and classic Tk controls, including dialogs."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    p = PALETTE
    style.configure(".", background=p["window"], foreground=p["text"], font=("Segoe UI", 9))
    style.configure("TFrame", background=p["window"])
    style.configure("TLabel", background=p["window"], foreground=p["text"])
    style.configure("TButton", background=p["panel_alt"], foreground=p["text"], bordercolor=p["border"], padding=(9, 5))
    style.map("TButton", background=[("active", "#314155"), ("pressed", "#263447")], foreground=[("disabled", p["muted"])])
    style.configure("TEntry", fieldbackground=p["panel"], foreground=p["text"], insertcolor=p["text"], bordercolor=p["border"])
    style.configure("TCombobox", fieldbackground=p["panel"], background=p["panel_alt"], foreground=p["text"], arrowcolor=p["text"])
    style.map("TCombobox", fieldbackground=[("readonly", p["panel"])], foreground=[("readonly", p["text"])])
    style.configure("TCheckbutton", background=p["window"], foreground=p["text"])
    style.configure("TRadiobutton", background=p["window"], foreground=p["text"])
    style.configure("TNotebook", background=p["window"], bordercolor=p["border"])
    style.configure("TNotebook.Tab", background=p["panel"], foreground=p["muted"], padding=(12, 7))
    style.map("TNotebook.Tab", background=[("selected", p["panel_alt"])], foreground=[("selected", p["text"])])
    style.configure("TLabelframe", background=p["panel"], foreground=p["text"], bordercolor=p["border"])
    style.configure("TLabelframe.Label", background=p["panel"], foreground=p["blue"], font=("Segoe UI", 9, "bold"))
    style.configure("Treeview", background=p["panel"], fieldbackground=p["panel"], foreground=p["text"], rowheight=26, bordercolor=p["border"])
    style.configure("Treeview.Heading", background=p["panel_alt"], foreground=p["text"], relief="flat")
    style.map("Treeview", background=[("selected", "#254c70")], foreground=[("selected", "#ffffff")])
    style.configure("Vertical.TScrollbar", background=p["panel_alt"], troughcolor=p["window"], arrowcolor=p["text"])
    style.configure("Horizontal.TScrollbar", background=p["panel_alt"], troughcolor=p["window"], arrowcolor=p["text"])

    def visit(widget):
        try:
            if isinstance(widget, tk.Text):
                widget.configure(background=p["panel"], foreground=p["text"], insertbackground=p["text"],
                                 selectbackground="#254c70", selectforeground="#ffffff", relief="flat",
                                 highlightthickness=1, highlightbackground=p["border"], highlightcolor=p["blue"])
            elif isinstance(widget, tk.Entry):
                widget.configure(background=p["panel"], foreground=p["text"], insertbackground=p["text"],
                                 selectbackground="#254c70", selectforeground="#ffffff", relief="flat",
                                 highlightthickness=1, highlightbackground=p["border"])
            elif isinstance(widget, tk.Listbox):
                widget.configure(background=p["panel"], foreground=p["text"], selectbackground="#254c70",
                                 selectforeground="#ffffff", relief="flat")
            elif isinstance(widget, (tk.Frame, tk.Toplevel)):
                widget.configure(background=p["window"])
            elif isinstance(widget, tk.Label):
                widget.configure(background=p["window"], foreground=p["text"])
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            visit(child)
    visit(root)
