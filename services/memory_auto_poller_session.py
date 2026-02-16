#!/usr/bin/env python
"""
Memory Auto-Poller with Session Authentication
Uses authenticated session cookies instead of API keys when API keys are disabled.
"""
import httpx
import asyncio
import sqlite3
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
OPEN_WEBUI_URL = os.environ.get("OPEN_WEBUI_URL", "http://localhost:8080")
OPENWEBUI_EMAIL = os.environ.get("OPENWEBUI_EMAIL", "me@itslittlekevin.com")
OPENWEBUI_PASSWORD = os.environ.get("OPENWEBUI_PASSWORD", "00_KevinZhao@0401_OpenWebUI")
MEMORY_DB = Path(__file__).parent.parent / "data" / "letta" / "memory.db"
POLL_INTERVAL = 5  # Check every 5 seconds for new conversations
STATE_FILE = Path(__file__).parent.parent / "data" / "letta" / ".last_sync"

class MemoryPoller:
    def __init__(self):
        self.client = None
        self.session_cookies = None
        self.last_sync = self._load_last_sync()
        self.synced_chat_ids = set()
        
    def _ensure_db(self):
        """Ensure database exists with required tables."""
        conn = sqlite3.connect(MEMORY_DB)
        c = conn.cursor()
        
        # Create conversation table if not exists
        c.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT,
                model TEXT,
                timestamp TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                chat_id TEXT UNIQUE
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_last_sync(self):
        """Load the last sync time to avoid re-syncing old conversations."""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    return float(f.read().strip())
        except:
            pass
        return time.time() - 3600  # Default to 1 hour ago on first run
    
    def _save_last_sync(self):
        """Save current time as last sync time."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            f.write(str(time.time()))
    
    async def login(self) -> bool:
        """Authenticate with Open WebUI and get session cookies."""
        print(f"[AUTH] Logging in to {OPEN_WEBUI_URL}")
        print(f"[AUTH] Email: {OPENWEBUI_EMAIL}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{OPEN_WEBUI_URL}/api/v1/auths/signin",
                    json={"email": OPENWEBUI_EMAIL, "password": OPENWEBUI_PASSWORD},
                    follow_redirects=True
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    self.session_cookies = dict(client.cookies)
                    print(f"[AUTH] ✓ Logged in as: {user_data.get('name')} ({user_data.get('role')})")
                    return True
                else:
                    print(f"[AUTH] ✗ Login failed (HTTP {response.status_code})")
                    print(f"       {response.json()}")
                    return False
        
        except Exception as e:
            print(f"[AUTH] ✗ Connection error: {e}")
            return False
    
    async def fetch_conversations(self) -> list:
        """Fetch conversations from Open WebUI API using session cookies."""
        try:
            endpoint = f"{OPEN_WEBUI_URL}/api/v1/chats"
            
            async with httpx.AsyncClient(cookies=self.session_cookies, timeout=10) as client:
                print(f"[POLLER] Fetching from: {endpoint}")
                r = await client.get(endpoint)
                
                if r.status_code == 200:
                    chats = r.json()
                    count = len(chats) if isinstance(chats, list) else len(chats.get("chats", []))
                    print(f"[POLLER] ✓ Got {count} chats")
                    return chats if isinstance(chats, list) else chats.get("chats", [])
                
                elif r.status_code == 401:
                    print(f"[POLLER] ✗ Session expired - need to re-login")
                    return []
                
                else:
                    print(f"[POLLER] ✗ HTTP {r.status_code}: {r.text[:100]}")
                    return []
            
        except Exception as e:
            print(f"[POLLER] Error fetching conversations: {e}")
            return []
    
    def _save_conversation(self, chat_id: str, title: str, messages: list, user_id: str = "default", model: str = None):
        """Save conversation to memory database."""
        try:
            if not messages or len(messages) < 2:
                return  # Need at least user + assistant message
            
            # Extract user and assistant messages
            user_msg = None
            assistant_msg = None
            
            for msg in messages:
                role = msg.get("role", "").lower()
                content = msg.get("content", "").strip()
                
                if role == "user" and not user_msg:
                    user_msg = content
                elif role == "assistant" and content:
                    assistant_msg = content
            
            if not user_msg:
                return  # No user message, skip
            
            # Store in memory database
            conn = sqlite3.connect(MEMORY_DB)
            c = conn.cursor()
            
            # Check if this chat_id is already stored
            existing = c.execute(
                'SELECT id FROM conversations WHERE chat_id = ?',
                (chat_id,)
            ).fetchone()
            
            if not existing:
                c.execute('''
                    INSERT INTO conversations (user_id, message, response, model, timestamp, chat_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, user_msg, assistant_msg or "", model, datetime.now().isoformat(), chat_id))
                
                conn.commit()
                print(f"[POLLER] ✓ Saved: {user_msg[:60]}...")
            
            conn.close()
            
        except Exception as e:
            print(f"[POLLER] Error saving conversation: {e}")
    
    async def sync(self):
        """Poll for new conversations and save them."""
        print(f"\n[POLLER] Syncing at {datetime.now().strftime('%H:%M:%S')}")
        
        chats = await self.fetch_conversations()
        
        if not chats:
            print("[POLLER] No chats found")
            return
        
        saved_count = 0
        for chat in chats:
            chat_id = chat.get("id") or chat.get("chat_id")
            title = chat.get("title", "Untitled")
            messages = chat.get("messages", [])
            
            # Try to get user_id
            user = chat.get("user_id") or chat.get("userId") or chat.get("user", {})
            if isinstance(user, dict):
                user_id = user.get("id") or "default"
            else:
                user_id = user or "default"
            
            if chat_id and messages:
                self._save_conversation(chat_id, title, messages, user_id)
                saved_count += 1
        
        self._save_last_sync()
        print(f"[POLLER] ✓ Sync complete ({saved_count} conversations)")
    
    async def run(self):
        """Main loop - continuously poll for new conversations."""
        self._ensure_db()
        
        print("=" * 70)
        print("MEMORY AUTO-POLLER (SESSION AUTH)")
        print("=" * 70)
        print(f"Open WebUI:  {OPEN_WEBUI_URL}")
        print(f"Memory DB:   {MEMORY_DB}")
        print(f"Poll Interval: {POLL_INTERVAL} seconds")
        print(f"Auth Method: Session-based (API keys disabled)")
        print("=" * 70)
        
        # Initial login
        if not await self.login():
            print("[ERROR] Could not login. Exiting.")
            return
        
        print("\nConversations will be automatically captured every few seconds.\n")
        
        while True:
            try:
                await self.sync()
            except Exception as e:
                print(f"[POLLER] Error in main loop: {e}")
            
            await asyncio.sleep(POLL_INTERVAL)


async def main():
    poller = MemoryPoller()
    await poller.run()


if __name__ == "__main__":
    asyncio.run(main())
