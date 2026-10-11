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
Write-Host "Step 6: Packaging ZIP for browser download..." -ForegroundColor Yellow
$ZipPath = Join-Path $DistDir "ApplyXAI-Agent-Windows.zip"
$ZipStage = Join-Path $env:TEMP ("applyxai-agent-zip-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $ZipStage -Force | Out-Null
$Readme = @"
ApplyXAI Agent for Windows
==========================

1. Extract this folder to somewhere permanent (e.g. Desktop\ApplyXAI-Agent).
2. Run ApplyXAI-Agent-Setup.exe if present, otherwise ApplyXAI-Agent-GUI.exe.
3. Sign in on applyxai.com, open Automation, and use Connect — Live in the desktop app.

If Chrome or Windows warns about an unsigned file, choose Keep / Run anyway.
"@
Set-Content -Path (Join-Path $ZipStage "README.txt") -Value $Readme -Encoding UTF8
$SetupExe = Join-Path $DistDir "ApplyXAI-Agent-Setup.exe"
$GuiExe = Join-Path $DistDir "ApplyXAI-Agent-GUI.exe"
if (-not (Test-Path -LiteralPath $GuiExe)) {
    $GuiExe = Join-Path $DistDir "ApplyXAI-Agent-GUI\ApplyXAI-Agent-GUI.exe"
}
$CliExe = Join-Path $DistDir "ApplyXAI-Agent.exe"
if (-not (Test-Path -LiteralPath $CliExe)) {
    $CliExe = Join-Path $DistDir "ApplyXAI-Agent\ApplyXAI-Agent.exe"
}
if (Test-Path -LiteralPath $SetupExe) {
    Copy-Item -LiteralPath $SetupExe -Destination $ZipStage
} else {
    if (Test-Path -LiteralPath $GuiExe) { Copy-Item -LiteralPath $GuiExe -Destination $ZipStage }
    if (Test-Path -LiteralPath $CliExe) { Copy-Item -LiteralPath $CliExe -Destination $ZipStage }
}
if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
Compress-Archive -Path (Join-Path $ZipStage "*") -DestinationPath $ZipPath -CompressionLevel Optimal
Remove-Item -LiteralPath $ZipStage -Recurse -Force
Write-Host "  ZIP: $ZipPath"

Write-Host ""
Write-Host "=== Build Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Artifacts:"
Write-Host "  CLI: $DistDir\ApplyXAI-Agent.exe"
Write-Host "  GUI: $DistDir\ApplyXAI-Agent-GUI.exe"
if ($InnoSetup) {
    Write-Host "  Installer: $DistDir\ApplyXAI-Agent-Setup.exe"
}
Write-Host "  ZIP:   $DistDir\ApplyXAI-Agent-Windows.zip"
Write-Host ""
Write-Host "To test the CLI:"
Write-Host "  cd $DistDir"
Write-Host "  .\ApplyXAI-Agent.exe --help"
Write-Host ""
Write-Host "To test the GUI:"
Write-Host "  cd $DistDir"
Write-Host "  .\ApplyXAI-Agent-GUI.exe"
