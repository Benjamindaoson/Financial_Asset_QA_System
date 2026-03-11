"""
统一数据加载器 - 支持多种格式的数据加载
Unified Data Loader - Support Multiple Format Data Loading

支持格式：
- Markdown (.md)
- PDF (.pdf) - 使用 MinerU 解析
- JSON (.json)
- HTML (.html)
"""
import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """文档数据结构"""
    content: str
    metadata: Dict[str, Any]
    doc_id: str
    source_file: str
    source_type: str  # "markdown", "pdf", "json", "html"


class UnifiedDataLoader:
    """
    统一数据加载器

    功能：
    1. 自动识别文件格式
    2. 统一的文档输出格式
    3. 提取基础元数据
    4. 生成唯一文档ID
    """

    SUPPORTED_FORMATS = {
        ".md": "markdown",
        ".markdown": "markdown",
        ".pdf": "pdf",
        ".json": "json",
        ".html": "html",
        ".htm": "html"
    }

    def __init__(self):
        """初始化数据加载器"""
        self.loaded_count = 0
        self.error_count = 0
        self.error_files = []

    def load_file(self, file_path: str) -> Optional[Document]:
        """
        加载单个文件

        Args:
            file_path: 文件路径

        Returns:
            Document 对象，失败返回 None
        """
        path = Path(file_path)

        if not path.exists():
            logger.error(f"文件不存在: {file_path}")
            self.error_count += 1
            self.error_files.append(file_path)
            return None

        # 识别文件格式
        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            logger.warning(f"不支持的文件格式: {suffix} ({file_path})")
            self.error_count += 1
            self.error_files.append(file_path)
            return None

        source_type = self.SUPPORTED_FORMATS[suffix]

        try:
            # 根据格式调用对应的加载器
            if source_type == "markdown":
                doc = self._load_markdown(path)
            elif source_type == "pdf":
                doc = self._load_pdf(path)
            elif source_type == "json":
                doc = self._load_json(path)
            elif source_type == "html":
                doc = self._load_html(path)
            else:
                logger.error(f"未实现的加载器: {source_type}")
                return None

            if doc:
                self.loaded_count += 1
                logger.info(f"成功加载: {file_path} ({source_type})")

            return doc

        except Exception as e:
            logger.error(f"加载文件失败: {file_path}, 错误: {e}", exc_info=True)
            self.error_count += 1
            self.error_files.append(file_path)
            return None

    def load_directory(
        self,
        dir_path: str,
        recursive: bool = True,
        file_pattern: Optional[str] = None
    ) -> List[Document]:
        """
        加载目录中的所有文件

        Args:
            dir_path: 目录路径
            recursive: 是否递归子目录
            file_pattern: 文件匹配模式（如 "*.md"）

        Returns:
            Document 列表
        """
        path = Path(dir_path)

        if not path.exists() or not path.is_dir():
            logger.error(f"目录不存在: {dir_path}")
            return []

        documents = []

        # 获取文件列表
        if recursive:
            if file_pattern:
                files = path.rglob(file_pattern)
            else:
                files = [f for f in path.rglob("*") if f.is_file()]
        else:
            if file_pattern:
                files = path.glob(file_pattern)
            else:
                files = [f for f in path.glob("*") if f.is_file()]

        # 加载每个文件
        for file_path in files:
            doc = self.load_file(str(file_path))
            if doc:
                documents.append(doc)

        logger.info(f"目录加载完成: {dir_path}")
        logger.info(f"  成功: {len(documents)} 个文件")
        logger.info(f"  失败: {self.error_count} 个文件")

        return documents

    def _load_markdown(self, path: Path) -> Optional[Document]:
        """加载 Markdown 文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # 提取元数据
            metadata = self._extract_markdown_metadata(content, path)

            # 生成文档ID
            doc_id = self._generate_doc_id(str(path))

            return Document(
                content=content,
                metadata=metadata,
                doc_id=doc_id,
                source_file=str(path),
                source_type="markdown"
            )

        except Exception as e:
            logger.error(f"Markdown 加载失败: {path}, 错误: {e}")
            return None

    def _load_pdf(self, path: Path) -> Optional[Document]:
        """
        加载 PDF 文件

        注意：假设 PDF 已经通过 MinerU 解析为 Markdown
        如果是原始 PDF，需要先调用 MinerU 解析
        """
        try:
            # 检查是否有对应的 Markdown 文件（MinerU 输出）
            md_path = path.with_suffix(".md")

            if md_path.exists():
                # 使用已解析的 Markdown
                logger.info(f"使用 MinerU 解析结果: {md_path}")
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                # 原始 PDF，需要解析
                logger.warning(f"PDF 未解析，需要先使用 MinerU: {path}")
                # 这里可以调用 MinerU API 或返回 None
                return None

            # 提取元数据
            metadata = {
                "source_file": str(path),
                "source_type": "pdf",
                "file_name": path.name,
                "file_size": path.stat().st_size,
                "parsed_from_mineru": md_path.exists()
            }

            # 生成文档ID
            doc_id = self._generate_doc_id(str(path))

            return Document(
                content=content,
                metadata=metadata,
                doc_id=doc_id,
                source_file=str(path),
                source_type="pdf"
            )

        except Exception as e:
            logger.error(f"PDF 加载失败: {path}, 错误: {e}")
            return None

    def _load_json(self, path: Path) -> Optional[Document]:
        """加载 JSON 文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 将 JSON 转换为文本
            if isinstance(data, dict):
                # 如果是字典，提取主要内容
                content = self._json_to_text(data)
            elif isinstance(data, list):
                # 如果是列表，合并所有项
                content = "\n\n".join([self._json_to_text(item) for item in data])
            else:
                content = str(data)

            # 提取元数据
            metadata = {
                "source_file": str(path),
                "source_type": "json",
                "file_name": path.name,
                "json_structure": type(data).__name__
            }

            # 生成文档ID
            doc_id = self._generate_doc_id(str(path))

            return Document(
                content=content,
                metadata=metadata,
                doc_id=doc_id,
                source_file=str(path),
                source_type="json"
            )

        except Exception as e:
            logger.error(f"JSON 加载失败: {path}, 错误: {e}")
            return None

    def _load_html(self, path: Path) -> Optional[Document]:
        """加载 HTML 文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # 简单的 HTML 清洗（移除标签）
            content = self._clean_html(html_content)

            # 提取元数据
            metadata = {
                "source_file": str(path),
                "source_type": "html",
                "file_name": path.name,
                "original_html_length": len(html_content)
            }

            # 生成文档ID
            doc_id = self._generate_doc_id(str(path))

            return Document(
                content=content,
                metadata=metadata,
                doc_id=doc_id,
                source_file=str(path),
                source_type="html"
            )

        except Exception as e:
            logger.error(f"HTML 加载失败: {path}, 错误: {e}")
            return None

    def _extract_markdown_metadata(self, content: str, path: Path) -> Dict[str, Any]:
        """从 Markdown 内容中提取元数据"""
        metadata = {
            "source_file": str(path),
            "source_type": "markdown",
            "file_name": path.name,
            "file_size": len(content)
        }

        # 提取标题（第一个 # 标题）
        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("# "):
                metadata["title"] = line.strip()[2:].strip()
                break

        # 识别教材类型
        file_name = path.name
        if "证券投资基金" in file_name:
            metadata["book_title"] = "证券投资基金基础知识"
            metadata["category"] = "textbook"
        elif "金融市场" in file_name:
            metadata["book_title"] = "金融市场基础知识"
            metadata["category"] = "textbook"
        else:
            metadata["category"] = "general"

        # 提取章节信息
        if "第" in file_name and "章" in file_name:
            import re
            chapter_match = re.search(r"第([一二三四五六七八九十\d]+)章", file_name)
            if chapter_match:
                metadata["chapter"] = chapter_match.group(0)

        return metadata

    def _json_to_text(self, data: Any) -> str:
        """将 JSON 数据转换为文本"""
        if isinstance(data, dict):
            parts = []
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    parts.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
                else:
                    parts.append(f"{key}: {value}")
            return "\n".join(parts)
        else:
            return str(data)

    def _clean_html(self, html_content: str) -> str:
        """清洗 HTML 内容"""
        import re

        # 移除 script 和 style 标签
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)

        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', html_content)

        # 清理多余空白
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text

    def _generate_doc_id(self, file_path: str) -> str:
        """生成唯一文档ID"""
        return hashlib.md5(file_path.encode()).hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """获取加载统计"""
        return {
            "loaded_count": self.loaded_count,
            "error_count": self.error_count,
            "error_files": self.error_files,
            "success_rate": self.loaded_count / (self.loaded_count + self.error_count) if (self.loaded_count + self.error_count) > 0 else 0
        }


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    loader = UnifiedDataLoader()

    # 测试加载目录
    data_dir = r"F:\Financial_Asset_QA_System_cyx-master\data\knowledge"
    documents = loader.load_directory(data_dir, recursive=False)

    print(f"\n加载完成:")
    print(f"  成功: {loader.loaded_count} 个文件")
    print(f"  失败: {loader.error_count} 个文件")

    if documents:
        print(f"\n示例文档:")
        doc = documents[0]
        print(f"  ID: {doc.doc_id}")
        print(f"  类型: {doc.source_type}")
        print(f"  文件: {doc.source_file}")
        print(f"  内容长度: {len(doc.content)}")
        print(f"  元数据: {doc.metadata}")
