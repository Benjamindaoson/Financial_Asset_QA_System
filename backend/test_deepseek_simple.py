"""
简单测试 DeepSeek AI 分析功能（不依赖 RAG）
"""
import sys
sys.path.insert(0, 'backend')

import asyncio
from app.market.service import MarketDataService
from app.routing import QueryRouter
from app.models.model_adapter import ModelAdapterFactory
from app.models.multi_model import model_manager

async def test_deepseek_streaming():
    print("=" * 60)
    print("测试 DeepSeek 流式输出")
    print("=" * 60)

    # 1. 获取市场数据
    market_service = MarketDataService()

    print("\n[1/3] 获取 AAPL 数据...")
    price = await market_service.get_price("AAPL")
    news = await market_service.get_news("AAPL", days=7)

    print(f"  价格: ${price.price}")
    print(f"  新闻: {len(news)} 篇")

    # 2. 构建分析上下文
    context = f"""用户问题: 分析 AAPL 的最新情况

价格数据:
- 标的: {price.symbol}
- 当前价格: {price.price}

最新新闻 (共{len(news)}篇):"""

    for i, article in enumerate(news[:5], 1):
        context += f"\n{i}. {article.get('title')} (来源: {article.get('source')}, {article.get('provider')})"

    # 3. 调用 DeepSeek 分析
    print("\n[2/3] 调用 DeepSeek AI 分析...")

    system_prompt = """你是一个专业的金融分析师。基于提供的市场数据、新闻和指标，给出深入的分析和见解。

要求:
1. 分析要客观、基于数据
2. 指出关键趋势和风险点
3. 结合新闻事件分析市场情绪
4. 不提供买入/卖出建议，只提供分析
5. 使用简洁专业的语言
6. 分析要有逻辑性和条理性"""

    user_message = f"""{context}

请基于以上数据进行深入分析，包括:
1. 价格走势和技术面分析
2. 基本面和估值分析
3. 新闻事件对市场的影响
4. 风险因素和关注点"""

    # 获取模型配置
    model_config = model_manager.models.get("deepseek-chat")
    if not model_config:
        print("错误: 找不到 deepseek-chat 模型配置")
        return

    # 创建适配器
    adapter = ModelAdapterFactory.create_adapter(model_config)

    # 流式输出
    print("\n[3/3] AI 分析结果:\n")
    print("-" * 60)

    messages = [{"role": "user", "content": user_message}]

    try:
        async for event in adapter.create_message_stream(
            messages=messages,
            system=system_prompt,
            tools=[],
            max_tokens=2000,
        ):
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    print(text, end="", flush=True)

        print("\n" + "-" * 60)
        print("\n✓ 测试完成")

    except Exception as e:
        print(f"\n\n错误: {str(e)}")
        import traceback
        traceback.print_exc()

asyncio.run(test_deepseek_streaming())
