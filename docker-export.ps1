# ClusterX AI - Export all Docker images to a single .tar file
# Usage: .\docker-export.ps1
# Output: clusterx-images.tar (copy this + docker-compose.yml to target machine)

$images = @(
    "agent-ollama",
    "agent-gpt-sovits",
    "agent-backend",
    "agent-audio-router",
    "agent-letta"
)

Write-Host "=== ClusterX AI Docker Export ===" -ForegroundColor Cyan

# Check which images exist
$existing = @()
foreach ($img in $images) {
    $found = docker image inspect $img 2>$null
    if ($LASTEXITCODE -eq 0) {
        $size = docker image inspect $img --format '{{.Size}}' 2>$null
        $sizeMB = [math]::Round([long]$size / 1MB)
        Write-Host "  [OK] $img (${sizeMB} MB)" -ForegroundColor Green
        $existing += $img
    } else {
        Write-Host "  [SKIP] $img (not built)" -ForegroundColor Yellow
    }
}

if ($existing.Count -eq 0) {
    Write-Host "No images found. Run 'docker compose build' first." -ForegroundColor Red
    exit 1
}

$outFile = "clusterx-images.tar"
Write-Host "`nExporting $($existing.Count) images to $outFile ..." -ForegroundColor Cyan

docker save $existing -o $outFile

if ($LASTEXITCODE -eq 0) {
    $fileSize = [math]::Round((Get-Item $outFile).Length / 1GB, 2)
    Write-Host "`nDone! $outFile ($fileSize GB)" -ForegroundColor Green
    Write-Host "`nTo deploy on target machine:" -ForegroundColor Yellow
    Write-Host "  1. Copy $outFile and docker-compose.yml to the target" 
    Write-Host "  2. Run: docker load -i $outFile"
    Write-Host "  3. Run: docker compose up -d"
} else {
    Write-Host "Export failed!" -ForegroundColor Red
    exit 1
}
