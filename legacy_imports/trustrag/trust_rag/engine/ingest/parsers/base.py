"""
Base Parser Interface.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from trust_rag.engine.ingest.models import Chunk


@dataclass
class ParsedChunk:
    """解析后的文本块"""
    text: str
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class BaseIngestParser(ABC):
    """Abstract base class for all ingestion parsers."""

    name: str = "base"

    @abstractmethod
    def parse_document(
        self,
        file_path: str,
        doc_id: str = "",
        **kwargs
    ) -> List[ParsedChunk]:
        """
        Parse a document and return a list of ParsedChunks.

        Args:
            file_path: Path to the document file
            doc_id: Document ID for metadata
            **kwargs: Additional parsing options

        Returns:
            List of ParsedChunk objects
        """
        pass

    @abstractmethod
    def get_parser_info(self) -> Dict[str, Any]:
        """Get parser information and capabilities."""
        pass

    def is_available(self) -> bool:
        """Check if the parser's dependencies are available."""
        try:
            # Try to import required dependencies
            self.get_parser_info()
            return True
        except ImportError:
            return False
