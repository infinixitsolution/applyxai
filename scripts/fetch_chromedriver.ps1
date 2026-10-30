# Download the pinned Windows x64 ChromeDriver into vendor/.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content (Join-Path $RepoRoot "vendor\CHROMEDRIVER_VERSION.txt") -TotalCount 1).Trim()
$OutWin64 = Join-Path $RepoRoot "vendor\chromedriver-win64.exe"
$OutLegacy = Join-Path $RepoRoot "vendor\chromedriver.exe"
$Zip = Join-Path $env:TEMP "chromedriver-win64.zip"
$Url = "https://storage.googleapis.com/chrome-for-testing-public/$Version/win64/chromedriver-win64.zip"
Write-Host "Downloading ChromeDriver $Version ..."
Invoke-WebRequest -Uri $Url -OutFile $Zip
$Extract = Join-Path $env:TEMP "chromedriver-win64"
if (Test-Path $Extract) { Remove-Item $Extract -Recurse -Force }
Expand-Archive -Path $Zip -DestinationPath $Extract -Force
$Bin = Get-ChildItem -Path $Extract -Filter chromedriver.exe -Recurse | Select-Object -First 1
if (-not $Bin) { throw "chromedriver.exe not found in archive" }
Copy-Item $Bin.FullName $OutWin64 -Force
Copy-Item $Bin.FullName $OutLegacy -Force
Write-Host "Wrote $OutWin64 (and $OutLegacy for older extraResources)"
