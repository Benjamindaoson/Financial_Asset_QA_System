"""Unified model adapter layer for Anthropic and OpenAI-compatible SDKs."""

from abc import ABC, abstractmethod
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Dict, List

import anthropic
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


class AnthropicAdapter(ModelAdapter):
    """Anthropic SDK adapter."""

    def __init__(self, config: ModelConfig):
        kwargs = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self.client = anthropic.Anthropic(**kwargs)
        self.model_name = config.model_name

    async def create_message_stream(
        self,
        messages: List[Dict[str, str]],
        system: str,
        tools: List[Dict[str, Any]],
        max_tokens: int,
    ) -> AsyncGenerator:
        with self.client.messages.stream(
            model=self.model_name,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        ) as stream:
            for event in stream:
                yield event
            yield {"final_message": stream.current_message_snapshot}


class OpenAIAdapter(ModelAdapter):
    """OpenAI-compatible SDK adapter used for OpenAI, DeepSeek, and similar providers."""

    def __init__(self, config: ModelConfig):
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)
        self.model_name = config.model_name

    def _convert_tools_to_openai_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
        openai_messages = [{"role": "system", "content": system}] + messages
        openai_tools = self._convert_tools_to_openai_format(tools)

        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=openai_messages,
            tools=openai_tools or None,
            max_tokens=max_tokens,
            stream=True,
        )

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

            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    call_id = tool_call.id or str(tool_call.index)
                    if call_id not in tool_blocks:
                        tool_blocks[call_id] = {
                            "name": "",
                            "arguments": "",
                        }
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
        if config.provider == ModelProvider.ANTHROPIC:
            return AnthropicAdapter(config)

        if config.provider in {
            ModelProvider.OPENAI,
            ModelProvider.DEEPSEEK,
            ModelProvider.QWEN,
            ModelProvider.ZHIPU,
            ModelProvider.BAICHUAN,
            ModelProvider.MINIMAX,
        }:
            return OpenAIAdapter(config)

        raise NotImplementedError(f"Provider {config.provider} not supported")
