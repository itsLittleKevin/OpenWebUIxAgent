<# 
  OpenWebUIxAgent - Launch Script
  Starts all required services for the agent system.
#>
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot | Split-Path -Parent
$OpenWebUIDir = Join-Path $ProjectRoot "open-webui"
$BackendDir = Join-Path $OpenWebUIDir "backend"
$VenvActivate = Join-Path $BackendDir ".venv\Scripts\Activate.ps1"

# Refresh PATH to pick up Ollama
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# --- Ollama ---
Write-Host "=== Checking Ollama ===" -ForegroundColor Cyan
$ollamaRunning = $false
try {
    $health = Invoke-RestMethod -Uri "http://localhost:11434" -Method Get -ErrorAction Stop
    $ollamaRunning = $true
    Write-Host "  Ollama is already running" -ForegroundColor Green
} catch {
    Write-Host "  Starting Ollama..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    try {
        Invoke-RestMethod -Uri "http://localhost:11434" -Method Get -ErrorAction Stop | Out-Null
        Write-Host "  Ollama started" -ForegroundColor Green
    } catch {
        Write-Host "  WARNING: Ollama failed to start. Is it installed?" -ForegroundColor Red
    }
}

# Check for models
$models = (Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get).models
if ($models.Count -eq 0) {
    Write-Host "  No models found. Pulling qwen2.5:7b..." -ForegroundColor Yellow
    & ollama pull qwen2.5:7b
} else {
    Write-Host "  Models available: $($models.name -join ', ')" -ForegroundColor Green
}

if ($FrontendOnly) { goto frontend }

# --- Backend ---
if (-not $FrontendOnly) {
    Write-Host "`n=== Starting Open WebUI Backend (port 8080) ===" -ForegroundColor Cyan
    $backendJob = Start-Job -ScriptBlock {
        param($BackendDir, $VenvActivate)
        Set-Location $BackendDir
        & $VenvActivate
        $env:CORS_ALLOW_ORIGIN = "http://localhost:5173;http://localhost:8080"
        python -m uvicorn open_webui.main:app --port 8080 --host 0.0.0.0 --forwarded-allow-ips="*" --reload
    } -ArgumentList $BackendDir, $VenvActivate
    Write-Host "  Backend starting (Job ID: $($backendJob.Id))..." -ForegroundColor Green
}

# --- Frontend ---
if (-not $BackendOnly) {
    Write-Host "`n=== Starting Open WebUI Frontend (port 5173) ===" -ForegroundColor Cyan
    $frontendJob = Start-Job -ScriptBlock {
        param($OpenWebUIDir)
        Set-Location $OpenWebUIDir
        npm run dev
    } -ArgumentList $OpenWebUIDir
    Write-Host "  Frontend starting (Job ID: $($frontendJob.Id))..." -ForegroundColor Green
}

# --- Wait ---
Write-Host "`n=== Services ===" -ForegroundColor Cyan
Write-Host "  Ollama:   http://localhost:11434" -ForegroundColor White
Write-Host "  Backend:  http://localhost:8080" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "`nPress Ctrl+C to stop all services." -ForegroundColor Yellow
Write-Host "First time? Open http://localhost:5173 and create an admin account." -ForegroundColor Yellow

try {
    while ($true) {
        Start-Sleep -Seconds 5
        # Check job health
        $jobs = Get-Job | Where-Object { $_.State -eq "Failed" }
        foreach ($j in $jobs) {
            Write-Host "  WARNING: Job $($j.Name) failed!" -ForegroundColor Red
            Receive-Job $j
        }
    }
} finally {
    Write-Host "`nStopping services..." -ForegroundColor Yellow
    Get-Job | Stop-Job
    Get-Job | Remove-Job
}
