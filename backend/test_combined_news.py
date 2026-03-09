from app.market.service import MarketDataService
import asyncio

async def test():
    service = MarketDataService()

    # Clear cache first
    if service.redis_client:
        service.redis_client.delete('news:AAPL:7')
        print('Cache cleared')

    print('\n=== Testing get_news with BOTH APIs ===')
    news = await service.get_news('AAPL', days=7)

    if news:
        print(f'[OK] Found {len(news)} articles total')

        # Count by provider
        finnhub_count = sum(1 for n in news if n.get('provider') == 'finnhub')
        newsapi_count = sum(1 for n in news if n.get('provider') == 'newsapi')

        print(f'  - Finnhub: {finnhub_count} articles')
        print(f'  - NewsAPI: {newsapi_count} articles')

        print(f'\nFirst 3 articles:')
        for i, article in enumerate(news[:3], 1):
            print(f'\n{i}. [{article.get("provider")}] {article.get("title")[:70]}')
            print(f'   Source: {article.get("source")}')
            print(f'   Published: {article.get("published_at")}')
    else:
        print('[FAIL] No news found')

asyncio.run(test())
