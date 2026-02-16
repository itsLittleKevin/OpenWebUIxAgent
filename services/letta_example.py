"""
Letta Integration Example and Testing

This script demonstrates how to use Letta with your Qwen model.
It shows memory persistence across sessions without increasing VRAM usage.

Run this after starting Ollama with your Qwen model:
    python letta_example.py
"""

import logging
import time
from letta_agent import LettaOllamaAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demonstrate_memory_persistence():
    """Demonstrate Letta's memory persistence across conversations."""
    
    print("\n" + "="*70)
    print("LETTA MEMORY PERSISTENCE DEMONSTRATION")
    print("="*70 + "\n")
    
    # Initialize agent
    print("[1] Initializing Letta agent with Qwen model...")
    agent = LettaOllamaAgent(
        model="huihui_ai/qwen3-abliterated:4b-v2",
        agent_name="QwenMemoryAgent"
    )
    print(f"✓ Agent ready: {agent}\n")
    
    # Session 1: Introduce yourself and facts
    print("[2] SESSION 1 - Learning about the user")
    print("-" * 70)
    
    messages = [
        "Hi! My name is Alice and I'm a software engineer.",
        "I specialize in AI and machine learning projects.",
        "I prefer working with Python and have 5 years of experience.",
    ]
    
    for msg in messages:
        print(f"\nYou: {msg}")
        response = agent.chat(msg)
        print(f"Agent: {response}\n")
        time.sleep(0.5)  # Rate limiting
    
    # Explicitly add memories
    print("[3] Adding explicit memories...")
    agent.add_memory(
        "Alice is a software engineer with 5 years of Python experience",
        memory_type="recall"
    )
    agent.add_memory(
        "Alice specializes in AI and machine learning projects",
        memory_type="archival"
    )
    print("✓ Memories added\n")
    
    # Session 2: Test memory recall
    print("[4] SESSION 2 - Testing memory recall")
    print("-" * 70)
    
    test_messages = [
        "What do you remember about me?",
        "What's my specialization again?",
        "How many years of Python experience do I have?",
    ]
    
    for msg in test_messages:
        print(f"\nYou: {msg}")
        response = agent.chat(msg)
        print(f"Agent: {response}\n")
        time.sleep(0.5)
    
    # Session 3: Search memory
    print("[5] Searching conversation history")
    print("-" * 70)
    
    queries = [
        "experience",
        "specialization",
        "programming languages",
    ]
    
    for query in queries:
        print(f"\nSearching for: '{query}'")
        results = agent.search_memory(query, limit=3)
        if results:
            for i, result in enumerate(results, 1):
                print(f"  Result {i}: {result}")
        else:
            print("  No results found")
        time.sleep(0.5)
    
    # Memory status
    print("\n[6] Memory Status")
    print("-" * 70)
    summary = agent.get_memory_summary()
    print(f"Agent: {summary.get('agent_name')}")
    print(f"Model: {summary.get('model')}")
    print(f"Timestamp: {summary.get('timestamp')}")
    
    # Save conversation
    print("\n[7] Exporting conversation...")
    filepath = agent.save_conversation()
    print(f"✓ Conversation saved to: {filepath}\n")
    
    print("="*70)
    print("DEMONSTRATION COMPLETE")
    print("="*70)
    print("\nKey Points:")
    print("• Your conversation history is saved on disk (SQLite)")
    print("• Zero VRAM overhead - only embeddings are stored")
    print("• Memories persist across sessions")
    print("• Agent can search and recall past conversations")
    print("• 1M tokens of history would use ~50-200MB disk, no VRAM")


def demonstrate_practical_usage():
    """Demonstrate practical usage patterns."""
    
    print("\n" + "="*70)
    print("PRACTICAL USAGE EXAMPLES")
    print("="*70 + "\n")
    
    agent = LettaOllamaAgent(model="huihui_ai/qwen3-abliterated:4b-v2")
    
    # Pattern 1: Long conversation with memory
    print("[Pattern 1] Long conversation with automatic memory management")
    print("-" * 70)
    
    conversation = [
        "I'm working on a machine learning project",
        "The dataset has about 100,000 samples",
        "What preprocessing steps should I take?",
        "I'll use scikit-learn for preprocessing",
        "What about feature scaling?",
    ]
    
    for msg in conversation:
        print(f"You: {msg}")
        response = agent.chat(msg)
        print(f"Agent: {response[:150]}...\n" if len(response) > 150 else f"Agent: {response}\n")
        time.sleep(0.3)
    
    # Pattern 2: Knowledge extraction
    print("\n[Pattern 2] Extracting and storing knowledge")
    print("-" * 70)
    
    knowledge_items = [
        "Use StandardScaler for numerical features",
        "Use OneHotEncoder for categorical features",
        "Split data into 80/20 train/test",
        "Use cross-validation for robust evaluation",
    ]
    
    print("Storing knowledge in agent memory...")
    for item in knowledge_items:
        agent.add_memory(item, memory_type="archival")
        print(f"  ✓ Stored: {item}")
    
    # Pattern 3: Memory-assisted response
    print("\n[Pattern 3] Memory-assisted responses")
    print("-" * 70)
    
    msg = "Can you summarize what you know about my ML project?"
    print(f"You: {msg}")
    response = agent.chat(msg)
    print(f"Agent: {response}\n")
    
    # Show memory being used
    memory_results = agent.search_memory("ML project")
    print(f"Memories retrieved: {len(memory_results)} items")


def demonstrate_multi_user_support():
    """Demonstrate multi-user conversations."""
    
    print("\n" + "="*70)
    print("MULTI-USER CONVERSATION EXAMPLE")
    print("="*70 + "\n")
    
    agent = LettaOllamaAgent(model="huihui_ai/qwen3-abliterated:4b-v2")
    
    # Different users
    users = {
        "alice": [
            "Hi, I'm Alice. I'm learning Python.",
            "Can you recommend good Python resources?"
        ],
        "bob": [
            "Hello, I'm Bob. I work with JavaScript.",
            "What's the best way to learn async/await?"
        ]
    }
    
    print("Multiple users having separate conversations with shared agent...\n")
    
    for user_id, messages in users.items():
        print(f"--- {user_id.upper()} ---")
        for msg in messages:
            print(f"{user_id}: {msg}")
            response = agent.chat(msg, user_id=user_id)
            print(f"Agent: {response[:100]}...\n" if len(response) > 100 else f"Agent: {response}\n")
            time.sleep(0.3)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        demo_type = sys.argv[1]
        
        if demo_type == "memory":
            demonstrate_memory_persistence()
        elif demo_type == "practical":
            demonstrate_practical_usage()
        elif demo_type == "multiuser":
            demonstrate_multi_user_support()
        else:
            print(f"Unknown demo type: {demo_type}")
            print("Valid options: memory, practical, multiuser")
    else:
        # Run all demos
        try:
            demonstrate_memory_persistence()
            demonstrate_practical_usage()
            demonstrate_multi_user_support()
        except KeyboardInterrupt:
            print("\n\nDemo interrupted.")
        except Exception as e:
            print(f"\nError during demo: {e}")
            logger.exception("Demo error")
