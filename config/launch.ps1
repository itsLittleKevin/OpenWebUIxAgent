<#
  OpenWebUIxAgent - Launch Script
  Starts: Ollama -> Backend (FastAPI) -> Frontend (SvelteKit) + GPT-SoVITS (TTS) + Letta Memory
  All services run in dedicated windows with unified terminal output for easy monitoring.

  Usage:
    .\config\launch.ps1                           # Start everything
    .\config\launch.ps1 -Stop                    # Kill all services
    .\config\launch.ps1 -BackendOnly             # Only Ollama + Backend
    .\config\launch.ps1 -FrontendOnly            # Only Frontend (assumes backend running)
    .\config\launch.ps1 -NoLetta                 # Skip Letta Memory Server
    .\config\launch.ps1 -NoTTS                   # Skip GPT-SoVITS
    .\config\launch.ps1 -NoAudioRouter           # Skip Audio Router
#>
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Stop,
    [switch]$NoLetta,
    [switch]$NoTTS,
    [switch]$NoAudioRouter
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot | Split-Path -Parent
$OpenWebUIDir = Join-Path $ProjectRoot "open-webui"
$BackendDir = Join-Path $OpenWebUIDir "backend"
$VenvActivate = Join-Path $BackendDir ".venv\Scripts\Activate.ps1"
$EnvFile = Join-Path $PSScriptRoot ".env"

# Window titles used to track spawned processes
$TitleBackend      = "OpenWebUIxAgent-Backend"
$TitleFrontend     = "OpenWebUIxAgent-Frontend"
$TitleGPTSoVITS    = "OpenWebUIxAgent-GPT-SoVITS"
$TitleAudioRouter  = "OpenWebUIxAgent-AudioRouter"
$TitleLetta        = "OpenWebUIxAgent-Letta"

# ── Helper: Force-kill processes and release ports ───────────
function Cleanup-Ports {
    param(
        [array]$Ports = @(11434, 8080, 5173, 5174, 9880, 8765, 8888),
        [bool]$Verbose = $true
    )
    
    $killed = 0
    foreach ($port in $Ports) {
        $process = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($process) {
            try {
                Stop-Process -Id $process.OwningProcess -Force -ErrorAction SilentlyContinue
                if ($Verbose) { Write-Host "  Killed process on port $port (PID: $($process.OwningProcess))" -ForegroundColor Gray }
                $killed++
            } catch { }
        }
    }
    
    # Kill service windows by title
    Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -in @($TitleBackend, $TitleFrontend, $TitleGPTSoVITS, $TitleAudioRouter, $TitleLetta)
    } | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        if ($Verbose) { Write-Host "  Killed window: $($_.MainWindowTitle)" -ForegroundColor Gray }
        $killed++
    }
    
    # Kill all Ollama processes (main + runner children)
    Get-Process -Name "ollama*" -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        if ($Verbose) { Write-Host "  Killed Ollama process: $($_.ProcessName) (PID $($_.Id))" -ForegroundColor Gray }
        $killed++
    }
    
    if ($killed -gt 0) {
        Write-Host "  Waiting for port release (TIME_WAIT)..." -ForegroundColor Gray
        Start-Sleep -Seconds 3
    }
    
    return $killed
}

# ── Stop mode ──────────────────────────────────────────────
if ($Stop) {
    Write-Host "Stopping services..." -ForegroundColor Yellow
    $count = Cleanup-Ports
    if ($count -eq 0) {
        Write-Host "  No services running." -ForegroundColor Gray
    } else {
        Write-Host "  Stopped $count process(es)" -ForegroundColor Green
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
            Write-Host "  $key = $val" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "WARNING: config/.env not found — copy from .env.example" -ForegroundColor Red
}

# ── Helper: build env export string for sub-shells ─────────
function Get-EnvExportBlock {
    $lines = @()
    foreach ($kv in $envVars.GetEnumerator()) {
        $lines += "`$env:$($kv.Key) = '$($kv.Value)'"
    }
    return ($lines -join "; ")
}

# ── Prerequisites check ───────────────────────────────────
function Test-Prerequisites {
    $ok = $true
    if (-not (Test-Path $VenvActivate)) {
        Write-Host "  ERROR: Python venv not found at $BackendDir\.venv" -ForegroundColor Red
        Write-Host "         Run: cd open-webui/backend; py -3.11 -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt" -ForegroundColor Yellow
        $ok = $false
    }
    if (-not (Test-Path (Join-Path $OpenWebUIDir "node_modules"))) {
        Write-Host "  ERROR: node_modules not found" -ForegroundColor Red
        Write-Host "         Run: cd open-webui; npm install --legacy-peer-deps" -ForegroundColor Yellow
        $ok = $false
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Write-Host "  ERROR: Node.js not found in PATH" -ForegroundColor Red
        $ok = $false
    }
    return $ok
}

Write-Host "=== Checking Prerequisites ===" -ForegroundColor Cyan
if (-not (Test-Prerequisites)) {
    Write-Host "`nFix the above errors and try again." -ForegroundColor Red
    return
}
Write-Host "  All prerequisites OK" -ForegroundColor Green

# ── Cleanup any stale processes ────────────────────────────
Write-Host "`n=== Cleaning up stale processes ===" -ForegroundColor Cyan
$cleaned = Cleanup-Ports -Verbose $false
if ($cleaned -gt 0) {
    Write-Host "  Cleaned up $cleaned stale process(es)" -ForegroundColor Green
} else {
    Write-Host "  No stale processes found" -ForegroundColor Green
}

# ── Ollama ─────────────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Host "`n=== Checking Ollama ===" -ForegroundColor Cyan
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:11434" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        Write-Host "  Ollama already running" -ForegroundColor Green
    } catch {
        Write-Host "  Starting Ollama..." -ForegroundColor Yellow
        $ollamaPath = (Get-Command ollama -ErrorAction SilentlyContinue).Source
        if (-not $ollamaPath) {
            $ollamaPath = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
        }
        if (Test-Path $ollamaPath) {
            # Set OLLAMA_KEEP_ALIVE so models unload from VRAM after idle timeout
            if ($envVars.ContainsKey("OLLAMA_KEEP_ALIVE")) {
                [System.Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", $envVars["OLLAMA_KEEP_ALIVE"], "Process")
            }
            Start-Process -FilePath $ollamaPath -ArgumentList "serve" -WindowStyle Hidden
            # Wait for Ollama to be ready (up to ~60s)
            $retries = 0
            $maxRetries = 20
            while ($retries -lt $maxRetries) {
                Start-Sleep -Seconds 3
                try {
                    $null = Invoke-WebRequest -Uri "http://localhost:11434" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
                    Write-Host "  Ollama started" -ForegroundColor Green
                    break
                } catch { $retries++ }
            }
            if ($retries -ge $maxRetries) {
                Write-Host "  WARNING: Ollama didn't respond after 60s" -ForegroundColor Red
            }
        } else {
            Write-Host "  WARNING: Ollama not found. Install: winget install Ollama.Ollama" -ForegroundColor Red
        }
    }

    # Check models
    try {
        $models = (Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 5).models
        if ($models.Count -eq 0) {
            Write-Host "  No models found. Run: ollama pull huihui_ai/qwen3-abliterated:4b-v2" -ForegroundColor Yellow
        } else {
            Write-Host "  Models: $($models.name -join ', ')" -ForegroundColor Green
        }
    } catch {
        Write-Host "  Could not query models" -ForegroundColor Yellow
    }
}

# ── Backend ────────────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Host "`n=== Starting Backend (port 8080) ===" -ForegroundColor Cyan

    # Kill existing backend window if any
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $TitleBackend } |
        ForEach-Object { Stop-Process -Id $_.Id -Force }

    $envBlock = Get-EnvExportBlock
    $backendCmd = @"
`$Host.UI.RawUI.WindowTitle = '$TitleBackend';
Set-Location '$BackendDir';
& '$VenvActivate';
$envBlock;
`$env:CORS_ALLOW_ORIGIN = 'http://localhost:5173;http://localhost:8080';
Write-Host 'Backend starting on http://localhost:8080 ...' -ForegroundColor Green;
python -m uvicorn open_webui.main:app --port 8080 --host 0.0.0.0 --forwarded-allow-ips='*' --reload --reload-exclude data;
Write-Host 'Backend exited. Press any key...' -ForegroundColor Red; `$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
    Write-Host "  Backend window opened" -ForegroundColor Green
}

# ── Frontend ───────────────────────────────────────────────
if (-not $BackendOnly) {
    Write-Host "`n=== Starting Frontend (port 5173) ===" -ForegroundColor Cyan

    # Kill existing frontend window if any
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $TitleFrontend } |
        ForEach-Object { Stop-Process -Id $_.Id -Force }

    $frontendCmd = @"
`$Host.UI.RawUI.WindowTitle = '$TitleFrontend';
Set-Location '$OpenWebUIDir';
Write-Host 'Frontend starting on http://localhost:5173 ...' -ForegroundColor Green;
npm run dev;
Write-Host 'Frontend exited. Press any key...' -ForegroundColor Red; `$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd
    Write-Host "  Frontend window opened" -ForegroundColor Green
}

# ── Wait for services ─────────────────────────────────────
Write-Host "`n=== Waiting for services... ===" -ForegroundColor Cyan

if (-not $FrontendOnly) {
    $retries = 0
    while ($retries -lt 30) {
        Start-Sleep -Seconds 2
        try {
            Invoke-RestMethod -Uri "http://localhost:8080/health" -Method Get -TimeoutSec 3 -ErrorAction Stop | Out-Null
            Write-Host "  Backend ready" -ForegroundColor Green
            break
        } catch { $retries++ }
    }
    if ($retries -ge 30) {
        Write-Host "  Backend not responding yet — check the Backend window for errors" -ForegroundColor Yellow
    }
}

if (-not $BackendOnly) {
    $retries = 0
    while ($retries -lt 20) {
        Start-Sleep -Seconds 2
        try {
            Invoke-WebRequest -Uri "http://localhost:5173" -Method Head -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop | Out-Null
            Write-Host "  Frontend ready" -ForegroundColor Green
            break
        } catch { $retries++ }
    }
    if ($retries -ge 20) {
        Write-Host "  Frontend not responding yet — check the Frontend window for errors" -ForegroundColor Yellow
    }
}

# ── GPT-SoVITS (TTS Engine) ───────────────────────────
if (-not $NoTTS) {
    Write-Host "`n=== Starting GPT-SoVITS (port 9880) ===" -ForegroundColor Cyan

    # Kill existing GPT-SoVITS window if any
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $TitleGPTSoVITS } |
        ForEach-Object { Stop-Process -Id $_.Id -Force }
    
    $GPTSoVITSDir = Join-Path $ProjectRoot "vendor\gpt-sovits"
    $VenvActivateTTS = Join-Path $GPTSoVITSDir "venv_tts\Scripts\Activate.ps1"

    if (Test-Path $VenvActivateTTS) {
        $envBlock = Get-EnvExportBlock
        $refAudioPath = Join-Path $GPTSoVITSDir "reference_audio\default_reference.wav"
        $refTextPath = Join-Path $GPTSoVITSDir "reference_audio\default_reference.txt"
        
        # Write a temporary launcher script with UTF-8 BOM encoding
        $tempScript = Join-Path $env:TEMP "gpt-sovits-launch-temp.ps1"
        
        $sovitsScript = @"
`$Host.UI.RawUI.WindowTitle = '$TitleGPTSoVITS'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
`$env:PYTHONIOENCODING = 'utf-8'
Set-Location '$GPTSoVITSDir'
& '$VenvActivateTTS'
$envBlock

# Read reference text directly with UTF-8 encoding at runtime
`$refText = 'hello'
if (Test-Path '$refTextPath') {
    `$refText = [System.IO.File]::ReadAllText('$refTextPath', [System.Text.Encoding]::UTF8).Trim()
}

Write-Host 'GPT-SoVITS starting on http://localhost:9880 ...' -ForegroundColor Green
Write-Host 'API endpoint: http://localhost:9880/tts (v2 streaming)' -ForegroundColor Green
python api_v2.py -a 0.0.0.0 -p 9880
Write-Host 'GPT-SoVITS exited. Press any key...' -ForegroundColor Red
`$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@
        
        [System.IO.File]::WriteAllText($tempScript, $sovitsScript, [System.Text.UTF8Encoding]::new($true))
        
        Start-Process powershell -ArgumentList "-NoExit", "-File", $tempScript
        Write-Host "  GPT-SoVITS window opened" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: GPT-SoVITS venv not found at $VenvActivateTTS" -ForegroundColor Red
    }
} else {
    Write-Host "`n=== GPT-SoVITS: Skipped (-NoTTS) ===" -ForegroundColor Gray
}

# ── Audio Router (for VMC lip sync) ────────────────────────
if (-not $NoAudioRouter) {
    Write-Host "`n=== Starting Audio Router (port 8765) ===" -ForegroundColor Cyan

    # Kill existing Audio Router window if any
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $TitleAudioRouter } |
        ForEach-Object { Stop-Process -Id $_.Id -Force }

    $ServicesDir = Join-Path $ProjectRoot "services"

    $routerCmd = @"
`$Host.UI.RawUI.WindowTitle = '$TitleAudioRouter';
Set-Location '$ServicesDir';
Write-Host 'Audio Router starting on http://localhost:8765 (VMC lip sync)...' -ForegroundColor Green;
python audio_router.py --serve --port 8765 --vmc-port 39540;
Write-Host 'Audio Router exited. Press any key...' -ForegroundColor Red; `$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $routerCmd
    Write-Host "  Audio Router window opened (VMC lip sync enabled)" -ForegroundColor Green
} else {
    Write-Host "`n=== Audio Router: Skipped (-NoAudioRouter) ===" -ForegroundColor Gray
}

# ── Letta Memory Server ────────────────────────────────────
if (-not $NoLetta) {
    Write-Host "`n=== Starting Letta Memory Server (port 8888) ===" -ForegroundColor Cyan

    # Kill existing Letta window if any
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $TitleLetta } |
        ForEach-Object { Stop-Process -Id $_.Id -Force }

    $ServicesDir = Join-Path $ProjectRoot "services"
    $LettaVenvPath = Join-Path $ProjectRoot ".venv_letta"
    if (-Not (Test-Path (Join-Path $LettaVenvPath "Scripts\python.exe"))) {
        $LettaVenvPath = Join-Path $ServicesDir ".venv_letta"
    }
    $LettaVenvActivate = Join-Path $LettaVenvPath "Scripts\Activate.ps1"
    
    if (Test-Path $LettaVenvActivate) {
        $lettaCmd = @"
`$Host.UI.RawUI.WindowTitle = '$TitleLetta';
Set-Location '$ServicesDir';
& '$LettaVenvActivate';
`$env:OLLAMA_URL = 'http://localhost:11434';
`$env:LETTA_MODEL = 'huihui_ai/qwen3-abliterated:4b-v2';
Write-Host 'Letta Memory Server starting on http://localhost:8888 ...' -ForegroundColor Green;
Write-Host 'Add as Tool Server in Open WebUI: Admin -> Settings -> Tools' -ForegroundColor Yellow;
python memory_server.py 127.0.0.1 8888;
Write-Host 'Letta exited. Press any key...' -ForegroundColor Red; `$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@

        Start-Process powershell -ArgumentList "-NoExit", "-Command", $lettaCmd
        Write-Host "  Letta Memory Server window opened" -ForegroundColor Green
    } else {
        Write-Host "  Letta venv not found. Run: cd config; .\letta-launch.ps1 (first time setup)" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n=== Letta Memory Server: Skipped (-NoLetta) ===" -ForegroundColor Gray
}

# ── Summary ────────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Ollama:      http://localhost:11434" -ForegroundColor White
Write-Host "  Backend:     http://localhost:8080" -ForegroundColor White
Write-Host "  Frontend:    http://localhost:5173" -ForegroundColor White
if (-not $NoTTS) {
    Write-Host "  GPT-SoVITS:  http://localhost:9880" -ForegroundColor White
}
if (-not $NoAudioRouter) {
    Write-Host "  AudioRouter: http://localhost:8765 (VMC lip sync)" -ForegroundColor White
}
if (-not $NoLetta) {
    Write-Host "  Letta:       http://localhost:8888 (Memory/Tools)" -ForegroundColor White
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services running in dedicated windows for clear logging:" -ForegroundColor Gray
Write-Host "  • Backend:     API server and audio processing" -ForegroundColor Gray
Write-Host "  • Frontend:    Web UI" -ForegroundColor Gray
if (-not $NoTTS) {
    Write-Host "  • GPT-SoVITS:  Voice synthesis" -ForegroundColor Gray
}
if (-not $NoAudioRouter) {
    Write-Host "  • AudioRouter: VMC/OSC lip sync for VRM" -ForegroundColor Gray
}
if (-not $NoLetta) {
    Write-Host "  • Letta:       Persistent memory for Open WebUI" -ForegroundColor Gray
}
Write-Host ""
Write-Host "To stop all: .\config\launch.ps1 -Stop" -ForegroundColor Gray
Write-Host "First time? Open http://localhost:5173 and create an admin account." -ForegroundColor Yellow

