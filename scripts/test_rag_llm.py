"""
Test simplified RAG + Claude API workflow
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

from app.rag.pipeline import RAGPipeline
from anthropic import Anthropic
import asyncio

async def test_rag_with_llm():
    """Test RAG retrieval + LLM generation"""

    print("=" * 60)
    print("RAG + Claude API Integration Test")
    print("=" * 60)

    try:
        # Initialize components
        print("\n[1/4] Initializing components...")
        rag = RAGPipeline()

        api_key = os.getenv('ANTHROPIC_API_KEY')
        base_url = os.getenv('ANTHROPIC_BASE_URL')
        model = os.getenv('CLAUDE_MODEL', 'claude-opus-4-6')

        client = Anthropic(api_key=api_key, base_url=base_url)

        print(f"[OK] RAG pipeline initialized ({rag.get_collection_count()} documents)")
        print(f"[OK] Claude client initialized")
        print(f"[INFO] Using model: {model}")
        print(f"[INFO] API endpoint: {base_url}")

        # Test question
        question = "什么是市盈率？如何使用它评估股票？"

        print(f"\n[2/4] Retrieving knowledge...")
        print(f"Question: {question}")

        # Retrieve from RAG
        rag_result = await rag.search(question)

        print(f"[OK] Found {len(rag_result.documents)} relevant documents")

        if not rag_result.documents:
            print("[ERROR] No documents found")
            return False

        # Build context from retrieved documents
        context = "\n\n".join([
            f"文档 {i+1} (来源: {doc.source}, 相关度: {doc.score:.4f}):\n{doc.content}"
            for i, doc in enumerate(rag_result.documents)
        ])

        print(f"\n[3/4] Generating answer with Claude...")

        # Create prompt with context
        prompt = f"""基于以下检索到的知识库内容，回答用户的问题。

知识库内容：
{context}

用户问题：{question}

请基于上述知识库内容，用清晰、专业的语言回答问题。如果知识库内容不足以完整回答，请说明。"""

        # Call Claude API (without tools)
        print("\n[Response]")
        print("-" * 60)

        full_response = ""

        with client.messages.stream(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            for text in stream.text_stream:
                print(text, end='', flush=True)
                full_response += text

        print("\n" + "-" * 60)

        # Get usage info
        final_message = stream.get_final_message()
        usage = final_message.usage

        print(f"\n[4/4] Completed")
        print(f"[Tokens] Input: {usage.input_tokens}, Output: {usage.output_tokens}")
        print(f"[Response length] {len(full_response)} characters")
        print(f"[Sources] {len(rag_result.documents)} documents used")

        print("\n" + "=" * 60)
        print("[OK] RAG + Claude API integration working correctly!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("[ERROR] Test failed")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_rag_with_llm())
    sys.exit(0 if success else 1)
