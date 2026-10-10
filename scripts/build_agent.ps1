# ApplyXAI Agent Build Script for Windows
# Builds both CLI and GUI versions of the agent

$ErrorActionPreference = "Stop"

# Repository root
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$BuildDir = Join-Path $RepoRoot "build"
$DistDir = Join-Path $RepoRoot "dist"

Write-Host "=== ApplyXAI Agent Build Script ===" -ForegroundColor Cyan
Write-Host "Repository: $RepoRoot"
Write-Host ""

# Check for virtual environment
$VenvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Error: Virtual environment not found at $VenvPython" -ForegroundColor Red
    Write-Host "Please create a virtual environment first:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv"
    Write-Host "  venv\Scripts\activate"
    Write-Host "  pip install -r requirements.txt"
    exit 1
}

Write-Host "Step 1: Cleaning previous build artifacts..." -ForegroundColor Yellow
if (Test-Path $DistDir) {
    Remove-Item -Path $DistDir -Recurse -Force
    Write-Host "  Removed dist/"
}
foreach ($sub in @("applyxai_agent", "applyxai_agent_gui")) {
    $cache = Join-Path $BuildDir $sub
    if (Test-Path $cache) {
        Remove-Item -Path $cache -Recurse -Force
        Write-Host "  Removed build/$sub/"
    }
}

Write-Host ""
Write-Host "Step 2: Installing PyInstaller..." -ForegroundColor Yellow
& $VenvPython -m pip install pyinstaller --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to install PyInstaller" -ForegroundColor Red
    exit 1
}
Write-Host "  PyInstaller installed"

Write-Host ""
Write-Host ""
Write-Host "Step 3: Building CLI executable..." -ForegroundColor Yellow
$CliSpec = Join-Path $BuildDir "applyxai_agent.spec"
& (Join-Path $RepoRoot "venv\Scripts\pyinstaller.exe") $CliSpec --clean
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: CLI build failed" -ForegroundColor Red
    exit 1
}
Write-Host "  CLI built successfully"

Write-Host ""
Write-Host "Step 4: Building GUI executable..." -ForegroundColor Yellow
$GuiSpec = Join-Path $BuildDir "applyxai_agent_gui.spec"
& (Join-Path $RepoRoot "venv\Scripts\pyinstaller.exe") $GuiSpec --clean
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: GUI build failed" -ForegroundColor Red
    exit 1
}
Write-Host "  GUI built successfully"

Write-Host ""
Write-Host "Step 5: Building installer (optional)..." -ForegroundColor Yellow
$InnoSetupPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 5\ISCC.exe"
)

$InnoSetup = $null
foreach ($path in $InnoSetupPaths) {
    if (Test-Path $path) {
        $InnoSetup = $path
        break
    }
}

if ($InnoSetup) {
    $InstallerSpec = Join-Path $BuildDir "applyxai_agent_setup.iss"
    & $InnoSetup $InstallerSpec
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Installer build failed" -ForegroundColor Yellow
    } else {
        Write-Host "  Installer built successfully"
    }
} else {
    Write-Host "  Inno Setup not found. Skipping installer build." -ForegroundColor Yellow
    Write-Host "  Download from: https://jrsoftware.org/isdl.php"
}

Write-Host ""
Write-Host "=== Build Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Artifacts:"
Write-Host "  CLI: $DistDir\ApplyXAI-Agent\ApplyXAI-Agent.exe"
Write-Host "  GUI: $DistDir\ApplyXAI-Agent-GUI\ApplyXAI-Agent-GUI.exe"
if ($InnoSetup) {
    Write-Host "  Installer: $DistDir\ApplyXAI-Agent-Setup.exe"
}
Write-Host ""
Write-Host "To test the CLI:"
Write-Host "  cd $DistDir\ApplyXAI-Agent"
Write-Host "  .\ApplyXAI-Agent.exe --help"
Write-Host ""
Write-Host "To test the GUI:"
Write-Host "  cd $DistDir\ApplyXAI-Agent-GUI"
Write-Host "  .\ApplyXAI-Agent-GUI.exe"
