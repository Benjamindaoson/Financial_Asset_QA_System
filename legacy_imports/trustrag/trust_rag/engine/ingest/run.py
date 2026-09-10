"""
CLI for Ingestion Pipeline.
Usage: python -m trust_rag.ingest.run --input <path> --out <output_dir>
"""
import argparse
import sys
import os
import logging

# Ensure root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from trust_rag.engine.ingest.pipeline import IngestPipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description="TrustRAG Multimodal Ingestion")
    parser.add_argument("--input", required=True, help="Path to input file")
    parser.add_argument("--out", default="artifacts/ingestion", help="Output directory")
    parser.add_argument("--doc-id", help="Optional document ID")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    pipeline = IngestPipeline(output_dir=args.out)
    
    try:
        result = pipeline.ingest(args.input, doc_id=args.doc_id)
        
        print(f"\n=== Ingestion Complete ===")
        print(f"Document ID: {result.doc_id}")
        print(f"Language: {result.language}")
        print(f"Modality: {result.modality}")
        print(f"Parser: {result.parser_used}")
        print(f"Chunks: {len(result.chunks)}")
        print(f"Time: {result.ingest_time_ms}ms")
        
        if result.errors:
            print(f"Warnings: {result.errors}")
        
        print(f"\nArtifacts written to: {args.out}/{result.doc_id}/")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
