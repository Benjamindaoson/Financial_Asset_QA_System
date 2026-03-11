"""Unified model adapter layer for DeepSeek."""

from abc import ABC, abstractmethod
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Dict, List

from openai import OpenAI

from app.models.multi_model import ModelConfig, ModelProvider


class ModelAdapter(ABC):
    """Base adapter interface."""

    @abstractmethod
    async def create_message_stream(
        self,
        messages: List[Dict[str, str]],
        system: str,
        tools: List[Dict[str, Any]],
        max_tokens: int,
    ) -> AsyncGenerator:
        """Create a streaming message generator."""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Non-streaming chat completion for function calling."""


class DeepSeekAdapter(ModelAdapter):
    """OpenAI-compatible SDK adapter used for DeepSeek."""

    def __init__(self, config: ModelConfig):
        import httpx
        # Create HTTP client without proxy to avoid connection issues
        http_client = httpx.Client(proxies=None)
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            http_client=http_client
        )
        self.model_name = config.model_name

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted = []
        for tool in tools:
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
            )
        return converted

    async def create_message_stream(
        self,
        messages: List[Dict[str, str]],
        system: str,
        tools: List[Dict[str, Any]],
        max_tokens: int,
    ) -> AsyncGenerator:
        import asyncio

        request_messages = [{"role": "system", "content": system}] + messages
        request_tools = self._convert_tools(tools) if tools else None

        # Run sync stream in executor to make it truly async
        loop = asyncio.get_event_loop()

        def _create_stream():
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=request_messages,
                tools=request_tools,
                max_tokens=max_tokens,
                stream=True,
            )

        stream = await loop.run_in_executor(None, _create_stream)

        text_chunks: List[str] = []
        tool_blocks: Dict[str, Dict[str, Any]] = {}
        tool_order: List[str] = []

        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                text_chunks.append(delta.content)
                yield {
                    "type": "content_block_delta",
                    "delta": {
                        "type": "text_delta",
                        "text": delta.content,
                    },
                }
                # Allow other tasks to run
                await asyncio.sleep(0)

            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    call_id = tool_call.id or str(tool_call.index)
                    if call_id not in tool_blocks:
                        tool_blocks[call_id] = {"name": "", "arguments": ""}
                        tool_order.append(call_id)

                    if tool_call.function:
                        if tool_call.function.name:
                            tool_blocks[call_id]["name"] = tool_call.function.name
                            yield {
                                "type": "content_block_start",
                                "content_block": {
                                    "type": "tool_use",
                                    "name": tool_call.function.name,
                                },
                            }
                        if tool_call.function.arguments:
                            tool_blocks[call_id]["arguments"] += str(tool_call.function.arguments)

        final_content = []
        final_text = "".join(text_chunks)
        if final_text:
            final_content.append(SimpleNamespace(type="text", text=final_text))

        for call_id in tool_order:
            tool_block = tool_blocks[call_id]
            final_content.append(
                SimpleNamespace(
                    type="tool_use",
                    name=tool_block["name"],
                    input=_safe_json_loads(tool_block["arguments"]),
                )
            )

        yield {"final_message": SimpleNamespace(content=final_content)}

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Non-streaming chat completion for function calling."""
        import asyncio
        import json

        request_tools = self._convert_tools(tools) if tools else None

        loop = asyncio.get_event_loop()

        def _create_completion():
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=request_tools,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )

        response = await loop.run_in_executor(None, _create_completion)

        # Parse response
        choice = response.choices[0]
        message = choice.message

        result = {
            "content": message.content or "",
            "tool_calls": []
        }

        # Extract tool calls
        if message.tool_calls:
            for tool_call in message.tool_calls:
                try:
                    arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                except json.JSONDecodeError:
                    arguments = {}

                result["tool_calls"].append({
                    "name": tool_call.function.name,
                    "input": arguments
                })

        return result


def _safe_json_loads(value: str) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        import json

        return json.loads(value)
    except Exception:
        return {}


class ModelAdapterFactory:
    """Factory for model adapters."""

    @staticmethod
    def create_adapter(config: ModelConfig) -> ModelAdapter:
        if config.provider == ModelProvider.DEEPSEEK:
            return DeepSeekAdapter(config)

        raise NotImplementedError(f"Provider {config.provider} not supported")
