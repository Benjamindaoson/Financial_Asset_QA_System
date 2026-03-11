"""
文档切分策略 - 针对不同数据源优化切分
Chunk Strategy - Optimize Chunking for Different Data Sources

策略：
1. 教材类：按章节切分（保留层级结构）
2. 财报类：按表格/段落切分
3. 习题类：按题目切分
4. 通用类：按语义切分
"""
import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkType(Enum):
    """切分类型"""
    TEXTBOOK = "textbook"  # 教材
    REPORT = "report"      # 财报
    EXERCISE = "exercise"  # 习题
    GENERAL = "general"    # 通用


@dataclass
class Chunk:
    """文档块"""
    content: str
    metadata: Dict
    chunk_id: str
    chunk_index: int
    chunk_type: str
    parent_doc_id: str


@dataclass
class ChunkConfig:
    """切分配置"""
    chunk_size: int
    overlap: int
    split_by: str  # "section", "paragraph", "question", "semantic"
    preserve_structure: bool = True


class ChunkStrategy:
    """
    文档切分策略

    根据文档类型选择最优切分策略
    """

    # 预定义配置
    CONFIGS = {
        ChunkType.TEXTBOOK: ChunkConfig(
            chunk_size=800,
            overlap=150,
            split_by="section",
            preserve_structure=True
        ),
        ChunkType.REPORT: ChunkConfig(
            chunk_size=600,
            overlap=100,
            split_by="paragraph",
            preserve_structure=False
        ),
        ChunkType.EXERCISE: ChunkConfig(
            chunk_size=400,
            overlap=50,
            split_by="question",
            preserve_structure=True
        ),
        ChunkType.GENERAL: ChunkConfig(
            chunk_size=600,
            overlap=120,
            split_by="semantic",
            preserve_structure=False
        )
    }

    def __init__(self):
        """初始化切分策略"""
        self.chunk_count = 0

    def chunk_document(
        self,
        content: str,
        metadata: Dict,
        doc_id: str,
        chunk_type: Optional[ChunkType] = None,
        custom_config: Optional[ChunkConfig] = None
    ) -> List[Chunk]:
        """
        切分文档

        Args:
            content: 文档内容
            metadata: 元数据
            doc_id: 文档ID
            chunk_type: 切分类型（自动检测或手动指定）
            custom_config: 自定义配置

        Returns:
            切分后的块列表
        """
        # 自动检测类型
        if chunk_type is None:
            chunk_type = self._detect_chunk_type(content, metadata)

        # 获取配置
        config = custom_config or self.CONFIGS[chunk_type]

        logger.info(f"切分文档: {doc_id}, 类型: {chunk_type.value}, 配置: {config}")

        # 根据类型选择切分方法
        if chunk_type == ChunkType.TEXTBOOK:
            chunks = self._chunk_by_section(content, metadata, doc_id, config)
        elif chunk_type == ChunkType.REPORT:
            chunks = self._chunk_by_paragraph(content, metadata, doc_id, config)
        elif chunk_type == ChunkType.EXERCISE:
            chunks = self._chunk_by_question(content, metadata, doc_id, config)
        else:
            chunks = self._chunk_by_semantic(content, metadata, doc_id, config)

        self.chunk_count += len(chunks)
        logger.info(f"切分完成: {len(chunks)} 个块")

        return chunks

    def _detect_chunk_type(self, content: str, metadata: Dict) -> ChunkType:
        """自动检测文档类型"""
        # 从元数据检测
        category = metadata.get("category", "")
        if category == "textbook":
            return ChunkType.TEXTBOOK

        # 从文件名检测
        source_file = metadata.get("source_file", "")
        if "教材" in source_file or "基础知识" in source_file:
            return ChunkType.TEXTBOOK
        elif "报告" in source_file or "财报" in source_file:
            return ChunkType.REPORT
        elif "习题" in source_file or "练习" in source_file:
            return ChunkType.EXERCISE

        # 从内容检测
        if re.search(r"第[一二三四五六七八九十\d]+章", content):
            return ChunkType.TEXTBOOK
        elif re.search(r"[【\[]题目[\]】]|^\d+[.、]", content, re.MULTILINE):
            return ChunkType.EXERCISE

        return ChunkType.GENERAL

    def _chunk_by_section(
        self,
        content: str,
        metadata: Dict,
        doc_id: str,
        config: ChunkConfig
    ) -> List[Chunk]:
        """按章节切分（教材类）"""
        chunks = []

        # 识别章节结构
        sections = self._extract_sections(content)

        if not sections:
            # 没有明确章节，降级为段落切分
            logger.warning("未找到章节结构，降级为段落切分")
            return self._chunk_by_paragraph(content, metadata, doc_id, config)

        for idx, section in enumerate(sections):
            section_title = section["title"]
            section_content = section["content"]
            section_level = section["level"]

            # 如果章节内容过长，进一步切分
            if len(section_content) > config.chunk_size:
                sub_chunks = self._split_long_text(
                    section_content,
                    config.chunk_size,
                    config.overlap
                )

                for sub_idx, sub_content in enumerate(sub_chunks):
                    chunk = self._create_chunk(
                        content=sub_content,
                        metadata={
                            **metadata,
                            "section_title": section_title,
                            "section_level": section_level,
                            "sub_chunk_index": sub_idx,
                            "chunk_type": "section"
                        },
                        doc_id=doc_id,
                        chunk_index=len(chunks)
                    )
                    chunks.append(chunk)
            else:
                chunk = self._create_chunk(
                    content=section_content,
                    metadata={
                        **metadata,
                        "section_title": section_title,
                        "section_level": section_level,
                        "chunk_type": "section"
                    },
                    doc_id=doc_id,
                    chunk_index=len(chunks)
                )
                chunks.append(chunk)

        return chunks

    def _chunk_by_paragraph(
        self,
        content: str,
        metadata: Dict,
        doc_id: str,
        config: ChunkConfig
    ) -> List[Chunk]:
        """按段落切分（财报类）"""
        chunks = []

        # 按段落分割
        paragraphs = content.split("\n\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        current_chunk = ""
        for para in paragraphs:
            # 检查是否是表格
            is_table = self._is_table(para)

            if is_table:
                # 表格单独成块
                if current_chunk:
                    chunk = self._create_chunk(
                        content=current_chunk,
                        metadata={**metadata, "chunk_type": "paragraph"},
                        doc_id=doc_id,
                        chunk_index=len(chunks)
                    )
                    chunks.append(chunk)
                    current_chunk = ""

                chunk = self._create_chunk(
                    content=para,
                    metadata={**metadata, "chunk_type": "table"},
                    doc_id=doc_id,
                    chunk_index=len(chunks)
                )
                chunks.append(chunk)
            else:
                # 累积段落
                if len(current_chunk) + len(para) > config.chunk_size:
                    if current_chunk:
                        chunk = self._create_chunk(
                            content=current_chunk,
                            metadata={**metadata, "chunk_type": "paragraph"},
                            doc_id=doc_id,
                            chunk_index=len(chunks)
                        )
                        chunks.append(chunk)
                    current_chunk = para
                else:
                    current_chunk += "\n\n" + para if current_chunk else para

        # 处理剩余内容
        if current_chunk:
            chunk = self._create_chunk(
                content=current_chunk,
                metadata={**metadata, "chunk_type": "paragraph"},
                doc_id=doc_id,
                chunk_index=len(chunks)
            )
            chunks.append(chunk)

        return chunks

    def _chunk_by_question(
        self,
        content: str,
        metadata: Dict,
        doc_id: str,
        config: ChunkConfig
    ) -> List[Chunk]:
        """按题目切分（习题类）"""
        chunks = []

        # 识别题目边界
        questions = self._extract_questions(content)

        if not questions:
            # 没有明确题目，降级为段落切分
            logger.warning("未找到题目结构，降级为段落切分")
            return self._chunk_by_paragraph(content, metadata, doc_id, config)

        for idx, question in enumerate(questions):
            chunk = self._create_chunk(
                content=question["content"],
                metadata={
                    **metadata,
                    "question_number": question.get("number"),
                    "question_type": question.get("type"),
                    "chunk_type": "question"
                },
                doc_id=doc_id,
                chunk_index=idx
            )
            chunks.append(chunk)

        return chunks

    def _chunk_by_semantic(
        self,
        content: str,
        metadata: Dict,
        doc_id: str,
        config: ChunkConfig
    ) -> List[Chunk]:
        """按语义切分（通用类）"""
        chunks = []

        # 简单的滑动窗口切分
        text_chunks = self._split_long_text(
            content,
            config.chunk_size,
            config.overlap
        )

        for idx, chunk_content in enumerate(text_chunks):
            chunk = self._create_chunk(
                content=chunk_content,
                metadata={**metadata, "chunk_type": "semantic"},
                doc_id=doc_id,
                chunk_index=idx
            )
            chunks.append(chunk)

        return chunks

    def _extract_sections(self, content: str) -> List[Dict]:
        """提取章节结构"""
        sections = []
        lines = content.split("\n")

        current_section = None
        current_content = []

        for line in lines:
            # 检查是否是标题
            if line.strip().startswith("#"):
                # 保存上一个章节
                if current_section:
                    current_section["content"] = "\n".join(current_content).strip()
                    sections.append(current_section)

                # 开始新章节
                level = len(re.match(r'^#+', line.strip()).group())
                title = line.strip().lstrip("#").strip()

                current_section = {
                    "title": title,
                    "level": level,
                    "content": ""
                }
                current_content = []
            else:
                if current_section:
                    current_content.append(line)

        # 保存最后一个章节
        if current_section:
            current_section["content"] = "\n".join(current_content).strip()
            sections.append(current_section)

        return sections

    def _extract_questions(self, content: str) -> List[Dict]:
        """提取题目"""
        questions = []

        # 匹配题目模式
        # 1. 数字编号：1. 2. 3.
        # 2. 括号编号：(1) (2) (3)
        # 3. 题目标记：【题目】
        pattern = r'(?:^|\n)(?:(\d+)[.、]|（(\d+)）|【题目】)\s*(.+?)(?=(?:\n(?:\d+[.、]|（\d+）|【题目】)|\Z))'

        matches = re.finditer(pattern, content, re.DOTALL)

        for match in matches:
            number = match.group(1) or match.group(2)
            question_content = match.group(3).strip()

            # 检测题目类型
            question_type = "unknown"
            if "选择" in question_content[:20]:
                question_type = "choice"
            elif "判断" in question_content[:20]:
                question_type = "judgment"
            elif "简答" in question_content[:20] or "论述" in question_content[:20]:
                question_type = "essay"

            questions.append({
                "number": number,
                "content": question_content,
                "type": question_type
            })

        return questions

    def _is_table(self, text: str) -> bool:
        """判断是否是表格"""
        # Markdown 表格特征
        lines = text.split("\n")
        if len(lines) < 2:
            return False

        # 检查是否有表格分隔符
        has_separator = any(re.match(r'^\|?[\s\-:]+\|', line) for line in lines)

        # 检查是否有多个 | 符号
        has_pipes = sum(1 for line in lines if line.count("|") >= 2) >= 2

        return has_separator or has_pipes

    def _split_long_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """滑动窗口切分长文本"""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # 尝试在句子边界切分
            if end < len(text):
                # 查找最近的句号、问号、感叹号
                for sep in ["。", "！", "？", "\n\n", "\n"]:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep != -1:
                        end = last_sep + 1
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # 移动窗口（考虑重叠）
            start = end - overlap if end < len(text) else end

        return chunks

    def _create_chunk(
        self,
        content: str,
        metadata: Dict,
        doc_id: str,
        chunk_index: int
    ) -> Chunk:
        """创建文档块"""
        chunk_id = f"{doc_id}_chunk_{chunk_index}"

        return Chunk(
            content=content,
            metadata=metadata,
            chunk_id=chunk_id,
            chunk_index=chunk_index,
            chunk_type=metadata.get("chunk_type", "unknown"),
            parent_doc_id=doc_id
        )

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_chunks": self.chunk_count
        }


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    # 测试教材切分
    textbook_content = """
# 第一章 金融市场概述

## 第一节 金融市场的定义

金融市场是指资金供求双方运用各种金融工具进行资金融通的场所。

## 第二节 金融市场的功能

金融市场具有以下功能：
1. 资金融通功能
2. 价格发现功能
3. 风险管理功能
"""

    strategy = ChunkStrategy()

    chunks = strategy.chunk_document(
        content=textbook_content,
        metadata={"category": "textbook"},
        doc_id="test_001"
    )

    print(f"\n切分结果: {len(chunks)} 个块")
    for i, chunk in enumerate(chunks):
        print(f"\n块 {i+1}:")
        print(f"  ID: {chunk.chunk_id}")
        print(f"  类型: {chunk.chunk_type}")
        print(f"  章节: {chunk.metadata.get('section_title', 'N/A')}")
        print(f"  内容长度: {len(chunk.content)}")
        print(f"  内容预览: {chunk.content[:100]}...")
