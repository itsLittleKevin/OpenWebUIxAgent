# Docker Deployment Guide

Complete Docker setup for OpenWebUIxAgent with all services.

## Quick Start

```powershell
# Build all images (first time only)
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **Ollama** | 11434 | LLM inference (Qwen3, etc.) |
| **Open WebUI Backend** | 8080 | FastAPI backend |
| **Open WebUI Frontend** | 5173 | Vite web UI |
| **GPT-SoVITS** | 9880 | Text-to-speech synthesis |
| **Audio Router** | 8765 | Audio playback + VMC lip sync |
| **Letta Memory** | 8888 | Persistent memory service |

## Accessing Services

Once running:
- **Web UI**: http://localhost:5173
- **Backend API**: http://localhost:8080
- **Ollama API**: http://localhost:11434
- **TTS API**: http://localhost:9880
- **Audio Router API**: http://localhost:8765
- **Memory Server**: http://localhost:8888

## Volume Mounts

Data persists in named volumes:
- `ollama_data` - Ollama models and cache
- `webui_data` - Open WebUI database
- `sovits_models` - GPT-SoVITS models
- `letta_data` - Letta memory database

## Deployment to Another Machine

### Option 1: Export Images (Recommended for Large Setup)

```powershell
# On your machine:
docker-compose build
docker save openwebui-backend:latest | gzip > backend.tar.gz
docker save openwebui-frontend:latest | gzip > frontend.tar.gz
docker save gpt-sovits:latest | gzip > sovits.tar.gz
docker save audio-router:latest | gzip > audio-router.tar.gz
docker save letta:latest | gzip > letta.tar.gz

# Copy .tar.gz files to target machine
# Then on target machine:
docker load < backend.tar.gz
docker load < frontend.tar.gz
docker load < sovits.tar.gz
docker load < audio-router.tar.gz
docker load < letta.tar.gz

docker-compose up -d
```

### Option 2: Copy Entire Source & Rebuild

```powershell
# On target machine:
git clone <your-repo>
cd agent
docker-compose build
docker-compose up -d
```

## Environment Variables

Create `.env` file in project root (optional):

```env
OLLAMA_MODEL=huihui_ai/qwen3-abliterated:4b-v2
LETTA_MODEL=huihui_ai/qwen3-abliterated:4b-v2
CUDA_VISIBLE_DEVICES=0
```

## Troubleshooting

### Services won't start
```powershell
docker-compose logs <service-name>
```

### Rebuild specific service
```powershell
docker-compose build --no-cache <service-name>
docker-compose up -d <service-name>
```

### Clean everything (WARNING: deletes all volumes!)
```powershell
docker-compose down -v
```

### Test individual service
```powershell
# Test Ollama
curl http://localhost:11434/api/tags

# Test TTS
curl -X POST http://localhost:9880/tts

# Test Backend health
curl http://localhost:8080/health
```

## Notes

- All services auto-restart on failure (`restart: unless-stopped`)
- Frontend uses production build (not dev server)
- Models are downloaded on first startup
- Symlinked GPT-SoVITS is resolved during Docker build (no symlink issues)
- Audio output may need host device access on Linux (add to docker-compose if needed)

## First-Time Setup

1. Run `docker-compose up -d`
2. Wait for Ollama to pull models (~5-10 min depending on internet)
3. Open http://localhost:5173
4. Create admin account
5. Access all services via Web UI
