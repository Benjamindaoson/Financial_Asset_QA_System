"""
完整的 API 集成测试
验证所有 API 和数据流程
"""
import sys
sys.path.insert(0, 'backend')

from app.config import settings
from app.market.api_providers import FinnhubProvider, NewsAPIProvider, TwelveDataProvider
from app.market.service import MarketDataService
import asyncio

async def test_all_apis():
    print("=" * 60)
    print("完整 API 集成测试")
    print("=" * 60)

    # 1. 验证配置
    print("\n[1/5] 验证 API Keys 配置...")
    print(f"  NewsAPI: {'OK' if settings.NEWSAPI_API_KEY else 'FAIL'}")
    print(f"  Finnhub: {'OK' if settings.FINNHUB_API_KEY else 'FAIL'}")
    print(f"  TwelveData: {'OK' if settings.TWELVE_DATA_API_KEY else 'FAIL'}")
    print(f"  DeepSeek: {'OK' if settings.DEEPSEEK_API_KEY else 'FAIL'}")

    # 2. 测试 Finnhub
    print("\n[2/5] 测试 Finnhub API...")
    finnhub = FinnhubProvider()
    fh_quote = await finnhub.get_quote('AAPL')
    fh_news = await finnhub.get_news('AAPL', from_date='2026-03-01', to_date='2026-03-08')

    if fh_quote:
        print(f"  [OK] Quote: ${fh_quote.get('c')}")
    else:
        print(f"  [FAIL] Quote failed")

    if fh_news:
        print(f"  [OK] News: {len(fh_news)} articles")
    else:
        print(f"  [FAIL] News failed")

    # 3. 测试 NewsAPI
    print("\n[3/5] 测试 NewsAPI...")
    newsapi = NewsAPIProvider()
    na_news = await newsapi.get_stock_news('AAPL', days=7, page_size=10)

    if na_news:
        print(f"  [OK] News: {len(na_news)} articles")
    else:
        print(f"  [FAIL] News failed")

    # 4. 测试 TwelveData
    print("\n[4/5] 测试 TwelveData API...")
    twelvedata = TwelveDataProvider()
    td_quote = await twelvedata.get_quote('AAPL')

    if td_quote:
        print(f"  [OK] Quote: ${td_quote.get('close')}")
    else:
        print(f"  [FAIL] Quote failed")

    # 5. 测试 MarketDataService 组合新闻
    print("\n[5/5] 测试 MarketDataService 组合新闻...")
    service = MarketDataService()

    # 清除缓存
    if service.redis_client:
        service.redis_client.delete('news:AAPL:7')

    combined_news = await service.get_news('AAPL', days=7)

    if combined_news:
        finnhub_count = sum(1 for n in combined_news if n.get('provider') == 'finnhub')
        newsapi_count = sum(1 for n in combined_news if n.get('provider') == 'newsapi')
        print(f"  [OK] 总计: {len(combined_news)} 篇新闻")
        print(f"    - Finnhub: {finnhub_count} 篇")
        print(f"    - NewsAPI: {newsapi_count} 篇")
    else:
        print(f"  [FAIL] 组合新闻失败")

    # 总结
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

    # 显示第一条新闻示例
    if combined_news:
        print("\n示例新闻:")
        news = combined_news[0]
        print(f"  标题: {news.get('title')[:60]}...")
        print(f"  来源: {news.get('source')} ({news.get('provider')})")
        print(f"  时间: {news.get('published_at')}")

asyncio.run(test_all_apis())
