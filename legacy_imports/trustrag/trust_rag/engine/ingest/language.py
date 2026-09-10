"""
Language Detection (Deterministic, Offline).
"""
from typing import Literal
import re

class LanguageDetector:
    """
    Rule-based language detector. 
    Prioritizes determinism and offline capability.
    """
    
    CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
    SAMPLE_SIZE = 2000
    ZH_THRESHOLD = 0.10  # If > 10% CJK chars, likely Chinese
    
    def detect(self, text: str) -> Literal["zh", "en", "unknown"]:
        """
        Detect language from text sample.
        Returns: "zh", "en", or "unknown"
        """
        if not text or not text.strip():
            return "unknown"
        
        # Take sample
        sample = text[:self.SAMPLE_SIZE]
        
        # Count only letter characters (ignore spaces, punctuation, numbers)
        letters_only = ''.join(c for c in sample if c.isalpha())
        total_letters = len(letters_only)
        
        if total_letters == 0:
            return "unknown"
        
        # Count CJK characters
        cjk_chars = len(self.CJK_PATTERN.findall(letters_only))
        cjk_ratio = cjk_chars / total_letters
        
        if cjk_ratio >= self.ZH_THRESHOLD:
            return "zh"
        
        # If very few CJK characters and mostly ASCII letters, it's English
        ascii_letters = sum(1 for c in letters_only if ord(c) < 128)
        ascii_ratio = ascii_letters / total_letters
        
        if ascii_ratio > 0.8:
            return "en"
        
        return "unknown"
    
    def detect_from_file(self, path: str, content_type: str) -> Literal["zh", "en", "unknown"]:
        """
        Detect language from a file by extracting a sample.
        For PDF/Image, this requires a lightweight extraction first.
        """
        import os
        if not os.path.exists(path):
            return "unknown"
        
        if content_type in ["text", "csv", "xlsx"]:
            # For text-based files, read directly
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return self.detect(f.read(self.SAMPLE_SIZE))
            except Exception:
                return "unknown"
        
        if content_type == "pdf":
            return self._detect_from_pdf(path)
        
        if content_type == "html":
            return self._detect_from_html(path)
        
        # For image/audio, we need OCR/ASR first - return unknown for now
        # The router will handle this after getting initial text
        return "unknown"
    
    def _detect_from_pdf(self, path: str) -> Literal["zh", "en", "unknown"]:
        """Extract text sample from PDF for language detection."""
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                sample_text = ""
                for page in pdf.pages[:3]:  # First 3 pages
                    text = page.extract_text() or ""
                    sample_text += text
                    if len(sample_text) >= self.SAMPLE_SIZE:
                        break
                return self.detect(sample_text)
        except ImportError:
            # Try pypdf
            try:
                from pypdf import PdfReader
                reader = PdfReader(path)
                sample_text = ""
                for page in reader.pages[:3]:
                    sample_text += page.extract_text() or ""
                    if len(sample_text) >= self.SAMPLE_SIZE:
                        break
                return self.detect(sample_text)
            except Exception:
                return "unknown"
        except Exception:
            return "unknown"
    
    def _detect_from_html(self, path: str) -> Literal["zh", "en", "unknown"]:
        """Extract text from HTML for detection."""
        try:
            from bs4 import BeautifulSoup
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
                text = soup.get_text()
                return self.detect(text)
        except Exception:
            return "unknown"
