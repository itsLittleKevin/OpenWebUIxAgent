# Letta Memory Server Launcher
# Starts the Letta HTTP server for Open WebUI Tool Server integration

param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8888,
    [string]$OllamaUrl = "http://localhost:11434",
    [string]$Model = "huihui_ai/qwen3-abliterated:4b-v2",
    [switch]$BackgroundProcess = $false
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$servicesDir = Join-Path $projectRoot "services"

# Try project-level venv first, then services-level
$venvPath = Join-Path $projectRoot ".venv_letta"
if (-Not (Test-Path (Join-Path $venvPath "Scripts\python.exe"))) {
    $venvPath = Join-Path $servicesDir ".venv_letta"
}

$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"
$requirementsTxt = Join-Path $servicesDir "requirements_letta.txt"

# Check if venv exists, create if needed
if (-Not (Test-Path $pythonExe)) {
    Write-Host "Creating Python virtual environment at: $venvPath" -ForegroundColor Yellow
    python -m venv $venvPath
    
    if (-Not (Test-Path $pythonExe)) {
        Write-Host "Error: Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    & $pythonExe -m pip install --upgrade pip
    & $pythonExe -m pip install -r $requirementsTxt
    
    # Also install httpx for async HTTP client
    & $pythonExe -m pip install httpx
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Virtual environment created successfully" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          Letta Memory Server for Open WebUI                " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor White
Write-Host "  Host:       $HostAddress"
Write-Host "  Port:       $Port"
Write-Host "  Ollama:     $OllamaUrl"
Write-Host "  Model:      $Model"
Write-Host "  Python:     $pythonExe"
Write-Host ""

# Navigate to services directory
Push-Location $servicesDir

# Ensure data directory exists
$dataDir = "$projectRoot\data\letta"
if (-Not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
    Write-Host "Created data directory: $dataDir" -ForegroundColor Green
}

# Ensure logs directory exists
$logsDir = "$projectRoot\logs"
if (-Not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
    Write-Host "Created logs directory: $logsDir" -ForegroundColor Green
}

# Set environment variables
$env:OLLAMA_URL = $OllamaUrl
$env:LETTA_MODEL = $Model

Write-Host "Starting Letta Memory Server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Endpoints:" -ForegroundColor White
Write-Host "  API Root:   http://$HostAddress`:$Port" -ForegroundColor Yellow
Write-Host "  API Docs:   http://$HostAddress`:$Port/docs" -ForegroundColor Yellow
Write-Host "  Health:     http://$HostAddress`:$Port/health" -ForegroundColor Yellow
Write-Host "  Tools:      http://$HostAddress`:$Port/tools" -ForegroundColor Yellow
Write-Host ""
Write-Host "Open WebUI Integration:" -ForegroundColor White
Write-Host "  1. Go to Admin -> Settings -> Tools" -ForegroundColor Gray
Write-Host "  2. Click 'Add Tool Server'" -ForegroundColor Gray
Write-Host "  3. Enter URL: http://$HostAddress`:$Port" -ForegroundColor Gray
Write-Host "  4. Enable tools in model settings" -ForegroundColor Gray
Write-Host ""

if ($BackgroundProcess) {
    # Start in background
    Write-Host "Starting in background..." -ForegroundColor Green
    $logFile = "$logsDir\letta-memory.log"
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
        "Set-Location '$servicesDir'; `$env:OLLAMA_URL='$OllamaUrl'; `$env:LETTA_MODEL='$Model'; & '$venvActivate'; python memory_server.py $HostAddress $Port" `
        -WorkingDirectory $servicesDir `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError "$logsDir\letta-memory-error.log"
    
    Write-Host "Process started. Logs: $logFile" -ForegroundColor Green
    Write-Host ""
    Write-Host "To stop: taskkill /FI `"WINDOWTITLE eq *letta*`" /T" -ForegroundColor Gray
} else {
    # Start in foreground
    Write-Host "Starting in foreground (Ctrl+C to stop)..." -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Activate venv and run
    & $venvActivate
    $env:PYTHONPATH = $servicesDir
    python memory_server.py $HostAddress $Port
}

Pop-Location
