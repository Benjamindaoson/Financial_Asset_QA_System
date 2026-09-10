"""
Audio Processor for GraphRAG.

This module provides comprehensive audio processing capabilities including
preprocessing, feature extraction, and multimodal integration.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import os
import tempfile
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Comprehensive audio processing for multimodal GraphRAG.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize audio processor optimized for large files.

        Args:
            config: Processing configuration
        """
        self.config = config or {}

        # Audio processing parameters
        self.sample_rate = self.config.get('sample_rate', 16000)
        self.channels = self.config.get('channels', 1)  # Mono
        self.max_duration = self.config.get('max_duration', 300)  # 5 minutes

        # Large file handling
        self.chunk_size_mb = self.config.get('chunk_size_mb', 500)  # 500MB chunks
        self.max_file_size_gb = self.config.get('max_file_size_gb', 10)  # 10GB max
        self.enable_streaming = self.config.get('enable_streaming', True)

        # Supported formats
        self.supported_formats = ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.webm']

        # Performance optimization
        self.enable_preprocessing_cache = self.config.get('enable_preprocessing_cache', True)
        self.preprocessing_cache = {}

        # Initialize audio libraries
        self._init_audio_libs()

        logger.info("Audio processor initialized with large file support")

    def _init_audio_libs(self):
        """Initialize audio processing libraries."""
        try:
            import librosa
            self.librosa_available = True
            logger.info("Librosa available for audio processing")
        except ImportError:
            self.librosa_available = False
            logger.warning("Librosa not available, limited audio processing")

        try:
            import pydub
            self.pydub_available = True
            logger.info("Pydub available for audio format conversion")
        except ImportError:
            self.pydub_available = False
            logger.warning("Pydub not available, format conversion limited")

    def process_audio_file(
        self,
        audio_path: Union[str, Path],
        preprocess: bool = True,
        extract_features: bool = True
    ) -> Dict[str, Any]:
        """
        Process audio file for analysis.

        Args:
            audio_path: Path to audio file
            preprocess: Whether to preprocess audio
            extract_features: Whether to extract audio features

        Returns:
            Audio processing result
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Check format
        if audio_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Unsupported audio format: {audio_path.suffix}")

        result = {
            'file_path': str(audio_path),
            'file_size': audio_path.stat().st_size,
            'format': audio_path.suffix.lower(),
            'processed': False
        }

        try:
            # Load audio
            audio_data, sample_rate = self._load_audio(audio_path)

            if audio_data is None:
                raise ValueError("Failed to load audio data")

            result.update({
                'sample_rate': sample_rate,
                'duration': len(audio_data) / sample_rate,
                'channels': 1 if len(audio_data.shape) == 1 else audio_data.shape[0],
                'dtype': str(audio_data.dtype)
            })

            # Check duration
            if result['duration'] > self.max_duration:
                logger.warning(f"Audio duration ({result['duration']:.1f}s) exceeds maximum ({self.max_duration}s)")
                # Truncate audio
                max_samples = int(self.max_duration * sample_rate)
                audio_data = audio_data[:max_samples]
                result['duration'] = self.max_duration
                result['truncated'] = True

            # Preprocess if requested
            if preprocess:
                audio_data = self._preprocess_audio(audio_data, sample_rate)
                result['preprocessed'] = True

            # Extract features if requested
            if extract_features:
                features = self._extract_audio_features(audio_data, sample_rate)
                result['features'] = features

            result['processed'] = True
            result['audio_data'] = audio_data

            logger.info(f"Successfully processed audio: {audio_path.name}")

        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            result['error'] = str(e)

        return result

    def _load_audio(self, audio_path: Path) -> Tuple[Optional[np.ndarray], int]:
        """
        Load audio file into numpy array.

        Args:
            audio_path: Path to audio file

        Returns:
            Tuple of (audio_data, sample_rate)
        """
        try:
            if self.librosa_available:
                import librosa
                audio_data, sample_rate = librosa.load(
                    audio_path,
                    sr=self.sample_rate,
                    mono=True  # Convert to mono
                )
                return audio_data, sample_rate

            elif self.pydub_available:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(audio_path)

                # Convert to mono and target sample rate
                audio = audio.set_channels(1).set_frame_rate(self.sample_rate)

                # Convert to numpy array
                audio_data = np.array(audio.get_array_of_samples(), dtype=np.float32)
                audio_data = audio_data / (2**15)  # Normalize to [-1, 1]

                return audio_data, self.sample_rate

            else:
                # Fallback: try to read as WAV
                if audio_path.suffix.lower() == '.wav':
                    import wave
                    with wave.open(str(audio_path), 'rb') as wav_file:
                        sample_rate = wav_file.getframerate()
                        n_channels = wav_file.getnchannels()
                        n_frames = wav_file.getnframes()

                        # Read audio data
                        audio_bytes = wav_file.readframes(n_frames)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)

                        # Convert to mono if necessary
                        if n_channels > 1:
                            audio_data = audio_data.reshape(-1, n_channels).mean(axis=1)

                        # Normalize
                        audio_data = audio_data.astype(np.float32) / 32768.0

                        return audio_data, sample_rate

        except Exception as e:
            logger.error(f"Failed to load audio: {e}")

        return None, 0

    def _preprocess_audio(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Preprocess audio data.

        Args:
            audio_data: Raw audio data
            sample_rate: Sample rate

        Returns:
            Preprocessed audio data
        """
        if not self.librosa_available:
            return audio_data

        try:
            import librosa

            # Normalize
            audio_data = librosa.util.normalize(audio_data)

            # Trim silence
            audio_data, _ = librosa.effects.trim(audio_data, top_db=20)

            # Apply pre-emphasis filter
            audio_data = librosa.effects.preemphasis(audio_data)

            # Normalize again
            audio_data = librosa.util.normalize(audio_data)

        except Exception as e:
            logger.warning(f"Audio preprocessing failed: {e}")

        return audio_data

    def _extract_audio_features(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """
        Extract audio features for analysis.

        Args:
            audio_data: Audio data array
            sample_rate: Sample rate

        Returns:
            Dictionary of audio features
        """
        features = {}

        if not self.librosa_available:
            return features

        try:
            import librosa

            # MFCCs (Mel-frequency cepstral coefficients)
            mfccs = librosa.feature.mfcc(y=audio_data, sr=sample_rate, n_mfcc=13)
            features['mfccs'] = {
                'mean': mfccs.mean(axis=1).tolist(),
                'std': mfccs.std(axis=1).tolist(),
                'shape': mfccs.shape
            }

            # Chroma features
            chroma = librosa.feature.chroma_stft(y=audio_data, sr=sample_rate)
            features['chroma'] = {
                'mean': chroma.mean(axis=1).tolist(),
                'std': chroma.std(axis=1).tolist()
            }

            # Spectral centroid
            spectral_centroid = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)
            features['spectral_centroid'] = {
                'mean': spectral_centroid.mean(),
                'std': spectral_centroid.std()
            }

            # Zero-crossing rate
            zcr = librosa.feature.zero_crossing_rate(audio_data)
            features['zero_crossing_rate'] = {
                'mean': zcr.mean(),
                'std': zcr.std()
            }

            # RMS energy
            rms = librosa.feature.rms(y=audio_data)
            features['rms_energy'] = {
                'mean': rms.mean(),
                'std': rms.std()
            }

            # Fundamental frequency (pitch)
            f0, voiced_flag, voiced_probs = librosa.pyin(
                audio_data,
                fmin=librosa.note_to_hz('C2'),
                fmax=librosa.note_to_hz('C7'),
                sr=sample_rate
            )
            features['pitch'] = {
                'mean': np.nanmean(f0) if np.any(~np.isnan(f0)) else 0,
                'voiced_ratio': np.mean(voiced_flag) if voiced_flag is not None else 0
            }

            # Tempo
            tempo, _ = librosa.beat.tempo(y=audio_data, sr=sample_rate)
            features['tempo'] = float(tempo)

            # Onset strength
            onset_env = librosa.onset.onset_strength(y=audio_data, sr=sample_rate)
            features['onset_strength'] = {
                'mean': onset_env.mean(),
                'max': onset_env.max()
            }

        except Exception as e:
            logger.warning(f"Feature extraction failed: {e}")

        return features

    def convert_audio_format(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        output_format: str = 'wav',
        sample_rate: Optional[int] = None
    ) -> bool:
        """
        Convert audio file to different format.

        Args:
            input_path: Input audio file path
            output_path: Output audio file path
            output_format: Target format ('wav', 'mp3', etc.)
            sample_rate: Target sample rate

        Returns:
            Success status
        """
        if not self.pydub_available:
            logger.warning("Audio conversion requires pydub")
            return False

        try:
            from pydub import AudioSegment

            # Load audio
            audio = AudioSegment.from_file(input_path)

            # Convert sample rate if specified
            if sample_rate:
                audio = audio.set_frame_rate(sample_rate)

            # Convert channels to mono
            audio = audio.set_channels(1)

            # Export in target format
            audio.export(output_path, format=output_format)

            logger.info(f"Converted audio: {input_path} -> {output_path}")
            return True

        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return False

    def split_audio(
        self,
        audio_path: Union[str, Path],
        segment_duration: float = 30.0,
        overlap: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Split audio file into segments.

        Args:
            audio_path: Input audio file path
            segment_duration: Duration of each segment in seconds
            overlap: Overlap between segments in seconds

        Returns:
            List of segment information
        """
        if not self.pydub_available:
            logger.warning("Audio splitting requires pydub")
            return []

        try:
            from pydub import AudioSegment

            # Load audio
            audio = AudioSegment.from_file(audio_path)
            total_duration = len(audio) / 1000.0  # Convert to seconds

            segments = []
            start_time = 0

            while start_time < total_duration:
                end_time = min(start_time + segment_duration, total_duration)

                # Extract segment
                start_ms = int(start_time * 1000)
                end_ms = int(end_time * 1000)
                segment = audio[start_ms:end_ms]

                segments.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': end_time - start_time,
                    'audio_segment': segment,
                    'segment_index': len(segments)
                })

                # Move start time with overlap consideration
                start_time += segment_duration - overlap

                if start_time >= total_duration:
                    break

            logger.info(f"Split audio into {len(segments)} segments")
            return segments

        except Exception as e:
            logger.error(f"Audio splitting failed: {e}")
            return []

    def get_audio_info(self, audio_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get basic information about audio file without full processing.

        Args:
            audio_path: Path to audio file

        Returns:
            Audio file information
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            return {'error': 'File not found'}

        try:
            # Get basic file info
            info = {
                'file_path': str(audio_path),
                'file_size': audio_path.stat().st_size,
                'format': audio_path.suffix.lower(),
                'last_modified': audio_path.stat().st_mtime
            }

            # Try to get audio metadata
            if self.pydub_available:
                from pydub import AudioSegment
                try:
                    audio = AudioSegment.from_file(audio_path)
                    info.update({
                        'duration': len(audio) / 1000.0,
                        'sample_rate': audio.frame_rate,
                        'channels': audio.channels,
                        'sample_width': audio.sample_width
                    })
                except Exception:
                    pass

            return info

        except Exception as e:
            return {'error': str(e)}

    def batch_process_audio(
        self,
        audio_paths: List[Union[str, Path]],
        preprocess: bool = True,
        extract_features: bool = True,
        max_workers: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Process multiple audio files in batch.

        Args:
            audio_paths: List of audio file paths
            preprocess: Whether to preprocess
            extract_features: Whether to extract features
            max_workers: Maximum parallel workers

        Returns:
            List of processing results
        """
        from concurrent.futures import ThreadPoolExecutor

        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.process_audio_file, path, preprocess, extract_features)
                for path in audio_paths
            ]

            for future in futures:
                try:
                    result = future.result(timeout=600)  # 10 minute timeout
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Batch audio processing failed: {e}")
                    results.append({'error': str(e)})

        return results

    def cleanup_temp_files(self, temp_dir: Optional[str] = None):
        """
        Clean up temporary audio processing files.

        Args:
            temp_dir: Temporary directory to clean (default: system temp)
        """
        import shutil

        temp_dir = temp_dir or tempfile.gettempdir()

        try:
            # Remove any temp audio files created during processing
            temp_path = Path(temp_dir)
            for temp_file in temp_path.glob("graphrag_audio_temp_*"):
                try:
                    if temp_file.is_file():
                        temp_file.unlink()
                    elif temp_file.is_dir():
                        shutil.rmtree(temp_file)
                except Exception:
                    pass

            logger.info(f"Cleaned up temporary audio files in {temp_dir}")

        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {e}")

    def get_processor_info(self) -> Dict[str, Any]:
        """Get processor information."""
        return {
            'sample_rate': self.sample_rate,
            'max_duration': self.max_duration,
            'supported_formats': self.supported_formats,
            'librosa_available': self.librosa_available,
            'pydub_available': self.pydub_available,
            'config': self.config
        }
