"""Single-model manager for the DeepSeek runtime."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from app.config import settings


class ModelProvider(str, Enum):
    """Supported model providers."""

    DEEPSEEK = "deepseek"


class QueryComplexity(str, Enum):
    """Lightweight complexity buckets used for telemetry."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class ModelConfig:
    """Runtime model configuration."""

    provider: ModelProvider
    model_name: str
    api_key: str
    base_url: Optional[str] = None
    supports_tool_use: bool = True
    supports_streaming: bool = True
    cost_per_1m_input: float = 0.27
    cost_per_1m_output: float = 1.10
    max_tokens: int = 4096
    priority: int = 10


class MultiModelManager:
    """Manage the only supported chat model: DeepSeek."""

    SIMPLE_KEYWORDS = {
        "price",
        "quote",
        "cost",
        "what is",
        "definition",
        "价格",
        "股价",
        "多少钱",
        "定义",
        "是什么",
    }
    COMPLEX_KEYWORDS = {
        "analyze",
        "compare",
        "impact",
        "predict",
        "detailed",
        "comprehensive",
        "分析",
        "对比",
        "比较",
        "影响",
        "预测",
        "为什么",
        "如何",
        "详细",
        "深入",
    }

    def __init__(self, settings_obj=settings):
        self.settings = settings_obj
        self.models: Dict[str, ModelConfig] = {}
        self.routing_rules: Dict[QueryComplexity, List[str]] = {
            QueryComplexity.SIMPLE: [],
            QueryComplexity.MEDIUM: [],
            QueryComplexity.COMPLEX: [],
        }
        self.usage_stats: Dict[str, Dict[str, Any]] = {}
        self._load_models()
        self._setup_routing()

    def _load_models(self) -> None:
        if not self.settings.DEEPSEEK_API_KEY:
            return

        self.add_model(
            self.settings.DEEPSEEK_MODEL,
            ModelConfig(
                provider=ModelProvider.DEEPSEEK,
                model_name=self.settings.DEEPSEEK_MODEL,
                api_key=self.settings.DEEPSEEK_API_KEY,
                base_url=self.settings.DEEPSEEK_BASE_URL,
            ),
        )

    def _setup_routing(self) -> None:
        model_name = self.settings.DEEPSEEK_MODEL
        if model_name not in self.models:
            return

        for complexity in QueryComplexity:
            self.routing_rules[complexity] = [model_name]

    def add_model(self, name: str, config: ModelConfig) -> None:
        self.models[name] = config
        self.usage_stats[name] = {
            "total_requests": 0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "total_cost": 0.0,
            "errors": 0,
        }

    def classify_query(self, query: str) -> QueryComplexity:
        lowered = query.lower()
        if any(keyword in lowered or keyword in query for keyword in self.COMPLEX_KEYWORDS):
            return QueryComplexity.COMPLEX
        if any(keyword in lowered or keyword in query for keyword in self.SIMPLE_KEYWORDS):
            return QueryComplexity.SIMPLE
        return QueryComplexity.MEDIUM

    def select_model(
        self,
        complexity: Optional[QueryComplexity] = None,
        preferred_provider: Optional[ModelProvider] = None,
    ) -> Optional[str]:
        if preferred_provider and preferred_provider != ModelProvider.DEEPSEEK:
            return None

        if complexity and self.routing_rules.get(complexity):
            return self.routing_rules[complexity][0]

        if self.models:
            return next(iter(self.models))

        return None

    def record_usage(
        self,
        model_name: str,
        tokens_input: int,
        tokens_output: int,
        success: bool = True,
    ) -> None:
        if model_name not in self.usage_stats:
            return

        stats = self.usage_stats[model_name]
        config = self.models[model_name]
        stats["total_requests"] += 1
        stats["total_tokens_input"] += tokens_input
        stats["total_tokens_output"] += tokens_output
        stats["total_cost"] += (
            tokens_input / 1_000_000 * config.cost_per_1m_input
            + tokens_output / 1_000_000 * config.cost_per_1m_output
        )
        if not success:
            stats["errors"] += 1

    def get_usage_report(self) -> Dict[str, Any]:
        return {
            "models": self.usage_stats,
            "total_cost": sum(stats["total_cost"] for stats in self.usage_stats.values()),
            "total_requests": sum(stats["total_requests"] for stats in self.usage_stats.values()),
        }

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "provider": config.provider,
                "model": config.model_name,
                "supports_tool_use": config.supports_tool_use,
                "cost_per_1m_input": config.cost_per_1m_input,
                "cost_per_1m_output": config.cost_per_1m_output,
                "priority": config.priority,
            }
            for name, config in self.models.items()
        ]


model_manager = MultiModelManager()
