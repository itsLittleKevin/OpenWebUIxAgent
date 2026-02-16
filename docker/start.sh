#!/bin/bash
# =============================================================================
# ClusterX AI - Docker Quick Start
# =============================================================================

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           ClusterX AI - Docker Deployment                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check for Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check for NVIDIA GPU
HAS_GPU=false
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        HAS_GPU=true
        echo "✓ NVIDIA GPU detected"
    fi
fi

if [ "$HAS_GPU" = false ]; then
    echo "⚠ No NVIDIA GPU detected. Using CPU-only mode."
    COMPOSE_FILE="docker-compose.cpu.yml"
else
    COMPOSE_FILE="docker-compose.yml"
fi

# Build frontend first (needed for backend)
echo ""
echo "=== Step 1: Building Frontend ==="
echo "This may take a few minutes..."

cd open-webui
if [ ! -d "node_modules" ]; then
    npm install --legacy-peer-deps
fi
npm run build
cd ..

# Build and start containers
echo ""
echo "=== Step 2: Building Docker Images ==="
echo "This may take 10-30 minutes depending on your internet speed..."

docker compose -f "$COMPOSE_FILE" build

echo ""
echo "=== Step 3: Starting Services ==="
echo "First startup will download AI models (~5GB)..."

docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    🚀 Startup Complete!                        ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  Open WebUI:    http://localhost:8080                          ║"
echo "║  Ollama API:    http://localhost:11434                         ║"
echo "║  Memory Server: http://localhost:8888                          ║"
if [ "$HAS_GPU" = true ]; then
echo "║  TTS API:       http://localhost:9880                          ║"
echo "║  Audio Router:  http://localhost:8765                          ║"
fi
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "First startup may take 5-10 minutes while models download."
echo "Monitor progress with: docker compose logs -f"
echo ""
echo "To stop: docker compose down"
echo "To restart: docker compose up -d"
