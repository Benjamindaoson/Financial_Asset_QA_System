"""
Main Ingestion Pipeline.
Orchestrates: Input -> Route -> Parse -> Output.
"""
import logging
import os
import json
import time
import hashlib
from typing import Optional
from datetime import datetime

from trust_rag.engine.ingest.models import DocInput, IngestResult, Chunk, Granularity
from trust_rag.engine.ingest.router import IngestionRouter
from trust_rag.engine.ingest.language import LanguageDetector
from trust_rag.engine.ingest.profile import ProfileManager
from trust_rag.engine.ingest.quality import QualityGate
from trust_rag.engine.ingest.validator import DocIRValidator
from trust_rag.engine.ingest.context import ingest_profile_context
from trust_rag.engine.ingest.chunking.table_chunker import TableAtomicChunker
from trust_rag.engine.ingest.chunking.enricher import ContextEnricher
from trust_rag.engine.ingest.preflight import PreflightGate, GateStatus
from trust_rag.engine.ingest.processor import DocumentProcessor

logger = logging.getLogger(__name__)

class IngestPipeline:
    """
    structured Multimodal Ingestion Pipeline.
    """
    
    def __init__(self, output_dir: str = "artifacts/ingestion"):
        self.router = IngestionRouter()
        self.lang_detector = LanguageDetector()
        self.output_dir = output_dir
        self.profile_manager = ProfileManager()
        self.quality_gate = QualityGate()
        self.validator = DocIRValidator()
        self.table_chunker = TableAtomicChunker()
        self.context_enricher = ContextEnricher()
        self.preflight_gate = PreflightGate()
        self.doc_processor = DocumentProcessor()
    
    def ingest(self, input_path: str, doc_id: Optional[str] = None, ingest_profile: str = "generic", use_new_processor: bool = False, document_group_id: Optional[str] = None, version_tag: Optional[str] = None) -> IngestResult:
        """
        Ingest a single document.
        
        Args:
            input_path: Path to the input file
            doc_id: Optional document ID (will be generated if not provided)
            ingest_profile: Name of the ingest profile to use
        
        Returns:
            IngestResult with chunks, metadata, and provenance
        """
        start_time = time.time()
        errors = []
        
        # Load Profile
        profile = self.profile_manager.get_profile(ingest_profile)
        logger.info(f"Using Ingest Profile: {profile.name}")
        
        # Create DocInput
        doc_input = DocInput(path=input_path)
        content_type = doc_input.infer_content_type()
        content_hash = doc_input.compute_content_hash()
        
        # Generate doc_id if not provided
        if not doc_id:
            filename = os.path.basename(input_path)
            doc_id = f"{filename}_{content_hash}"
        
        logger.info(f"Ingesting {input_path} (type={content_type}, doc_id={doc_id})")

        chunks = []
        parser_used = "none"
        language = "unknown"
        modality = content_type

        # Use new document processor if requested
        if use_new_processor:
            try:
                chunks, metadata = self.doc_processor.process_file(input_path, doc_id)
                parser_used = "document_processor"
                language = metadata.language if hasattr(metadata, 'language') else "unknown"
                modality = getattr(metadata, 'modality', content_type) or content_type
                # Convert chunks to expected format if needed
                return IngestResult(
                    doc_id=doc_id,
                    language=language,
                    modality=modality,
                    chunks=chunks,
                    parser_used=parser_used,
                    content_hash=content_hash,
                    ingest_time_ms=int((time.time() - start_time) * 1000),
                    errors=errors,
                    ingest_status="OK",
                    ingest_status_reason=[],
                    quality_report=None
                )
            except Exception as e:
                logger.warning(f"New processor failed, falling back to legacy: {e}")
                errors.append(f"New processor failed: {e}")
                # Fall through to legacy processing
        
        # Route to parser
        try:
            route_decision = self.router.route(input_path, content_type)
            language = route_decision.language
            modality = route_decision.content_type
            parser_used = route_decision.parser.name
            
            # Parse with Profile Context
            with ingest_profile_context(profile):
                try:
                    chunks = route_decision.parser.parse(input_path, doc_id, route_decision.language)
                except Exception as e:
                    logger.warning(f"Primary parser {parser_used} failed: {e}")
                    errors.append(f"Primary parser failed: {e}")
                    
                    # Try fallback
                    if route_decision.fallback_parser:
                        try:
                            parser_used = route_decision.fallback_parser.name
                            chunks = route_decision.fallback_parser.parse(input_path, doc_id, route_decision.language)
                            errors.append(f"Fell back to {parser_used}")
                        except Exception as e2:
                            errors.append(f"Fallback parser also failed: {e2}")
        except ValueError as e:
            errors.append(str(e))
        
        # --- Apply Smart Chunking ---
        if profile.chunking_strategy == "intelligent":
            try:
                from trust_rag.core.offline.smart_chunker import SmartChunker
                chunker = SmartChunker()
                # Convert chunks to parsed doc format for chunker
                parsed_doc = {
                    "pages": [{"text": chunk.text, "page_number": getattr(chunk.provenance, 'page_number', 1)}
                             for chunk in chunks]
                }
                chunked_docs = chunker.chunk_document(parsed_doc)
                # Convert back to Chunk objects
                chunks = []
                for chunk_data in chunked_docs:
                    from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
                    chunk = Chunk(
                        evidence_id=chunk_data["chunk_id"],
                        text=chunk_data["text"],
                        provenance=ChunkProvenance(
                            doc_id=doc_id,
                            page_number=chunk_data["source_page"],
                            source_path=input_path
                        ),
                        metadata=chunk_data
                    )
                    chunks.append(chunk)
                logger.info(f"Applied intelligent chunking: {len(chunks)} chunks generated")
            except Exception as e:
                logger.warning(f"Intelligent chunking failed, using original chunks: {e}")

        # --- Pre-flight Gate: Catch parsing pollution BEFORE embedding ---
        preflight_result = self.preflight_gate.evaluate(chunks)
        logger.info(f"Preflight: status={preflight_result.gate_status}, anomaly={preflight_result.anomaly_score:.2f}")

        if preflight_result.gate_status == GateStatus.FAILED:
            # Document rejected - do not proceed to indexing, but save to quarantine
            result = IngestResult(
                doc_id=doc_id,
                language=language,
                modality=modality,
                chunks=[],  # No chunks for failed documents
                parser_used=parser_used,
                content_hash=content_hash,
                ingest_time_ms=int((time.time() - start_time) * 1000),
                errors=errors + [f"Preflight FAILED: {preflight_result.gate_reason}"],
                ingest_profile=profile.name,
                ingest_status="FAILED",
                ingest_status_reason=["PREFLIGHT_FAILED", preflight_result.gate_reason]
            )
            self._write_artifacts(result)
            return result
        
        # --- Guardrails Phase 1: Quality Gate ---
        # Evaluate BEFORE processing (raw output)
        q_report = self.quality_gate.evaluate(chunks)
        
        # Determine provisional status (combine preflight and quality)
        status = "OK"
        if preflight_result.gate_status == GateStatus.DEGRADED:
            status = "DEGRADED"
        if q_report.layout_integrity == "INVALID":
             status = "FAILED"
        elif q_report.ocr_confidence < self.quality_gate.ocr_threshold:
             status = "DEGRADED"
        
        # --- Phase F: Structural Chunking & Enrichment ---
        # Only process if status is not FAILED (and potentially skip table chunking if DEGRADED?)
        
        final_chunks = []
        if status != "FAILED":
            # 1. Structural Chunking
            for chunk in chunks:
                final_chunks.append(chunk) # Always keep the composite chunk
                
                # If Table and NOT DEGRADED, generate atomic rows
                if chunk.provenance.modality == "table" and status != "DEGRADED":
                    # Check if table structure exists in metadata
                    table_structure = chunk.metadata.get("table_structure")
                    if table_structure:
                        try:
                            rows = self.table_chunker.chunk_table(chunk, table_structure)
                            final_chunks.extend(rows)
                        except Exception as e:
                            logger.warn(f"Failed to chunk table {chunk.evidence_id}: {e}")
                            # Don't fail ingestion, just skip atomic chunks
                            errors.append(f"Table chunking failed: {e}")
            
            # 2. Context Enrichment
            final_chunks = self.context_enricher.enrich(final_chunks)
        else:
             final_chunks = [] # clear chunks if failed

        # --- Guardrails Phase 2: DocIR Validation ---
        # Build provisional result for validation
        temp_result = IngestResult(
            doc_id=doc_id,
            language=language,
            modality=modality,
            chunks=final_chunks,
            parser_used=parser_used,
            content_hash=content_hash,
            ingest_time_ms=0, # temp
            errors=errors
        )
        v_report = self.validator.validate(temp_result)
        
        # --- Determine Final Status ---
        status_reasons = []
        
        if errors:
             if not chunks:
                 status = "FAILED"
                 status_reasons.append("PARSING_FAILED")

        if v_report.status == "INVALID":
            status = "FAILED"
            status_reasons.append("DOCIR_INVALID")
            status_reasons.extend([f"Validation: {k}={v}" for k,v in v_report.issues.dict().items() if v > 0])
             
        elif v_report.status == "DEGRADED":
             if status != "FAILED":
                 status = "DEGRADED"
             status_reasons.append("DOCIR_DEGRADED")
             status_reasons.extend([f"Validation: {k}={v}" for k,v in v_report.issues.dict().items() if v > 0])

        if q_report.layout_integrity == "INVALID":
             status = "FAILED"
             status_reasons.append("LAYOUT_INTEGRITY_VIOLATION")
        
        if q_report.ocr_confidence < self.quality_gate.ocr_threshold:
             if status != "FAILED":
                status = "DEGRADED"
             status_reasons.append("LOW_OCR_CONFIDENCE")

        # Build final result
        ingest_time_ms = int((time.time() - start_time) * 1000)
        
        result = IngestResult(
            doc_id=doc_id,
            language=language,
            modality=modality,
            chunks=final_chunks if status != "FAILED" else [],
            parser_used=parser_used,
            content_hash=content_hash,
            ingest_time_ms=ingest_time_ms,
            errors=errors,
            ingest_profile=profile.name,
            ingest_status=status,
            ingest_status_reason=status_reasons,
            quality_report=q_report.dict(),
            docir_validation=v_report.dict(),
            document_group_id=document_group_id,
            version_tag=version_tag
        )
        
        # Write output artifacts
        self._write_artifacts(result)
        
        logger.info(f"Ingested {doc_id}: Status={status} in {ingest_time_ms}ms")
        
        return result
    
    def _write_artifacts(self, result: IngestResult):
        """Write output artifacts to disk."""
        base_dir = self.output_dir
        if result.ingest_status == "FAILED":
            # QUARANTINE: Don't pollute main index, but save for human review
            base_dir = os.path.join(os.path.dirname(self.output_dir), "quarantine")
            logger.warning(f"Document {result.doc_id} FAILED validation. Moving to quarantine: {base_dir}")
        elif result.ingest_status == "DEGRADED":
            logger.warning(f"Document {result.doc_id} DEGRADED but accepted.")
            
        doc_dir = os.path.join(base_dir, result.doc_id)
        os.makedirs(doc_dir, exist_ok=True)
        
        # 1. chunks.jsonl
        chunks_path = os.path.join(doc_dir, "chunks.jsonl")
        with open(chunks_path, "w", encoding="utf-8") as f:
            for chunk in result.chunks:
                # Flatten for retrieval compatibility
                row = {
                    "evidence_id": chunk.evidence_id,
                    "text": chunk.text,
                    "doc_id": chunk.provenance.doc_id,
                    "page_number": chunk.provenance.page_number,
                    "bbox": chunk.provenance.bbox,
                    "source_path": chunk.provenance.source_path,
                    "parser_name": chunk.provenance.parser_name,
                    "language": chunk.provenance.language,
                    "modality": chunk.provenance.modality,
                    "block_index": chunk.provenance.block_index,
                    "parent_id": chunk.parent_id,
                    "granularity": chunk.granularity,
                    "document_group_id": result.document_group_id,
                    "version_tag": result.version_tag,
                    **chunk.metadata,
                    **chunk.semantic_context # Flatten semantic context too? Or keep nested? Keep nested for structured use, prompt builder will handle it.
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        
        # 2. doc_index.json
        index_path = os.path.join(doc_dir, "doc_index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({
                "doc_id": result.doc_id,
                "language": result.language,
                "modality": result.modality,
                "chunk_count": len(result.chunks),
                "parser_used": result.parser_used,
                "content_hash": result.content_hash,
                "ingest_status": result.ingest_status,
                "ingest_profile": result.ingest_profile
            }, f, indent=2, ensure_ascii=False)
        
        # 3. run_manifest.json
        manifest_path = os.path.join(doc_dir, "run_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            # Dump entire result as dict
            json.dump(result.dict(), f, indent=2, ensure_ascii=False)
