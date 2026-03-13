"""Test migrated RAG system"""
import sys
from pathlib import Path
import io

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("Testing Migrated RAG System")
print("=" * 60)

# Test 1: Check if RAG files exist
print("\n[Test 1] Checking migrated RAG files...")
rag_files = [
    "app/rag/hybrid_pipeline.py",
    "app/rag/grounded_pipeline.py",
    "app/rag/fact_verifier.py",
    "app/rag/hybrid_retrieval.py",
    "app/rag/ultimate_pipeline.py",
    "app/rag/bge_embedding.py",
    "app/rag/enhanced_document_parser.py",
    "app/rag/enhanced_data_pipeline.py",
]

all_exist = True
for file in rag_files:
    exists = Path(file).exists()
    status = "[OK]" if exists else "[MISSING]"
    print(f"  {status} {file}")
    if not exists:
        all_exist = False

# Test 2: Check vector database
print("\n[Test 2] Checking vector database...")
chroma_path = Path("../vectorstore/chroma/chroma.sqlite3")
if chroma_path.exists():
    size_mb = chroma_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] ChromaDB exists: {size_mb:.2f} MB")
else:
    print(f"  [MISSING] ChromaDB not found")
    all_exist = False

# Test 3: Check raw_data
print("\n[Test 3] Checking raw_data...")
raw_data_path = Path("../data/raw_data")
if raw_data_path.exists():
    knowledge_files = list(raw_data_path.glob("knowledge/*.md"))
    report_files = list(raw_data_path.glob("finance_report/*"))
    print(f"  [OK] Knowledge files: {len(knowledge_files)}")
    print(f"  [OK] Report files: {len(report_files)}")
else:
    print(f"  [MISSING] raw_data not found")
    all_exist = False

# Test 4: Try to import RAG modules
print("\n[Test 4] Testing RAG module imports...")
import_success = True
try:
    from app.rag.hybrid_pipeline import HybridRAGPipeline
    print("  [OK] HybridRAGPipeline imported")
except Exception as e:
    print(f"  [FAIL] HybridRAGPipeline: {e}")
    import_success = False

try:
    from app.rag.grounded_pipeline import GroundedRAGPipeline
    print("  [OK] GroundedRAGPipeline imported")
except Exception as e:
    print(f"  [FAIL] GroundedRAGPipeline: {e}")
    import_success = False

try:
    from app.rag.fact_verifier import AnswerQualityController
    print("  [OK] AnswerQualityController imported")
except Exception as e:
    print(f"  [FAIL] AnswerQualityController: {e}")
    import_success = False

try:
    from app.rag.hybrid_retrieval import HybridRetriever
    print("  [OK] HybridRetriever imported")
except Exception as e:
    print(f"  [FAIL] HybridRetriever: {e}")
    import_success = False

try:
    from app.rag.ultimate_pipeline import UltimateRAGPipeline
    print("  [OK] UltimateRAGPipeline imported")
except Exception as e:
    print(f"  [FAIL] UltimateRAGPipeline: {e}")
    import_success = False

# Test 5: Check AgentCore integration
print("\n[Test 5] Testing AgentCore integration...")
agent_success = True
try:
    from app.agent.core import AgentCore
    agent = AgentCore()
    has_rag = hasattr(agent, 'rag_pipeline')
    print(f"  [OK] AgentCore imported")
    print(f"  [{'OK' if has_rag else 'FAIL'}] AgentCore has rag_pipeline: {has_rag}")
    if not has_rag:
        agent_success = False
except Exception as e:
    print(f"  [FAIL] AgentCore: {e}")
    agent_success = False

print("\n" + "=" * 60)
print("Migration Test Summary")
print("=" * 60)

if all_exist and import_success and agent_success:
    print("[SUCCESS] RAG system migration completed successfully!")
    print("All files copied, imports working, AgentCore integrated.")
else:
    print("[PARTIAL] Some issues detected:")
    if not all_exist:
        print("  - Some files are missing")
    if not import_success:
        print("  - Some imports failed")
    if not agent_success:
        print("  - AgentCore integration issue")

print("=" * 60)
