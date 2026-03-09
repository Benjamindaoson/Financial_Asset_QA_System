"""
测试 DeepSeek AI 深度分析功能
"""
import sys
sys.path.insert(0, 'backend')

import asyncio
from app.agent.core import AgentCore

async def test_deepseek_analysis():
    print("=" * 60)
    print("测试 DeepSeek AI 深度分析")
    print("=" * 60)

    agent = AgentCore()

    # 测试查询
    query = "分析 AAPL 的最新情况"

    print(f"\n查询: {query}\n")
    print("-" * 60)

    # 收集所有事件
    events = []
    tool_data_received = False
    analysis_started = False

    async for event in agent.run(query):
        events.append(event)

        if event.type == "model_selected":
            print(f"[模型选择] {event.model}")

        elif event.type == "tool_start":
            print(f"[工具启动] {event.display}")

        elif event.type == "tool_data":
            tool_data_received = True
            print(f"[工具数据] {event.tool}")
            if event.tool == "get_news":
                news_count = event.data.get("count", 0)
                print(f"  -> 获取到 {news_count} 篇新闻")

        elif event.type == "chunk":
            if not analysis_started:
                print("\n[AI 分析开始]")
                analysis_started = True
            print(event.text, end="", flush=True)

        elif event.type == "done":
            print("\n\n[完成]")
            print(f"  验证状态: {event.verified}")
            print(f"  置信度: {event.data.get('confidence', {}).get('level')}")
            print(f"  输入 tokens: {event.tokens_input}")
            print(f"  输出 tokens: {event.tokens_output}")

        elif event.type == "error":
            print(f"\n[错误] {event.message}")

    print("\n" + "=" * 60)
    print("测试总结:")
    print(f"  总事件数: {len(events)}")
    print(f"  工具数据已接收: {tool_data_received}")
    print(f"  AI 分析已执行: {analysis_started}")
    print("=" * 60)

asyncio.run(test_deepseek_analysis())
