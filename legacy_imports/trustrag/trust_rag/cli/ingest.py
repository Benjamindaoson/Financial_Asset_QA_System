"""
TrustRAG Document Ingestion CLI.

Usage:
    python -m trust_rag.cli.ingest <file_path> [--doc-id ID] [--profile PROFILE]
    python -m trust_rag.cli.ingest --batch <directory> [--profile PROFILE]
    
Examples:
    python -m trust_rag.cli.ingest artifacts/raw_docs/nvidia_fy2023.pdf
    python -m trust_rag.cli.ingest --batch artifacts/raw_docs/
"""
import argparse
import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Optional

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trust_rag.engine.ingest.pipeline import IngestPipeline
from trust_rag.config import get_config, get_paths

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ingest_single(
    file_path: str,
    doc_id: Optional[str] = None,
    profile: str = "generic",
    output_dir: Optional[str] = None
) -> dict:
    """
    Ingest a single document.
    
    Args:
        file_path: Path to document file
        doc_id: Optional document ID
        profile: Ingest profile name
        output_dir: Output directory for artifacts
        
    Returns:
        Ingest result dictionary
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    output_dir = output_dir or get_paths().ingestion_dir
    pipeline = IngestPipeline(output_dir=output_dir)
    
    logger.info(f"Ingesting: {file_path}")
    result = pipeline.ingest(file_path, doc_id=doc_id, ingest_profile=profile)
    
    return {
        "doc_id": result.doc_id,
        "status": result.ingest_status,
        "chunks_count": len(result.chunks),
        "parser_used": result.parser_used,
        "language": result.language,
        "modality": result.modality,
        "ingest_time_ms": result.ingest_time_ms,
        "errors": result.errors,
        "status_reasons": result.ingest_status_reason
    }


def ingest_batch(
    directory: str,
    profile: str = "generic",
    output_dir: Optional[str] = None,
    extensions: List[str] = None
) -> List[dict]:
    """
    Ingest all documents in a directory.
    
    Args:
        directory: Directory containing documents
        profile: Ingest profile name
        output_dir: Output directory for artifacts
        extensions: File extensions to process (default: pdf, html, txt)
        
    Returns:
        List of ingest results
    """
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Not a directory: {directory}")
    
    extensions = extensions or ['.pdf', '.html', '.txt', '.csv', '.xlsx']
    extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions]
    
    results = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in extensions:
                continue
            
            file_path = os.path.join(root, file)
            
            try:
                result = ingest_single(file_path, profile=profile, output_dir=output_dir)
                results.append(result)
                
                status_emoji = "✅" if result["status"] == "OK" else "⚠️" if result["status"] == "DEGRADED" else "❌"
                logger.info(f"{status_emoji} {file}: {result['status']} ({result['chunks_count']} chunks)")
                
            except Exception as e:
                logger.error(f"Failed to ingest {file}: {e}")
                results.append({
                    "doc_id": file,
                    "status": "FAILED",
                    "error": str(e)
                })
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="TrustRAG Document Ingestion CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    Ingest a single file:
        python -m trust_rag.cli.ingest report.pdf
        
    Ingest with custom doc ID:
        python -m trust_rag.cli.ingest report.pdf --doc-id nvidia_2023
        
    Batch ingest a directory:
        python -m trust_rag.cli.ingest --batch ./documents/
        
    Use specific profile:
        python -m trust_rag.cli.ingest report.pdf --profile financial
        """
    )
    
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to document file to ingest"
    )
    
    parser.add_argument(
        "--batch",
        metavar="DIR",
        help="Batch ingest all documents in directory"
    )
    
    parser.add_argument(
        "--doc-id",
        help="Custom document ID (for single file)"
    )
    
    parser.add_argument(
        "--profile",
        default="generic",
        help="Ingest profile to use (default: generic)"
    )
    
    parser.add_argument(
        "--output-dir",
        help="Output directory for artifacts"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    if not args.file and not args.batch:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.batch:
            results = ingest_batch(
                args.batch,
                profile=args.profile,
                output_dir=args.output_dir
            )
            
            # Summary
            ok_count = sum(1 for r in results if r.get("status") == "OK")
            degraded_count = sum(1 for r in results if r.get("status") == "DEGRADED")
            failed_count = sum(1 for r in results if r.get("status") == "FAILED")
            
            if args.json:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                print("\n" + "=" * 50)
                print("Batch Ingestion Complete")
                print("=" * 50)
                print(f"✅ OK:       {ok_count}")
                print(f"⚠️  DEGRADED: {degraded_count}")
                print(f"❌ FAILED:   {failed_count}")
                print(f"Total:      {len(results)}")
        
        else:
            result = ingest_single(
                args.file,
                doc_id=args.doc_id,
                profile=args.profile,
                output_dir=args.output_dir
            )
            
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print("\n" + "=" * 50)
                print("Document Ingestion Complete")
                print("=" * 50)
                print(f"Doc ID:     {result['doc_id']}")
                print(f"Status:     {result['status']}")
                print(f"Chunks:     {result['chunks_count']}")
                print(f"Parser:     {result['parser_used']}")
                print(f"Language:   {result['language']}")
                print(f"Time:       {result['ingest_time_ms']}ms")
                
                if result['errors']:
                    print(f"\nWarnings/Errors:")
                    for err in result['errors']:
                        print(f"  - {err}")
    
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()



