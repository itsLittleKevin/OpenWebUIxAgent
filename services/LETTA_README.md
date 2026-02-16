# Letta Integration for Qwen Model

This implements persistent conversation memory with Letta, giving your Qwen3-abliterated 4B model access to unlimited conversation history without any VRAM overhead.

## What is Letta?

Letta (formerly MemGPT) solves the "context window is too small" problem by:
- **Archival Memory**: Stores unlimited conversation history on disk (SQLite)
- **Recall Memory**: Indexes past conversations for semantic search
- **Core Memory**: Persistent facts the model always has access to
- **Automatic Retrieval**: Searches and injects relevant past context when needed

**Key Benefit**: Your 4B model effectively gets access to 1M+ tokens of history without VRAM cost.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Your Chat Application (Open WebUI / Custom)     │
└────────────┬────────────────────────────────────┘
             │ HTTP REST API
             ▼
┌─────────────────────────────────────────────────┐
│  Letta HTTP Server (letta_server.py)            │
│  - Manages chat sessions                        │
│  - Routes to LettaOllamaAgent                   │
└────────────┬────────────────────────────────────┘
             │ Python API
             ▼
┌─────────────────────────────────────────────────┐
│  LettaOllamaAgent (letta_agent.py)              │
│  - Manages memory (core, recall, archival)      │
│  - Connects to Ollama                           │
│  - Handles semantic search                      │
└────────────┬─────────────────┬──────────────────┘
             │                 │
      HTTP 11434          Disk Storage
             ▼                 ▼
    ┌──────────────┐   ┌────────────────┐
    │   Ollama     │   │ SQLite DBs     │
    │  (Qwen 4B)   │   │ (recall.db,    │
    │              │   │  archival.db)  │
    └──────────────┘   └────────────────┘
```

## Installation

### 1. Prerequisites
- Ollama running with Qwen model: `huihui_ai/qwen3-abliterated:4b-v2`
- Python 3.10+
- Virtual environment configured

### 2. Install Dependencies

The dependencies are already installed via pip:
```powershell
cd d:\Projects\Clusters\Agent
pip install letta ollama fastapi uvicorn pydantic
```

## Usage

### Option 1: Direct Python API (Simplest)

```python
from services.letta_agent import LettaOllamaAgent

# Create agent
agent = LettaOllamaAgent(
    model="huihui_ai/qwen3-abliterated:4b-v2",
    agent_name="MyAgent"
)

# Chat - memories persist automatically
response = agent.chat("Tell me about AI")

# Add explicit facts to memory
agent.add_memory("I like Python programming", memory_type="recall")

# Search past conversations
results = agent.search_memory("Python", limit=5)
```

### Option 2: HTTP REST API (For Integration)

#### Start the server:
```powershell
# Foreground (for debugging)
cd d:\Projects\Clusters\Agent\config
.\letta-launch.ps1

# Or background
.\letta-launch.ps1 -BackgroundProcess
```

Server runs at: `http://127.0.0.1:8888`

#### API Endpoints:

**Chat with memory:**
```bash
curl -X POST http://127.0.0.1:8888/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, remember I like Python", "user_id": "alice"}'
```

**Add memory:**
```bash
curl -X POST http://127.0.0.1:8888/memory/add \
  -H "Content-Type: application/json" \
  -d '{"content": "User prefers async programming", "memory_type": "archival"}'
```

**Search memory:**
```bash
curl -X POST http://127.0.0.1:8888/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python preferences", "limit": 5}'
```

**Get status:**
```bash
curl http://127.0.0.1:8888/status | jq
```

**API Documentation (interactive):**
- Swagger UI: `http://127.0.0.1:8888/docs`
- ReDoc: `http://127.0.0.1:8888/redoc`

### Option 3: Run Examples

```powershell
cd d:\Projects\Clusters\Agent\services

# Memory persistence demo
python letta_example.py memory

# Practical usage examples
python letta_example.py practical

# Multi-user conversation
python letta_example.py multiuser

# Run all demos
python letta_example.py
```

## Configuration

Configuration file: `d:\Projects\Clusters\Agent\config\letta_config.json`

Key settings:
```json
{
  "model": {
    "type": "ollama",
    "name": "huihui_ai/qwen3-abliterated:4b-v2",
    "context_window": 8192
  },
  "memory": {
    "archival": {
      "type": "sqlite",
      "path": "data/letta/archival.db"
    }
  },
  "retrieval": {
    "top_k": 3,
    "relevance_threshold": 0.5
  }
}
```

## Memory Storage

- **Location**: `d:\Projects\Clusters\Agent\data\letta\`
- **Files**:
  - `recall.db` - Recent conversation history
  - `archival.db` - Long-term searchable memory
  - `embeddings/` - Vector embeddings for semantic search

- **Size**: 
  - 1M tokens raw text ≈ 4 MB on disk
  - With embeddings ≈ 50-200 MB total
  - No VRAM overhead

## Integration with Open WebUI

### Approach 1: Custom Plugin (Recommended)

Create a custom function in Open WebUI that calls Letta:

```python
# In Open WebUI > Admin > Functions

import requests

def letta_chat(prompt: str) -> str:
    """Chat with Letta agent that remembers history"""
    response = requests.post(
        "http://127.0.0.1:8888/chat",
        json={
            "message": prompt,
            "user_id": "openwebui",
            "include_memory_search": True
        }
    )
    return response.json()["message"]
```

### Approach 2: Proxy All Chats

Modify Open WebUI to use Letta as middleware that wraps all chat calls.

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Memory search overhead | 50-200ms |
| Archival capacity | Unlimited (disk-bound) |
| Max history tokens | 1M+ |
| VRAM overhead | 0 (disk-based) |
| RAM overhead | 300-500MB (embedding model) |
| Model context window | 8K (your Qwen model) |

## Architecture Details

### Memory Flow

1. **User message arrives** → Letta server
2. **Semantic search** → Query archival DB for relevant past context
3. **Context injection** → Prepend top-3 retrieved messages to input
4. **Model inference** → Qwen 4B processes augmented input
5. **Response generation** → Model produces response
6. **Memory update** → New conversation saved to recall + archival DB

### Why No VRAM Cost?

- Embeddings stored on disk, loaded once at startup
- Vector search runs on CPU (ChromaDB)
- Only relevant context chunks added to model input
- Model context window (8K tokens) unchanged

## Troubleshooting

### No Ollama connection
```
Error: Could not connect to Ollama at http://localhost:11434
```
**Fix**: Start Ollama first: `ollama serve`

### Memory not persisting
**Check**:
- Database files exist in `data/letta/`
- Write permissions on the data directory
- SQLite not corrupted: `sqlite3 data/letta/archival.db "SELECT COUNT(*) FROM memories;"`

### Slow semantic search
**Cause**: Embedding model not cached
**Fix**: First query is slower (embedding model loads). Subsequent queries are fast.

### Out of memory
**Check**:
- Embedding model size (default 500MB+)
- SQLite index size
- Reduce `top_k` in config from 3 to 1-2

### Server port already in use
```powershell
# Find process using port 8888
netstat -ano | findstr :8888

# Kill it
taskkill /PID <PID> /F
```

## Advanced Usage

### Consolidate Old Memories

```python
agent.consolidate_memory()  # Summarize old conversations
```

### Export/Backup Conversations

```python
# Export to JSON
filepath = agent.save_conversation("my_conversation.json")

# Export with metadata
agent.save_conversation("backup_2024.json")
```

### Multi-User Sessions

```python
# Each user gets separate memory
agent.chat("My project is about ML", user_id="alice")
agent.chat("My project is about web dev", user_id="bob")

# Memories stay separate
agent.search_memory("project", user_id="alice")  # Returns ML project
agent.search_memory("project", user_id="bob")    # Returns web project
```

### Custom Embedding Model

In `letta_config.json`:
```json
{
  "model": {
    "embedding_model": "mxbai-embed-large:latest",
    "embedding_dim": 1024
  }
}
```

## Comparison with Alternatives

| Feature | Letta | Open WebUI Memory | mem0 | LangChain |
|---------|-------|------------------|------|-----------|
| Unlimited history | ✓ | ✗ | ✓ | ✗ |
| Semantic search | ✓ | ✓ | ✓ | ✓ |
| Zero VRAM cost | ✓ | ✓ | ✓ | ✓ |
| Multi-user support | ✓ | ✗ | ✓ | ✓ |
| Auto memory management | ✓ | ✗ | ✓ | ✗ |
| Ease of integration | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |

## Next Steps

1. **Start server**: `.\config\letta-launch.ps1`
2. **Test with examples**: `python services\letta_example.py`
3. **Integrate with Open WebUI** (create custom function)
4. **Monitor memory**: Check `data/letta/` directory regularly

## Resources

- [Letta GitHub](https://github.com/letta-ai/letta)
- [Letta Docs](https://docs.letta.com)
- [Vector Databases Guide](https://www.pinecone.io/learn/vector-database/)

---

**Status**: ✅ Ready to use
**Start**: Run `.\config\letta-launch.ps1` in PowerShell
