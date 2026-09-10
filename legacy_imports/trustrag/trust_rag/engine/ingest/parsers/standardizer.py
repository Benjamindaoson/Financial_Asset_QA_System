"""
Standardizer - Markdown标准化后处理器

解决不同Tier解析器输出格式不一致的问题：
1. 表格格式统一
2. 标题层级标准化
3. 引用格式规范
4. 代码块格式统一
5. 列表格式规范

确保所有Tier输出严格同分布，消除语义不一致性
"""
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .base_parser import ParsedDocument, ParserTier

logger = logging.getLogger(__name__)


class MarkdownStyle(Enum):
    """Markdown风格枚举"""
    GITHUB = "github"      # GitHub风格
    COMMONMARK = "commonmark"  # CommonMark标准
    STRICT = "strict"      # 严格格式
    FINANCIAL = "financial"  # 财务文档专用


@dataclass
class StandardizationRule:
    """标准化规则"""
    pattern: str
    replacement: str
    description: str
    priority: int = 1  # 处理优先级，数字越大越先处理


class MarkdownStandardizer:
    """
    Markdown标准化器

    统一不同解析器输出的Markdown格式，确保语义一致性
    """

    def __init__(self, style: MarkdownStyle = MarkdownStyle.FINANCIAL):
        self.style = style
        self.rules = self._build_standardization_rules()

    def standardize(self, parsed_doc: ParsedDocument) -> ParsedDocument:
        """
        标准化ParsedDocument

        Args:
            parsed_doc: 原始解析结果

        Returns:
            ParsedDocument: 标准化后的结果
        """
        if not parsed_doc.content or not parsed_doc.content.strip():
            return parsed_doc

        original_content = parsed_doc.content
        standardized_content = original_content

        # 按优先级应用标准化规则
        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            try:
                standardized_content = re.sub(
                    rule.pattern,
                    rule.replacement,
                    standardized_content,
                    flags=re.MULTILINE | re.DOTALL
                )
            except Exception as e:
                logger.warning(f"应用规则失败 '{rule.description}': {e}")
                continue

        # 应用特定于文档类型的标准化
        standardized_content = self._apply_domain_specific_standardization(
            standardized_content, parsed_doc
        )

        # 验证标准化结果
        validation_result = self._validate_standardization(
            original_content, standardized_content
        )

        # 更新文档
        standardized_doc = parsed_doc.copy()
        standardized_doc.content = standardized_content
        standardized_doc.raw_metadata = parsed_doc.raw_metadata.copy()
        standardized_doc.raw_metadata.update({
            "standardization_applied": True,
            "standardization_style": self.style.value,
            "original_length": len(original_content),
            "standardized_length": len(standardized_content),
            "content_preserved": validation_result["content_preserved"],
            "format_consistency_score": validation_result["format_consistency_score"]
        })

        logger.info(f"Markdown标准化完成: {len(original_content)} -> {len(standardized_content)} 字符")

        return standardized_doc

    def _build_standardization_rules(self) -> List[StandardizationRule]:
        """构建标准化规则"""
        rules = []

        # 表格格式统一
        rules.extend(self._build_table_rules())

        # 标题格式统一
        rules.extend(self._build_header_rules())

        # 列表格式统一
        rules.extend(self._build_list_rules())

        # 引用和脚注格式统一
        rules.extend(self._build_reference_rules())

        # 代码块格式统一
        rules.extend(self._build_code_rules())

        # 财务文档专用规则
        if self.style == MarkdownStyle.FINANCIAL:
            rules.extend(self._build_financial_rules())

        return rules

    def _build_table_rules(self) -> List[StandardizationRule]:
        """表格格式标准化规则"""
        rules = []

        # 统一表格分隔符（使用GitHub风格的|分隔符）
        rules.append(StandardizationRule(
            pattern=r'^[\s]*\|[\s]*[-:\s]*\|[\s]*$',
            replacement=lambda m: self._standardize_table_separator(m.group(0)),
            description="标准化表格分隔行",
            priority=5
        ))

        # 修复表格对齐
        rules.append(StandardizationRule(
            pattern=r'(\|[\s]*:?-+:?[\s]*\|)',
            replacement=lambda m: self._fix_table_alignment(m.group(1)),
            description="修复表格列对齐",
            priority=4
        ))

        # 清理表格中的多余空格
        rules.append(StandardizationRule(
            pattern=r'\|[\s]+',
            replacement='| ',
            description="清理表格中多余的空格",
            priority=3
        ))

        rules.append(StandardizationRule(
            pattern=r'[\s]+\|',
            replacement=' |',
            description="清理表格中多余的空格",
            priority=3
        ))

        return rules

    def _build_header_rules(self) -> List[StandardizationRule]:
        """标题格式标准化规则"""
        rules = []

        # 统一标题格式（确保#后有空格）
        for level in range(1, 7):
            hash_marks = '#' * level
            rules.append(StandardizationRule(
                pattern=f'^{hash_marks}([^\\s#])',
                replacement=f'{hash_marks} \\1',
                description=f"标题级别{level}后添加空格",
                priority=3
            ))

        # 移除标题后多余的#
        rules.append(StandardizationRule(
            pattern=r'^(#{1,6}[^#]*)#+\s*$',
            replacement=r'\1',
            description="移除标题后多余的#号",
            priority=3
        ))

        return rules

    def _build_list_rules(self) -> List[StandardizationRule]:
        """列表格式标准化规则"""
        rules = []

        # 有序列表统一格式
        rules.append(StandardizationRule(
            pattern=r'^(\d+)\.([^\s])',
            replacement=r'\1. \2',
            description="有序列表项后添加空格",
            priority=3
        ))

        # 无序列表统一使用-
        rules.append(StandardizationRule(
            pattern=r'^[\s]*[*+][\s]+',
            replacement='- ',
            description="统一无序列表符号为-",
            priority=3
        ))

        return rules

    def _build_reference_rules(self) -> List[StandardizationRule]:
        """引用和脚注格式标准化规则"""
        rules = []

        # 统一脚注格式 [1]
        rules.append(StandardizationRule(
            pattern=r'\[(\d+)\]',
            replacement=r'[\1]',
            description="标准化脚注格式",
            priority=2
        ))

        # 统一引用格式
        rules.append(StandardizationRule(
            pattern=r'^>\s*([^>])',
            replacement=r'> \1',
            description="标准化引用块格式",
            priority=2
        ))

        return rules

    def _build_code_rules(self) -> List[StandardizationRule]:
        """代码块格式标准化规则"""
        rules = []

        # 统一代码块分隔符
        rules.append(StandardizationRule(
            pattern=r'```(\w+)?',
            replacement=r'```\1',
            description="标准化代码块语言标识",
            priority=2
        ))

        return rules

    def _build_financial_rules(self) -> List[StandardizationRule]:
        """财务文档专用标准化规则"""
        rules = []

        # 货币符号统一
        rules.append(StandardizationRule(
            pattern=r'\$([\d,]+(?:\.\d+)?)',
            replacement=r'$\1',
            description="标准化美元符号格式",
            priority=4
        ))

        # 百分比格式统一
        rules.append(StandardizationRule(
            pattern=r'(\d+(?:\.\d+)?)\s*%',
            replacement=r'\1%',
            description="标准化百分比格式",
            priority=3
        ))

        # 财务表格特殊处理（确保数字列右对齐）
        rules.append(StandardizationRule(
            pattern=r'\|([\s]*[\d,]+\.?\d*[\s]*)\|',
            replacement=lambda m: self._align_numeric_column(m.group(1)),
            description="数字列右对齐",
            priority=4
        ))

        return rules

    def _apply_domain_specific_standardization(self, content: str, parsed_doc: ParsedDocument) -> str:
        """
        应用特定于文档类型的标准化

        基于解析器层级和文档类型进行针对性处理
        """
        # 如果是财务文档，应用额外的财务格式化
        if self._is_financial_document(parsed_doc):
            content = self._apply_financial_formatting(content)

        # 根据解析器层级进行调整
        if parsed_doc.parser_tier == ParserTier.TIER_1:
            # Tier 1可能需要更多格式化
            content = self._enhance_tier1_formatting(content)
        elif parsed_doc.parser_tier == ParserTier.TIER_3:
            # Tier 3的输出通常已经很规范，但可能需要清理
            content = self._clean_tier3_artifacts(content)

        return content

    def _is_financial_document(self, parsed_doc: ParsedDocument) -> bool:
        """判断是否为财务文档"""
        content_lower = parsed_doc.content.lower()
        financial_keywords = [
            'balance sheet', 'income statement', 'cash flow',
            '资产负债表', '利润表', '现金流量表',
            'financial statements', '财务报表'
        ]

        return any(keyword in content_lower for keyword in financial_keywords)

    def _apply_financial_formatting(self, content: str) -> str:
        """应用财务文档专用格式化"""
        # 确保财务表格的数字格式
        lines = content.split('\n')
        formatted_lines = []

        in_table = False
        for line in lines:
            if '|' in line and ('$' in line or re.search(r'\d{1,3}(?:,\d{3})+', line)):
                in_table = True
                # 财务表格中的数字格式化
                line = self._format_financial_numbers(line)
            elif line.strip() and not line.startswith('|'):
                in_table = False

            formatted_lines.append(line)

        return '\n'.join(formatted_lines)

    def _enhance_tier1_formatting(self, content: str) -> str:
        """增强Tier 1的格式化"""
        # Tier 1的输出可能比较简单，需要添加更多结构
        lines = content.split('\n')
        formatted_lines = []

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                formatted_lines.append("")
                continue

            # 尝试识别可能的标题
            if self._is_potential_header(line, lines, i):
                formatted_lines.append(f"## {line}")
            else:
                formatted_lines.append(line)

        return '\n'.join(formatted_lines)

    def _clean_tier3_artifacts(self, content: str) -> str:
        """清理Tier 3的输出 artifacts"""
        # VLM可能产生的一些不需要的格式
        # 移除多余的解释性文字
        content = re.sub(r'^请将此.*?\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^输出格式：.*?\n', '', content, flags=re.MULTILINE)

        return content

    def _validate_standardization(self, original: str, standardized: str) -> Dict[str, Any]:
        """验证标准化结果"""
        # 检查内容是否基本保持
        original_length = len(original)
        standardized_length = len(standardized)
        content_preserved = abs(original_length - standardized_length) / max(original_length, 1) < 0.5

        # 格式一致性评分（基于表格和标题的正确性）
        consistency_score = self._calculate_format_consistency(standardized)

        return {
            "content_preserved": content_preserved,
            "format_consistency_score": consistency_score,
            "length_change_ratio": (standardized_length - original_length) / max(original_length, 1)
        }

    def _calculate_format_consistency(self, content: str) -> float:
        """计算格式一致性评分"""
        score = 1.0

        # 检查表格格式一致性
        table_lines = [line for line in content.split('\n') if '|' in line]
        if table_lines:
            # 检查是否有分隔行
            separator_lines = [line for line in table_lines if re.match(r'^\s*\|[\s\-\|:]+\|\s*$', line)]
            if not separator_lines:
                score -= 0.3

        # 检查标题格式一致性
        header_lines = [line for line in content.split('\n') if line.strip().startswith('#')]
        if header_lines:
            # 检查是否有空格
            malformed_headers = [line for line in header_lines if not re.match(r'^#{1,6}\s+', line)]
            if malformed_headers:
                score -= 0.2

        return max(0.0, score)

    # 辅助方法
    def _standardize_table_separator(self, separator: str) -> str:
        """标准化表格分隔行"""
        # 确保分隔行格式正确
        parts = separator.split('|')
        standardized_parts = []
        for part in parts:
            part = part.strip()
            if part:
                # 使用标准的分隔符格式
                standardized_parts.append('---')
            else:
                standardized_parts.append('')

        return '|'.join(standardized_parts)

    def _fix_table_alignment(self, alignment: str) -> str:
        """修复表格对齐"""
        # 简化对齐处理，确保格式正确
        return alignment.strip()

    def _align_numeric_column(self, content: str) -> str:
        """数字列右对齐"""
        # 对于财务表格，确保数字右对齐
        stripped = content.strip()
        if re.match(r'^[\d,]+\.?\d*$', stripped):
            return f"{stripped:>10}"
        return content

    def _format_financial_numbers(self, line: str) -> str:
        """格式化财务数字"""
        # 确保财务数字的格式一致
        def format_number(match):
            num = match.group(1)
            # 移除多余的格式化，保持原始格式
            return f"${num}"

        line = re.sub(r'\$([\d,]+(?:\.\d+)?)', format_number, line)
        return line

    def _is_potential_header(self, line: str, all_lines: List[str], index: int) -> bool:
        """判断是否可能是标题"""
        # 基于上下文和格式的启发式判断
        if len(line) > 100:  # 太长了
            return False

        # 检查是否全大写
        if line.isupper() and len(line) > 5:
            return True

        # 检查上下文（下一行是否为空行或短行）
        if index + 1 < len(all_lines):
            next_line = all_lines[index + 1].strip()
            if not next_line or len(next_line) < len(line) * 0.5:
                return True

        return False
