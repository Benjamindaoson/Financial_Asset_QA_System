"""Web search service."""

import httpx

from typing import List, Optional
from datetime import datetime

from app.config import settings
from app.models import SearchResult, WebSearchResult



class WebSearchService:
    """Web search using Tavily when configured."""

    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"

    async def search(self, query: str, symbols: Optional[List[str]] = None, context: Optional[str] = None, max_results: int = 5) -> WebSearchResult:
        """Advanced financial web search with query expansion and high-signal domain filtering."""
        if not self.api_key:
            return WebSearchResult(results=[], search_query=query)

        # 1. Query Expansion (Intent-Driven)
        enhanced_query = query
        if symbols:
            symbol_str = ", ".join(symbols)
            if symbol_str.lower() not in query.lower():
                enhanced_query = f"{enhanced_query} ({symbol_str})"
                
        # 2. Market Fact Injection 
        if context:
            enhanced_query = f"{enhanced_query} [Market Context: {context}]"
            
        try:
            async with httpx.AsyncClient(timeout=settings.API_TIMEOUT) as client:
                payload = {
                    "api_key": self.api_key,
                    "query": enhanced_query,
                    "max_results": max_results,
                    "search_depth": "advanced", # Use advanced depth for better financial parsing
                    "topic": "news", # Switch to News topic to avoid Wikipedia/old blogs
                    "days": 7, # Restrict to recent 7 days for market dynamics
                    "include_answer": False,
                    "include_raw_content": False,
                    # 3. High-Signal Domain Whitelisting (Silicon Valley standard)
                    "include_domains": [
                        "bloomberg.com", "reuters.com", "cnbc.com", "wsj.com", 
                        "finance.yahoo.com", "ft.com", "barrons.com", "investopedia.com",
                        "seekingalpha.com", "marketwatch.com"
                    ]
                }
                
                response = await client.post(self.base_url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for item in data.get("results", [])[:max_results]:
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            snippet=item.get("content", "")[:250], # Increased snippet length
                            url=item.get("url", ""),
                            published=item.get("published_date"),
                            source="tavily_financial_news",
                        ))

                    return WebSearchResult(results=results, search_query=enhanced_query)

        except Exception:
            pass

        return WebSearchResult(results=[], search_query=query)
