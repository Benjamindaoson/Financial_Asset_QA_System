"""
多模型管理器 - 支持Claude、DeepSeek及未来更多模型
Multi-Model Manager - Support for Claude, DeepSeek, and future models
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
from enum import Enum
import anthropic
from openai import OpenAI
from app.config import settings
import json


class ModelProvider(str, Enum):
    """模型提供商"""
    ANTHROPIC = "anthropic"  # Claude
    OPENAI = "openai"  # GPT
    DEEPSEEK = "deepseek"  # DeepSeek
    QWEN = "qwen"  # 通义千问
    ZHIPU = "zhipu"  # 智谱AI
    BAICHUAN = "baichuan"  # 百川
    MINIMAX = "minimax"  # MiniMax


class QueryComplexity(str, Enum):
    """查询复杂度"""
    SIMPLE = "simple"  # 简单查询（价格、基础信息）
    MEDIUM = "medium"  # 中等查询（历史数据、简单分析）
    COMPLEX = "complex"  # 复杂查询（深度分析、多维对比）


class ModelConfig:
    """模型配置"""
    def __init__(
        self,
        provider: ModelProvider,
        model_name: str,
        api_key: str,
        base_url: Optional[str] = None,
        supports_tool_use: bool = True,
        supports_streaming: bool = True,
        cost_per_1m_input: float = 0,
        cost_per_1m_output: float = 0,
        max_tokens: int = 4096,
        priority: int = 0  # 优先级，数字越大优先级越高
    ):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.supports_tool_use = supports_tool_use
        self.supports_streaming = supports_streaming
        self.cost_per_1m_input = cost_per_1m_input
        self.cost_per_1m_output = cost_per_1m_output
        self.max_tokens = max_tokens
        self.priority = priority


class MultiModelManager:
    """
    多模型管理器

    功能：
    1. 管理多个模型配置
    2. 根据查询复杂度智能路由
    3. 支持降级和故障转移
    4. 统计成本和使用情况
    """

    def __init__(self):
        self.models: Dict[str, ModelConfig] = {}
        self.routing_rules: Dict[QueryComplexity, List[str]] = {
            QueryComplexity.SIMPLE: [],
            QueryComplexity.MEDIUM: [],
            QueryComplexity.COMPLEX: []
        }
        self.usage_stats: Dict[str, Dict[str, Any]] = {}

        # 加载配置
        self._load_models()
        self._setup_routing()

    def _load_models(self):
        """加载模型配置"""

        # Claude (Anthropic) - 从环境变量加载
        if settings.ANTHROPIC_API_KEY:
            self.add_model(
                name="claude-opus",
                config=ModelConfig(
                    provider=ModelProvider.ANTHROPIC,
                    model_name=settings.CLAUDE_MODEL,
                    api_key=settings.ANTHROPIC_API_KEY,
                    base_url=settings.ANTHROPIC_BASE_URL,
                    supports_tool_use=True,
                    supports_streaming=True,
                    cost_per_1m_input=15.0,  # $15/M tokens
                    cost_per_1m_output=75.0,  # $75/M tokens
                    priority=10  # 高优先级
                )
            )

        # DeepSeek - 如果配置了
        deepseek_key = getattr(settings, 'DEEPSEEK_API_KEY', None)
        if deepseek_key:
            self.add_model(
                name="deepseek-chat",
                config=ModelConfig(
                    provider=ModelProvider.DEEPSEEK,
                    model_name="deepseek-chat",
                    api_key=deepseek_key,
                    base_url="https://api.deepseek.com",
                    supports_tool_use=True,  # 使用OpenAI格式
                    supports_streaming=True,
                    cost_per_1m_input=0.27,  # $0.27/M tokens
                    cost_per_1m_output=1.1,  # $1.1/M tokens
                    priority=8  # 中高优先级
                )
            )

        # 可以继续添加更多模型...
        # OpenAI GPT
        openai_key = getattr(settings, 'OPENAI_API_KEY', None)
        if openai_key:
            self.add_model(
                name="gpt-4",
                config=ModelConfig(
                    provider=ModelProvider.OPENAI,
                    model_name="gpt-4-turbo-preview",
                    api_key=openai_key,
                    base_url="https://api.openai.com/v1",
                    supports_tool_use=True,
                    supports_streaming=True,
                    cost_per_1m_input=10.0,
                    cost_per_1m_output=30.0,
                    priority=9
                )
            )

    def add_model(self, name: str, config: ModelConfig):
        """添加模型"""
        self.models[name] = config
        self.usage_stats[name] = {
            "total_requests": 0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "total_cost": 0.0,
            "errors": 0
        }
        print(f"[MultiModel] 已添加模型: {name} ({config.provider})")

    def _setup_routing(self):
        """设置路由规则"""

        # 简单查询：优先使用便宜的模型
        if "deepseek-chat" in self.models:
            self.routing_rules[QueryComplexity.SIMPLE].append("deepseek-chat")
        if "claude-opus" in self.models:
            self.routing_rules[QueryComplexity.SIMPLE].append("claude-opus")

        # 中等查询：平衡成本和质量
        if "claude-opus" in self.models:
            self.routing_rules[QueryComplexity.MEDIUM].append("claude-opus")
        if "deepseek-chat" in self.models:
            self.routing_rules[QueryComplexity.MEDIUM].append("deepseek-chat")

        # 复杂查询：优先使用高质量模型
        if "claude-opus" in self.models:
            self.routing_rules[QueryComplexity.COMPLEX].append("claude-opus")
        if "gpt-4" in self.models:
            self.routing_rules[QueryComplexity.COMPLEX].append("gpt-4")
        if "deepseek-chat" in self.models:
            self.routing_rules[QueryComplexity.COMPLEX].append("deepseek-chat")

    def classify_query(self, query: str) -> QueryComplexity:
        """
        分类查询复杂度

        简单查询：价格、基础信息
        中等查询：历史数据、简单分析
        复杂查询：深度分析、多维对比
        """
        query_lower = query.lower()

        # 简单查询关键词
        simple_keywords = [
            "价格", "股价", "多少", "price", "cost",
            "是什么", "what is", "定义", "definition"
        ]

        # 复杂查询关键词
        complex_keywords = [
            "分析", "对比", "比较", "影响", "预测",
            "analyze", "compare", "impact", "predict",
            "为什么", "如何", "why", "how",
            "详细", "深入", "detailed", "comprehensive"
        ]

        # 检查复杂查询
        if any(keyword in query_lower for keyword in complex_keywords):
            return QueryComplexity.COMPLEX

        # 检查简单查询
        if any(keyword in query_lower for keyword in simple_keywords):
            return QueryComplexity.SIMPLE

        # 默认中等
        return QueryComplexity.MEDIUM

    def select_model(
        self,
        complexity: Optional[QueryComplexity] = None,
        preferred_provider: Optional[ModelProvider] = None
    ) -> Optional[str]:
        """
        选择模型

        Args:
            complexity: 查询复杂度
            preferred_provider: 首选提供商

        Returns:
            模型名称
        """
        # 如果指定了提供商，优先使用
        if preferred_provider:
            for name, config in self.models.items():
                if config.provider == preferred_provider:
                    return name

        # 根据复杂度选择
        if complexity and complexity in self.routing_rules:
            candidates = self.routing_rules[complexity]
            if candidates:
                return candidates[0]  # 返回第一个（优先级最高）

        # 默认返回优先级最高的
        if self.models:
            sorted_models = sorted(
                self.models.items(),
                key=lambda x: x[1].priority,
                reverse=True
            )
            return sorted_models[0][0]

        return None

    def get_client(self, model_name: str):
        """获取模型客户端"""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")

        config = self.models[model_name]

        if config.provider == ModelProvider.ANTHROPIC:
            kwargs = {"api_key": config.api_key}
            if config.base_url:
                kwargs["base_url"] = config.base_url
            return anthropic.Anthropic(**kwargs)

        elif config.provider in [ModelProvider.OPENAI, ModelProvider.DEEPSEEK]:
            return OpenAI(
                api_key=config.api_key,
                base_url=config.base_url
            )

        else:
            raise NotImplementedError(f"Provider {config.provider} not implemented yet")

    def record_usage(
        self,
        model_name: str,
        tokens_input: int,
        tokens_output: int,
        success: bool = True
    ):
        """记录使用情况"""
        if model_name not in self.usage_stats:
            return

        stats = self.usage_stats[model_name]
        config = self.models[model_name]

        stats["total_requests"] += 1
        stats["total_tokens_input"] += tokens_input
        stats["total_tokens_output"] += tokens_output

        # 计算成本
        cost = (
            tokens_input / 1_000_000 * config.cost_per_1m_input +
            tokens_output / 1_000_000 * config.cost_per_1m_output
        )
        stats["total_cost"] += cost

        if not success:
            stats["errors"] += 1

    def get_usage_report(self) -> Dict[str, Any]:
        """获取使用报告"""
        return {
            "models": self.usage_stats,
            "total_cost": sum(s["total_cost"] for s in self.usage_stats.values()),
            "total_requests": sum(s["total_requests"] for s in self.usage_stats.values())
        }

    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有可用模型"""
        return [
            {
                "name": name,
                "provider": config.provider,
                "model": config.model_name,
                "supports_tool_use": config.supports_tool_use,
                "cost_per_1m_input": config.cost_per_1m_input,
                "cost_per_1m_output": config.cost_per_1m_output,
                "priority": config.priority
            }
            for name, config in self.models.items()
        ]


# 全局实例
model_manager = MultiModelManager()
