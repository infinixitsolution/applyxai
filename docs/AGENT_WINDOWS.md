# ApplyXAI Agent - Windows Distribution

This document describes the Windows executable distribution of the ApplyXAI Agent.

## Overview

The ApplyXAI Agent is a Windows desktop application that runs job automation on the user's computer. It connects to the ApplyXAI web service to receive automation jobs and executes them using the LinkedIn automation engine.

## Architecture

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

- **CLI Version**: `ApplyXAI-Agent.exe` - Command-line interface for advanced users
- **GUI Version**: `ApplyXAI-Agent-GUI.exe` - Graphical interface for ease of use

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

- Device tokens are stored in plain text in `agent.json`
- Future versions may use Windows Credential Manager for enhanced security

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
- Email: saivigneshgolla@outlook.com
