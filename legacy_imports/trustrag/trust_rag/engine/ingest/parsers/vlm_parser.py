"""
VLM Document Parser: Qwen2-VL (2026 Production Upgrade).

Replaces Tesseract/PaddleOCR with Vision-Language Models for superior document understanding.
Specialized for financial documents: tables, charts, complex layouts.
"""
import logging
import base64
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
from PIL import Image
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoTokenizer, AutoProcessor

from trust_rag.engine.ingest.parsers.base import BaseIngestParser, ParsedChunk
from trust_rag.config import get_config

logger = logging.getLogger(__name__)


class QwenVLDocumentParser(BaseIngestParser):
    """
    Qwen2-VL Document Parser for financial documents.

    Key improvements over OCR:
    - Understands document structure and layout
    - Recognizes tables as structured data
    - Handles complex financial charts
    - Multi-page document understanding
    - Better handling of scanned/faxed documents
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2-VL-7B-Instruct",
        cache_dir: Optional[str] = None,
        device: str = "auto",
        max_tokens: int = 2048,
        temperature: float = 0.1
    ):
        """
        Initialize Qwen2-VL parser.

        Args:
            model_name: HuggingFace model name
            cache_dir: Model cache directory
            device: Device to run model on
            max_tokens: Maximum tokens for generation
            temperature: Generation temperature
        """
        self.model_name = model_name
        self.cache_dir = cache_dir or get_config().embedding.cache_dir
        self.device = device
        self.max_tokens = max_tokens
        self.temperature = temperature

        self.model = None
        self.processor = None
        self.tokenizer = None
        self._load_model()

    def _load_model(self):
        """Load Qwen2-VL model and processor."""
        try:
            logger.info(f"Loading Qwen2-VL model: {self.model_name}")

            # Determine device
            if self.device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"

            # Load processor and tokenizer
            self.processor = AutoProcessor.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )

            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )

            # Load model
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None
            )

            if self.device == "cpu":
                self.model.to(self.device)

            self.model.eval()

            logger.info(f"Qwen2-VL loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load Qwen2-VL model: {e}")
            raise

    def parse_image(
        self,
        image_path: Union[str, Path],
        page_number: int = 1,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse document image using VLM.

        Args:
            image_path: Path to image file
            page_number: Page number for metadata
            context: Optional context about the document

        Returns:
            Parsed content with structured data
        """
        try:
            # Load and preprocess image
            image = Image.open(image_path).convert('RGB')

            # Create VLM prompt for financial document understanding
            prompt = self._create_financial_parsing_prompt(context)

            # Prepare inputs
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]

            # Apply chat template
            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

            # Process inputs
            inputs = self.processor(
                text=[text],
                images=[image],
                return_tensors="pt"
            ).to(self.device)

            # Generate response
            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=self.max_tokens,
                    temperature=self.temperature,
                    do_sample=self.temperature > 0,
                    pad_token_id=self.tokenizer.pad_token_id
                )

            # Decode response
            generated_text = self.processor.batch_decode(
                generated_ids[:, inputs.input_ids.shape[1]:],
                skip_special_tokens=True
            )[0].strip()

            # Parse structured output
            parsed_data = self._parse_vlm_response(generated_text)

            return {
                "success": True,
                "page_number": page_number,
                "content": parsed_data,
                "raw_response": generated_text,
                "confidence": self._estimate_confidence(parsed_data)
            }

        except Exception as e:
            logger.error(f"VLM parsing failed for {image_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "page_number": page_number,
                "content": {},
                "confidence": 0.0
            }

    def _create_financial_parsing_prompt(self, context: Optional[str] = None) -> str:
        """Create specialized prompt for financial document parsing."""
        base_prompt = """
        You are an expert financial document analyzer. Analyze this financial document image and extract:

        1. TEXT CONTENT: Extract all readable text, maintaining original formatting
        2. TABLES: Identify and extract tables as structured data (JSON format)
        3. CHARTS/GRAPHS: Describe any charts, graphs, or visual data
        4. KEY METRICS: Extract important financial numbers and their context
        5. DOCUMENT STRUCTURE: Identify sections, headers, and document type

        Return the analysis in this exact JSON format:
        {
            "document_type": "balance_sheet|income_statement|annual_report|10k|10q|etc",
            "text_content": "full text content here",
            "tables": [
                {
                    "title": "table title",
                    "headers": ["col1", "col2", ...],
                    "rows": [["val1", "val2", ...], ...]
                }
            ],
            "charts": [
                {
                    "type": "bar|line|pie|etc",
                    "title": "chart title",
                    "description": "detailed description of data"
                }
            ],
            "key_metrics": [
                {
                    "metric": "revenue",
                    "value": "1000000",
                    "unit": "USD",
                    "period": "FY2023",
                    "context": "total revenue"
                }
            ],
            "sections": ["section1", "section2", ...]
        }

        IMPORTANT:
        - Be precise with numbers and maintain original formatting
        - Identify document type accurately
        - Extract tables as structured data, not text
        - Include units and time periods for metrics
        - If uncertain, mark confidence appropriately
        """

        if context:
            base_prompt += f"\n\nAdditional context: {context}"

        return base_prompt

    def _parse_vlm_response(self, response: str) -> Dict[str, Any]:
        """Parse VLM JSON response with error handling."""
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
            else:
                # Fallback: create structured response from text
                return {
                    "document_type": "unknown",
                    "text_content": response,
                    "tables": [],
                    "charts": [],
                    "key_metrics": [],
                    "sections": []
                }

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse VLM JSON response: {response[:200]}...")
            return {
                "document_type": "unknown",
                "text_content": response,
                "tables": [],
                "charts": [],
                "key_metrics": [],
                "sections": []
            }

    def _estimate_confidence(self, parsed_data: Dict[str, Any]) -> float:
        """Estimate parsing confidence based on extracted data quality."""
        confidence = 0.5  # Base confidence

        # Boost confidence based on data completeness
        if parsed_data.get("document_type") != "unknown":
            confidence += 0.1

        if parsed_data.get("text_content"):
            confidence += 0.2

        if parsed_data.get("tables"):
            confidence += 0.1 * min(len(parsed_data["tables"]), 3)

        if parsed_data.get("key_metrics"):
            confidence += 0.1 * min(len(parsed_data["key_metrics"]), 5)

        if parsed_data.get("charts"):
            confidence += 0.05 * min(len(parsed_data["charts"]), 2)

        return min(confidence, 1.0)

    def parse_document(
        self,
        file_path: Union[str, Path],
        doc_id: str = "",
        **kwargs
    ) -> List[ParsedChunk]:
        """
        Parse document using VLM (implements BaseIngestParser interface).

        Args:
            file_path: Path to document file
            doc_id: Document ID for metadata
            **kwargs: Additional parsing options

        Returns:
            List of ParsedChunk objects
        """
        file_path = Path(file_path)
        chunks = []

        try:
            if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
                # Single image parsing
                result = self.parse_image(file_path, page_number=1)

                if result["success"]:
                    # Create chunks from parsed content
                    chunks.extend(self._create_chunks_from_parsed_data(
                        result["content"], doc_id, result["page_number"]
                    ))

            elif file_path.suffix.lower() == '.pdf':
                # PDF parsing (convert pages to images first)
                chunks.extend(self._parse_pdf_pages(file_path, doc_id))

            else:
                logger.warning(f"Unsupported file type for VLM parsing: {file_path.suffix}")

        except Exception as e:
            logger.error(f"VLM document parsing failed for {file_path}: {e}")

        return chunks

    def _parse_pdf_pages(self, pdf_path: Path, doc_id: str) -> List[ParsedChunk]:
        """Parse PDF by converting pages to images."""
        chunks = []

        try:
            from pdf2image import convert_from_path

            # Convert PDF pages to images
            images = convert_from_path(pdf_path, dpi=300)

            for page_num, image in enumerate(images, 1):
                # Save temporary image
                temp_image_path = pdf_path.parent / f"temp_page_{page_num}.png"
                image.save(temp_image_path, "PNG")

                try:
                    # Parse image
                    result = self.parse_image(temp_image_path, page_number=page_num)

                    if result["success"]:
                        page_chunks = self._create_chunks_from_parsed_data(
                            result["content"], doc_id, page_num
                        )
                        chunks.extend(page_chunks)

                finally:
                    # Clean up temporary image
                    if temp_image_path.exists():
                        temp_image_path.unlink()

        except ImportError:
            logger.error("pdf2image not installed. Install with: pip install pdf2image")
        except Exception as e:
            logger.error(f"PDF page parsing failed: {e}")

        return chunks

    def _create_chunks_from_parsed_data(
        self,
        parsed_data: Dict[str, Any],
        doc_id: str,
        page_number: int
    ) -> List[ParsedChunk]:
        """Create ParsedChunk objects from VLM parsed data."""
        chunks = []

        # Text content chunk
        if parsed_data.get("text_content"):
            chunks.append(ParsedChunk(
                text=parsed_data["text_content"],
                metadata={
                    "doc_id": doc_id,
                    "page_number": page_number,
                    "modality": "text_native",
                    "parser": "qwen_vlm",
                    "document_type": parsed_data.get("document_type", "unknown"),
                    "confidence": 0.9
                }
            ))

        # Table chunks
        for i, table in enumerate(parsed_data.get("tables", [])):
            if table.get("rows"):
                # Convert table to text representation
                table_text = self._table_to_text(table)
                chunks.append(ParsedChunk(
                    text=table_text,
                    metadata={
                        "doc_id": doc_id,
                        "page_number": page_number,
                        "modality": "table_native",
                        "parser": "qwen_vlm",
                        "table_index": i,
                        "table_title": table.get("title", ""),
                        "confidence": 0.95
                    }
                ))

        # Chart descriptions
        for i, chart in enumerate(parsed_data.get("charts", [])):
            chunks.append(ParsedChunk(
                text=chart.get("description", ""),
                metadata={
                    "doc_id": doc_id,
                    "page_number": page_number,
                    "modality": "chart",
                    "parser": "qwen_vlm",
                    "chart_index": i,
                    "chart_type": chart.get("type", "unknown"),
                    "confidence": 0.8
                }
            ))

        # Key metrics as structured data
        for metric in parsed_data.get("key_metrics", []):
            metric_text = f"{metric['metric']}: {metric['value']} {metric.get('unit', '')} ({metric.get('period', '')})"
            if metric.get("context"):
                metric_text += f" - {metric['context']}"

            chunks.append(ParsedChunk(
                text=metric_text,
                metadata={
                    "doc_id": doc_id,
                    "page_number": page_number,
                    "modality": "text_native",
                    "parser": "qwen_vlm",
                    "metric_type": "financial",
                    "metric_name": metric["metric"],
                    "metric_value": metric["value"],
                    "metric_unit": metric.get("unit", ""),
                    "metric_period": metric.get("period", ""),
                    "confidence": 0.95
                }
            ))

        return chunks

    def _table_to_text(self, table: Dict[str, Any]) -> str:
        """Convert structured table to readable text."""
        text_parts = []

        if table.get("title"):
            text_parts.append(f"Table: {table['title']}")

        headers = table.get("headers", [])
        rows = table.get("rows", [])

        if headers:
            text_parts.append(" | ".join(headers))

        for row in rows:
            if isinstance(row, list):
                text_parts.append(" | ".join(str(cell) for cell in row))

        return "\n".join(text_parts)

    def get_parser_info(self) -> Dict[str, Any]:
        """Get parser information."""
        return {
            "parser_name": "qwen_vlm",
            "model": self.model_name,
            "device": self.device,
            "supports_tables": True,
            "supports_charts": True,
            "supports_multipage": True,
            "financial_optimized": True,
            "fallback_available": True
        }
