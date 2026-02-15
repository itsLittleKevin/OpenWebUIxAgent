#!/usr/bin/env pwsh
<#
.SYNOPSIS
Comprehensive system health check for OpenWebUIxAgent

.DESCRIPTION
Verifies all services are running and responsive

.EXAMPLE
.\verify-system.ps1
#>

Write-Host "`n╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           OpenWebUIxAgent - System Verification             ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$services = @(
    @{
        name = "Ollama"
        port = 11434
        url = "http://localhost:11434/api/tags"
        critical = $true
        description = "Local LLM inference engine"
    },
    @{
        name = "Open WebUI Backend"
        port = 8080
        url = "http://localhost:8080/health"
        critical = $true
        description = "REST API and chat backend"
    },
    @{
        name = "Open WebUI Frontend"
        port = 5173
        url = "http://localhost:5173"
        critical = $true
        description = "Web user interface"
    },
    @{
        name = "GPT-SoVITS TTS"
        port = 9880
        url = "http://localhost:9880/"
        critical = $false
        description = "Voice synthesis service"
    },
    @{
        name = "Audio Router"
        port = 8765
        url = "http://localhost:8765/status"
        critical = $false
        description = "Audio dual-output routing"
    }
)

$results = @()
$allHealthy = $true

foreach ($service in $services) {
    $listening = (netstat -ano 2>$null | Select-String ":$($service.port)") -ne $null
    $responding = $false
    $statusCode = 0
    
    if ($listening) {
        try {
            $response = Invoke-WebRequest -Uri $service.url -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            $responding = $true
            $statusCode = $response.StatusCode
        } catch {
            $responding = $false
        }
    }
    
    $status = if ($responding) { 
        "✓ RUNNING"
    } elseif ($listening) {
        "⏳ STARTING"
    } else {
        "✗ NOT RUNNING"
    }
    
    $color = if ($responding) {
        "Green"
    } elseif ($listening) {
        "Yellow"
    } else {
        if ($service.critical) { "Red" } else { "Yellow" }
    }
    
    $results += @{
        name = $service.name
        status = $status
        color = $color
        critical = $service.critical
        responding = $responding
        listening = $listening
        port = $service.port
        description = $service.description
    }
    
    if ($service.critical -and -not $responding) {
        $allHealthy = $false
    }
}

# Display results
Write-Host "SERVICE STATUS" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray
foreach ($result in $results) {
    $statusDisplay = $result.status.PadRight(15)
    Write-Host "  " -NoNewline
    Write-Host $statusDisplay -ForegroundColor $result.color -NoNewline
    Write-Host "  $($result.name)" -NoNewline
    if (-not $result.responding -and -not $result.critical) {
        Write-Host " (optional, still starting...)" -ForegroundColor DarkGray
    } else {
        Write-Host ""
    }
    Write-Host "                 └─ Port $($result.port) | $($result.description)" -ForegroundColor DarkGray
}

Write-Host "`n" 

# Summary
if ($allHealthy) {
    Write-Host "✓ ALL CRITICAL SERVICES ARE RUNNING" -ForegroundColor Green
    Write-Host "  Ready to use! Open http://localhost:5173 in your browser" -ForegroundColor Green
} else {
    Write-Host "✗ SOME SERVICES ARE NOT RESPONDING" -ForegroundColor Red
    Write-Host "  Start services with: .\config\launch.ps1 -WithVoiceTTS -WithAudioRouter" -ForegroundColor Yellow
}

Write-Host ""

# Optional services status
$optionalRunning = ($results | Where-Object { -not $_.critical -and $_.responding } | Measure-Object).Count
$optionalTotal = ($results | Where-Object { -not $_.critical } | Measure-Object).Count

if ($optionalRunning -eq $optionalTotal) {
    Write-Host "✓ ALL OPTIONAL SERVICES RUNNING ($optionalRunning/$optionalTotal)" -ForegroundColor Green
    Write-Host "  • Voice TTS: GPT-SoVITS available" -ForegroundColor Green
    Write-Host "  • Audio routing: Dual-output (speakers + virtual cable) ready" -ForegroundColor Green
} elseif ($optionalRunning -gt 0) {
    Write-Host "⏳ SOME OPTIONAL SERVICES STARTING ($optionalRunning/$optionalTotal)" -ForegroundColor Yellow
} else {
    Write-Host "ℹ NO OPTIONAL SERVICES RUNNING ($optionalRunning/$optionalTotal)" -ForegroundColor Gray
    Write-Host "  To enable voice TTS and audio routing:" -ForegroundColor Gray
    Write-Host "  .\config\launch.ps1 -WithVoiceTTS -WithAudioRouter" -ForegroundColor Gray
}

# Configuration check
Write-Host "`nCONFIGURATION CHECKS" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray

$checks = @(
    @{ name = "GPT-SoVITS symlink"; path = "d:\Projects\Clusters\Agent\vendor\gpt-sovits" },
    @{ name = ".env file"; path = "d:\Projects\Clusters\Agent\config\.env" },
    @{ name = "Audio router script"; path = "d:\Projects\Clusters\Agent\config\audio-router-launch.ps1" }
)

foreach ($check in $checks) {
    $exists = Test-Path $check.path
    $icon = if ($exists) { "✓" } else { "✗" }
    $color = if ($exists) { "Green" } else { "Red" }
    Write-Host "  $icon " -ForegroundColor $color -NoNewline
    Write-Host "$($check.name)" -ForegroundColor $color
}

Write-Host "`nNEXT STEPS" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  1. Open Web UI:       http://localhost:5173" -ForegroundColor White
Write-Host "  2. Configure TTS:     Admin → Settings → Audio" -ForegroundColor White
Write-Host "  3. Configure VSeeFace: Select 'Cable Output' in audio input" -ForegroundColor White
Write-Host "  4. Test voice input:   Click 🎤 microphone and speak" -ForegroundColor White
Write-Host ""
Write-Host "  Full documentation: d:\Projects\Clusters\Agent\SETUP_COMPLETE.md" -ForegroundColor Gray
Write-Host ""
