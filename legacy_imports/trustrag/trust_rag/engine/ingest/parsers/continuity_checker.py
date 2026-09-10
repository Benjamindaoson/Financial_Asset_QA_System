"""
ContinuityChecker - 连续性检查和修复系统

解决VLM上下文窗口溢出导致的截断问题：
1. 检测JSON/Markdown语法完整性
2. 实现重叠扫描策略
3. 自动触发LLM缝合机制
4. 支持多页面的连续性修复

核心算法：当检测到不完整输出时，使用页边界重叠识别进行修复
"""
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import difflib

logger = logging.getLogger(__name__)


class ContinuityIssue(Enum):
    """连续性问题类型"""
    INCOMPLETE_JSON = "incomplete_json"
    INCOMPLETE_MARKDOWN_TABLE = "incomplete_markdown_table"
    INCOMPLETE_LIST = "incomplete_list"
    INCOMPLETE_CODE_BLOCK = "incomplete_code_block"
    TRUNCATED_SENTENCE = "truncated_sentence"
    MISSING_CLOSING_BRACKET = "missing_closing_bracket"


@dataclass
class ContinuityProblem:
    """连续性问题描述"""
    issue_type: ContinuityIssue
    location: Tuple[int, int]  # (start_pos, end_pos)
    severity: float  # 0.0-1.0
    context: str
    suggested_fix: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type.value,
            "location": self.location,
            "severity": self.severity,
            "context": self.context[:100],  # 截断上下文
            "suggested_fix": self.suggested_fix
        }


@dataclass
class OverlapRegion:
    """重叠区域定义"""
    page_a_end: int  # 页面A的结束位置
    page_b_start: int  # 页面B的开始位置
    overlap_content: str  # 重叠的内容
    confidence: float  # 匹配置信度


class ContinuityChecker:
    """
    连续性检查器

    检测和修复VLM输出中的截断和不连续问题
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # 配置参数
        self.overlap_window_size = self.config.get('overlap_window_size', 200)  # 重叠窗口大小
        self.min_overlap_similarity = self.config.get('min_overlap_similarity', 0.8)  # 最小相似度
        self.max_pages_to_check = self.config.get('max_pages_to_check', 3)  # 最大检查页数
        self.enable_llm_stitching = self.config.get('enable_llm_stitching', True)

        # 语法检查规则
        self.syntax_patterns = self._build_syntax_patterns()

    def check_continuity(self, content: str, page_boundaries: Optional[List[int]] = None) -> List[ContinuityProblem]:
        """
        检查内容的连续性

        Args:
            content: 完整内容
            page_boundaries: 页面边界位置列表

        Returns:
            List[ContinuityProblem]: 发现的问题列表
        """
        problems = []

        # 检查JSON完整性
        problems.extend(self._check_json_integrity(content))

        # 检查Markdown表格完整性
        problems.extend(self._check_markdown_table_integrity(content))

        # 检查列表完整性
        problems.extend(self._check_list_integrity(content))

        # 检查代码块完整性
        problems.extend(self._check_code_block_integrity(content))

        # 检查页面边界连续性（如果有页面边界信息）
        if page_boundaries:
            problems.extend(self._check_page_boundary_continuity(content, page_boundaries))

        # 按严重程度排序
        problems.sort(key=lambda p: p.severity, reverse=True)

        logger.info(f"连续性检查完成，发现 {len(problems)} 个问题")
        return problems

    def repair_continuity(self, content: str, problems: List[ContinuityProblem],
                         overlap_regions: Optional[List[OverlapRegion]] = None) -> str:
        """
        修复连续性问题

        Args:
            content: 原始内容
            problems: 发现的问题
            overlap_regions: 重叠区域信息

        Returns:
            str: 修复后的内容
        """
        if not problems:
            return content

        repaired_content = content

        # 按位置排序问题（从后往前修复，避免位置偏移）
        sorted_problems = sorted(problems, key=lambda p: p.location[1], reverse=True)

        for problem in sorted_problems:
            try:
                repaired_content = self._apply_fix(repaired_content, problem, overlap_regions)
            except Exception as e:
                logger.warning(f"修复问题失败 {problem.issue_type.value}: {e}")
                continue

        logger.info(f"连续性修复完成，处理了 {len(problems)} 个问题")
        return repaired_content

    def find_overlap_regions(self, page_contents: List[str]) -> List[OverlapRegion]:
        """
        查找页面间的重叠区域

        Args:
            page_contents: 各页面的内容列表

        Returns:
            List[OverlapRegion]: 重叠区域列表
        """
        overlap_regions = []

        for i in range(len(page_contents) - 1):
            page_a = page_contents[i]
            page_b = page_contents[i + 1]

            overlap = self._find_page_overlap(page_a, page_b)
            if overlap:
                overlap_regions.append(OverlapRegion(
                    page_a_end=len(page_a),
                    page_b_start=0,  # 简化处理
                    overlap_content=overlap["content"],
                    confidence=overlap["confidence"]
                ))

        return overlap_regions

    def _build_syntax_patterns(self) -> Dict[str, Dict[str, Any]]:
        """构建语法检查模式"""
        return {
            "json": {
                "start_pattern": r'\{',
                "end_pattern": r'\}',
                "validator": self._validate_json_syntax
            },
            "markdown_table": {
                "start_pattern": r'\|.*\|.*\n\|[\s\-\|:]+\|',
                "end_pattern": r'(?=\n\n|\n#{1,6}|\n[\-\*\+]|\Z)',
                "validator": self._validate_table_syntax
            },
            "list": {
                "start_pattern": r'^[\s]*[-\*\+]|\d+\.',
                "end_pattern": r'(?=\n\n|\n#{1,6}|\Z)',
                "validator": self._validate_list_syntax
            },
            "code_block": {
                "start_pattern": r'```',
                "end_pattern": r'```',
                "validator": self._validate_code_block_syntax
            }
        }

    def _check_json_integrity(self, content: str) -> List[ContinuityProblem]:
        """检查JSON完整性"""
        problems = []

        # 查找JSON对象
        json_matches = re.finditer(r'\{.*?\}(?=\s*(?:\{|\n\n|\Z))', content, re.DOTALL)

        for match in json_matches:
            json_str = match.group(0)
            try:
                json.loads(json_str)
            except json.JSONDecodeError as e:
                problems.append(ContinuityProblem(
                    issue_type=ContinuityIssue.INCOMPLETE_JSON,
                    location=(match.start(), match.end()),
                    severity=0.8,
                    context=json_str[:100],
                    suggested_fix=f"JSON解析错误: {e.msg}"
                ))

        return problems

    def _check_markdown_table_integrity(self, content: str) -> List[ContinuityProblem]:
        """检查Markdown表格完整性"""
        problems = []

        # 查找表格
        table_pattern = r'(\|.*\|.*\n\|[\s\-\|:]+\|(?:\n\|.*\|)*)'
        table_matches = re.finditer(table_pattern, content, re.MULTILINE)

        for match in table_matches:
            table_content = match.group(0)
            if not self._validate_table_syntax(table_content):
                problems.append(ContinuityProblem(
                    issue_type=ContinuityIssue.INCOMPLETE_MARKDOWN_TABLE,
                    location=(match.start(), match.end()),
                    severity=0.7,
                    context=table_content[:100],
                    suggested_fix="表格结构不完整，缺少分隔行或数据行"
                ))

        return problems

    def _check_list_integrity(self, content: str) -> List[ContinuityProblem]:
        """检查列表完整性"""
        problems = []

        # 查找列表
        list_pattern = r'(?:^[\s]*[-\*\+]|\d+\..*?(?=\n\n|\n#{1,6}|\Z))'
        list_matches = re.finditer(list_pattern, content, re.MULTILINE)

        for match in list_matches:
            list_content = match.group(0)
            if not self._validate_list_syntax(list_content):
                problems.append(ContinuityProblem(
                    issue_type=ContinuityIssue.INCOMPLETE_LIST,
                    location=(match.start(), match.end()),
                    severity=0.5,
                    context=list_content[:100],
                    suggested_fix="列表结构不完整"
                ))

        return problems

    def _check_code_block_integrity(self, content: str) -> List[ContinuityProblem]:
        """检查代码块完整性"""
        problems = []

        # 查找代码块
        code_block_pattern = r'```.*?(?=```|\Z)'
        code_matches = re.finditer(code_block_pattern, content, re.DOTALL)

        for match in code_matches:
            code_content = match.group(0)
            if not code_content.endswith('```'):
                problems.append(ContinuityProblem(
                    issue_type=ContinuityIssue.INCOMPLETE_CODE_BLOCK,
                    location=(match.start(), match.end()),
                    severity=0.6,
                    context=code_content[:100],
                    suggested_fix="代码块未正确关闭"
                ))

        return problems

    def _check_page_boundary_continuity(self, content: str, page_boundaries: List[int]) -> List[ContinuityProblem]:
        """检查页面边界连续性"""
        problems = []

        for boundary in page_boundaries:
            if boundary >= len(content):
                continue

            # 检查边界附近的连续性
            context_start = max(0, boundary - 50)
            context_end = min(len(content), boundary + 50)
            context = content[context_start:context_end]

            # 检查是否有被截断的句子
            if self._is_truncated_sentence(context, boundary - context_start):
                problems.append(ContinuityProblem(
                    issue_type=ContinuityIssue.TRUNCATED_SENTENCE,
                    location=(boundary - 20, boundary + 20),
                    severity=0.4,
                    context=context,
                    suggested_fix="句子在页面边界被截断"
                ))

        return problems

    def _find_page_overlap(self, page_a: str, page_b: str) -> Optional[Dict[str, Any]]:
        """
        查找两页之间的重叠内容

        使用序列匹配算法找到页面间的重叠区域
        """
        # 取页面A的末尾和页面B的开头进行比较
        window_a = page_a[-self.overlap_window_size:] if len(page_a) > self.overlap_window_size else page_a
        window_b = page_b[:self.overlap_window_size] if len(page_b) > self.overlap_window_size else page_b

        # 使用difflib计算相似度
        matcher = difflib.SequenceMatcher(None, window_a, window_b)
        similarity = matcher.ratio()

        if similarity >= self.min_overlap_similarity:
            # 找到最长的匹配块
            blocks = matcher.get_matching_blocks()
            if blocks:
                best_block = max(blocks, key=lambda b: b.size)
                overlap_content = window_a[best_block.a: best_block.a + best_block.size]

                return {
                    "content": overlap_content,
                    "confidence": similarity,
                    "position_a": len(page_a) - len(window_a) + best_block.a,
                    "position_b": best_block.b
                }

        return None

    def _apply_fix(self, content: str, problem: ContinuityProblem,
                  overlap_regions: Optional[List[OverlapRegion]] = None) -> str:
        """应用修复"""
        start, end = problem.location

        if problem.issue_type == ContinuityIssue.INCOMPLETE_JSON:
            return self._fix_incomplete_json(content, start, end)
        elif problem.issue_type == ContinuityIssue.INCOMPLETE_MARKDOWN_TABLE:
            return self._fix_incomplete_table(content, start, end, overlap_regions)
        elif problem.issue_type == ContinuityIssue.INCOMPLETE_CODE_BLOCK:
            return self._fix_incomplete_code_block(content, start, end)
        elif problem.issue_type == ContinuityIssue.TRUNCATED_SENTENCE:
            return self._fix_truncated_sentence(content, start, end, overlap_regions)

        # 默认保持不变
        return content

    def _fix_incomplete_json(self, content: str, start: int, end: int) -> str:
        """修复不完整的JSON"""
        json_part = content[start:end]

        # 尝试补全JSON结构
        open_braces = json_part.count('{')
        close_braces = json_part.count('}')

        if open_braces > close_braces:
            # 添加缺失的关闭大括号
            missing_braces = open_braces - close_braces
            json_part += '}' * missing_braces

        return content[:start] + json_part + content[end:]

    def _fix_incomplete_table(self, content: str, start: int, end: int,
                            overlap_regions: Optional[List[OverlapRegion]] = None) -> str:
        """修复不完整的表格"""
        table_part = content[start:end]

        # 如果有重叠区域信息，尝试使用重叠内容补全表格
        if overlap_regions:
            for region in overlap_regions:
                if region.confidence > 0.7:
                    # 查找表格续接点
                    lines = table_part.split('\n')
                    if lines and '|' in lines[-1]:
                        # 在表格末尾添加续接内容
                        extension = f"\n{region.overlap_content}"
                        table_part += extension
                        break

        return content[:start] + table_part + content[end:]

    def _fix_incomplete_code_block(self, content: str, start: int, end: int) -> str:
        """修复不完整的代码块"""
        code_part = content[start:end]

        # 添加缺失的代码块结束标记
        if not code_part.endswith('```'):
            code_part += '\n```'

        return content[:start] + code_part + content[end:]

    def _fix_truncated_sentence(self, content: str, start: int, end: int,
                              overlap_regions: Optional[List[OverlapRegion]] = None) -> str:
        """修复被截断的句子"""
        context = content[start:end]

        # 如果有重叠区域，尝试找到句子续接
        if overlap_regions:
            for region in overlap_regions:
                if region.confidence > 0.6:
                    # 查找句子的续接点
                    words = region.overlap_content.split()
                    if words:
                        # 添加续接词
                        continuation = f" {words[0]}..."
                        context += continuation
                        break

        return content[:start] + context + content[end:]

    # 验证辅助方法
    def _validate_json_syntax(self, content: str) -> bool:
        """验证JSON语法"""
        try:
            json.loads(content)
            return True
        except json.JSONDecodeError:
            return False

    def _validate_table_syntax(self, content: str) -> bool:
        """验证表格语法"""
        lines = content.strip().split('\n')
        if len(lines) < 2:
            return False

        # 检查是否有分隔行
        has_separator = False
        for line in lines[1:]:
            if re.match(r'^\s*\|[\s\-\|:]+\|\s*$', line):
                has_separator = True
                break

        return has_separator

    def _validate_list_syntax(self, content: str) -> bool:
        """验证列表语法"""
        # 简单检查是否有列表标记
        return bool(re.search(r'^[\s]*[-\*\+]|\d+\.', content, re.MULTILINE))

    def _validate_code_block_syntax(self, content: str) -> bool:
        """验证代码块语法"""
        return content.count('```') >= 2 and content.endswith('```')

    def _is_truncated_sentence(self, context: str, boundary_pos: int) -> bool:
        """检查句子是否在边界处被截断"""
        if boundary_pos <= 0 or boundary_pos >= len(context):
            return False

        # 检查边界前后的字符
        before = context[boundary_pos - 1] if boundary_pos > 0 else ''
        after = context[boundary_pos] if boundary_pos < len(context) else ''

        # 如果前一个字符是句子中间的字符，且后一个字符是大写字母，可能是截断
        return (before and before not in '.!?' and after and after.isupper())
