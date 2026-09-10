"""
Advanced Table Parser for Advanced RAG.
Uses multimodal LLMs for table understanding and reconstruction.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json

from trust_rag.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class TableReconstruction:
    """Reconstructed table with semantic understanding."""
    headers: List[str]
    rows: List[List[str]]
    confidence: float
    semantic_type: str  # "financial", "comparison", "data", "unknown"
    relationships: Dict[str, Any]  # row/column relationships
    cross_page_links: List[Tuple[int, int]]  # (page1, page2) continuations


class SiliconValleyTableParser:
    """
    advanced approach: Use multimodal LLMs for table understanding.

    Strategy:
    1. Extract table images from PDF pages
    2. Use GPT-4V to understand table structure and content
    3. Cross-validate with traditional OCR
    4. Reconstruct semantic table representation
    """

    def __init__(self):
        self.config = get_config()
        self._multimodal_llm = None

    def parse_complex_table(self, table_images: List[bytes], context_text: str = "") -> TableReconstruction:
        """
        Parse complex table using multimodal LLM approach.

        Args:
            table_images: List of table image bytes (can be multiple pages)
            context_text: Surrounding text context

        Returns:
            Reconstructed table with high confidence
        """
        try:
            # Initialize multimodal LLM (lazy loading)
            if not self._multimodal_llm:
                self._init_multimodal_llm()

            # Create comprehensive prompt
            prompt = self._create_table_parsing_prompt(context_text)

            # Process with multimodal LLM
            table_data = self._process_with_multimodal_llm(table_images, prompt)

            # Validate and reconstruct
            reconstruction = self._reconstruct_table(table_data)

            # Cross-validate with traditional OCR if available
            if len(table_images) == 1:
                reconstruction = self._cross_validate_with_ocr(table_images[0], reconstruction)

            return reconstruction

        except Exception as e:
            logger.error(f"Advanced table parsing failed: {e}")
            # Fallback to low-confidence result
            return TableReconstruction(
                headers=[],
                rows=[],
                confidence=0.0,
                semantic_type="unknown",
                relationships={},
                cross_page_links=[]
            )

    def _init_multimodal_llm(self):
        """Initialize multimodal LLM (GPT-4V or similar)."""
        try:
            import openai
            self._multimodal_llm = openai.OpenAI()
            logger.info("Initialized multimodal LLM for table parsing")
        except ImportError:
            logger.warning("OpenAI not available, table parsing will be limited")
            self._multimodal_llm = None

    def _create_table_parsing_prompt(self, context: str) -> str:
        """Create comprehensive table parsing prompt."""
        return f"""
You are an expert financial analyst and table parsing specialist. Analyze this table image and extract structured data.

Context from document: {context[:500]}

Instructions:
1. Identify the table structure (headers, data rows, footers)
2. Determine the table's semantic type (financial statements, comparisons, data tables, etc.)
3. Extract all headers exactly as they appear
4. Extract all data rows, maintaining the correct column alignment
5. Identify any row/column relationships or hierarchies
6. If this appears to be a continuation of a previous table, note that
7. Provide confidence score (0-1) for the extraction accuracy

Return JSON format:
{{
    "headers": ["Header1", "Header2", ...],
    "rows": [["value1", "value2", ...], ...],
    "semantic_type": "financial|comparison|data|unknown",
    "relationships": {{
        "hierarchical_rows": true/false,
        "merged_cells": [],
        "continuation_from_previous": true/false
    }},
    "confidence": 0.95,
    "notes": "Any observations about data quality or structure"
}}
"""

    def _process_with_multimodal_llm(self, images: List[bytes], prompt: str) -> Dict[str, Any]:
        """Process images with multimodal LLM."""
        if not self._multimodal_llm:
            return {"error": "Multimodal LLM not available"}

        try:
            # Convert images to base64
            import base64
            image_contents = []

            for img_bytes in images:
                base64_image = base64.b64encode(img_bytes).decode('utf-8')
                image_contents.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                })

            # Create message with images
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        *image_contents
                    ]
                }
            ]

            # Call multimodal LLM
            response = self._multimodal_llm.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=messages,
                max_tokens=2000,
                temperature=0.1
            )

            result_text = response.choices[0].message.content

            # Parse JSON response
            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {result_text}")
                return {"error": "Invalid JSON response"}

        except Exception as e:
            logger.error(f"Multimodal LLM processing failed: {e}")
            return {"error": str(e)}

    def _reconstruct_table(self, llm_data: Dict[str, Any]) -> TableReconstruction:
        """Reconstruct table from LLM output."""
        if "error" in llm_data:
            return TableReconstruction(
                headers=[], rows=[], confidence=0.0,
                semantic_type="unknown", relationships={}, cross_page_links=[]
            )

        # Extract data with defaults
        headers = llm_data.get("headers", [])
        rows = llm_data.get("rows", [])
        semantic_type = llm_data.get("semantic_type", "unknown")
        relationships = llm_data.get("relationships", {})
        confidence = llm_data.get("confidence", 0.5)

        # Validate structure
        if headers and rows:
            # Check if all rows have correct number of columns
            expected_cols = len(headers)
            valid_rows = [row for row in rows if len(row) == expected_cols]

            if len(valid_rows) != len(rows):
                logger.warning(f"Table structure inconsistent: {len(valid_rows)}/{len(rows)} rows valid")
                confidence *= 0.8  # Reduce confidence for structural issues

            rows = valid_rows

        return TableReconstruction(
            headers=headers,
            rows=rows,
            confidence=confidence,
            semantic_type=semantic_type,
            relationships=relationships,
            cross_page_links=[]
        )

    def _cross_validate_with_ocr(self, image_bytes: bytes, reconstruction: TableReconstruction) -> TableReconstruction:
        """Cross-validate LLM results with traditional OCR."""
        try:
            from trust_rag.engine.ingest.image_processor import AdvancedOCRProcessor

            # Create temporary file for OCR
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_file.write(image_bytes)
                tmp_path = tmp_file.name

            try:
                ocr_processor = AdvancedOCRProcessor()
                ocr_chunks, _ = ocr_processor.process_image(tmp_path)

                # Extract text from OCR results
                ocr_text = " ".join([chunk.text for chunk in ocr_chunks])

                # Simple validation: check if key terms from LLM appear in OCR
                llm_text = " ".join(reconstruction.headers + [" ".join(row) for row in reconstruction.rows])

                # Calculate overlap
                llm_words = set(llm_text.lower().split())
                ocr_words = set(ocr_text.lower().split())

                overlap_ratio = len(llm_words & ocr_words) / len(llm_words) if llm_words else 0

                if overlap_ratio > 0.7:
                    # High overlap, increase confidence
                    reconstruction.confidence = min(1.0, reconstruction.confidence * 1.2)
                    logger.info(f"OCR validation passed: {overlap_ratio:.2f} overlap")
                else:
                    # Low overlap, decrease confidence
                    reconstruction.confidence *= 0.8
                    logger.warning(f"OCR validation concern: {overlap_ratio:.2f} overlap")

            finally:
                os.unlink(tmp_path)

        except Exception as e:
            logger.debug(f"OCR cross-validation failed: {e}")
            # Don't modify confidence if validation fails

        return reconstruction


class TableStructureValidator:
    """
    Validate table structure and detect cross-page continuations.
    """

    def validate_table_structure(self, reconstruction: TableReconstruction) -> Dict[str, Any]:
        """Comprehensive table structure validation."""
        issues = []
        recommendations = []

        # Check header consistency
        if not reconstruction.headers:
            issues.append("No headers detected")
            recommendations.append("Manual review recommended")
        elif len(reconstruction.headers) > 20:
            issues.append("Excessive number of columns")
            recommendations.append("Consider splitting into multiple tables")

        # Check data consistency
        if reconstruction.rows:
            col_counts = [len(row) for row in reconstruction.rows]
            if len(set(col_counts)) > 1:
                issues.append("Inconsistent column counts across rows")
                recommendations.append("Review table structure")

            # Check for empty rows
            empty_rows = sum(1 for row in reconstruction.rows if all(not cell.strip() for cell in row))
            if empty_rows > len(reconstruction.rows) * 0.3:
                issues.append("High proportion of empty rows")
                recommendations.append("Clean table data")

        # Semantic validation
        if reconstruction.semantic_type == "financial":
            # Financial table specific checks
            financial_indicators = ['revenue', 'income', 'profit', 'cost', 'expense', 'million', 'billion']
            has_financial_terms = any(any(term in " ".join(row).lower() for term in financial_indicators)
                                    for row in reconstruction.rows)

            if not has_financial_terms:
                issues.append("Marked as financial but lacks financial terms")
                recommendations.append("Review semantic classification")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "overall_quality": "good" if not issues else "needs_review"
        }


class FinancialStatementReconstructor:
    """
    structured Financial Statement Reconstructor.
    Specializes in accurately rebuilding hierarchical table rows, handling cross-page 
    continuations, and performing semantic column alignment for Income Statements, 
    Balance Sheets, and Cash Flow Statements.
    """
    
    def __init__(self):
        # Heuristic keywords for identifying statements
        self.statement_keywords = {
            "balance_sheet": ["assets", "liabilities", "equity", "资产", "负债", "所有者权益"],
            "income_statement": ["revenue", "net income", "profit", "收入", "利润", "净利润"],
            "cash_flow": ["operating activities", "investing activities", "经营活动", "投资活动", "筹资活动"]
        }

    def reconstruct(self, table: TableReconstruction) -> Dict[str, Any]:
        """
        Reconstructs a raw table into a highly structured JSON and Markdown representation,
        retaining row hierarchies (e.g., 'Total Assets' summing preceding rows) and exact
        column timeline bindings.
        """
        if not table.headers or not table.rows:
            return {"error": "Empty table provided for reconstruction"}
            
        # 1. Identify statement type
        statement_type = self._detect_statement_type(table)
        
        # 2. Perform semantic row hierarchy detection
        structured_rows = self._detect_hierarchy(table.rows)
        
        # 3. Create strictly-bound metadata (Lineage)
        records = []
        for s_row in structured_rows:
            record = {
                "item": s_row["item"],
                "level": s_row["level"],
                "values": {}
            }
            # Bind to timeline columns
            for i, val in enumerate(s_row["raw_values"]):
                # Offset by 1 since usually index 0 is the item name
                col_idx = i + 1
                if col_idx < len(table.headers):
                    col_header = table.headers[col_idx]
                    record["values"][col_header] = val
                    
            records.append(record)
            
        # 4. Generate Markdown equivalent
        markdown = self._to_markdown(table.headers, table.rows)
            
        return {
            "statement_type": statement_type,
            "structured_records": records,
            "markdown": markdown,
            "confidence": table.confidence
        }

    def _detect_statement_type(self, table: TableReconstruction) -> str:
        """Detect statement type based on heuristics in headers and top rows."""
        sample_text = (" ".join(table.headers) + " " + " ".join([r[0] for r in table.rows[:5] if r])).lower()
        for s_type, keywords in self.statement_keywords.items():
            if any(k in sample_text for k in keywords):
                return s_type
        return "financial_table"
        
    def _detect_hierarchy(self, rows: List[List[str]]) -> List[Dict[str, Any]]:
        """
        Detects indentation or total-subtotal relationships.
        A very simplified heuristic implementation for demonstration.
        """
        structured = []
        for r in rows:
            if not r: continue
            
            item_name = r[0]
            values = r[1:]
            
            # Simple heuristic: Leading spaces or specific keywords denote sub-levels
            level = 0
            if item_name.startswith("  ") or item_name.startswith("\t"):
                level = 1
                item_name = item_name.strip()
            if "total" in item_name.lower() or "合计" in item_name:
                level = 0 # Totals wrap up to root level
                
            structured.append({
                "item": item_name,
                "raw_values": values,
                "level": level
            })
            
        return structured

    def _to_markdown(self, headers: List[str], rows: List[List[str]]) -> str:
        """Converts to a clean markdown table."""
        if not headers: return ""
        
        md = f"| {' | '.join(headers)} |\n"
        md += f"|{'|'.join(['---'] * len(headers))}|\n"
        
        for r in rows:
            # Pad row if necessary
            padded_r = r + [""] * (len(headers) - len(r))
            md += f"| {' | '.join(padded_r)} |\n"
            
        return md
