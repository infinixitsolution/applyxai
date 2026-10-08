@echo off
REM ApplyXAI Agent Distribution Package Creator
REM Creates a distributable package with installer

setlocal enabledelayedexpansion

REM Change to repository root
cd /d "%~dp0.."
set REPO_ROOT=%CD%
set DIST_DIR=%REPO_ROOT%\dist
set PACKAGE_DIR=%REPO_ROOT%\ApplyXAI-Agent-Setup-v1.0.0

echo === ApplyXAI Agent Distribution Package Creator ===
echo Repository: %REPO_ROOT%
echo.

REM Check if executables are built
if not exist "%DIST_DIR%\ApplyXAI-Agent-GUI.exe" (
    echo Error: GUI executable not found.
    echo Please build first: .\scripts\build_agent.bat
    exit /b 1
)

echo Step 1: Cleaning previous package...
if exist "%PACKAGE_DIR%" (
    rmdir /s /q "%PACKAGE_DIR%"
    echo   Removed previous package
)

echo.
echo Step 2: Creating package directory...
mkdir "%PACKAGE_DIR%"

echo.
echo Step 3: Copying files...
copy scripts\install_agent.bat "%PACKAGE_DIR%\" >nul
copy scripts\install_agent.ps1 "%PACKAGE_DIR%\" >nul
copy "%DIST_DIR%\ApplyXAI-Agent-GUI.exe" "%PACKAGE_DIR%\ApplyXAI-Agent-GUI.exe" >nul
copy docs\INSTALLER.md "%PACKAGE_DIR%\README.txt" >nul

echo.
echo Step 4: Creating version file...
echo ApplyXAI Agent v1.0.0 > "%PACKAGE_DIR%\VERSION.txt"
echo Built: %date% %time% >> "%PACKAGE_DIR%\VERSION.txt"

echo.
echo Step 5: Creating quick start guide...
(
echo ApplyXAI Agent - Quick Start Guide
echo ==================================
echo.
echo 1. Double-click install_agent.bat
echo 2. Click "Yes" if prompted by User Account Control
echo 3. Wait for installation to complete
echo 4. Launch from Start Menu or desktop shortcut
echo.
echo For detailed instructions, see README.txt
echo.
echo System Requirements:
echo - Windows 10 or later
echo - Chrome browser (for LinkedIn automation)
echo - Administrator privileges for installation only
) > "%PACKAGE_DIR%\QUICKSTART.txt"

echo.
echo === Package Created Successfully ===
echo.
echo Package location: %PACKAGE_DIR%
echo.
echo Package contents:
echo   - install_agent.bat (installer launcher)
echo   - install_agent.ps1 (installer script)
echo   - ApplyXAI-Agent-GUI.exe (single-file executable)
echo   - README.txt (detailed instructions)
echo   - QUICKSTART.txt (quick start guide)
echo   - VERSION.txt (version info)
echo.
echo To distribute:
echo   1. Zip the %PACKAGE_DIR% folder
echo   2. Upload to your website
echo   3. Users download, extract, and run install_agent.bat
echo.

pause
