#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""简单验证市场数据修复。"""

import asyncio
from app.market.service import MarketDataService

async def main():
    print("验证市场数据服务修复...")
    service = MarketDataService()

    # 测试 1: 检查数据源优先级
    print("\n1. 检查数据源配置:")
    print(f"   - yfinance 超时: {service.TIMEOUT_YFINANCE}s")
    print(f"   - akshare 超时: {service.TIMEOUT_AKSHARE}s")
    print(f"   - stooq 超时: {service.TIMEOUT_STOOQ}s")
    print(f"   - 内存缓存: {'已启用' if hasattr(service, '_memory_cache') else '未启用'}")

    # 测试 2: 检查 A股识别
    print("\n2. 检查 A股识别:")
    test_symbols = ["600519.SS", "000001.SZ", "AAPL", "0700.HK"]
    for symbol in test_symbols:
        is_a = service._is_china_a_stock(symbol)
        is_hk = service._is_hk_stock(symbol)
        print(f"   {symbol}: A股={is_a}, 港股={is_hk}")

    # 测试 3: 检查 range_key 映射
    print("\n3. 检查 range_key 映射:")
    for key in ["1d", "5d", "1m", "3m", "6m", "ytd", "1y", "5y"]:
        period, days = service._range_to_period(key, 30)
        print(f"   {key} -> period={period}, days={days}")

    # 测试 4: 测试缓存（不需要网络）
    print("\n4. 测试内存缓存:")
    service._set_cache("test_key", {"value": 123}, 60)
    cached = service._get_cache("test_key")
    print(f"   写入缓存: OK")
    print(f"   读取缓存: {'OK' if cached and cached.get('value') == 123 else 'FAIL'}")

    print("\n所有基础功能检查完成！")
    print("\n注意: 由于 yfinance 速率限制，实际数据获取测试需要等待或使用备用数据源。")

if __name__ == "__main__":
    asyncio.run(main())
