from app.market.service import MarketDataService
import asyncio

async def test():
    service = MarketDataService()

    print('=== Testing get_news with Finnhub primary ===')
    news = await service.get_news('AAPL', days=7)

    if news:
        print(f'[OK] Found {len(news)} articles')
        print(f'Provider: {news[0].get("provider")}')
        print(f'\nFirst article:')
        print(f'  Title: {news[0].get("title")[:80]}')
        print(f'  Source: {news[0].get("source")}')
        print(f'  Published: {news[0].get("published_at")}')
        print(f'  URL: {news[0].get("url")[:60]}...')

        print(f'\nSecond article:')
        print(f'  Title: {news[1].get("title")[:80]}')
        print(f'  Source: {news[1].get("source")}')
    else:
        print('[FAIL] No news found')

asyncio.run(test())
