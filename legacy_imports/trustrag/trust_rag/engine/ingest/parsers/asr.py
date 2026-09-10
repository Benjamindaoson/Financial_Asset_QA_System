"""
ASR Parser using Whisper.
"""
import logging
import os
from typing import List
from trust_rag.engine.ingest.parsers.base import BaseIngestParser
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
from trust_rag.engine.ingest.evidence_id import generate_evidence_id

logger = logging.getLogger(__name__)

class WhisperASRParser(BaseIngestParser):
    """
    ASR Parser using OpenAI Whisper.
    Supports both Chinese and English audio.
    """
    name = "whisper_asr"
    
    def is_available(self) -> bool:
        try:
            import whisper
            return True
        except ImportError:
            try:
                from faster_whisper import WhisperModel
                return True
            except ImportError:
                return False
    
    def parse(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        # Prefer faster-whisper if available
        try:
            return self._parse_with_faster_whisper(path, doc_id, language)
        except ImportError:
            pass
        
        # Fallback to openai-whisper
        return self._parse_with_openai_whisper(path, doc_id, language)
    
    def _parse_with_faster_whisper(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        from faster_whisper import WhisperModel
        
        model = WhisperModel("large-v3", device="cpu", compute_type="int8")
        
        lang_code = None
        if language == "zh":
            lang_code = "zh"
        elif language == "en":
            lang_code = "en"
        
        segments, info = model.transcribe(path, language=lang_code)
        
        chunks = []
        block_index = 0
        
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            
            evidence_id = generate_evidence_id(doc_id, 1, block_index, text)
            
            prov = ChunkProvenance(
                doc_id=doc_id,
                page_number=1,
                bbox=None,
                source_path=path,
                parser_name=self.name,
                language=info.language or language,
                modality="audio",
                block_index=block_index
            )
            prov.metadata = {
                "start_ms": int(segment.start * 1000),
                "end_ms": int(segment.end * 1000)
            }
            
            chunks.append(Chunk(
                evidence_id=evidence_id,
                text=text,
                provenance=prov,
                metadata={"start_ms": int(segment.start * 1000), "end_ms": int(segment.end * 1000)}
            ))
            block_index += 1
        
        return chunks
    
    def _parse_with_openai_whisper(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        import whisper
        
        model = whisper.load_model("large-v3")
        
        lang_code = None
        if language == "zh":
            lang_code = "zh"
        elif language == "en":
            lang_code = "en"
        
        result = model.transcribe(path, language=lang_code)
        
        chunks = []
        block_index = 0
        
        for segment in result["segments"]:
            text = segment["text"].strip()
            if not text:
                continue
            
            evidence_id = generate_evidence_id(doc_id, 1, block_index, text)
            
            prov = ChunkProvenance(
                doc_id=doc_id,
                page_number=1,
                bbox=None,
                source_path=path,
                parser_name=self.name,
                language=result.get("language", language),
                modality="audio",
                block_index=block_index
            )
            
            chunks.append(Chunk(
                evidence_id=evidence_id,
                text=text,
                provenance=prov,
                metadata={"start_ms": int(segment["start"] * 1000), "end_ms": int(segment["end"] * 1000)}
            ))
            block_index += 1
        
        return chunks
