"""
Windows GUI for ApplyXAI Agent — dashboard layout with sidebar navigation.
"""

import os
import sys

from agent.engine_bootstrap import run_engine_child_if_requested
from agent.win_process import background_creationflags

if run_engine_child_if_requested():
    raise SystemExit(0)
import subprocess
import threading
import queue
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from datetime import datetime

from agent import branding_paths
from agent.gui_theme import (
    BG,
    BORDER,
    BRAND,
    BRAND_HOVER,
    BRAND_LIGHT,
    BRAND_SOFT,
    DANGER,
    DANGER_SOFT,
    LOG_BG,
    MUTED,
    PAGE,
    SIDEBAR,
    SUCCESS,
    SUCCESS_BG,
    SUCCESS_FG,
    SURFACE,
    TEXT,
    TEXT_SOFT,
    setup as setup_theme,
)

try:
    from agent import config
    from agent.client import ApiClient, ApiError, NetworkError
    from agent import AGENT_VERSION
    AGENT_MODULES_AVAILABLE = True
except ImportError:
    AGENT_MODULES_AVAILABLE = False
    AGENT_VERSION = "1.1.5"


class AgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"ApplyXAI Agent v{AGENT_VERSION}")
        self.root.minsize(1024, 720)
        self.root.resizable(True, True)
        self._fit_window()
        setup_theme(self.root)
        self._mascot_img = None
        self._sidebar_mascot = None
        self._apply_window_icon()

        self.agent_process = None
        self.agent_running = False
        self.command_queue = queue.Queue()
        self.home = self._get_home()
        self._log_has_content = False
        self._connect_preset = "live" if getattr(sys, "frozen", False) else "local"
        self._nav_buttons: dict[str, tk.Frame] = {}
        self._views: dict[str, tk.Frame] = {}

        self._build_ui()
        self._process_queue()
        self._refresh_status()
        self._start_local_wake_server()
        self._load_linkedin_from_disk()
        self.root.after(1500, self._schedule_stats_refresh)

    def _get_home(self):
        if AGENT_MODULES_AVAILABLE:
            return str(config.default_home())
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            return str(Path(localappdata) / "ApplyXAI" / "agent")
        return str(Path.home() / ".applyxai" / "agent")

    def _apply_window_icon(self) -> None:
        ico = branding_paths.window_icon_ico()
        if ico.is_file():
            try:
                self.root.iconbitmap(str(ico))
            except tk.TclError:
                pass
        photo = self._load_mascot_photo(max_side=32)
        if photo is not None:
            try:
                self.root.iconphoto(True, photo)
            except tk.TclError:
                pass

    def _load_mascot_photo(self, max_side: int = 96, attr: str = "_mascot_img") -> tk.PhotoImage | None:
        path = branding_paths.mascot_png()
        if not path.is_file():
            return None
        try:
            img = tk.PhotoImage(file=str(path))
            w, h = img.width(), img.height()
            scale = max(max(w, h) // max_side, 1)
            if scale > 1:
                img = img.subsample(scale, scale)
            setattr(self, attr, img)
            return img
        except tk.TclError:
            return None

    def _fit_window(self) -> None:
        self.root.update_idletasks()
        screen_w = max(self.root.winfo_screenwidth(), 1024)
        screen_h = max(self.root.winfo_screenheight(), 720)
        width = min(1320, max(1024, int(screen_w * 0.82)))
        height = min(920, max(720, int(screen_h * 0.85)))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 8)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------------------ UI shell
    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        shell = tk.Frame(self.root, bg=BG)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=0, minsize=272)
        shell.columnconfigure(1, weight=0, minsize=1)
        shell.columnconfigure(2, weight=1)
        shell.rowconfigure(0, weight=1)

        self._sidebar_frame = tk.Frame(shell, bg=SIDEBAR, width=272)
        self._sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self._sidebar_frame.grid_propagate(False)
        tk.Frame(shell, bg=BORDER, width=1).grid(row=0, column=1, sticky="ns")

        self._build_sidebar(self._sidebar_frame)
        main = tk.Frame(shell, bg=PAGE)
        main.grid(row=0, column=2, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        self._build_top_bar(main)
        self._build_views(main)
        self._build_footer(main)
        self._set_nav("home")
        self._sidebar_frame.lift()
        self.root.update_idletasks()

    def _build_sidebar(self, parent):
        side = parent

        brand = tk.Frame(side, bg=SIDEBAR)
        brand.pack(fill=tk.X, padx=16, pady=(20, 12))
        mascot = self._load_mascot_photo(max_side=36, attr="_sidebar_mascot")
        if mascot:
            tk.Label(brand, image=mascot, bg=SIDEBAR, borderwidth=0).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(
            brand, text="ApplyXAI Agent", bg=SIDEBAR, fg=TEXT,
            font=("Segoe UI", 13, "bold"), justify=tk.LEFT,
        ).pack(side=tk.LEFT)

        tk.Label(
            side, text="MENU", bg=SIDEBAR, fg=MUTED, font=("Segoe UI", 8, "bold"),
        ).pack(anchor=tk.W, padx=20, pady=(0, 4))

        nav_host = tk.Frame(side, bg=SIDEBAR)
        nav_host.pack(fill=tk.BOTH, expand=True, padx=8)
        nav = tk.Frame(nav_host, bg=SIDEBAR)
        nav.pack(fill=tk.X, pady=(0, 8))
        for key, label, icon in (
            ("home", "Home", "⌂"),
            ("automation", "Automation", "⚡"),
            ("log", "Activity Log", "☰"),
            ("linkedin", "LinkedIn", "in"),
            ("settings", "Settings", "⚙"),
        ):
            self._nav_buttons[key] = self._nav_item(nav, icon, label, lambda k=key: self._set_nav(k))

        promo = tk.Frame(side, bg=BRAND_SOFT, highlightbackground=BRAND_LIGHT, highlightthickness=1)
        promo.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=12)
        mini = self._load_mascot_photo(max_side=56, attr="_promo_mascot")
        if mini:
            tk.Label(promo, image=mini, bg=BRAND_SOFT).pack(pady=(14, 6))
        tk.Label(
            promo, text="Let AI find your next opportunity",
            bg=BRAND_SOFT, fg=TEXT, font=("Segoe UI", 10, "bold"), wraplength=200, justify=tk.CENTER,
        ).pack(padx=12)
        tk.Label(
            promo, text="Automate. Apply. Grow.",
            bg=BRAND_SOFT, fg=MUTED, font=("Segoe UI", 9), wraplength=200, justify=tk.CENTER,
        ).pack(padx=12, pady=(4, 14))

    def _nav_item(self, parent, icon: str, label: str, command) -> tk.Frame:
        row = tk.Frame(parent, bg=SIDEBAR, cursor="hand2")
        row.pack(fill=tk.X, pady=2)
        bar = tk.Frame(row, bg=SIDEBAR, width=4)
        bar.pack(side=tk.LEFT, fill=tk.Y)
        inner = tk.Frame(row, bg=SIDEBAR)
        inner.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8), pady=8)
        tk.Label(inner, text=icon, bg=SIDEBAR, fg=BRAND, font=("Segoe UI", 11, "bold"), width=2).pack(side=tk.LEFT)
        lbl = tk.Label(inner, text=label, bg=SIDEBAR, fg=TEXT_SOFT, font=("Segoe UI", 10))
        lbl.pack(side=tk.LEFT, padx=(6, 0))

        def activate(_e=None):
            command()

        for w in (row, inner, lbl):
            w.bind("<Button-1>", activate)
        row._nav_bar = bar
        row._nav_inner = inner
        row._nav_lbl = lbl
        return row

    def _set_nav(self, key: str):
        for nav_key, row in self._nav_buttons.items():
            active = nav_key == key
            bg = BRAND_SOFT if active else SIDEBAR
            fg = BRAND if active else TEXT_SOFT
            weight = "bold" if active else "normal"
            row._nav_bar.configure(bg=BRAND if active else SIDEBAR)
            row._nav_inner.configure(bg=bg)
            row._nav_lbl.configure(bg=bg, fg=fg, font=("Segoe UI", 10, weight))
            for child in row._nav_inner.winfo_children():
                if isinstance(child, tk.Label) and child is not row._nav_lbl:
                    child.configure(bg=bg, fg=BRAND if active else TEXT_SOFT)
        for frame in self._views.values():
            frame.grid_remove()
        target = {"automation": "automation", "log": "log", "linkedin": "linkedin", "settings": "settings"}.get(
            key, "home",
        )
        self._views[target].grid(row=0, column=0, sticky="nsew")
        self._place_linkedin_card(key == "linkedin")
        if key in ("home", "automation"):
            self._refresh_stats()
        if key == "settings":
            self._load_settings_display()

    def _build_top_bar(self, parent):
        bar = tk.Frame(parent, bg=PAGE)
        bar.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 8))
        bar.columnconfigure(0, weight=1)

        left = tk.Frame(bar, bg=PAGE)
        left.grid(row=0, column=0, sticky="w")
        tk.Label(
            left, text="Welcome to ApplyXAI Agent 👋", bg=PAGE, fg=TEXT,
            font=("Segoe UI", 22, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            left,
            text="Your personal AI job application assistant. Sit back and let us do the work.",
            bg=PAGE, fg=MUTED, font=("Segoe UI", 10),
        ).pack(anchor=tk.W, pady=(4, 0))

        right = tk.Frame(bar, bg=PAGE)
        right.grid(row=0, column=1, sticky="e")
        self._pill_connected = tk.Label(
            right, text="● Disconnected", bg="#fee2e2", fg=DANGER,
            font=("Segoe UI", 9, "bold"), padx=12, pady=6,
        )
        self._pill_connected.pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(right, text="🔔", bg=PAGE, fg=MUTED, font=("Segoe UI", 14)).pack(side=tk.LEFT, padx=4)
        self._avatar = tk.Label(
            right, text="AX", bg=BRAND, fg="#ffffff",
            font=("Segoe UI", 10, "bold"), width=3, height=1,
        )
        self._avatar.pack(side=tk.LEFT, padx=(8, 0))

    def _build_views(self, parent):
        stack = tk.Frame(parent, bg=PAGE)
        stack.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 8))
        stack.columnconfigure(0, weight=1)
        stack.rowconfigure(0, weight=1)

        home = tk.Frame(stack, bg=PAGE)
        home.columnconfigure(0, weight=3)
        home.columnconfigure(1, weight=2)
        home.rowconfigure(0, weight=1)
        self._views["home"] = home
        self._build_dashboard(home)

        automation = tk.Frame(stack, bg=PAGE)
        automation.columnconfigure(0, weight=1)
        automation.rowconfigure(0, weight=1)
        self._views["automation"] = automation
        self._build_automation_page(automation)

        log_view = tk.Frame(stack, bg=PAGE)
        log_view.columnconfigure(0, weight=1)
        log_view.rowconfigure(0, weight=1)
        self._views["log"] = log_view
        log_view_body = self._card(
            log_view, "Activity Log", "📄", "Real-time logs of the agent's activity.", expand=True,
        )
        log_view_body.master.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._attach_log_panel(log_view_body, secondary=True)

        linkedin_view = tk.Frame(stack, bg=PAGE)
        linkedin_view.columnconfigure(0, weight=1)
        linkedin_view.rowconfigure(0, weight=1)
        self._views["linkedin"] = linkedin_view
        self._linkedin_nav_host = tk.Frame(linkedin_view, bg=PAGE)
        self._linkedin_nav_host.grid(row=0, column=0, sticky="n", padx=24, pady=24)
        self._build_linkedin_card(self._linkedin_nav_host)

        settings_view = tk.Frame(stack, bg=PAGE)
        settings_view.columnconfigure(0, weight=1)
        self._views["settings"] = settings_view
        scard = self._card(
            settings_view,
            "Settings",
            "⚙",
            "Local agent data on this PC (passwords are never shown here).",
        )
        scard.master.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        scard.rowconfigure(2, weight=1)
        settings_view.rowconfigure(0, weight=1)
        self.settings_text = scrolledtext.ScrolledText(
            scard, height=16, wrap=tk.WORD, font=("Consolas", 9), bg=LOG_BG, fg=TEXT,
        )
        self.settings_text.grid(row=2, column=0, sticky="nsew", pady=(12, 8))
        self.settings_text.config(state=tk.DISABLED)
        btn_row = tk.Frame(scard, bg=SURFACE)
        btn_row.grid(row=3, column=0, sticky="ew")
        ttk.Button(btn_row, text="↻  Refresh", style="Secondary.TButton", command=self._load_settings_display).pack(
            side=tk.LEFT, padx=(0, 8),
        )
        ttk.Button(btn_row, text="Disconnect from ApplyXAI", style="Danger.TButton", command=self._on_unpair).pack(
            side=tk.LEFT,
        )
        tk.Label(
            scard, text=f"Version {AGENT_VERSION} · Folder: {self.home}", bg=SURFACE, fg=MUTED,
            font=("Segoe UI", 9), wraplength=720, justify=tk.LEFT,
        ).grid(row=4, column=0, sticky=tk.W, pady=(12, 0))

    def _build_stats_row(self, parent, row: int) -> dict:
        stats_row = tk.Frame(parent, bg=PAGE)
        stats_row.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        for c in range(4):
            stats_row.columnconfigure(c, weight=1)
        return {
            "applied": self._metric_card(stats_row, 0, "Applied (month)", "✓", "—"),
            "today": self._metric_card(stats_row, 1, "Applied today", "📅", "—"),
            "success": self._metric_card(stats_row, 2, "Success rate", "%", "—"),
            "run": self._metric_card(stats_row, 3, "Active run", "⚡", "None"),
        }

    def _build_dashboard(self, parent):
        left = tk.Frame(parent, bg=PAGE)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 10), pady=8)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(4, weight=1)

        status_row = tk.Frame(left, bg=PAGE)
        status_row.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        status_row.columnconfigure(0, weight=1)
        status_row.columnconfigure(1, weight=1)
        self._server_card = self._metric_card(status_row, 0, "Server", "🌐", "—")
        self._device_card = self._metric_card(status_row, 1, "Device", "💻", "—")
        self.server_label = self._server_card["value"]
        self.device_label = self._device_card["value"]
        self._server_badge = self._server_card["badge"]
        self._device_badge = self._device_card["badge"]

        self._home_stats = self._build_stats_row(left, 1)

        connect = self._card(left, "Connect to ApplyXAI", "🔗", "Your browser will open so you can sign in and approve this computer.")
        connect.master.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        seg = tk.Frame(connect, bg=BORDER)
        seg.grid(row=2, column=0, sticky=tk.W, pady=(12, 0))
        self.connect_local_btn = tk.Button(
            seg, text="  Connect — Local  ", relief=tk.FLAT, bg=BRAND, fg="#ffffff",
            activebackground=BRAND_HOVER, activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"), padx=14, pady=10, cursor="hand2",
            command=lambda: self._on_connect("local"),
        )
        self.connect_local_btn.pack(side=tk.LEFT)
        self.connect_live_btn = tk.Button(
            seg, text="  Connect — Live  ", relief=tk.FLAT, bg=SURFACE, fg=BRAND,
            activebackground=BRAND_SOFT, font=("Segoe UI", 10, "bold"), padx=14, pady=10, cursor="hand2",
            command=lambda: self._on_connect("live"),
        )
        self.connect_live_btn.pack(side=tk.LEFT)
        self.pair_button = self.connect_live_btn
        self._style_connect_buttons()

        hint = self._card(
            left,
            "Automation",
            "⚡",
            "Start a run from the ApplyXAI website (Automation page). This app will pick it up when the agent is running.",
        )
        hint.master.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(hint, text="Open Automation controls →", style="Secondary.TButton", command=lambda: self._set_nav("automation")).grid(
            row=2, column=0, sticky=tk.W, pady=(12, 0),
        )

        log_card = self._card(
            left, "Activity Log", "📄",
            "Real-time logs of the agent's activity will appear here.",
            expand=True,
        )
        log_card.master.grid(row=4, column=0, sticky="nsew")
        log_card.rowconfigure(2, weight=1)
        self._attach_log_panel(log_card)

        right = tk.Frame(parent, bg=PAGE)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 8), pady=8)
        right.columnconfigure(0, weight=1)

        qa = self._card(right, "Quick Actions", "⚡")
        qa.master.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        grid = tk.Frame(qa, bg=SURFACE)
        grid.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        self._quick_start = self._quick_tile(grid, 0, 0, "▶", "Start Agent", "Begin job search & apply", self._on_start, BRAND)
        self._quick_refresh = self._quick_tile(grid, 0, 1, "↻", "Refresh", "Reload connection", self._refresh_status, BRAND)
        self._quick_stop = self._quick_tile(grid, 1, 0, "■", "Stop Agent", "Halt current session", self._on_stop, DANGER)
        self._quick_disconnect = self._quick_tile(
            grid, 1, 1, "⎋", "Disconnect", "End session", self._on_unpair, DANGER,
        )

        self.status_label = self._device_badge
        self._automation_control_host = None

    def _build_automation_page(self, parent):
        body = tk.Frame(parent, bg=PAGE, padx=8, pady=8)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)

        self._auto_stats = self._build_stats_row(body, 0)

        control = self._card(body, "Automation controls", "⚙", "Start the agent here, then queue a run from the website.")
        control.master.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ctrl = tk.Frame(control, bg=SURFACE)
        ctrl.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.start_button = ttk.Button(ctrl, text="▶  Start Agent", style="Primary.TButton", command=self._on_start)
        self.start_button.pack(side=tk.LEFT, padx=(0, 8))
        self.stop_button = ttk.Button(
            ctrl, text="■  Stop", style="Danger.TButton", command=self._on_stop, state=tk.DISABLED,
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(ctrl, text="↻  Refresh stats", style="Secondary.TButton", command=self._refresh_stats).pack(
            side=tk.LEFT, padx=(0, 8),
        )
        ttk.Button(ctrl, text="⎋  Disconnect", style="Secondary.TButton", command=self._on_unpair).pack(side=tk.LEFT)

        self._run_detail = tk.Label(
            control, text="No active run.", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9),
            wraplength=900, justify=tk.LEFT,
        )
        self._run_detail.grid(row=3, column=0, sticky="w", pady=(12, 0))

    def _card(self, parent, title: str, icon: str = "", subtitle: str = "", *, expand: bool = False) -> tk.Frame:
        outer = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        if expand:
            outer.rowconfigure(0, weight=1)
        body = tk.Frame(outer, bg=SURFACE, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=expand)
        body.columnconfigure(0, weight=1)
        if expand:
            body.rowconfigure(2, weight=1)
        head = tk.Frame(body, bg=SURFACE)
        head.grid(row=0, column=0, sticky="ew")
        if icon:
            tk.Label(head, text=icon, bg=SURFACE, fg=BRAND, font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(head, text=title, bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        if subtitle:
            tk.Label(
                body, text=subtitle, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9),
                wraplength=520, justify=tk.LEFT,
            ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        outer._card_body = body  # noqa: SLF001 — tk parent/child wiring
        return body

    def _metric_card(self, parent, column: int, title: str, icon: str, value: str) -> dict:
        tile = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        tile.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 6 if column == 0 else 0))
        inner = tk.Frame(tile, bg=SURFACE, padx=16, pady=14)
        inner.pack(fill=tk.BOTH, expand=True)
        top = tk.Frame(inner, bg=SURFACE)
        top.pack(fill=tk.X)
        tk.Label(top, text=icon, bg=SURFACE, font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(top, text=title, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        val = tk.Label(inner, text=value, bg=SURFACE, fg=TEXT, font=("Segoe UI", 11, "bold"), anchor=tk.W, justify=tk.LEFT)
        val.pack(fill=tk.X, pady=(10, 0))
        badge = tk.Label(
            inner, text="Offline", bg="#f1f5f9", fg=MUTED, font=("Segoe UI", 8, "bold"), padx=8, pady=3,
        )
        badge.pack(anchor=tk.W, pady=(8, 0))
        return {"value": val, "badge": badge}

    def _quick_tile(self, parent, row, col, icon, title, subtitle, command, accent):
        tile = tk.Frame(
            parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, cursor="hand2",
        )
        tile.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        inner = tk.Frame(tile, bg=SURFACE, padx=12, pady=12)
        inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(inner, text=icon, bg=SURFACE, fg=accent, font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        tk.Label(inner, text=title, bg=SURFACE, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(6, 0))
        tk.Label(inner, text=subtitle, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8), wraplength=140, justify=tk.LEFT).pack(
            anchor=tk.W,
        )

        def activate(_e=None):
            command()

        for w in (tile, inner):
            w.bind("<Button-1>", activate)
        return tile

    def _place_linkedin_card(self, on_linkedin_view: bool) -> None:
        outer = getattr(self, "_linkedin_card_outer", None)
        if outer is None:
            return
        outer.grid_forget()
        if not on_linkedin_view:
            outer.grid_forget()
            return
        outer.grid(row=0, column=0, sticky="ew", in_=self._linkedin_nav_host)

    def _build_linkedin_card(self, parent):
        card = self._card(
            parent,
            "LinkedIn (Optional)",
            "in",
            "Add your LinkedIn credentials for better results.",
        )
        self._linkedin_card_outer = card.master
        card.master.grid(row=0, column=0, sticky="ew")

        email_row = tk.Frame(card, bg=SURFACE)
        email_row.grid(row=2, column=0, sticky="ew", pady=(12, 8))
        email_row.columnconfigure(1, weight=1)
        tk.Label(email_row, text="✉", bg=SURFACE, fg=MUTED).grid(row=0, column=0, padx=(0, 8))
        self.linkedin_email = ttk.Entry(email_row)
        self.linkedin_email.grid(row=0, column=1, sticky="ew")

        pw_row = tk.Frame(card, bg=SURFACE)
        pw_row.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        pw_row.columnconfigure(1, weight=1)
        tk.Label(pw_row, text="🔒", bg=SURFACE, fg=MUTED).grid(row=0, column=0, padx=(0, 8))
        self.linkedin_password = ttk.Entry(pw_row, show="•")
        self.linkedin_password.grid(row=0, column=1, sticky="ew")
        self._pw_visible = tk.BooleanVar(value=False)
        tk.Button(
            pw_row, text="👁", relief=tk.FLAT, bg=SURFACE, fg=MUTED, command=self._toggle_password,
        ).grid(row=0, column=2, padx=(6, 0))

        ttk.Button(
            card, text="🔒  Save Credentials", style="Primary.TButton", command=self._save_linkedin_credentials,
        ).grid(row=4, column=0, sticky="ew")

        notice = tk.Frame(card, bg=BRAND_SOFT, highlightbackground=BRAND_LIGHT, highlightthickness=1)
        notice.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        tk.Label(
            notice,
            text="🛡  Your credentials are secure. We never store your password on ApplyXAI servers.",
            bg=BRAND_SOFT, fg=TEXT_SOFT, font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, padx=10, pady=10,
        ).pack(anchor=tk.W)

    def _toggle_password(self):
        self._pw_visible.set(not self._pw_visible.get())
        self.linkedin_password.configure(show="" if self._pw_visible.get() else "•")

    def _attach_log_panel(self, card: tk.Frame, *, secondary: bool = False):
        wrap = tk.Frame(card, bg=LOG_BG, highlightbackground=BORDER, highlightthickness=1)
        wrap.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        log = scrolledtext.ScrolledText(
            wrap, height=10 if not secondary else 24, state=tk.DISABLED, wrap=tk.WORD, bg=LOG_BG, fg=TEXT,
            font=("Consolas", 10), relief=tk.FLAT, borderwidth=0, padx=10, pady=10,
        )
        log.grid(row=0, column=0, sticky="nsew")
        if not hasattr(self, "_log_widgets"):
            self._log_widgets = []
            self._log_empty_frames = []
            self.log_text = log
        self._log_widgets.append(log)
        empty = tk.Frame(wrap, bg=LOG_BG)
        empty.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        tk.Label(empty, text="📄", bg=LOG_BG, fg=BRAND, font=("Segoe UI", 28)).pack()
        tk.Label(
            empty, text="No activity yet", bg=LOG_BG, fg=TEXT, font=("Segoe UI", 11, "bold"),
        ).pack(pady=(8, 4))
        tk.Label(
            empty, text="Start the agent to see live logs here.", bg=LOG_BG, fg=MUTED, font=("Segoe UI", 9),
        ).pack()
        self._log_empty_frames.append(empty)

    def _build_footer(self, parent):
        foot = tk.Frame(parent, bg=PAGE)
        foot.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 16))
        foot.columnconfigure(0, weight=1)
        tk.Label(
            foot, text=f"ApplyXAI Agent v{AGENT_VERSION}", bg=PAGE, fg=MUTED, font=("Segoe UI", 9),
        ).grid(row=0, column=0, sticky=tk.W)
        tk.Label(
            foot, text="Smarter Applications • Better Opportunities", bg=PAGE, fg=MUTED, font=("Segoe UI", 9),
        ).grid(row=0, column=1, sticky=tk.E)

    def _style_connect_buttons(self):
        if self._connect_preset == "local":
            self.connect_local_btn.configure(bg=BRAND, fg="#ffffff")
            self.connect_live_btn.configure(bg=SURFACE, fg=BRAND)
        else:
            self.connect_live_btn.configure(bg=BRAND, fg="#ffffff")
            self.connect_local_btn.configure(bg=SURFACE, fg=BRAND)

    def _update_avatar(self, device_name: str):
        parts = (device_name or "AX").replace("_", " ").split()
        initials = "".join(p[0].upper() for p in parts[:2]) or "AX"
        self._avatar.configure(text=initials[:2])

    # ------------------------------------------------------------------ queue / status
    def _process_queue(self):
        try:
            while True:
                command = self.command_queue.get_nowait()
                if command[0] == "log":
                    self._append_log(command[1])
                elif command[0] == "status":
                    self._update_status_display(command[1], command[2], command[3])
                elif command[0] == "error":
                    messagebox.showerror("Error", command[1])
                elif command[0] == "info":
                    messagebox.showinfo("Info", command[1])
                elif command[0] == "running":
                    self._set_agent_running(command[1])
                elif command[0] == "refresh_connect_buttons":
                    from agent import config as agent_config
                    cfg = agent_config.load(Path(self.home)) if AGENT_MODULES_AVAILABLE else None
                    if cfg:
                        self._update_status_display(cfg.server, cfg.name, True)
                    else:
                        self.connect_local_btn.config(state=tk.NORMAL)
                        self.connect_live_btn.config(state=tk.NORMAL)
        except queue.Empty:
            pass
        self.root.after(100, self._process_queue)

    def _append_log(self, message):
        if not self._log_has_content:
            self._log_has_content = True
            for frame in getattr(self, "_log_empty_frames", []):
                frame.place_forget()
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        for log in getattr(self, "_log_widgets", [self.log_text]):
            log.config(state=tk.NORMAL)
            log.insert(tk.END, line)
            log.see(tk.END)
            log.config(state=tk.DISABLED)

    def _update_status_display(self, server, device, connected):
        if connected:
            self.server_label.config(text=server or "—", fg=TEXT)
            self.device_label.config(text=device or "—", fg=TEXT)
            self._server_badge.config(text="● Online", bg=SUCCESS_BG, fg=SUCCESS_FG)
            self._device_badge.config(text="● Connected", bg=SUCCESS_BG, fg=SUCCESS_FG)
            self._pill_connected.config(text="● Connected", bg=SUCCESS_BG, fg=SUCCESS_FG)
            self.connect_local_btn.config(state=tk.DISABLED)
            self.connect_live_btn.config(state=tk.DISABLED)
            self._update_avatar(device or "")
        else:
            self.server_label.config(text="Not connected", fg=MUTED)
            self.device_label.config(text="—", fg=MUTED)
            self._server_badge.config(text="Offline", bg="#f1f5f9", fg=MUTED)
            self._device_badge.config(text="Disconnected", bg="#fee2e2", fg=DANGER)
            self._pill_connected.config(text="● Disconnected", bg="#fee2e2", fg=DANGER)
            self.connect_local_btn.config(state=tk.NORMAL)
            self.connect_live_btn.config(state=tk.NORMAL)
            self._update_avatar("AX")

    def _set_agent_running(self, running):
        self.agent_running = running
        state_start = tk.DISABLED if running else tk.NORMAL
        state_stop = tk.NORMAL if running else tk.DISABLED
        self.start_button.config(state=state_start)
        self.stop_button.config(state=state_stop)
        if running:
            self._append_log("Agent started — waiting for jobs from ApplyXAI...")
            self._append_log("Start a run from the Automation page in your dashboard.")
        else:
            self._append_log("Agent stopped")

    def _log(self, message):
        self.command_queue.put(("log", message))

    def _on_connect(self, preset_name: str):
        self._connect_preset = preset_name
        self._style_connect_buttons()
        self.connect_local_btn.config(state=tk.DISABLED)
        self.connect_live_btn.config(state=tk.DISABLED)
        threading.Thread(target=self._do_connect, args=(preset_name,), daemon=True).start()

    def _do_connect(self, preset_name: str):
        try:
            if AGENT_MODULES_AVAILABLE:
                from agent.config import preset
                from agent.connect_flow import connect_with_browser

                p = preset(preset_name)
                cfg = connect_with_browser(
                    api_base=p["api"],
                    web_base=p["web"],
                    home=Path(self.home),
                    log=self._log,
                )
                self.command_queue.put(("status", cfg.server, cfg.name, True))
                self.command_queue.put(("info", f'Connected as "{cfg.name}"'))
            else:
                exe = self._cli_exe()
                cmd = [str(exe), "connect", "--preset", preset_name] if exe else [
                    sys.executable, "-m", "agent", "connect", "--preset", preset_name,
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, creationflags=background_creationflags(),
                )
                if result.returncode == 0:
                    self._refresh_status()
                    self.command_queue.put(("info", "Connected successfully"))
                else:
                    err = (result.stderr or result.stdout or "Connection failed").strip()
                    self.command_queue.put(("error", err))
        except Exception as e:
            self.command_queue.put(("error", f"Connection failed: {str(e)}"))
        finally:
            self.command_queue.put(("refresh_connect_buttons",))

    def _cli_exe(self) -> Path | None:
        if not getattr(sys, "frozen", False):
            return None
        gui_dir = Path(sys.executable).parent
        for candidate in (gui_dir / "ApplyXAI-Agent.exe", gui_dir / "_internal" / "ApplyXAI-Agent.exe"):
            if candidate.is_file():
                return candidate
        return None

    def _on_start(self):
        if self.agent_running:
            return
        threading.Thread(target=self._run_agent, daemon=True).start()

    def _run_agent(self):
        self._log("Starting agent...")
        try:
            inline = AGENT_MODULES_AVAILABLE or getattr(sys, "frozen", False)
            if inline:
                from agent import config, AGENT_VERSION
                from agent.client import ApiClient
                from agent.supervisor import Supervisor

                cfg = config.load(Path(self.home))
                if cfg is None:
                    self.command_queue.put(("error", "Not paired. Please connect first."))
                    return

                self.command_queue.put(("running", True))
                self._log(f"Connected to {cfg.server}")
                self._log("Polling for jobs... (Start a run from the Automation page)")
                supervisor = Supervisor(ApiClient(cfg.server, cfg.token), Path(self.home), cfg.user_id)
                supervisor.run_forever()
            else:
                if getattr(sys, "frozen", False):
                    cli = self._cli_exe()
                    cmd = [str(cli), "run"] if cli else [sys.executable, "-m", "agent", "run"]
                else:
                    cmd = ["python", "-m", "agent", "run"]

                self.command_queue.put(("running", True))
                popen_kw = {
                    "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
                    "text": True, "bufsize": 1, "creationflags": background_creationflags(),
                }
                self.agent_process = subprocess.Popen(cmd, **popen_kw)

                for line in self.agent_process.stdout:
                    self._log(line.strip())

                self.agent_process.wait()
        except Exception as e:
            self._log(f"Agent error: {str(e)}")
        finally:
            self.command_queue.put(("running", False))

    def _on_stop(self):
        if not self.agent_running:
            return
        self._log("Stopping agent...")
        if self.agent_process:
            self.agent_process.terminate()
            try:
                self.agent_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.agent_process.kill()
            self.agent_process = None
        self.command_queue.put(("running", False))

    def _on_unpair(self):
        if not messagebox.askyesno("Confirm", "Disconnect this computer from ApplyXAI?"):
            return
        try:
            if AGENT_MODULES_AVAILABLE:
                from agent import config
                config.forget(Path(self.home))
            else:
                exe_path = sys.executable if getattr(sys, "frozen", False) else "python"
                cmd = [exe_path, "-m", "agent", "unpair"]
                subprocess.run(cmd, capture_output=True, text=True, creationflags=background_creationflags())
            self._refresh_status()
            self._log("Disconnected from ApplyXAI")
        except Exception as e:
            self.command_queue.put(("error", f"Disconnect failed: {str(e)}"))

    def _refresh_status(self):
        threading.Thread(target=self._do_refresh_status, daemon=True).start()

    def _do_refresh_status(self):
        try:
            if AGENT_MODULES_AVAILABLE:
                from agent import config
                cfg = config.load(Path(self.home))
                if cfg:
                    self.command_queue.put(("status", cfg.server, cfg.name, True))
                else:
                    self.command_queue.put(("status", "", "", False))
            else:
                exe_path = sys.executable if getattr(sys, "frozen", False) else "python"
                cmd = [exe_path, "-m", "agent", "status"]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, creationflags=background_creationflags(),
                )
                if result.returncode == 0 and "Connected to" in result.stdout:
                    self.command_queue.put(("status", "Connected", "Device", True))
                else:
                    self.command_queue.put(("status", "", "", False))
        except Exception as e:
            self._log(f"Status check failed: {str(e)}")

    def _save_linkedin_credentials(self):
        email = self.linkedin_email.get().strip()
        password = self.linkedin_password.get().strip()
        if not email or not password:
            messagebox.showerror("Error", "Please enter both LinkedIn email and password")
            return
        try:
            agent_home = Path(self.home)
            user_config_path = agent_home / "user_config.json"
            user_config = {}
            if user_config_path.exists():
                with open(user_config_path, "r") as f:
                    user_config = json.load(f)
            if "secrets" not in user_config:
                user_config["secrets"] = {}
            user_config["secrets"]["username"] = email
            user_config["secrets"]["password"] = password
            agent_home.mkdir(parents=True, exist_ok=True)
            with open(user_config_path, "w") as f:
                json.dump(user_config, f, indent=2)
            messagebox.showinfo("Success", "LinkedIn credentials saved on this PC.")
            self._log("LinkedIn credentials saved to user_config.json")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save credentials: {e}")
            self._log(f"Failed to save credentials: {e}")

    def _start_local_wake_server(self) -> None:
        try:
            from agent.local_wake import start_wake_server

            start_wake_server(lambda: self.root.after(0, self._on_wake_from_browser))
        except Exception as exc:
            self._log(f"Local wake listener unavailable: {exc}")

    def _on_wake_from_browser(self) -> None:
        if self.agent_running:
            self._log("Browser requested agent start — already running.")
            return
        self._log("Run queued from website — starting agent…")
        self._on_start()

    def _schedule_stats_refresh(self) -> None:
        self._refresh_stats()
        self.root.after(30_000, self._schedule_stats_refresh)

    def _refresh_stats(self) -> None:
        threading.Thread(target=self._do_refresh_stats, daemon=True).start()

    def _apply_stats_cards(self, cards: dict, stats: dict, overview: dict | None) -> None:
        usage = stats.get("usage") or {}
        apps = usage.get("applications") or {}
        applied = apps.get("used", stats.get("total_applied", "—"))
        cards["applied"]["value"].config(text=str(applied))
        cards["today"]["value"].config(text=str(stats.get("applied_today", "—")))
        rate = stats.get("success_rate")
        cards["success"]["value"].config(
            text="—" if rate is None else f"{int(round(float(rate) * 100))}%",
        )
        active = (stats.get("automation") or {}).get("active")
        if active:
            cards["run"]["value"].config(
                text=f"{active.get('status', 'active')} · {active.get('successful_count', 0)} ok",
            )
            cards["run"]["badge"].config(text="● Running", bg=SUCCESS_BG, fg=SUCCESS_FG)
        else:
            cards["run"]["value"].config(text="None")
            cards["run"]["badge"].config(text="Idle", bg="#f1f5f9", fg=MUTED)
        if overview and getattr(self, "_run_detail", None):
            run = overview.get("active")
            if run:
                detail = (
                    f"Run {run.get('status')} · {run.get('successful_count', 0)} applied, "
                    f"{run.get('failed_count', 0)} failed, {run.get('skipped_count', 0)} skipped"
                )
                if run.get("current_job"):
                    detail += f" · Now: {run['current_job']}"
                self._run_detail.config(text=detail, fg=TEXT)
            else:
                self._run_detail.config(text="No active run. Start the agent, then queue a run on the website.", fg=MUTED)

    def _do_refresh_stats(self) -> None:
        if not AGENT_MODULES_AVAILABLE:
            return
        try:
            from agent import config
            from agent.client import ApiClient

            cfg = config.load(Path(self.home))
            if cfg is None:
                return
            client = ApiClient(cfg.server, cfg.token)
            stats = client.dashboard_stats()
            overview = client.automation_overview()
            self.root.after(0, lambda: self._apply_stats_cards(self._home_stats, stats, overview))
            self.root.after(0, lambda: self._apply_stats_cards(self._auto_stats, stats, overview))
        except Exception as exc:
            self._log(f"Stats refresh failed: {exc}")

    def _load_settings_display(self) -> None:
        lines: list[str] = [f"Data folder: {self.home}", ""]
        home = Path(self.home)
        for name in ("user_config.json", "config.json", "paired.json"):
            path = home / name
            lines.append(f"--- {name} ---")
            if not path.is_file():
                lines.append("(not created yet)")
                lines.append("")
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if name == "user_config.json" and isinstance(raw.get("secrets"), dict):
                    raw = {**raw, "secrets": {**raw["secrets"], "password": "(saved locally — hidden)"}}
                lines.append(json.dumps(raw, indent=2))
            except Exception as exc:
                lines.append(f"(could not read: {exc})")
            lines.append("")
        if AGENT_MODULES_AVAILABLE:
            try:
                from agent import config as agent_config

                cfg = agent_config.load(home)
                if cfg:
                    lines.append("--- connection ---")
                    lines.append(json.dumps({"server": cfg.server, "name": cfg.name, "user_id": cfg.user_id}, indent=2))
            except Exception:
                pass
        text = "\n".join(lines)
        self.settings_text.config(state=tk.NORMAL)
        self.settings_text.delete("1.0", tk.END)
        self.settings_text.insert(tk.END, text)
        self.settings_text.config(state=tk.DISABLED)

    def _load_linkedin_from_disk(self) -> None:
        path = Path(self.home) / "user_config.json"
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            secrets = data.get("secrets") or {}
            email = secrets.get("username") or ""
            if email and hasattr(self, "linkedin_email"):
                self.linkedin_email.delete(0, tk.END)
                self.linkedin_email.insert(0, email)
        except Exception:
            pass


def _enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    AgentGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
