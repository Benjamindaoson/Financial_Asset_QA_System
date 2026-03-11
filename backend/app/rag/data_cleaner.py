"""
数据清洗器 - 清洗和标准化文档内容
Data Cleaner - Clean and Standardize Document Content

功能：
1. 去除版权信息、页眉页脚
2. 合并重复的标题
3. 标准化章节结构
4. 清理特殊字符
5. 去重处理
"""
import logging
import re
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CleanedDocument:
    """清洗后的文档"""
    content: str
    metadata: Dict
    doc_id: str
    source_file: str
    source_type: str
    cleaning_applied: List[str]  # 应用的清洗操作


class DataCleaner:
    """
    数据清洗器

    清洗策略：
    1. 移除常见的版权信息
    2. 清理 MinerU 解析的特殊符号
    3. 标准化章节标题
    4. 去除重复内容
    5. 清理多余空白
    """

    # 版权信息关键词
    COPYRIGHT_KEYWORDS = [
        "版权所有",
        "Copyright",
        "All Rights Reserved",
        "保留所有权利",
        "未经许可不得转载",
        "本资料仅供",
        "内部资料"
    ]

    # 页眉页脚模式
    HEADER_FOOTER_PATTERNS = [
        r"第\s*\d+\s*页",
        r"Page\s+\d+",
        r"共\s*\d+\s*页",
        r"\d+\s*/\s*\d+",
    ]

    # MinerU 特殊符号
    MINERU_ARTIFACTS = [
        "<!-- pagebreak -->",
        "<!-- image -->",
        "<!-- table -->",
        "[图片]",
        "[表格]"
    ]

    def __init__(self):
        """初始化清洗器"""
        self.cleaned_count = 0
        self.duplicate_count = 0
        self.seen_hashes: Set[str] = set()

    def clean_document(
        self,
        content: str,
        metadata: Dict,
        doc_id: str,
        source_file: str,
        source_type: str,
        remove_copyright: bool = True,
        remove_headers: bool = True,
        clean_mineru: bool = True,
        normalize_structure: bool = True
    ) -> CleanedDocument:
        """
        清洗单个文档

        Args:
            content: 原始内容
            metadata: 元数据
            doc_id: 文档ID
            source_file: 源文件
            source_type: 源类型
            remove_copyright: 是否移除版权信息
            remove_headers: 是否移除页眉页脚
            clean_mineru: 是否清理 MinerU 符号
            normalize_structure: 是否标准化结构

        Returns:
            清洗后的文档
        """
        cleaned_content = content
        cleaning_applied = []

        # 1. 移除版权信息
        if remove_copyright:
            cleaned_content = self._remove_copyright(cleaned_content)
            cleaning_applied.append("remove_copyright")

        # 2. 移除页眉页脚
        if remove_headers:
            cleaned_content = self._remove_headers_footers(cleaned_content)
            cleaning_applied.append("remove_headers")

        # 3. 清理 MinerU 符号
        if clean_mineru and source_type in ["pdf", "html"]:
            cleaned_content = self._clean_mineru_artifacts(cleaned_content)
            cleaning_applied.append("clean_mineru")

        # 4. 标准化章节结构
        if normalize_structure:
            cleaned_content = self._normalize_structure(cleaned_content)
            cleaning_applied.append("normalize_structure")

        # 5. 清理多余空白
        cleaned_content = self._clean_whitespace(cleaned_content)
        cleaning_applied.append("clean_whitespace")

        # 6. 清理特殊字符
        cleaned_content = self._clean_special_chars(cleaned_content)
        cleaning_applied.append("clean_special_chars")

        self.cleaned_count += 1

        return CleanedDocument(
            content=cleaned_content,
            metadata=metadata,
            doc_id=doc_id,
            source_file=source_file,
            source_type=source_type,
            cleaning_applied=cleaning_applied
        )

    def deduplicate_documents(
        self,
        documents: List[CleanedDocument],
        similarity_threshold: float = 0.95
    ) -> List[CleanedDocument]:
        """
        去重文档

        Args:
            documents: 文档列表
            similarity_threshold: 相似度阈值（基于内容哈希）

        Returns:
            去重后的文档列表
        """
        unique_docs = []
        seen_hashes = set()

        for doc in documents:
            # 计算内容哈希
            content_hash = self._compute_content_hash(doc.content)

            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_docs.append(doc)
            else:
                self.duplicate_count += 1
                logger.info(f"发现重复文档: {doc.source_file}")

        logger.info(f"去重完成: 原始 {len(documents)} 个 -> 唯一 {len(unique_docs)} 个")
        logger.info(f"移除重复: {self.duplicate_count} 个")

        return unique_docs

    def _remove_copyright(self, content: str) -> str:
        """移除版权信息"""
        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            # 检查是否包含版权关键词
            has_copyright = any(kw in line for kw in self.COPYRIGHT_KEYWORDS)

            if not has_copyright:
                cleaned_lines.append(line)
            else:
                logger.debug(f"移除版权行: {line[:50]}...")

        return "\n".join(cleaned_lines)

    def _remove_headers_footers(self, content: str) -> str:
        """移除页眉页脚"""
        for pattern in self.HEADER_FOOTER_PATTERNS:
            content = re.sub(pattern, "", content)

        return content

    def _clean_mineru_artifacts(self, content: str) -> str:
        """清理 MinerU 解析的特殊符号"""
        for artifact in self.MINERU_ARTIFACTS:
            content = content.replace(artifact, "")

        # 清理多余的分隔符
        content = re.sub(r'-{3,}', '', content)
        content = re.sub(r'={3,}', '', content)

        return content

    def _normalize_structure(self, content: str) -> str:
        """标准化章节结构"""
        lines = content.split("\n")
        normalized_lines = []
        prev_line = ""

        for line in lines:
            stripped = line.strip()

            # 合并重复的标题
            if stripped.startswith("#") and stripped == prev_line:
                logger.debug(f"跳过重复标题: {stripped}")
                continue

            # 标准化章节标题格式
            if re.match(r"^第[一二三四五六七八九十\d]+章", stripped):
                # 确保章节标题是 ## 级别
                if not stripped.startswith("#"):
                    stripped = "## " + stripped
                elif stripped.startswith("# ") and not stripped.startswith("## "):
                    stripped = "#" + stripped

            normalized_lines.append(line)
            prev_line = stripped

        return "\n".join(normalized_lines)

    def _clean_whitespace(self, content: str) -> str:
        """清理多余空白"""
        # 移除行尾空白
        lines = [line.rstrip() for line in content.split("\n")]

        # 移除连续的空行（保留最多2个）
        cleaned_lines = []
        empty_count = 0

        for line in lines:
            if line.strip() == "":
                empty_count += 1
                if empty_count <= 2:
                    cleaned_lines.append(line)
            else:
                empty_count = 0
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _clean_special_chars(self, content: str) -> str:
        """清理特殊字符"""
        # 移除零宽字符
        content = re.sub(r'[\u200b-\u200f\ufeff]', '', content)

        # 标准化引号
        content = content.replace('"', '"').replace('"', '"')
        content = content.replace(''', "'").replace(''', "'")

        # 标准化破折号
        content = content.replace('—', '-').replace('–', '-')

        return content

    def _compute_content_hash(self, content: str) -> str:
        """计算内容哈希（用于去重）"""
        # 标准化后计算哈希
        normalized = content.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        return hashlib.md5(normalized.encode()).hexdigest()

    def clean_batch(
        self,
        documents: List[Dict],
        deduplicate: bool = True
    ) -> List[CleanedDocument]:
        """
        批量清洗文档

        Args:
            documents: 文档列表（来自 UnifiedDataLoader）
            deduplicate: 是否去重

        Returns:
            清洗后的文档列表
        """
        cleaned_docs = []

        for doc in documents:
            cleaned = self.clean_document(
                content=doc.content,
                metadata=doc.metadata,
                doc_id=doc.doc_id,
                source_file=doc.source_file,
                source_type=doc.source_type
            )
            cleaned_docs.append(cleaned)

        # 去重
        if deduplicate:
            cleaned_docs = self.deduplicate_documents(cleaned_docs)

        logger.info(f"批量清洗完成: {len(cleaned_docs)} 个文档")

        return cleaned_docs

    def get_stats(self) -> Dict:
        """获取清洗统计"""
        return {
            "cleaned_count": self.cleaned_count,
            "duplicate_count": self.duplicate_count,
            "unique_count": self.cleaned_count - self.duplicate_count
        }


class AdvancedCleaner(DataCleaner):
    """
    高级清洗器

    额外功能：
    1. 表格格式标准化
    2. 公式格式标准化
    3. 列表格式标准化
    """

    def clean_document(self, *args, **kwargs) -> CleanedDocument:
        """扩展清洗功能"""
        doc = super().clean_document(*args, **kwargs)

        # 额外清洗
        doc.content = self._normalize_tables(doc.content)
        doc.content = self._normalize_formulas(doc.content)
        doc.content = self._normalize_lists(doc.content)

        doc.cleaning_applied.extend([
            "normalize_tables",
            "normalize_formulas",
            "normalize_lists"
        ])

        return doc

    def _normalize_tables(self, content: str) -> str:
        """标准化表格格式"""
        # 确保表格前后有空行
        content = re.sub(r'([^\n])\n(\|)', r'\1\n\n\2', content)
        content = re.sub(r'(\|[^\n]+)\n([^\n|])', r'\1\n\n\2', content)

        return content

    def _normalize_formulas(self, content: str) -> str:
        """标准化公式格式"""
        # 确保 LaTeX 公式格式正确
        content = re.sub(r'\$\$([^\$]+)\$\$', r'\n$$\1$$\n', content)

        return content

    def _normalize_lists(self, content: str) -> str:
        """标准化列表格式"""
        lines = content.split("\n")
        normalized = []

        for line in lines:
            stripped = line.strip()

            # 标准化无序列表
            if re.match(r'^[•·\*]\s+', stripped):
                stripped = re.sub(r'^[•·\*]\s+', '- ', stripped)

            # 标准化有序列表
            if re.match(r'^\d+[.、]\s+', stripped):
                stripped = re.sub(r'^(\d+)[.、]\s+', r'\1. ', stripped)

            normalized.append(stripped if stripped else line)

        return "\n".join(normalized)


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    # 测试文本
    test_content = """
# 第一章 金融市场概述

版权所有 © 2024 某某出版社
未经许可不得转载

## 第一节 金融市场的定义

金融市场是指资金供求双方运用各种金融工具进行资金融通的场所。

第 1 页 / 共 100 页

## 第一节 金融市场的定义

金融市场具有以下功能：
• 资金融通
• 价格发现
• 风险管理

<!-- pagebreak -->

市盈率（P/E）= 股价 / 每股收益
    """

    cleaner = AdvancedCleaner()

    cleaned = cleaner.clean_document(
        content=test_content,
        metadata={},
        doc_id="test_001",
        source_file="test.md",
        source_type="markdown"
    )

    print("清洗前长度:", len(test_content))
    print("清洗后长度:", len(cleaned.content))
    print("\n应用的清洗操作:", cleaned.cleaning_applied)
    print("\n清洗后内容:")
    print(cleaned.content)
