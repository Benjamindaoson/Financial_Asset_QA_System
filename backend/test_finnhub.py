from app.market.api_providers import FinnhubProvider
import asyncio

async def test():
    provider = FinnhubProvider()
    print(f'Finnhub API Key configured: {provider.api_key is not None}')
    if provider.api_key:
        print(f'API Key: {provider.api_key[:10]}...')

    print('\n=== Testing Quote ===')
    quote = await provider.get_quote('AAPL')
    if quote:
        print(f'[OK] Quote test passed')
        print(f'   Current price: ${quote.get("c")}')
        print(f'   Change: {quote.get("d")}')
        print(f'   High: ${quote.get("h")}')
        print(f'   Low: ${quote.get("l")}')
    else:
        print('[FAIL] Quote test failed')

    print('\n=== Testing Company Profile ===')
    profile = await provider.get_company_profile('AAPL')
    if profile:
        print(f'[OK] Profile test passed')
        print(f'   Name: {profile.get("name")}')
        print(f'   Industry: {profile.get("finnhubIndustry")}')
        print(f'   Market Cap: {profile.get("marketCapitalization")}')
    else:
        print('[FAIL] Profile test failed')

    print('\n=== Testing News ===')
    news = await provider.get_news('AAPL', from_date='2026-03-01', to_date='2026-03-08')
    if news:
        print(f'[OK] News test passed')
        print(f'   Found {len(news)} articles')
        if news:
            print(f'   Latest: {news[0].get("headline", "")[:80]}')
            print(f'   Source: {news[0].get("source", "")}')
    else:
        print('[FAIL] News test failed')

asyncio.run(test())
