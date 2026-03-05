"""
Web Search Service - Tavily API integration
"""
import httpx
from typing import Optional
from app.config import settings
from app.models import WebSearchResult, SearchResult


class WebSearchService:
    """Web search using Tavily API"""

    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"

    async def search(self, query: str, max_results: int = 5) -> WebSearchResult:
        """
        Search web for news and information
        Returns structured summaries
        """
        if not self.api_key:
            # Return empty result if API key not configured
            return WebSearchResult(
                results=[],
                search_query=query
            )

        try:
            async with httpx.AsyncClient(timeout=settings.API_TIMEOUT) as client:
                response = await client.post(
                    self.base_url,
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                        "include_answer": False,
                        "include_raw_content": False
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for item in data.get("results", []):
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            snippet=item.get("content", "")[:200],
                            url=item.get("url", ""),
                            published=item.get("published_date")
                        ))

                    return WebSearchResult(
                        results=results,
                        search_query=query
                    )
        except Exception:
            pass

        # Return empty result on error
        return WebSearchResult(
            results=[],
            search_query=query
        )
