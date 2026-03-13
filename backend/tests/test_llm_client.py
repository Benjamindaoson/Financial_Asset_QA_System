"""Tests for LLMClient."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.llm_client import LLMClient


@pytest.mark.asyncio
async def test_llm_client_initialization():
    """Test that LLMClient initializes correctly."""
    client = LLMClient()

    assert client is not None
    assert client.api_key is not None
    assert client.base_url is not None
    assert client.model is not None


@pytest.mark.asyncio
async def test_chat_completion_basic():
    """Test basic chat completion."""
    client = LLMClient()

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ]

    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_create.return_value = mock_response

        response = await client.chat_completion(messages)

        assert response == "Hello! How can I help you?"
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_chat_completion_with_temperature():
    """Test chat completion with custom temperature."""
    client = LLMClient()

    messages = [{"role": "user", "content": "Test"}]

    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_create.return_value = mock_response

        await client.chat_completion(messages, temperature=0.7)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['temperature'] == 0.7


@pytest.mark.asyncio
async def test_chat_completion_with_json_mode():
    """Test chat completion with JSON response format."""
    client = LLMClient()

    messages = [{"role": "user", "content": "Return JSON"}]

    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"key": "value"}'
        mock_create.return_value = mock_response

        response = await client.chat_completion(
            messages,
            response_format={"type": "json_object"}
        )

        assert response == '{"key": "value"}'
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['response_format'] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_chat_completion_timeout():
    """Test chat completion with timeout."""
    client = LLMClient()

    messages = [{"role": "user", "content": "Test"}]

    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_create.return_value = mock_response

        await client.chat_completion(messages, timeout=15)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['timeout'] == 15


@pytest.mark.asyncio
async def test_chat_completion_error_handling():
    """Test error handling in chat completion."""
    client = LLMClient()

    messages = [{"role": "user", "content": "Test"}]

    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = Exception("API Error")

        with pytest.raises(Exception) as exc_info:
            await client.chat_completion(messages)

        assert "API Error" in str(exc_info.value)
