# OpenWebUIxAgent

Local personal AI agent with VRM avatar, built on an Open WebUI fork.

## Structure

```
├── open-webui/          ← Open WebUI fork (git submodule) — VRM sidebar UI mods
├── tools/               ← Custom tools/functions loaded into Open WebUI
├── services/            ← Helper services (VMC controller, audio routing)
├── config/              ← Environment configs, launch scripts
└── plan.prompt.md       ← Project plan (gitignored)
```

## Repos

- **This repo** ([OpenWebUIxAgent](https://github.com/itsLittleKevin/OpenWebUIxAgent)) — agent-specific code, tools, services, configs
- **Fork** ([itsLittleKevin/open-webui](https://github.com/itsLittleKevin/open-webui)) — Open WebUI with VRM sidebar modifications

## Prerequisites

- [Ollama](https://ollama.com/) — local LLM inference
- [Node.js](https://nodejs.org/) 18+ (tested with 22.x)
- [Python](https://www.python.org/) 3.11 (3.13 not compatible with some deps)
- [VSeeFace](https://www.vseeface.icu/) — VRM avatar renderer (Windows only, Phase 2)
- [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) — audio routing for lip sync (Phase 4)
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) — voice cloning TTS (optional, Phase 4)

## Quick Start

```powershell
# Clone with submodule
git clone --recursive https://github.com/itsLittleKevin/OpenWebUIxAgent.git
cd OpenWebUIxAgent

# Install Ollama (if not already installed)
winget install Ollama.Ollama
ollama pull huihui_ai/qwen3-abliterated:4b-v2

# Frontend setup
cd open-webui
npm install --legacy-peer-deps

# Backend setup (Python 3.11 required)
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Start backend (from open-webui/backend/, venv activated)
$env:CORS_ALLOW_ORIGIN = "http://localhost:5173;http://localhost:8080"
python -m uvicorn open_webui.main:app --port 8080 --host 0.0.0.0 --forwarded-allow-ips="*" --reload

# Start frontend (from open-webui/, in a separate terminal)
npm run dev
```

Open http://localhost:5173 and create an admin account on first launch.

## Configuration (after first login)

### STT (Speech-to-Text)
Admin > Settings > Audio > STT Engine: **Whisper (Local)**
- Model: `small.en` (or `base` for lower VRAM)
- Compute Type: `int8`
- VAD Filter: Enabled

### TTS (Text-to-Speech)
User Settings > Audio > TTS: **Kokoro.js (Browser)**
- Runs in-browser via WebGPU/WASM, no server VRAM needed
- First use downloads the 82M ONNX model

### Ollama
Auto-detected at `http://localhost:11434`. Verify in Admin > Settings > Connections.
