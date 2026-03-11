"""
元数据提取器 - 为每个 chunk 添加丰富的元数据
Metadata Extractor - Add Rich Metadata to Each Chunk

元数据字段：
- source_file: 源文件路径
- source_type: 文件类型
- book_title: 书名
- chapter: 章节
- section: 小节
- page_number: 页码
- difficulty: 难度级别
- tags: 标签列表
- created_at: 创建时间
- chunk_type: 块类型
"""
import logging
import re
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class EnhancedMetadata:
    """增强的元数据"""
    # 基础信息
    source_file: str
    source_type: str
    chunk_id: str
    chunk_index: int
    chunk_type: str

    # 文档信息
    book_title: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    page_number: Optional[int] = None

    # 内容特征
    difficulty: str = "unknown"  # basic, intermediate, advanced
    tags: List[str] = None
    keywords: List[str] = None

    # 时间信息
    created_at: str = None

    # 额外信息
    content_length: int = 0
    has_formula: bool = False
    has_table: bool = False
    has_code: bool = False

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.keywords is None:
            self.keywords = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class MetadataExtractor:
    """
    元数据提取器

    功能：
    1. 从文件名提取书名、章节信息
    2. 从内容提取关键词、标签
    3. 判断难度级别
    4. 检测特殊内容（公式、表格、代码）
    """

    # 金融关键词库
    FINANCE_KEYWORDS = {
        "basic": [
            "金融市场", "证券", "股票", "债券", "基金", "市盈率", "市净率",
            "资产", "负债", "权益", "收益", "风险", "投资", "融资"
        ],
        "intermediate": [
            "资本资产定价模型", "有效市场假说", "套利定价理论", "期权定价",
            "久期", "凸性", "贝塔系数", "夏普比率", "詹森指数"
        ],
        "advanced": [
            "随机过程", "布朗运动", "伊藤引理", "Black-Scholes", "VaR",
            "蒙特卡洛模拟", "GARCH模型", "协整", "因子模型"
        ]
    }

    # 章节模式
    CHAPTER_PATTERNS = [
        r"第([一二三四五六七八九十\d]+)章",
        r"Chapter\s+(\d+)",
        r"第(\d+)章"
    ]

    # 小节模式
    SECTION_PATTERNS = [
        r"第([一二三四五六七八九十\d]+)节",
        r"Section\s+(\d+)",
        r"(\d+\.\d+)"
    ]

    def __init__(self):
        """初始化提取器"""
        self.extracted_count = 0

    def extract_metadata(
        self,
        chunk_content: str,
        chunk_id: str,
        chunk_index: int,
        chunk_type: str,
        source_file: str,
        source_type: str,
        base_metadata: Optional[Dict] = None
    ) -> EnhancedMetadata:
        """
        提取元数据

        Args:
            chunk_content: 块内容
            chunk_id: 块ID
            chunk_index: 块索引
            chunk_type: 块类型
            source_file: 源文件
            source_type: 源类型
            base_metadata: 基础元数据（来自文档级别）

        Returns:
            增强的元数据
        """
        base_metadata = base_metadata or {}

        # 提取书名
        book_title = self._extract_book_title(source_file, base_metadata)

        # 提取章节信息
        chapter = self._extract_chapter(chunk_content, source_file, base_metadata)
        section = self._extract_section(chunk_content, base_metadata)

        # 提取页码
        page_number = self._extract_page_number(chunk_content, base_metadata)

        # 判断难度
        difficulty = self._determine_difficulty(chunk_content)

        # 提取标签
        tags = self._extract_tags(chunk_content, book_title, chapter)

        # 提取关键词
        keywords = self._extract_keywords(chunk_content)

        # 检测特殊内容
        has_formula = self._has_formula(chunk_content)
        has_table = self._has_table(chunk_content)
        has_code = self._has_code(chunk_content)

        metadata = EnhancedMetadata(
            source_file=source_file,
            source_type=source_type,
            chunk_id=chunk_id,
            chunk_index=chunk_index,
            chunk_type=chunk_type,
            book_title=book_title,
            chapter=chapter,
            section=section,
            page_number=page_number,
            difficulty=difficulty,
            tags=tags,
            keywords=keywords,
            content_length=len(chunk_content),
            has_formula=has_formula,
            has_table=has_table,
            has_code=has_code
        )

        self.extracted_count += 1

        return metadata

    def _extract_book_title(self, source_file: str, base_metadata: Dict) -> Optional[str]:
        """提取书名"""
        # 优先从 base_metadata 获取
        if "book_title" in base_metadata:
            return base_metadata["book_title"]

        # 从文件名提取
        if "证券投资基金" in source_file:
            return "证券投资基金基础知识"
        elif "金融市场" in source_file:
            return "金融市场基础知识"
        elif "财务报表" in source_file or "财报" in source_file:
            return "财务报表分析"

        return None

    def _extract_chapter(
        self,
        content: str,
        source_file: str,
        base_metadata: Dict
    ) -> Optional[str]:
        """提取章节"""
        # 优先从 base_metadata 获取
        if "chapter" in base_metadata:
            return base_metadata["chapter"]

        # 从内容提取
        for pattern in self.CHAPTER_PATTERNS:
            match = re.search(pattern, content)
            if match:
                return match.group(0)

        # 从文件名提取
        for pattern in self.CHAPTER_PATTERNS:
            match = re.search(pattern, source_file)
            if match:
                return match.group(0)

        return None

    def _extract_section(self, content: str, base_metadata: Dict) -> Optional[str]:
        """提取小节"""
        # 优先从 base_metadata 获取
        if "section" in base_metadata:
            return base_metadata["section"]

        # 从内容提取
        for pattern in self.SECTION_PATTERNS:
            match = re.search(pattern, content)
            if match:
                return match.group(0)

        return None

    def _extract_page_number(self, content: str, base_metadata: Dict) -> Optional[int]:
        """提取页码"""
        # 优先从 base_metadata 获取
        if "page_number" in base_metadata:
            return base_metadata["page_number"]

        # 从内容提取（页眉页脚）
        patterns = [
            r"第\s*(\d+)\s*页",
            r"Page\s+(\d+)",
            r"- (\d+) -"
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass

        return None

    def _determine_difficulty(self, content: str) -> str:
        """判断难度级别"""
        content_lower = content.lower()

        # 统计各级别关键词出现次数
        basic_count = sum(1 for kw in self.FINANCE_KEYWORDS["basic"] if kw in content)
        intermediate_count = sum(1 for kw in self.FINANCE_KEYWORDS["intermediate"] if kw in content)
        advanced_count = sum(1 for kw in self.FINANCE_KEYWORDS["advanced"] if kw in content)

        # 判断难度
        if advanced_count >= 2:
            return "advanced"
        elif intermediate_count >= 2:
            return "intermediate"
        elif basic_count >= 2:
            return "basic"

        # 根据内容特征判断
        if re.search(r"定义|概念|什么是", content):
            return "basic"
        elif re.search(r"模型|理论|公式|计算", content):
            return "intermediate"
        elif re.search(r"推导|证明|高级|复杂", content):
            return "advanced"

        return "basic"  # 默认基础

    def _extract_tags(
        self,
        content: str,
        book_title: Optional[str],
        chapter: Optional[str]
    ) -> List[str]:
        """提取标签"""
        tags = []

        # 添加书名标签
        if book_title:
            tags.append(book_title)

        # 添加章节标签
        if chapter:
            tags.append(chapter)

        # 添加主题标签
        topic_keywords = {
            "金融市场": ["金融市场", "市场体系", "市场功能"],
            "证券": ["股票", "债券", "证券"],
            "基金": ["基金", "投资基金", "基金管理"],
            "财务分析": ["财务报表", "财务分析", "财务指标"],
            "风险管理": ["风险", "风险管理", "风险控制"],
            "投资": ["投资", "投资策略", "投资组合"]
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in content for kw in keywords):
                tags.append(topic)

        return list(set(tags))  # 去重

    def _extract_keywords(self, content: str, top_k: int = 5) -> List[str]:
        """提取关键词"""
        keywords = []

        # 提取所有金融关键词
        all_keywords = []
        for level_keywords in self.FINANCE_KEYWORDS.values():
            all_keywords.extend(level_keywords)

        # 统计关键词频率
        keyword_freq = {}
        for kw in all_keywords:
            count = content.count(kw)
            if count > 0:
                keyword_freq[kw] = count

        # 按频率排序，取 top_k
        sorted_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [kw for kw, _ in sorted_keywords[:top_k]]

        return keywords

    def _has_formula(self, content: str) -> bool:
        """检测是否包含公式"""
        # LaTeX 公式
        if re.search(r'\$\$.*?\$\$|\$.*?\$', content):
            return True

        # 数学符号
        math_symbols = ["=", "≈", "≠", "≤", "≥", "∑", "∫", "√", "×", "÷"]
        symbol_count = sum(1 for sym in math_symbols if sym in content)

        return symbol_count >= 3

    def _has_table(self, content: str) -> bool:
        """检测是否包含表格"""
        # Markdown 表格
        lines = content.split("\n")

        # 检查表格分隔符
        has_separator = any(re.match(r'^\|?[\s\-:]+\|', line) for line in lines)

        # 检查多个 | 符号
        pipe_lines = sum(1 for line in lines if line.count("|") >= 2)

        return has_separator or pipe_lines >= 2

    def _has_code(self, content: str) -> bool:
        """检测是否包含代码"""
        # 代码块
        if re.search(r'```.*?```', content, re.DOTALL):
            return True

        # 行内代码
        if re.search(r'`[^`]+`', content):
            return True

        return False

    def batch_extract(
        self,
        chunks: List[Dict],
        source_file: str,
        source_type: str,
        base_metadata: Optional[Dict] = None
    ) -> List[EnhancedMetadata]:
        """
        批量提取元数据

        Args:
            chunks: 块列表
            source_file: 源文件
            source_type: 源类型
            base_metadata: 基础元数据

        Returns:
            元数据列表
        """
        metadata_list = []

        for chunk in chunks:
            metadata = self.extract_metadata(
                chunk_content=chunk.content,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                source_file=source_file,
                source_type=source_type,
                base_metadata={**base_metadata, **chunk.metadata} if base_metadata else chunk.metadata
            )
            metadata_list.append(metadata)

        logger.info(f"批量提取完成: {len(metadata_list)} 个元数据")

        return metadata_list

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "extracted_count": self.extracted_count
        }


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    # 测试内容
    test_content = """
# 第一章 金融市场概述

## 第一节 金融市场的定义

金融市场是指资金供求双方运用各种金融工具进行资金融通的场所。

市盈率（P/E）= 股价 / 每股收益

| 指标 | 公式 | 说明 |
|------|------|------|
| ROE | 净利润/净资产 | 净资产收益率 |
| ROA | 净利润/总资产 | 总资产收益率 |
"""

    extractor = MetadataExtractor()

    metadata = extractor.extract_metadata(
        chunk_content=test_content,
        chunk_id="test_001_chunk_0",
        chunk_index=0,
        chunk_type="section",
        source_file="教材_金融市场基础知识_第一章.md",
        source_type="markdown"
    )

    print("\n提取的元数据:")
    for key, value in asdict(metadata).items():
        print(f"  {key}: {value}")
