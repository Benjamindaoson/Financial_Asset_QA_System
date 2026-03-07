"""EastMoney financial knowledge crawler."""
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_crawler import BaseCrawler


class EastMoneyCrawler(BaseCrawler):
    """Crawler for EastMoney financial encyclopedia."""

    BASE_URL = "https://baike.eastmoney.com"

    async def crawl(self) -> List[Dict[str, Any]]:
        """Crawl financial knowledge from EastMoney."""
        results = []

        # Sample categories to crawl
        categories = [
            "/wiki/股票",
            "/wiki/基金",
            "/wiki/债券",
            "/wiki/期货",
            "/wiki/外汇"
        ]

        for category in categories:
            url = f"{self.BASE_URL}{category}"
            html = await self.fetch(url)

            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")

            # Extract article links
            links = soup.find_all("a", class_="wiki-link")

            for link in links[:20]:  # Limit per category
                article_url = self.BASE_URL + link.get("href", "")
                article_html = await self.fetch(article_url)

                if article_html:
                    article_data = self._parse_article(article_html)
                    if article_data:
                        results.append(article_data)

        return results

    def _parse_article(self, html: str) -> Dict[str, Any]:
        """Parse article content."""
        soup = BeautifulSoup(html, "lxml")

        title = soup.find("h1", class_="wiki-title")
        content = soup.find("div", class_="wiki-content")

        if not title or not content:
            return None

        return {
            "title": title.get_text(strip=True),
            "content": content.get_text(strip=True),
            "source": "EastMoney",
            "type": "financial_knowledge"
        }
