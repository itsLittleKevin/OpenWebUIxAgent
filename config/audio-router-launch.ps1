<#
  Audio Router Launch Script
  Starts audio routing service (playback with VMC lip sync for VSeeFace)
  
  Usage:
    .\config\audio-router-launch.ps1                                    # Start audio router
    .\config\audio-router-launch.ps1 -Stop                              # Stop audio router
    .\config\audio-router-launch.ps1 -ListDevices                       # Show available audio devices
    .\config\audio-router-launch.ps1 -Test                              # Play test tone
    .\config\audio-router-launch.ps1 -SpeakerDeviceId 46                # Use specific speaker device
#>
param(
    [switch]$Stop,
    [switch]$ListDevices,
    [switch]$Test,
    [switch]$NoWait,
    [int]$SpeakerDeviceId = -1,
    [int]$Port = 8765
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot | Split-Path -Parent
$ServicesDir = Join-Path $ProjectRoot "services"
$RouterScript = Join-Path $ServicesDir "audio_router.py"

# Window title to track process
$TitleAudioRouter = "OpenWebUIxAgent-AudioRouter"

# ── Stop mode ──────────────────────────────────────────────
if ($Stop) {
    Write-Host "Stopping Audio Router..." -ForegroundColor Yellow
    Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -eq $TitleAudioRouter
    } | ForEach-Object {
        Write-Host "  Stopping $($_.MainWindowTitle) (PID $($_.Id))" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force
    }
    Write-Host "Done." -ForegroundColor Green
    return
}

# ── List devices mode ──────────────────────────────────────
if ($ListDevices) {
    Write-Host "=== Available Audio Devices ===" -ForegroundColor Cyan
    $cmd = @("$RouterScript", "--list-devices")
    python @cmd
    return
}

# ── Test mode ──────────────────────────────────────────────
if ($Test) {
    Write-Host "=== Playing Test Tone ===" -ForegroundColor Cyan
    $cmd = @("$RouterScript", "--test")
    if ($SpeakerDeviceId -ge 0) { $cmd += "--speaker-device-id"; $cmd += $SpeakerDeviceId }
    python @cmd
    return
}

# ── Prerequisites check ───────────────────────────────────
Write-Host "=== Checking Prerequisites ===" -ForegroundColor Cyan

if (-not (Test-Path $RouterScript)) {
    Write-Host "  ERROR: audio_router.py not found at $RouterScript" -ForegroundColor Red
    return
}

Write-Host "  ✓ Venv found at: $BackendDir\.venv" -ForegroundColor Green
Write-Host "  ✓ Python executable: $PythonExe" -ForegroundColor Green
Write-Host "  ✓ Dependencies managed via requirements.txt" -ForegroundColor Green

# ── Start Audio Router ─────────────────────────────────────
Write-Host "`n=== Starting Audio Router ===" -ForegroundColor Cyan

# Kill existing window if any
Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $TitleAudioRouter } |
    ForEach-Object { Stop-Process -Id $_.Id -Force }

$pyArgs = @('audio_router.py', '--serve', '--port', $Port)
if ($SpeakerDeviceId -ge 0) {
    $pyArgs += '--speaker-device-id'
    $pyArgs += $SpeakerDeviceId
}

# Build command string for background process
$pyArgStr = ($pyArgs | ForEach-Object {
    if ($_ -match '^-' -or $_ -match '^\d+$') { $_ } else { "'$_'" }
}) -join ' '

$routerCmd = @"
`$Host.UI.RawUI.WindowTitle = '$TitleAudioRouter';
Set-Location '$ServicesDir';
Write-Host 'Audio Router initializing...' -ForegroundColor Green;
Write-Host 'API endpoint: http://localhost:$Port/play' -ForegroundColor Green;
python $pyArgStr;
Write-Host 'Audio Router exited. Press any key...' -ForegroundColor Red; `$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $routerCmd
Write-Host "  Audio Router window opened" -ForegroundColor Green

# ── Wait for service ───────────────────────────────────────
if (-not $NoWait) {
    Write-Host "`n=== Waiting for Audio Router... ===" -ForegroundColor Cyan
    
    $retries = 0
    $maxRetries = 10
    while ($retries -lt $maxRetries) {
        Start-Sleep -Seconds 1
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8765/status" `
                -Method GET `
                -TimeoutSec 2 `
                -ErrorAction Stop
            Write-Host "  Audio Router ready" -ForegroundColor Green
            break
        } catch {
            $retries++
        }
    }
    
    if ($retries -ge $maxRetries) {
        Write-Host "  Audio Router not responding (check window for errors)" -ForegroundColor Yellow
    }
}

# ── Summary ────────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Audio Router: http://localhost:$Port" -ForegroundColor White
Write-Host "  Speaker Device: $SpeakerDeviceId" -ForegroundColor White
Write-Host "  API:             /play-bytes, /status" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test the router: .\config\audio-router-launch.ps1 -ListDevices" -ForegroundColor Gray
Write-Host "To stop:         .\config\audio-router-launch.ps1 -Stop" -ForegroundColor Gray
