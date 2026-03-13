"""LLM client for unified API calls."""

from typing import Any, AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI

from app.config import settings


class LLMClient:
    """Unified LLM client for DeepSeek API calls."""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None
    ):
        """Initialize LLM client.

        Args:
            api_key: API key for DeepSeek. If None, uses settings.DEEPSEEK_API_KEY
            base_url: Base URL for API. If None, uses settings.DEEPSEEK_BASE_URL
            model: Model name. If None, uses settings.DEEPSEEK_MODEL
        """
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = base_url or settings.DEEPSEEK_BASE_URL
        self.model = model or settings.DEEPSEEK_MODEL

        # Initialize OpenAI client (compatible with DeepSeek API)
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: int = 30,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """Call chat completion API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            response_format: Optional response format, e.g., {"type": "json_object"}

        Returns:
            Generated text response

        Raises:
            Exception: If API call fails
        """
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": timeout
            }

            if response_format:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)

            return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"LLM API call failed: {str(e)}") from e

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: int = 30
    ) -> AsyncGenerator[str, None]:
        """Call chat completion API with streaming.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds

        Yields:
            Text chunks as they arrive

        Raises:
            Exception: If API call fails
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                stream=True
            )

            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise Exception(f"LLM streaming API call failed: {str(e)}") from e
