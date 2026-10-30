# Build ApplyXAI Desktop (Electron + bundled SPA + agent worker) for Windows.
# Default: packaged exe proxies /api to local dev (http://127.0.0.1:8010).
# Production installer: $env:APPLYXAI_DESKTOP_RELEASE = "1"; .\scripts\build_desktop.ps1
param(
    [switch]$Release
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$IsRelease = $Release -or ($env:APPLYXAI_DESKTOP_RELEASE -eq "1")
$PackagedApiOrigin = if ($IsRelease) { "https://applyxai.com" } else { "http://127.0.0.1:8010" }

$VenvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Create venv and install requirements first." -ForegroundColor Red
    exit 1
}

$VersionFile = Join-Path $RepoRoot "VERSION"
$ProductVersion = (Get-Content $VersionFile -Raw).Trim().Split("`n")[0].Trim()
Write-Host "=== ApplyXAI Desktop build v$ProductVersion ($(
    if ($IsRelease) { 'production API' } else { 'local dev API' }
)) ===" -ForegroundColor Cyan
Write-Host "Packaged API default: $PackagedApiOrigin" -ForegroundColor DarkGray

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($Path, $Content, $utf8)
}

$ProductVersionTs = Join-Path $RepoRoot "desktop\src\productVersion.ts"
$productVersionSource = @(
  "/** Auto-synced from VERSION by scripts/build_desktop.ps1 */",
  "export const PRODUCT_VERSION = `"$ProductVersion`";",
  "/** Default /api proxy target when the packaged exe starts (override with APPLYXAI_API_URL). */",
  "export const PACKAGED_API_ORIGIN = `"$PackagedApiOrigin`";",
  ""
) -join "`n"
Write-Utf8NoBom $ProductVersionTs $productVersionSource

$DesktopPkg = Join-Path $RepoRoot "desktop\package.json"
if (Test-Path $DesktopPkg) {
    $raw = Get-Content $DesktopPkg -Raw
    $updated = $raw -replace '"version"\s*:\s*"[^"]+"', "`"version`": `"$ProductVersion`""
    Write-Utf8NoBom $DesktopPkg $updated.TrimEnd()
}

Write-Host "Stopping ApplyXAI Desktop if running (unlocks dist\win-unpacked)..." -ForegroundColor DarkGray
Get-Process -Name "ApplyXAI", "agent-worker", "electron" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and ($_.Path -like "*\applyxainew\dist\win-unpacked\*" -or $_.Path -like "*\applyxainew\dist\desktop-build\*")
} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "Step 1: Frontend (desktop env)..." -ForegroundColor Yellow
Push-Location (Join-Path $RepoRoot "frontend")
if (-not $env:APPLYXAI_CLOUD_API) { $env:APPLYXAI_CLOUD_API = $PackagedApiOrigin }
$env:VITE_AGENT_SERVER_URL = $env:APPLYXAI_CLOUD_API
$env:VITE_DESKTOP_BUILD = "1"
if (Test-Path "node_modules") {
    npm run build
} elseif (Test-Path "package-lock.json") {
    npm ci
    if ($LASTEXITCODE -ne 0) { npm install; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
    npm run build
} else {
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm run build
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Pop-Location

Write-Host "Step 2: Copy frontend dist into desktop/resources/dist..." -ForegroundColor Yellow
$DistTarget = Join-Path $RepoRoot "desktop\resources\dist"
if (Test-Path $DistTarget) { Remove-Item $DistTarget -Recurse -Force }
New-Item -ItemType Directory -Force -Path $DistTarget | Out-Null
Copy-Item -Path (Join-Path $RepoRoot "frontend\dist\*") -Destination $DistTarget -Recurse

$ChromeDriver = Join-Path $RepoRoot "vendor\chromedriver-win64.exe"
if (-not (Test-Path $ChromeDriver)) { $ChromeDriver = Join-Path $RepoRoot "vendor\chromedriver.exe" }
if (-not (Test-Path $ChromeDriver)) {
    Write-Host "ChromeDriver not in vendor/; downloading pinned Windows x64 driver..." -ForegroundColor DarkGray
    try {
        & (Join-Path $RepoRoot "scripts\fetch_chromedriver.ps1")
    } catch {
        Write-Host "ChromeDriver download skipped ($($_.Exception.Message)). Selenium Manager will fetch at runtime." -ForegroundColor Yellow
    }
}

if ($env:CSC_LINK) {
    Write-Host "Authenticode: CSC_LINK is set; electron-builder will sign the NSIS installer." -ForegroundColor Green
} else {
    Write-Host "Authenticode: CSC_LINK not set. Installer will be unsigned (SmartScreen). Supply a cert to sign." -ForegroundColor DarkGray
}

Write-Host "Step 3: PyInstaller agent worker..." -ForegroundColor Yellow
& $VenvPython -m pip install pyinstaller --quiet
& $VenvPython -m PyInstaller build/applyxai_agent_worker.spec --noconfirm
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$WorkerVersioned = Join-Path $RepoRoot "dist\agent-worker-v$ProductVersion.exe"
$WorkerStable = Join-Path $RepoRoot "dist\agent-worker.exe"
if (Test-Path $WorkerVersioned) {
    Copy-Item $WorkerVersioned $WorkerStable -Force
    $WorkerResource = Join-Path $RepoRoot "desktop\resources\agent-worker-v$ProductVersion.exe"
    Copy-Item $WorkerVersioned $WorkerResource -Force
    Write-Host "Agent worker: dist\agent-worker-v$ProductVersion.exe (+ dist\agent-worker.exe)" -ForegroundColor Green
} else {
    Write-Host "Expected $WorkerVersioned - check PyInstaller output." -ForegroundColor Red
    exit 1
}

Write-Host "Step 4: Electron package..." -ForegroundColor Yellow
$DistRoot = Join-Path $RepoRoot "dist"
$WinUnpacked = Join-Path $DistRoot "win-unpacked"
if (Test-Path $WinUnpacked) {
    try {
        Remove-Item $WinUnpacked -Recurse -Force -ErrorAction Stop
    } catch {
        Write-Host "dist\win-unpacked is locked (close ApplyXAI Desktop if it is running). Building to dist\desktop-build instead." -ForegroundColor Yellow
        $env:APPLYXAI_DESKTOP_OUTPUT = "desktop-build"
    }
}

Push-Location (Join-Path $RepoRoot "desktop")
if (Test-Path "package-lock.json") { npm ci } else { npm install }
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$PreloadJs = Join-Path (Get-Location) "dist\preload.js"
if (-not (Test-Path $PreloadJs)) {
    Write-Host "Build verification failed: missing desktop\dist\preload.js" -ForegroundColor Red
    exit 1
}
$preloadText = Get-Content $PreloadJs -Raw
if ($preloadText -match 'require\("\./config"\)') {
    Write-Host "Build verification failed: preload.js must not import ./config (breaks Electron bridge)." -ForegroundColor Red
    exit 1
}
if ($env:APPLYXAI_DESKTOP_OUTPUT) {
    npx electron-builder --win --config electron-builder.yml --config.directories.output=../dist/$env:APPLYXAI_DESKTOP_OUTPUT
} else {
    npm run dist
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Pop-Location

$ElectronOut = if ($env:APPLYXAI_DESKTOP_OUTPUT) { Join-Path $DistRoot $env:APPLYXAI_DESKTOP_OUTPUT } else { $DistRoot }
$SetupVersioned = Join-Path $ElectronOut "ApplyXAI-Desktop-Setup-v$ProductVersion.exe"
$SetupStable = Join-Path $DistRoot "ApplyXAI-Desktop-Setup.exe"
if (Test-Path $SetupVersioned) {
    Copy-Item $SetupVersioned $SetupStable -Force
    $versionedAtRoot = Join-Path $DistRoot "ApplyXAI-Desktop-Setup-v$ProductVersion.exe"
    $srcPath = (Resolve-Path $SetupVersioned).Path
    $dstPath = if (Test-Path $versionedAtRoot) { (Resolve-Path $versionedAtRoot).Path } else { "" }
    if ($srcPath -ne $dstPath) {
        Copy-Item $SetupVersioned $versionedAtRoot -Force
    }
} elseif (Test-Path (Join-Path $ElectronOut "ApplyXAI-Desktop-Setup.exe")) {
    Copy-Item (Join-Path $ElectronOut "ApplyXAI-Desktop-Setup.exe") $SetupStable -Force
}

$UnpackedExe = Join-Path $ElectronOut "win-unpacked\ApplyXAI.exe"
if (-not (Test-Path $UnpackedExe)) {
    $UnpackedExe = Join-Path $DistRoot "win-unpacked\ApplyXAI.exe"
}
$Launcher = Join-Path $RepoRoot "dist\ApplyXAI-Launch.bat"
@(
  "@echo off",
  "set APPLYXAI_PROJECT_ROOT=$RepoRoot",
  "rem Do not set APPLYXAI_DESKTOP_LOCAL=1 (forces Vite public site).",
  "set APPLYXAI_API_URL=http://127.0.0.1:8010",
  "set APPLYXAI_CLOUD_API=http://127.0.0.1:8010",
  "start `"`" `"$UnpackedExe`""
) | Set-Content -Path $Launcher -Encoding ASCII

$DesktopSetup = Join-Path $RepoRoot "dist\ApplyXAI-Desktop-Setup.exe"
$DesktopZip = Join-Path $RepoRoot "dist\ApplyXAI-Desktop-Windows.zip"
if (Test-Path $DesktopSetup) {
    try {
        if (Test-Path $DesktopZip) { Remove-Item $DesktopZip -Force -ErrorAction Stop }
        Compress-Archive -Path $DesktopSetup -DestinationPath $DesktopZip -ErrorAction Stop
        Write-Host "ZIP mirror: dist\ApplyXAI-Desktop-Windows.zip" -ForegroundColor Green
    } catch {
        Write-Host "Skipped ZIP mirror (file locked - close ApplyXAI Desktop / Explorer preview): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host "Step 5: Verify artifacts..." -ForegroundColor Yellow
$Required = @(
    (Join-Path $RepoRoot "dist\agent-worker-v$ProductVersion.exe"),
    (Join-Path $RepoRoot "dist\agent-worker.exe"),
    (Join-Path $DistRoot "ApplyXAI-Desktop-Setup-v$ProductVersion.exe")
)
foreach ($path in $Required) {
    if (-not (Test-Path $path)) {
        Write-Host "Build verification failed: missing $path" -ForegroundColor Red
        exit 1
    }
}
$BundledWorker = Join-Path $ElectronOut "win-unpacked\resources\agent-worker.exe"
if (-not (Test-Path $BundledWorker)) {
    Write-Host "Build verification failed: installer did not bundle agent-worker.exe at $BundledWorker" -ForegroundColor Red
    exit 1
}
$srcLen = (Get-Item $WorkerStable).Length
$dstLen = (Get-Item $BundledWorker).Length
if ($srcLen -ne $dstLen) {
    Write-Host "Build verification failed: bundled worker size ($dstLen) != dist\agent-worker.exe ($srcLen)" -ForegroundColor Red
    exit 1
}
Write-Host "Verified: worker v$ProductVersion bundled in Desktop installer." -ForegroundColor Green

Write-Host "Step 6: Single-file release layout (worker embedded in installer only)..." -ForegroundColor Yellow
$BuildCache = Join-Path $DistRoot ".build-cache"
New-Item -ItemType Directory -Force -Path $BuildCache | Out-Null
foreach ($workerArtifact in @($WorkerVersioned, $WorkerStable)) {
    if (Test-Path $workerArtifact) {
        Move-Item -Path $workerArtifact -Destination (Join-Path $BuildCache (Split-Path $workerArtifact -Leaf)) -Force
    }
}

Write-Host ""
Write-Host "Done. End-user download (one file):" -ForegroundColor Green
Write-Host "  dist\ApplyXAI-Desktop-Setup-v$ProductVersion.exe" -ForegroundColor Green
Write-Host "  dist\ApplyXAI-Desktop-Setup.exe (stable alias)" -ForegroundColor Green
Write-Host "Agent worker is inside the installer (not a separate download)." -ForegroundColor DarkGray
Write-Host "Build cache:    dist\.build-cache\agent-worker*.exe (developers only)" -ForegroundColor DarkGray
Write-Host "Dev launcher:   dist\ApplyXAI-Launch.bat (sets project root + starts unpacked app)" -ForegroundColor Green
