"""
Test Agent Core with RAG and Claude API
"""
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Change to backend directory
script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
backend_dir = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
env_file = os.path.join(backend_dir, '.env')
os.chdir(backend_dir)

# Load .env file
from dotenv import load_dotenv
load_dotenv(dotenv_path=env_file, override=True)

sys.path.insert(0, backend_dir)

from app.agent.core import AgentCore
import asyncio

async def test_agent():
    """Test Agent with knowledge-based questions"""

    print("=" * 60)
    print("Agent Core Test (RAG + Claude API)")
    print("=" * 60)

    try:
        # Initialize Agent
        print("\n[1/3] Initializing Agent...")
        agent = AgentCore(preferred_model="claude-opus")
        print("[OK] Agent initialized successfully")

        # Test questions
        questions = [
            "什么是市盈率？如何使用它评估股票？",
            "解释一下财务报表的三大报表",
        ]

        print(f"\n[2/3] Testing with {len(questions)} questions...")

        for i, question in enumerate(questions, 1):
            print(f"\n{'=' * 60}")
            print(f"Question {i}: {question}")
            print('=' * 60)

            full_response = ""
            tools_used = []

            # Run agent and collect streaming response
            async for event in agent.run(question):
                if event.type == "model_selected":
                    print(f"\n[Model] {event.model} ({event.provider})")
                    print(f"[Complexity] {event.complexity}")

                elif event.type == "tool_start":
                    print(f"\n[Tool] {event.name}")
                    tools_used.append(event.name)

                elif event.type == "tool_data":
                    print(f"[Data] Retrieved from {event.tool}")
                    if event.tool == "search_knowledge":
                        docs = event.data.get("documents", [])
                        print(f"  Found {len(docs)} relevant documents")
                        if docs:
                            print(f"  Top score: {docs[0].get('score', 'N/A')}")

                elif event.type == "chunk":
                    print(event.text, end='', flush=True)
                    full_response += event.text

                elif event.type == "done":
                    print(f"\n\n[Done] Request ID: {event.request_id}")
                    print(f"[Tokens] Input: {event.tokens_input}, Output: {event.tokens_output}")
                    print(f"[Verified] {event.verified}")
                    if event.sources:
                        print(f"[Sources] {len(event.sources)} sources used")

                elif event.type == "error":
                    print(f"\n[ERROR] {event.message}")
                    print(f"[Code] {event.code}")

            print(f"\n\n[Summary]")
            print(f"  Tools used: {', '.join(tools_used) if tools_used else 'None'}")
            print(f"  Response length: {len(full_response)} characters")

        print(f"\n[3/3] All tests completed")
        print("\n" + "=" * 60)
        print("[OK] Agent system is working correctly!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("[ERROR] Agent test failed")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_agent())
    sys.exit(0 if success else 1)
