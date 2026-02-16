# Memory System - Complete Guide

## Quick Start (30 Seconds)

### 1. Start Memory Server
```powershell
cd D:\Projects\Clusters\Agent\services
python memory_server.py 127.0.0.1 8888
```

### 2. Verify Running
```powershell
curl http://127.0.0.1:8888/health
# Should return: 200 OK
```

### 3. Add Memory Instructions to Model System Prompt

Copy the content from `services/MEMORY_SYSTEM_PROMPT.md` into your Open WebUI model's system prompt.

---

## How It Works

### Automatic (Model-Driven)
Once you add memory instructions to the system prompt, your model will:

**Auto-save** when it detects:
- "I like/dislike..." → saves as `preference`
- "I learned..." → saves as `fact`
- "My setting is..." → saves as `setting`

**Auto-search** when user asks:
- "Do you remember...?"
- "What did I say about...?"
- "What are my preferences?"

### Manual (Force Tool Use)
```
User: "Remember that I hate Java"
→ Model calls add_memory (triggered by keyword)

User: "Search memory for programming languages I like"
→ Model calls search_memory (triggered by keyword)
```

---

## System Tools Available

### `add_memory` - Store Information
**When to use:** Save preferences, facts, settings, or skills

**Parameters:**
- `content` (required): Text to remember
- `memory_type` (optional): `preference` | `fact` | `setting` | `skill`
- `user_id` (optional): default is "default"

**Example responses:**
```
✓ Successfully saved preference: "likes Python"
✓ Successfully saved fact: "uses Windows"
✓ Successfully saved setting: "prefers dark mode"
```

### `search_memory` - Retrieve Information
**When to use:** Find what you've told the model previously

**Parameters:**
- `query` (required): What to search for
- `user_id` (optional): default is "default"
- `limit` (optional): Max results (default 5)
- `filter_type` (optional): 
  - `user_only` - only user statements (default)
  - `assistant_only` - only model responses
  - `all` - both

**Example results:**
```json
[
  {
    "content": "likes Python programming",
    "memory_type": "preference",
    "timestamp": "2026-02-15T20:00:00",
    "score": 0.98,
    "source": "user_statement"
  }
]
```

---

## Usage Examples

### Example 1: Accumulate Preferences
```
Conv 1: "I like Python"
       → Model saves automatically
       
Conv 2: "I prefer TypeScript"  
       → Model saves automatically
       
Conv 3: "What languages do I like?"
       → Model searches, returns Python + TypeScript
```

### Example 2: Context-Aware Responses
```
Conv 1: User shares dietary restrictions
       → Model saves as setting
       
Conv 2: User asks for restaurant recommendations
       → Model searches memory, filters based on dietary needs
```

### Example 3: Cross-Session Memory
```
Session 1 (Yesterday):
  User: "I have ADHD"
  → Saved as fact

Session 2 (Today, weeks later):
  User: "Recommend productivity tips"
  → Model finds fact, tailors response
  → Still remembers from previous session!
```

---

## Current Database

**Location:** `D:\Projects\Clusters\Agent\data\letta\memory.db`

**Tables:**
- `conversations` - Full chat transcripts
- `memories` - Extracted memories with metadata
- `embeddings` - Semantic search vectors (optional)
- `reminders` - Scheduled alerts (optional)

**Auto-Creation:** Database and all tables are created automatically on first use. No manual setup needed.

---

## Testing

### Clean Test
```powershell
# 1. Delete database to start fresh
Remove-Item D:\Projects\Clusters\Agent\data\letta\memory.db -Force

# 2. Memory server will auto-create tables on next tool call
# (No need to restart if already running)

# 3. Start chatting with model
# First add_memory call triggers creation
```

### Manual Tool Test
```powershell
# Test add_memory
curl -X POST http://127.0.0.1:8888/api/add_memory `
  -H "Content-Type: application/json" `
  -d '{
    "content": "test memory",
    "memory_type": "fact",
    "user_id": "default"
  }'

# Test search_memory
curl -X POST http://127.0.0.1:8888/api/search `
  -H "Content-Type: application/json" `
  -d '{
    "query": "test",
    "limit": 5,
    "filter_type": "user_only"
  }'
```

---

## Technical Details

### Search Algorithm (Hybrid)

**Stage 1 - Keyword Search (Fast)**
- Splits text into keywords (handles CJK characters properly)
- OR-based matching (any keyword matches)
- Scores by keyword count
- Response time: <10ms

**Stage 2 - Semantic Search (Accurate)**
- Uses Ollama embeddings (model: nomic-embed-text)
- Cosine similarity scoring
- Triggered if no keyword matches
- Response time: <1s

### Source Type Separation

Every memory includes `source_type`:
- `user_statement` - What you said (default for search)
- `assistant_response` - What model said (useful for debugging)

This prevents models from accidentally echoing their own responses back to you.

### CJK Character Support

Properly handles Chinese/Japanese/Korean text:
```
Input: "我喜欢编程" (I like programming)
Split: ["我", "喜欢", "编程"]
Matches: ✓ Both individual chars and phrases work
```

---

## File Structure

**Essential Production Files:**
```
services/
├── memory_server.py              # Main API server (port 8888) - ALWAYS KEEP RUNNING
└── MEMORY_SYSTEM_PROMPT.md       # System prompt content (copy to model)

data/letta/
├── memory.db                     # SQLite database (auto-created)
└── .last_sync                    # Polling state (if using auto-poller)
```

**Optional/Advanced:**
```
services/
├── memory_auto_poller_session.py # Auto-capture (currently blocked by API routing)
└── letta_example.py              # Letta integration example

Root:
└── MEMORY.md                     # This file
```

---

## API Endpoints (Port 8888)

All endpoints require `user_id` parameter (default: "default")

### Health Check
```
GET /health
Response: 200 OK
```

### Add Memory
```
POST /api/add_memory
Body: {
  "content": "text to remember",
  "memory_type": "preference|fact|setting|skill",
  "user_id": "default"
}
Response: { "memory_id": 1, "status": "success" }
```

### Search Memories
```
POST /api/search
Body: {
  "query": "search terms",
  "user_id": "default",
  "limit": 5,
  "filter_type": "user_only|assistant_only|all"
}
Response: [{
  "id": 1,
  "content": "matched memory",
  "memory_type": "preference",
  "source_type": "user_statement",
  "timestamp": "2026-02-15T20:00:00"
}]
```

---

## Troubleshooting

### Server Won't Start
```powershell
# Check if port 8888 is in use
netstat -ano | grep 8888

# Kill if needed
Get-Process python | Stop-Process
```

### Tools Not Showing in Open WebUI
1. Check: Settings → Admin → Tool Server
2. Verify URL: `http://127.0.0.1:8888`
3. Reload page (Ctrl+Shift+R)

### Memories Not Saving
1. Confirm server running: `curl http://127.0.0.1:8888/health` → 200
2. Check Open WebUI logs for errors
3. Verify model system prompt includes memory tools

### Search Returns Nothing
- Try exact keyword from stored memory
- Check `filter_type` isn't too restrictive
- Use `filter_type="all"` to debug

---

## System Prompt Setup

Your input model can use memory tools automatically once you add instructions to the system prompt.

**Location:** `services/MEMORY_SYSTEM_PROMPT.md`

**How to use:**
1. Open your model's system prompt in Open WebUI
2. Copy content from `MEMORY_SYSTEM_PROMPT.md`
3. Paste into model system prompt section
4. Save

**Result:** Model will now intelligently call memory tools during conversations.

---

## Architecture

```
Open WebUI (http://localhost:8080)
    ↓
  Model System Prompt (with memory instructions)
    ↓
Memory Tools: add_memory | search_memory
    ↓
Memory Server API (http://127.0.0.1:8888)
    ↓
SQLite Database (memory.db)
    ↓
Persistent Cross-Session Memory ✓
```

---

## Summary

✅ **Production Ready**
- Server running on port 8888
- Tools registered in Open WebUI
- Storage working (add_memory)
- Retrieval working (search_memory)
- Cross-session persistence ✓
- CJK support ✓
- Hybrid search ✓

**Start Using:**
1. Memory server running
2. System prompt updated with memory instructions
3. Start chatting - model handles the rest!

---

## Status

**Current Implementation:** Model-driven (responsive to user/model requests)

**Future Enhancement:** Auto-poller (capture all conversations automatically) - currently blocked by Open WebUI frontend routing at port 8080

The model-driven approach is actually superior for most use cases as it's intelligent about what to remember.
