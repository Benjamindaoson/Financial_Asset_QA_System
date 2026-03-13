"""LLM-based query router."""

import json
from typing import Dict, Any

from app.core.prompt_manager import PromptManager
from app.core.llm_client import LLMClient
from app.config import settings


class LLMRouter:
    """LLM-based router for query classification."""

    def __init__(
        self,
        prompt_manager: PromptManager = None,
        llm_client: LLMClient = None
    ):
        """Initialize LLM Router.

        Args:
            prompt_manager: PromptManager instance. If None, creates new one.
            llm_client: LLMClient instance. If None, creates new one.
        """
        self.prompt_manager = prompt_manager or PromptManager()
        self.llm_client = llm_client or LLMClient()

    async def route(self, user_question: str) -> Dict[str, Any]:
        """Route a user question using LLM.

        Args:
            user_question: The user's question

        Returns:
            Dict containing:
                - question_type: Type of question (real_time_quote, financial_knowledge, etc.)
                - confidence: Confidence score (0-1)
                - route: Routing path (api_direct, rag_retrieval, hybrid)
                - entities: Extracted entities (ticker, company, time_range)
                - reasoning: Explanation of classification

        Raises:
            json.JSONDecodeError: If LLM response is not valid JSON
            KeyError: If response is missing required fields
        """
        # Get system prompt and user prompt
        system_prompt = self.prompt_manager.get_system_prompt("router")
        user_prompt = self.prompt_manager.render_user_prompt(
            "router",
            user_question=user_question
        )

        # Get temperature and max_tokens from config
        temperature = self.prompt_manager.get_temperature("router")
        max_tokens = self.prompt_manager.get_max_tokens("router")

        # Call LLM with JSON mode
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.LLM_ROUTER_TIMEOUT,
            response_format={"type": "json_object"}
        )

        # Parse JSON response
        result = json.loads(response)

        # Validate required fields
        required_fields = ["question_type", "confidence", "route", "entities", "reasoning"]
        for field in required_fields:
            if field not in result:
                raise KeyError(f"Missing required field: {field}")

        return result
