# TrustRAG Multimodal Ingestion Module
"""
structured ingestion pipeline for PDF, Image, Audio, Table, and Web content.
"""
from .pipeline import IngestPipeline
from .models import DocInput, IngestResult
from .language import LanguageDetector
from .router import IngestionRouter
