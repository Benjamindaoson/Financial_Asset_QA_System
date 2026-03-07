"""
Financial API integration guide and usage examples.
"""

# ============================================================================
# API KEYS SETUP
# ============================================================================
# Add these to your .env file:

# ALPHA_VANTAGE_API_KEY=your_key_here          # Free: 25 requests/day
# FINNHUB_API_KEY=your_key_here                # Free: 60 requests/minute
# FRED_API_KEY=your_key_here                   # Free: Unlimited
# POLYGON_API_KEY=your_key_here                # Free: 5 requests/minute (15-min delayed)
# TWELVE_DATA_API_KEY=your_key_here            # Free: Limited daily credits
# FMP_API_KEY=your_key_here                    # Free tier available

# No API key needed:
# - CoinGecko (crypto prices)
# - Frankfurter (forex rates)

# ============================================================================
# USAGE EXAMPLES
# ============================================================================

from app.market.enhanced_service import EnhancedMarketDataService
from app.market.api_providers import MultiProviderClient

# Initialize services
market_service = EnhancedMarketDataService()
multi_provider = MultiProviderClient()


# ============================================================================
# 1. STOCK PRICES (Multi-provider fallback)
# ============================================================================

async def get_stock_price_example():
    """Get stock price with automatic fallback across providers."""

    # Single provider - tries yfinance, then Finnhub, Alpha Vantage, etc.
    price_data = await market_service.get_price("AAPL")
    print(f"Price: ${price_data.price}")
    print(f"Source: {price_data.source}")
    print(f"Latency: {price_data.latency_ms}ms")

    # Multi-provider comparison
    all_quotes = await multi_provider.get_stock_quote_multi("AAPL")
    for provider, data in all_quotes.items():
        print(f"{provider}: {data}")


# ============================================================================
# 2. CRYPTOCURRENCY PRICES (CoinGecko - Free, no API key)
# ============================================================================

async def get_crypto_price_example():
    """Get cryptocurrency prices from CoinGecko."""

    # Bitcoin price
    btc_data = await market_service.get_price("BTC-USD")
    print(f"Bitcoin: ${btc_data.price}")

    # Direct CoinGecko access
    btc_info = await multi_provider.coingecko.get_price("bitcoin")
    print(f"BTC Price: ${btc_info['usd']}")
    print(f"24h Change: {btc_info.get('usd_24h_change')}%")
    print(f"Market Cap: ${btc_info.get('usd_market_cap')}")

    # Ethereum
    eth_info = await multi_provider.coingecko.get_price("ethereum")
    print(f"ETH Price: ${eth_info['usd']}")


# ============================================================================
# 3. FOREX RATES (Frankfurter - Free, no API key)
# ============================================================================

async def get_forex_rate_example():
    """Get foreign exchange rates from Frankfurter."""

    # USD to EUR
    forex_data = await market_service.get_forex_rate("USD", "EUR")
    print(f"USD to EUR: {forex_data['rates']['EUR']}")

    # Multiple currencies
    rates = await multi_provider.frankfurter.get_latest_rates("USD", "EUR,GBP,JPY,CNY")
    print(f"Exchange rates: {rates['rates']}")

    # Historical rate
    historical = await multi_provider.frankfurter.get_historical_rates("2024-01-01", "USD", "EUR")
    print(f"Historical rate: {historical}")


# ============================================================================
# 4. ECONOMIC INDICATORS (FRED - Free, unlimited)
# ============================================================================

async def get_economic_data_example():
    """Get economic indicators from FRED."""

    # GDP
    gdp_data = await market_service.get_economic_indicator("GDP")
    print(f"GDP data: {gdp_data}")

    # Unemployment rate
    unemployment = await multi_provider.fred.get_series("UNRATE")
    print(f"Latest unemployment rate: {unemployment.iloc[-1]}%")

    # Inflation (CPI)
    cpi = await multi_provider.fred.get_series("CPIAUCSL")
    print(f"Latest CPI: {cpi.iloc[-1]}")

    # Federal Funds Rate
    fed_rate = await multi_provider.fred.get_series("FEDFUNDS")
    print(f"Fed Funds Rate: {fed_rate.iloc[-1]}%")

    # Series info
    series_info = await multi_provider.fred.get_series_info("GDP")
    print(f"Series info: {series_info}")


# ============================================================================
# 5. COMPANY INFORMATION (Multi-provider)
# ============================================================================

async def get_company_info_example():
    """Get company information with fallback."""

    # Comprehensive company info
    info = await market_service.get_info("AAPL")
    print(f"Name: {info.name}")
    print(f"Sector: {info.sector}")
    print(f"Industry: {info.industry}")
    print(f"Market Cap: ${info.market_cap:,}")
    print(f"P/E Ratio: {info.pe_ratio}")
    print(f"Description: {info.description}")

    # Finnhub company profile
    fh_profile = await multi_provider.finnhub.get_company_profile("AAPL")
    print(f"Finnhub profile: {fh_profile}")

    # Alpha Vantage overview
    av_overview = await multi_provider.alpha_vantage.get_company_overview("AAPL")
    print(f"Alpha Vantage overview: {av_overview}")


# ============================================================================
# 6. HISTORICAL DATA
# ============================================================================

async def get_historical_data_example():
    """Get historical price data."""

    # 30 days of history
    history = await market_service.get_history("AAPL", days=30)
    print(f"Data points: {len(history.data)}")
    for point in history.data[-5:]:  # Last 5 days
        print(f"{point.date}: Close=${point.close}, Volume={point.volume:,}")

    # Price change over period
    change = await market_service.get_change("AAPL", days=7)
    print(f"7-day change: {change.change_pct}%")
    print(f"Trend: {change.trend}")


# ============================================================================
# 7. COMPANY NEWS (Finnhub)
# ============================================================================

async def get_company_news_example():
    """Get company news from Finnhub."""

    from datetime import datetime, timedelta

    # Last 7 days of news
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    news = await multi_provider.finnhub.get_news("AAPL", from_date, to_date)
    if news:
        for article in news[:5]:  # First 5 articles
            print(f"Headline: {article['headline']}")
            print(f"Source: {article['source']}")
            print(f"URL: {article['url']}")
            print(f"Summary: {article['summary'][:100]}...")
            print("---")


# ============================================================================
# 8. FINANCIAL STATEMENTS (FMP)
# ============================================================================

async def get_financial_statements_example():
    """Get financial statements from FMP."""

    # Income statement
    income_stmt = await multi_provider.fmp.get_income_statement("AAPL", period="annual", limit=3)
    if income_stmt:
        for year in income_stmt:
            print(f"Year: {year['date']}")
            print(f"Revenue: ${year['revenue']:,}")
            print(f"Net Income: ${year['netIncome']:,}")
            print(f"EPS: ${year['eps']}")
            print("---")


# ============================================================================
# 9. BATCH OPERATIONS
# ============================================================================

async def batch_operations_example():
    """Fetch data for multiple symbols in parallel."""

    import asyncio

    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]

    # Fetch all prices in parallel
    tasks = [market_service.get_price(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)

    for symbol, result in zip(symbols, results):
        print(f"{symbol}: ${result.price} ({result.source})")


# ============================================================================
# 10. ERROR HANDLING
# ============================================================================

async def error_handling_example():
    """Handle API errors gracefully."""

    # Invalid symbol
    result = await market_service.get_price("INVALID_SYMBOL")
    if result.error:
        print(f"Error: {result.error}")
        print(f"Source: {result.source}")

    # Check if data is available
    if result.price:
        print(f"Price: ${result.price}")
    else:
        print("No price data available")


# ============================================================================
# COMMON FRED SERIES IDs
# ============================================================================

FRED_SERIES = {
    # GDP & Growth
    "GDP": "Gross Domestic Product",
    "GDPC1": "Real GDP",
    "A191RL1Q225SBEA": "GDP Growth Rate",

    # Employment
    "UNRATE": "Unemployment Rate",
    "PAYEMS": "Total Nonfarm Payrolls",
    "CIVPART": "Labor Force Participation Rate",

    # Inflation
    "CPIAUCSL": "Consumer Price Index",
    "CPILFESL": "Core CPI (ex food & energy)",
    "PCEPI": "Personal Consumption Expenditures Price Index",

    # Interest Rates
    "FEDFUNDS": "Federal Funds Rate",
    "DGS10": "10-Year Treasury Rate",
    "DGS2": "2-Year Treasury Rate",
    "MORTGAGE30US": "30-Year Mortgage Rate",

    # Money Supply
    "M1SL": "M1 Money Supply",
    "M2SL": "M2 Money Supply",

    # Housing
    "HOUST": "Housing Starts",
    "CSUSHPISA": "Case-Shiller Home Price Index",

    # Consumer
    "RSXFS": "Retail Sales",
    "UMCSENT": "Consumer Sentiment Index",

    # Manufacturing
    "INDPRO": "Industrial Production Index",
    "NAPM": "ISM Manufacturing PMI",
}


# ============================================================================
# COINGECKO COIN IDs (Popular cryptocurrencies)
# ============================================================================

COINGECKO_COINS = {
    "bitcoin": "Bitcoin",
    "ethereum": "Ethereum",
    "tether": "Tether",
    "binancecoin": "BNB",
    "solana": "Solana",
    "ripple": "XRP",
    "cardano": "Cardano",
    "dogecoin": "Dogecoin",
    "polkadot": "Polkadot",
    "avalanche-2": "Avalanche",
}


# ============================================================================
# API RATE LIMITS & BEST PRACTICES
# ============================================================================

"""
RATE LIMITS:
- Alpha Vantage: 25 requests/day (free)
- Finnhub: 60 requests/minute (free)
- FRED: Unlimited (free)
- Polygon: 5 requests/minute (free, 15-min delayed)
- Twelve Data: Limited daily credits (free)
- CoinGecko: ~50 requests/minute (free, no key)
- Frankfurter: No strict limit (free, no key)

BEST PRACTICES:
1. Use caching (Redis) to minimize API calls
2. Implement exponential backoff for retries
3. Use multi-provider fallback for reliability
4. Batch requests when possible
5. Monitor API usage to stay within limits
6. Use free APIs (CoinGecko, Frankfurter, FRED) when possible
7. Cache economic data for 24 hours (changes infrequently)
8. Cache stock prices for 60 seconds (real-time needs)
9. Cache company info for 7 days (rarely changes)
"""


# ============================================================================
# INTEGRATION WITH EXISTING SYSTEM
# ============================================================================

"""
To integrate with your existing system:

1. Update backend/app/market/service.py:
   - Import EnhancedMarketDataService
   - Replace MarketDataService with EnhancedMarketDataService

2. Update backend/app/agent/core.py:
   - Add new tools for economic data, forex, crypto

3. Add API keys to .env file

4. Install dependencies:
   pip install -r requirements.txt

5. Test the integration:
   pytest backend/tests/test_api_providers.py
"""
