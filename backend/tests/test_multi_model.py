"""Tests for the DeepSeek-only model manager."""

from types import SimpleNamespace

from app.models.multi_model import ModelConfig, ModelProvider, MultiModelManager, QueryComplexity


def build_manager(api_key: str = "test-key") -> MultiModelManager:
    return MultiModelManager(
        settings_obj=SimpleNamespace(
            DEEPSEEK_API_KEY=api_key,
            DEEPSEEK_BASE_URL="https://api.deepseek.com",
            DEEPSEEK_MODEL="deepseek-chat",
        )
    )


class TestModelConfig:
    def test_model_config_creation(self):
        config = ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test-key",
            base_url="https://api.deepseek.com",
        )

        assert config.provider == ModelProvider.DEEPSEEK
        assert config.model_name == "deepseek-chat"
        assert config.api_key == "test-key"
        assert config.supports_tool_use is True


class TestMultiModelManager:
    def test_manager_initialization_with_key(self):
        manager = build_manager()

        assert "deepseek-chat" in manager.models
        assert manager.select_model() == "deepseek-chat"

    def test_manager_initialization_without_key(self):
        manager = build_manager(api_key="")

        assert manager.models == {}
        assert manager.select_model() is None

    def test_classify_query(self):
        manager = build_manager()

        assert manager.classify_query("AAPL price") == QueryComplexity.SIMPLE
        assert manager.classify_query("分析苹果估值和风险") == QueryComplexity.COMPLEX
        assert manager.classify_query("苹果最近走势") == QueryComplexity.MEDIUM

    def test_select_model_by_provider(self):
        manager = build_manager()

        assert manager.select_model(preferred_provider=ModelProvider.DEEPSEEK) == "deepseek-chat"

    def test_record_usage(self):
        manager = build_manager()
        manager.record_usage("deepseek-chat", 1000, 500, True)

        stats = manager.usage_stats["deepseek-chat"]
        assert stats["total_requests"] == 1
        assert stats["total_tokens_input"] == 1000
        assert stats["total_tokens_output"] == 500
        assert stats["total_cost"] > 0

    def test_record_usage_with_error(self):
        manager = build_manager()
        manager.record_usage("deepseek-chat", 1000, 500, False)

        assert manager.usage_stats["deepseek-chat"]["errors"] == 1

    def test_list_models(self):
        manager = build_manager()
        models = manager.list_models()

        assert len(models) == 1
        assert models[0]["provider"] == ModelProvider.DEEPSEEK
        assert models[0]["model"] == "deepseek-chat"


class TestEnums:
    def test_complexity_values(self):
        assert QueryComplexity.SIMPLE == "simple"
        assert QueryComplexity.MEDIUM == "medium"
        assert QueryComplexity.COMPLEX == "complex"

    def test_provider_values(self):
        assert ModelProvider.DEEPSEEK == "deepseek"
