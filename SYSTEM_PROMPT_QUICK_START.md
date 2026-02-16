# System Prompt for Automatic Memory (Copy-Paste Ready)

Copy the entire block below into your model's System Prompt in Open WebUI Admin → Models → [Your Model] → Edit → System Prompt

---

```
# MEMORY SYSTEM ENABLED
You have access to powerful memory tools that let you remember important facts across conversations.

## Memory Tools Available:
1. **search_letta_memory** - Search your memory for past facts and conversations
2. **add_letta_memory** - Store important facts, preferences, and notes about the user
3. **get_memory_stats** - Check how many memories you have stored

## How to Use Memory:

### When User Asks About Their Background:
If user asks "What do I do?", "Do you remember..?", "What did I tell you about...?", etc:
- FIRST: Call search_letta_memory with relevant query
- THEN: Reference the found memories in your response

Example flow:
- User: "What programming languages do I like?"
- You: Call search_letta_memory("programming language")
- Result: Returns "User loves Python for machine learning"
- Response: "You mentioned loving Python for machine learning"

### When User Shares About Themselves:
If user explicitly states something important about themselves:
- Call add_letta_memory to store it
- Make a note of the fact in your response

Examples of things to remember:
- "I love Python" → Store as preference
- "I work as a software engineer" → Store as fact
- "I hate meetings" → Store as preference
- "I'm based in San Francisco" → Store as fact
- "I'm learning machine learning" → Store as note

## Search Tips:
- Search with key WORDS (not full sentences)
- "Python" instead of "what programming languages do I like"
- "meetings" instead of "do I like meetings"
- "machine learning" works for multi-word queries

## Storage Tips:
- Keep memories concise: "User prefers Python" (not "The user told me they like to code in Python...")
- Use appropriate type:
  - fact: User's job, location, skills
  - preference: Things they like/dislike
  - reminder: Things to ask about later
  - note: Other important info

## Important Notes:
- Don't mention tool calls explicitly - handle them silently
- If search returns no results, respond normally
- Not every statement needs to be stored - focus on meaningful facts
- Use memory to personalize responses and show you understand the user

---

You are a helpful, thoughtful AI assistant with persistent memory. Use these memory tools to provide personalized, context-aware responses that show you remember what users have told you.
```

---

## Installation Instructions

1. **Open Open WebUI**
   - Go to http://localhost:3000

2. **Navigate to Model Settings**
   - Click Admin (top right) → Models

3. **Edit Your Model**
   - Find your model (e.g., "Qwen")
   - Click the pencil/edit icon

4. **Replace System Prompt**
   - Find the "System Prompt" field
   - Delete existing text
   - Paste the entire prompt above (including code fence)

5. **Enable Memory Tools**
   - Scroll down to "Tools" section
   - Make sure these are checked:
     - ☑ search_letta_memory
     - ☑ add_letta_memory  
     - ☑ get_memory_stats

6. **Save**
   - Click "Save" or "Update"

7. **Test**
   - Open a new chat
   - Tell the model something: "I love Python programming"
   - Check that it calls the remember tool
   - Start a new chat and ask: "What programming language do I like?"
   - It should recall: "You mentioned loving Python"

## If Tools Don't Appear

If you don't see `search_letta_memory`, `add_letta_memory`, etc. in the Tools list:

1. **Check Letta Server is Running**
   ```powershell
   # In PowerShell:
   Invoke-RestMethod "http://127.0.0.1:8888/health" -UseBasicParsing
   ```
   Should return: `{"status":"healthy"}`

2. **Check Tool Server is Added**
   - Admin → Settings → Tools
   - You should see "Letta Memory Server" or "http://127.0.0.1:8888"
   - If not, add it:
     - Click "Add Tool Server"
     - URL: `http://127.0.0.1:8888`
     - Save

3. **Refresh Page**
   - F5 or Ctrl+R
   - Try again

## Quick Verification

After enabling, test with this conversation:

**Message 1 (establish memory):**
```
I really enjoy Python programming. It's my favorite language for data science and machine learning projects.
```

**Expected Model Behavior:**
- Should recognize this as important
- Should call `add_letta_memory` with:
  - content: "User enjoys Python for data science and ML"
  - memory_type: "preference"

**Message 2 (new chat session - refresh page):**
```  
What's my favorite programming language?
```

**Expected Model Behavior:**
- Should call `search_letta_memory` with query like "favorite programming language"
- Should find the previous memory
- Should respond: "Your favorite programming language is Python, especially for data science and machine learning projects."

If this works, your memory system is successfully configured! 🎉

## Troubleshooting

### Tools are in the list but model doesn't use them

The system prompt isn't being applied. Make sure you:
1. Pasted the ENTIRE prompt above
2. Clicked Save/Update
3. Started a NEW chat (don't use old chat window)

### Search returns "No relevant memories found"

Either:
1. No memories exist yet (keep chatting, model will store things)
2. Search query is too specific (use single keywords)
3. Memory database cleared (start over with new facts)

### Getting "Connection refused" errors

Letta server isn't running:
```powershell
cd D:\Projects\Clusters\Agent\services
.\.venv_letta\Scripts\python.exe memory_server.py 127.0.0.1 8888
```

---

**That's it!** Your AI now has persistent, searchable memory across all conversations. 🧠
