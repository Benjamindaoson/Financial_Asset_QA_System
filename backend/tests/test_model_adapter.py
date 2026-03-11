"""Tests for the DeepSeek adapter layer."""

from unittest.mock import Mock, patch

import pytest

from app.models.model_adapter import DeepSeekAdapter, ModelAdapterFactory
from app.models.multi_model import ModelConfig, ModelProvider


class TestDeepSeekAdapter:
    def test_adapter_creation(self):
        config = ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test-key",
            base_url="https://api.deepseek.com",
        )

        with patch("app.models.model_adapter.OpenAI"):
            adapter = DeepSeekAdapter(config)

        assert adapter.model_name == "deepseek-chat"
        assert adapter.client is not None

    def test_convert_tools(self):
        config = ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test-key",
            base_url="https://api.deepseek.com",
        )

        with patch("app.models.model_adapter.OpenAI"):
            adapter = DeepSeekAdapter(config)
            converted = adapter._convert_tools(
                [
                    {
                        "name": "get_price",
                        "description": "Fetch latest price",
                        "input_schema": {
                            "type": "object",
                            "properties": {"symbol": {"type": "string"}},
                            "required": ["symbol"],
                        },
                    }
                ]
            )

        assert converted[0]["type"] == "function"
        assert converted[0]["function"]["name"] == "get_price"
        assert converted[0]["function"]["parameters"]["required"] == ["symbol"]

    @pytest.mark.asyncio
    async def test_stream_with_text(self):
        config = ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test-key",
            base_url="https://api.deepseek.com",
        )

        with patch("app.models.model_adapter.OpenAI") as mock_openai:
            mock_chunk = Mock()
            mock_chunk.choices = [Mock()]
            mock_chunk.choices[0].delta = Mock()
            mock_chunk.choices[0].delta.content = "test text"
            mock_chunk.choices[0].delta.tool_calls = None
            mock_openai.return_value.chat.completions.create.return_value = iter([mock_chunk])

            adapter = DeepSeekAdapter(config)
            events = []
            async for event in adapter.create_message_stream(
                messages=[{"role": "user", "content": "hello"}],
                system="system",
                tools=[],
                max_tokens=100,
            ):
                events.append(event)

        assert events[0]["type"] == "content_block_delta"
        assert events[0]["delta"]["text"] == "test text"

    @pytest.mark.asyncio
    async def test_stream_with_tool_calls(self):
        config = ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test-key",
            base_url="https://api.deepseek.com",
        )

        with patch("app.models.model_adapter.OpenAI") as mock_openai:
            mock_chunk = Mock()
            mock_chunk.choices = [Mock()]
            mock_chunk.choices[0].delta = Mock()
            mock_chunk.choices[0].delta.content = None

            mock_tool_call = Mock()
            mock_tool_call.id = "call-1"
            mock_tool_call.index = 0
            mock_tool_call.function = Mock()
            mock_tool_call.function.name = "get_price"
            mock_tool_call.function.arguments = '{"symbol":"AAPL"}'
            mock_chunk.choices[0].delta.tool_calls = [mock_tool_call]
            mock_openai.return_value.chat.completions.create.return_value = iter([mock_chunk])

            adapter = DeepSeekAdapter(config)
            events = []
            async for event in adapter.create_message_stream(
                messages=[{"role": "user", "content": "price"}],
                system="system",
                tools=[{"name": "get_price", "description": "x", "input_schema": {}}],
                max_tokens=100,
            ):
                events.append(event)

        assert events[0]["type"] == "content_block_start"
        assert events[-1]["final_message"].content[-1].input == {"symbol": "AAPL"}


class TestModelAdapterFactory:
    def test_create_deepseek_adapter(self):
        config = ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test-key",
            base_url="https://api.deepseek.com",
        )

        with patch("app.models.model_adapter.OpenAI"):
            adapter = ModelAdapterFactory.create_adapter(config)

        assert isinstance(adapter, DeepSeekAdapter)

    def test_unsupported_provider(self):
        config = ModelConfig(provider="unsupported", model_name="test-model", api_key="test-key")

        with pytest.raises(NotImplementedError):
            ModelAdapterFactory.create_adapter(config)
