"""
HTML Parser for web content.
"""
import logging
from typing import List
from trust_rag.engine.ingest.parsers.base import BaseIngestParser
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
from trust_rag.engine.ingest.evidence_id import generate_evidence_id

logger = logging.getLogger(__name__)

class HTMLParser(BaseIngestParser):
    """
    Parser for HTML files.
    Extracts main content, headers, and tables.
    """
    name = "html_parser"
    
    def is_available(self) -> bool:
        try:
            from bs4 import BeautifulSoup
            return True
        except ImportError:
            return False
    
    def parse(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        from bs4 import BeautifulSoup
        
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        soup = BeautifulSoup(content, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        chunks = []
        block_index = 0
        
        # Extract title
        title = soup.find("title")
        if title and title.text.strip():
            title_text = title.text.strip()
            evidence_id = generate_evidence_id(doc_id, 1, block_index, title_text)
            prov = ChunkProvenance(
                doc_id=doc_id,
                page_number=1,
                bbox=None,
                source_path=path,
                parser_name=self.name,
                language=language,
                modality="web",
                block_index=block_index
            )
            chunks.append(Chunk(
                evidence_id=evidence_id,
                text=f"Title: {title_text}",
                provenance=prov,
                metadata={"type": "title"}
            ))
            block_index += 1
        
        # Extract headers
        for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = h.get_text().strip()
            if not text:
                continue
            
            evidence_id = generate_evidence_id(doc_id, 1, block_index, text)
            prov = ChunkProvenance(
                doc_id=doc_id,
                page_number=1,
                bbox=None,
                source_path=path,
                parser_name=self.name,
                language=language,
                modality="web",
                block_index=block_index
            )
            chunks.append(Chunk(
                evidence_id=evidence_id,
                text=text,
                provenance=prov,
                metadata={"type": "header", "level": h.name}
            ))
            block_index += 1
        
        # Extract paragraphs
        for p in soup.find_all("p"):
            text = p.get_text().strip()
            if len(text) < 20:  # Skip very short paragraphs
                continue
            
            evidence_id = generate_evidence_id(doc_id, 1, block_index, text)
            prov = ChunkProvenance(
                doc_id=doc_id,
                page_number=1,
                bbox=None,
                source_path=path,
                parser_name=self.name,
                language=language,
                modality="web",
                block_index=block_index
            )
            chunks.append(Chunk(
                evidence_id=evidence_id,
                text=text,
                provenance=prov,
                metadata={"type": "paragraph"}
            ))
            block_index += 1
        
        # Extract tables
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            table_text = []
            for row in rows[:50]:  # Limit rows
                cells = row.find_all(["td", "th"])
                row_text = " | ".join([c.get_text().strip() for c in cells])
                if row_text:
                    table_text.append(row_text)
            
            if table_text:
                full_text = "\n".join(table_text)
                evidence_id = generate_evidence_id(doc_id, 1, block_index, full_text)
                prov = ChunkProvenance(
                    doc_id=doc_id,
                    page_number=1,
                    bbox=None,
                    source_path=path,
                    parser_name=self.name,
                    language=language,
                    modality="web",
                    block_index=block_index
                )
                chunks.append(Chunk(
                    evidence_id=evidence_id,
                    text=full_text,
                    provenance=prov,
                    metadata={"type": "table"}
                ))
                block_index += 1
        
        return chunks
