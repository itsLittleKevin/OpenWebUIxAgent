<#
  GPT-SoVITS Launch Script
  Starts GPT-SoVITS service with OpenAI API compatibility on port 9880
  
  Usage:
    .\config\gpt-sovits-launch.ps1              # Start GPT-SoVITS
    .\config\gpt-sovits-launch.ps1 -Stop        # Stop GPT-SoVITS
    .\config\gpt-sovits-launch.ps1 -NoWait      # Start without waiting for health check
#>
param(
    [switch]$Stop,
    [switch]$NoWait
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot | Split-Path -Parent
$GPTSoVITSDir = Join-Path $ProjectRoot "vendor\gpt-sovits"
$VenvActivate = Join-Path $GPTSoVITSDir "venv_tts\Scripts\Activate.ps1"
$EnvFile = Join-Path $PSScriptRoot ".env"

# Window title to track process
$TitleGPTSoVITS = "OpenWebUIxAgent-GPT-SoVITS"

# ── Stop mode ──────────────────────────────────────────────
if ($Stop) {
    Write-Host "Stopping GPT-SoVITS..." -ForegroundColor Yellow
    Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -eq $TitleGPTSoVITS
    } | ForEach-Object {
        Write-Host "  Stopping $($_.MainWindowTitle) (PID $($_.Id))" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force
    }
    Write-Host "Done." -ForegroundColor Green
    return
}

# ── Refresh PATH ───────────────────────────────────────────
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path","User")

# ── Load .env ──────────────────────────────────────────────
$envVars = @{}
if (Test-Path $EnvFile) {
    Write-Host "=== Loading .env ===" -ForegroundColor Cyan
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+?)\s*=\s*(.+?)\s*$') {
            $key = $Matches[1].Trim()
            $val = $Matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
            $envVars[$key] = $val
            Write-Host "  $key = ***" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "WARNING: config/.env not found" -ForegroundColor Yellow
}

# ── Helper: build env export string ────────────────────────
function Get-EnvExportBlock {
    $lines = @()
    foreach ($kv in $envVars.GetEnumerator()) {
        $lines += "`$env:$($kv.Key) = '$($kv.Value)'"
    }
    return ($lines -join "; ")
}

# ── Prerequisites check ───────────────────────────────────
Write-Host "=== Checking Prerequisites ===" -ForegroundColor Cyan

if (-not (Test-Path $GPTSoVITSDir)) {
    Write-Host "  ERROR: GPT-SoVITS not found at $GPTSoVITSDir" -ForegroundColor Red
    Write-Host "         Did symlink fail? Check: " -ForegroundColor Yellow
    Write-Host "         New-Item -ItemType SymbolicLink -Path `"d:\Projects\Clusters\Agent\vendor\gpt-sovits`" -Target `"d:\Projects\Vocal10n\vendor\gpt-sovits`"" -ForegroundColor Yellow
    return
}

if (-not (Test-Path $VenvActivate)) {
    Write-Host "  ERROR: venv_tts not found at $GPTSoVITSDir\venv_tts" -ForegroundColor Red
    Write-Host "         Run setup first: " -ForegroundColor Yellow
    Write-Host "         .\gpt-sovits-setup.bat" -ForegroundColor Yellow
    return
}

Write-Host "  ✓ GPT-SoVITS directory found" -ForegroundColor Green
Write-Host "  ✓ venv_tts environment found" -ForegroundColor Green

# ── Start GPT-SoVITS ───────────────────────────────────────
Write-Host "`n=== Starting GPT-SoVITS (port 9880) ===" -ForegroundColor Cyan

# Kill existing window if any
Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $TitleGPTSoVITS } |
    ForEach-Object { Stop-Process -Id $_.Id -Force }

$envBlock = Get-EnvExportBlock
$refAudioPath = Join-Path $GPTSoVITSDir "reference_audio\default_reference.wav"
$refTextPath = Join-Path $GPTSoVITSDir "reference_audio\default_reference.txt"

# Write a temporary launcher script with UTF-8 BOM encoding
# (passing Chinese text via Start-Process -Command corrupts encoding)
$tempScript = Join-Path $env:TEMP "gpt-sovits-launch-temp.ps1"

$sovitsScript = @"
`$Host.UI.RawUI.WindowTitle = '$TitleGPTSoVITS'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
`$env:PYTHONIOENCODING = 'utf-8'
Set-Location '$GPTSoVITSDir'
& '$VenvActivate'
$envBlock

# Read reference text directly with UTF-8 encoding
`$refText = ''
if (Test-Path '$refTextPath') {
    `$refText = [System.IO.File]::ReadAllText('$refTextPath', [System.Text.Encoding]::UTF8).Trim()
} else {
    `$refText = 'hello'
}

Write-Host 'GPT-SoVITS starting on http://localhost:9880 ...' -ForegroundColor Green
Write-Host 'API endpoint: http://localhost:9880/tts (v2 streaming)' -ForegroundColor Green
python api_v2.py -a 0.0.0.0 -p 9880
Write-Host 'GPT-SoVITS exited. Press any key...' -ForegroundColor Red
`$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@

# Save with UTF-8 BOM so PowerShell reads it correctly
[System.IO.File]::WriteAllText($tempScript, $sovitsScript, [System.Text.UTF8Encoding]::new($true))

Start-Process powershell -ArgumentList "-NoExit", "-File", $tempScript
Write-Host "  GPT-SoVITS window opened" -ForegroundColor Green

# ── Wait for service to be ready ────────────────────────────
if (-not $NoWait) {
    Write-Host "`n=== Waiting for GPT-SoVITS... ===" -ForegroundColor Cyan
    
    $retries = 0
    $maxRetries = 30
    while ($retries -lt $maxRetries) {
        Start-Sleep -Seconds 2
        try {
            # v2 API: use /tts endpoint with required params; 400 = server up but bad params = OK
            $response = Invoke-WebRequest -Uri "http://localhost:9880/tts?text=test&text_lang=en&ref_audio_path=x&prompt_lang=en" `
                -Method GET `
                -TimeoutSec 3 `
                -ErrorAction Stop
            Write-Host "  GPT-SoVITS ready" -ForegroundColor Green
            break
        } catch {
            $statusCode = $_.Exception.Response.StatusCode.value__
            if ($statusCode -eq 400) {
                # Server is up, just bad params - that's fine for health check
                Write-Host "  GPT-SoVITS ready" -ForegroundColor Green
                break
            }
            $retries++
            if ($retries -eq 10) {
                Write-Host "  Still waiting for GPT-SoVITS to initialize... (this can take 20-30s)" -ForegroundColor Yellow
            }
        }
    }
    
    if ($retries -ge $maxRetries) {
        Write-Host "  GPT-SoVITS not responding after $(($maxRetries * 2))s" -ForegroundColor Yellow
        Write-Host "  Check the GPT-SoVITS window for startup errors" -ForegroundColor Yellow
        Write-Host "  (First startup may take longer due to model loading)" -ForegroundColor Gray
    }
    
    # ── Warm-up during initialization ────────────────────────────
    if ($retries -lt $maxRetries) {
        Write-Host "`n=== Warming up GPT-SoVITS (pre-loading models)... ===" -ForegroundColor Cyan
        try {
            # v2 API warmup with reference audio
            $warmupPayload = @{
                text = "Warming up models."
                text_lang = "en"
                ref_audio_path = $refAudioPath
                prompt_text = "hello"
                prompt_lang = "en"
                streaming_mode = 0
            } | ConvertTo-Json
            
            $warmupResponse = Invoke-RestMethod -Uri "http://localhost:9880/tts" `
                -Method POST `
                -Headers @{ "Content-Type" = "application/json" } `
                -Body $warmupPayload `
                -TimeoutSec 60 `
                -ErrorAction Stop
            
            Write-Host "  Warm-up complete - models pre-loaded for faster synthesis" -ForegroundColor Green
        } catch {
            Write-Host "  Warm-up request completed (may have been processed in background)" -ForegroundColor Gray
        }
    }
}

# ── Summary ────────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  GPT-SoVITS: http://localhost:9880" -ForegroundColor White
Write-Host "  API:        POST /tts (v2 streaming)" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop:    .\config\gpt-sovits-launch.ps1 -Stop" -ForegroundColor Gray
Write-Host "Integration: Open WebUI Admin > Audio > TTS" -ForegroundColor Yellow
Write-Host "            Select 'GPT-SoVITS (Local)'" -ForegroundColor Yellow
