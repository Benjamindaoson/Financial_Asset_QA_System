"""
Table Parser for GraphRAG.

This module provides advanced table parsing and understanding capabilities,
extracting structured data from documents and converting to graph representations.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import re
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class TableParser:
    """
    Advanced table parser for extracting structured data from documents.

    Supports multiple table formats (HTML, image-based, structured text)
    and converts table data to graph-compatible representations.
    """

    def __init__(self):
        """Initialize table parser."""
        # Patterns for table detection and parsing
        self.table_patterns = {
            'html_table': re.compile(r'<table[^>]*>.*?</table>', re.DOTALL | re.IGNORECASE),
            'markdown_table': re.compile(r'\|.*\|\n\|[-\s|:]+\|\n(?:\|.*\|\n)+', re.MULTILINE),
            'csv_like': re.compile(r'(?:^|\n)([^,\n]+(?:,[^,\n]+)+)(?:\n|$)', re.MULTILINE),
        }

        # Financial data patterns
        self.financial_patterns = {
            'currency': re.compile(r'\$[\d,]+(?:\.\d+)?|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:USD|EUR|GBP|CNY|JPY)\b', re.IGNORECASE),
            'percentage': re.compile(r'\d+(?:\.\d+)?%'),
            'year': re.compile(r'\b(?:FY|FY\s*)?(\d{4})\b'),
            'quarter': re.compile(r'\bQ[1-4]\s*\d{4}\b', re.IGNORECASE),
            'million_billion': re.compile(r'\b\d+(?:\.\d+)?\s*(M|B|MM|BN|million|billion)\b', re.IGNORECASE),
        }

        logger.info("Table parser initialized")

    def parse_html_table(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parse HTML tables from content.

        Args:
            html_content: HTML content containing tables

        Returns:
            List of parsed table data
        """
        tables = []

        try:
            # Find all table elements
            table_matches = self.table_patterns['html_table'].findall(html_content)

            for table_html in table_matches:
                table_data = self._parse_single_html_table(table_html)
                if table_data:
                    tables.append(table_data)

        except Exception as e:
            logger.error(f"Failed to parse HTML tables: {e}")

        return tables

    def parse_markdown_table(self, markdown_content: str) -> List[Dict[str, Any]]:
        """
        Parse Markdown tables from content.

        Args:
            markdown_content: Markdown content containing tables

        Returns:
            List of parsed table data
        """
        tables = []

        try:
            # Find all markdown table blocks
            table_matches = self.table_patterns['markdown_table'].findall(markdown_content)

            for table_md in table_matches:
                table_data = self._parse_single_markdown_table(table_md)
                if table_data:
                    tables.append(table_data)

        except Exception as e:
            logger.error(f"Failed to parse Markdown tables: {e}")

        return tables

    def parse_structured_text(self, text_content: str) -> List[Dict[str, Any]]:
        """
        Parse tables from structured text (CSV-like, fixed-width).

        Args:
            text_content: Text content containing table-like structures

        Returns:
            List of parsed table data
        """
        tables = []

        try:
            # Try CSV-like parsing
            lines = text_content.strip().split('\n')
            if len(lines) >= 2:
                # Check if lines have similar structure (similar number of separators)
                csv_tables = self._extract_csv_like_tables(lines)
                tables.extend(csv_tables)

            # Try fixed-width table detection
            fixed_width_tables = self._extract_fixed_width_tables(lines)
            tables.extend(fixed_width_tables)

        except Exception as e:
            logger.error(f"Failed to parse structured text tables: {e}")

        return tables

    def extract_table_from_image(self, image_path: str, ocr_results: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Extract table data from image using OCR and table detection.

        Args:
            image_path: Path to image containing table
            ocr_results: Pre-computed OCR results (optional)

        Returns:
            Parsed table data or None
        """
        try:
            # This would integrate with OCR engine and table detection
            # For now, return a placeholder structure
            return {
                "table_id": f"table_from_image_{hash(image_path) % 10000}",
                "source": "image",
                "headers": [],  # Would be extracted by OCR
                "rows": [],     # Would be extracted by table detection
                "metadata": {
                    "extraction_method": "ocr_table_detection",
                    "confidence": 0.0
                }
            }

        except Exception as e:
            logger.error(f"Failed to extract table from image {image_path}: {e}")
            return None

    def convert_table_to_graph_format(self, table_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parsed table data to graph-compatible format.

        Args:
            table_data: Parsed table data

        Returns:
            Graph-compatible table representation
        """
        try:
            headers = table_data.get("headers", [])
            rows = table_data.get("rows", [])

            # Create graph nodes for table structure
            graph_format = {
                "table_node": {
                    "id": table_data.get("table_id", f"table_{hash(str(table_data)) % 10000}"),
                    "type": "table",
                    "properties": {
                        "headers": headers,
                        "row_count": len(rows),
                        "column_count": len(headers),
                        "table_type": self._classify_table_type(headers, rows)
                    }
                },
                "header_nodes": [],
                "cell_nodes": [],
                "relationships": []
            }

            # Create header nodes
            for col_idx, header in enumerate(headers):
                header_node = {
                    "id": f"header_{graph_format['table_node']['id']}_{col_idx}",
                    "type": "table_header",
                    "properties": {
                        "text": header,
                        "column_index": col_idx,
                        "table_id": graph_format['table_node']['id'],
                        "data_type": self._infer_column_type(header, [row[col_idx] for row in rows if col_idx < len(row)])
                    }
                }
                graph_format["header_nodes"].append(header_node)

                # Relationship: table -> header
                graph_format["relationships"].append({
                    "source": graph_format['table_node']['id'],
                    "target": header_node["id"],
                    "type": "has_header",
                    "properties": {"position": col_idx}
                })

            # Create cell nodes and extract metrics
            for row_idx, row in enumerate(rows):
                for col_idx, cell_value in enumerate(row):
                    if col_idx < len(headers):
                        cell_id = f"cell_{graph_format['table_node']['id']}_{row_idx}_{col_idx}"
                        cell_node = {
                            "id": cell_id,
                            "type": "table_cell",
                            "properties": {
                                "value": str(cell_value),
                                "row_index": row_idx,
                                "column_index": col_idx,
                                "table_id": graph_format['table_node']['id'],
                                "header": headers[col_idx] if col_idx < len(headers) else "",
                                "is_metric": self._is_metric_value(str(cell_value))
                            }
                        }

                        # Extract additional properties for metrics
                        if cell_node["properties"]["is_metric"]:
                            cell_node["properties"].update(self._extract_metric_properties(str(cell_value)))

                        graph_format["cell_nodes"].append(cell_node)

                        # Relationship: header -> cell
                        header_id = f"header_{graph_format['table_node']['id']}_{col_idx}"
                        graph_format["relationships"].append({
                            "source": header_id,
                            "target": cell_id,
                            "type": "has_cell",
                            "properties": {"row": row_idx}
                        })

                        # Relationship: table -> cell
                        graph_format["relationships"].append({
                            "source": graph_format['table_node']['id'],
                            "target": cell_id,
                            "type": "contains",
                            "properties": {"position": f"{row_idx},{col_idx}"}
                        })

            return graph_format

        except Exception as e:
            logger.error(f"Failed to convert table to graph format: {e}")
            return {}

    def _parse_single_html_table(self, table_html: str) -> Optional[Dict[str, Any]]:
        """Parse a single HTML table."""
        try:
            # Simple HTML table parsing (would use BeautifulSoup in production)
            # Extract headers
            headers = []
            header_matches = re.findall(r'<th[^>]*>(.*?)</th>', table_html, re.IGNORECASE)
            if header_matches:
                headers = [self._clean_html_text(h) for h in header_matches]

            # Extract rows
            rows = []
            row_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.IGNORECASE | re.DOTALL)

            for row_match in row_matches:
                cell_matches = re.findall(r'<td[^>]*>(.*?)</td>', row_match, re.IGNORECASE)
                if cell_matches:
                    row = [self._clean_html_text(cell) for cell in cell_matches]
                    rows.append(row)

            if headers or rows:
                return {
                    "table_id": f"html_table_{hash(table_html) % 10000}",
                    "source": "html",
                    "headers": headers,
                    "rows": rows,
                    "metadata": {
                        "extraction_method": "html_parsing",
                        "confidence": 0.9 if headers else 0.7
                    }
                }

            return None

        except Exception as e:
            logger.error(f"Failed to parse HTML table: {e}")
            return None

    def _parse_single_markdown_table(self, table_md: str) -> Optional[Dict[str, Any]]:
        """Parse a single Markdown table."""
        try:
            lines = table_md.strip().split('\n')

            # First line should be headers
            if len(lines) < 2:
                return None

            headers = [cell.strip() for cell in lines[0].split('|')[1:-1]]

            # Skip separator line and parse data rows
            rows = []
            for line in lines[2:]:
                if '|' in line:
                    cells = [cell.strip() for cell in line.split('|')[1:-1]]
                    if cells and any(cell for cell in cells):  # Skip empty rows
                        rows.append(cells)

            return {
                "table_id": f"md_table_{hash(table_md) % 10000}",
                "source": "markdown",
                "headers": headers,
                "rows": rows,
                "metadata": {
                    "extraction_method": "markdown_parsing",
                    "confidence": 0.9
                }
            }

        except Exception as e:
            logger.error(f"Failed to parse Markdown table: {e}")
            return None

    def _extract_csv_like_tables(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Extract CSV-like tables from text lines."""
        tables = []

        try:
            # Look for consecutive lines with similar comma patterns
            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Check if line looks like CSV
                if ',' in line and not line.startswith('#'):
                    # Try to parse as CSV block
                    table_lines = []
                    start_idx = i

                    # Collect consecutive CSV-like lines
                    while i < len(lines):
                        curr_line = lines[i].strip()
                        if ',' in curr_line and not curr_line.startswith('#'):
                            table_lines.append(curr_line)
                            i += 1
                        else:
                            break

                    if len(table_lines) >= 2:  # At least header + 1 data row
                        table_data = self._parse_csv_block(table_lines)
                        if table_data:
                            tables.append(table_data)
                    else:
                        i = start_idx + 1
                else:
                    i += 1

        except Exception as e:
            logger.error(f"Failed to extract CSV tables: {e}")

        return tables

    def _parse_csv_block(self, lines: List[str]) -> Optional[Dict[str, Any]]:
        """Parse a block of CSV-like lines."""
        try:
            # Simple CSV parsing (would use csv module in production)
            headers = [cell.strip() for cell in lines[0].split(',')]
            rows = []

            for line in lines[1:]:
                cells = [cell.strip() for cell in line.split(',')]
                if len(cells) == len(headers):  # Ensure consistent column count
                    rows.append(cells)

            if rows:
                return {
                    "table_id": f"csv_table_{hash(str(lines)) % 10000}",
                    "source": "csv",
                    "headers": headers,
                    "rows": rows,
                    "metadata": {
                        "extraction_method": "csv_parsing",
                        "confidence": 0.8
                    }
                }

            return None

        except Exception as e:
            logger.error(f"Failed to parse CSV block: {e}")
            return None

    def _extract_fixed_width_tables(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Extract fixed-width tables from text lines."""
        # Simplified implementation - would need more sophisticated logic
        return []

    def _classify_table_type(self, headers: List[str], rows: List[List[str]]) -> str:
        """Classify table type based on headers and content."""
        header_text = ' '.join(headers).lower()

        # Financial table indicators
        if any(word in header_text for word in ['revenue', 'profit', 'income', 'earnings', 'sales']):
            return 'financial'

        # Comparison table indicators
        if len(rows) > 1 and len(set(len(row) for row in rows)) == 1:  # Consistent columns
            return 'comparison'

        # Data table indicators
        if len(rows) > 5:
            return 'data'

        return 'general'

    def _infer_column_type(self, header: str, values: List[str]) -> str:
        """Infer column data type."""
        header_lower = header.lower()

        # Financial columns
        if any(word in header_lower for word in ['revenue', 'profit', 'income', 'cost', 'expense', 'sales']):
            return 'currency'

        # Percentage columns
        if 'percent' in header_lower or '%' in header:
            return 'percentage'

        # Date columns
        if any(word in header_lower for word in ['year', 'quarter', 'date', 'period']):
            return 'date'

        # Numeric columns
        numeric_count = sum(1 for v in values if self._is_numeric(v))
        if numeric_count / len(values) > 0.8:
            return 'numeric'

        return 'text'

    def _is_metric_value(self, value: str) -> bool:
        """Check if a value represents a metric."""
        for pattern in self.financial_patterns.values():
            if pattern.search(value):
                return True
        return False

    def _is_numeric(self, value: str) -> bool:
        """Check if a value is numeric."""
        try:
            float(value.replace(',', '').replace('$', '').replace('%', ''))
            return True
        except ValueError:
            return False

    def _extract_metric_properties(self, value: str) -> Dict[str, Any]:
        """Extract properties from metric values."""
        properties = {}

        # Extract currency
        currency_match = self.financial_patterns['currency'].search(value)
        if currency_match:
            properties['currency'] = 'USD'  # Default
            properties['numeric_value'] = self._extract_numeric_value(value)

        # Extract percentage
        pct_match = self.financial_patterns['percentage'].search(value)
        if pct_match:
            properties['percentage'] = float(pct_match.group().replace('%', ''))
            properties['numeric_value'] = properties['percentage'] / 100

        # Extract scale (million, billion)
        scale_match = self.financial_patterns['million_billion'].search(value)
        if scale_match:
            scale_text = scale_match.group().split()[-1].lower()
            if scale_text in ['m', 'million']:
                properties['scale'] = 1000000
            elif scale_text in ['b', 'bn', 'billion']:
                properties['scale'] = 1000000000

        return properties

    def _extract_numeric_value(self, value: str) -> Optional[float]:
        """Extract numeric value from formatted string."""
        try:
            # Remove common formatting
            clean_value = value.replace('$', '').replace(',', '').replace('%', '').strip()

            # Handle scale suffixes
            if 'M' in clean_value:
                return float(clean_value.replace('M', '')) * 1000000
            elif 'B' in clean_value:
                return(clean_value.replace('B', '')) * 1000000000
            else:
                return float(clean_value)
        except ValueError:
            return None

    def _clean_html_text(self, html_text: str) -> str:
        """Clean HTML tags from text."""
        # Simple HTML tag removal (would use BeautifulSoup in production)
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        return clean_text.strip()







