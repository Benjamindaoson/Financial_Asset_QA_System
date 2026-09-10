"""
Structure Extractor: Extracts outline, clause trees, and chapter hierarchies from financial PDFs.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DocumentNode:
    """A node in the document structure tree (e.g., Chapter, Section, Clause)."""
    node_id: str
    level: int          # 0 for root, 1 for H1, 2 for H2, etc.
    title: str
    content: str        # Text belonging directly to this node
    page_number: int
    children: List['DocumentNode']
    parent_id: Optional[str] = None
    bbox: Optional[Tuple[float, float, float, float]] = None

class StructureExtractor:
    """
    Extracts structure trees from documents using table of contents, 
    font sizes, and regex heuristics specialized for financial prospectuses, 
    10-K/10-Q reports, and A-share annual reports.
    """
    
    def __init__(self):
        # Heuristics for A-share annual reports
        self.chapter_pattern = re.compile(r"^(?:第[一二三四五六七八九十]+[章节部分]|Chapter\s+\d+|Part\s+[IVX]+)\s*(.*)$", re.IGNORECASE)
        self.section_pattern = re.compile(r"^(?:\d+\.\d+|\([一二三四五六七八九十]+\)|[A-Z]\.)\s+(.*)$")
        self.clause_pattern = re.compile(r"^(?:\d+\.\d+\.\d+|\(\d+\)|[a-z]\.)\s+(.*)$")

    def extract_structure(self, pages: List[Dict[str, Any]]) -> DocumentNode:
        """
        Extracts a hierarchical DocumentNode tree from page data (produced by OCR/PyMuPDF).
        """
        root = DocumentNode(node_id="root", level=0, title="Document Root", content="", page_number=0, children=[])
        current_path = {0: root}
        
        # Simplified sequential extraction based on regex heuristics
        # In a full enterprise setting, this would use a LayoutLMv3 layout parsed output 
        # to detect font sizing and line spacing for heading detection.
        
        node_counter = 1
        for page_num, page in enumerate(pages):
            text_blocks = page.get("blocks", [])
            for block in text_blocks:
                text = block.get("text", "").strip()
                if not text:
                    continue
                    
                # Detect level
                level = -1
                if self.chapter_pattern.match(text):
                    level = 1
                elif self.section_pattern.match(text):
                    level = 2
                elif self.clause_pattern.match(text):
                    level = 3
                
                if level != -1:
                    # Found a heading
                    node = DocumentNode(
                        node_id=f"node_{node_counter}",
                        level=level,
                        title=text,
                        content="",
                        page_number=page_num + 1,
                        children=[],
                        bbox=block.get("bbox")
                    )
                    node_counter += 1
                    
                    # Attach to the closest parent strictly higher in hierarchy (lower level number)
                    parent_level = level - 1
                    while parent_level > 0 and parent_level not in current_path:
                        parent_level -= 1
                    
                    parent = current_path.get(parent_level, root)
                    node.parent_id = parent.node_id
                    parent.children.append(node)
                    
                    # Update current path
                    current_path[level] = node
                    # Clear deeper levels
                    for l in list(current_path.keys()):
                        if l > level:
                            del current_path[l]
                else:
                    # Regular content, attach to the deepest active node
                    deepest_level = max(current_path.keys())
                    current_node = current_path[deepest_level]
                    if current_node.content:
                        current_node.content += "\n" + text
                    else:
                        current_node.content = text
                        
        return root

    def flatten_structure(self, root: DocumentNode) -> List[Dict[str, Any]]:
        """Flatten tree into a list of structure-aware text chunks."""
        chunks = []
        
        def traverse(node: DocumentNode, breadcrumbs: List[str]):
            current_breadcrumbs = breadcrumbs.copy()
            if node.level > 0:
                current_breadcrumbs.append(node.title)
                
            if node.content:
                chunks.append({
                    "title_path": " > ".join(current_breadcrumbs),
                    "content": node.content,
                    "level": node.level,
                    "page_number": node.page_number,
                    "node_id": node.node_id
                })
                
            for child in node.children:
                traverse(child, current_breadcrumbs)
                
        traverse(root, [])
        return chunks
