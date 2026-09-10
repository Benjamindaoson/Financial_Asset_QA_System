"""
Production Built-in Tools for TrustRAG.
Real implementations of Search, Slack, LLM Analysis tools.
"""
import logging
import requests
import json
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0


class SearchTool:
    """
    Production web search tool.
    Integrates with search APIs (Google, Bing, etc.).
    """

    def __init__(self, api_key: Optional[str] = None, search_engine: str = "google"):
        self.api_key = api_key
        self.search_engine = search_engine
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TrustRAG-Search/1.0'
        })

    def search(self, query: str, num_results: int = 10,
              time_filter: Optional[str] = None) -> ToolResult:
        """
        Execute web search.

        Args:
            query: Search query
            num_results: Number of results to return
            time_filter: Time filter ("day", "week", "month", "year")

        Returns:
            Search results
        """
        start_time = time.time()

        try:
            if self.search_engine == "google":
                results = self._google_search(query, num_results, time_filter)
            elif self.search_engine == "bing":
                results = self._bing_search(query, num_results, time_filter)
            else:
                results = self._mock_search(query, num_results)  # Fallback

            execution_time = time.time() - start_time

            return ToolResult(
                success=True,
                data=results,
                metadata={
                    "search_engine": self.search_engine,
                    "query": query,
                    "num_results_requested": num_results,
                    "num_results_returned": len(results)
                },
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Search failed: {e}")

            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    def _google_search(self, query: str, num_results: int, time_filter: Optional[str]) -> List[Dict]:
        """Execute Google Custom Search."""
        if not self.api_key:
            raise ValueError("Google API key required")

        # Google Custom Search API implementation
        base_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "q": query,
            "num": min(num_results, 10),  # Google limits to 10 per request
        }

        # Add time filter
        if time_filter:
            date_restrict_map = {
                "day": "d1",
                "week": "w1",
                "month": "m1",
                "year": "y1"
            }
            if time_filter in date_restrict_map:
                params["dateRestrict"] = date_restrict_map[time_filter]

        response = self.session.get(base_url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        results = []

        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "google"
            })

        return results

    def _bing_search(self, query: str, num_results: int, time_filter: Optional[str]) -> List[Dict]:
        """Execute Bing Web Search."""
        if not self.api_key:
            raise ValueError("Bing API key required")

        # Bing Search API implementation
        base_url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {
            "q": query,
            "count": min(num_results, 50),  # Bing allows up to 50
            "responseFilter": "Webpages"
        }

        # Add time filter
        if time_filter:
            freshness_map = {
                "day": "Day",
                "week": "Week",
                "month": "Month"
            }
            if time_filter in freshness_map:
                params["freshness"] = freshness_map[time_filter]

        response = self.session.get(base_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        results = []

        for item in data.get("webPages", {}).get("value", []):
            results.append({
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "source": "bing"
            })

        return results

    def _mock_search(self, query: str, num_results: int) -> List[Dict]:
        """Mock search results for development."""
        logger.warning("Using mock search results - configure real search API")
        return [
            {
                "title": f"Mock Result {i+1} for '{query}'",
                "url": f"https://example.com/result{i+1}",
                "snippet": f"This is a mock search result {i+1} for the query '{query}'.",
                "source": "mock"
            }
            for i in range(min(num_results, 5))
        ]


class SlackTool:
    """
    Production Slack integration tool.
    Searches messages, posts updates, manages channels.
    """

    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {bot_token}',
            'Content-Type': 'application/json'
        })

    def search_messages(self, query: str, channel: Optional[str] = None,
                       limit: int = 20) -> ToolResult:
        """
        Search Slack messages.

        Args:
            query: Search query
            channel: Optional channel ID to search in
            limit: Maximum results to return

        Returns:
            Search results
        """
        start_time = time.time()

        try:
            url = "https://slack.com/api/search.messages"
            params = {
                "query": query,
                "count": min(limit, 100)  # Slack limits to 100
            }

            if channel:
                params["query"] += f" in:{channel}"

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if not data.get("ok"):
                raise ValueError(f"Slack API error: {data.get('error')}")

            messages = []
            for message in data.get("messages", {}).get("matches", []):
                messages.append({
                    "text": message.get("text", ""),
                    "user": message.get("user", ""),
                    "channel": message.get("channel", {}).get("name", ""),
                    "timestamp": message.get("ts", ""),
                    "permalink": message.get("permalink", "")
                })

            execution_time = time.time() - start_time

            return ToolResult(
                success=True,
                data=messages,
                metadata={
                    "query": query,
                    "channel": channel,
                    "total_results": data.get("messages", {}).get("total", 0)
                },
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Slack search failed: {e}")

            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    def post_message(self, channel: str, text: str,
                    thread_ts: Optional[str] = None) -> ToolResult:
        """
        Post a message to Slack.

        Args:
            channel: Channel ID or name
            text: Message text
            thread_ts: Optional thread timestamp for replies

        Returns:
            Post result
        """
        start_time = time.time()

        try:
            url = "https://slack.com/api/chat.postMessage"
            payload = {
                "channel": channel,
                "text": text
            }

            if thread_ts:
                payload["thread_ts"] = thread_ts

            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()

            data = response.json()

            if not data.get("ok"):
                raise ValueError(f"Slack API error: {data.get('error')}")

            execution_time = time.time() - start_time

            return ToolResult(
                success=True,
                data={
                    "message_id": data.get("ts"),
                    "channel": data.get("channel")
                },
                metadata={"text_length": len(text)},
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Slack post failed: {e}")

            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )


class LLMAnalysisTool:
    """
    Production LLM analysis tool.
    Uses LLM for text analysis, summarization, classification.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def analyze_text(self, text: str, task: str,
                    max_tokens: int = 500) -> ToolResult:
        """
        Analyze text using LLM.

        Args:
            text: Text to analyze
            task: Analysis task (summarize, classify, extract, etc.)
            max_tokens: Maximum response tokens

        Returns:
            Analysis result
        """
        start_time = time.time()

        try:
            prompt = self._build_analysis_prompt(text, task)

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.1  # Low temperature for analysis
            }

            response = self.session.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            analysis_result = data["choices"][0]["message"]["content"]

            execution_time = time.time() - start_time

            return ToolResult(
                success=True,
                data=analysis_result,
                metadata={
                    "task": task,
                    "model": self.model,
                    "input_tokens": len(text.split()) * 1.3,  # Rough estimate
                    "output_tokens": len(analysis_result.split()) * 1.3
                },
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"LLM analysis failed: {e}")

            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    def _build_analysis_prompt(self, text: str, task: str) -> str:
        """Build analysis prompt based on task type."""
        base_prompts = {
            "summarize": f"Summarize the following text in 2-3 sentences:\n\n{text}",
            "classify": f"Classify the sentiment of this text as positive, negative, or neutral:\n\n{text}",
            "extract": f"Extract the key facts and entities from this text:\n\n{text}",
            "sentiment": f"Analyze the sentiment of this text on a scale of 1-10 (1=very negative, 10=very positive):\n\n{text}",
            "topics": f"Identify the main topics discussed in this text:\n\n{text}"
        }

        return base_prompts.get(task, f"Analyze this text: {text}")

    def batch_analyze(self, texts: List[str], task: str) -> List[ToolResult]:
        """
        Analyze multiple texts in batch.

        Args:
            texts: List of texts to analyze
            task: Analysis task

        Returns:
            List of analysis results
        """
        results = []
        for text in texts:
            result = self.analyze_text(text, task)
            results.append(result)
            time.sleep(0.1)  # Rate limiting

        return results


# Global tool instances
_search_tool = None
_slack_tool = None
_llm_tool = None

def get_search_tool() -> SearchTool:
    """Get global search tool instance."""
    global _search_tool
    if _search_tool is None:
        _search_tool = SearchTool()
    return _search_tool

def get_slack_tool() -> SlackTool:
    """Get global Slack tool instance."""
    global _slack_tool
    if _slack_tool is None:
        _slack_tool = SlackTool()
    return _slack_tool

def get_llm_analysis_tool() -> LLMAnalysisTool:
    """Get global LLM analysis tool instance."""
    global _llm_tool
    if _llm_tool is None:
        _llm_tool = LLMAnalysisTool()
    return _llm_tool

