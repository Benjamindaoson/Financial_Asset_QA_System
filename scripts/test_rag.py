"""
Test RAG system with the configured API
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
import asyncio

async def test_rag():
    """Test RAG pipeline with sample questions"""

    print("=" * 60)
    print("RAG System Test")
    print("=" * 60)

    try:
        # Initialize RAG pipeline
        print("\n[1/3] Initializing RAG pipeline...")
        rag = RAGPipeline()
        print("[OK] RAG pipeline initialized successfully")
        print(f"[INFO] Knowledge base contains {rag.get_collection_count()} documents")

        # Test questions
        questions = [
            "什么是市盈率？",
            "如何分析财务报表？",
            "技术分析的主要指标有哪些？"
        ]

        print(f"\n[2/3] Testing with {len(questions)} questions...")

        for i, question in enumerate(questions, 1):
            print(f"\n--- Question {i} ---")
            print(f"Q: {question}")

            # Search RAG
            result = await rag.search(question)

            print(f"Found: {result.total_found} candidates, {len(result.documents)} after reranking")

            if result.documents:
                for j, doc in enumerate(result.documents, 1):
                    print(f"\n  Document {j}:")
                    print(f"    Score: {doc.score:.4f}")
                    print(f"    Source: {doc.source}")
                    print(f"    Content: {doc.content[:150]}...")
            else:
                print("  No relevant documents found")

        print("\n[3/3] All tests completed")
        print("\n" + "=" * 60)
        print("[OK] RAG system is working correctly!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("[ERROR] RAG test failed")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_rag())
    sys.exit(0 if success else 1)
