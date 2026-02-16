# Letta + Open WebUI Integration Guide

Connect Letta's persistent memory to Open WebUI for unlimited conversation history with your Qwen model.

## Quick Start

### 1. Start Letta Server

In PowerShell:
```powershell
cd d:\Projects\Clusters\Agent\config
.\letta-launch.ps1
```

Server will be available at: `http://127.0.0.1:8888`

### 2. Test Letta Connection

```bash
# Check health
curl http://127.0.0.1:8888/health

# View API docs
# Open browser: http://127.0.0.1:8888/docs
```

### 3. Integrate with Open WebUI

Choose one of the integration methods below.

---

## Integration Method 1: Custom Chat Function (Recommended)

This method sends all Open WebUI chats through Letta automatically.

### Steps:

1. Open Open WebUI in browser (usually `http://localhost:3000`)
2. Go to **Admin Panel** → **Functions**
3. Create new function with:
   - **Name**: `letta_memory_chat`
   - **Type**: `Chat`
4. Paste this code:

```python
"""
Letta Memory-Enhanced Chat Function

Wraps your chat with Letta's persistent memory.
All conversations are automatically: saved, indexed, and searchable.
"""

import requests
import json
from typing import Optional

def letta_memory_chat(prompt: str, model: str = None, **kwargs) -> str:
    """
    Chat with Letta agent that remembers all history.
    
    Args:
        prompt: User message
        model: Model name (ignored, uses Qwen internally)
        **kwargs: Additional OpenAI-compatible parameters
    
    Returns:
        Agent response with memory-aware context
    """
    
    LETTA_API_URL = "http://127.0.0.1:8888"
    
    try:
        # Send to Letta which manages memory automatically
        response = requests.post(
            f"{LETTA_API_URL}/chat",
            json={
                "message": prompt,
                "user_id": kwargs.get("user_id", "openwebui"),
                "include_memory_search": True
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()["message"]
        else:
            return f"Error: Letta service returned {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Letta server. Start with: .\\config\\letta-launch.ps1"
    except Exception as e:
        return f"Error: {str(e)}"


# For Open WebUI compatibility
async def process_stream(prompt: str, **kwargs):
    """Streaming version (if needed)"""
    response = letta_memory_chat(prompt, **kwargs)
    yield response
```

5. Save the function
6. In chat settings, select `letta_memory_chat` as the function to use

**Result**: All your chats now go through Letta!

---

## Integration Method 2: Langchain + Open WebUI

For more advanced integration with additional OpenAI compatibility.

### Create wrapper in services:

File: `d:\Projects\Clusters\Agent\services\openwebui_letta_bridge.py`

```python
"""
Bridge between Open WebUI and Letta Agent

Acts as a compatibility layer to make Letta work seamlessly with Open WebUI's
OpenAI-compatible interface.
"""

from typing import Iterator, Optional
import requests
from letta_agent import LettaOllamaAgent

class OpenWebUILettaBridge:
    """Bridges Open WebUI chat requests to Letta agent."""
    
    def __init__(self):
        self.agent = LettaOllamaAgent(
            model="huihui_ai/qwen3-abliterated:4b-v2"
        )
    
    def chat_completion(
        self,
        messages: list,
        model: str = None,
        temperature: float = 0.7,
        **kwargs
    ) -> dict:
        """
        OpenAI-compatible chat completion endpoint.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (ignored)
            temperature: Temperature parameter
            
        Returns:
            OpenAI-compatible response
        """
        
        # Extract last user message
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        
        if not user_message:
            return {
                "choices": [{"message": {"role": "assistant", "content": "No message provided"}}]
            }
        
        # Get response from Letta (with memory)
        response_text = self.agent.chat(user_message)
        
        # Return in OpenAI format
        return {
            "id": "letta-" + str(int(__import__('time').time())),
            "model": "huihui_ai/qwen3-abliterated:4b-v2",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ]
        }

# Global instance
_bridge = None

def get_bridge():
    global _bridge
    if _bridge is None:
        _bridge = OpenWebUILettaBridge()
    return _bridge
```

---

## Integration Method 3: Manual REST API Calls

For advanced users who want fine-grained control.

### In your Open WebUI function:

```python
import requests

def custom_letta_chat(prompt: str, search_history: bool = True, **kwargs) -> str:
    """Multi-step Letta integration with explicit control."""
    
    LETTA_BASE = "http://127.0.0.1:8888"
    
    # Step 1: Search relevant past conversations (optional)
    if search_history:
        search_response = requests.post(
            f"{LETTA_BASE}/memory/search",
            json={"query": prompt, "limit": 3}
        )
        
        if search_response.status_code == 200:
            relevant_memories = search_response.json()["results"]
            if relevant_memories:
                memory_context = "\n".join([
                    f"- {m.get('text', '')}" 
                    for m in relevant_memories
                ])
                augmented_prompt = (
                    f"Relevant past context:\n{memory_context}\n\n"
                    f"Current question: {prompt}"
                )
            else:
                augmented_prompt = prompt
        else:
            augmented_prompt = prompt
    else:
        augmented_prompt = prompt
    
    # Step 2: Send chat with augmented context
    chat_response = requests.post(
        f"{LETTA_BASE}/chat",
        json={
            "message": augmented_prompt,
            "user_id": kwargs.get("user_id", "openwebui")
        }
    )
    
    if chat_response.status_code == 200:
        return chat_response.json()["message"]
    else:
        return "Error communicating with Letta"

# This function will be called by Open WebUI
def process(prompt: str, **kwargs) -> str:
    return custom_letta_chat(prompt, **kwargs)
```

---

## Integration Method 4: As System Prompt

Simplest approach - use Letta as a context provider.

### In Open WebUI System Prompt:

```markdown
You are an AI assistant with access to a persistent memory system.
When the user asks about something you might have discussed before,
search your memory for relevant context before responding.

[System message generation from Letta memory would go here]
```

Then in your function:

```python
import requests

def get_memory_context(query: str) -> str:
    """Get relevant memory for system context."""
    response = requests.post(
        "http://127.0.0.1:8888/memory/search",
        json={"query": query, "limit": 2}
    )
    
    if response.status_code == 200:
        results = response.json()["results"]
        if results:
            return "Relevant context:\n" + "\n".join([
                f"• {r.get('text', '')}" for r in results
            ])
    
    return ""

def augment_system_prompt(original_prompt: str, user_query: str) -> str:
    """Add memory context to system prompt."""
    memory_context = get_memory_context(user_query)
    return original_prompt + "\n\n" + memory_context
```

---

## Monitoring & Debugging

### Check Letta Server Status

```bash
# Health check
curl http://127.0.0.1:8888/health

# Get agent status
curl http://127.0.0.1:8888/status | jq

# View API documentation
# Browser: http://127.0.0.1:8888/docs
```

### View Memory Contents

```bash
# Search for specific topics
curl -X POST http://127.0.0.1:8888/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "python", "limit": 10}'
```

### View Database Files

```powershell
# List Letta data directory
dir d:\Projects\Clusters\Agent\data\letta\

# Check database size
(Get-Item d:\Projects\Clusters\Agent\data\letta\archival.db).Length
```

### Tail Server Logs

```powershell
# If running in background
tail -f d:\Projects\Clusters\Agent\logs\letta-server.log
```

---

## Testing the Integration

### 1. Test Direct Chat

```bash
curl -X POST http://127.0.0.1:8888/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "My favorite programming language is Python",
    "user_id": "openwebui"
  }'
```

### 2. Test Memory Persistence

```bash
# Message 1: Tell it something
curl -X POST http://127.0.0.1:8888/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I work on machine learning projects",
    "user_id": "openwebui"
  }'

# Message 2: Ask it to recall
curl -X POST http://127.0.0.1:8888/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What field do I work in?",
    "user_id": "openwebui"
  }'

# Agent should remember from previous message
```

### 3. Test in Open WebUI

1. Open Open WebUI
2. Create new conversation
3. Send message: "Remember that I like to work on AI projects"
4. Send follow-up: "What do I like to work on?"
5. Agent should recall from memory

---

## Troubleshooting Integration

### "Cannot connect to Letta server"

**Check**:
1. Letta server is running: `curl http://127.0.0.1:8888/health`
2. Firewall allows connection to port 8888
3. Server is bound to correct address

**Fix**:
```powershell
# Start server again
cd d:\Projects\Clusters\Agent\config
.\letta-launch.ps1
```

### Memory not being used

**Check**:
1. Letta function is selected in Open WebUI
2. Server logs show chat requests: `tail -f logs/letta-server.log`
3. Memory database exists: `ls data/letta/`

### Slow responses

**Cause**: First query loads embedding model (~5-10 seconds)

**Expected**: Subsequent queries are faster (50-200ms)

**Optimize**:
- Reduce `top_k` in config from 3 to 1
- Use smaller embedding model

---

## Performance Tuning

### Reduce Memory Search Latency

In `config/letta_config.json`:
```json
{
  "retrieval": {
    "top_k": 1,
    "relevance_threshold": 0.6
  }
}
```

### Increase Memory Capacity

No special configuration needed - just disk space:
- 1GB disk = ~100K tokens history
- 10GB disk = ~1M tokens history

### Use Smaller Embedding Model

```json
{
  "model": {
    "embedding_model": "all-MiniLM-L6-v2:latest"
  }
}
```

---

## Network Architecture

For production setups:

```
┌─────────────────────┐
│   Open WebUI        │ (localhost:3000)
│  + Function Module  │
└──────────┬──────────┘
           │ localhost:8888
           ▼
┌─────────────────────┐
│  Letta HTTP Server  │
│  + REST API         │
└──────────┬──────────┘
           │ localhost:11434
           ▼
┌─────────────────────┐
│   Ollama Qwen4B     │
│   (GPU)             │
└─────────────────────┘
```

For remote access:
- Make sure firewall allows 8888
- Use reverse proxy (nginx) for SSL
- Add authentication if exposed

---

## Next Steps

1. ✅ Start Letta: `.\letta-launch.ps1`
2. ✅ Verify connection: `curl http://127.0.0.1:8888/health`
3. ✅ Choose integration method from above
4. ✅ Test in Open WebUI
5. ✅ Monitor memory growth

**You're ready!** All Open WebUI chats now have 1M+ token memory.
