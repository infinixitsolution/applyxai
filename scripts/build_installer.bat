@echo off
REM Build ApplyXAI-Agent-Setup.exe (GUI + CLI) with Inno Setup 6.
setlocal
cd /d "%~dp0.."
set REPO=%CD%

if not exist "%REPO%\dist\ApplyXAI-Agent-GUI.exe" (
    echo Missing dist\ApplyXAI-Agent-GUI.exe — run scripts\build_agent.bat first.
    exit /b 1
)
if not exist "%REPO%\dist\ApplyXAI-Agent.exe" (
    echo Missing dist\ApplyXAI-Agent.exe — run scripts\build_agent.bat first.
    exit /b 1
)

set "ISCC="
set "PF86=%ProgramFiles(x86)%"
if exist "%PF86%\Inno Setup 6\ISCC.exe" set "ISCC=%PF86%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo Inno Setup 6 not found. Download: https://jrsoftware.org/isdl.php
    exit /b 1
)

echo Building installer...
"%ISCC%" "%REPO%\build\applyxai_agent_setup.iss"
if errorlevel 1 exit /b 1
echo.
echo Done: %REPO%\dist\ApplyXAI-Agent-Setup.exe
exit /b 0
