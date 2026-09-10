"""
TieredDocumentParser - 智能路由决策大脑

实现"三层梯度解析引擎"的总控类：
1. DocumentLayoutAnalyzer：裁判逻辑，利用PyMuPDF快速探测，决定路由
2. TieredDocumentParser：总控类，按裁判结果调度对应Parser
3. CostEstimator：成本预警模块，预估Token超过阈值时记录COST_WARNING
4. test_tiered_pipeline.py：验收脚本，测试纯文本、发票、财报对比
"""
import os
import time
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

import fitz
from PIL import Image

from .base_parser import BaseParser, ParserTier, ParsedDocument, ParserError, FatalError
from .standardizer import MarkdownStandardizer
from .native_text_parser import NativeTextParser
from .standard_ocr_parser import StandardOCRParser
from .vision_semantic_parser import VisionSemanticParser

logger = logging.getLogger(__name__)


class DocumentComplexity(Enum):
    """文档复杂度枚举"""
    SIMPLE_TEXT = "simple_text"          # 纯文本文档
    STANDARD_LAYOUT = "standard_layout"  # 标准布局（表格、图片少）
    COMPLEX_FINANCIAL = "complex_financial"  # 复杂财务报表
    HIGH_COMPLEXITY = "high_complexity"  # 高复杂度文档


@dataclass
class LayoutAnalysis:
    """布局分析结果"""
    complexity: DocumentComplexity
    recommended_tier: ParserTier
    confidence: float
    features: Dict[str, Any]
    reasoning: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "complexity": self.complexity.value,
            "recommended_tier": self.recommended_tier.value,
            "confidence": self.confidence,
            "features": self.features,
            "reasoning": self.reasoning
        }


@dataclass
class CostEstimation:
    """成本估算结果"""
    estimated_tokens: int
    estimated_cost: float
    currency: str = "USD"
    breakdown: Dict[str, Any] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.breakdown is None:
            self.breakdown = {}
        if self.warnings is None:
            self.warnings = []


class CostEstimator:
    """
    成本估算模块

    预估不同层级的处理成本，超过阈值时发出警告
    """

    # Token成本估算（每1000 tokens）
    TOKEN_COSTS = {
        ParserTier.TIER_1: 0.001,    # 几乎免费
        ParserTier.TIER_2: 0.01,     # OCR处理
        ParserTier.TIER_3: 0.05      # VLM处理
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.cost_threshold = self.config.get('cost_threshold', 0.1)  # 0.1美元阈值
        self.token_overhead_factor = self.config.get('token_overhead_factor', 1.2)

    def estimate_cost(self, file_path: str, tier: ParserTier,
                     layout_features: Dict[str, Any]) -> CostEstimation:
        """
        估算处理成本

        Args:
            file_path: 文件路径
            tier: 解析层级
            layout_features: 布局特征

        Returns:
            CostEstimation: 成本估算结果
        """
        # 获取文件基本信息
        file_size = os.path.getsize(file_path)
        page_count = layout_features.get('total_pages', 1)

        # 估算token数量
        base_tokens = self._estimate_tokens(file_size, page_count, layout_features)
        estimated_tokens = int(base_tokens * self.token_overhead_factor)

        # 计算成本
        cost_per_1000 = self.TOKEN_COSTS[tier]
        estimated_cost = (estimated_tokens / 1000) * cost_per_1000

        # 成本分解
        breakdown = {
            "base_tokens": base_tokens,
            "overhead_factor": self.token_overhead_factor,
            "cost_per_1000_tokens": cost_per_1000,
            "page_count": page_count,
            "file_size_mb": file_size / 1024 / 1024
        }

        # 检查阈值警告
        warnings = []
        if estimated_cost > self.cost_threshold:
            warnings.append(".2f")

        return CostEstimation(
            estimated_tokens=estimated_tokens,
            estimated_cost=round(estimated_cost, 4),
            breakdown=breakdown,
            warnings=warnings
        )

    def _estimate_tokens(self, file_size: int, page_count: int,
                        layout_features: Dict[str, Any]) -> int:
        """
        估算文档的token数量

        基于文件大小、页面数和复杂度特征
        """
        # 基础估算：假设每页平均500个token
        base_tokens = page_count * 500

        # 根据文件大小调整
        size_mb = file_size / 1024 / 1024
        if size_mb > 10:
            base_tokens *= 1.5  # 大文件通常内容更多

        # 根据复杂度调整
        complexity_multipliers = {
            "has_tables": 1.3,
            "has_images": 1.2,
            "has_complex_layout": 1.4,
            "high_text_density": 1.1
        }

        for feature, multiplier in complexity_multipliers.items():
            if layout_features.get(feature, False):
                base_tokens *= multiplier

        return int(base_tokens)


class DocumentLayoutAnalyzer:
    """
    文档布局分析器 - 智能裁判

    快速探测文档特征，决定最合适的解析层级：
    1. 利用PyMuPDF快速提取文本和布局信息
    2. 轻量级YOLO或规则引擎检测复杂元素
    3. 基于特征给出复杂度判断和层级推荐
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # 分析配置
        self.max_sample_pages = self.config.get('max_sample_pages', 5)  # 最多分析5页
        self.image_ratio_threshold = self.config.get('image_ratio_threshold', 0.3)  # 图片占比阈值
        self.table_detection_threshold = self.config.get('table_detection_threshold', 3)  # 表格检测阈值

        # 冷启动优化配置
        self.enable_smart_sampling = self.config.get('enable_smart_sampling', True)
        self.long_doc_threshold = self.config.get('long_doc_threshold', 100)  # 长文档阈值（页数）
        self.head_tail_pages = self.config.get('head_tail_pages', 3)  # 首尾各取几页
        self.random_sample_ratio = self.config.get('random_sample_ratio', 0.1)  # 随机采样比例

        # 复杂度判断阈值
        self.complexity_thresholds = {
            "image_ratio_tier3": 0.2,      # 图片占比>20% -> TIER_3
            "table_count_tier3": 5,        # 表格数量>5 -> TIER_3
            "merged_cells_tier3": True,    # 检测到合并单元格 -> TIER_3
            "formula_density_tier3": 0.1,  # 公式密度>10% -> TIER_3
            "table_count_tier2": 1,        # 表格数量>1 -> TIER_2
            "image_ratio_tier2": 0.05      # 图片占比>5% -> TIER_2
        }

    def analyze_document(self, file_path: str) -> LayoutAnalysis:
        """
        分析文档布局和复杂度

        支持智能采样策略：
        - 短文档：全量分析
        - 长文档：首尾+随机采样，避免全量扫描延迟

        Args:
            file_path: PDF文件路径

        Returns:
            LayoutAnalysis: 布局分析结果
        """
        start_time = time.time()

        try:
            # 打开文档
            doc = fitz.open(file_path)
            total_pages = len(doc)

            # 根据文档长度选择采样策略
            if self.enable_smart_sampling and total_pages > self.long_doc_threshold:
                # 长文档：智能采样
                sampled_page_nums = self._smart_sample_pages(doc, total_pages)
            else:
                # 短文档：传统采样
                sample_pages = min(self.max_sample_pages, total_pages)
                sampled_page_nums = self._select_sample_pages(total_pages, sample_pages)

            # 收集特征
            features = self._extract_layout_features(doc, sampled_page_nums)

            # 计算复杂度
            complexity, reasoning = self._determine_complexity(features)

            # 推荐解析层级
            recommended_tier, confidence = self._recommend_tier(complexity, features)

            doc.close()

            analysis_time = time.time() - start_time

            logger.info(f"文档分析完成: {file_path} ({total_pages}页), "
                      f"采样{len(sampled_page_nums)}页, 复杂度: {complexity.value}, "
                      f"推荐层级: {recommended_tier.value}, 耗时: {analysis_time:.2f}s")

            return LayoutAnalysis(
                complexity=complexity,
                recommended_tier=recommended_tier,
                confidence=confidence,
                features=features,
                reasoning=reasoning
            )

        except Exception as e:
            if 'doc' in locals():
                doc.close()
            logger.error(f"文档分析失败: {e}")
            raise ParserError(f"文档布局分析失败: {e}")

    def _smart_sample_pages(self, doc, total_pages: int) -> List[int]:
        """
        智能采样策略 - 针对长文档优化

        策略：
        1. 固定采样首尾页（head_tail_pages参数控制）
        2. 从中间部分随机采样（random_sample_ratio控制）
        3. 优先采样可能包含复杂内容的页面

        Args:
            doc: PDF文档对象
            total_pages: 总页数

        Returns:
            List[int]: 采样页面编号列表
        """
        selected = []

        # 1. 固定采样首尾页
        # 取前head_tail_pages页
        for i in range(min(self.head_tail_pages, total_pages)):
            selected.append(i)

        # 取后head_tail_pages页
        for i in range(max(0, total_pages - self.head_tail_pages), total_pages):
            if i not in selected:
                selected.append(i)

        # 2. 计算需要随机采样的页数
        remaining_slots = max(0, self.max_sample_pages - len(selected))
        if remaining_slots > 0 and total_pages > len(selected):
            # 计算随机采样范围（排除首尾）
            middle_start = self.head_tail_pages
            middle_end = total_pages - self.head_tail_pages

            if middle_end > middle_start:
                # 计算采样比例，但不超过remaining_slots
                target_samples = min(
                    remaining_slots,
                    max(1, int((middle_end - middle_start) * self.random_sample_ratio))
                )

                # 生成随机采样（使用确定性种子确保可重现）
                import random
                random.seed(42)  # 固定种子

                middle_pages = list(range(middle_start, middle_end))
                sampled_middle = random.sample(middle_pages, min(target_samples, len(middle_pages)))

                selected.extend(sampled_middle)

        # 3. 智能优先级排序（可选）
        # 可以根据页面的复杂度特征进行优先级排序，但这里简化处理

        return sorted(list(set(selected)))  # 去重并排序

    def _select_sample_pages(self, total_pages: int, sample_count: int) -> List[int]:
        """
        传统采样策略 - 向后兼容

        策略：优先选择首尾页和中间页
        """
        if total_pages <= sample_count:
            return list(range(total_pages))

        # 确保包含第一页和最后一页
        selected = [0]  # 第一页

        if total_pages > 1:
            selected.append(total_pages - 1)  # 最后一页

        # 添加中间页
        remaining_slots = sample_count - len(selected)
        if remaining_slots > 0:
            step = max(1, (total_pages - 2) // remaining_slots)
            for i in range(1, total_pages - 1, step):
                if len(selected) < sample_count:
                    selected.append(i)

        return sorted(selected)

    def _extract_layout_features(self, doc, page_nums: List[int]) -> Dict[str, Any]:
        """
        提取布局特征
        """
        features = {
            "total_pages": len(doc),
            "analyzed_pages": len(page_nums),
            "text_pages": 0,
            "image_pages": 0,
            "total_text_length": 0,
            "total_image_area": 0.0,
            "total_page_area": 0.0,
            "table_indicators": 0,
            "has_merged_cells": False,
            "has_formulas": False,
            "has_headers_footers": False,
            "text_lines": [],
            "image_ratios": []
        }

        for page_num in page_nums:
            page = doc.load_page(page_num)
            page_features = self._analyze_single_page(page)

            # 合并特征
            if page_features["has_text"]:
                features["text_pages"] += 1
            if page_features["has_images"]:
                features["image_pages"] += 1

            features["total_text_length"] += page_features["text_length"]
            features["total_image_area"] += page_features["image_area"]
            features["total_page_area"] += page_features["page_area"]
            features["table_indicators"] += page_features["table_indicators"]

            if page_features["has_merged_cells"]:
                features["has_merged_cells"] = True
            if page_features["has_formulas"]:
                features["has_formulas"] = True
            if page_features["has_headers_footers"]:
                features["has_headers_footers"] = True

            features["text_lines"].extend(page_features["text_lines"])
            features["image_ratios"].append(page_features["image_ratio"])

        # 计算汇总指标
        features["avg_text_density"] = (
            features["total_text_length"] / max(features["analyzed_pages"], 1)
        )
        features["avg_image_ratio"] = (
            sum(features["image_ratios"]) / max(len(features["image_ratios"]), 1)
        )
        features["has_tables"] = features["table_indicators"] >= self.table_detection_threshold
        features["has_images"] = features["image_pages"] > 0
        features["high_text_density"] = features["avg_text_density"] > 2000

        return features

    def _analyze_single_page(self, page) -> Dict[str, Any]:
        """
        分析单个页面
        """
        features = {
            "has_text": False,
            "has_images": False,
            "text_length": 0,
            "image_area": 0.0,
            "page_area": 0.0,
            "table_indicators": 0,
            "has_merged_cells": False,
            "has_formulas": False,
            "has_headers_footers": False,
            "text_lines": [],
            "image_ratio": 0.0
        }

        # 获取页面尺寸
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height
        features["page_area"] = page_area

        # 提取文本
        text = page.get_text()
        text_length = len(text.strip())
        features["text_length"] = text_length
        features["has_text"] = text_length > 50

        # 分析文本行
        text_lines = text.split('\n')
        features["text_lines"] = [line.strip() for line in text_lines if line.strip()]

        # 检测表格特征
        features["table_indicators"] = self._detect_table_features(text_lines)

        # 检测合并单元格（启发式）
        features["has_merged_cells"] = self._detect_merged_cells(text_lines)

        # 检测公式
        features["has_formulas"] = self._detect_formulas(text_lines)

        # 检测页眉页脚
        features["has_headers_footers"] = self._detect_headers_footers(text_lines, page_rect)

        # 分析图片
        images = page.get_images(full=True)
        if images:
            features["has_images"] = True
            # 估算图片面积占比
            for img in images:
                try:
                    img_rect = page.get_image_bbox(img)
                    if img_rect:
                        img_area = (img_rect.x1 - img_rect.x0) * (img_rect.y1 - img_rect.y0)
                        features["image_area"] += img_area
                except:
                    pass

            features["image_ratio"] = features["image_area"] / page_area

        return features

    def _detect_table_features(self, text_lines: List[str]) -> int:
        """
        检测表格特征
        """
        indicators = 0

        for line in text_lines:
            line = line.strip()
            if not line:
                continue

            # 检查分隔符
            if '|' in line or '\t' in line:
                indicators += 2

            # 检查数字列
            import re
            numbers = re.findall(r'\d+\.?\d*', line)
            if len(numbers) >= 3:
                indicators += 1

            # 检查表头特征
            if re.match(r'^\s*(第[一二三四五六七八九十\d]+|表\s*\d+|Table\s*\d+)', line):
                indicators += 2

        return indicators

    def _detect_merged_cells(self, text_lines: List[str]) -> bool:
        """
        检测合并单元格（启发式）
        """
        # 查找跨越多列的文本模式
        for line in text_lines:
            # 检查是否有多列对齐但内容跨越
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 3:
                    # 检查是否有空单元格后跟跨越内容
                    empty_cells = sum(1 for part in parts if not part.strip())
                    if empty_cells >= 2:
                        return True

        return False

    def _detect_formulas(self, text_lines: List[str]) -> bool:
        """
        检测公式
        """
        formula_indicators = ['∑', '∫', '√', '±', '×', '÷', '∈', '∋', '=', '≠', '≤', '≥']

        formula_lines = 0
        for line in text_lines:
            if any(indicator in line for indicator in formula_indicators):
                formula_lines += 1

        # 如果公式行占比超过5%，认为有公式
        return formula_lines / max(len(text_lines), 1) > 0.05

    def _detect_headers_footers(self, text_lines: List[str], page_rect) -> bool:
        """
        检测页眉页脚
        """
        if len(text_lines) < 3:
            return False

        # 检查第一行和最后一行的特征
        first_line = text_lines[0].strip()
        last_line = text_lines[-1].strip()

        # 页眉特征：页码、日期、标题等
        header_indicators = ['页', 'Page', '第', '日期', '时间']
        footer_indicators = ['页', 'Page', '第', '版权', '©']

        has_header = any(indicator in first_line for indicator in header_indicators)
        has_footer = any(indicator in last_line for indicator in footer_indicators)

        return has_header or has_footer

    def _determine_complexity(self, features: Dict[str, Any]) -> Tuple[DocumentComplexity, List[str]]:
        """
        确定文档复杂度
        """
        reasoning = []

        # 高复杂度条件
        if (features.get("has_merged_cells", False) or
            features.get("table_indicators", 0) >= 10 or
            features.get("avg_image_ratio", 0) > 0.3 or
            features.get("has_formulas", False)):
            reasoning.append("检测到合并单元格、复杂表格或高密度图片")
            return DocumentComplexity.HIGH_COMPLEXITY, reasoning

        # 复杂财务文档条件
        if (features.get("table_indicators", 0) >= 5 or
            features.get("has_headers_footers", False)):
            reasoning.append("检测到多个表格和页眉页脚，疑似财务文档")
            return DocumentComplexity.COMPLEX_FINANCIAL, reasoning

        # 标准布局条件
        if (features.get("has_tables", False) or
            features.get("has_images", False) or
            features.get("avg_image_ratio", 0) > 0.05):
            reasoning.append("检测到表格或图片，需要结构化解析")
            return DocumentComplexity.STANDARD_LAYOUT, reasoning

        # 简单文本条件
        reasoning.append("主要是纯文本内容，无复杂布局")
        return DocumentComplexity.SIMPLE_TEXT, reasoning

    def _recommend_tier(self, complexity: DocumentComplexity,
                       features: Dict[str, Any]) -> Tuple[ParserTier, float]:
        """
        根据复杂度推荐解析层级
        """
        if complexity == DocumentComplexity.HIGH_COMPLEXITY:
            return ParserTier.TIER_3, 0.95

        elif complexity == DocumentComplexity.COMPLEX_FINANCIAL:
            return ParserTier.TIER_3, 0.90

        elif complexity == DocumentComplexity.STANDARD_LAYOUT:
            return ParserTier.TIER_2, 0.85

        else:  # SIMPLE_TEXT
            return ParserTier.TIER_1, 0.95


class TieredDocumentParser(BaseParser):
    """
    三层梯度解析引擎总控类

    智能路由决策大脑：
    1. 使用DocumentLayoutAnalyzer快速分析文档复杂度
    2. 根据分析结果路由到最合适的Parser
    3. 集成CostEstimator进行成本控制
    4. 支持强制指定层级和降级重试
    """

    tier = ParserTier.TIER_1  # 默认，但会动态路由
    name = "tiered_document_parser"
    version = "2.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # 初始化各个层级的解析器
        self.parsers = {
            ParserTier.TIER_1: NativeTextParser(self.config.get('tier1_config', {})),
            ParserTier.TIER_2: StandardOCRParser(self.config.get('tier2_config', {})),
            ParserTier.TIER_3: VisionSemanticParser(self.config.get('tier3_config', {}))
        }

        # 初始化分析器和成本估算器
        self.layout_analyzer = DocumentLayoutAnalyzer(self.config.get('analyzer_config', {}))
        self.cost_estimator = CostEstimator(self.config.get('cost_config', {}))

        # 初始化标准化器
        self.standardizer = MarkdownStandardizer(self.config.get('standardizer_config', {}))

        # 路由配置
        self.force_tier = self.config.get('force_tier')  # 强制指定层级
        self.enable_auto_routing = self.config.get('enable_auto_routing', True)
        self.enable_cost_warnings = self.config.get('enable_cost_warnings', True)
        self.fallback_tiers = self.config.get('fallback_tiers', True)  # 是否允许降级

    def _check_dependencies(self):
        """检查所有解析器的依赖"""
        available_tiers = []

        for tier, parser in self.parsers.items():
            if parser.is_available():
                available_tiers.append(tier.value)
            else:
                logger.warning(f"{tier.value} 解析器依赖不满足")

        if not available_tiers:
            raise ImportError("没有可用的解析器")

        logger.info(f"TieredDocumentParser初始化完成，可用层级: {available_tiers}")

    def _get_supported_formats(self) -> List[str]:
        """获取支持的文件格式"""
        return ['pdf']

    def _get_performance_profile(self) -> Dict[str, Any]:
        """获取性能配置（动态路由的平均值）"""
        return {
            "average_latency_ms": 5000,  # 5秒平均延迟（动态）
            "throughput_docs_per_minute": 10,  # 10文档/分钟
            "memory_usage_mb": 512,  # 512MB内存
            "cpu_cores_required": 2  # 2核心（分析+解析）
        }

    def _get_quality_profile(self) -> Dict[str, Any]:
        """获取质量配置（动态路由）"""
        return {
            "expected_accuracy": 0.90,  # 90%平均准确率
            "handles_complex_layouts": True,  # 通过路由处理
            "handles_multilingual": True,  # 各层级都支持
            "handles_tables": True,  # TIER_2和TIER_3支持
            "handles_images": True  # TIER_2和TIER_3支持
        }

    def parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        智能路由解析方法

        Args:
            file_path: PDF文件路径
            **kwargs: 额外参数
                - force_tier: 强制指定层级 (TIER_1, TIER_2, TIER_3)
                - document_type: 文档类型 ('financial', 'general')
                - skip_cost_check: 跳过成本检查
                - enable_fallback: 允许降级重试

        Returns:
            ParsedDocument: 解析结果
        """
        start_time = time.time()

        try:
            # 预检文件
            self._validate_file(file_path)

            # 确定目标层级
            target_tier = self._determine_target_tier(file_path, **kwargs)

            # 成本预估和警告
            if self.enable_cost_warnings and not kwargs.get('skip_cost_check', False):
                cost_estimation = self._check_cost_threshold(file_path, target_tier)
                if cost_estimation.warnings:
                    logger.warning(f"成本警告: {cost_estimation.warnings}")

            # 执行解析
            parsed_doc = self._execute_parsing(file_path, target_tier, **kwargs)

            # 应用Markdown标准化（胶水层）
            standardized_doc = self.standardizer.standardize(parsed_doc)

            # 计算使用指标
            processing_time = time.time() - start_time
            usage_metrics = {
                "processing_time_seconds": round(processing_time, 3),
                "routing_time_seconds": round(parsed_doc.usage_metrics.get("routing_time_seconds", 0), 3),
                "final_tier": parsed_doc.parser_tier.value,
                "auto_routed": not self.force_tier and self.enable_auto_routing,
                "fallback_used": parsed_doc.usage_metrics.get("fallback_used", False),
                "total_tokens_estimated": parsed_doc.usage_metrics.get("total_tokens_estimated", 0),
                "tier_used": parsed_doc.parser_tier.value,
                "standardization_applied": standardized_doc.raw_metadata.get("standardization_applied", False)
            }

            # 添加成本信息
            if 'cost_estimation' in locals():
                usage_metrics.update({
                    "estimated_cost": cost_estimation.estimated_cost,
                    "cost_warnings": cost_estimation.warnings
                })

            # 更新标准化后的文档元数据和使用指标
            standardized_doc.raw_metadata.update({
                "file_path": file_path,
                "routing_analysis": parsed_doc.raw_metadata.get("routing_analysis", {}),
                "target_tier": target_tier.value,
                "final_tier": parsed_doc.parser_tier.value
            })
            standardized_doc.usage_metrics = usage_metrics

            # 更新性能指标
            self._update_metrics(True, processing_time)

            logger.info(f"TieredDocumentParser completed: {file_path}, "
                      f"routed to {parsed_doc.parser_tier.value}, "
                      f"standardized: {standardized_doc.raw_metadata.get('standardization_applied', False)}, "
                      f"{processing_time:.2f}s")

            return standardized_doc

        except Exception as e:
            processing_time = time.time() - start_time
            self._update_metrics(False, processing_time)
            raise ParserError(f"TieredDocumentParser failed: {str(e)}")

    async def async_parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        异步智能路由解析
        """
        # 分析阶段是CPU密集型，使用线程池
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def sync_parse():
            return self.parse(file_path, **kwargs)

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return await loop.run_in_executor(executor, sync_parse)

    def _determine_target_tier(self, file_path: str, **kwargs) -> ParserTier:
        """
        确定目标解析层级
        """
        # 强制指定层级
        if self.force_tier:
            return self.force_tier

        if not self.enable_auto_routing:
            return ParserTier.TIER_2  # 默认中等层级

        # 分析文档确定层级
        routing_start = time.time()
        analysis = self.layout_analyzer.analyze_document(file_path)
        routing_time = time.time() - routing_start

        logger.info(f"文档分析结果: 复杂度={analysis.complexity.value}, "
                  f"推荐层级={analysis.recommended_tier.value}, "
                  f"置信度={analysis.confidence:.2f}")

        # 存储分析结果用于后续
        self._last_analysis = {
            "analysis": analysis,
            "routing_time": routing_time
        }

        return analysis.recommended_tier

    def _check_cost_threshold(self, file_path: str, tier: ParserTier) -> CostEstimation:
        """
        检查成本阈值
        """
        # 获取布局特征（复用分析结果）
        if hasattr(self, '_last_analysis'):
            layout_features = self._last_analysis["analysis"].features
        else:
            # 如果没有分析结果，进行快速分析
            analysis = self.layout_analyzer.analyze_document(file_path)
            layout_features = analysis.features

        return self.cost_estimator.estimate_cost(file_path, tier, layout_features)

    def _execute_parsing(self, file_path: str, target_tier: ParserTier, **kwargs) -> Dict[str, Any]:
        """
        执行解析，支持降级重试
        """
        enable_fallback = kwargs.get('enable_fallback', self.fallback_tiers)

        # 尝试目标层级
        try:
            parser = self.parsers[target_tier]
            logger.info(f"尝试使用 {target_tier.value} 解析文档")

            result = parser.parse(file_path, **kwargs)

            return {
                "content": result.content,
                "tier_used": target_tier.value,
                "page_count": result.page_count,
                "layout_profile": result.layout_profile,
                "content_types": result.content_types,
                "confidence": result.confidence_score,
                "total_tokens": result.usage_metrics.get("total_tokens_estimated", 0),
                "fallback_used": False,
                "analysis": getattr(self, '_last_analysis', {}).get("analysis", {}),
                "routing_time": getattr(self, '_last_analysis', {}).get("routing_time", 0)
            }

        except Exception as e:
            logger.warning(f"{target_tier.value} 解析失败: {e}")

            if not enable_fallback:
                raise

            # 尝试降级
            return self._fallback_parsing(file_path, target_tier, str(e), **kwargs)

    def _fallback_parsing(self, file_path: str, failed_tier: ParserTier,
                         error_msg: str, **kwargs) -> Dict[str, Any]:
        """
        降级解析策略
        """
        fallback_order = {
            ParserTier.TIER_3: [ParserTier.TIER_2, ParserTier.TIER_1],
            ParserTier.TIER_2: [ParserTier.TIER_1],
            ParserTier.TIER_1: []  # TIER_1失败则无降级选项
        }

        for fallback_tier in fallback_order.get(failed_tier, []):
            try:
                logger.info(f"降级到 {fallback_tier.value} 重新尝试")

                parser = self.parsers[fallback_tier]
                result = parser.parse(file_path, **kwargs)

                logger.info(f"降级成功: {failed_tier.value} -> {fallback_tier.value}")

                return {
                    "content": result.content,
                    "tier_used": fallback_tier.value,
                    "page_count": result.page_count,
                    "layout_profile": result.layout_profile,
                    "content_types": result.content_types,
                    "confidence": result.confidence_score * 0.9,  # 降级略微降低置信度
                    "total_tokens": result.usage_metrics.get("total_tokens_estimated", 0),
                    "fallback_used": True,
                    "fallback_reason": f"{failed_tier.value} failed: {error_msg}",
                    "analysis": getattr(self, '_last_analysis', {}).get("analysis", {}),
                    "routing_time": getattr(self, '_last_analysis', {}).get("routing_time", 0)
                }

            except Exception as fallback_error:
                logger.warning(f"降级到 {fallback_tier.value} 也失败: {fallback_error}")
                continue

        # 所有降级都失败
        raise FatalError(f"所有解析层级都失败，最后一次错误: {error_msg}")

    def _validate_file(self, file_path: str):
        """验证文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if not file_path.lower().endswith('.pdf'):
            raise ValueError(f"不支持的文件格式: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > 500 * 1024 * 1024:  # 500MB
            raise ValueError(f"文件过大: {file_size} bytes")

    def get_available_tiers(self) -> List[str]:
        """获取可用层级列表"""
        return [tier.value for tier, parser in self.parsers.items() if parser.is_available()]

    def get_parser_capabilities(self) -> Dict[str, Any]:
        """获取所有解析器的能力信息"""
        capabilities = {}
        for tier, parser in self.parsers.items():
            capabilities[tier.value] = parser.get_capabilities()
        return capabilities