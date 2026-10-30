# ApplyXAI Agent - Windows Distribution

This document describes the Windows executable distribution of the ApplyXAI Agent and **ApplyXAI Desktop**.

## ApplyXAI Desktop (full app)

**ApplyXAI Desktop** is an Electron app that bundles the complete web UI and a headless **`agent-worker.exe`**. It talks to **https://applyxai.com** only (API proxied locally for session cookies). Build with `scripts\build_desktop.ps1` → `dist\ApplyXAI-Desktop-Setup.exe`.

```
ApplyXAI Cloud (https://applyxai.com)
         |
         +-- Electron UI (bundled SPA, all roles/RBAC)
         |
         +-- agent-worker.exe (wake :39217 + supervisor)
                 |
                 v
         Automation Engine (runAiBot.py) → Chrome → LinkedIn / Naukri
```

### Live interview coaching (Desktop)

Live interviews run **inside ApplyXAI Desktop**, not in the legacy Tkinter GUI:

1. Open **Support** or **Live interviews** in the desktop app.
2. Use the **Live interview** panel: **Request** → pay if prompted → confirm the 8-digit token → pick an auto-applied job.
3. Optional: **Test audio** before starting (checks microphone + system loopback permissions).
4. Click **Start interview** (requires this computer linked under **Automation**). Device auth uses the same token as the automation worker (`agent.json` or Windows Credential Manager **ApplyXAI** / `agent_device_token`).
5. Allow **screen/system audio** and **microphone** when Windows prompts — the coach listens to the call and suggests answers in the floating panel.
6. The **coach icon and panel** open in a separate always-on-top window on your desktop (not inside the main ApplyXAI window), so you can keep the app in the background during the call.
7. Click **End interview** in the coach when finished; the report appears under **Live interviews**. For an API session still **In progress**, use **Continue in coach** on **Live interviews** to reopen the floating coach.

**Manual QA checklist (Windows):**

| Step | Expected |
|------|----------|
| Automation → link this PC | Device shows online |
| Support → Request live interview → token in chat | 8-digit token visible |
| Live interviews → Test audio | Success or clear permission error |
| Start interview | Floating coach; transcript updates |
| End interview | Session completed; report on `/app/live-interviews` |
| Continue in coach (after closing coach, session still active) | Coach restarts without new token |

## Naukri (staging and production)

Naukri on-site Apply runs in the same engine as LinkedIn. It is **off by default** (`ENABLE_NAUKRI=false` in `backend/app/core/config.py`). An **admin** must turn on **Naukri** under **Admin → Settings → Job sources** (or set the env var) before users can select it on the Automation page.

### Staging / local smoke

1. Set `ENABLE_NAUKRI=true` in the backend `.env` (or enable Naukri in admin job sources). Restart the API after changing `.env`.
2. On Automation, choose **Naukri** only or **LinkedIn + Naukri** with a switch count.
3. Save **LinkedIn** and **Naukri** logins on this PC:
   - **ApplyXAI Desktop**: Automation page → **Job site logins (this computer)**.
   - **Legacy GUI**: Credentials tab → Save credentials.
   - File: `%LOCALAPPDATA%\ApplyXAI\agent\user_config.json` under `secrets` (`naukri_username`, `naukri_password`).
4. Start a **dry run** first; sign in manually in Chrome if auto-login is blank.
5. Automated API smoke: `pytest backend/tests/test_naukri_staging.py`.

Per-site applied history is stored under `history\linkedin\` and `history\naukri\`.

## Legacy agent-only distribution

The standalone agent is still built with `scripts\build_agent.ps1` for developers and browser-only users.

## Overview

The ApplyXAI Agent runs job automation on the user's computer. It connects to the ApplyXAI web service to receive automation jobs and executes them using the LinkedIn automation engine.

## Architecture (legacy agent)

```
ApplyXAI Cloud (HTTPS/WSS)
         |
         v
ApplyXAI-Agent.exe (CLI) or ApplyXAI-Agent-GUI.exe (GUI)
         |
         v
Automation Engine (runAiBot.py)
         |
         v
Chrome/Selenium
         |
         v
LinkedIn
```

## Versions

- **Desktop**: `ApplyXAI-Desktop-Setup.exe` — full web app + embedded worker (recommended)
- **CLI Version**: `ApplyXAI-Agent.exe` - Command-line interface for advanced users
- **GUI Version**: `ApplyXAI-Agent-GUI.exe` - Graphical interface for ease of use (legacy)

## Installation

### From Installer

1. Download `ApplyXAI-Agent-Setup.exe` from the ApplyXAI website
2. Run the installer
3. Choose installation directory (default: `C:\Program Files\ApplyXAI\Agent`)
4. Optionally create desktop icon
5. Optionally start with Windows (disabled by default)
6. Click "Finish" to complete installation

### Manual Installation

1. Download and extract the ZIP archive
2. Move the extracted folder to your desired location
3. Create shortcuts as needed

## Usage

### GUI Version

1. Launch `ApplyXAI-Agent-GUI.exe`
2. Click "Connect Computer" on the Automation page of the ApplyXAI web app
3. Enter the pairing code in the GUI
4. Enter the server URL (default: `https://app.applyxai.com`)
5. Click "Connect"
6. Once connected, click "Start Agent" to begin waiting for jobs
7. View logs in the log window

### CLI Version

Open Command Prompt or PowerShell and navigate to the installation directory:

```powershell
# Pair with the server
ApplyXAI-Agent.exe pair --server https://app.applyxai.com --code YOUR_CODE

# Start the agent
ApplyXAI-Agent.exe run

# Check status
ApplyXAI-Agent.exe status

# Disconnect
ApplyXAI-Agent.exe unpair
```

## Local Data Storage

The agent stores its data in the Windows per-user application directory:

```
%LOCALAPPDATA%\ApplyXAI\agent\
├── agent.json          # Device token and configuration
├── user_config.json    # Optional local logins (LinkedIn + Naukri); never uploaded
└── workspace\
    └── <user_id>\
        ├── profile\    # Chrome profile (LinkedIn login state)
        ├── history\    # Applied/failed job history
        └── runs\       # Individual run logs and data
```

**Note**: This directory is private to the current Windows user. Each user has their own agent data.

## Logs

### Agent Logs

Agent logs are displayed in the GUI log window and stored in the workspace:

```
%LOCALAPPDATA%\ApplyXAI\agent\workspace\<user_id>\runs\<run_id>\engine.log
```

### Viewing Logs

- **GUI**: Click "Open Logs Folder" to open the agent data directory in File Explorer
- **CLI**: Logs are printed to the console

## Uninstallation

### From Installer

1. Go to Control Panel > Programs and Features
2. Find "ApplyXAI Agent"
3. Click "Uninstall"
4. Follow the prompts

**Note**: User data in `%LOCALAPPDATA%\ApplyXAI\agent` is preserved by default.

### Manual Removal

1. Delete the installation directory
2. Delete shortcuts
3. Optionally delete user data: `%LOCALAPPDATA%\ApplyXAI\agent`

## Troubleshooting

### Agent won't start

1. Check that Chrome is installed
2. Check that you have internet connectivity
3. Check the logs for error messages
4. Verify the pairing code is still valid (codes expire in 10 minutes)

### "Not paired" error

- You need to pair the computer first using the "Connect Computer" button on the Automation page
- Pairing codes are one-time use and expire after 10 minutes

### Chrome won't open

- Ensure Google Chrome is installed
- The agent uses undetected-chromedriver which auto-downloads a compatible driver
- Check firewall/antivirus settings

### "Connection failed" error

- Verify the server URL is correct (e.g., `https://app.applyxai.com`)
- Check your internet connection
- The server may be temporarily unavailable

### Automation stops unexpectedly

- Check the logs for error messages
- Ensure you're signed in to LinkedIn in the Chrome window
- Check your plan limits on the ApplyXAI website

## Security

### What's Stored Locally

- Device token (authentication credential)
- Chrome profile (LinkedIn session)
- Job application history (CSV files)
- Run logs

### What's NOT Stored

- LinkedIn password (never handled by ApplyXAI)
- ApplyXAI account password
- API keys
- Payment information

### Encryption

- Device token is stored in Windows Credential Manager (service `ApplyXAI`, account `agent_device_token`) via `keyring` / Desktop `keytar`.
- `agent.json` keeps server/device metadata. The token is omitted from that file when Credential Manager succeeds, and falls back to `agent.json` only if the OS store is unavailable.

### Network Security

- All communication with ApplyXAI servers uses HTTPS/WSS
- Plain HTTP is only allowed for localhost (development)

## Developer Build Process

### Prerequisites

- Python 3.10+
- Virtual environment
- PyInstaller
- (Optional) Inno Setup for installer creation

### Building

1. Activate virtual environment:
   ```powershell
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Run build script:
   ```powershell
   scripts\build_agent.bat
   ```

   Or manually:
   ```powershell
   venv\Scripts\pyinstaller.exe build/applyxai_agent.spec --clean
   venv\Scripts\pyinstaller.exe build/applyxai_agent_gui.spec --clean
   ```

4. Build installer (requires Inno Setup):
   ```powershell
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build/applyxai_agent_setup.iss
   ```

### Artifacts

- CLI: `dist/ApplyXAI-Agent/ApplyXAI-Agent.exe`
- GUI: `dist/ApplyXAI-Agent-GUI/ApplyXAI-Agent-GUI.exe`
- Installer: `dist/ApplyXAI-Agent-Setup.exe`

### Testing

```powershell
# Test CLI
cd dist\ApplyXAI-Agent
.\ApplyXAI-Agent.exe --help
.\ApplyXAI-Agent.exe status

# Test GUI
cd dist\ApplyXAI-Agent-GUI
.\ApplyXAI-Agent-GUI.exe
```

## Version History

- **1.0.0** - Initial Windows release with CLI and GUI
- **0.1.0** - Development version

## Auto-Update

The current version does not include automatic updates. A future version will:

- Check for updates on startup
- Download and install updates with user confirmation
- Preserve user data during updates

## Support

For issues and support:
- Discord: https://discord.gg/fFp7uUzWCY
- GitHub Issues: https://github.com/GodsScion/Auto_job_applier_linkedIn/issues
- Email:
