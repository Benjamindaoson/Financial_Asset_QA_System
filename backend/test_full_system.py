"""
完整系统测试 - 测试多模型集成的端到端功能
Full System Test - End-to-end testing of multi-model integration
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.agent.core import AgentCore
from app.models.multi_model import QueryComplexity


async def test_agent_with_auto_selection():
    """测试自动模型选择"""
    print("\n" + "="*60)
    print("测试1: 自动模型选择")
    print("="*60)

    agent = AgentCore()

    test_queries = [
        ("苹果股价", QueryComplexity.SIMPLE, "deepseek-chat"),
        ("特斯拉最近一个月的走势", QueryComplexity.MEDIUM, "claude-opus"),
        ("分析美联储加息对科技股的影响", QueryComplexity.COMPLEX, "claude-opus"),
    ]

    for query, expected_complexity, expected_model in test_queries:
        print(f"\n查询: '{query}'")
        print(f"期望复杂度: {expected_complexity}")
        print(f"期望模型: {expected_model}")

        # 分类查询
        actual_complexity = agent.model_manager.classify_query(query)
        print(f"实际复杂度: {actual_complexity}")

        # 选择模型
        selected_model = agent._select_model(query)
        print(f"选择模型: {selected_model}")

        status = "[OK]" if selected_model == expected_model else "[WARN]"
        print(f"{status} 模型选择")


async def test_agent_with_manual_selection():
    """测试手动模型选择"""
    print("\n" + "="*60)
    print("测试2: 手动模型选择")
    print("="*60)

    agent = AgentCore()

    # 测试强制使用特定模型
    test_cases = [
        ("苹果股价", "claude-opus"),
        ("苹果股价", "deepseek-chat"),
    ]

    for query, model in test_cases:
        print(f"\n查询: '{query}'")
        print(f"指定模型: {model}")

        # 模拟运行（不实际调用API）
        if model in agent.model_manager.models:
            print(f"[OK] 模型 {model} 可用")
        else:
            print(f"[ERROR] 模型 {model} 不可用")


async def test_model_availability():
    """测试模型可用性"""
    print("\n" + "="*60)
    print("测试3: 模型可用性")
    print("="*60)

    agent = AgentCore()

    models = agent.get_available_models()
    print(f"\n可用模型数量: {len(models)}")

    for model in models:
        print(f"\n模型: {model['name']}")
        print(f"  提供商: {model['provider']}")
        print(f"  模型ID: {model['model']}")
        print(f"  支持工具: {model['supports_tool_use']}")
        print(f"  输入成本: ${model['cost_per_1m_input']}/M")
        print(f"  输出成本: ${model['cost_per_1m_output']}/M")
        print(f"  优先级: {model['priority']}")


async def test_usage_tracking():
    """测试使用统计"""
    print("\n" + "="*60)
    print("测试4: 使用统计")
    print("="*60)

    agent = AgentCore()

    # 模拟一些使用
    agent.model_manager.record_usage("claude-opus", 1000, 500, True)
    agent.model_manager.record_usage("deepseek-chat", 2000, 1000, True)

    report = agent.get_usage_report()

    print(f"\n总请求数: {report['total_requests']}")
    print(f"总成本: ${report['total_cost']:.4f}")

    print("\n各模型统计:")
    for model_name, stats in report['models'].items():
        if stats['total_requests'] > 0:
            print(f"\n{model_name}:")
            print(f"  请求数: {stats['total_requests']}")
            print(f"  输入tokens: {stats['total_tokens_input']:,}")
            print(f"  输出tokens: {stats['total_tokens_output']:,}")
            print(f"  成本: ${stats['total_cost']:.4f}")
            print(f"  错误数: {stats['errors']}")


async def test_cost_comparison():
    """测试成本对比"""
    print("\n" + "="*60)
    print("测试5: 成本对比分析")
    print("="*60)

    agent = AgentCore()

    # 模拟1000个查询的成本
    queries = {
        QueryComplexity.SIMPLE: 800,    # 80%
        QueryComplexity.MEDIUM: 150,    # 15%
        QueryComplexity.COMPLEX: 50,    # 5%
    }

    avg_tokens_input = 1000
    avg_tokens_output = 500

    # 纯Claude成本
    claude_config = agent.model_manager.models["claude-opus"]
    claude_cost = sum(
        count * (
            avg_tokens_input / 1_000_000 * claude_config.cost_per_1m_input +
            avg_tokens_output / 1_000_000 * claude_config.cost_per_1m_output
        )
        for count in queries.values()
    )

    # 纯DeepSeek成本
    deepseek_cost = 0
    if "deepseek-chat" in agent.model_manager.models:
        deepseek_config = agent.model_manager.models["deepseek-chat"]
        deepseek_cost = sum(
            count * (
                avg_tokens_input / 1_000_000 * deepseek_config.cost_per_1m_input +
                avg_tokens_output / 1_000_000 * deepseek_config.cost_per_1m_output
            )
            for count in queries.values()
        )

    # 混合方案成本
    hybrid_cost = 0
    for complexity, count in queries.items():
        model_name = agent.model_manager.select_model(complexity)
        model_config = agent.model_manager.models[model_name]
        hybrid_cost += count * (
            avg_tokens_input / 1_000_000 * model_config.cost_per_1m_input +
            avg_tokens_output / 1_000_000 * model_config.cost_per_1m_output
        )

    print(f"\n假设场景: 1000个查询")
    print(f"  简单查询: {queries[QueryComplexity.SIMPLE]} (80%)")
    print(f"  中等查询: {queries[QueryComplexity.MEDIUM]} (15%)")
    print(f"  复杂查询: {queries[QueryComplexity.COMPLEX]} (5%)")
    print(f"  平均tokens: {avg_tokens_input}输入 + {avg_tokens_output}输出")

    print(f"\n成本对比:")
    print(f"  纯Claude:    ${claude_cost:.2f}")
    if deepseek_cost > 0:
        print(f"  纯DeepSeek:  ${deepseek_cost:.2f} (节省 {(1-deepseek_cost/claude_cost)*100:.1f}%)")
    print(f"  混合方案:    ${hybrid_cost:.2f} (节省 {(1-hybrid_cost/claude_cost)*100:.1f}%)")

    print(f"\n月度成本估算 (30天, 每天1000查询):")
    print(f"  纯Claude:    ${claude_cost*30:.2f}/月")
    if deepseek_cost > 0:
        print(f"  纯DeepSeek:  ${deepseek_cost*30:.2f}/月")
    print(f"  混合方案:    ${hybrid_cost*30:.2f}/月")


async def main():
    """运行所有测试"""
    print("="*60)
    print("Financial Asset QA System - 完整系统测试")
    print("="*60)

    try:
        await test_agent_with_auto_selection()
        await test_agent_with_manual_selection()
        await test_model_availability()
        await test_usage_tracking()
        await test_cost_comparison()

        print("\n" + "="*60)
        print("[OK] 所有测试完成")
        print("="*60)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
