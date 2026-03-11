"""Web search service."""

import httpx

from app.config import settings
from app.models import SearchResult, WebSearchResult


class WebSearchService:
    """Web search using Tavily when configured."""

    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"

    async def search(self, query: str, max_results: int = 5) -> WebSearchResult:
        """Search the web for recent news and background."""
        if not self.api_key:
            return WebSearchResult(results=[], search_query=query)

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
                            published=item.get("published_date"),
                            source="tavily",
                        ))

                    return WebSearchResult(results=results, search_query=query)
        except Exception:
            pass

        return WebSearchResult(results=[], search_query=query)
