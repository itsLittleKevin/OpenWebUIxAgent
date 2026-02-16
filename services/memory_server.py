"""
Letta Memory & Tools Server for Open WebUI Integration

This provides:
- Persistent conversation memory (SQLite-based)
- Memory search across all conversations  
- OpenAI-compatible Tool Server for Open WebUI
- Ollama integration for chat completion with memory
- Automatic conversation archival
"""

import sqlite3
import json
import os
import httpx
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import asyncio

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data" / "letta"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "memory.db"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("LETTA_MODEL", "huihui_ai/qwen3-abliterated:4b-v2")
EMBEDDING_MODEL = "nomic-embed-text"  # Multilingual embedding model

# Semantic search threshold (cosine similarity 0-1, higher = more similar)
SEMANTIC_SIMILARITY_THRESHOLD = 0.6


def split_keywords(text: str) -> List[str]:
    """
    Smart keyword splitting that handles both English and CJK (Chinese, Japanese, Korean).
    
    For English: Splits by whitespace and removes punctuation.
    For CJK: Splits into individual characters since there are no spaces.
    
    Examples:
    - "hello world" -> ["hello", "world"]
    - "我在二月说" -> ["我", "在", "二", "月", "说"]
    - "I like Python编程" -> ["i", "like", "python", "编", "程"]
    """
    import re
    import unicodedata
    
    text = text.lower().strip()
    keywords = []
    
    # CJK Unicode ranges
    cjk_ranges = [
        (0x4E00, 0x9FFF),   # CJK Unified Ideographs
        (0x3040, 0x309F),   # Hiragana
        (0x30A0, 0x30FF),   # Katakana
        (0xAC00, 0xD7AF),   # Hangul Syllables
    ]
    
    def is_cjk(char: str) -> bool:
        code = ord(char)
        return any(start <= code <= end for start, end in cjk_ranges)
    
    i = 0
    while i < len(text):
        char = text[i]
        
        if is_cjk(char):
            # CJK character: add individually
            keywords.append(char)
            i += 1
        elif char.isspace() or char in '.,!?;:\'"()-':
            # Punctuation/whitespace: skip
            i += 1
        else:
            # English word: collect until next space/punctuation/CJK
            word = ''
            while i < len(text) and not text[i].isspace() and text[i] not in '.,!?;:\'"()-' and not is_cjk(text[i]):
                word += text[i]
                i += 1
            if word:
                keywords.append(word)
    
    return keywords


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    print(f"Memory database ready at: {DB_PATH}")
    yield


app = FastAPI(
    title="Letta Memory Server",
    description="""
Persistent memory and tools server for Open WebUI integration.

**Features:**
- 🧠 Persistent conversation memory (SQLite)
- 🔍 Full-text memory search
- 💬 Ollama chat with automatic memory context
- 📦 OpenAPI Tool Server compatible with Open WebUI

**Integration:**
Add this server as a Tool Server in Open WebUI:
1. Go to Admin → Settings → Tools
2. Add Tool Server URL: http://127.0.0.1:8888
3. Enable the tools in your model settings
    """,
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    model: str = DEFAULT_MODEL
    include_memory: bool = True
    max_memory_results: int = 3


class ChatResponse(BaseModel):
    response: str
    user_id: str
    timestamp: str
    memory_context: List[Dict[str, Any]] = []
    model: str


class MemoryAddRequest(BaseModel):
    content: str
    memory_type: str = "conversation"
    source_type: str = "user_statement"  # 'user_statement' or 'assistant_response'
    user_id: str = "default"


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 5
    user_id: Optional[str] = None


class ToolCallRequest(BaseModel):
    """OpenAPI Tool Server request format."""
    name: str
    arguments: Dict[str, Any]


# ============================================================================
# OpenAPI Tool Definitions (for Open WebUI Tool Server)
# ============================================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_letta_memory",
            "description": "Search the user's conversation history and stored memories for relevant information. Use this to recall past conversations, facts, or context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant memories"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_letta_memory",
            "description": "Store an important fact, preference, or note about the user for future recall. Use this when the user shares something worth remembering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The memory content to store"
                    },
                    "memory_type": {
                        "type": "string",
                        "enum": ["fact", "preference", "reminder", "note"],
                        "description": "Type of memory",
                        "default": "fact"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "get_memory_stats",
            "description": "Get statistics about the user's stored memories and conversation history.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# ============================================================================
# Database Functions
# ============================================================================

def init_db():
    """Initialize database tables with proper indexing."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Conversations table - stores full chat exchanges
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT,
            model TEXT,
            timestamp TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0
        )
    ''')
    
    # Memory table - explicit facts, preferences, notes
    c.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            memory_type TEXT DEFAULT 'fact',
            source_type TEXT DEFAULT 'user_statement',
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    ''')
    
    # Reminders table - time-based reminders
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            text TEXT NOT NULL,
            due_date TEXT,
            created_at TEXT NOT NULL,
            completed INTEGER DEFAULT 0
        )
    ''')
    
    # Embeddings table - stores semantic embeddings for semantic search
    c.execute('''
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY,
            source_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Create indexes for faster search
    c.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_embeddings_source ON embeddings(source_id, source_type)')
    
    # Migration: Add source_type column if it doesn't exist (for existing databases)
    try:
        c.execute('SELECT source_type FROM memories LIMIT 1')
    except Exception:
        # Column doesn't exist, add it
        c.execute('ALTER TABLE memories ADD COLUMN source_type TEXT DEFAULT "user_statement"')
        print("Database migration: Added source_type column to memories table")
    
    conn.commit()
    conn.close()


async def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding vector from Ollama for multilingual text."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text}
            )
            if response.status_code == 200:
                return response.json().get("embedding")
    except Exception as e:
        print(f"Warning: Failed to get embedding for text: {e}")
    return None


def store_embedding(source_id: int, source_type: str, embedding: List[float]):
    """Store embedding vector in database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        embedding_blob = json.dumps(embedding)
        c.execute('''
            INSERT OR REPLACE INTO embeddings (source_id, source_type, embedding, created_at)
            VALUES (?, ?, ?, ?)
        ''', (source_id, source_type, embedding_blob, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Warning: Failed to store embedding: {e}")


def get_stored_embedding(source_id: int, source_type: str) -> Optional[List[float]]:
    """Retrieve stored embedding from database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT embedding FROM embeddings WHERE source_id = ? AND source_type = ?',
                  (source_id, source_type))
        row = c.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception as e:
        print(f"Warning: Failed to retrieve embedding: {e}")
    return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    try:
        a_arr = np.array(a, dtype=np.float32)
        b_arr = np.array(b, dtype=np.float32)
        dot_product = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))
    except Exception as e:
        print(f"Warning: Failed to compute similarity: {e}")
        return 0.0


def search_memories(query: str, user_id: str = None, limit: int = 5, filter_type: str = "user_only") -> List[Dict]:
    """
    Hybrid search: keyword-first with semantic fallback.
    
    Args:
        query: Search query text
        user_id: Filter by user (optional)
        limit: Maximum results to return
        filter_type: 'user_only' (default), 'assistant_only', or 'all'
    
    Returns:
        List of matching memories
        
    1. First tries keyword search (word-based OR matching - must contain SOME query keywords)
    2. If no results, falls back to semantic search (multilingual embeddings)
    3. Works across languages with nomic-embed-text model
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    results = []
    searched_ids = set()
    
    # ========== STAGE 1: KEYWORD SEARCH (Fast, OR-based) ==========
    # Split query into individual keywords (CJK-aware)
    keywords = split_keywords(query)
    
    # For keyword matching, use OR logic: if ANY keyword is found, it's a match
    # Also score by how many keywords match (relevance)
    scored_results = []
    
    # Search conversations
    conv_sql = 'SELECT id, user_id, message, response, timestamp, "conversation" as source FROM conversations WHERE 1=1'
    conv_params = []
    
    if user_id:
        conv_sql += ' AND user_id = ?'
        conv_params.append(user_id)
    
    conv_sql += ' ORDER BY timestamp DESC'
    
    for row in c.execute(conv_sql, conv_params):
        row_dict = dict(row)
        content = (row_dict.get('message', '') + ' ' + row_dict.get('response', '')).lower()
        
        # Count how many keywords match (relevance score)
        match_count = sum(1 for keyword in keywords if keyword in content)
        
        # Include if ANY keyword matches (OR logic)
        if match_count > 0:
            row_dict['keyword_matches'] = match_count
            scored_results.append(row_dict)
            searched_ids.add(row_dict['id'])
    
    # Search explicit memories with source_type filtering
    # Convert filter_type to source_type values
    if filter_type == "user_only":
        source_types = ['user_statement']
    elif filter_type == "assistant_only":
        source_types = ['assistant_response']
    elif filter_type == "all":
        source_types = ['user_statement', 'assistant_response']
    else:
        source_types = ['user_statement']  # Default
    
    mem_sql = 'SELECT id, user_id, content, memory_type, source_type, created_at as timestamp, "memory" as source FROM memories WHERE source_type IN (' + ','.join('?' * len(source_types)) + ')'
    mem_params = source_types.copy()
    
    if user_id:
        mem_sql += ' AND user_id = ?'
        mem_params.append(user_id)
    
    mem_sql += ' ORDER BY created_at DESC'
    
    for row in c.execute(mem_sql, mem_params):
        row_dict = dict(row)
        content = row_dict.get('content', '').lower()
        
        # Count how many keywords match
        match_count = sum(1 for keyword in keywords if keyword in content)
        
        if match_count > 0:
            row_dict['keyword_matches'] = match_count
            scored_results.append(row_dict)
            searched_ids.add(row_dict['id'])
    
    # If keyword search found results, sort by relevance (match count) and return
    if scored_results:
        scored_results.sort(key=lambda x: (x.get('keyword_matches', 0), x.get('timestamp', '')), reverse=True)
        
        # Remove the scoring field before returning
        for result in scored_results:
            result.pop('keyword_matches', None)
        
        conn.close()
        return scored_results[:limit]
    
    # ========== STAGE 2: SEMANTIC SEARCH (Fallback, multilingual) ==========
    # Use asyncio to get embedding (this is sync context, so we create a new event loop)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        query_embedding = loop.run_until_complete(get_embedding(query))
        loop.close()
        
        if query_embedding is None:
            conn.close()
            return []  # Can't do semantic search without embedding
        
        semantic_results = []
        
        # Score conversations
        conv_sql = 'SELECT id, user_id, message, response, timestamp, "conversation" as source FROM conversations WHERE 1=1'
        conv_params = []
        
        if user_id:
            conv_sql += ' AND user_id = ?'
            conv_params.append(user_id)
        
        conv_sql += ' ORDER BY timestamp DESC'
        
        for row in c.execute(conv_sql, conv_params):
            row_dict = dict(row)
            stored_emb = get_stored_embedding(row_dict['id'], 'conversation')
            
            if stored_emb is None:
                # Generate and store embedding if not cached
                content = (row_dict.get('message', '') + ' ' + row_dict.get('response', ''))
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                stored_emb = loop.run_until_complete(get_embedding(content))
                loop.close()
                
                if stored_emb:
                    store_embedding(row_dict['id'], 'conversation', stored_emb)
            
            if stored_emb:
                similarity = cosine_similarity(query_embedding, stored_emb)
                if similarity >= SEMANTIC_SIMILARITY_THRESHOLD:
                    row_dict['similarity'] = similarity
                    semantic_results.append(row_dict)
        
        # Score memories
        mem_sql = 'SELECT id, user_id, content, memory_type, created_at as timestamp, "memory" as source FROM memories WHERE 1=1'
        mem_params = []
        
        if user_id:
            mem_sql += ' AND user_id = ?'
            mem_params.append(user_id)
        
        mem_sql += ' ORDER BY created_at DESC'
        
        for row in c.execute(mem_sql, mem_params):
            row_dict = dict(row)
            stored_emb = get_stored_embedding(row_dict['id'], 'memory')
            
            if stored_emb is None:
                # Generate and store embedding if not cached
                content = row_dict.get('content', '')
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                stored_emb = loop.run_until_complete(get_embedding(content))
                loop.close()
                
                if stored_emb:
                    store_embedding(row_dict['id'], 'memory', stored_emb)
            
            if stored_emb:
                similarity = cosine_similarity(query_embedding, stored_emb)
                if similarity >= SEMANTIC_SIMILARITY_THRESHOLD:
                    row_dict['similarity'] = similarity
                    semantic_results.append(row_dict)
        
        # Sort by similarity and limit
        semantic_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        results = semantic_results[:limit]
        
    except Exception as e:
        print(f"Warning: Semantic search failed: {e}")
        results = []
    
    conn.close()
    return results


def add_conversation(message: str, response: str, user_id: str = "default", model: str = None):
    """Store conversation in memory and generate embeddings."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO conversations (user_id, message, response, model, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, message, response, model, datetime.now().isoformat()))
    conn.commit()
    
    # Get the ID of the newly inserted conversation
    c.execute('SELECT last_insert_rowid() as id')
    conv_id = c.fetchone()[0]
    conn.close()
    
    # Generate and store embedding asynchronously (fire and forget)
    combined_text = f"{message} {response}"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        embedding = loop.run_until_complete(get_embedding(combined_text))
        loop.close()
        
        if embedding:
            store_embedding(conv_id, 'conversation', embedding)
    except Exception as e:
        print(f"Warning: Failed to generate embedding for conversation: {e}")


def add_memory(content: str, memory_type: str, user_id: str = "default", source_type: str = "user_statement"):
    """Store explicit memory and generate embeddings.
    
    Args:
        content: The memory content
        memory_type: Type of memory (fact, preference, reminder, note)
        user_id: User identifier
        source_type: 'user_statement' for user utterances, 'assistant_response' for LLM responses
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO memories (user_id, content, memory_type, source_type, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, content, memory_type, source_type, datetime.now().isoformat()))
    conn.commit()
    
    # Get the ID of the newly inserted memory
    c.execute('SELECT last_insert_rowid() as id')
    mem_id = c.fetchone()[0]
    conn.close()
    
    # Generate and store embedding asynchronously (fire and forget)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        embedding = loop.run_until_complete(get_embedding(content))
        loop.close()
        
        if embedding:
            store_embedding(mem_id, 'memory', embedding)
    except Exception as e:
        print(f"Warning: Failed to generate embedding for memory: {e}")


def get_recent_context(user_id: str, limit: int = 5) -> List[Dict]:
    """Get recent conversation context for a user."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    results = c.execute('''
        SELECT message, response, timestamp
        FROM conversations
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (user_id, limit)).fetchall()
    
    conn.close()
    return [dict(row) for row in results]


def get_stats(user_id: str = None) -> Dict:
    """Get memory statistics."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if user_id:
        conv_count = c.execute(
            'SELECT COUNT(*) FROM conversations WHERE user_id = ?', 
            (user_id,)
        ).fetchone()[0]
        mem_count = c.execute(
            'SELECT COUNT(*) FROM memories WHERE user_id = ?',
            (user_id,)
        ).fetchone()[0]
    else:
        conv_count = c.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]
        mem_count = c.execute('SELECT COUNT(*) FROM memories').fetchone()[0]
    
    # Get database size
    db_size = os.path.getsize(DB_PATH) if DB_PATH.exists() else 0
    
    conn.close()
    
    return {
        "conversations": conv_count,
        "memories": mem_count,
        "database_size_mb": round(db_size / (1024 * 1024), 2),
        "database_path": str(DB_PATH)
    }


# ============================================================================
# Ollama Integration
# ============================================================================

async def chat_with_ollama(
    message: str,
    model: str = DEFAULT_MODEL,
    system_prompt: str = None,
    context: List[Dict] = None
) -> str:
    """Send chat to Ollama and get response."""
    
    messages = []
    
    # Add system prompt with memory context
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # Add conversation context from memory
    if context:
        for ctx in reversed(context):  # Oldest first
            messages.append({"role": "user", "content": ctx.get("message", "")})
            if ctx.get("response"):
                messages.append({"role": "assistant", "content": ctx.get("response", "")})
    
    # Add current message
    messages.append({"role": "user", "content": message})
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("message", {}).get("content", "")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama error: {response.text}"
            )


# ============================================================================
# API Endpoints - Core
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/")
async def root():
    """API root with endpoint documentation."""
    return {
        "service": "Letta Memory Server",
        "version": "2.0.0",
        "description": "Persistent memory and tools for Open WebUI",
        "endpoints": {
            "GET /health": "Health check",
            "GET /openapi.json": "OpenAPI specification",
            "POST /chat": "Chat with Ollama + memory context",
            "POST /memory/search": "Search conversation history",
            "POST /memory/add": "Add explicit memory",
            "GET /memory/stats": "Memory statistics",
            "GET /tools": "List available tools (OpenAPI Tool Server)",
            "POST /tools/call": "Execute a tool (OpenAPI Tool Server)"
        },
        "integration": {
            "openwebui_tool_server": "Add this URL as a Tool Server in Open WebUI Admin → Settings → Tools"
        }
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with Ollama with automatic memory context.
    
    - Searches past conversations for relevant context
    - Sends context + message to Ollama
    - Stores the conversation for future recall
    """
    try:
        memory_context = []
        system_prompt = None
        
        if request.include_memory:
            # Search for relevant past context
            memories = search_memories(
                request.message, 
                request.user_id, 
                limit=request.max_memory_results
            )
            
            if memories:
                memory_context = memories
                context_text = "\n".join([
                    f"- {m.get('message', m.get('content', ''))[:200]}"
                    for m in memories
                ])
                system_prompt = f"""You have access to the user's past conversation history.
Relevant context from previous conversations:
{context_text}

Use this context to provide more personalized and contextual responses."""
        
        # Get recent conversation history for continuity
        recent = get_recent_context(request.user_id, limit=3)
        
        # Chat with Ollama
        response_text = await chat_with_ollama(
            message=request.message,
            model=request.model,
            system_prompt=system_prompt,
            context=recent
        )
        
        # Store conversation
        add_conversation(
            request.message, 
            response_text, 
            request.user_id,
            request.model
        )
        
        return ChatResponse(
            response=response_text,
            user_id=request.user_id,
            timestamp=datetime.now().isoformat(),
            memory_context=memory_context,
            model=request.model
        )
        
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {OLLAMA_URL}. Is it running?"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# API Endpoints - Memory
# ============================================================================

@app.post("/memory/search")
async def memory_search(request: MemorySearchRequest):
    """Search conversation history and explicit memories."""
    try:
        results = search_memories(
            request.query, 
            request.user_id,
            limit=request.limit
        )
        return {
            "query": request.query,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/add")
async def memory_add(request: MemoryAddRequest):
    """Add explicit memory (fact, preference, note)."""
    try:
        add_memory(request.content, request.memory_type, request.user_id)
        return {
            "status": "success",
            "message": f"Stored {request.memory_type}: {request.content[:50]}..."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/stats")
async def memory_stats(user_id: Optional[str] = None):
    """Get memory statistics."""
    try:
        stats = get_stats(user_id)
        stats["timestamp"] = datetime.now().isoformat()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/recent")
async def memory_recent(user_id: str = "default", limit: int = 10):
    """Get recent conversations for a user."""
    try:
        recent = get_recent_context(user_id, limit)
        return {
            "user_id": user_id,
            "count": len(recent),
            "conversations": recent
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# API Endpoints - OpenAPI Tool Server (for Open WebUI integration)
# ============================================================================

@app.get("/tools")
async def list_tools():
    """
    List available tools (OpenAPI Tool Server format).
    
    This endpoint allows Open WebUI to discover available tools.
    """
    return {"tools": TOOL_DEFINITIONS}


@app.post("/tools/call")
async def call_tool(request: ToolCallRequest, req: Request):
    """
    Execute a tool by name (OpenAPI Tool Server format).
    
    This endpoint is called by Open WebUI when a tool is invoked.
    """
    tool_name = request.name
    args = request.arguments
    
    # Get user_id from request headers if available
    user_id = req.headers.get("X-User-ID", "default")
    
    try:
        if tool_name == "search_letta_memory":
            query = args.get("query", "")
            limit = args.get("limit", 5)
            filter_type = args.get("filter_type", "user_only")  # 'user_only', 'assistant_only', or 'all'
            results = search_memories(query, user_id, limit, filter_type)
            
            if results:
                formatted = []
                for r in results:
                    source_label = ""
                    if r.get("source_type") == "assistant_response":
                        source_label = " [LLM]"
                    
                    if r.get("source") == "conversation":
                        formatted.append(f"[{r['timestamp'][:10]}] Q: {r['message'][:100]}")
                    else:
                        formatted.append(f"[{r['timestamp'][:10]}] {r['content'][:150]}{source_label}")
                return {"result": "\n".join(formatted)}
            return {"result": "No relevant memories found."}
            
        elif tool_name == "add_letta_memory":
            content = args.get("content", "")
            memory_type = args.get("memory_type", "fact")
            source_type = args.get("source_type", "user_statement")  # Default to user statement
            add_memory(content, memory_type, user_id, source_type)
            return {"result": f"Memory stored: {content[:50]}..."}  
            
        elif tool_name == "get_memory_stats":
            stats = get_stats(user_id)
            return {
                "result": f"Conversations: {stats['conversations']}, "
                         f"Memories: {stats['memories']}, "
                         f"Database size: {stats['database_size_mb']}MB"
            }
            
        else:
            return {"error": f"Unknown tool: {tool_name}"}
            
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# Webhook for Open WebUI (Auto-log conversations)
# ============================================================================

class WebhookPayload(BaseModel):
    """Payload from Open WebUI webhook."""
    user_message: str
    assistant_response: str
    user_id: str = "default"
    model: str = None
    chat_id: str = None


@app.post("/webhook/log")
async def webhook_log_conversation(req: Request):
    """
    Webhook endpoint for Open WebUI to auto-log conversations.
    
    Configure in Open WebUI: Admin → Settings → General → Webhook URL
    Add webhook URL: http://127.0.0.1:8888/webhook/log
    
    Accepts multiple payload formats from different Open WebUI versions.
    """
    try:
        body = await req.json()
        
        # Log the incoming request for debugging
        print(f"\n[WEBHOOK] Incoming request:")
        print(f"  Headers: {dict(req.headers)}")
        print(f"  Body: {json.dumps(body, indent=2, ensure_ascii=False)[:300]}")
        
        # Try different payload formats
        user_message = body.get("user_message") or body.get("message") or body.get("content")
        assistant_response = body.get("assistant_response") or body.get("response") or ""
        user_id = body.get("user_id") or body.get("userId") or "default"
        model = body.get("model") or body.get("modelId") or None
        chat_id = body.get("chat_id") or body.get("chatId") or None
        
        if user_message:
            add_conversation(user_message, assistant_response, user_id, model)
            print(f"[WEBHOOK] ✓ Logged: {user_message[:50]}...")
            return {"status": "logged", "chat_id": chat_id}
        else:
            print(f"[WEBHOOK] ❌ No user_message found in payload")
            return {"status": "error", "message": "No user_message in payload"}
            
    except Exception as e:
        print(f"[WEBHOOK] ❌ Error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.post("/webhook/debug")
async def webhook_debug(req: Request):
    """Debug endpoint to log all incoming webhook requests from Open WebUI."""
    try:
        body = await req.json()
        print(f"\n[WEBHOOK DEBUG] Raw request received")
        print(f"  Content-Type: {req.headers.get('content-type')}")
        print(f"  Full payload: {json.dumps(body, indent=2, ensure_ascii=False)}")
        return {"status": "debug_logged", "received": True}
    except Exception as e:
        print(f"[WEBHOOK DEBUG] Error: {e}")
        return {"status": "error", "message": str(e)}


# ============================================================================
# Server Entry Point
# ============================================================================

def main(host: str = "127.0.0.1", port: int = 8888):
    """Run the Letta memory server."""
    print("=" * 60)
    print("Letta Memory Server")
    print("=" * 60)
    print(f"Server:     http://{host}:{port}")
    print(f"API Docs:   http://{host}:{port}/docs")
    print(f"Health:     http://{host}:{port}/health")
    print(f"Database:   {DB_PATH}")
    print(f"Ollama:     {OLLAMA_URL}")
    print(f"Model:      {DEFAULT_MODEL}")
    print("=" * 60)
    print("\nOpen WebUI Integration:")
    print(f"  Tool Server URL: http://{host}:{port}")
    print("  Add in: Admin → Settings → Tools → Add Tool Server")
    print("=" * 60)
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8888
    main(host, port)
