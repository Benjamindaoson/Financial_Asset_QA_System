"""
IndexLoader: Loads ingested chunks into RetrievalAdapter.
Bridges ingestion artifacts with retrieval layer.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from trust_rag.config import get_config, get_paths
from trust_rag.engine.retrieval.vector_store import VectorChunk
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class LoadedIndex:
    """Result of index loading operation."""
    total_chunks: int
    documents: List[str]
    tiers: Dict[str, int]
    load_errors: List[str]

class IndexLoader:
    """
    Loads chunks from ingestion artifacts into retrieval adapter.
    Supports hot-reload and incremental updates.
    """
    
    def __init__(self, ingestion_dir: Optional[str] = None):
        self.ingestion_dir = ingestion_dir or get_paths().ingestion_dir
        self._loaded_docs: set = set()
        self._all_chunks: List[Dict] = []
    
    def load_all_chunks(self) -> List[Dict]:
        """
        Load all chunks from ingestion directory.
        Scans all doc subdirectories for chunks.jsonl files.
        """
        all_chunks = []
        errors = []
        
        if not os.path.exists(self.ingestion_dir):
            logger.warning(f"Ingestion directory not found: {self.ingestion_dir}")
            return all_chunks
        
        for doc_dir in os.listdir(self.ingestion_dir):
            doc_path = os.path.join(self.ingestion_dir, doc_dir)
            
            if not os.path.isdir(doc_path):
                continue
            
            chunks_path = os.path.join(doc_path, "chunks.jsonl")
            
            if not os.path.exists(chunks_path):
                continue
            
            try:
                with open(chunks_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            # Add doc_dir as fallback doc_id if not present
                            if "doc_id" not in chunk:
                                chunk["doc_id"] = doc_dir
                            all_chunks.append(chunk)
                        except json.JSONDecodeError as e:
                            errors.append(f"{chunks_path}:{line_num}: {e}")
                
                self._loaded_docs.add(doc_dir)
                logger.info(f"Loaded chunks from {doc_dir}")
                
            except Exception as e:
                errors.append(f"Failed to load {chunks_path}: {e}")
                logger.error(f"Failed to load {chunks_path}: {e}")
        
        if errors:
            logger.warning(f"Index loading had {len(errors)} errors")
        
        self._all_chunks = all_chunks
        logger.info(f"Loaded {len(all_chunks)} total chunks from {len(self._loaded_docs)} documents")
        
        return all_chunks
    
    def load_new_chunks(self) -> List[Dict]:
        """
        Load only chunks from newly ingested documents.
        Used for incremental index updates.
        """
        new_chunks = []
        
        if not os.path.exists(self.ingestion_dir):
            return new_chunks
        
        for doc_dir in os.listdir(self.ingestion_dir):
            if doc_dir in self._loaded_docs:
                continue
            
            doc_path = os.path.join(self.ingestion_dir, doc_dir)
            
            if not os.path.isdir(doc_path):
                continue
            
            chunks_path = os.path.join(doc_path, "chunks.jsonl")
            
            if not os.path.exists(chunks_path):
                continue
            
            try:
                with open(chunks_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        chunk = json.loads(line)
                        if "doc_id" not in chunk:
                            chunk["doc_id"] = doc_dir
                        new_chunks.append(chunk)
                
                self._loaded_docs.add(doc_dir)
                logger.info(f"Loaded new document: {doc_dir}")
                
            except Exception as e:
                logger.error(f"Failed to load new document {doc_dir}: {e}")
        
        # Add to cached chunks
        self._all_chunks.extend(new_chunks)
        
        return new_chunks
    
    def get_chunks_by_tier(self, chunks: List[Dict] = None) -> Dict[str, List[Dict]]:
        """
        Organize chunks by tier for adapter seeding.
        
        Returns:
            Dict with keys 'micro', 'base', 'macro' containing chunk lists
        """
        chunks = chunks or self._all_chunks
        
        tiers = {
            "micro": [],
            "base": [],
            "macro": []
        }
        
        for chunk in chunks:
            # Determine tier from granularity or explicit tier field
            tier = chunk.get("tier", "base")
            granularity = chunk.get("granularity", "composite")
            
            if tier == "micro" or granularity == "atomic":
                tiers["micro"].append(chunk)
            elif tier == "macro":
                tiers["macro"].append(chunk)
            else:
                # Default to base tier
                tiers["base"].append(chunk)
        
        return tiers
    
    def seed_adapter(self, adapter) -> LoadedIndex:
        """
        Load all chunks and seed them into the retrieval adapter.
        
        Args:
            adapter: RetrievalAdapter instance to seed
            
        Returns:
            LoadedIndex with statistics
        """
        # Load chunks
        chunks = self.load_all_chunks()
        
        # Organize by tier
        by_tier = self.get_chunks_by_tier(chunks)
        
        # Convert chunks and upsert into adapter
        for tier, tier_chunks in by_tier.items():
            adapter_chunks = [self._to_vector_chunk(c) for c in tier_chunks]
            if adapter_chunks:
                adapter.add_chunks(adapter_chunks)
                logger.info(f"Seeded {len(adapter_chunks)} chunks to {tier} tier")
        
        return LoadedIndex(
            total_chunks=len(chunks),
            documents=list(self._loaded_docs),
            tiers={k: len(v) for k, v in by_tier.items()},
            load_errors=[]
        )
    
    def refresh_adapter(self, adapter) -> int:
        """
        Refresh adapter with newly ingested documents.
        
        Returns:
            Number of new chunks added
        """
        new_chunks = self.load_new_chunks()
        
        if not new_chunks:
            return 0
        
        # Organize by tier
        by_tier = self.get_chunks_by_tier(new_chunks)
        
        # Append to adapter (pgvector + BM25)
        for tier, tier_chunks in by_tier.items():
            if tier_chunks:
                adapter_chunks = [self._to_vector_chunk(c) for c in tier_chunks]
                adapter.add_chunks(adapter_chunks)
        
        return len(new_chunks)
    
    def _to_vector_chunk(self, chunk: Dict) -> VectorChunk:
        """Convert ingested chunk dict to VectorChunk."""
        metadata = {
            k: v for k, v in chunk.items()
            if k not in ["text", "embedding"]
        }
        return VectorChunk(
            chunk_id=chunk.get("evidence_id", f"chunk_{id(chunk)}"),
            doc_id=chunk.get("doc_id", ""),
            text=chunk.get("text", ""),
            embedding=chunk.get("embedding", []) or [],
            metadata=metadata,
            modality=chunk.get("modality", "text_native"),
            page_number=chunk.get("page_number", 0),
            chunk_index=chunk.get("block_index", 0),
            created_at=datetime.utcnow()
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current index statistics."""
        by_tier = self.get_chunks_by_tier()
        return {
            "total_chunks": len(self._all_chunks),
            "documents_loaded": len(self._loaded_docs),
            "documents": list(self._loaded_docs),
            "chunks_by_tier": {k: len(v) for k, v in by_tier.items()}
        }



