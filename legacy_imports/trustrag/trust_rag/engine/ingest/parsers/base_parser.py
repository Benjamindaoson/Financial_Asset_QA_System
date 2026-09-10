"""
TrustRAG 2.0 三层梯度解析引擎 - 基础架构与策略模式定义

核心设计：
1. Strategy Pattern：BaseParser抽象基类 + parse()/async_parse()
2. 数据契约：ParsedDocument Pydantic模型
3. 错误处理：ParserError异常体系
4. 审计追踪：@trace_parser装饰器
"""
import abc
import asyncio
import time
import logging
import uuid
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from enum import Enum

from pydantic import BaseModel, Field, validator
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)


class ParserTier(Enum):
    """解析器层级枚举"""
    TIER_1 = "tier_1"  # 轻量级文本解析 (PyMuPDF + Marker)
    TIER_2 = "tier_2"  # 标准OCR解析 (MinerU/PaddleOCR)
    TIER_3 = "tier_3"  # VLM语义解析 (Qwen2-VL)


class ParsedDocument(BaseModel):
    """
    解析后的文档数据契约

    严格的数据模型，确保所有解析器输出的一致性
    """
    # 核心内容
    content: str = Field(..., description="Markdown格式的解析内容")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="原始元数据")

    # 解析信息
    parser_tier: ParserTier = Field(..., description="使用的解析器层级")
    layout_profile: Dict[str, Any] = Field(default_factory=dict, description="布局分析结果")

    # 使用指标 (金融审计必需)
    usage_metrics: Dict[str, Any] = Field(default_factory=dict, description="耗时/Token等使用指标")

    # 审计追踪
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="全链路TraceID")
    parsed_at: datetime = Field(default_factory=datetime.now, description="解析完成时间")
    parser_version: str = Field(default="2.0.0", description="解析器版本")

    # 质量评估
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="解析置信度")
    is_degraded: bool = Field(default=False, description="是否降级处理")
    degradation_reason: Optional[str] = Field(default=None, description="降级原因")

    # 内容分析
    page_count: int = Field(default=1, ge=1, description="页面数量")
    content_types: List[str] = Field(default_factory=list, description="内容类型列表")
    language_detected: str = Field(default="unknown", description="检测到的语言")

    class Config:
        """Pydantic配置"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator('content')
    def validate_content(cls, v):
        """验证内容不为空"""
        if not v or not v.strip():
            raise ValueError("解析内容不能为空")
        return v

    @validator('confidence_score')
    def validate_confidence(cls, v):
        """验证置信度范围"""
        if not 0.0 <= v <= 1.0:
            raise ValueError("置信度必须在0.0-1.0之间")
        return v

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return self.dict()

    def get_audit_summary(self) -> Dict[str, Any]:
        """获取审计摘要"""
        return {
            "trace_id": self.trace_id,
            "parser_tier": self.parser_tier.value,
            "parsed_at": self.parsed_at.isoformat(),
            "confidence_score": self.confidence_score,
            "is_degraded": self.is_degraded,
            "page_count": self.page_count,
            "usage_metrics": self.usage_metrics
        }


class ParserError(Exception):
    """解析器基础异常类"""
    def __init__(self, message: str, trace_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.trace_id = trace_id or str(uuid.uuid4())
        self.details = details or {}
        self.timestamp = datetime.now()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式用于日志"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        }


class RetryableError(ParserError):
    """可重试错误"""
    def __init__(self, message: str, retry_after: int = 60, max_retries: int = 3, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after  # 重试间隔(秒)
        self.max_retries = max_retries  # 最大重试次数


class FatalError(ParserError):
    """致命错误，不可重试"""
    pass


class InadequateTierError(ParserError):
    """层级不足错误，建议升级到更高层级"""
    def __init__(self, current_tier: ParserTier, recommended_tier: ParserTier, reason: str, **kwargs):
        message = f"当前层级 {current_tier.value} 不足以处理文档，建议升级到 {recommended_tier.value}: {reason}"
        super().__init__(message, **kwargs)
        self.current_tier = current_tier
        self.recommended_tier = recommended_tier
        self.reason = reason


def trace_parser(operation: str = "parse"):
    """
    解析器审计追踪装饰器

    自动记录解析操作的全链路TraceID，确保金融审计合规性
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # 获取或生成TraceID
            trace_id = getattr(self, '_current_trace_id', None)
            if not trace_id:
                trace_id = str(uuid.uuid4())
                self._current_trace_id = trace_id

            # OpenTelemetry追踪
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(
                f"parser.{operation}",
                kind=trace.SpanKind.INTERNAL
            ) as span:
                # 设置追踪属性
                span.set_attribute("parser.class", self.__class__.__name__)
                span.set_attribute("parser.tier", getattr(self, 'tier', ParserTier.TIER_1).value)
                span.set_attribute("trace.id", trace_id)
                span.set_attribute("operation", operation)

                start_time = time.time()
                try:
                    # 执行解析
                    result = func(self, *args, **kwargs)

                    # 记录成功指标
                    duration = time.time() - start_time
                    span.set_attribute("duration_ms", duration * 1000)
                    span.set_attribute("success", True)

                    # 审计日志
                    logger.info(f"Parser operation completed: {self.__class__.__name__}.{operation}",
                              extra={
                                  "trace_id": trace_id,
                                  "duration_ms": round(duration * 1000, 2),
                                  "parser_tier": getattr(self, 'tier', ParserTier.TIER_1).value,
                                  "success": True
                              })

                    span.set_status(Status(StatusCode.OK))
                    return result

                except ParserError as e:
                    # 记录解析错误
                    duration = time.time() - start_time
                    span.set_attribute("duration_ms", duration * 1000)
                    span.set_attribute("success", False)
                    span.set_attribute("error_type", e.__class__.__name__)
                    span.record_exception(e)

                    # 审计日志
                    logger.warning(f"Parser operation failed: {self.__class__.__name__}.{operation} - {e.message}",
                                 extra={
                                     "trace_id": trace_id or e.trace_id,
                                     "duration_ms": round(duration * 1000, 2),
                                     "error_type": e.__class__.__name__,
                                     "success": False
                                 })

                    span.set_status(Status(StatusCode.ERROR, e.message))
                    raise

                except Exception as e:
                    # 记录未知错误
                    duration = time.time() - start_time
                    span.set_attribute("duration_ms", duration * 1000)
                    span.set_attribute("success", False)
                    span.set_attribute("error_type", "UnknownError")
                    span.record_exception(e)

                    # 转换为ParserError
                    parser_error = ParserError(
                        f"Unexpected error in {self.__class__.__name__}.{operation}: {str(e)}",
                        trace_id=trace_id
                    )

                    logger.error(f"Parser operation unexpected error: {self.__class__.__name__}.{operation}",
                               extra={
                                   "trace_id": trace_id,
                                   "duration_ms": round(duration * 1000, 2),
                                   "error": str(e),
                                   "success": False
                               })

                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise parser_error from e

        return wrapper
    return decorator


class BaseParser(abc.ABC):
    """
    解析器抽象基类 - Strategy Pattern实现

    所有解析器必须继承此类，实现统一的接口
    """

    # 类属性
    tier: ParserTier = ParserTier.TIER_1
    name: str = "base_parser"
    version: str = "2.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._current_trace_id = None

        # 性能监控
        self.metrics = {
            "total_parses": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "average_duration": 0.0,
            "total_duration": 0.0
        }

    @abc.abstractmethod
    @trace_parser("parse")
    def parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        同步解析方法

        Args:
            file_path: 文件路径
            **kwargs: 额外参数

        Returns:
            ParsedDocument: 解析结果

        Raises:
            ParserError: 解析失败时抛出
        """
        pass

    @abc.abstractmethod
    @trace_parser("async_parse")
    async def async_parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        异步解析方法

        Args:
            file_path: 文件路径
            **kwargs: 额外参数

        Returns:
            ParsedDocument: 解析结果

        Raises:
            ParserError: 解析失败时抛出
        """
        pass

    def is_available(self) -> bool:
        """
        检查解析器是否可用（依赖项是否满足）

        Returns:
            bool: 是否可用
        """
        try:
            # 尝试导入必要的依赖
            self._check_dependencies()
            return True
        except ImportError:
            return False

    @abc.abstractmethod
    def _check_dependencies(self):
        """检查依赖项"""
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        """
        获取解析器能力描述

        Returns:
            Dict: 能力信息
        """
        return {
            "tier": self.tier.value,
            "name": self.name,
            "version": self.version,
            "supported_formats": self._get_supported_formats(),
            "performance_profile": self._get_performance_profile(),
            "quality_profile": self._get_quality_profile()
        }

    @abc.abstractmethod
    def _get_supported_formats(self) -> List[str]:
        """获取支持的文件格式"""
        pass

    def _get_performance_profile(self) -> Dict[str, Any]:
        """获取性能配置"""
        return {
            "average_latency_ms": 1000,  # 默认1秒
            "throughput_docs_per_minute": 10,  # 默认10文档/分钟
            "memory_usage_mb": 256,  # 默认256MB
            "cpu_cores_required": 1  # 默认1核心
        }

    def _get_quality_profile(self) -> Dict[str, Any]:
        """获取质量配置"""
        return {
            "expected_accuracy": 0.95,  # 期望准确率
            "handles_complex_layouts": False,  # 是否处理复杂布局
            "handles_multilingual": False,  # 是否支持多语言
            "handles_tables": False,  # 是否处理表格
            "handles_images": False  # 是否处理图片
        }

    def get_metrics(self) -> Dict[str, Any]:
        """获取解析器性能指标"""
        metrics = self.metrics.copy()
        if metrics["total_parses"] > 0:
            metrics["success_rate"] = metrics["successful_parses"] / metrics["total_parses"]
        else:
            metrics["success_rate"] = 0.0

        if metrics["successful_parses"] > 0:
            metrics["average_duration"] = metrics["total_duration"] / metrics["successful_parses"]
        else:
            metrics["average_duration"] = 0.0

        return metrics

    def _update_metrics(self, success: bool, duration: float):
        """更新性能指标"""
        self.metrics["total_parses"] += 1

        if success:
            self.metrics["successful_parses"] += 1
            self.metrics["total_duration"] += duration
        else:
            self.metrics["failed_parses"] += 1

    def _create_parsed_document(
        self,
        content: str,
        raw_metadata: Dict[str, Any],
        layout_profile: Dict[str, Any],
        usage_metrics: Dict[str, Any],
        **kwargs
    ) -> ParsedDocument:
        """创建标准化的ParsedDocument"""
        return ParsedDocument(
            content=content,
            raw_metadata=raw_metadata,
            parser_tier=self.tier,
            layout_profile=layout_profile,
            usage_metrics=usage_metrics,
            parser_version=self.version,
            **kwargs
        )
