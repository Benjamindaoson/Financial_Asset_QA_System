import sys
import os
sys.path.insert(0, 'backend')
os.chdir('backend')

from app.market.api_providers import FinnhubProvider
import asyncio

async def test():
    provider = FinnhubProvider()
    print(f'Finnhub API Key configured: {provider.api_key is not None}')
    print(f'API Key: {provider.api_key[:10]}...' if provider.api_key else 'No key')

    # Test quote
    quote = await provider.get_quote('AAPL')
    if quote:
        print(f'[OK] Quote test passed')
        print(f'   Current price: ${quote.get("c")}')
        print(f'   Change: {quote.get("d")}')
    else:
        print('[FAIL] Quote test failed')

    # Test company profile
    profile = await provider.get_company_profile('AAPL')
    if profile:
        print(f'[OK] Profile test passed')
        print(f'   Name: {profile.get("name")}')
        print(f'   Industry: {profile.get("finnhubIndustry")}')
    else:
        print('[FAIL] Profile test failed')

    # Test news
    news = await provider.get_news('AAPL', from_date='2026-03-01', to_date='2026-03-08')
    if news:
        print(f'[OK] News test passed')
        print(f'   Found {len(news)} articles')
        if news:
            print(f'   Latest: {news[0].get("headline", "")[:60]}...')
    else:
        print('[FAIL] News test failed')

asyncio.run(test())
