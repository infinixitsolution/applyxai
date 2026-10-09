@echo off
REM ApplyXAI Agent Build Script for Windows (Batch version)
REM Builds both CLI and GUI versions of the agent

setlocal enabledelayedexpansion

REM Change to repository root
cd /d "%~dp0.."
set REPO_ROOT=%CD%
set BUILD_DIR=%REPO_ROOT%\build
set DIST_DIR=%REPO_ROOT%\dist

echo === ApplyXAI Agent Build Script ===
echo Repository: %REPO_ROOT%
echo.

REM Check for virtual environment
set VENV_PYTHON=%REPO_ROOT%\venv\Scripts\python.exe
if not exist "%VENV_PYTHON%" (
    echo Error: Virtual environment not found at %VENV_PYTHON%
    echo Please create a virtual environment first:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    exit /b 1
)

echo Step 1: Cleaning previous build artifacts...
if exist "%DIST_DIR%" (
    rmdir /s /q "%DIST_DIR%"
    echo   Removed dist\
)
if exist "%REPO_ROOT%\build\applyxai_agent" (
    rmdir /s /q "%REPO_ROOT%\build\applyxai_agent"
    echo   Removed build\applyxai_agent
)
if exist "%REPO_ROOT%\build\applyxai_agent_gui" (
    rmdir /s /q "%REPO_ROOT%\build\applyxai_agent_gui"
    echo   Removed build\applyxai_agent_gui
)

echo.
echo Step 2: Installing PyInstaller...
"%VENV_PYTHON%" -m pip install pyinstaller --quiet
if errorlevel 1 (
    echo Error: Failed to install PyInstaller
    exit /b 1
)
echo   PyInstaller installed

echo.
echo Step 3: Running tests...
cd /d "%REPO_ROOT%"
"%VENV_PYTHON%" -m pytest tests/test_agent.py -v
if errorlevel 1 (
    echo Warning: Tests failed. Continuing with build...
)

echo.
echo Step 4: Building CLI executable...
set CLI_SPEC=%BUILD_DIR%\applyxai_agent.spec
"%REPO_ROOT%\venv\Scripts\pyinstaller.exe" "%CLI_SPEC%" --clean
if errorlevel 1 (
    echo Error: CLI build failed
    exit /b 1
)
echo   CLI built successfully

echo.
echo Step 5: Building GUI executable...
set GUI_SPEC=%BUILD_DIR%\applyxai_agent_gui.spec
"%REPO_ROOT%\venv\Scripts\pyinstaller.exe" "%GUI_SPEC%" --clean
if errorlevel 1 (
    echo Error: GUI build failed
    exit /b 1
)
echo   GUI built successfully

echo.
echo Step 6: Building installer (optional)...
set INNO_PATH1=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
set INNO_PATH2=%ProgramFiles%\Inno Setup 6\ISCC.exe
set INNO_PATH3=%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe
set INNO_PATH4=%ProgramFiles%\Inno Setup 5\ISCC.exe
set INNO_PATH5=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe

set INNO_SETUP=
if exist "%INNO_PATH1%" set INNO_SETUP=%INNO_PATH1%
if exist "%INNO_PATH2%" set INNO_SETUP=%INNO_PATH2%
if exist "%INNO_PATH3%" set INNO_SETUP=%INNO_PATH3%
if exist "%INNO_PATH4%" set INNO_SETUP=%INNO_PATH4%
if exist "%INNO_PATH5%" set INNO_SETUP=%INNO_PATH5%

if defined INNO_SETUP (
    set INSTALLER_SPEC=%BUILD_DIR%\applyxai_agent_setup.iss
    "%INNO_SETUP%" "%INSTALLER_SPEC%"
    if errorlevel 1 (
        echo Warning: Installer build failed
    ) else (
        echo   Installer built successfully
    )
) else (
    echo   Inno Setup not found. Skipping installer build.
    echo   Download from: https://jrsoftware.org/isdl.php
)

echo.
echo === Build Complete ===
echo.
echo Artifacts:
echo   CLI: %DIST_DIR%\ApplyXAI-Agent.exe
echo   GUI: %DIST_DIR%\ApplyXAI-Agent-GUI.exe
if defined INNO_SETUP (
    echo   Installer: %DIST_DIR%\ApplyXAI-Agent-Setup.exe
) else (
    echo   Installer: run scripts\package_distribution.bat after installing Inno Setup 6
)
echo.
echo To test:
echo   %DIST_DIR%\ApplyXAI-Agent-GUI.exe
echo   %DIST_DIR%\ApplyXAI-Agent.exe --help
echo.

pause
