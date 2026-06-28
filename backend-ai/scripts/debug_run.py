"""Minimal debug to find exact import error."""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("1. Testing config...", flush=True)
try:
    from src.config import get_settings
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAIL: {e}", flush=True)

print("2. Testing database...", flush=True)
try:
    from src.db.database import get_db
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAIL: {e}", flush=True)

print("3. Testing state...", flush=True)
try:
    from src.agents.state import QueryMode
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAIL: {e}", flush=True)

print("4. Testing deepagents import...", flush=True)
try:
    from deepagents import create_deep_agent
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAIL: {e}", flush=True)

print("5. Testing memory module...", flush=True)
try:
    from src.agents.memory import get_memory_config
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAIL: {e}", flush=True)

print("6. Testing orchestrator import...", flush=True)
try:
    from src.agents.orchestrator import build_research_agent
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAIL: {e}", flush=True)

print("7. Building agent...", flush=True)
try:
    agent = build_research_agent()
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAIL: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("8. Test invoking agent...", flush=True)
try:
    import uuid

    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Hello, what can you do?"}]},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    print("   OK", flush=True)
    print(f"Response: {result['messages'][-1].content[:300]}", flush=True)
except Exception as e:
    print(f"   FAIL: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("DONE", flush=True)
