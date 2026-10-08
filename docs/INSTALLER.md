# ApplyXAI Agent Installer

This installer makes the ApplyXAI Agent installable on any Windows laptop without requiring Python, PowerShell, or source code.

## Installation Methods

### Method 1: Automated Installer (Recommended)

**For End Users:**

1. Download the installer package containing:
   - `install_agent.bat`
   - `install_agent.ps1`
   - `ApplyXAI-Agent-GUI.exe`
   - `_internal/` folder

2. Right-click `install_agent.bat` and select **"Run as administrator"**

3. The installer will:
   - Install to `C:\Program Files\ApplyXAI\Agent`
   - Create Start Menu shortcut
   - Create desktop shortcut
   - Register in Programs and Features (for easy uninstall)
   - Create user data directory in `%LOCALAPPDATA%\ApplyXAI\agent`

4. Launch from Start Menu or desktop shortcut

### Method 2: Manual Installation

**For Developers/Advanced Users:**

1. Extract the distribution folder:
   - `ApplyXAI-Agent-GUI/` folder with:
     - `ApplyXAI-Agent-GUI.exe`
     - `_internal/` folder

2. Copy to desired location (e.g., `C:\Program Files\ApplyXAI\Agent`)

3. Create shortcuts manually if needed

## Installer Options

The PowerShell installer supports the following options:

```powershell
# Install with GUI and desktop shortcut
.\install_agent.ps1 -InstallGUI -CreateDesktopShortcut

# Install CLI version only
.\install_agent.ps1 -InstallGUI:$false

# Install and add to Windows startup
.\install_agent.ps1 -InstallGUI -AddToStartup

# Install to custom location
.\install_agent.ps1 -InstallPath "C:\Custom\Path"

# All options
.\install_agent.ps1 -InstallPath "C:\Program Files\ApplyXAI\Agent" -InstallGUI -CreateDesktopShortcut -AddToStartup
```

## Uninstallation

### Method 1: Using Programs and Features

1. Open **Control Panel** > **Programs and Features**
2. Find **ApplyXAI Agent**
3. Click **Uninstall**

### Method 2: Using Uninstall Script

1. Navigate to installation directory (default: `C:\Program Files\ApplyXAI\Agent`)
2. Run `uninstall.ps1` as administrator

The uninstaller will:
- Stop any running agent processes
- Remove Start Menu shortcut
- Remove desktop shortcut
- Remove from Windows startup
- Remove installation directory
- **Keep user data** (preserved in `%LOCALAPPDATA%\ApplyXAI\agent`)

## User Data Location

The agent stores user data separately from the installation:

```
%LOCALAPPDATA%\ApplyXAI\agent\
├── agent.json              # Device token and configuration
└── workspace\
    └── <user_id>\
        ├── profile\        # Chrome profile (LinkedIn login)
        ├── history\        # Applied/failed job history
        └── runs\           # Individual run logs
```

User data is **preserved** during uninstallation. To completely remove everything:

1. Uninstall using the methods above
2. Manually delete: `%LOCALAPPDATA%\ApplyXAI\agent`

## Distribution Package

The distribution package should contain:

```
ApplyXAI-Agent-Setup\
├── install_agent.bat           # Easy installer for end users
├── install_agent.ps1           # PowerShell installer
├── ApplyXAI-Agent-GUI\
│   ├── ApplyXAI-Agent-GUI.exe   # Main executable
│   └── _internal\              # Dependencies
└── README.txt                  # Installation instructions
```

### Creating the Distribution Package

From the project root:

```powershell
# Build the executables
.\scripts\build_agent.bat

# Create distribution package
mkdir ApplyXAI-Agent-Setup
copy scripts\install_agent.bat ApplyXAI-Agent-Setup\
copy scripts\install_agent.ps1 ApplyXAI-Agent-Setup\
xcopy /E /I dist\ApplyXAI-Agent-GUI ApplyXAI-Agent-Setup\ApplyXAI-Agent-GUI
copy docs\INSTALLER.md ApplyXAI-Agent-Setup\README.txt
```

## Requirements

- **Windows 10 or later**
- **Administrator privileges** for installation
- **Chrome browser** (for LinkedIn automation)

## Troubleshooting

### Installation Fails

**Problem:** "This installer requires administrator privileges"

**Solution:** Right-click `install_agent.bat` and select "Run as administrator"

### Agent Won't Start

**Problem:** Agent executable doesn't run

**Solution:** 
- Check if `_internal` folder is present in the installation directory
- Ensure antivirus is not blocking the executable
- Run as administrator if needed

### LinkedIn Login Issues

**Problem:** Chrome doesn't start or crashes

**Solution:**
- Ensure Chrome is installed on the system
- Update Chrome to the latest version
- Check Chrome profile in user data directory

### Permission Errors

**Problem:** "Access denied" errors

**Solution:**
- Run as administrator
- Check folder permissions in user data directory
- Ensure antivirus is not blocking file access

## Technical Details

### Executable Type

- **PyInstaller onedir build** (folder-based)
- **Size:** ~19 MB
- **Includes:** Python runtime, all dependencies, automation engine

### Registry Entries

The installer creates the following registry entry:

```
HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\ApplyXAI Agent
├── DisplayName: ApplyXAI Agent
├── DisplayVersion: 1.0.0
├── Publisher: ApplyXAI
├── InstallLocation: C:\Program Files\ApplyXAI\Agent
└── UninstallString: powershell.exe -ExecutionPolicy Bypass -File "...\uninstall.ps1"
```

### File Structure After Installation

```
C:\Program Files\ApplyXAI\Agent\
├── ApplyXAI-Agent-GUI.exe     # Main executable
├── _internal\                  # Dependencies
│   ├── python312.dll
│   ├── config/
│   ├── modules/
│   └── ...
└── uninstall.ps1              # Uninstaller script
```

## Security Considerations

✅ **No admin privileges required** to run the agent (only for installation)
✅ **User data isolated** in %LOCALAPPDATA%
✅ **No secrets bundled** in executable
✅ **HTTPS-only communication** with ApplyXAI server
✅ **Device token authentication** required
✅ **Clean uninstall** (preserves user data)

⚠️ **Known Limitations:**
- No code signing (SmartScreen warning possible)
- Device token stored in plain text (acceptable for MVP)
- No automatic updates (planned for v1.1)

## Support

For issues or questions:
- Check the agent logs in user data directory
- Review the engine.log for automation errors
- Contact support at support@applyxai.com
