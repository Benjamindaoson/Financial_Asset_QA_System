"""
测试模型适配器
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.models.model_adapter import (
    ModelAdapter,
    AnthropicAdapter,
    OpenAIAdapter,
    ModelAdapterFactory
)
from app.models.multi_model import ModelProvider, ModelConfig


class TestAnthropicAdapter:
    """测试AnthropicAdapter"""

    def test_adapter_creation(self):
        """测试创建Anthropic适配器"""
        config = ModelConfig(
            provider=ModelProvider.ANTHROPIC,
            model_name="claude-opus-4-6",
            api_key="test_key",
            base_url="https://api.anthropic.com"
        )

        with patch('app.models.model_adapter.anthropic.Anthropic'):
            adapter = AnthropicAdapter(config)
            assert adapter.model_name == "claude-opus-4-6"
            assert adapter.client is not None

    def test_adapter_creation_without_base_url(self):
        """测试创建Anthropic适配器（无base_url）"""
        config = ModelConfig(
            provider=ModelProvider.ANTHROPIC,
            model_name="claude-opus-4-6",
            api_key="test_key"
        )

        with patch('app.models.model_adapter.anthropic.Anthropic'):
            adapter = AnthropicAdapter(config)
            assert adapter.model_name == "claude-opus-4-6"


class TestOpenAIAdapter:
    """测试OpenAIAdapter"""

    def test_adapter_creation(self):
        """测试创建OpenAI适配器"""
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4",
            api_key="test_key",
            base_url="https://api.openai.com/v1"
        )

        with patch('app.models.model_adapter.OpenAI'):
            adapter = OpenAIAdapter(config)
            assert adapter.model_name == "gpt-4"
            assert adapter.client is not None

    def test_convert_tools_to_openai_format(self):
        """测试工具格式转换"""
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4",
            api_key="test_key",
            base_url="https://api.openai.com/v1"
        )

        with patch('app.models.model_adapter.OpenAI'):
            adapter = OpenAIAdapter(config)

            anthropic_tools = [
                {
                    "name": "get_price",
                    "description": "获取股票价格",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "股票代码"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            ]

            openai_tools = adapter._convert_tools_to_openai_format(anthropic_tools)

            assert len(openai_tools) == 1
            assert openai_tools[0]["type"] == "function"
            assert openai_tools[0]["function"]["name"] == "get_price"
            assert openai_tools[0]["function"]["description"] == "获取股票价格"
            assert "parameters" in openai_tools[0]["function"]


class TestModelAdapterFactory:
    """测试ModelAdapterFactory"""

    def test_create_anthropic_adapter(self):
        """测试创建Anthropic适配器"""
        config = ModelConfig(
            provider=ModelProvider.ANTHROPIC,
            model_name="claude-opus-4-6",
            api_key="test_key"
        )

        with patch('app.models.model_adapter.anthropic.Anthropic'):
            adapter = ModelAdapterFactory.create_adapter(config)
            assert isinstance(adapter, AnthropicAdapter)

    def test_create_openai_adapter(self):
        """测试创建OpenAI适配器"""
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4",
            api_key="test_key",
            base_url="https://api.openai.com/v1"
        )

        with patch('app.models.model_adapter.OpenAI'):
            adapter = ModelAdapterFactory.create_adapter(config)
            assert isinstance(adapter, OpenAIAdapter)

    def test_create_deepseek_adapter(self):
        """测试创建DeepSeek适配器"""
        config = ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test_key",
            base_url="https://api.deepseek.com"
        )

        with patch('app.models.model_adapter.OpenAI'):
            adapter = ModelAdapterFactory.create_adapter(config)
            assert isinstance(adapter, OpenAIAdapter)

    def test_create_qwen_adapter(self):
        """测试创建Qwen适配器"""
        config = ModelConfig(
            provider=ModelProvider.QWEN,
            model_name="qwen-turbo",
            api_key="test_key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        with patch('app.models.model_adapter.OpenAI'):
            adapter = ModelAdapterFactory.create_adapter(config)
            assert isinstance(adapter, OpenAIAdapter)

    def test_create_unsupported_provider(self):
        """测试创建不支持的提供商适配器"""
        # 创建一个假的提供商
        config = ModelConfig(
            provider="unsupported",
            model_name="test-model",
            api_key="test_key"
        )

        with pytest.raises(NotImplementedError):
            ModelAdapterFactory.create_adapter(config)


class TestAdapterIntegration:
    """测试适配器集成"""

    def test_multiple_adapters(self):
        """测试创建多个适配器"""
        configs = [
            ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-opus-4-6",
                api_key="test_key1"
            ),
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4",
                api_key="test_key2",
                base_url="https://api.openai.com/v1"
            ),
            ModelConfig(
                provider=ModelProvider.DEEPSEEK,
                model_name="deepseek-chat",
                api_key="test_key3",
                base_url="https://api.deepseek.com"
            )
        ]

        with patch('app.models.model_adapter.anthropic.Anthropic'), \
             patch('app.models.model_adapter.OpenAI'):

            adapters = [ModelAdapterFactory.create_adapter(config) for config in configs]

            assert len(adapters) == 3
            assert isinstance(adapters[0], AnthropicAdapter)
            assert isinstance(adapters[1], OpenAIAdapter)
            assert isinstance(adapters[2], OpenAIAdapter)
