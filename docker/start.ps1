# =============================================================================
# ClusterX AI - Docker Quick Start (Windows)
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host @"
╔════════════════════════════════════════════════════════════════╗
║           ClusterX AI - Docker Deployment                      ║
╚════════════════════════════════════════════════════════════════╝
"@

# Check for Docker
try {
    docker version | Out-Null
} catch {
    Write-Host "ERROR: Docker is not installed or not running. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check for NVIDIA GPU
$HasGPU = $false
try {
    nvidia-smi | Out-Null
    $HasGPU = $true
    Write-Host "✓ NVIDIA GPU detected" -ForegroundColor Green
} catch {
    Write-Host "⚠ No NVIDIA GPU detected. Using CPU-only mode." -ForegroundColor Yellow
}

if ($HasGPU) {
    $ComposeFile = "docker-compose.yml"
} else {
    $ComposeFile = "docker-compose.cpu.yml"
}

# Build frontend first
Write-Host ""
Write-Host "=== Step 1: Building Frontend ===" -ForegroundColor Cyan
Write-Host "This may take a few minutes..."

Push-Location open-webui
if (-not (Test-Path "node_modules")) {
    npm install --legacy-peer-deps
}
npm run build
Pop-Location

# Build Docker images
Write-Host ""
Write-Host "=== Step 2: Building Docker Images ===" -ForegroundColor Cyan
Write-Host "This may take 10-30 minutes depending on your internet speed..."

docker compose -f $ComposeFile build

# Start services
Write-Host ""
Write-Host "=== Step 3: Starting Services ===" -ForegroundColor Cyan
Write-Host "First startup will download AI models (~5GB)..."

docker compose -f $ComposeFile up -d

Write-Host @"

╔════════════════════════════════════════════════════════════════╗
║                    🚀 Startup Complete!                        ║
╠════════════════════════════════════════════════════════════════╣
║  Open WebUI:    http://localhost:8080                          ║
║  Ollama API:    http://localhost:11434                         ║
║  Memory Server: http://localhost:8888                          ║
"@

if ($HasGPU) {
    Write-Host "║  TTS API:       http://localhost:9880                          ║"
    Write-Host "║  Audio Router:  http://localhost:8765                          ║"
}

Write-Host @"
╚════════════════════════════════════════════════════════════════╝

First startup may take 5-10 minutes while models download.
Monitor progress with: docker compose logs -f

To stop: docker compose down
To restart: docker compose up -d
"@
