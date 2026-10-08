@echo off
echo ApplyXAI Agent Installer
echo ========================
echo.

REM Check for administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This installer requires administrator privileges.
    echo Please right-click and select "Run as administrator".
    pause
    exit /b 1
)

REM Run the PowerShell installer
powershell.exe -ExecutionPolicy Bypass -File "%~dp0install_agent.ps1" -InstallGUI -CreateDesktopShortcut

pause
