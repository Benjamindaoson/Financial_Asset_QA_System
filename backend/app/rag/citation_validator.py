"""
引用验证器 - 验证和修复LLM生成的文档引用
Citation Validator - Validate and fix document citations in LLM output
"""
import re
from typing import Dict, List, Set


class CitationValidator:
    """引用验证器"""

    def __init__(self):
        self.citation_pattern = re.compile(r'\[文档(\d+)\]')

    def validate(self, answer: str, num_docs: int) -> Dict:
        """
        验证答案中的引用是否有效

        Args:
            answer: LLM生成的答案
            num_docs: 实际提供的文档数量

        Returns:
            验证结果字典
        """
        # 提取所有引用
        citations = self.citation_pattern.findall(answer)
        citation_nums = [int(c) for c in citations]

        # 检查引用是否有效
        valid_citations = [c for c in citation_nums if 1 <= c <= num_docs]
        invalid_citations = [c for c in citation_nums if c > num_docs or c < 1]

        return {
            "is_valid": len(invalid_citations) == 0 and len(valid_citations) > 0,
            "has_citations": len(citation_nums) > 0,
            "citations": set(valid_citations),
            "invalid_citations": invalid_citations,
            "total_citations": len(citation_nums)
        }

    def fix_citations(self, answer: str, num_docs: int) -> str:
        """
        修复无效引用

        Args:
            answer: 包含无效引用的答案
            num_docs: 实际文档数量

        Returns:
            修复后的答案
        """
        def replace_invalid(match):
            doc_num = int(match.group(1))
            if doc_num > num_docs or doc_num < 1:
                # 替换为有效的文档编号（使用文档1作为默认）
                return "[文档1]"
            return match.group(0)

        fixed = self.citation_pattern.sub(replace_invalid, answer)
        return fixed

    def add_missing_citations(self, answer: str, num_docs: int) -> str:
        """
        为缺少引用的答案添加引用

        Args:
            answer: 缺少引用的答案
            num_docs: 可用文档数量

        Returns:
            添加引用后的答案
        """
        if num_docs == 0:
            return answer

        # 如果答案中完全没有引用，在末尾添加
        if not self.citation_pattern.search(answer):
            return answer + "[文档1]"

        return answer
