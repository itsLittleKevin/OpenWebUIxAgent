"""
Letta Agent Service Integration

This service integrates Letta with your local Ollama models.
Provides persistent memory, conversation archival, and automatic recall.

Usage:
    agent = LettaOllamaAgent(model="huihui_ai/qwen3-abliterated:4b-v2")
    response = agent.chat("Hello, remember this fact for later")
"""

import logging
import os
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Configuration paths
PROJECT_ROOT = Path(__file__).parent.parent
LETTA_DATA_DIR = PROJECT_ROOT / "data" / "letta"
LETTA_CONFIG_FILE = PROJECT_ROOT / "config" / "letta_config.json"


class LettaOllamaAgent:
    """
    Wrapper for Letta Memory Server that communicates via REST API.
    
    Features:
    - Sends chats to Letta server with automatic memory context
    - Leverages persistent memory (SQLite-based, no VRAM cost)
    - Automatic memory recall from past conversations
    - Integrates with Ollama for LLM responses
    """
    
    def __init__(
        self,
        model: str = "huihui_ai/qwen3-abliterated:4b-v2",
        agent_name: str = "OllamaAgent",
        letta_url: str = "http://127.0.0.1:8888",
    ):
        """
        Initialize Letta agent client (REST API).
        
        Args:
            model: Ollama model name
            agent_name: Name for this agent instance
            letta_url: URL of Letta Memory Server
        """
        self.model = model
        self.agent_name = agent_name
        self.letta_url = letta_url.rstrip('/')
        
        # Check Letta server is running
        if not self._check_server():
            logger.warning(f"Letta server not available at {self.letta_url}")
    
    def _check_server(self) -> bool:
        """Check if Letta server is running."""
        try:
            response = requests.get(f"{self.letta_url}/health", timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Server check failed: {e}")
            return False
    
    def chat(self, message: str, user_id: str = "default", include_memory: bool = True) -> str:
        """
        Send a message to Letta and get response with memory awareness.
        
        Args:
            message: User message
            user_id: User identifier
            include_memory: Whether to include memory context
            
        Returns:
            Agent response text
        """
        try:
            response = requests.post(
                f"{self.letta_url}/chat",
                json={
                    "message": message,
                    "user_id": user_id,
                    "model": self.model,
                    "include_memory": include_memory
                },
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", str(data))
            else:
                logger.error(f"Letta returned status {response.status_code}")
                return f"Error: Letta server returned {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Letta server")
            return "Error: Cannot connect to Letta server. Make sure it's running with: .\\config\\letta-launch.ps1"
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Error: {str(e)}"
    
    def add_memory(self, content: str, memory_type: str = "fact", user_id: str = "default") -> bool:
        """
        Add explicit content to memory.
        
        Args:
            content: Memory content to store
            memory_type: 'fact', 'preference', 'reminder', or 'note'
            user_id: User identifier
            
        Returns:
            Success status
        """
        try:
            response = requests.post(
                f"{self.letta_url}/memory/add",
                json={
                    "content": content,
                    "memory_type": memory_type,
                    "user_id": user_id
                },
                timeout=10
            )
            
            success = response.status_code == 200
            if success:
                logger.info(f"Added to {memory_type} memory: {content[:100]}...")
            return success
            
        except Exception as e:
            logger.error(f"Memory add error: {e}")
            return False
    
    def search_memory(self, query: str, limit: int = 5, user_id: str = None) -> List[Dict[str, Any]]:
        """
        Search memory for relevant conversations and facts.
        
        Args:
            query: Search query
            limit: Max results to return
            user_id: Optional user filter
            
        Returns:
            List of matching results
        """
        try:
            payload = {"query": query, "limit": limit}
            if user_id:
                payload["user_id"] = user_id
                
            response = requests.post(
                f"{self.letta_url}/memory/search",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            return []
            
        except Exception as e:
            logger.error(f"Memory search error: {e}")
            return []
    
    def get_memory_summary(self, user_id: str = None) -> Dict[str, Any]:
        """Get summary of memory state."""
        try:
            url = f"{self.letta_url}/memory/stats"
            if user_id:
                url += f"?user_id={user_id}"
                
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                stats = response.json()
                stats["agent_name"] = self.agent_name
                stats["model"] = self.model
                return stats
            return {
                "agent_name": self.agent_name,
                "model": self.model,
                "status": "error"
            }
            
        except Exception as e:
            logger.error(f"Memory summary error: {e}")
            return {}
    
    def get_recent_context(self, user_id: str = "default", limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent conversation history."""
        try:
            response = requests.get(
                f"{self.letta_url}/memory/recent",
                params={"user_id": user_id, "limit": limit},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("conversations", [])
            return []
            
        except Exception as e:
            logger.error(f"Get recent context error: {e}")
            return []
    
    def __repr__(self) -> str:
        return f"LettaOllamaAgent(model='{self.model}', agent='{self.agent_name}')"


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create agent
    agent = LettaOllamaAgent(
        model="huihui_ai/qwen3-abliterated:4b-v2",
        agent_name="QwenMemoryAgent"
    )
    
    print(f"Agent initialized: {agent}")
    print(f"Memory summary: {agent.get_memory_summary()}")
    
    # Example conversation
    print("\n--- Starting conversation ---")
    response = agent.chat("Hi! I'm testing Letta with your Qwen model.")
    print(f"Agent: {response}")
    
    # Add memory
    agent.add_memory("User is testing Letta integration", memory_type="fact")
    
    # Another message
    response = agent.chat("Can you remember that I like to work on AI projects?")
    print(f"Agent: {response}")
    
    # Search memory
    results = agent.search_memory("AI projects")
    print(f"Memory search results: {len(results)} items found")
    for r in results:
        print(f"  - {r.get('message', r.get('content', ''))[:80]}...")
