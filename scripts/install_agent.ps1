# ApplyXAI Agent Installer
# This script installs the ApplyXAI Agent on Windows

param(
    [Parameter(Mandatory=$false)]
    [string]$InstallPath = "$env:ProgramFiles\ApplyXAI\Agent",
    
    [Parameter(Mandatory=$false)]
    [switch]$CreateDesktopShortcut = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$AddToStartup = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$InstallGUI = $true
)

Write-Host "ApplyXAI Agent Installer" -ForegroundColor Cyan
Write-Host "=====================" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "This installer requires administrator privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    exit 1
}

# Create installation directory
Write-Host "Creating installation directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $InstallPath | Out-Null

# Determine which executable to install
$sourceDir = Join-Path $PSScriptRoot "..\dist"
if ($InstallGUI) {
    $sourceExe = Join-Path $sourceDir "ApplyXAI-Agent-GUI.exe"
    $exeName = "ApplyXAI-Agent-GUI.exe"
} else {
    $sourceExe = Join-Path $sourceDir "ApplyXAI-Agent.exe"
    $exeName = "ApplyXAI-Agent.exe"
}

# Check if source exists
if (-not (Test-Path $sourceExe)) {
    Write-Host "Error: Executable not found at $sourceExe" -ForegroundColor Red
    Write-Host "Please build the agent first using: .\scripts\build_agent.bat" -ForegroundColor Yellow
    exit 1
}

# Copy executable (single-file build)
Write-Host "Copying executable..." -ForegroundColor Yellow
Copy-Item -Path $sourceExe -Destination $InstallPath -Force

# Create Start Menu shortcut
Write-Host "Creating Start Menu shortcut..." -ForegroundColor Yellow
$startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\ApplyXAI Agent"
New-Item -ItemType Directory -Force -Path $startMenuPath | Out-Null

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$startMenuPath\ApplyXAI Agent.lnk")
$Shortcut.TargetPath = Join-Path $InstallPath $exeName
$Shortcut.WorkingDirectory = $InstallPath
$Shortcut.Description = "ApplyXAI Desktop Agent"
$Shortcut.Save()

# Create desktop shortcut if requested
if ($CreateDesktopShortcut) {
    Write-Host "Creating desktop shortcut..." -ForegroundColor Yellow
    $Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\ApplyXAI Agent.lnk")
    $Shortcut.TargetPath = Join-Path $InstallPath $exeName
    $Shortcut.WorkingDirectory = $InstallPath
    $Shortcut.Description = "ApplyXAI Desktop Agent"
    $Shortcut.Save()
}

# Add to Windows startup if requested
if ($AddToStartup) {
    Write-Host "Adding to Windows startup..." -ForegroundColor Yellow
    $startupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
    $Shortcut = $WshShell.CreateShortcut("$startupPath\ApplyXAI Agent.lnk")
    $Shortcut.TargetPath = Join-Path $InstallPath $exeName
    $Shortcut.WorkingDirectory = $InstallPath
    $Shortcut.Description = "ApplyXAI Desktop Agent"
    $Shortcut.Save()
}

# Create uninstall script
Write-Host "Creating uninstall script..." -ForegroundColor Yellow
$uninstallScript = @"
# ApplyXAI Agent Uninstaller
param()

Write-Host "Uninstalling ApplyXAI Agent..." -ForegroundColor Cyan

# Stop running agent
Write-Host "Stopping running agent..." -ForegroundColor Yellow
Get-Process -Name "ApplyXAI-Agent" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "ApplyXAI-Agent-GUI" -ErrorAction SilentlyContinue | Stop-Process -Force

# Remove shortcuts
Write-Host "Removing shortcuts..." -ForegroundColor Yellow
Remove-Item -Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\ApplyXAI Agent" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:USERPROFILE\Desktop\ApplyXAI Agent.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\ApplyXAI Agent.lnk" -Force -ErrorAction SilentlyContinue

# Remove installation directory
Write-Host "Removing installation directory..." -ForegroundColor Yellow
Remove-Item -Path "$InstallPath" -Recurse -Force

Write-Host "ApplyXAI Agent has been uninstalled." -ForegroundColor Green
"@
$uninstallScript | Out-File -FilePath "$InstallPath\uninstall.ps1" -Encoding UTF8

# Register uninstaller in Programs and Features (optional)
Write-Host "Registering in Programs and Features..." -ForegroundColor Yellow
$regPath = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ApplyXAI Agent"
New-Item -Path $regPath -Force | Out-Null
New-ItemProperty -Path $regPath -Name "DisplayName" -Value "ApplyXAI Agent" -Force | Out-Null
New-ItemProperty -Path $regPath -Name "DisplayVersion" -Value "1.0.0" -Force | Out-Null
New-ItemProperty -Path $regPath -Name "Publisher" -Value "ApplyXAI" -Force | Out-Null
New-ItemProperty -Path $regPath -Name "InstallLocation" -Value $InstallPath -Force | Out-Null
New-ItemProperty -Path $regPath -Name "UninstallString" -Value "powershell.exe -ExecutionPolicy Bypass -File `"$InstallPath\uninstall.ps1`"" -Force | Out-Null

# Create user data directory
Write-Host "Creating user data directory..." -ForegroundColor Yellow
$userDataPath = "$env:LOCALAPPDATA\ApplyXAI\agent"
New-Item -ItemType Directory -Force -Path $userDataPath | Out-Null

Write-Host ""
Write-Host "Installation completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Installation location: $InstallPath" -ForegroundColor Cyan
Write-Host "User data location: $userDataPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "To uninstall, run: $InstallPath\uninstall.ps1" -ForegroundColor Yellow
Write-Host "Or use Programs and Features in Control Panel." -ForegroundColor Yellow
Write-Host ""
Write-Host "The agent can be launched from the Start Menu." -ForegroundColor Cyan
if ($CreateDesktopShortcut) {
    Write-Host "A desktop shortcut has also been created." -ForegroundColor Cyan
}
if ($AddToStartup) {
    Write-Host "The agent will start automatically when you log in." -ForegroundColor Cyan
}
