"""
增强的金融文档解析器
Enhanced Financial Document Parser

亮点功能:
1. 表格提取和结构化 (Table Extraction)
2. 财务指标识别 (Financial Metrics Recognition)
3. 结构保留分块 (Structure-Preserving Chunking)
4. 多格式支持 (Multi-format Support)
"""
import logging
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class EnhancedPDFParser:
    """增强的PDF解析器，支持表格提取"""

    def __init__(self):
        self.has_pdfplumber = False
        self.has_pymupdf = False

        try:
            import pdfplumber
            self.has_pdfplumber = True
            logger.info("pdfplumber已加载，支持表格提取")
        except ImportError:
            logger.warning("pdfplumber未安装，表格提取功能不可用")

        try:
            import fitz
            self.has_pymupdf = True
        except ImportError:
            logger.warning("PyMuPDF未安装，PDF解析功能受限")

    def parse_with_tables(self, pdf_path: str) -> Dict:
        """
        解析PDF并提取表格

        Args:
            pdf_path: PDF文件路径

        Returns:
            包含文本、表格和元数据的字典
        """
        if not self.has_pdfplumber:
            logger.warning(f"无法提取表格: {pdf_path}, 使用基础解析")
            return self._parse_basic(pdf_path)

        try:
            import pdfplumber
            import pandas as pd

            result = {
                "text_blocks": [],
                "tables": [],
                "metadata": {}
            }

            with pdfplumber.open(pdf_path) as pdf:
                result["metadata"]["page_count"] = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages):
                    # 提取表格
                    tables = page.extract_tables()

                    for table_idx, table in enumerate(tables):
                        if not table or len(table) < 2:
                            continue

                        # 转换为DataFrame
                        try:
                            df = pd.DataFrame(table[1:], columns=table[0])

                            # 转换为Markdown格式
                            markdown_table = df.to_markdown(index=False)

                            result["tables"].append({
                                "type": "table",
                                "content": markdown_table,
                                "page": page_num + 1,
                                "table_index": table_idx,
                                "raw_data": table
                            })

                            logger.debug(f"提取表格: 页{page_num+1}, 表{table_idx+1}")
                        except Exception as e:
                            logger.warning(f"表格转换失败: {e}")

                    # 提取文本（排除表格区域）
                    text = page.extract_text()
                    if text and text.strip():
                        result["text_blocks"].append({
                            "type": "text",
                            "content": text.strip(),
                            "page": page_num + 1
                        })

            logger.info(f"PDF解析完成: {len(result['text_blocks'])}个文本块, {len(result['tables'])}个表格")
            return result

        except Exception as e:
            logger.error(f"PDF解析失败 {pdf_path}: {e}")
            return self._parse_basic(pdf_path)

    def _parse_basic(self, pdf_path: str) -> Dict:
        """基础PDF解析（无表格提取）"""
        if not self.has_pymupdf:
            return {"text_blocks": [], "tables": [], "metadata": {}}

        try:
            import fitz

            result = {
                "text_blocks": [],
                "tables": [],
                "metadata": {}
            }

            doc = fitz.open(pdf_path)
            result["metadata"]["page_count"] = len(doc)

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                if text and text.strip():
                    result["text_blocks"].append({
                        "type": "text",
                        "content": text.strip(),
                        "page": page_num + 1
                    })

            doc.close()
            return result

        except Exception as e:
            logger.error(f"基础PDF解析失败 {pdf_path}: {e}")
            return {"text_blocks": [], "tables": [], "metadata": {}}


class FinancialMetricsExtractor:
    """财务指标提取器"""

    def __init__(self):
        # 财务指标模式
        self.patterns = {
            "revenue": [
                r'营收[:：]\s*\$?([0-9,\.]+)\s*(亿|万|百万|million|billion)?',
                r'总收入[:：]\s*\$?([0-9,\.]+)\s*(亿|万|百万|million|billion)?',
                r'revenue[:：]\s*\$?([0-9,\.]+)\s*(亿|万|百万|million|billion)?',
            ],
            "net_profit": [
                r'净利润[:：]\s*\$?([0-9,\.]+)\s*(亿|万|百万|million|billion)?',
                r'net\s+profit[:：]\s*\$?([0-9,\.]+)\s*(亿|万|百万|million|billion)?',
            ],
            "eps": [
                r'EPS[:：]\s*\$?([0-9\.]+)',
                r'每股收益[:：]\s*\$?([0-9\.]+)',
            ],
            "pe_ratio": [
                r'市盈率[:：]\s*([0-9\.]+)',
                r'P/E[:：]\s*([0-9\.]+)',
            ],
            "roe": [
                r'ROE[:：]\s*([0-9\.]+)%?',
                r'净资产收益率[:：]\s*([0-9\.]+)%?',
            ],
            "gross_margin": [
                r'毛利率[:：]\s*([0-9\.]+)%',
                r'gross\s+margin[:：]\s*([0-9\.]+)%',
            ]
        }

    def extract(self, text: str) -> Dict[str, str]:
        """
        从文本中提取财务指标

        Args:
            text: 文本内容

        Returns:
            提取的财务指标字典
        """
        metrics = {}

        for metric_name, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    unit = match.group(2) if len(match.groups()) > 1 else ""

                    metrics[metric_name] = {
                        "value": value,
                        "unit": unit,
                        "raw_text": match.group(0)
                    }
                    break

        return metrics


class StructurePreservingChunker:
    """结构保留分块器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.metrics_extractor = FinancialMetricsExtractor()

    def chunk_document(self, parsed_doc: Dict, source_file: str) -> List[Dict]:
        """
        对解析后的文档进行分块，保留结构

        Args:
            parsed_doc: 解析后的文档
            source_file: 源文件名

        Returns:
            文档块列表
        """
        chunks = []
        chunk_index = 0

        # 1. 表格单独成块（不分割）
        for table in parsed_doc.get("tables", []):
            chunks.append({
                "content": table["content"],
                "metadata": {
                    "source_file": source_file,
                    "chunk_index": chunk_index,
                    "chunk_type": "table",
                    "page": table.get("page"),
                    "is_table": True
                }
            })
            chunk_index += 1

        # 2. 文本块按语义分块
        for text_block in parsed_doc.get("text_blocks", []):
            text_content = text_block["content"]
            page = text_block.get("page")

            # 提取财务指标
            metrics = self.metrics_extractor.extract(text_content)

            # 按段落分块
            text_chunks = self._chunk_text(text_content)

            for chunk_text in text_chunks:
                chunks.append({
                    "content": chunk_text,
                    "metadata": {
                        "source_file": source_file,
                        "chunk_index": chunk_index,
                        "chunk_type": "text",
                        "page": page,
                        "is_table": False,
                        "financial_metrics": metrics if metrics else None
                    }
                })
                chunk_index += 1

        return chunks

    def _chunk_text(self, text: str) -> List[str]:
        """
        文本分块（语义分块）

        Args:
            text: 文本内容

        Returns:
            文本块列表
        """
        # 按段落分割
        paragraphs = text.split('\n\n')

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前块加上新段落超过限制，保存当前块
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())

                # 保留重叠部分
                if self.chunk_overlap > 0:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        # 保存最后一块
        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks


class EnhancedDocumentParser:
    """增强的文档解析器（统一接口）"""

    def __init__(self):
        self.pdf_parser = EnhancedPDFParser()
        self.chunker = StructurePreservingChunker()
        self.metrics_extractor = FinancialMetricsExtractor()

    def parse_and_chunk(self, file_path: str) -> Dict:
        """
        解析文档并分块

        Args:
            file_path: 文件路径

        Returns:
            包含chunks和metadata的字典
        """
        file_path_obj = Path(file_path)
        suffix = file_path_obj.suffix.lower()

        if suffix == '.pdf':
            parsed_doc = self.pdf_parser.parse_with_tables(file_path)
        else:
            # 其他格式使用基础解析
            parsed_doc = self._parse_other_format(file_path)

        # 分块
        chunks = self.chunker.chunk_document(parsed_doc, file_path_obj.name)

        return {
            "file_path": file_path,
            "file_name": file_path_obj.name,
            "file_type": suffix[1:],
            "chunks": chunks,
            "metadata": parsed_doc.get("metadata", {}),
            "table_count": len(parsed_doc.get("tables", [])),
            "text_block_count": len(parsed_doc.get("text_blocks", []))
        }

    def _parse_other_format(self, file_path: str) -> Dict:
        """解析其他格式（Markdown, HTML等）"""
        # 这里可以集成之前的MarkdownProcessor和HTMLProcessor
        return {
            "text_blocks": [],
            "tables": [],
            "metadata": {}
        }


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    parser = EnhancedDocumentParser()

    # 测试PDF解析
    test_pdf = "f:/Financial_Asset_QA_System_cyx-master/data/raw_data/finance_report/TSLA_2024_Q4.pdf"

    if Path(test_pdf).exists():
        result = parser.parse_and_chunk(test_pdf)
        print(f"\n解析结果:")
        print(f"  文件: {result['file_name']}")
        print(f"  表格数: {result['table_count']}")
        print(f"  文本块数: {result['text_block_count']}")
        print(f"  总chunks: {len(result['chunks'])}")

        # 显示前3个chunks
        print(f"\n前3个chunks:")
        for i, chunk in enumerate(result['chunks'][:3]):
            print(f"\nChunk {i+1}:")
            print(f"  类型: {chunk['metadata']['chunk_type']}")
            print(f"  内容预览: {chunk['content'][:100]}...")
    else:
        print(f"测试文件不存在: {test_pdf}")
