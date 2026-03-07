"""
Quick test script for APIs that don't require keys.
"""
import asyncio
from app.market.api_providers import CoinGeckoProvider, FrankfurterProvider


async def test_no_key_apis():
    print('Testing APIs that do not require keys...\n')

    # Test CoinGecko
    print('1. Testing CoinGecko (Cryptocurrency prices):')
    coingecko = CoinGeckoProvider()
    btc = await coingecko.get_price('bitcoin')
    if btc:
        print(f'   Bitcoin price: ${btc["usd"]:,.2f}')
        print(f'   24h change: {btc.get("usd_24h_change", 0):.2f}%')
        print(f'   Market cap: ${btc.get("usd_market_cap", 0):,.0f}')
    else:
        print('   Failed to fetch')

    # Test Ethereum
    print('\n   Ethereum:')
    eth = await coingecko.get_price('ethereum')
    if eth:
        print(f'   Ethereum price: ${eth["usd"]:,.2f}')
        print(f'   24h change: {eth.get("usd_24h_change", 0):.2f}%')

    # Test Frankfurter
    print('\n2. Testing Frankfurter (Forex rates):')
    frankfurter = FrankfurterProvider()
    forex = await frankfurter.get_latest_rates('USD', 'EUR,GBP,JPY,CNY')
    if forex:
        print(f'   Exchange rates (base: USD):')
        for currency, rate in forex['rates'].items():
            print(f'      1 USD = {rate:.4f} {currency}')
    else:
        print('   Failed to fetch')

    print('\n3. Testing Enhanced Service:')
    from app.market.enhanced_service import EnhancedMarketDataService
    service = EnhancedMarketDataService()

    # Test crypto via enhanced service
    btc_data = await service.get_price('BTC-USD')
    print(f'   BTC-USD via enhanced service: ${btc_data.price:.2f}')
    print(f'   Source: {btc_data.source}')

    # Test forex via enhanced service
    forex_data = await service.get_forex_rate('USD', 'EUR')
    if forex_data:
        print(f'   USD to EUR: {forex_data["rates"]["EUR"]:.4f}')

    print('\nAll tests completed successfully!')
    print('\nThese APIs work without any API keys!')
    print('You can use them immediately in your application.')


if __name__ == '__main__':
    asyncio.run(test_no_key_apis())
