"""
完整的RAG数据处理管道
Complete RAG Data Processing Pipeline

处理raw_data中的所有数据：
1. 财报数据（PDF、HTML、Markdown）
2. 知识文档（Markdown、PDF）
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
import hashlib
import json

logger = logging.getLogger(__name__)


class DataProcessor:
    """数据处理器基类"""

    def __init__(self):
        self.processed_count = 0
        self.failed_count = 0
        self.errors = []

    def process(self, file_path: str) -> Optional[Dict]:
        """
        处理单个文件

        Args:
            file_path: 文件路径

        Returns:
            处理后的文档字典，包含content、metadata等
        """
        raise NotImplementedError

    def get_file_hash(self, file_path: str) -> str:
        """计算文件哈希值，用于去重"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()


class MarkdownProcessor(DataProcessor):
    """Markdown文件处理器"""

    def process(self, file_path: str) -> Optional[Dict]:
        """
        处理Markdown文件

        Args:
            file_path: Markdown文件路径

        Returns:
            文档字典
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取元数据（YAML front matter）
            metadata = self._extract_metadata(content)

            # 提取正文
            main_content = self._extract_content(content)

            # 分块
            chunks = self._chunk_content(main_content, file_path)

            self.processed_count += 1

            return {
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "file_type": "markdown",
                "metadata": metadata,
                "chunks": chunks,
                "file_hash": self.get_file_hash(file_path)
            }

        except Exception as e:
            logger.error(f"处理Markdown文件失败 {file_path}: {e}")
            self.failed_count += 1
            self.errors.append({"file": file_path, "error": str(e)})
            return None

    def _extract_metadata(self, content: str) -> Dict:
        """提取YAML front matter"""
        metadata = {}

        if content.startswith('---'):
            # 提取YAML部分
            parts = content.split('---', 2)
            if len(parts) >= 3:
                yaml_content = parts[1].strip()

                # 简单解析YAML（不依赖yaml库）
                for line in yaml_content.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()

                        # 处理列表
                        if value.startswith('[') and value.endswith(']'):
                            value = [v.strip() for v in value[1:-1].split(',')]

                        metadata[key] = value

        return metadata

    def _extract_content(self, content: str) -> str:
        """提取正文内容（去除YAML front matter）"""
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                return parts[2].strip()

        return content

    def _chunk_content(self, content: str, file_path: str, chunk_size: int = 500) -> List[Dict]:
        """
        将内容分块

        Args:
            content: 文档内容
            file_path: 文件路径
            chunk_size: 每块的字符数

        Returns:
            分块列表
        """
        chunks = []

        # 按段落分割
        paragraphs = content.split('\n\n')

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前块加上新段落超过限制，保存当前块
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "source_file": os.path.basename(file_path)
                })
                current_chunk = para
                chunk_index += 1
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        # 保存最后一块
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "chunk_index": chunk_index,
                "source_file": os.path.basename(file_path)
            })

        return chunks


class PDFProcessor(DataProcessor):
    """PDF文件处理器"""

    def __init__(self):
        super().__init__()
        self.has_pymupdf = False

        try:
            import fitz  # PyMuPDF
            self.has_pymupdf = True
        except ImportError:
            logger.warning("PyMuPDF未安装，PDF处理功能受限")

    def process(self, file_path: str) -> Optional[Dict]:
        """
        处理PDF文件

        Args:
            file_path: PDF文件路径

        Returns:
            文档字典
        """
        if not self.has_pymupdf:
            logger.error(f"无法处理PDF文件 {file_path}: PyMuPDF未安装")
            self.failed_count += 1
            return None

        try:
            import fitz

            doc = fitz.open(file_path)

            # 提取所有页面文本
            full_text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                full_text += page.get_text()

            doc.close()

            # 分块
            chunks = self._chunk_content(full_text, file_path)

            self.processed_count += 1

            return {
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "file_type": "pdf",
                "metadata": {
                    "page_count": len(doc),
                },
                "chunks": chunks,
                "file_hash": self.get_file_hash(file_path)
            }

        except Exception as e:
            logger.error(f"处理PDF文件失败 {file_path}: {e}")
            self.failed_count += 1
            self.errors.append({"file": file_path, "error": str(e)})
            return None

    def _chunk_content(self, content: str, file_path: str, chunk_size: int = 500) -> List[Dict]:
        """将PDF内容分块"""
        chunks = []
        lines = content.split('\n')

        current_chunk = ""
        chunk_index = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if len(current_chunk) + len(line) > chunk_size and current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "source_file": os.path.basename(file_path)
                })
                current_chunk = line
                chunk_index += 1
            else:
                current_chunk += "\n" + line if current_chunk else line

        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "chunk_index": chunk_index,
                "source_file": os.path.basename(file_path)
            })

        return chunks


class HTMLProcessor(DataProcessor):
    """HTML文件处理器"""

    def __init__(self):
        super().__init__()
        self.has_bs4 = False

        try:
            from bs4 import BeautifulSoup
            self.has_bs4 = True
        except ImportError:
            logger.warning("BeautifulSoup未安装，HTML处理功能受限")

    def process(self, file_path: str) -> Optional[Dict]:
        """
        处理HTML文件

        Args:
            file_path: HTML文件路径

        Returns:
            文档字典
        """
        if not self.has_bs4:
            logger.error(f"无法处理HTML文件 {file_path}: BeautifulSoup未安装")
            self.failed_count += 1
            return None

        try:
            from bs4 import BeautifulSoup

            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'html.parser')

            # 移除script和style标签
            for script in soup(["script", "style"]):
                script.decompose()

            # 提取文本
            text = soup.get_text()

            # 清理空白
            lines = (line.strip() for line in text.splitlines())
            chunks_text = '\n'.join(line for line in lines if line)

            # 分块
            chunks = self._chunk_content(chunks_text, file_path)

            self.processed_count += 1

            return {
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "file_type": "html",
                "metadata": {
                    "title": soup.title.string if soup.title else ""
                },
                "chunks": chunks,
                "file_hash": self.get_file_hash(file_path)
            }

        except Exception as e:
            logger.error(f"处理HTML文件失败 {file_path}: {e}")
            self.failed_count += 1
            self.errors.append({"file": file_path, "error": str(e)})
            return None

    def _chunk_content(self, content: str, file_path: str, chunk_size: int = 500) -> List[Dict]:
        """将HTML内容分块"""
        chunks = []
        paragraphs = content.split('\n\n')

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "source_file": os.path.basename(file_path)
                })
                current_chunk = para
                chunk_index += 1
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "chunk_index": chunk_index,
                "source_file": os.path.basename(file_path)
            })

        return chunks


class RAGDataPipeline:
    """RAG数据处理管道"""

    def __init__(self, raw_data_dir: str, output_dir: str):
        """
        初始化数据管道

        Args:
            raw_data_dir: 原始数据目录
            output_dir: 输出目录
        """
        self.raw_data_dir = Path(raw_data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化处理器
        self.processors = {
            '.md': MarkdownProcessor(),
            '.pdf': PDFProcessor(),
            '.html': HTMLProcessor(),
        }

        self.processed_documents = []
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "total_chunks": 0
        }

    def process_all(self) -> Dict:
        """
        处理所有文件

        Returns:
            处理统计信息
        """
        logger.info(f"开始处理数据目录: {self.raw_data_dir}")

        # 遍历所有文件
        for file_path in self.raw_data_dir.rglob('*'):
            if file_path.is_file():
                self.stats["total_files"] += 1
                self._process_file(file_path)

        # 保存处理结果
        self._save_results()

        # 更新统计
        self.stats["processed_files"] = sum(
            p.processed_count for p in self.processors.values()
        )
        self.stats["failed_files"] = sum(
            p.failed_count for p in self.processors.values()
        )
        self.stats["total_chunks"] = sum(
            len(doc["chunks"]) for doc in self.processed_documents
        )

        logger.info(f"处理完成: {self.stats}")

        return self.stats

    def _process_file(self, file_path: Path):
        """处理单个文件"""
        suffix = file_path.suffix.lower()

        if suffix not in self.processors:
            logger.debug(f"跳过不支持的文件类型: {file_path}")
            return

        processor = self.processors[suffix]
        result = processor.process(str(file_path))

        if result:
            self.processed_documents.append(result)
            logger.info(f"成功处理: {file_path.name} ({len(result['chunks'])} chunks)")

    def _save_results(self):
        """保存处理结果"""
        output_file = self.output_dir / "processed_documents.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.processed_documents, f, ensure_ascii=False, indent=2)

        logger.info(f"处理结果已保存到: {output_file}")

        # 保存统计信息
        stats_file = self.output_dir / "processing_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)

    def get_all_chunks(self) -> List[Dict]:
        """
        获取所有文档块

        Returns:
            所有文档块的列表
        """
        all_chunks = []

        for doc in self.processed_documents:
            for chunk in doc["chunks"]:
                # 合并文档元数据和块信息
                chunk_with_metadata = {
                    "content": chunk["content"],
                    "metadata": {
                        "source_file": doc["file_name"],
                        "file_type": doc["file_type"],
                        "chunk_index": chunk["chunk_index"],
                        **doc.get("metadata", {})
                    }
                }
                all_chunks.append(chunk_with_metadata)

        return all_chunks
