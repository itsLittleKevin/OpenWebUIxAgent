"""
Letta HTTP Server Wrapper

Exposes Letta agent via REST API for integration with Open WebUI or other clients.

This server wraps Letta's memory capabilities and exposes:
- /chat - Send messages and get responses with memory
- /memory/add - Add explicit memories  
- /memory/search - Search conversation history
- /status - Get agent and memory status
"""

import logging
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Letta Agent Server",
    description="REST API for Letta agent with Ollama backend",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent: Optional[LettaOllamaAgent] = None


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    include_memory_search: bool = False


class ChatResponse(BaseModel):
    message: str
    user_id: str
    timestamp: str
    memory_used: Optional[list] = None


class MemoryAddRequest(BaseModel):
    content: str
    memory_type: str = "recall"  # or "archival"


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 5


class MemorySearchResponse(BaseModel):
    query: str
    results: list
    timestamp: str


class AgentStatusResponse(BaseModel):
    agent_name: str
    model: str
    status: str
    timestamp: str
    memory_summary: Dict[str, Any]


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("Starting server wrapper for Letta...")
    logger.info("Letta service should be running separately")
    logger.info("Wrapper API available at: http://127.0.0.1:8888")


@app.get("/")
async def root():
    """Root endpoint with API documentation."""
    return {
        "service": "Letta Agent Server",
        "version": "1.0.0",
        "status": "running" if agent else "error",
        "endpoints": {
            "POST /chat": "Send message and get response",
            "POST /memory/add": "Add content to memory",
            "POST /memory/search": "Search conversation history",
            "GET /status": "Get agent status",
            "GET /health": "Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/status", response_model=AgentStatusResponse)
async def get_agent_status():
    """Get agent status and memory summary."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    return AgentStatusResponse(
        agent_name=agent.agent_name,
        model=agent.model,
        status="ready",
        timestamp=datetime.now().isoformat(),
        memory_summary=agent.get_memory_summary()
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the agent.
    
    Letta automatically searches past conversations and injects relevant
    context into the LLM's input, giving it access to your full history
    without increasing VRAM usage.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        logger.info(f"Chat request from {request.user_id}: {request.message[:100]}...")
        
        # Get response from agent
        response_text = agent.chat(request.message, user_id=request.user_id)
        
        # Optionally search memory for related context
        memory_used = None
        if request.include_memory_search:
            memory_used = agent.search_memory(request.message, limit=3)
        
        return ChatResponse(
            message=response_text,
            user_id=request.user_id,
            timestamp=datetime.now().isoformat(),
            memory_used=memory_used
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/add")
async def add_memory(request: MemoryAddRequest):
    """Add explicit memory/fact to the agent's memory."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        success = agent.add_memory(request.content, memory_type=request.memory_type)
        if success:
            return {
                "status": "success",
                "message": f"Added to {request.memory_type} memory",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add memory")
            
    except Exception as e:
        logger.error(f"Add memory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/search", response_model=MemorySearchResponse)
async def search_memory(request: MemorySearchRequest):
    """Search past conversations in archival memory."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        results = agent.search_memory(request.query, limit=request.limit)
        return MemorySearchResponse(
            query=request.query,
            results=results,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/export")
async def export_memory(filename: Optional[str] = None):
    """Export conversation to file."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        filepath = agent.save_conversation(filename)
        return {
            "status": "success",
            "filepath": filepath,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memory/clear")
async def clear_memory():
    """Clear all agent memory (irreversible)."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        success = agent.clear_memory()
        if success:
            return {"status": "success", "message": "Memory cleared"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear memory")
            
    except Exception as e:
        logger.error(f"Clear memory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming conversations."""
    await websocket.accept()
    
    if agent is None:
        await websocket.send_json({"error": "Agent not initialized"})
        await websocket.close()
        return
    
    try:
        while True:
            data = await websocket.receive_text()
            request = json.loads(data)
            
            # Send message to agent
            response = agent.chat(request.get("message", ""), user_id=request.get("user_id", "default"))
            
            await websocket.send_json({
                "type": "response",
                "message": response,
                "timestamp": datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()


def run_server(host: str = "127.0.0.1", port: int = 8888):
    """Run the Letta server."""
    logger.info(f"Starting Letta server on {host}:{port}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    import sys
    
    # Allow command-line arguments
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8888
    
    run_server(host, port)
