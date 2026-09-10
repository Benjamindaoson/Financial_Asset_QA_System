"""
Advanced Audio Processor for TrustRAG.
Supports Chinese + English ASR with first-class evidence modeling.
"""
import os
import logging
import tempfile
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

from trust_rag.config import get_config
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance, Granularity, ChunkTier

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages for ASR."""
    ENGLISH = "en"
    CHINESE = "zh"
    UNKNOWN = "unknown"


class ASRProvider(Enum):
    """ASR provider options."""
    GOOGLE = "google"
    WHISPER = "whisper"
    AZURE = "azure"


@dataclass
class AudioSegment:
    """Audio segment with transcription."""
    start_time: float  # Start time in seconds
    end_time: float    # End time in seconds
    text: str          # Transcribed text
    confidence: float  # Confidence score (0-1)
    language: Language # Detected language
    speaker_id: Optional[str] = None  # For speaker diarization


@dataclass
class AudioTranscription:
    """Complete audio transcription result."""
    segments: List[AudioSegment] = field(default_factory=list)
    full_text: str = ""
    language: Language = Language.UNKNOWN
    duration: float = 0.0
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AudioLanguageDetector:
    """Detect audio language automatically."""

    def detect_language(self, audio_path: str) -> Language:
        """Detect the primary language in audio file."""
        try:
            # Simple heuristic: try short transcription in different languages
            # and see which gives higher confidence

            # For now, use file naming or metadata hints
            filename = Path(audio_path).name.lower()

            if any(keyword in filename for keyword in ['chinese', 'chinese', 'zh', 'cn', 'mandarin']):
                return Language.CHINESE
            elif any(keyword in filename for keyword in ['english', 'en', 'us', 'uk']):
                return Language.ENGLISH

            # Default fallback - try both and see
            return self._detect_by_content(audio_path)

        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return Language.UNKNOWN

    def _detect_by_content(self, audio_path: str) -> Language:
        """Detect language by trying short transcription."""
        try:
            # Try English first (Google has good English detection)
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                # Get first 10 seconds
                audio = recognizer.record(source, duration=10)

                try:
                    # Try English
                    text_en = recognizer.recognize_google(audio, language='en-US')
                    if text_en and len(text_en.split()) > 3:  # Has substantial content
                        return Language.ENGLISH
                except:
                    pass

                try:
                    # Try Chinese
                    text_zh = recognizer.recognize_google(audio, language='zh-CN')
                    if text_zh and len(text_zh) > 6:  # Has substantial Chinese content
                        return Language.CHINESE
                except:
                    pass

        except Exception as e:
            logger.debug(f"Content-based detection failed: {e}")

        return Language.ENGLISH  # Default fallback


class ChineseEnglishASR:
    """
    Advanced ASR supporting both Chinese and English with high accuracy.
    """

    def __init__(self, provider: ASRProvider = ASRProvider.GOOGLE):
        self.provider = provider
        self.language_detector = AudioLanguageDetector()
        self._recognizer = None

    def _get_recognizer(self):
        """Lazy initialization of speech recognizer."""
        if self._recognizer is None:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            # Adjust for ambient noise
            self._recognizer.dynamic_energy_threshold = True
        return self._recognizer

    def transcribe_audio(self, audio_path: str) -> AudioTranscription:
        """
        Transcribe audio file with automatic language detection.
        """
        result = AudioTranscription()

        try:
            # Get audio duration
            result.duration = self._get_audio_duration(audio_path)

            # Detect language
            result.language = self.language_detector.detect_language(audio_path)

            # Choose language code for ASR
            if result.language == Language.CHINESE:
                language_code = "zh-CN"
            else:
                language_code = "en-US"

            # Perform transcription
            segments = self._transcribe_with_segments(audio_path, language_code)

            if segments:
                result.segments = segments
                result.full_text = " ".join([seg.text for seg in segments])
                result.confidence = sum(seg.confidence for seg in segments) / len(segments)

                # Update language if detected differently during transcription
                if segments and segments[0].language != result.language:
                    result.language = segments[0].language

            result.metadata = {
                'provider': self.provider.value,
                'language_code': language_code,
                'segment_count': len(segments)
            }

        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            result.metadata['error'] = str(e)

        return result

    def _transcribe_with_segments(self, audio_path: str, language_code: str) -> List[AudioSegment]:
        """Transcribe audio with time segmentation."""
        segments = []

        try:
            recognizer = self._get_recognizer()

            # For segmentation, we'll process in chunks
            # Google Speech Recognition doesn't provide timestamps by default
            # We'll use a sliding window approach

            chunk_duration = 30  # 30 seconds per chunk
            overlap = 5  # 5 second overlap

            with recognizer.AudioFile(audio_path) as source:
                audio_length = source.DURATION if hasattr(source, 'DURATION') else 0

                if audio_length == 0:
                    # Fallback: process entire audio
                    audio = recognizer.record(source)
                    text = self._recognize_audio(audio, language_code)

                    if text:
                        segment = AudioSegment(
                            start_time=0.0,
                            end_time=audio_length or len(text) * 0.1,  # Rough estimate
                            text=text,
                            confidence=0.8,  # Default confidence
                            language=Language.CHINESE if 'zh' in language_code else Language.ENGLISH
                        )
                        segments.append(segment)
                else:
                    # Process in chunks with overlap
                    current_time = 0.0

                    while current_time < audio_length:
                        chunk_start = max(0, current_time - overlap)
                        duration = min(chunk_duration + overlap, audio_length - chunk_start)

                        # Record chunk
                        audio = recognizer.record(source, offset=chunk_start, duration=duration)

                        # Transcribe chunk
                        text = self._recognize_audio(audio, language_code)

                        if text and len(text.strip()) > 0:
                            segment = AudioSegment(
                                start_time=current_time,
                                end_time=min(current_time + chunk_duration, audio_length),
                                text=text.strip(),
                                confidence=0.8,  # Could be improved with confidence scores
                                language=Language.CHINESE if 'zh' in language_code else Language.ENGLISH
                            )
                            segments.append(segment)

                        current_time += chunk_duration

        except Exception as e:
            logger.error(f"Segmented transcription failed: {e}")

        return segments

    def _recognize_audio(self, audio, language_code: str) -> Optional[str]:
        """Recognize audio using the configured provider."""
        try:
            if self.provider == ASRProvider.GOOGLE:
                return self._recognizer.recognize_google(audio, language=language_code)
            elif self.provider == ASRProvider.WHISPER:
                # Placeholder for Whisper implementation
                logger.warning("Whisper provider not fully implemented, using Google fallback")
                return self._recognizer.recognize_google(audio, language=language_code)
            else:
                logger.error(f"Unsupported ASR provider: {self.provider}")
                return None
        except Exception as e:
            logger.debug(f"Audio recognition failed for {language_code}: {e}")
            return None

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio file duration in seconds."""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # Convert to seconds
        except ImportError:
            logger.warning("pydub not installed, cannot get audio duration")
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}")
            return 0.0


class AudioEvidenceProcessor:
    """
    Process audio files into first-class evidence for RAG.
    """

    def __init__(self):
        self.config = get_config().document_processing
        self.asr = ChineseEnglishASR()

    def process_audio(self, audio_path: str, doc_id: Optional[str] = None) -> Tuple[List[Chunk], Dict[str, Any]]:
        """
        Process audio file into evidence-ready chunks.
        """
        chunks = []
        metadata = {}

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Generate doc_id
        if not doc_id:
            filename = Path(audio_path).name
            file_hash = hash(open(audio_path, 'rb').read()) % 10000
            doc_id = f"{filename}_{file_hash}"

        try:
            # Transcribe audio
            transcription = self.asr.transcribe_audio(audio_path)

            # Convert to chunks
            audio_chunks = self._transcription_to_chunks(transcription, audio_path, doc_id)
            chunks.extend(audio_chunks)

            # Build metadata
            metadata = {
                'duration': transcription.duration,
                'language': transcription.language.value,
                'confidence': transcription.confidence,
                'segment_count': len(transcription.segments),
                'full_text': transcription.full_text,
                'asr_provider': transcription.metadata.get('provider', 'unknown')
            }

        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            # Create error chunk
            error_chunk = Chunk(
                evidence_id=f"{doc_id}_error",
                text=f"Audio processing failed: {str(e)}",
                provenance=ChunkProvenance(
                    doc_id=doc_id,
                    source_path=audio_path,
                    parser_name="audio_processor",
                    language="unknown",
                    modality="audio",
                    block_index=0
                ),
                granularity=Granularity.ATOMIC,
                tier=ChunkTier.MICRO,
                metadata={'processing_error': str(e)}
            )
            chunks.append(error_chunk)

        return chunks, metadata

    def _transcription_to_chunks(self, transcription: AudioTranscription, audio_path: str, doc_id: str) -> List[Chunk]:
        """Convert transcription to RAG chunks."""
        chunks = []

        if not transcription.segments:
            # No transcription available
            chunk = Chunk(
                evidence_id=f"{doc_id}_no_transcription",
                text="Audio transcription unavailable or failed.",
                provenance=ChunkProvenance(
                    doc_id=doc_id,
                    source_path=audio_path,
                    parser_name="audio_processor",
                    language=transcription.language.value,
                    modality="audio",
                    block_index=0
                ),
                granularity=Granularity.ATOMIC,
                tier=ChunkTier.MICRO,
                metadata={
                    'transcription_failed': True,
                    'duration': transcription.duration
                }
            )
            chunks.append(chunk)
            return chunks

        # Process each segment
        for i, segment in enumerate(transcription.segments):
            # Skip very short or low-confidence segments
            if len(segment.text.strip()) < 5 or segment.confidence < 0.3:
                continue

            # Create chunk for this segment
            chunk_id = f"{doc_id}_seg_{i}"
            evidence_id = f"ev_{chunk_id}"

            # Format time stamps
            start_time_str = self._format_timestamp(segment.start_time)
            end_time_str = self._format_timestamp(segment.end_time)

            # Create chunk text with timing
            chunk_text = f"[{start_time_str}-{end_time_str}] {segment.text}"

            provenance = ChunkProvenance(
                doc_id=doc_id,
                source_path=audio_path,
                parser_name="audio_processor",
                language=segment.language.value,
                modality="audio",
                block_index=i
            )

            chunk = Chunk(
                evidence_id=evidence_id,
                text=chunk_text,
                provenance=provenance,
                granularity=Granularity.ATOMIC,
                tier=ChunkTier.MICRO,
                metadata={
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'confidence': segment.confidence,
                    'speaker_id': segment.speaker_id,
                    'segment_index': i,
                    'asr_provider': transcription.metadata.get('provider', 'unknown')
                }
            )

            chunks.append(chunk)

        # If we have multiple segments, also create a summary chunk
        if len(chunks) > 1:
            summary_text = f"Audio transcription summary: {transcription.full_text[:500]}{'...' if len(transcription.full_text) > 500 else ''}"

            summary_chunk = Chunk(
                evidence_id=f"{doc_id}_summary",
                text=summary_text,
                provenance=ChunkProvenance(
                    doc_id=doc_id,
                    source_path=audio_path,
                    parser_name="audio_processor",
                    language=transcription.language.value,
                    modality="audio",
                    block_index=-1  # Special marker for summary
                ),
                granularity=Granularity.COMPOSITE,
                tier=ChunkTier.BASE,
                metadata={
                    'is_summary': True,
                    'total_segments': len(chunks),
                    'full_duration': transcription.duration,
                    'average_confidence': transcription.confidence
                }
            )

            chunks.append(summary_chunk)

        return chunks

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds into HH:MM:SS or MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return "02d"
        else:
            return "02d"

    def validate_audio_evidence(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """
        Validate audio evidence quality and provide assessment.
        """
        validation = {
            'total_chunks': len(chunks),
            'audio_chunks': 0,
            'summary_chunks': 0,
            'average_confidence': 0.0,
            'low_confidence_chunks': 0,
            'total_duration': 0.0,
            'language_distribution': {},
            'quality_assessment': 'unknown'
        }

        confidences = []
        languages = []

        for chunk in chunks:
            if chunk.provenance.modality == 'audio':
                validation['audio_chunks'] += 1

                confidence = chunk.metadata.get('confidence', 0.0)
                confidences.append(confidence)

                if confidence < 0.5:
                    validation['low_confidence_chunks'] += 1

                language = chunk.provenance.language
                languages.append(language)

                duration = chunk.metadata.get('end_time', 0) - chunk.metadata.get('start_time', 0)
                validation['total_duration'] += duration

                if chunk.metadata.get('is_summary'):
                    validation['summary_chunks'] += 1

        if confidences:
            validation['average_confidence'] = sum(confidences) / len(confidences)

        # Language distribution
        for lang in languages:
            validation['language_distribution'][lang] = validation['language_distribution'].get(lang, 0) + 1

        # Quality assessment
        if validation['audio_chunks'] == 0:
            validation['quality_assessment'] = 'failed'
        elif validation['average_confidence'] > 0.8 and validation['low_confidence_chunks'] == 0:
            validation['quality_assessment'] = 'high'
        elif validation['average_confidence'] > 0.6:
            validation['quality_assessment'] = 'medium'
        else:
            validation['quality_assessment'] = 'low'

        return validation

