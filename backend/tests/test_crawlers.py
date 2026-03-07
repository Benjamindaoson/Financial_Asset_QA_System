"""Tests for crawler infrastructure."""
import pytest
from scripts.crawlers.base_crawler import BaseCrawler
from scripts.crawlers.eastmoney_crawler import EastMoneyCrawler


class MockCrawler(BaseCrawler):
    """Mock crawler for testing."""

    async def crawl(self):
        return [{"test": "data"}]


@pytest.mark.asyncio
async def test_base_crawler_context_manager():
    """Test BaseCrawler context manager."""
    async with MockCrawler() as crawler:
        assert crawler.session is not None
    # Session should be closed after exit


@pytest.mark.asyncio
async def test_base_crawler_fetch():
    """Test BaseCrawler fetch method."""
    async with MockCrawler(rate_limit=0.1) as crawler:
        # Test with a simple URL (this will fail but tests error handling)
        html = await crawler.fetch("https://httpbin.org/html")
        assert isinstance(html, str)


@pytest.mark.asyncio
async def test_eastmoney_crawler_initialization():
    """Test EastMoneyCrawler initialization."""
    crawler = EastMoneyCrawler(rate_limit=0.5)
    assert crawler.rate_limit == 0.5
    assert crawler.BASE_URL == "https://baike.eastmoney.com"


@pytest.mark.asyncio
async def test_eastmoney_crawler_parse_article():
    """Test article parsing."""
    crawler = EastMoneyCrawler()

    # Test with empty HTML
    result = crawler._parse_article("")
    assert result is None

    # Test with valid HTML structure
    html = """
    <html>
        <h1 class="wiki-title">股票基础知识</h1>
        <div class="wiki-content">股票是一种有价证券</div>
    </html>
    """
    result = crawler._parse_article(html)
    assert result is not None
    assert result["title"] == "股票基础知识"
    assert "股票" in result["content"]
    assert result["source"] == "EastMoney"
