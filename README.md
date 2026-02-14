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

- **This repo** (`OpenWebUIxAgent`) — agent-specific code, tools, services, configs
- **Fork** (`itsLittleKevin/open-webui`) — Open WebUI with VRM sidebar modifications

## Prerequisites

- [Ollama](https://ollama.com/) — local LLM inference
- [VSeeFace](https://www.vseeface.icu/) — VRM avatar renderer (Windows)
- [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) — audio routing for lip sync
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) — voice cloning TTS (optional)
- Node.js 18+, Python 3.11+

## Quick Start

```bash
# Clone with submodule
git clone --recursive https://github.com/itsLittleKevin/OpenWebUIxAgent.git

# Start Ollama
ollama serve
ollama pull qwen2.5:7b

# Start Open WebUI (dev mode)
cd open-webui
npm install
npm run dev

# In another terminal, start backend
cd open-webui/backend
pip install -r requirements.txt
bash start.sh  # or: uvicorn open_webui.main:app --host 0.0.0.0 --port 8080
```
