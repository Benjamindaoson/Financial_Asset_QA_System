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


class TestAnthropicAdapterStreaming:
    """测试Anthropic适配器流式功能"""

    @pytest.mark.asyncio
    async def test_anthropic_stream_with_text(self):
        """测试Anthropic流式文本响应"""
        config = ModelConfig(
            model_name="claude-3-5-sonnet-20241022",
            provider=ModelProvider.ANTHROPIC,
            api_key="test-key"
        )

        with patch('app.models.model_adapter.anthropic.Anthropic') as mock_anthropic:
            # Mock stream context manager
            mock_stream = MagicMock()
            mock_stream.__enter__ = Mock(return_value=mock_stream)
            mock_stream.__exit__ = Mock(return_value=None)
            mock_stream.__iter__ = Mock(return_value=iter([Mock(type="text")]))
            mock_stream.current_message_snapshot = Mock()

            mock_anthropic.return_value.messages.stream.return_value = mock_stream

            adapter = AnthropicAdapter(config)
            events = []
            async for event in adapter.create_message_stream(
                messages=[{"role": "user", "content": "test"}],
                system="test system",
                tools=[],
                max_tokens=100
            ):
                events.append(event)

            assert len(events) > 0

    @pytest.mark.asyncio
    async def test_anthropic_adapter_with_base_url(self):
        """测试带base_url的Anthropic适配器"""
        config = ModelConfig(
            model_name="claude-3-5-sonnet-20241022",
            provider=ModelProvider.ANTHROPIC,
            api_key="test-key",
            base_url="https://custom.api.com"
        )

        with patch('app.models.model_adapter.anthropic.Anthropic') as mock_anthropic:
            adapter = AnthropicAdapter(config)

            # Verify base_url was passed
            mock_anthropic.assert_called_once_with(
                api_key="test-key",
                base_url="https://custom.api.com"
            )


class TestOpenAIAdapterStreaming:
    """测试OpenAI适配器流式功能"""

    @pytest.mark.asyncio
    async def test_openai_stream_with_text(self):
        """测试OpenAI流式文本响应"""
        config = ModelConfig(
            model_name="deepseek-chat",
            provider=ModelProvider.DEEPSEEK,
            api_key="test-key",
            base_url="https://api.deepseek.com"
        )

        with patch('app.models.model_adapter.OpenAI') as mock_openai:
            # Mock streaming response
            mock_chunk = Mock()
            mock_chunk.choices = [Mock()]
            mock_chunk.choices[0].delta = Mock()
            mock_chunk.choices[0].delta.content = "测试文本"
            mock_chunk.choices[0].delta.tool_calls = None

            mock_openai.return_value.chat.completions.create.return_value = iter([mock_chunk])

            adapter = OpenAIAdapter(config)
            events = []
            async for event in adapter.create_message_stream(
                messages=[{"role": "user", "content": "test"}],
                system="test system",
                tools=[],
                max_tokens=100
            ):
                events.append(event)

            assert len(events) > 0
            assert events[0]["type"] == "content_block_delta"
            assert events[0]["delta"]["text"] == "测试文本"

    @pytest.mark.asyncio
    async def test_openai_stream_with_tool_calls(self):
        """测试OpenAI流式工具调用"""
        config = ModelConfig(
            model_name="deepseek-chat",
            provider=ModelProvider.DEEPSEEK,
            api_key="test-key",
            base_url="https://api.deepseek.com"
        )

        with patch('app.models.model_adapter.OpenAI') as mock_openai:
            # Mock tool call chunk
            mock_chunk = Mock()
            mock_chunk.choices = [Mock()]
            mock_chunk.choices[0].delta = Mock()
            mock_chunk.choices[0].delta.content = None

            mock_tool_call = Mock()
            mock_tool_call.function = Mock()
            mock_tool_call.function.name = "get_price"
            mock_chunk.choices[0].delta.tool_calls = [mock_tool_call]

            mock_openai.return_value.chat.completions.create.return_value = iter([mock_chunk])

            adapter = OpenAIAdapter(config)
            events = []
            async for event in adapter.create_message_stream(
                messages=[{"role": "user", "content": "test"}],
                system="test system",
                tools=[{"name": "get_price", "description": "test", "input_schema": {}}],
                max_tokens=100
            ):
                events.append(event)

            assert len(events) > 0
            assert events[0]["type"] == "content_block_start"
            assert events[0]["content_block"]["name"] == "get_price"
