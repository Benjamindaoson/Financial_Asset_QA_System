"""
TrustRAG Query CLI.

Usage:
    python -m trust_rag.cli.query "What was Nvidia's revenue for FY2023?"
    python -m trust_rag.cli.query --interactive
"""
import argparse
import sys
import json
import logging
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trust_rag.system import TrustRAG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_result(result, verbose: bool = False) -> str:
    """Format system result for display."""
    lines = []
    
    # Verdict
    verdict_emoji = {
        "VERIFIED": "✅",
        "REFUSED": "❌",
        "CONFLICT": "⚠️"
    }
    lines.append(f"\n{verdict_emoji.get(result.verdict, '?')} Verdict: {result.verdict}")
    
    # Answer
    if result.answer:
        lines.append(f"\n📝 Answer: {result.answer.text}")
        lines.append(f"   Confidence: {result.answer.confidence:.1%}")
    
    # Reasons
    if result.reasons:
        lines.append(f"\n📋 Reasons:")
        for reason in result.reasons[:3]:
            lines.append(f"   - {reason}")
    
    # Evidence
    if result.evidence:
        lines.append(f"\n📚 Evidence ({len(result.evidence)} items):")
        for ev in result.evidence[:3]:
            lines.append(f"   - {ev.source} (p.{ev.page}): {ev.value[:80]}...")
    
    # Trace ID
    lines.append(f"\n🔍 Trace ID: {result.trace_id}")
    
    # Verbose: risk flags and verification
    if verbose:
        if result.risk_flags:
            lines.append(f"\n⚡ Risk Flags: {result.risk_flags}")
        if result.verification_data:
            lines.append(f"📊 Verification: {result.verification_data}")
    
    return "\n".join(lines)


def interactive_mode(rag: TrustRAG):
    """Run interactive query mode."""
    print("\n" + "=" * 60)
    print("TrustRAG Interactive Mode")
    print("=" * 60)
    print("Enter your questions. Type 'quit' or 'exit' to stop.")
    print("Type 'stats' to see index statistics.")
    print("=" * 60 + "\n")
    
    while True:
        try:
            query = input("📎 Query: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if query.lower() == 'stats':
                stats = rag.get_index_stats()
                print(f"\n📊 Index Statistics:")
                print(f"   Documents: {stats['documents_loaded']}")
                print(f"   Total chunks: {stats['total_chunks']}")
                print(f"   By tier: {stats['chunks_by_tier']}\n")
                continue
            
            result = rag.process_query(query)
            print(format_result(result, verbose=False))
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="TrustRAG Query CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "query",
        nargs="?",
        help="Query to process"
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    
    parser.add_argument(
        "--risk-level",
        default="medium",
        choices=["low", "medium", "high"],
        help="Risk level for query processing"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show verbose output"
    )
    
    parser.add_argument(
        "--artifact-dir",
        default="artifacts",
        help="Artifact directory"
    )
    
    args = parser.parse_args()
    
    if not args.query and not args.interactive:
        parser.print_help()
        sys.exit(1)
    
    # Initialize system
    print("Initializing TrustRAG...")
    rag = TrustRAG(artifact_dir=args.artifact_dir)
    
    # Show index stats
    stats = rag.get_index_stats()
    print(f"Loaded {stats['total_chunks']} chunks from {stats['documents_loaded']} documents")
    
    if args.interactive:
        interactive_mode(rag)
    else:
        result = rag.process_query(args.query, risk_level=args.risk_level)
        
        if args.json:
            print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
        else:
            print(format_result(result, verbose=args.verbose))


if __name__ == "__main__":
    main()



