# ClusterX AI - Docker Deployment Guide

Complete Docker deployment for ClusterX AI with all services: VRM avatars, TTS, persistent memory, and local LLM.

## ⚡ Quick Start

### Windows (PowerShell)
```powershell
cd docker
.\start.ps1
```

### Linux/macOS (Bash)
```bash
cd docker
chmod +x start.sh
./start.sh
```

### Manual Start
```bash
# Build frontend first
cd open-webui && npm install --legacy-peer-deps && npm run build && cd ..

# Start with GPU support
docker compose up -d

# Or for CPU-only mode
docker compose -f docker-compose.cpu.yml up -d
```

---

## 🛠 Services Overview

| Service | Port | Container Name | Description |
|---------|------|----------------|-------------|
| **Open WebUI** | 8080 | clusterx-backend | Main web interface + API |
| **Ollama** | 11434 | clusterx-ollama | Local LLM server (Qwen3) |
| **Memory Server** | 8888 | clusterx-memory | Letta persistent memory |
| **GPT-SoVITS** | 9880 | clusterx-tts | Text-to-speech (GPU only) |
| **Audio Router** | 8765 | clusterx-audio | TTS → VMC lip sync bridge |

---

## 📦 What's Included

### AI Models (Auto-downloaded on first start)
- `huihui_ai/qwen3-abliterated:4b-v2` - 4.3GB chat model
- `nomic-embed-text:latest` - 274MB embedding model

### Features
- ✅ VRM Avatar with blur gradient overlay
- ✅ Arm pose slider (0-90°)
- ✅ Gamma/exposure correction
- ✅ Face tracking support (VMC/OSC)
- ✅ Text-to-speech with lip sync
- ✅ Persistent conversation memory
- ✅ Custom branding (ClusterX AI)
- ✅ Update notification customization

---

## 💾 Data Persistence

All data is stored in Docker volumes:

| Volume | Purpose | Typical Size |
|--------|---------|--------------|
| `ollama_data` | AI models | ~5GB |
| `webui_data` | User settings, chats | ~100MB |
| `webui_uploads` | VRM models, uploaded files | varies |
| `letta_data` | Conversation memory | ~50MB |
| `sovits_models` | TTS voice models | ~2GB |
| `sovits_outputs` | Generated audio cache | varies |

### Backup Volumes
```bash
# Backup all data
docker run --rm -v clusterx-network_ollama_data:/data -v $(pwd):/backup alpine tar cvf /backup/ollama_backup.tar /data

# Restore
docker run --rm -v clusterx-network_ollama_data:/data -v $(pwd):/backup alpine tar xvf /backup/ollama_backup.tar
```

---

## 🖥 System Requirements

### Minimum (CPU-only mode)
- RAM: 16GB
- Storage: 20GB free
- Docker Desktop

### Recommended (GPU mode)
- RAM: 32GB
- Storage: 50GB free
- NVIDIA GPU with 8GB+ VRAM
- NVIDIA Container Toolkit

### Check GPU Support
```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

---

## 🔧 Common Commands

```bash
# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f ollama

# Stop all services
docker compose down

# Stop and remove volumes (⚠️ deletes all data)
docker compose down -v

# Restart a single service
docker compose restart backend

# Rebuild after code changes
docker compose build --no-cache
docker compose up -d

# Shell into a container
docker exec -it clusterx-backend bash
```

---

## 🌐 Accessing Services

Once running, open your browser:

| Service | URL |
|---------|-----|
| **Web UI** | http://localhost:8080 |
| **Ollama API** | http://localhost:11434 |
| **Memory API** | http://localhost:8888 |
| **TTS API** | http://localhost:9880 |
| **Audio API** | http://localhost:8765 |

---

## 🚀 Deploy to Another Machine

### Option 1: Export Images (Recommended)
```bash
# On source machine - save images
docker save clusterx-ai | gzip > clusterx-ai.tar.gz

# Copy to target machine
scp clusterx-ai.tar.gz user@target:/path/

# On target machine - load images
docker load < clusterx-ai.tar.gz
docker compose up -d
```

### Option 2: Build from Source
```bash
git clone https://github.com/itsLittleKevin/OpenWebUIxAgent.git
cd OpenWebUIxAgent
git submodule update --init --recursive
cd docker && ./start.sh
```

### Option 3: Docker Registry
```bash
# Tag and push to registry
docker tag clusterx-backend:latest your-registry.com/clusterx-backend:latest
docker push your-registry.com/clusterx-backend:latest

# Pull on target
docker pull your-registry.com/clusterx-backend:latest
```

---

## ⚠️ Troubleshooting

### Models not downloading
```bash
# Check Ollama logs
docker compose logs ollama

# Manually pull models
docker exec -it clusterx-ollama ollama pull huihui_ai/qwen3-abliterated:4b-v2
```

### GPU not detected
```bash
# Verify NVIDIA runtime
docker info | grep -i nvidia

# Install NVIDIA Container Toolkit
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
```

### Backend fails to connect to Ollama
```bash
# Check if Ollama is healthy
docker compose ps
docker exec -it clusterx-backend curl http://ollama:11434/api/tags
```

### Out of disk space
```bash
# Clean up Docker
docker system prune -a
docker volume prune
```

---

## 📝 Environment Variables

Key environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBUI_NAME` | ClusterX AI | App name in UI |
| `OLLAMA_BASE_URL` | http://ollama:11434 | Ollama server URL |
| `LETTA_MODEL` | qwen3-abliterated:4b-v2 | Memory agent model |
| `OLLAMA_PRELOAD_MODELS` | (see compose) | Models to pre-download |

---

## 📄 File Structure

```
├── docker/
│   ├── start.sh               # Linux/macOS startup script
│   ├── start.ps1              # Windows startup script
│   └── ollama-entrypoint.sh   # Ollama model preloader
├── docker-compose.yml         # Full stack (GPU)
├── docker-compose.cpu.yml     # CPU-only stack
├── Dockerfile.backend         # Open WebUI backend
├── Dockerfile.frontend        # Frontend builder
├── Dockerfile.ollama          # Custom Ollama with preload
├── Dockerfile.letta           # Memory server
├── Dockerfile.audio-router    # Audio/VMC bridge
└── .dockerignore              # Build exclusions
```

---

## 🔄 Updates

To update after pulling new changes:
```bash
git pull
git submodule update --remote
cd open-webui && npm install && npm run build && cd ..
docker compose build --no-cache
docker compose up -d
```
