from app.market.api_providers import TwelveDataProvider
import asyncio

async def test():
    provider = TwelveDataProvider()
    print(f'TwelveData API Key configured: {provider.api_key is not None}')
    if provider.api_key:
        print(f'API Key: {provider.api_key[:10]}...')

    print('\n=== Testing Quote ===')
    quote = await provider.get_quote('AAPL')
    if quote:
        print(f'[OK] Quote test passed')
        print(f'   Symbol: {quote.get("symbol")}')
        print(f'   Close: ${quote.get("close")}')
        print(f'   Open: ${quote.get("open")}')
        print(f'   High: ${quote.get("high")}')
        print(f'   Low: ${quote.get("low")}')
    else:
        print('[FAIL] Quote test failed')

    print('\n=== Testing Time Series ===')
    series = await provider.get_time_series('AAPL', interval='1day', outputsize=5)
    if series:
        print(f'[OK] Time series test passed')
        values = series.get('values', [])
        print(f'   Got {len(values)} data points')
        if values:
            print(f'   Latest: {values[0].get("datetime")} - Close: ${values[0].get("close")}')
    else:
        print('[FAIL] Time series test failed')

asyncio.run(test())
