# Stop duplicate ApplyXAI automation workers (then reopen ApplyXAI Desktop once).
$names = @("agent-worker", "ApplyXAI-Agent-GUI", "ApplyXAI-Agent", "chromedriver")
foreach ($n in $names) {
    Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Stopping $($_.ProcessName) (PID $($_.Id))..."
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "Done. Restart ApplyXAI Desktop only (one instance)."
