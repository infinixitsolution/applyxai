"""
Simple Windows GUI for ApplyXAI Agent.

Uses tkinter (built into Python) to provide a user-friendly interface for:
- Pairing with ApplyXAI server
- Viewing connection status
- Starting/stopping the agent
- Viewing logs
- Settings

The GUI calls the existing agent CLI commands rather than duplicating logic.
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
    BRAND_LIGHT,
    DANGER,
    MUTED,
    SUCCESS,
    SURFACE,
    setup as setup_theme,
)


class _ButtonRow(tk.Frame):
    """Lays buttons in a row and wraps them when the window gets narrow."""

    def __init__(self, parent, bg=SURFACE):
        super().__init__(parent, bg=bg, height=36)
        self._items: list[tk.Widget] = []
        self.bind("<Configure>", self._reflow)

    def add(self, widget: tk.Widget) -> tk.Widget:
        self._items.append(widget)
        widget.place(x=0, y=0)
        return widget

    def _reflow(self, event):
        width = event.width
        if width < 40:
            return
        x = y = 0
        row_h = 0
        gap = 8
        for widget in self._items:
            widget.update_idletasks()
            ww = max(widget.winfo_reqwidth(), 1)
            hh = max(widget.winfo_reqheight(), 1)
            if x and x + ww > width:
                x = 0
                y += row_h + gap
                row_h = 0
            widget.place(x=x, y=y)
            x += ww + gap
            row_h = max(row_h, hh)
        self.configure(height=max(y + row_h, 36))

# Try to import agent modules (works when running from source)
try:
    from agent import config
    from agent.client import ApiClient, ApiError, NetworkError
    from agent import AGENT_VERSION
    AGENT_MODULES_AVAILABLE = True
except ImportError:
    # When packaged, we'll use subprocess to call the EXE
    AGENT_MODULES_AVAILABLE = False
    AGENT_VERSION = "1.1.2"


class AgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"ApplyXAI Agent v{AGENT_VERSION}")
        self.root.minsize(460, 560)
        self.root.resizable(True, True)
        self._fit_window()
        setup_theme(self.root)
        self._mascot_img = None
        self._apply_window_icon()

        # Agent process
        self.agent_process = None
        self.agent_running = False

        # Command queue for thread-safe UI updates
        self.command_queue = queue.Queue()

        # Configuration
        self.home = self._get_home()

        # Build UI
        self._build_ui()

        # Start queue processor
        self._process_queue()

        # Load initial status
        self._refresh_status()
        
        # Load existing LinkedIn credentials
        self._load_linkedin_credentials()

    def _get_home(self):
        """Get the agent home directory."""
        if AGENT_MODULES_AVAILABLE:
            return str(config.default_home())
        else:
            # Fallback for packaged builds
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

    def _load_mascot_photo(self, max_side: int = 96) -> tk.PhotoImage | None:
        path = branding_paths.mascot_png()
        if not path.is_file():
            return None
        try:
            img = tk.PhotoImage(file=str(path))
            w, h = img.width(), img.height()
            scale = max(max(w, h) // max_side, 1)
            if scale > 1:
                img = img.subsample(scale, scale)
            self._mascot_img = img
            return img
        except tk.TclError:
            return None

    def _fit_window(self) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(980, max(520, screen_w - 80))
        height = min(860, max(620, screen_h - 120))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 6)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _surface_card(self, parent, row: int, *, padding=(16, 14), expand: bool = False) -> ttk.Frame:
        sticky = (tk.W, tk.E, tk.N, tk.S) if expand else (tk.W, tk.E)
        outer = ttk.Frame(parent)
        outer.grid(row=row, column=0, sticky=sticky, pady=(0, 12))
        outer.columnconfigure(0, weight=1)
        if expand:
            outer.rowconfigure(0, weight=1)
        inner = tk.Frame(outer, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        inner.grid(row=0, column=0, sticky=sticky)
        inner.columnconfigure(0, weight=1)
        if expand:
            inner.rowconfigure(0, weight=1)
        body = ttk.Frame(inner, style="Card.TFrame", padding=padding)
        body.grid(row=0, column=0, sticky=sticky)
        body.columnconfigure(0, weight=1)
        return body

    def _muted(self, parent, text: str) -> ttk.Label:
        label = ttk.Label(parent, text=text, style="CardMuted.TLabel", wraplength=480, justify=tk.LEFT)
        self._wrap_labels.append(label)
        return label

    def _build_ui(self):
        """Build a layout that scrolls on short windows and reflows on narrow ones."""
        self._wrap_labels: list[ttk.Label] = []
        self._status_tiles: list[tk.Frame] = []
        self._status_value_labels: dict[str, tk.Label] = {}
        self._status_cols = 3

        shell = ttk.Frame(self.root, padding=(16, 12))
        shell.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        accent = tk.Frame(shell, bg=BRAND, height=4)
        accent.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 12))

        self._canvas = tk.Canvas(shell, bg=BG, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(shell, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))

        content = ttk.Frame(self._canvas)
        self._content = content
        content.columnconfigure(0, weight=1)
        content.rowconfigure(4, weight=1)
        self._canvas_window = self._canvas.create_window((0, 0), window=content, anchor=tk.NW)
        content.bind("<Configure>", self._on_content_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Enter>", lambda _e: self._canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self._canvas.bind("<Leave>", lambda _e: self._canvas.unbind_all("<MouseWheel>"))

        hero = self._surface_card(content, 0, padding=(14, 16))
        hero_inner = ttk.Frame(hero, style="Card.TFrame")
        hero_inner.grid(row=0, column=0, sticky=(tk.W, tk.E))
        hero_inner.columnconfigure(1, weight=1)
        mascot = self._load_mascot_photo(max_side=72)
        if mascot:
            tk.Label(hero_inner, image=mascot, bg=SURFACE, borderwidth=0).grid(
                row=0, column=0, rowspan=2, padx=(0, 14), sticky=tk.N,
            )
        title_col = ttk.Frame(hero_inner, style="Card.TFrame")
        title_col.grid(row=0, column=1, sticky=(tk.W, tk.E))
        title_col.columnconfigure(0, weight=1)
        heading = ttk.Frame(title_col, style="Card.TFrame")
        heading.grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Label(heading, text="ApplyXAI Agent", style="Title.TLabel").pack(side=tk.LEFT)
        tk.Label(
            heading, text=f"  v{AGENT_VERSION}  ", bg=BRAND_LIGHT, fg=BRAND,
            font=("Segoe UI", 9, "bold"), padx=8, pady=2,
        ).pack(side=tk.LEFT, padx=(10, 0))
        self._muted(
            title_col,
            "Runs LinkedIn Easy Apply on this PC. Passwords stay on this computer.",
        ).grid(row=1, column=0, sticky=tk.W, pady=(6, 0))

        status = self._surface_card(content, 1)
        self._status_host = status
        ttk.Label(status, text="Connection", style="Card.TLabel", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10),
        )
        self._status_tile("Server", "server")
        self._status_tile("Device", "device")
        self._status_tile("Status", "status")

        connect = self._surface_card(content, 2)
        ttk.Label(connect, text="Connect to ApplyXAI", style="Card.TLabel", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky=tk.W,
        )
        self._muted(
            connect,
            "Choose Local for this PC or Live for applyxai.com. Your browser opens so you can sign in and approve this computer.",
        ).grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(6, 12))
        connect_row = _ButtonRow(connect, bg=SURFACE)
        connect_row.grid(row=2, column=0, sticky=(tk.W, tk.E))
        self.connect_local_btn = connect_row.add(ttk.Button(
            connect_row, text="Connect — Local", style="Secondary.TButton", command=lambda: self._on_connect("local"),
        ))
        self.connect_live_btn = connect_row.add(ttk.Button(
            connect_row, text="Connect — Live", style="Primary.TButton", command=lambda: self._on_connect("live"),
        ))
        self.pair_button = self.connect_live_btn

        control = self._surface_card(content, 3)
        ttk.Label(control, text="Automation", style="Card.TLabel", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 10),
        )
        ctrl_row = _ButtonRow(control, bg=SURFACE)
        ctrl_row.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.start_button = ctrl_row.add(ttk.Button(
            ctrl_row, text="Start agent", style="Primary.TButton", command=self._on_start,
        ))
        self.stop_button = ctrl_row.add(ttk.Button(
            ctrl_row, text="Stop", style="Danger.TButton", command=self._on_stop, state=tk.DISABLED,
        ))
        ctrl_row.add(ttk.Button(ctrl_row, text="Refresh", style="Secondary.TButton", command=self._refresh_status))
        ctrl_row.add(ttk.Button(ctrl_row, text="Disconnect", style="Secondary.TButton", command=self._on_unpair))

        logs_outer = self._surface_card(content, 4, padding=(12, 12), expand=True)
        logs_outer.rowconfigure(1, weight=1)
        ttk.Label(logs_outer, text="Activity log", style="Card.TLabel", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 8),
        )
        log_wrap = tk.Frame(logs_outer, bg="#f8fafc", highlightbackground=BORDER, highlightthickness=1)
        log_wrap.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_wrap.columnconfigure(0, weight=1)
        log_wrap.rowconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(
            log_wrap, height=8, state=tk.DISABLED, wrap=tk.WORD, bg="#f8fafc", fg="#0f172a",
            font=("Consolas", 10), relief=tk.FLAT, borderwidth=0, padx=8, pady=8,
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        linkedin = self._surface_card(content, 5)
        linkedin.columnconfigure(1, weight=1)
        ttk.Label(linkedin, text="LinkedIn (optional)", style="Card.TLabel", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 8),
        )
        ttk.Label(linkedin, text="Email", style="CardMuted.TLabel").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.linkedin_email = ttk.Entry(linkedin)
        self.linkedin_email.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=4, padx=(12, 0))
        ttk.Label(linkedin, text="Password", style="CardMuted.TLabel").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.linkedin_password = ttk.Entry(linkedin, show="•")
        self.linkedin_password.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=4, padx=(12, 0))
        ttk.Button(
            linkedin, text="Save on this PC only", style="Secondary.TButton", command=self._save_linkedin_credentials,
        ).grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)
        self._muted(
            linkedin,
            "Saved in user_config.json on this machine only. Leave blank to sign in yourself in Chrome.",
        ).grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky=(tk.W, tk.E))

        foot = ttk.Frame(content)
        foot.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=(4, 8))
        foot.columnconfigure(0, weight=1)
        hint = ttk.Label(
            foot,
            text="1) Connect    2) Start agent    3) Start a run on the Automation page",
            style="Muted.TLabel",
            wraplength=420,
            justify=tk.LEFT,
        )
        self._wrap_labels.append(hint)
        hint.grid(row=0, column=0, sticky=tk.W)
        ttk.Button(foot, text="Open data folder", style="Secondary.TButton", command=self._open_logs_folder).grid(
            row=0, column=1, sticky=tk.E, padx=(12, 0),
        )

        self.server_label = self._status_value_labels["server"]
        self.device_label = self._status_value_labels["device"]
        self.status_label = self._status_value_labels["status"]

    def _on_content_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        width = max(event.width, 1)
        self._canvas.itemconfigure(self._canvas_window, width=width)
        self._apply_responsive(width)
        needed = self._content.winfo_reqheight()
        self._canvas.itemconfigure(self._canvas_window, height=max(needed, event.height))
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _apply_responsive(self, width: int) -> None:
        wrap = max(220, width - 56)
        for label in self._wrap_labels:
            try:
                label.configure(wraplength=wrap)
            except tk.TclError:
                pass
        cols = 1 if width < 720 else 3
        tile_wrap = max(140, (width // cols) - 48)
        for val in self._status_value_labels.values():
            val.configure(wraplength=tile_wrap)
        if cols != self._status_cols:
            self._status_cols = cols
            self._place_status_tiles()

    def _place_status_tiles(self) -> None:
        cols = self._status_cols
        for index, tile in enumerate(self._status_tiles):
            row, col = (index, 0) if cols == 1 else (0, index)
            tile.grid_configure(
                row=row + 1,
                column=col,
                columnspan=1,
                sticky=(tk.W, tk.E, tk.N, tk.S),
                padx=(0 if col == 0 else 8, 0),
                pady=(8 if cols == 1 and index else 0, 0),
            )
        for col in range(3):
            self._status_host.columnconfigure(col, weight=1 if cols == 3 or col == 0 else 0)

    def _status_tile(self, title: str, key: str) -> None:
        tile = tk.Frame(self._status_host, bg=BRAND_LIGHT, highlightbackground=BORDER, highlightthickness=1)
        self._status_tiles.append(tile)
        tk.Label(tile, text=title.upper(), bg=BRAND_LIGHT, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(
            anchor=tk.W, padx=12, pady=(10, 0),
        )
        val = tk.Label(
            tile, text="—", bg=BRAND_LIGHT, fg=MUTED, font=("Segoe UI", 11),
            wraplength=180, justify=tk.LEFT, anchor=tk.W,
        )
        val.pack(anchor=tk.W, fill=tk.X, padx=12, pady=(2, 12))
        self._status_value_labels[key] = val
        self._place_status_tiles()

    def _process_queue(self):
        """Process commands from the queue to update UI safely."""
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
        """Append a message to the log window."""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _update_status_display(self, server, device, connected):
        """Update the status display."""
        if connected:
            self.server_label.config(text=server or "—", fg="#0f172a")
            self.device_label.config(text=device or "—", fg="#0f172a")
            self.status_label.config(text="Connected", fg=SUCCESS)
            self.connect_local_btn.config(state=tk.DISABLED)
            self.connect_live_btn.config(state=tk.DISABLED)
        else:
            self.server_label.config(text="Not connected", fg=MUTED)
            self.device_label.config(text="—", fg=MUTED)
            self.status_label.config(text="Disconnected", fg=DANGER)
            self.connect_local_btn.config(state=tk.NORMAL)
            self.connect_live_btn.config(state=tk.NORMAL)

    def _set_agent_running(self, running):
        """Set the agent running state."""
        self.agent_running = running
        if running:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self._append_log("Agent started - waiting for jobs from ApplyXAI...")
            self._append_log("Start a job from the Automation page to begin automation")
        else:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self._append_log("Agent stopped")

    def _log(self, message):
        """Thread-safe log message."""
        self.command_queue.put(("log", message))

    def _on_connect(self, preset_name: str):
        """One-click connect using a built-in server preset."""
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
                self.command_queue.put(("info", f"Connected as \"{cfg.name}\""))
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
        """Handle the start button click."""
        if self.agent_running:
            return

        # Run agent in a thread
        threading.Thread(target=self._run_agent, daemon=True).start()

    def _run_agent(self):
        """Run the agent."""
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
                self._log("Polling for jobs... (Start a job from the Automation page)")
                supervisor = Supervisor(ApiClient(cfg.server, cfg.token), Path(self.home), cfg.user_id)
                supervisor.run_forever()
            else:
                if getattr(sys, "frozen", False):
                    cli = self._cli_exe()
                    cmd = [str(cli), "run"] if cli else [sys.executable, "-m", "agent", "run"]
                else:
                    cmd = ["python", "-m", "agent", "run"]

                self.command_queue.put(("running", True))
                popen_kw = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
                            "text": True, "bufsize": 1, "creationflags": background_creationflags()}
                self.agent_process = subprocess.Popen(cmd, **popen_kw)

                for line in self.agent_process.stdout:
                    self._log(line.strip())

                self.agent_process.wait()
        except Exception as e:
            self._log(f"Agent error: {str(e)}")
        finally:
            self.command_queue.put(("running", False))

    def _on_stop(self):
        """Handle the stop button click."""
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
        """Handle the unpair button click."""
        if not messagebox.askyesno("Confirm", "Disconnect this computer from ApplyXAI?"):
            return

        try:
            if AGENT_MODULES_AVAILABLE:
                from agent import config
                config.forget(Path(self.home))
            else:
                exe_path = sys.executable if getattr(sys, 'frozen', False) else "python"
                cmd = [exe_path, "-m", "agent", "unpair"]
                subprocess.run(cmd, capture_output=True, text=True, creationflags=background_creationflags())

            self._refresh_status()
            self._log("Disconnected from ApplyXAI")
        except Exception as e:
            self.command_queue.put(("error", f"Disconnect failed: {str(e)}"))

    def _refresh_status(self):
        """Refresh the connection status."""
        threading.Thread(target=self._do_refresh_status, daemon=True).start()

    def _do_refresh_status(self):
        """Perform the status refresh."""
        try:
            if AGENT_MODULES_AVAILABLE:
                from agent import config
                cfg = config.load(Path(self.home))
                if cfg:
                    self.command_queue.put(("status", cfg.server, cfg.name, True))
                else:
                    self.command_queue.put(("status", "", "", False))
            else:
                exe_path = sys.executable if getattr(sys, 'frozen', False) else "python"
                cmd = [exe_path, "-m", "agent", "status"]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, creationflags=background_creationflags(),
                )
                if result.returncode == 0:
                    # Parse output - simple check for "Connected to"
                    if "Connected to" in result.stdout:
                        self.command_queue.put(("status", "Connected", "Device", True))
                    else:
                        self.command_queue.put(("status", "", "", False))
        except Exception as e:
            self._log(f"Status check failed: {str(e)}")

    def _load_linkedin_credentials(self):
        """Load existing LinkedIn credentials from user_config.json."""
        try:
            agent_home = Path(self.home)
            user_config_path = agent_home / "user_config.json"
            
            if user_config_path.exists():
                with open(user_config_path, 'r') as f:
                    user_config = json.load(f)
                
                secrets = user_config.get("secrets", {})
                username = secrets.get("username", "")
                password = secrets.get("password", "")
                
                self.linkedin_email.delete(0, tk.END)
                self.linkedin_email.insert(0, username)
                self.linkedin_password.delete(0, tk.END)
                self.linkedin_password.insert(0, password)
        except Exception as e:
            # Silently fail if config doesn't exist or can't be read
            pass

    def _save_linkedin_credentials(self):
        """Save LinkedIn credentials to the secrets file."""
        email = self.linkedin_email.get().strip()
        password = self.linkedin_password.get().strip()
        
        if not email or not password:
            messagebox.showerror("Error", "Please enter both LinkedIn email and password")
            return
        
        try:
            # Save to user_config.json in the agent home directory
            # This is where the automation will look for it
            agent_home = Path(self.home)
            user_config_path = agent_home / "user_config.json"
            user_config = {}
            
            if user_config_path.exists():
                with open(user_config_path, 'r') as f:
                    user_config = json.load(f)
            
            # Add LinkedIn credentials to the "secrets" section
            if "secrets" not in user_config:
                user_config["secrets"] = {}
            user_config["secrets"]["username"] = email
            user_config["secrets"]["password"] = password
            
            # Ensure directory exists
            agent_home.mkdir(parents=True, exist_ok=True)
            
            with open(user_config_path, 'w') as f:
                json.dump(user_config, f, indent=2)
            
            messagebox.showinfo("Success", "LinkedIn credentials saved successfully!")
            self._log("LinkedIn credentials saved to user_config.json")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save credentials: {e}")
            self._log(f"Failed to save credentials: {e}")

    def _open_logs_folder(self):
        """Open the logs folder in the file explorer."""
        import subprocess
        path = Path(self.home)
        if path.exists():
            subprocess.Popen(["explorer", str(path)])
        else:
            messagebox.showinfo("Info", f"Logs folder does not exist yet: {path}")


def main():
    """Main entry point for the GUI."""
    root = tk.Tk()
    app = AgentGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
