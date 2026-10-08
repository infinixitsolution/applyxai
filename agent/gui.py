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
import subprocess
import threading
import queue
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from pathlib import Path
from datetime import datetime

# Try to import agent modules (works when running from source)
try:
    from agent import config
    from agent.client import ApiClient, ApiError, NetworkError
    from agent import AGENT_VERSION
    AGENT_MODULES_AVAILABLE = True
except ImportError:
    # When packaged, we'll use subprocess to call the EXE
    AGENT_MODULES_AVAILABLE = False
    AGENT_VERSION = "1.0.0"


class AgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"ApplyXAI Agent v{AGENT_VERSION}")
        self.root.geometry("600x700")
        self.root.resizable(True, True)

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

    def _build_ui(self):
        """Build the GUI layout."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Label(header_frame, text="ApplyXAI Agent", font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
        ttk.Label(header_frame, text=f"v{AGENT_VERSION}", font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(10, 0))

        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="Connection Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        status_frame.columnconfigure(1, weight=1)

        ttk.Label(status_frame, text="Server:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.server_label = ttk.Label(status_frame, text="Not connected", foreground="gray")
        self.server_label.grid(row=0, column=1, sticky=tk.W, pady=2, padx=(10, 0))

        ttk.Label(status_frame, text="Device:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.device_label = ttk.Label(status_frame, text="-", foreground="gray")
        self.device_label.grid(row=1, column=1, sticky=tk.W, pady=2, padx=(10, 0))

        ttk.Label(status_frame, text="Status:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.status_label.grid(row=2, column=1, sticky=tk.W, pady=2, padx=(10, 0))

        # Pairing section
        pair_frame = ttk.LabelFrame(main_frame, text="Connect Computer", padding="10")
        pair_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        pair_frame.columnconfigure(1, weight=1)

        ttk.Label(pair_frame, text="Server URL:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.server_entry = ttk.Entry(pair_frame)
        self.server_entry.insert(0, "https://app.applyxai.com")
        self.server_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=(10, 0))

        ttk.Label(pair_frame, text="Pairing Code:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.code_entry = ttk.Entry(pair_frame)
        self.code_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=(10, 0))

        self.pair_button = ttk.Button(pair_frame, text="Connect", command=self._on_pair)
        self.pair_button.grid(row=2, column=0, columnspan=2, pady=(10, 0))

        # Agent control section
        control_frame = ttk.LabelFrame(main_frame, text="Agent Control", padding="10")
        control_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        self.start_button = ttk.Button(control_frame, text="Start Agent", command=self._on_start)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_button = ttk.Button(control_frame, text="Stop Agent", command=self._on_stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(control_frame, text="Refresh Status", command=self._refresh_status).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(control_frame, text="Disconnect", command=self._on_unpair).pack(side=tk.LEFT)

        # Logs section
        log_frame = ttk.LabelFrame(main_frame, text="Agent Logs", padding="10")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Help info
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        info_text = "Workflow: 1) Connect this computer, 2) Start Agent, 3) Start job from web. ⚠️ LinkedIn login is manual - sign in when Chrome opens."
        info_label = ttk.Label(info_frame, text=info_text, foreground="gray", wraplength=550)
        info_label.pack()
        
        # LinkedIn login info
        linkedin_frame = ttk.LabelFrame(main_frame, text="LinkedIn Credentials", padding="10")
        linkedin_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        linkedin_frame.columnconfigure(1, weight=1)
        
        ttk.Label(linkedin_frame, text="LinkedIn Email:", foreground="gray").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.linkedin_email = ttk.Entry(linkedin_frame)
        self.linkedin_email.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=(10, 0))
        
        ttk.Label(linkedin_frame, text="LinkedIn Password:", foreground="gray").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.linkedin_password = ttk.Entry(linkedin_frame, show="*")
        self.linkedin_password.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=(10, 0))
        
        ttk.Button(linkedin_frame, text="Save Credentials", command=self._save_linkedin_credentials).grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        email_info = ttk.Label(linkedin_frame, text="The email address you sign in to LinkedIn with. Optional - if left blank the tool tries the browser's saved login, and asks you to log in by hand if that fails.",
                               foreground="gray", wraplength=550, justify=tk.LEFT)
        email_info.grid(row=3, column=0, columnspan=2, pady=(5, 0), sticky=tk.W)
        
        password_info = ttk.Label(linkedin_frame, text="Your LinkedIn password. Stored only on this computer in user_config.json (never uploaded anywhere). Optional - leave blank to log in manually.",
                               foreground="gray", wraplength=550, justify=tk.LEFT)
        password_info.grid(row=4, column=0, columnspan=2, pady=(5, 0), sticky=tk.W)

        # Settings button
        ttk.Button(main_frame, text="Open Logs Folder", command=self._open_logs_folder).grid(
            row=7, column=0, columnspan=2, pady=(0, 5))

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
            self.server_label.config(text=server, foreground="black")
            self.device_label.config(text=device, foreground="black")
            self.status_label.config(text="Connected", foreground="green")
            self.pair_button.config(state=tk.DISABLED)
        else:
            self.server_label.config(text="Not connected", foreground="gray")
            self.device_label.config(text="-", foreground="gray")
            self.status_label.config(text="Disconnected", foreground="red")
            self.pair_button.config(state=tk.NORMAL)

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

    def _on_pair(self):
        """Handle the pair button click."""
        server = self.server_entry.get().strip()
        code = self.code_entry.get().strip()

        if not server:
            messagebox.showerror("Error", "Please enter a server URL")
            return

        if not code:
            messagebox.showerror("Error", "Please enter a pairing code")
            return

        # Run pairing in a thread to avoid blocking UI
        threading.Thread(target=self._do_pair, args=(server, code), daemon=True).start()

    def _do_pair(self, server, code):
        """Perform the pairing operation."""
        self._log(f"Connecting to {server}...")

        try:
            if AGENT_MODULES_AVAILABLE:
                # Use direct API calls when running from source
                from agent.config import check_server_url, default_device_name, save, AgentConfig
                from agent.client import ApiClient

                server_url = check_server_url(server)
                data = ApiClient(server_url).pair(code, default_device_name())
                home = Path(self.home)
                save(home, AgentConfig(
                    server=server_url,
                    token=data["token"],
                    device_id=data["device_id"],
                    user_id=data["user_id"],
                    name=data.get("name", "")
                ))
                self.command_queue.put(("status", server_url, data.get("name", ""), True))
                self.command_queue.put(("info", f"Connected as \"{data.get('name', '')}\""))
            else:
                # Use subprocess when packaged - call the CLI EXE
                if getattr(sys, 'frozen', False):
                    # When GUI is packaged, look for the CLI EXE in the same directory
                    gui_dir = Path(sys.executable).parent
                    cli_exe = gui_dir / "ApplyXAI-Agent.exe"
                    if not cli_exe.exists():
                        # Fallback to _internal directory
                        cli_exe = gui_dir / "_internal" / "ApplyXAI-Agent.exe"
                    if cli_exe.exists():
                        cmd = [str(cli_exe), "pair", "--server", server, "--code", code]
                    else:
                        # Fallback to running the GUI itself with agent mode
                        cmd = [sys.executable, "-m", "agent", "pair", "--server", server, "--code", code]
                else:
                    cmd = ["python", "-m", "agent", "pair", "--server", server, "--code", code]

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self._refresh_status()
                    self.command_queue.put(("info", "Connected successfully"))
                else:
                    self.command_queue.put(("error", f"Connection failed: {result.stderr}"))
        except Exception as e:
            self.command_queue.put(("error", f"Connection failed: {str(e)}"))

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
            if AGENT_MODULES_AVAILABLE:
                # Direct import when running from source
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
                # Subprocess when packaged
                if getattr(sys, 'frozen', False):
                    gui_dir = Path(sys.executable).parent
                    cli_exe = gui_dir / "ApplyXAI-Agent.exe"
                    if not cli_exe.exists():
                        cli_exe = gui_dir / "_internal" / "ApplyXAI-Agent.exe"
                    if cli_exe.exists():
                        cmd = [str(cli_exe), "run"]
                    else:
                        cmd = [sys.executable, "-m", "agent", "run"]
                else:
                    cmd = ["python", "-m", "agent", "run"]

                self.command_queue.put(("running", True))
                self.agent_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                       text=True, bufsize=1, universal_newlines=True)

                # Stream output to log
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
                subprocess.run(cmd, capture_output=True, text=True)

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
                result = subprocess.run(cmd, capture_output=True, text=True)
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
