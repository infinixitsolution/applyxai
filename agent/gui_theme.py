"""Visual theme for the ApplyXAI desktop agent (tkinter / ttk)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Brand palette (aligned with web app)
BG = "#f1f5f9"
SURFACE = "#ffffff"
BORDER = "#e2e8f0"
TEXT = "#0f172a"
MUTED = "#64748b"
BRAND = "#2563eb"
BRAND_HOVER = "#1d4ed8"
BRAND_LIGHT = "#dbeafe"
SUCCESS = "#16a34a"
DANGER = "#dc2626"
WARN = "#d97706"

FONT = "Segoe UI"
MONO = "Consolas"


def setup(root: tk.Tk) -> ttk.Style:
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT, font=(FONT, 10))
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE)
    style.configure("TLabel", background=BG, foreground=TEXT, font=(FONT, 10))
    style.configure("Card.TLabel", background=SURFACE, foreground=TEXT, font=(FONT, 10))
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=(FONT, 9))
    style.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED, font=(FONT, 9))
    style.configure("Title.TLabel", background=SURFACE, foreground=TEXT, font=(FONT, 18, "bold"))
    style.configure("Version.TLabel", background=SURFACE, foreground=MUTED, font=(FONT, 9))
    style.configure("Hero.TLabel", background=BRAND_LIGHT, foreground=TEXT, font=(FONT, 10))

    style.configure(
        "TLabelframe",
        background=BG,
        bordercolor=BORDER,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=BG,
        foreground=TEXT,
        font=(FONT, 10, "bold"),
    )
    style.configure("Card.TLabelframe", background=SURFACE)
    style.configure("Card.TLabelframe.Label", background=SURFACE, font=(FONT, 10, "bold"))

    style.configure(
        "TButton",
        padding=(14, 8),
        font=(FONT, 10, "bold"),
    )
    style.configure("Primary.TButton", background=BRAND, foreground="#ffffff")
    style.map(
        "Primary.TButton",
        background=[("active", BRAND_HOVER), ("disabled", "#94a3b8")],
        foreground=[("disabled", "#f8fafc")],
    )
    style.configure("Secondary.TButton", background=SURFACE, foreground=TEXT)
    style.map("Secondary.TButton", background=[("active", BORDER)])

    style.configure("Danger.TButton", background="#fef2f2", foreground=DANGER)
    style.map("Danger.TButton", background=[("active", "#fee2e2")])

    style.configure("TEntry", padding=8, fieldbackground=SURFACE)
    style.configure("TScrollbar", background=BG, troughcolor=BG, arrowcolor=MUTED)
    return style


def card(parent: tk.Widget, **grid) -> ttk.Frame:
    frame = ttk.Frame(parent, style="Card.TFrame", padding=16)
    if grid:
        frame.grid(**grid, sticky="nsew")
    return frame
