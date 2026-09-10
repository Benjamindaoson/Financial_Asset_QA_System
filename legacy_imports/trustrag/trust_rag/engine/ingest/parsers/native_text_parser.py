"""
NativeTextParser (Tier 1) - 轻量级文本解析器

基于 PyMuPDF 和 Marker 的高性能文本提取：
- 直接提取文本流，通过正则或轻量级模型还原 Markdown
- 检测图片页占比 > 10% 时抛出 InadequateTierError
- 适用于80%的标准文档场景
"""
import os
import re
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
import numpy as np

from .base_parser import BaseParser, ParserTier, ParsedDocument, InadequateTierError, RetryableError

logger = logging.getLogger(__name__)


class NativeTextParser(BaseParser):
    """
    Tier 1: 轻量级文本解析器

    核心逻辑：
    1. 使用PyMuPDF直接提取文本流
    2. 通过正则表达式和轻量级规则还原Markdown格式
    3. 检测图片占比，超过阈值建议升级到更高层级
    4. 性能优化：单进程处理，内存友好
    """

    tier = ParserTier.TIER_1
    name = "native_text_parser"
    version = "2.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # 配置参数
        self.image_threshold = self.config.get('image_threshold', 0.1)  # 图片占比阈值
        self.max_pages = self.config.get('max_pages', 100)  # 最大页面数
        self.markdown_formatting = self.config.get('markdown_formatting', True)

        # 性能监控
        self._memory_usage = 0

    def _check_dependencies(self):
        """检查依赖项"""
        try:
            import fitz
            from PIL import Image
        except ImportError as e:
            raise ImportError(f"NativeTextParser dependencies missing: {e}")

    def _get_supported_formats(self) -> List[str]:
        """获取支持的文件格式"""
        return ['pdf', 'txt', 'md']

    def _get_performance_profile(self) -> Dict[str, Any]:
        """获取性能配置"""
        return {
            "average_latency_ms": 500,  # 0.5秒平均延迟
            "throughput_docs_per_minute": 30,  # 30文档/分钟
            "memory_usage_mb": 128,  # 128MB内存使用
            "cpu_cores_required": 1  # 单核心
        }

    def _get_quality_profile(self) -> Dict[str, Any]:
        """获取质量配置"""
        return {
            "expected_accuracy": 0.90,  # 90%准确率
            "handles_complex_layouts": False,  # 不处理复杂布局
            "handles_multilingual": True,  # 支持多语言（UTF-8）
            "handles_tables": False,  # 不处理复杂表格
            "handles_images": False  # 不处理图片
        }

    def parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        同步解析方法

        Args:
            file_path: PDF文件路径
            **kwargs: 额外参数

        Returns:
            ParsedDocument: 解析结果
        """
        start_time = time.time()

        try:
            # 预检文件
            self._validate_file(file_path)

            # 打开PDF文档
            doc = fitz.open(file_path)

            try:
                # 分析文档结构
                doc_profile = self._analyze_document_profile(doc)

                # 检查是否适合当前层级
                self._check_tier_adequacy(doc_profile)

                # 提取文本内容
                content, layout_info = self._extract_content(doc)

                # 格式化为Markdown（如果启用）
                if self.markdown_formatting:
                    content = self._format_as_markdown(content, layout_info)

                # 计算使用指标
                processing_time = time.time() - start_time
                usage_metrics = {
                    "processing_time_seconds": round(processing_time, 3),
                    "pages_processed": len(doc),
                    "total_tokens_estimated": len(content.split()) * 1.3,  # 粗略估算
                    "memory_peak_mb": self._memory_usage,
                    "tier_used": self.tier.value
                }

                # 创建解析结果
                parsed_doc = self._create_parsed_document(
                    content=content,
                    raw_metadata={
                        "file_path": file_path,
                        "file_size": os.path.getsize(file_path),
                        "page_count": len(doc)
                    },
                    layout_profile=doc_profile,
                    usage_metrics=usage_metrics,
                    page_count=len(doc),
                    content_types=self._detect_content_types(layout_info),
                    confidence_score=self._calculate_confidence(doc_profile)
                )

                # 更新性能指标
                self._update_metrics(True, processing_time)

                logger.info(f"NativeTextParser completed: {len(doc)} pages, "
                          f"{processing_time:.2f}s, confidence: {parsed_doc.confidence_score:.2f}")

                return parsed_doc

            finally:
                doc.close()

        except InadequateTierError:
            # 重新抛出层级不足错误
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            self._update_metrics(False, processing_time)
            raise RetryableError(
                f"NativeTextParser failed: {str(e)}",
                details={"file_path": file_path, "error_type": type(e).__name__}
            )

    async def async_parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        异步解析方法（Tier 1通常很快，直接调用同步方法）
        """
        # 对于Tier 1，异步处理意义不大，直接调用同步方法
        return self.parse(file_path, **kwargs)

    def _validate_file(self, file_path: str):
        """验证文件有效性"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if not file_path.lower().endswith('.pdf'):
            raise ValueError(f"不支持的文件格式: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:  # 50MB
            raise ValueError(f"文件过大: {file_size} bytes")

    def _analyze_document_profile(self, doc) -> Dict[str, Any]:
        """
        分析文档结构特征

        Returns:
            Dict: 文档特征分析结果
        """
        profile = {
            "total_pages": len(doc),
            "pages_with_images": 0,
            "pages_with_text": 0,
            "total_image_area": 0,
            "total_page_area": 0,
            "has_tables": False,
            "has_complex_layout": False,
            "text_density_avg": 0.0,
            "language_detected": "unknown"
        }

        text_lengths = []

        for page_num in range(min(len(doc), 10)):  # 只分析前10页作为样本
            page = doc.load_page(page_num)

            # 分析文本
            text = page.get_text()
            text_length = len(text.strip())
            text_lengths.append(text_length)

            if text_length > 100:  # 有意义文本
                profile["pages_with_text"] += 1

            # 分析图片
            image_list = page.get_images(full=True)
            if image_list:
                profile["pages_with_images"] += 1

                # 估算图片面积占比
                page_rect = page.rect
                page_area = page_rect.width * page_rect.height

                for img in image_list:
                    try:
                        # 获取图片边界框
                        img_rect = page.get_image_bbox(img)
                        if img_rect:
                            img_area = (img_rect.x1 - img_rect.x0) * (img_rect.y1 - img_rect.y0)
                            profile["total_image_area"] += img_area
                    except:
                        pass

                profile["total_page_area"] += page_area

            # 简单的表格检测（通过文本模式）
            if self._detect_table_patterns(text):
                profile["has_tables"] = True

        # 计算平均指标
        if text_lengths:
            profile["text_density_avg"] = sum(text_lengths) / len(text_lengths)

        # 计算图片占比
        if profile["total_page_area"] > 0:
            profile["image_area_ratio"] = profile["total_image_area"] / profile["total_page_area"]
        else:
            profile["image_area_ratio"] = 0.0

        return profile

    def _check_tier_adequacy(self, profile: Dict[str, Any]):
        """
        检查文档是否适合当前层级处理

        如果不适合，抛出InadequateTierError建议升级
        """
        reasons = []

        # 检查图片占比
        image_ratio = profile.get("image_area_ratio", 0)
        if image_ratio > self.image_threshold:
            reasons.append(".1%")

        # 检查页面数量
        if profile["total_pages"] > self.max_pages:
            reasons.append(f"页面数量过多: {profile['total_pages']} > {self.max_pages}")

        # 检查复杂特征
        if profile.get("has_tables", False):
            reasons.append("检测到表格结构")

        if profile.get("has_complex_layout", False):
            reasons.append("检测到复杂布局")

        # 如果有任何不适合的特征，建议升级
        if reasons:
            raise InadequateTierError(
                current_tier=self.tier,
                recommended_tier=ParserTier.TIER_2,
                reason="; ".join(reasons),
                details={
                    "image_ratio": image_ratio,
                    "page_count": profile["total_pages"],
                    "has_tables": profile.get("has_tables", False)
                }
            )

    def _extract_content(self, doc) -> Tuple[str, Dict[str, Any]]:
        """
        提取文档文本内容

        Returns:
            Tuple[str, Dict]: (内容, 布局信息)
        """
        content_parts = []
        layout_info = {
            "pages": [],
            "total_chars": 0,
            "sections": []
        }

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            # 提取文本
            text = page.get_text()

            if text.strip():
                # 添加页面分隔符
                if page_num > 0:
                    content_parts.append(f"\n\n--- Page {page_num + 1} ---\n\n")

                content_parts.append(text)

                # 收集布局信息
                layout_info["pages"].append({
                    "page_num": page_num + 1,
                    "text_length": len(text),
                    "has_images": len(page.get_images(full=True)) > 0
                })

                layout_info["total_chars"] += len(text)

        full_content = "".join(content_parts)
        return full_content, layout_info

    def _format_as_markdown(self, content: str, layout_info: Dict[str, Any]) -> str:
        """
        将纯文本格式化为Markdown

        简单的启发式格式化：
        - 识别标题（短行、大写等）
        - 识别列表
        - 保持段落结构
        """
        lines = content.split('\n')
        formatted_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append("")
                continue

            # 识别标题（短行、大写、数字开头等）
            if self._is_likely_header(line):
                formatted_lines.append(f"## {line}")
            else:
                formatted_lines.append(line)

        # 合并连续空行
        result = []
        prev_empty = False

        for line in formatted_lines:
            is_empty = line.strip() == ""
            if is_empty and prev_empty:
                continue
            result.append(line)
            prev_empty = is_empty

        return "\n".join(result)

    def _is_likely_header(self, line: str) -> bool:
        """启发式判断是否为标题"""
        if len(line) > 100:  # 太长了
            return False

        if len(line) < 5:  # 太短了
            return False

        # 检查是否全大写或首字母大写
        if line.isupper() or (len(line) > 10 and sum(1 for c in line if c.isupper()) / len(line) > 0.3):
            return True

        # 检查是否以数字开头（可能是有序列表）
        if re.match(r'^\d+\.', line.strip()):
            return True

        return False

    def _detect_table_patterns(self, text: str) -> bool:
        """检测表格模式（简单启发式）"""
        # 检查是否有多列对齐的文本
        lines = text.split('\n')
        table_indicators = 0

        for line in lines:
            # 检查制表符或多个连续空格
            if '\t' in line or '  ' in line:
                table_indicators += 1

            # 检查数字列
            numbers = re.findall(r'\d+\.?\d*', line)
            if len(numbers) >= 3:  # 一行有3个以上数字
                table_indicators += 1

        return table_indicators >= 2

    def _detect_content_types(self, layout_info: Dict[str, Any]) -> List[str]:
        """检测内容类型"""
        types = ["text"]

        # 检查是否有图片页面
        image_pages = sum(1 for p in layout_info.get("pages", []) if p.get("has_images", False))
        if image_pages > 0:
            types.append("images")

        return types

    def _calculate_confidence(self, profile: Dict[str, Any]) -> float:
        """计算解析置信度"""
        confidence = 0.9  # 基础置信度

        # 根据文档特征调整
        if profile.get("image_area_ratio", 0) > 0.05:
            confidence -= 0.1  # 图片影响准确性

        if profile.get("has_tables", False):
            confidence -= 0.2  # 表格处理不完美

        if profile["pages_with_text"] / max(profile["total_pages"], 1) < 0.5:
            confidence -= 0.1  # 文本页面比例低

        return max(0.1, min(1.0, confidence))
