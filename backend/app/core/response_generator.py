"""Response generator for structured LLM outputs."""

import json
from typing import AsyncGenerator, Dict, Any

from app.core.prompt_manager import PromptManager
from app.core.llm_client import LLMClient
from app.config import settings


class ResponseGenerator:
    """Generate structured responses using LLM."""

    def __init__(
        self,
        prompt_manager: PromptManager = None,
        llm_client: LLMClient = None
    ):
        """Initialize Response Generator.

        Args:
            prompt_manager: PromptManager instance. If None, creates new one.
            llm_client: LLMClient instance. If None, creates new one.
        """
        self.prompt_manager = prompt_manager or PromptManager()
        self.llm_client = llm_client or LLMClient()

    async def generate(
        self,
        user_question: str,
        api_data: str,
        rag_context: str,
        api_completeness: float,
        rag_relevance: float,
        news_context: str = "",
        route_type: str = "market",
    ) -> str:
        """Generate structured response based on data.

        Args:
            user_question: Original user question
            api_data: Data from API calls (formatted string)
            rag_context: Retrieved context from RAG
            api_completeness: API data completeness score (0-1)
            rag_relevance: RAG relevance score (0-1)
            news_context: News and web search results
            route_type: Query route type (market/knowledge/news/hybrid)

        Returns:
            Generated response string in markdown format
        """
        # Get system prompt and user prompt
        system_prompt = self.prompt_manager.get_system_prompt("generator")
        user_prompt = self.prompt_manager.render_user_prompt(
            "generator",
            user_question=user_question,
            api_data=api_data,
            rag_context=rag_context,
            api_completeness=api_completeness,
            rag_relevance=rag_relevance,
            news_context=news_context or "暂无新闻数据",
            route_type=route_type,
        )

        # Get temperature and max_tokens from config
        temperature = self.prompt_manager.get_temperature("generator")
        max_tokens = self.prompt_manager.get_max_tokens("generator")

        # Call LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.LLM_GENERATOR_TIMEOUT
        )

        return response

    async def generate_stream(
        self,
        user_question: str,
        api_data: str,
        rag_context: str,
        api_completeness: float,
        rag_relevance: float,
        news_context: str = "",
        route_type: str = "market",
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response based on data.

        Args:
            user_question: Original user question
            api_data: Data from API calls (formatted string)
            rag_context: Retrieved context from RAG
            api_completeness: API data completeness score (0-1)
            rag_relevance: RAG relevance score (0-1)
            news_context: News and web search results
            route_type: Query route type (market/knowledge/news/hybrid)

        Yields:
            Text chunks as they arrive from LLM
        """
        # Get system prompt and user prompt
        system_prompt = self.prompt_manager.get_system_prompt("generator")
        user_prompt = self.prompt_manager.render_user_prompt(
            "generator",
            user_question=user_question,
            api_data=api_data,
            rag_context=rag_context,
            api_completeness=api_completeness,
            rag_relevance=rag_relevance,
            news_context=news_context or "暂无新闻数据",
            route_type=route_type,
        )

        # Get temperature and max_tokens from config
        temperature = self.prompt_manager.get_temperature("generator")
        max_tokens = self.prompt_manager.get_max_tokens("generator")

        # Call LLM with streaming
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        async for chunk in self.llm_client.chat_completion_stream(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.LLM_GENERATOR_TIMEOUT
        ):
            yield chunk

    def _format_api_data(self, api_data: Dict[str, Any]) -> str:
        """Format API data as readable string.

        Args:
            api_data: Dictionary of API data

        Returns:
            Formatted string representation
        """
        if not api_data:
            return "暂无API数据"

        try:
            # Pretty print JSON
            return json.dumps(api_data, indent=2, ensure_ascii=False)
        except Exception:
            # Fallback to string representation
            return str(api_data)
