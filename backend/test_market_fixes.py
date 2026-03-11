#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试市场数据端点修复。"""

import asyncio
import sys
from app.market.service import MarketDataService

async def test_price():
    """测试价格端点。"""
    print("\n=== 测试 1: 获取价格 ===")
    service = MarketDataService()

    symbols = ["AAPL", "TSLA", "0700.HK", "600519.SS"]
    for symbol in symbols:
        result = await service.get_price(symbol)
        status = "OK" if result.price is not None else "FAIL"
        print(f"[{status}] {symbol}: price={result.price}, source={result.source}, latency={result.latency_ms:.0f}ms")

async def test_history():
    """测试历史数据端点。"""
    print("\n=== 测试 2: 获取历史数据 (1年) ===")
    service = MarketDataService()

    symbols = ["AAPL", "TSLA"]
    for symbol in symbols:
        result = await service.get_history(symbol, range_key="1y")
        status = "OK" if len(result.data) >= 200 else "FAIL"
        print(f"[{status}] {symbol}: {len(result.data)} 个数据点, source={result.source}")
        if len(result.data) > 0:
            print(f"   首个数据点: {result.data[0].date}, 最后数据点: {result.data[-1].date}")

async def test_metrics():
    """测试指标端点。"""
    print("\n=== 测试 3: 计算风险指标 ===")
    service = MarketDataService()

    symbols = ["AAPL", "TSLA"]
    for symbol in symbols:
        result = await service.get_metrics(symbol, range_key="1y")
        if result.error:
            print(f"[FAIL] {symbol}: {result.error}")
        else:
            print(f"[OK] {symbol}:")
            print(f"   总收益: {result.total_return_pct:+.2f}%")
            print(f"   年化波动率: {result.annualized_volatility:.2f}%")
            print(f"   最大回撤: {result.max_drawdown_pct:+.2f}%")
            print(f"   夏普比率: {result.sharpe_ratio:.2f}" if result.sharpe_ratio else "   夏普比率: N/A")
            print(f"   数据源: {result.source}")

async def test_compare():
    """测试对比端点。"""
    print("\n=== 测试 4: 对比资产 ===")
    service = MarketDataService()

    result = await service.compare_assets(["AAPL", "TSLA"], range_key="1y")
    print(f"对比 {len(result.symbols)} 个资产:")
    for row in result.rows:
        print(f"  {row.symbol}:")
        print(f"    价格: {row.price}")
        print(f"    总收益: {row.total_return_pct:+.2f}%" if row.total_return_pct is not None else "    总收益: N/A")
        print(f"    波动率: {row.annualized_volatility:.2f}%" if row.annualized_volatility is not None else "    波动率: N/A")
        print(f"    最大回撤: {row.max_drawdown_pct:+.2f}%" if row.max_drawdown_pct is not None else "    最大回撤: N/A")
    print(f"图表数据点: {len(result.chart)}")
    print(f"数据源: {result.source}")

async def test_cache():
    """测试缓存功能。"""
    print("\n=== 测试 5: 缓存功能 ===")
    service = MarketDataService()

    # 第一次请求
    result1 = await service.get_price("AAPL")
    print(f"第一次请求: cache_hit={result1.cache_hit}, latency={result1.latency_ms:.0f}ms")

    # 第二次请求（应该命中缓存）
    result2 = await service.get_price("AAPL")
    print(f"第二次请求: cache_hit={result2.cache_hit}, latency={result2.latency_ms:.0f}ms")

    if result2.cache_hit and result2.latency_ms < result1.latency_ms:
        print("[OK] 缓存工作正常")
    else:
        print("[WARN] 缓存可能未生效")

async def main():
    print("开始测试市场数据端点修复...")
    print("=" * 60)

    try:
        await test_price()
        await test_history()
        await test_metrics()
        await test_compare()
        await test_cache()

        print("\n" + "=" * 60)
        print("测试完成！")
        return 0
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
