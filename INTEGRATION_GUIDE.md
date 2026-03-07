# Financial API Integration - Setup Guide

## 📋 Overview

This guide will help you integrate 8 free financial APIs into your system:

1. **Alpha Vantage** - Stock data, 25 requests/day
2. **Finnhub** - Stock data, 60 requests/minute
3. **FRED** - Economic indicators, unlimited
4. **Polygon.io** - Stock data, 5 requests/minute
5. **Twelve Data** - Multi-asset data, limited credits
6. **Financial Modeling Prep (FMP)** - Financial statements
7. **CoinGecko** - Crypto prices, no API key needed
8. **Frankfurter** - Forex rates, no API key needed

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Get API Keys

#### Alpha Vantage (Free - 25 requests/day)
1. Visit: https://www.alphavantage.co/support/#api-key
2. Enter your email
3. Get instant API key

#### Finnhub (Free - 60 requests/minute)
1. Visit: https://finnhub.io/register
2. Sign up with email
3. Get API key from dashboard

#### FRED (Free - Unlimited)
1. Visit: https://fred.stlouisfed.org/docs/api/api_key.html
2. Create account
3. Request API key (instant approval)

#### Polygon.io (Free - 5 requests/minute, 15-min delayed)
1. Visit: https://polygon.io/dashboard/signup
2. Sign up
3. Get API key from dashboard

#### Twelve Data (Free - Limited credits)
1. Visit: https://twelvedata.com/pricing
2. Sign up for free plan
3. Get API key

#### Financial Modeling Prep (Free tier available)
1. Visit: https://site.financialmodelingprep.com/developer/docs/
2. Sign up
3. Get API key

#### CoinGecko & Frankfurter
- No API key needed! ✅

### 3. Configure Environment Variables

Add to your `.env` file:

```bash
# Existing keys
ANTHROPIC_API_KEY=your_anthropic_key
REDIS_HOST=localhost
REDIS_PORT=6379

# New Financial API Keys
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
FINNHUB_API_KEY=your_finnhub_key
FRED_API_KEY=your_fred_key
POLYGON_API_KEY=your_polygon_key
TWELVE_DATA_API_KEY=your_twelve_data_key
FMP_API_KEY=your_fmp_key

# No keys needed for CoinGecko and Frankfurter
```

### 4. Test the Integration

```bash
# Run tests
pytest backend/tests/test_api_providers.py -v

# Test specific provider
pytest backend/tests/test_api_providers.py::TestCoinGeckoProvider -v
```

## 📊 Usage Examples

### Basic Stock Price

```python
from app.market.enhanced_service import EnhancedMarketDataService

service = EnhancedMarketDataService()

# Get stock price (tries multiple providers automatically)
price_data = await service.get_price("AAPL")
print(f"Price: ${price_data.price}")
print(f"Source: {price_data.source}")
```

### Cryptocurrency Price

```python
# Bitcoin price (uses CoinGecko - no API key needed)
btc_data = await service.get_price("BTC-USD")
print(f"Bitcoin: ${btc_data.price}")
```

### Forex Rate

```python
# USD to EUR (uses Frankfurter - no API key needed)
forex_data = await service.get_forex_rate("USD", "EUR")
print(f"USD to EUR: {forex_data['rates']['EUR']}")
```

### Economic Indicator

```python
# GDP data (uses FRED)
gdp_data = await service.get_economic_indicator("GDP")
print(f"GDP: {gdp_data}")
```

### Company Information

```python
# Company info with multi-provider fallback
info = await service.get_info("AAPL")
print(f"Name: {info.name}")
print(f"Sector: {info.sector}")
print(f"Market Cap: ${info.market_cap:,}")
```

## 🔧 Integration with Existing System

### Option 1: Replace Existing Service (Recommended)

Update `backend/app/main.py`:

```python
# Before
from app.market.service import MarketDataService

# After
from app.market.enhanced_service import EnhancedMarketDataService as MarketDataService
```

### Option 2: Use Both Services

Keep both services and use enhanced service for new features:

```python
from app.market.service import MarketDataService
from app.market.enhanced_service import EnhancedMarketDataService

# Use original for existing functionality
market_service = MarketDataService()

# Use enhanced for new features
enhanced_service = EnhancedMarketDataService()

# Crypto prices
btc = await enhanced_service.get_price("BTC-USD")

# Economic data
gdp = await enhanced_service.get_economic_indicator("GDP")

# Forex rates
forex = await enhanced_service.get_forex_rate("USD", "EUR")
```

## 📈 API Rate Limits & Strategy

| Provider | Free Limit | Best For | Requires Key |
|----------|------------|----------|--------------|
| **Finnhub** | 60/min | Real-time stocks | ✅ |
| **FRED** | Unlimited | Economic data | ✅ |
| **CoinGecko** | ~50/min | Crypto prices | ❌ |
| **Frankfurter** | No limit | Forex rates | ❌ |
| **Alpha Vantage** | 25/day | Historical data | ✅ |
| **Polygon** | 5/min | End-of-day data | ✅ |
| **Twelve Data** | Limited credits | Multi-asset | ✅ |
| **FMP** | Limited | Financials | ✅ |

### Recommended Strategy

1. **Primary**: Use Finnhub (60/min) for real-time stock quotes
2. **Fallback**: Alpha Vantage, Twelve Data, FMP
3. **Crypto**: CoinGecko (free, no key)
4. **Forex**: Frankfurter (free, no key)
5. **Economic**: FRED (unlimited, free)
6. **Cache**: Redis (60s for prices, 24h for economic data)

## 🎯 Common Use Cases

### 1. Multi-Asset Portfolio Tracking

```python
async def track_portfolio():
    service = EnhancedMarketDataService()

    portfolio = {
        "AAPL": 10,    # 10 shares
        "GOOGL": 5,    # 5 shares
        "BTC-USD": 0.5 # 0.5 Bitcoin
    }

    total_value = 0
    for symbol, quantity in portfolio.items():
        price_data = await service.get_price(symbol)
        value = price_data.price * quantity
        total_value += value
        print(f"{symbol}: ${value:,.2f}")

    print(f"Total Portfolio Value: ${total_value:,.2f}")
```

### 2. Economic Dashboard

```python
async def economic_dashboard():
    service = EnhancedMarketDataService()

    indicators = {
        "GDP": "Gross Domestic Product",
        "UNRATE": "Unemployment Rate",
        "CPIAUCSL": "Inflation (CPI)",
        "FEDFUNDS": "Fed Funds Rate"
    }

    for series_id, name in indicators.items():
        data = await service.get_economic_indicator(series_id)
        if data:
            latest = data['data'][max(data['data'].keys())]
            print(f"{name}: {latest}")
```

### 3. Currency Converter

```python
async def convert_currency(amount: float, from_curr: str, to_curr: str):
    service = EnhancedMarketDataService()

    rate_data = await service.get_forex_rate(from_curr, to_curr)
    rate = rate_data['rates'][to_curr]
    converted = amount * rate

    print(f"{amount} {from_curr} = {converted:.2f} {to_curr}")
    return converted
```

### 4. Market Comparison

```python
async def compare_stocks(symbols: list):
    service = EnhancedMarketDataService()

    for symbol in symbols:
        price = await service.get_price(symbol)
        change = await service.get_change(symbol, days=7)
        info = await service.get_info(symbol)

        print(f"\n{symbol} - {info.name}")
        print(f"Price: ${price.price}")
        print(f"7-day change: {change.change_pct}%")
        print(f"Trend: {change.trend}")
        print(f"P/E Ratio: {info.pe_ratio}")
```

## 🐛 Troubleshooting

### API Key Not Working

```python
# Test individual provider
from app.market.api_providers import FinnhubProvider

provider = FinnhubProvider()
result = await provider.get_quote("AAPL")
print(result)  # Should return data or None
```

### Rate Limit Exceeded

The system automatically falls back to other providers. Check logs:

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Redis Connection Issues

```python
# Check Redis connection
service = EnhancedMarketDataService()
is_connected = service.check_cache()
print(f"Redis connected: {is_connected}")
```

### No Data Returned

```python
# Check all providers
from app.market.api_providers import MultiProviderClient

client = MultiProviderClient()
results = await client.get_stock_quote_multi("AAPL")
print(f"Available providers: {list(results.keys())}")
```

## 📚 Additional Resources

- [API Usage Guide](./backend/app/market/api_usage_guide.py) - Detailed examples
- [API Providers](./backend/app/market/api_providers.py) - Provider implementations
- [Enhanced Service](./backend/app/market/enhanced_service.py) - Main service
- [Tests](./backend/tests/test_api_providers.py) - Test suite

## 🎉 What You Get

✅ **8 Financial APIs** integrated and ready to use
✅ **Multi-provider fallback** for reliability
✅ **Automatic caching** with Redis
✅ **95+ free APIs** documented for future expansion
✅ **Comprehensive tests** included
✅ **Usage examples** for common scenarios
✅ **No-API-key options** (CoinGecko, Frankfurter)

## 🚦 Next Steps

1. Get API keys (start with free ones: Finnhub, FRED, CoinGecko)
2. Add keys to `.env` file
3. Run tests to verify integration
4. Start using enhanced service in your application
5. Monitor API usage and adjust caching strategy

## 💡 Pro Tips

- **Start with free APIs**: CoinGecko and Frankfurter need no keys
- **Use FRED for economic data**: Unlimited and free
- **Finnhub for stocks**: Best free tier (60/min)
- **Cache aggressively**: Reduce API calls
- **Monitor usage**: Stay within rate limits
- **Fallback strategy**: Always have backup providers

---

**Need help?** Check the [detailed API documentation](./docs/FREE_FINANCIAL_APIS.md) or [quick reference](./docs/API_QUICK_REFERENCE.md).
