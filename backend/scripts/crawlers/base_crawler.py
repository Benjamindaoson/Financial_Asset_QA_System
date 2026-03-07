"""Base crawler with rate limiting and error handling."""
import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from fake_useragent import UserAgent


class BaseCrawler(ABC):
    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self.ua = UserAgent()
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch(self, url: str) -> str:
        """Fetch URL with rate limiting and error handling."""
        await asyncio.sleep(self.rate_limit)
        headers = {"User-Agent": self.ua.random}

        # Create session if not exists
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            async with self.session.get(url, headers=headers, timeout=30) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return ""

    @abstractmethod
    async def crawl(self) -> List[Dict[str, Any]]:
        """Implement crawling logic in subclass."""
        pass
