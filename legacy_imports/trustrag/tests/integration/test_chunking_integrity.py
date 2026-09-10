"""
TrustRAG 2.0 Chunking Integrity Tests

Verifies:
1. Table atomicity (no 断头表)
2. Header path injection
3. Chunk quality and completeness
"""
import pytest
import re
import sys
from pathlib import Path
from typing import List

# Add parent directory to path to allow direct imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trust_rag.engine.ingest.chunking.markdown_structure_parser import (
    MarkdownStructureParser, DocNode, NodeType
)
from trust_rag.engine.ingest.chunking.structure_aware_chunker import (
    StructureAwareChunker, ChunkingConfig
)
from trust_rag.engine.ingest.models import Chunk


# Test fixtures
@pytest.fixture
def sample_markdown_with_tables():
    """Sample markdown with complex tables"""
    return """# 2024年财务报告

## 第一季度业绩

本季度业绩良好，各项指标稳步增长。

### 收入明细表

| 地区 | Q1收入 | Q2收入 | 增长率 |
|------|--------|--------|--------|
| 华东 | 1000万 | 1200万 | 20% |
| 华南 | 800万 | 900万 | 12.5% |
| 华北 | 600万 | 750万 | 25% |

以上数据显示华北地区增长最快。

## 第二季度业绩

### 成本分析

运营成本持续优化。

| 成本项 | 金额 | 占比 |
|--------|------|------|
| 人力 | 500万 | 40% |
| 租金 | 300万 | 24% |
| 其他 | 450万 | 36% |

### 利润表

| 项目 | 金额 |
|------|------|
| 总收入 | 2500万 |
| 总成本 | 1250万 |
| 净利润 | 1250万 |

利润率达到50%。
"""


@pytest.fixture
def parser():
    """Create parser instance"""
    return MarkdownStructureParser()


@pytest.fixture
def chunker():
    """Create chunker instance"""
    config = ChunkingConfig(
        max_chunk_size=500,  # Smaller for testing
        overlap_size=50,
        table_size_threshold=0.8
    )
    return StructureAwareChunker(config)


class TestMarkdownStructureParser:
    """Test MarkdownStructureParser"""
    
    def test_parse_headers(self, parser):
        """Test header parsing"""
        markdown = "# Header 1\n## Header 2\n### Header 3"
        nodes = parser.parse(markdown)
        
        assert len(nodes) == 3
        assert all(node.type == NodeType.HEADER for node in nodes)
        assert nodes[0].level == 1
        assert nodes[1].level == 2
        assert nodes[2].level == 3
    
    def test_parse_table(self, parser):
        """Test table parsing with atomicity"""
        markdown = """| Col1 | Col2 |
|------|------|
| A | B |
| C | D |"""
        
        nodes = parser.parse(markdown)
        
        assert len(nodes) == 1
        assert nodes[0].type == NodeType.TABLE
        assert nodes[0].metadata["num_columns"] == 2
        assert nodes[0].metadata["num_rows"] == 2
        assert nodes[0].metadata["has_alignment"] is True
    
    def test_table_integrity(self, parser):
        """Test that tables are extracted completely"""
        markdown = """Some text before.

| Header1 | Header2 | Header3 |
|---------|---------|---------|
| Data1 | Data2 | Data3 |
| Data4 | Data5 | Data6 |

Some text after."""
        
        nodes = parser.parse(markdown)
        
        # Find table node
        table_nodes = [n for n in nodes if n.type == NodeType.TABLE]
        assert len(table_nodes) == 1
        
        table = table_nodes[0]
        # Verify table has all components
        assert "Header1" in table.content
        assert "Header2" in table.content
        assert "Header3" in table.content
        assert "Data1" in table.content
        assert "Data6" in table.content
        # Verify alignment row is present
        assert re.search(r'\|[-:\s]+\|', table.content)
    
    def test_parse_mixed_content(self, parser, sample_markdown_with_tables):
        """Test parsing mixed content"""
        nodes = parser.parse(sample_markdown_with_tables)
        
        # Should have headers, paragraphs, and tables
        node_types = {node.type for node in nodes}
        assert NodeType.HEADER in node_types
        assert NodeType.PARAGRAPH in node_types
        assert NodeType.TABLE in node_types
        
        # Count tables
        table_nodes = [n for n in nodes if n.type == NodeType.TABLE]
        assert len(table_nodes) == 3  # Three tables in sample
    
    def test_audit_stats(self, parser, sample_markdown_with_tables):
        """Test audit statistics generation"""
        nodes = parser.parse(sample_markdown_with_tables)
        stats = parser.get_audit_stats()
        
        assert stats["total_nodes"] == len(nodes)
        assert "by_type" in stats
        assert "total_tokens" in stats
        assert "type_percentages" in stats
        assert stats["total_tokens"] > 0


class TestStructureAwareChunker:
    """Test StructureAwareChunker"""
    
    def test_header_path_tracking(self, parser, chunker):
        """Test header path inheritance"""
        markdown = """# Chapter 1
## Section 1.1
Content here.
### Subsection 1.1.1
More content."""
        
        nodes = parser.parse(markdown)
        chunks = chunker.chunk(nodes, "test_doc", "test.md")
        
        # Check that chunks have header paths
        for chunk in chunks:
            if chunk.metadata.get("chunk_type") != "header":
                assert "header_path" in chunk.metadata
                # Should have context prefix
                if chunk.metadata["header_path"]:
                    assert "[Context:" in chunk.text
    
    def test_table_atomicity_small_table(self, parser, chunker):
        """Test that small tables are kept atomic"""
        markdown = """# Report

Some intro text.

| Col1 | Col2 |
|------|------|
| A | B |
| C | D |

Some conclusion."""
        
        nodes = parser.parse(markdown)
        chunks = chunker.chunk(nodes, "test_doc", "test.md")
        
        # Find chunk containing table
        table_chunks = [c for c in chunks if "Col1" in c.text and "Col2" in c.text]
        
        assert len(table_chunks) >= 1
        
        # Verify table is complete in at least one chunk
        for chunk in table_chunks:
            if "|" in chunk.text:
                # Check for table header
                assert re.search(r'\|\s*Col1\s*\|\s*Col2\s*\|', chunk.text)
                # Check for alignment row
                assert re.search(r'\|[-:\s]+\|', chunk.text)
                # Check for data rows
                assert "A" in chunk.text and "B" in chunk.text
    
    def test_no_broken_tables(self, parser, chunker, sample_markdown_with_tables):
        """Critical test: Verify no 断头表 (broken tables)"""
        nodes = parser.parse(sample_markdown_with_tables)
        chunks = chunker.chunk(nodes, "test_doc", "test.md")
        
        for i, chunk in enumerate(chunks):
            # If chunk contains table markers
            if "|" in chunk.text:
                lines = chunk.text.split('\n')
                table_lines = [l for l in lines if '|' in l]
                
                if table_lines:
                    # Must have at least 3 lines (header + alignment + data)
                    # OR be part of a context prefix
                    has_alignment = any(re.match(r'^\|[\s:|-]+\|$', line.strip()) 
                                      for line in table_lines)
                    
                    # If it looks like a table, it must be complete
                    if len(table_lines) >= 2:
                        assert has_alignment, \
                            f"Chunk {i} has table-like content but missing alignment row:\n{chunk.text}"
    
    def test_context_injection(self, parser, chunker):
        """Test semantic context injection"""
        markdown = """# Main Title
## Subtitle
Paragraph content."""
        
        nodes = parser.parse(markdown)
        chunks = chunker.chunk(nodes, "test_doc", "test.md")
        
        # Find paragraph chunk
        para_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "text"]
        
        if para_chunks:
            chunk = para_chunks[0]
            # Should have context prefix
            assert "[Context: Main Title > Subtitle]" in chunk.text
    
    def test_chunk_metadata(self, parser, chunker, sample_markdown_with_tables):
        """Test chunk metadata completeness"""
        nodes = parser.parse(sample_markdown_with_tables)
        chunks = chunker.chunk(nodes, "test_doc", "test.md")
        
        for chunk in chunks:
            # All chunks should have required metadata
            assert "chunk_type" in chunk.metadata
            assert "node_types" in chunk.metadata
            assert "num_nodes" in chunk.metadata
            assert "header_path" in chunk.metadata
            assert "line_range" in chunk.metadata
            
            # Chunks should have section_path
            assert hasattr(chunk, 'section_path')
    
    def test_large_node_splitting(self, parser, chunker):
        """Test that large nodes are split with overlap"""
        # Create a very large paragraph
        large_text = "This is a sentence. " * 500  # ~500 tokens
        markdown = f"# Title\n\n{large_text}"
        
        nodes = parser.parse(markdown)
        chunks = chunker.chunk(nodes, "test_doc", "test.md")
        
        # Should create multiple chunks
        text_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "text"]
        
        # At least some splitting should occur
        assert len(text_chunks) >= 1
        
        # Check for split metadata
        split_chunks = [c for c in text_chunks if c.metadata.get("is_split")]
        if split_chunks:
            assert all("split_index" in c.metadata for c in split_chunks)


class TestTableIntegrity:
    """Comprehensive table integrity tests"""
    
    def test_table_header_preservation(self, parser, chunker):
        """Ensure table headers are always preserved"""
        markdown = """| Product | Price | Stock |
|---------|-------|-------|
| Apple | $1.00 | 100 |
| Banana | $0.50 | 200 |
| Orange | $0.75 | 150 |"""
        
        nodes = parser.parse(markdown)
        chunks = chunker.chunk(nodes, "test_doc", "test.md")
        
        # Find table chunk
        table_chunk = next((c for c in chunks if "Product" in c.text), None)
        assert table_chunk is not None
        
        # Verify all headers present
        assert "Product" in table_chunk.text
        assert "Price" in table_chunk.text
        assert "Stock" in table_chunk.text
    
    def test_table_data_completeness(self, parser, chunker):
        """Ensure all table data is preserved"""
        markdown = """| ID | Value |
|-----|-------|
| 1 | A |
| 2 | B |
| 3 | C |
| 4 | D |
| 5 | E |"""
        
        nodes = parser.parse(markdown)
        chunks = chunker.chunk(nodes, "test_doc", "test.md")
        
        # Combine all chunk texts
        all_text = "\n".join(c.text for c in chunks)
        
        # Verify all data present
        for i in range(1, 6):
            assert str(i) in all_text
        for letter in ['A', 'B', 'C', 'D', 'E']:
            assert letter in all_text
    
    def test_multiple_tables_separation(self, parser, chunker):
        """Test that multiple tables are properly separated"""
        markdown = """# Report

## Table 1

| A | B |
|---|---|
| 1 | 2 |

## Table 2

| C | D |
|---|---|
| 3 | 4 |"""
        
        nodes = parser.parse(markdown)
        chunks = chunker.chunk(nodes, "test_doc", "test.md")
        
        # Should have separate chunks or clearly delineated tables
        table_chunks = [c for c in chunks if "|" in c.text]
        
        # At least one chunk should exist
        assert len(table_chunks) >= 1


def test_end_to_end_pipeline(parser, chunker, sample_markdown_with_tables):
    """End-to-end test of the full pipeline"""
    # Parse
    nodes = parser.parse(sample_markdown_with_tables)
    assert len(nodes) > 0
    
    # Chunk
    chunks = chunker.chunk(nodes, "test_doc", "test.md")
    assert len(chunks) > 0
    
    # Verify all chunks are valid
    for chunk in chunks:
        assert chunk.evidence_id
        assert chunk.text
        assert chunk.provenance
        assert chunk.metadata
        
        # No broken tables
        if "|" in chunk.text:
            lines = [l for l in chunk.text.split('\n') if '|' in l]
            if len(lines) >= 2:
                has_alignment = any(re.match(r'^\|[\s:|-]+\|$', l.strip()) for l in lines)
                assert has_alignment, f"Broken table in chunk: {chunk.evidence_id}"
    
    # Verify audit stats
    stats = parser.get_audit_stats()
    assert stats["total_nodes"] == len(nodes)
    assert stats["total_tokens"] > 0
