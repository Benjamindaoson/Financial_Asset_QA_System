"""
测试多模型管理器
"""
import pytest
from app.models.multi_model import (
    ModelProvider,
    QueryComplexity,
    ModelConfig,
    MultiModelManager
)


class TestModelConfig:
    """测试ModelConfig类"""

    def test_model_config_creation(self):
        """测试创建模型配置"""
        config = ModelConfig(
            provider=ModelProvider.ANTHROPIC,
            model_name="claude-opus-4-6",
            api_key="test_key",
            base_url="https://api.anthropic.com",
            supports_tool_use=True,
            supports_streaming=True,
            cost_per_1m_input=15.0,
            cost_per_1m_output=75.0,
            max_tokens=4096,
            priority=10
        )

        assert config.provider == ModelProvider.ANTHROPIC
        assert config.model_name == "claude-opus-4-6"
        assert config.api_key == "test_key"
        assert config.supports_tool_use is True
        assert config.cost_per_1m_input == 15.0
        assert config.priority == 10


class TestMultiModelManager:
    """测试MultiModelManager类"""

    def test_manager_initialization(self):
        """测试管理器初始化"""
        manager = MultiModelManager()

        assert isinstance(manager.models, dict)
        assert isinstance(manager.routing_rules, dict)
        assert isinstance(manager.usage_stats, dict)
        assert len(manager.models) >= 1  # 至少有Claude

    def test_add_model(self):
        """测试添加模型"""
        manager = MultiModelManager()
        initial_count = len(manager.models)

        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4",
            api_key="test_key",
            supports_tool_use=True,
            supports_streaming=True,
            cost_per_1m_input=10.0,
            cost_per_1m_output=30.0,
            priority=9
        )

        manager.add_model("test-gpt-4", config)

        assert len(manager.models) == initial_count + 1
        assert "test-gpt-4" in manager.models
        assert "test-gpt-4" in manager.usage_stats

    def test_classify_query_simple(self):
        """测试简单查询分类"""
        manager = MultiModelManager()

        simple_queries = [
            "苹果股价",
            "AAPL price",
            "特斯拉多少钱",
            "价格是多少",
            "cost of TSLA"
        ]

        for query in simple_queries:
            complexity = manager.classify_query(query)
            assert complexity == QueryComplexity.SIMPLE

    def test_classify_query_complex(self):
        """测试复杂查询分类"""
        manager = MultiModelManager()

        complex_queries = [
            "分析美联储加息对科技股的影响",
            "对比微软和谷歌的财务状况",
            "详细解释DCF估值法",
            "为什么特斯拉股价下跌"
        ]

        for query in complex_queries:
            complexity = manager.classify_query(query)
            assert complexity == QueryComplexity.COMPLEX

    def test_classify_query_medium(self):
        """测试中等查询分类"""
        manager = MultiModelManager()

        # 不包含简单或复杂关键词的查询应该是中等
        query = "特斯拉最近的走势"
        complexity = manager.classify_query(query)
        assert complexity == QueryComplexity.MEDIUM

    def test_select_model_by_complexity(self):
        """测试根据复杂度选择模型"""
        manager = MultiModelManager()

        # 简单查询
        model = manager.select_model(QueryComplexity.SIMPLE)
        assert model is not None
        assert model in manager.models

        # 复杂查询
        model = manager.select_model(QueryComplexity.COMPLEX)
        assert model is not None
        assert model in manager.models

    def test_select_model_by_provider(self):
        """测试根据提供商选择模型"""
        manager = MultiModelManager()

        # 选择Anthropic提供商
        model = manager.select_model(preferred_provider=ModelProvider.ANTHROPIC)
        assert model is not None
        config = manager.models[model]
        assert config.provider == ModelProvider.ANTHROPIC

    def test_record_usage(self):
        """测试记录使用情况"""
        manager = MultiModelManager()
        model_name = list(manager.models.keys())[0]

        # 记录使用前
        initial_requests = manager.usage_stats[model_name]["total_requests"]
        initial_cost = manager.usage_stats[model_name]["total_cost"]

        # 记录使用
        manager.record_usage(model_name, 1000, 500, True)

        # 验证统计更新
        assert manager.usage_stats[model_name]["total_requests"] == initial_requests + 1
        assert manager.usage_stats[model_name]["total_tokens_input"] == 1000
        assert manager.usage_stats[model_name]["total_tokens_output"] == 500
        assert manager.usage_stats[model_name]["total_cost"] > initial_cost

    def test_record_usage_with_error(self):
        """测试记录失败的使用"""
        manager = MultiModelManager()
        model_name = list(manager.models.keys())[0]

        initial_errors = manager.usage_stats[model_name]["errors"]

        # 记录失败
        manager.record_usage(model_name, 1000, 500, False)

        assert manager.usage_stats[model_name]["errors"] == initial_errors + 1

    def test_get_usage_report(self):
        """测试获取使用报告"""
        manager = MultiModelManager()
        model_name = list(manager.models.keys())[0]

        # 记录一些使用
        manager.record_usage(model_name, 1000, 500, True)
        manager.record_usage(model_name, 2000, 1000, True)

        report = manager.get_usage_report()

        assert "models" in report
        assert "total_cost" in report
        assert "total_requests" in report
        assert report["total_requests"] >= 2
        assert report["total_cost"] > 0

    def test_list_models(self):
        """测试列出所有模型"""
        manager = MultiModelManager()

        models = manager.list_models()

        assert isinstance(models, list)
        assert len(models) >= 1

        for model in models:
            assert "name" in model
            assert "provider" in model
            assert "model" in model
            assert "supports_tool_use" in model
            assert "cost_per_1m_input" in model
            assert "cost_per_1m_output" in model
            assert "priority" in model

    def test_routing_rules_setup(self):
        """测试路由规则设置"""
        manager = MultiModelManager()

        # 验证所有复杂度都有路由规则
        for complexity in QueryComplexity:
            assert complexity in manager.routing_rules
            assert isinstance(manager.routing_rules[complexity], list)

    def test_cost_calculation(self):
        """测试成本计算"""
        manager = MultiModelManager()
        model_name = list(manager.models.keys())[0]
        config = manager.models[model_name]

        # 记录使用
        tokens_input = 1000000  # 1M tokens
        tokens_output = 500000  # 0.5M tokens

        manager.record_usage(model_name, tokens_input, tokens_output, True)

        # 计算预期成本
        expected_cost = (
            tokens_input / 1_000_000 * config.cost_per_1m_input +
            tokens_output / 1_000_000 * config.cost_per_1m_output
        )

        stats = manager.usage_stats[model_name]
        assert abs(stats["total_cost"] - expected_cost) < 0.01

    def test_model_priority_ordering(self):
        """测试模型优先级排序"""
        manager = MultiModelManager()

        # 添加不同优先级的模型
        manager.add_model(
            "low-priority",
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-3.5",
                api_key="test",
                priority=5
            )
        )

        manager.add_model(
            "high-priority",
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4",
                api_key="test",
                priority=15
            )
        )

        # 不指定复杂度，应该返回优先级最高的
        model = manager.select_model()
        config = manager.models[model]
        assert config.priority >= 10  # 应该是高优先级模型


class TestQueryComplexity:
    """测试QueryComplexity枚举"""

    def test_complexity_values(self):
        """测试复杂度值"""
        assert QueryComplexity.SIMPLE == "simple"
        assert QueryComplexity.MEDIUM == "medium"
        assert QueryComplexity.COMPLEX == "complex"


class TestModelProvider:
    """测试ModelProvider枚举"""

    def test_provider_values(self):
        """测试提供商值"""
        assert ModelProvider.ANTHROPIC == "anthropic"
        assert ModelProvider.OPENAI == "openai"
        assert ModelProvider.DEEPSEEK == "deepseek"
        assert ModelProvider.QWEN == "qwen"
        assert ModelProvider.ZHIPU == "zhipu"
        assert ModelProvider.BAICHUAN == "baichuan"
        assert ModelProvider.MINIMAX == "minimax"


