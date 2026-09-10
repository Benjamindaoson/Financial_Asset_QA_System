"""
Realtime Audio Transcriber for GraphRAG.

This module provides real-time audio transcription capabilities for live audio streams.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import threading
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor
import numpy as np

logger = logging.getLogger(__name__)


class RealtimeTranscriber:
    """
    Real-time audio transcription with streaming support.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize real-time transcriber.

        Args:
            config: Real-time transcription configuration
        """
        self.config = config or {}

        # Real-time performance targets
        self.target_latency = self.config.get('target_latency', 1.0)  # 1 second target
        self.buffer_size_seconds = self.config.get('buffer_size_seconds', 3.0)  # 3 second buffer
        self.chunk_size_seconds = self.config.get('chunk_size_seconds', 0.5)  # 0.5 second chunks

        # Audio processing
        self.sample_rate = self.config.get('sample_rate', 16000)
        self.channels = self.config.get('channels', 1)

        # ASR backend
        self.backend = self.config.get('backend', 'whisper')
        self.asr_model = None

        # Streaming state
        self.is_streaming = False
        self.audio_buffer = queue.Queue()
        self.transcription_queue = queue.Queue()
        self.stream_thread = None
        self.processing_thread = None

        # Callbacks
        self.on_transcription: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None

        # Performance monitoring
        self.latencies = []
        self.max_latency_history = 100

        # Initialize ASR model
        self._init_asr_model()

        logger.info("Realtime transcriber initialized")

    def _init_asr_model(self):
        """Initialize ASR model for real-time processing."""
        try:
            if self.backend == 'whisper':
                import whisper
                # Use smaller model for real-time processing
                model_size = self.config.get('whisper_model', 'tiny')
                self.asr_model = whisper.load_model(model_size)
                logger.info(f"Loaded Whisper {model_size} model for real-time transcription")
            else:
                logger.warning(f"Backend {self.backend} not supported for real-time transcription")
        except ImportError:
            logger.warning("Whisper not available for real-time transcription")
        except Exception as e:
            logger.error(f"Failed to initialize ASR model: {e}")

    def set_transcription_callback(self, callback: Callable[[str], None]):
        """
        Set callback for transcription results.

        Args:
            callback: Function to call with transcription text
        """
        self.on_transcription = callback

    def set_error_callback(self, callback: Callable[[Exception], None]):
        """
        Set callback for errors.

        Args:
            callback: Function to call with exceptions
        """
        self.on_error = callback

    def start_streaming(self) -> bool:
        """
        Start real-time transcription streaming.

        Returns:
            Success status
        """
        if self.is_streaming:
            logger.warning("Streaming already active")
            return False

        if not self.asr_model:
            logger.error("ASR model not available")
            return False

        try:
            self.is_streaming = True

            # Start processing thread
            self.processing_thread = threading.Thread(
                target=self._processing_loop,
                name='realtime-processing',
                daemon=True
            )
            self.processing_thread.start()

            logger.info("Real-time transcription streaming started")
            return True

        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self.is_streaming = False
            return False

    def stop_streaming(self):
        """Stop real-time transcription streaming."""
        if not self.is_streaming:
            return

        self.is_streaming = False

        # Wait for threads to finish
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5.0)

        logger.info("Real-time transcription streaming stopped")

    def add_audio_chunk(self, audio_data: np.ndarray, sample_rate: int = None):
        """
        Add audio chunk to processing queue.

        Args:
            audio_data: Audio data as numpy array
            sample_rate: Sample rate of audio data
        """
        if not self.is_streaming:
            return

        try:
            # Resample if necessary
            if sample_rate and sample_rate != self.sample_rate:
                audio_data = self._resample_audio(audio_data, sample_rate, self.sample_rate)

            # Add timestamp
            timestamp = time.time()

            # Put in buffer
            self.audio_buffer.put({
                'audio': audio_data,
                'timestamp': timestamp
            })

        except Exception as e:
            logger.error(f"Failed to add audio chunk: {e}")
            if self.on_error:
                self.on_error(e)

    def _resample_audio(self, audio_data: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
        """Resample audio data."""
        try:
            import librosa
            return librosa.resample(audio_data, orig_sr=from_rate, target_sr=to_rate)
        except ImportError:
            # Simple resampling (not recommended for production)
            ratio = to_rate / from_rate
            return np.interp(
                np.linspace(0, len(audio_data) - 1, int(len(audio_data) * ratio)),
                np.arange(len(audio_data)),
                audio_data
            )

    def _processing_loop(self):
        """Main processing loop for real-time transcription."""
        audio_chunks = []
        last_process_time = time.time()

        while self.is_streaming:
            try:
                # Collect audio chunks
                chunk_available = True
                while chunk_available and len(audio_chunks) < 10:  # Max 10 chunks
                    try:
                        chunk = self.audio_buffer.get(timeout=0.1)
                        audio_chunks.append(chunk)
                        chunk_available = True
                    except queue.Empty:
                        chunk_available = False

                # Process chunks if we have enough data or it's been too long
                current_time = time.time()
                should_process = (
                    len(audio_chunks) >= 3 or  # At least 3 chunks (1.5 seconds)
                    (current_time - last_process_time) > 1.0  # Or 1 second has passed
                )

                if should_process and audio_chunks:
                    # Combine chunks
                    combined_audio = self._combine_audio_chunks(audio_chunks)

                    if len(combined_audio) > self.sample_rate * 0.5:  # At least 0.5 seconds
                        # Process transcription
                        start_time = time.time()
                        transcription = self._transcribe_audio_chunk(combined_audio)
                        latency = time.time() - start_time

                        # Record latency
                        self.latencies.append(latency)
                        if len(self.latencies) > self.max_latency_history:
                            self.latencies = self.latencies[-self.max_latency_history:]

                        # Send result
                        if transcription and self.on_transcription:
                            self.on_transcription(transcription)

                        last_process_time = current_time

                    # Clear processed chunks
                    audio_chunks.clear()

                # Small sleep to prevent busy waiting
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"Processing loop error: {e}")
                if self.on_error:
                    self.on_error(e)
                time.sleep(0.5)  # Longer sleep on error

    def _combine_audio_chunks(self, chunks: List[Dict[str, Any]]) -> np.ndarray:
        """Combine multiple audio chunks into single array."""
        if not chunks:
            return np.array([])

        # Sort by timestamp
        chunks.sort(key=lambda x: x['timestamp'])

        # Concatenate audio data
        audio_arrays = [chunk['audio'] for chunk in chunks]
        return np.concatenate(audio_arrays)

    def _transcribe_audio_chunk(self, audio_data: np.ndarray) -> Optional[str]:
        """Transcribe a chunk of audio data."""
        if not self.asr_model or len(audio_data) == 0:
            return None

        try:
            # Normalize audio
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Normalize to [-1, 1] range
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val

            # Transcribe using Whisper
            result = self.asr_model.transcribe(
                audio_data,
                language='en',  # Could be made configurable
                without_timestamps=True,
                max_initial_timestamp=1.0,
                verbose=False
            )

            text = result.get('text', '').strip()

            # Filter out very short or low-confidence transcriptions
            if len(text) < 3:
                return None

            return text

        except Exception as e:
            logger.error(f"Audio chunk transcription failed: {e}")
            return None

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get real-time transcription performance statistics."""
        if not self.latencies:
            return {'status': 'no_data'}

        avg_latency = sum(self.latencies) / len(self.latencies)
        p95_latency = np.percentile(self.latencies, 95) if len(self.latencies) >= 20 else avg_latency

        return {
            'is_streaming': self.is_streaming,
            'avg_latency': avg_latency,
            'p95_latency': p95_latency,
            'target_latency': self.target_latency,
            'latency_target_met': p95_latency <= self.target_latency,
            'buffer_size_seconds': self.buffer_size_seconds,
            'chunk_size_seconds': self.chunk_size_seconds,
            'sample_rate': self.sample_rate,
            'backend': self.backend,
            'latencies_count': len(self.latencies)
        }

    def get_supported_formats(self) -> List[str]:
        """Get supported audio formats for real-time processing."""
        return [
            'raw_pcm',
            'wav',
            'flac',
            'ogg',
            'webm'
        ]

    def is_available(self) -> bool:
        """Check if real-time transcription is available."""
        return self.asr_model is not None and not self.is_streaming

    def reset_stats(self):
        """Reset performance statistics."""
        self.latencies.clear()
        logger.info("Realtime transcription stats reset")

    def __enter__(self):
        """Context manager entry."""
        self.start_streaming()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_streaming()
