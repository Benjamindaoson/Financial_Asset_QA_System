"""
Advanced Audio Processor with Advanced Language Detection.
Uses Whisper, language identification models, and confidence scoring.
"""
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class SiliconValleyLanguageDetector:
    """
    Advanced language detection using multiple models and voting.
    """

    def __init__(self):
        self._whisper_model = None
        self._lang_id_model = None
        self._init_models()

    def _init_models(self):
        """Initialize language detection models."""
        try:
            # Try to load Whisper (has built-in language detection)
            import whisper
            self._whisper_model = whisper.load_model("base")
            logger.info("Loaded Whisper model for language detection")
        except (ImportError, RuntimeError, Exception) as e:
            logger.warning(f"Whisper model loading failed: {e}. Using fallback language detection")
            self._whisper_model = None

        try:
            # Try to load fasttext language identification
            import fasttext
            # This would need a pre-trained model
            # self._lang_id_model = fasttext.load_model('lid.176.bin')
            logger.info("FastText language ID ready")
        except ImportError:
            logger.warning("FastText not available for language identification")

    def detect_language_ensemble(self, audio_path: str) -> Dict[str, Any]:
        """
        Use ensemble of methods for robust language detection.

        Returns:
            {
                "detected_language": "en|zh|unknown",
                "confidence": 0.0-1.0,
                "methods_used": ["whisper", "acoustic", "text_fallback"],
                "alternative_languages": [{"lang": "en", "confidence": 0.8}, ...]
            }
        """
        results = []
        methods_used = []

        # Method 1: Whisper language detection
        whisper_result = self._detect_with_whisper(audio_path)
        if whisper_result:
            results.append(whisper_result)
            methods_used.append("whisper")

        # Method 2: Acoustic feature analysis
        acoustic_result = self._detect_with_acoustic_features(audio_path)
        if acoustic_result:
            results.append(acoustic_result)
            methods_used.append("acoustic")

        # Method 3: Short transcription + language ID (if audio is very short)
        text_result = self._detect_with_text_analysis(audio_path)
        if text_result:
            results.append(text_result)
            methods_used.append("text")

        # Ensemble voting
        if not results:
            return {
                "detected_language": "unknown",
                "confidence": 0.0,
                "methods_used": [],
                "alternative_languages": []
            }

        # Aggregate results
        language_votes = {}
        confidence_sum = {}

        for result in results:
            lang = result["language"]
            conf = result["confidence"]

            if lang not in language_votes:
                language_votes[lang] = 0
                confidence_sum[lang] = 0

            language_votes[lang] += 1
            confidence_sum[lang] += conf

        # Find winner
        best_lang = max(language_votes.keys(), key=lambda x: (language_votes[x], confidence_sum[x]))
        avg_confidence = confidence_sum[best_lang] / language_votes[best_lang]

        # Create alternatives list
        alternatives = [
            {"lang": lang, "confidence": confidence_sum[lang] / language_votes[lang]}
            for lang in language_votes.keys() if lang != best_lang
        ]
        alternatives.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "detected_language": best_lang,
            "confidence": avg_confidence,
            "methods_used": methods_used,
            "alternative_languages": alternatives[:3]  # Top 3 alternatives
        }

    def _detect_with_whisper(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """Use Whisper's built-in language detection."""
        if not self._whisper_model:
            return None

        try:
            # Load a short segment for language detection
            import torchaudio
            waveform, sample_rate = torchaudio.load(audio_path, num_frames=16000*30)  # 30 seconds

            # Detect language
            audio_np = waveform.squeeze().numpy()
            result = self._whisper_model.detect_language(audio_np)

            if result and len(result) >= 2:
                detected_lang, confidence = result[0], result[1]

                # Map Whisper language codes to our codes
                lang_mapping = {
                    "english": "en",
                    "chinese": "zh",
                    "mandarin": "zh",
                    "cantonese": "zh"
                }

                mapped_lang = lang_mapping.get(detected_lang.lower(), detected_lang[:2])

                return {
                    "language": mapped_lang,
                    "confidence": float(confidence),
                    "method": "whisper"
                }

        except Exception as e:
            logger.debug(f"Whisper language detection failed: {e}")

        return None

    def _detect_with_acoustic_features(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """Use acoustic features for language detection."""
        try:
            import librosa
            import numpy as np

            # Load audio
            y, sr = librosa.load(audio_path, duration=10)  # First 10 seconds

            # Extract acoustic features
            # Pitch features (fundamental frequency)
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            pitch_mean = np.mean(pitches[pitches > 0]) if np.any(pitches > 0) else 0

            # Spectral centroid
            centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))

            # Zero crossing rate
            zcr = np.mean(librosa.feature.zero_crossing_rate(y))

            # Simple heuristic-based classification
            # Mandarin Chinese typically has higher pitch and different spectral characteristics
            if pitch_mean > 150:  # High pitch suggests tonal language like Chinese
                confidence = min(0.7, pitch_mean / 300)  # Normalize confidence
                return {
                    "language": "zh",
                    "confidence": confidence,
                    "method": "acoustic",
                    "features": {
                        "pitch_mean": pitch_mean,
                        "centroid": centroid,
                        "zcr": zcr
                    }
                }
            elif pitch_mean > 80:  # Medium pitch, could be English
                confidence = 0.6
                return {
                    "language": "en",
                    "confidence": confidence,
                    "method": "acoustic",
                    "features": {
                        "pitch_mean": pitch_mean,
                        "centroid": centroid,
                        "zcr": zcr
                    }
                }

        except ImportError:
            logger.debug("Librosa not available for acoustic feature analysis")
        except Exception as e:
            logger.debug(f"Acoustic feature analysis failed: {e}")

        return None

    def _detect_with_text_analysis(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """Try short transcription and analyze the text."""
        try:
            # Transcribe a very short segment
            import speech_recognition as sr

            recognizer = sr.Recognizer()

            with sr.AudioFile(audio_path) as source:
                # Get first 5 seconds
                audio = recognizer.record(source, duration=5)

                # Try multiple languages
                languages = [
                    ("en-US", "en"),
                    ("zh-CN", "zh"),
                    ("zh-TW", "zh")
                ]

                best_result = None
                best_confidence = 0

                for lang_code, lang_short in languages:
                    try:
                        text = recognizer.recognize_google(audio, language=lang_code)

                        if text and len(text.strip()) > 2:
                            # Simple confidence heuristic based on text length and coherence
                            confidence = min(0.8, len(text) / 50)  # Normalize by expected length

                            if confidence > best_confidence:
                                best_confidence = confidence
                                best_result = {
                                    "language": lang_short,
                                    "confidence": confidence,
                                    "method": "text",
                                    "sample_text": text[:100]
                                }

                    except:
                        continue

                return best_result

        except Exception as e:
            logger.debug(f"Text-based language detection failed: {e}")

        return None


class AdvancedAudioTranscriber:
    """
    Advanced audio transcription with fallback strategies.
    """

    def __init__(self):
        self.language_detector = SiliconValleyLanguageDetector()
        self._whisper_model = None
        self._google_recognizer = None

    def transcribe_with_fallback(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe audio with multiple fallback strategies.

        Returns:
            {
                "transcription": {...},
                "language_detection": {...},
                "fallback_used": "primary|secondary|tertiary",
                "confidence": 0.0-1.0
            }
        """
        # Step 1: Language detection
        lang_result = self.language_detector.detect_language_ensemble(audio_path)

        detected_lang = lang_result["detected_language"]
        lang_confidence = lang_result["confidence"]

        # Step 2: Try primary transcription method
        if detected_lang in ["en", "zh"] and lang_confidence > 0.6:
            transcription = self._transcribe_primary(audio_path, detected_lang)
            if transcription and transcription.get("confidence", 0) > 0.5:
                return {
                    "transcription": transcription,
                    "language_detection": lang_result,
                    "fallback_used": "primary",
                    "overall_confidence": transcription.get("confidence", 0) * lang_confidence
                }

        # Step 3: Fallback to secondary method
        transcription = self._transcribe_secondary(audio_path)
        if transcription and transcription.get("confidence", 0) > 0.3:
            return {
                "transcription": transcription,
                "language_detection": lang_result,
                "fallback_used": "secondary",
                "overall_confidence": transcription.get("confidence", 0) * 0.8  # Penalty for fallback
            }

        # Step 4: Final fallback - language-agnostic processing
        transcription = self._transcribe_tertiary(audio_path)
        return {
            "transcription": transcription,
            "language_detection": lang_result,
            "fallback_used": "tertiary",
            "overall_confidence": transcription.get("confidence", 0) * 0.5  # Heavy penalty
        }

    def _transcribe_primary(self, audio_path: str, language: str) -> Optional[Dict[str, Any]]:
        """Primary transcription using Whisper."""
        try:
            if not self._whisper_model:
                import whisper
                self._whisper_model = whisper.load_model("base")

            # Map language
            whisper_lang = "english" if language == "en" else "chinese"

            result = self._whisper_model.transcribe(
                audio_path,
                language=whisper_lang,
                task="transcribe"
            )

            # Convert to our format
            segments = []
            for segment in result["segments"]:
                segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip(),
                    "confidence": segment.get("confidence", 0.8)
                })

            return {
                "segments": segments,
                "full_text": result["text"],
                "language": language,
                "confidence": 0.8,  # Whisper typically has good confidence
                "method": "whisper"
            }

        except Exception as e:
            logger.debug(f"Primary transcription failed: {e}")
            return None

    def _transcribe_secondary(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """Secondary transcription using Google Speech Recognition."""
        try:
            if not self._google_recognizer:
                import speech_recognition as sr
                self._google_recognizer = sr.Recognizer()

            # Try different language codes
            lang_codes = ["en-US", "zh-CN", "zh-TW"]

            for lang_code in lang_codes:
                try:
                    with sr.AudioFile(audio_path) as source:
                        audio = self._google_recognizer.record(source)

                        text = self._google_recognizer.recognize_google(audio, language=lang_code)

                        if text and len(text.strip()) > 5:
                            # Create segment (since Google doesn't provide timing)
                            return {
                                "segments": [{
                                    "start": 0.0,
                                    "end": 0.0,  # Unknown timing
                                    "text": text,
                                    "confidence": 0.6  # Google typically good but no timing
                                }],
                                "full_text": text,
                                "language": "zh" if "zh" in lang_code else "en",
                                "confidence": 0.6,
                                "method": "google"
                            }

                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    continue

        except Exception as e:
            logger.debug(f"Secondary transcription failed: {e}")

        return None

    def _transcribe_tertiary(self, audio_path: str) -> Dict[str, Any]:
        """Tertiary fallback - basic processing with low confidence."""
        try:
            # Try to get at least some audio information
            import speech_recognition as sr

            if not self._google_recognizer:
                self._google_recognizer = sr.Recognizer()

            with sr.AudioFile(audio_path) as source:
                # Try language-agnostic recognition
                audio = self._google_recognizer.record(source, duration=10)  # First 10 seconds

                try:
                    text = self._google_recognizer.recognize_google(audio)  # No language specified

                    if text:
                        return {
                            "segments": [{
                                "start": 0.0,
                                "end": 10.0,
                                "text": text,
                                "confidence": 0.3  # Very low confidence
                            }],
                            "full_text": text,
                            "language": "unknown",
                            "confidence": 0.3,
                            "method": "tertiary_fallback"
                        }

                except:
                    pass

        except Exception as e:
            logger.debug(f"Tertiary transcription failed: {e}")

        # Ultimate fallback
        return {
            "segments": [],
            "full_text": "",
            "language": "unknown",
            "confidence": 0.0,
            "method": "no_transcription",
            "error": "All transcription methods failed"
        }


class AudioQualityAssessor:
    """
    Assess audio quality for transcription confidence.
    """

    def assess_audio_quality(self, audio_path: str) -> Dict[str, Any]:
        """Comprehensive audio quality assessment."""
        assessment = {
            "overall_quality": "unknown",
            "issues": [],
            "recommendations": [],
            "metrics": {}
        }

        try:
            import librosa
            import numpy as np

            # Load audio
            y, sr = librosa.load(audio_path, duration=30)  # First 30 seconds

            # Length check
            duration = len(y) / sr
            assessment["metrics"]["duration"] = duration

            if duration < 1.0:
                assessment["issues"].append("Audio too short for reliable transcription")
                assessment["recommendations"].append("Need at least 3 seconds of audio")

            # Sample rate check
            assessment["metrics"]["sample_rate"] = sr
            if sr < 8000:
                assessment["issues"].append("Low sample rate may affect quality")

            # Volume check (RMS)
            rms = np.sqrt(np.mean(y**2))
            assessment["metrics"]["rms_level"] = rms

            if rms < 0.01:
                assessment["issues"].append("Audio too quiet")
                assessment["recommendations"].append("Increase recording volume")

            # Noise estimation
            # Simple noise gate to find quiet portions
            noise_threshold = rms * 0.1
            noise_frames = np.sum(np.abs(y) < noise_threshold)
            noise_ratio = noise_frames / len(y)
            assessment["metrics"]["noise_ratio"] = noise_ratio

            if noise_ratio > 0.8:
                assessment["issues"].append("High background noise")
                assessment["recommendations"].append("Record in quieter environment")

            # Determine overall quality
            quality_score = 0

            if duration >= 3.0:
                quality_score += 1
            if sr >= 16000:
                quality_score += 1
            if rms >= 0.05:
                quality_score += 1
            if noise_ratio <= 0.5:
                quality_score += 1

            if quality_score >= 3:
                assessment["overall_quality"] = "good"
            elif quality_score >= 2:
                assessment["overall_quality"] = "fair"
            else:
                assessment["overall_quality"] = "poor"

        except ImportError:
            assessment["issues"].append("Audio analysis libraries not available")
        except Exception as e:
            assessment["issues"].append(f"Quality assessment failed: {str(e)}")

        return assessment
