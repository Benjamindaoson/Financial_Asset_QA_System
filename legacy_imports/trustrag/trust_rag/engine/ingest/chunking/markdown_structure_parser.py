"""
TrustRAG 2.0 Markdown Structure Parser

Converts parsed Markdown text into structured node streams with:
1. Proper type classification (HEADER, PARAGRAPH, TABLE, LIST, CODE)
2. Table atomicity protection (complete table blocks)
3. Audit logging for node statistics
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    """Document node types"""
    HEADER = "header"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    CODE = "code"
    BLOCKQUOTE = "blockquote"


class DocNode(BaseModel):
    """
    Structured document node
    
    Represents a single semantic unit in the document (header, paragraph, table, etc.)
    """
    type: NodeType = Field(..., description="Node type")
    content: str = Field(..., description="Text content of the node")
    level: Optional[int] = Field(None, description="Header level (1-6) for HEADER nodes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    line_start: int = Field(..., description="Starting line number (0-indexed)")
    line_end: int = Field(..., description="Ending line number (0-indexed)")
    
    def token_estimate(self) -> int:
        """Estimate token count (rough approximation: 1 token ≈ 4 chars)"""
        return len(self.content) // 4
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.type.value,
            "content": self.content,
            "level": self.level,
            "metadata": self.metadata,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "token_estimate": self.token_estimate()
        }


class MarkdownStructureParser:
    """
    Parse Markdown text into structured node streams
    
    Features:
    - Complete table block extraction (no partial tables)
    - Header level detection
    - List and code block recognition
    - Audit statistics for chunking strategy optimization
    """
    
    # Regex patterns
    HEADER_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$')
    TABLE_LINE_PATTERN = re.compile(r'^\|.+\|$')
    TABLE_ALIGNMENT_PATTERN = re.compile(r'^\|[\s:|-]+\|$')
    LIST_PATTERN = re.compile(r'^(\s*)([-*+]|\d+\.)\s+(.+)$')
    CODE_FENCE_PATTERN = re.compile(r'^```(\w*)$')
    BLOCKQUOTE_PATTERN = re.compile(r'^>\s+(.+)$')
    
    def __init__(self):
        """Initialize parser"""
        self.audit_stats: Dict[str, Any] = {}
    
    def parse(self, markdown_text: str) -> List[DocNode]:
        """
        Parse Markdown text into structured nodes
        
        Args:
            markdown_text: Markdown content to parse
            
        Returns:
            List of DocNode objects
        """
        if not markdown_text or not markdown_text.strip():
            logger.warning("Empty markdown text provided")
            return []
        
        lines = markdown_text.split('\n')
        nodes: List[DocNode] = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Skip empty lines
            if not line.strip():
                i += 1
                continue
            
            # Try to detect node type and extract
            node, lines_consumed = self._extract_node(lines, i)
            
            if node:
                nodes.append(node)
                i += lines_consumed
            else:
                # Fallback: treat as paragraph
                node, lines_consumed = self._extract_paragraph(lines, i)
                if node:
                    nodes.append(node)
                i += lines_consumed
        
        # Generate audit statistics
        self.audit_stats = self._audit_nodes(nodes)
        
        logger.info(f"Parsed {len(nodes)} nodes: {self.audit_stats}")
        
        return nodes
    
    def _extract_node(self, lines: List[str], start_idx: int) -> Tuple[Optional[DocNode], int]:
        """
        Extract a single node starting from the given line
        
        Returns:
            (DocNode or None, number of lines consumed)
        """
        line = lines[start_idx]
        
        # Check for header
        header_match = self.HEADER_PATTERN.match(line)
        if header_match:
            level = len(header_match.group(1))
            content = header_match.group(2).strip()
            return DocNode(
                type=NodeType.HEADER,
                content=content,
                level=level,
                line_start=start_idx,
                line_end=start_idx,
                metadata={"raw_line": line}
            ), 1
        
        # Check for table
        if self.TABLE_LINE_PATTERN.match(line):
            return self._extract_table_block(lines, start_idx)
        
        # Check for code fence
        if self.CODE_FENCE_PATTERN.match(line):
            return self._extract_code_block(lines, start_idx)
        
        # Check for list
        if self.LIST_PATTERN.match(line):
            return self._extract_list_block(lines, start_idx)
        
        # Check for blockquote
        if self.BLOCKQUOTE_PATTERN.match(line):
            return self._extract_blockquote(lines, start_idx)
        
        return None, 0
    
    def _extract_table_block(self, lines: List[str], start_idx: int) -> Tuple[Optional[DocNode], int]:
        """
        Extract complete Markdown table block
        
        Critical: Ensures table atomicity by capturing:
        1. All header rows
        2. Alignment row (|---|---|)
        3. All data rows
        
        Returns:
            (DocNode with complete table, number of lines consumed)
        """
        table_lines = []
        i = start_idx
        has_alignment_row = False
        
        # Collect all consecutive table lines
        while i < len(lines):
            line = lines[i]
            
            if self.TABLE_LINE_PATTERN.match(line):
                table_lines.append(line)
                
                # Check if this is the alignment row
                if self.TABLE_ALIGNMENT_PATTERN.match(line):
                    has_alignment_row = True
                
                i += 1
            else:
                # Stop when we hit a non-table line
                break
        
        # Validate table structure
        if not has_alignment_row:
            logger.warning(f"Table at line {start_idx} missing alignment row, treating as paragraph")
            return None, 0
        
        if len(table_lines) < 3:  # Minimum: header + alignment + 1 data row
            logger.warning(f"Table at line {start_idx} too short ({len(table_lines)} lines)")
            return None, 0
        
        # Create table node
        table_content = '\n'.join(table_lines)
        
        # Extract table metadata
        num_columns = table_lines[0].count('|') - 1
        num_rows = len(table_lines) - 2  # Exclude header and alignment
        
        return DocNode(
            type=NodeType.TABLE,
            content=table_content,
            level=None,
            line_start=start_idx,
            line_end=i - 1,
            metadata={
                "num_columns": num_columns,
                "num_rows": num_rows,
                "has_alignment": has_alignment_row
            }
        ), i - start_idx
    
    def _extract_code_block(self, lines: List[str], start_idx: int) -> Tuple[Optional[DocNode], int]:
        """Extract fenced code block"""
        code_lines = [lines[start_idx]]  # Include opening fence
        i = start_idx + 1
        language = self.CODE_FENCE_PATTERN.match(lines[start_idx]).group(1)
        
        # Find closing fence
        while i < len(lines):
            code_lines.append(lines[i])
            if self.CODE_FENCE_PATTERN.match(lines[i]):
                # Found closing fence
                i += 1
                break
            i += 1
        
        code_content = '\n'.join(code_lines)
        
        return DocNode(
            type=NodeType.CODE,
            content=code_content,
            level=None,
            line_start=start_idx,
            line_end=i - 1,
            metadata={"language": language}
        ), i - start_idx
    
    def _extract_list_block(self, lines: List[str], start_idx: int) -> Tuple[Optional[DocNode], int]:
        """Extract consecutive list items"""
        list_lines = []
        i = start_idx
        
        while i < len(lines):
            line = lines[i]
            
            # Check if still a list item or continuation
            if self.LIST_PATTERN.match(line) or (line.startswith('  ') and list_lines):
                list_lines.append(line)
                i += 1
            else:
                break
        
        list_content = '\n'.join(list_lines)
        
        return DocNode(
            type=NodeType.LIST,
            content=list_content,
            level=None,
            line_start=start_idx,
            line_end=i - 1,
            metadata={"num_items": len([l for l in list_lines if self.LIST_PATTERN.match(l)])}
        ), i - start_idx
    
    def _extract_blockquote(self, lines: List[str], start_idx: int) -> Tuple[Optional[DocNode], int]:
        """Extract blockquote"""
        quote_lines = []
        i = start_idx
        
        while i < len(lines):
            line = lines[i]
            if self.BLOCKQUOTE_PATTERN.match(line):
                quote_lines.append(line)
                i += 1
            else:
                break
        
        quote_content = '\n'.join(quote_lines)
        
        return DocNode(
            type=NodeType.BLOCKQUOTE,
            content=quote_content,
            level=None,
            line_start=start_idx,
            line_end=i - 1,
            metadata={}
        ), i - start_idx
    
    def _extract_paragraph(self, lines: List[str], start_idx: int) -> Tuple[Optional[DocNode], int]:
        """
        Extract paragraph (consecutive non-empty lines that don't match other patterns)
        """
        para_lines = []
        i = start_idx
        
        while i < len(lines):
            line = lines[i]
            
            # Stop at empty line or special syntax
            if not line.strip():
                break
            
            # Stop at headers, tables, lists, code, blockquotes
            if (self.HEADER_PATTERN.match(line) or
                self.TABLE_LINE_PATTERN.match(line) or
                self.LIST_PATTERN.match(line) or
                self.CODE_FENCE_PATTERN.match(line) or
                self.BLOCKQUOTE_PATTERN.match(line)):
                break
            
            para_lines.append(line)
            i += 1
        
        if not para_lines:
            return None, 0
        
        para_content = '\n'.join(para_lines)
        
        return DocNode(
            type=NodeType.PARAGRAPH,
            content=para_content,
            level=None,
            line_start=start_idx,
            line_end=i - 1,
            metadata={}
        ), i - start_idx
    
    def _audit_nodes(self, nodes: List[DocNode]) -> Dict[str, Any]:
        """
        Generate audit statistics for nodes
        
        Used for dynamic chunking strategy adjustment
        """
        stats = {
            "total_nodes": len(nodes),
            "by_type": {},
            "total_tokens": 0,
            "avg_tokens_per_node": 0.0
        }
        
        # Count by type
        for node in nodes:
            node_type = node.type.value
            stats["by_type"][node_type] = stats["by_type"].get(node_type, 0) + 1
            stats["total_tokens"] += node.token_estimate()
        
        # Calculate averages
        if nodes:
            stats["avg_tokens_per_node"] = stats["total_tokens"] / len(nodes)
        
        # Calculate type percentages
        stats["type_percentages"] = {
            node_type: (count / len(nodes)) * 100
            for node_type, count in stats["by_type"].items()
        }
        
        return stats
    
    def get_audit_stats(self) -> Dict[str, Any]:
        """Get the most recent audit statistics"""
        return self.audit_stats
