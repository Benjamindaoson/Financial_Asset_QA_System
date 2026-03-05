"""
快速系统测试 - 不加载重型模型
Quick System Test - Without loading heavy models
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 设置环境变量避免加载模型
os.environ['SKIP_MODEL_LOADING'] = '1'

from app.models.multi_model import model_manager, QueryComplexity


def test_configuration():
    """测试配置"""
    print("\n" + "="*60)
    print("测试1: 配置检查")
    print("="*60)

    print(f"\n已加载模型数量: {len(model_manager.models)}")

    for name, config in model_manager.models.items():
        print(f"\n模型: {name}")
        print(f"  提供商: {config.provider}")
        print(f"  模型名: {config.model_name}")
        print(f"  支持工具: {config.supports_tool_use}")
        print(f"  输入成本: ${config.cost_per_1m_input}/M tokens")
        print(f"  输出成本: ${config.cost_per_1m_output}/M tokens")
        print(f"  优先级: {config.priority}")


def test_query_routing():
    """测试查询路由"""
    print("\n" + "="*60)
    print("测试2: 查询路由")
    print("="*60)

    test_cases = [
        ("苹果股价", QueryComplexity.SIMPLE),
        ("茅台涨了多少", QueryComplexity.SIMPLE),
        ("特斯拉最近一个月的走势", QueryComplexity.MEDIUM),
        ("分析美联储加息对科技股的影响", QueryComplexity.COMPLEX),
        ("对比微软和谷歌的财务状况", QueryComplexity.COMPLEX),
    ]

    for query, expected_complexity in test_cases:
        actual_complexity = model_manager.classify_query(query)
        selected_model = model_manager.select_model(actual_complexity)

        status = "[OK]" if actual_complexity == expected_complexity else "[WARN]"
        print(f"\n{status} '{query}'")
        print(f"  复杂度: {actual_complexity} (期望: {expected_complexity})")
        print(f"  选择模型: {selected_model}")


def test_cost_calculation():
    """测试成本计算"""
    print("\n" + "="*60)
    print("测试3: 成本计算")
    print("="*60)

    # 模拟1000个查询
    queries = {
        QueryComplexity.SIMPLE: 800,
        QueryComplexity.MEDIUM: 150,
        QueryComplexity.COMPLEX: 50,
    }

    avg_tokens_input = 1000
    avg_tokens_output = 500

    print(f"\n假设场景:")
    print(f"  总查询数: 1000")
    print(f"  简单查询: {queries[QueryComplexity.SIMPLE]} (80%)")
    print(f"  中等查询: {queries[QueryComplexity.MEDIUM]} (15%)")
    print(f"  复杂查询: {queries[QueryComplexity.COMPLEX]} (5%)")
    print(f"  平均tokens: {avg_tokens_input}输入 + {avg_tokens_output}输出")

    # 计算各方案成本
    costs = {}

    # 纯Claude
    if "claude-opus" in model_manager.models:
        config = model_manager.models["claude-opus"]
        costs["claude"] = sum(queries.values()) * (
            avg_tokens_input / 1_000_000 * config.cost_per_1m_input +
            avg_tokens_output / 1_000_000 * config.cost_per_1m_output
        )

    # 纯DeepSeek
    if "deepseek-chat" in model_manager.models:
        config = model_manager.models["deepseek-chat"]
        costs["deepseek"] = sum(queries.values()) * (
            avg_tokens_input / 1_000_000 * config.cost_per_1m_input +
            avg_tokens_output / 1_000_000 * config.cost_per_1m_output
        )

    # 混合方案
    hybrid_cost = 0
    for complexity, count in queries.items():
        model_name = model_manager.select_model(complexity)
        if model_name:
            config = model_manager.models[model_name]
            hybrid_cost += count * (
                avg_tokens_input / 1_000_000 * config.cost_per_1m_input +
                avg_tokens_output / 1_000_000 * config.cost_per_1m_output
            )
    costs["hybrid"] = hybrid_cost

    print(f"\n成本对比 (1000查询):")
    if "claude" in costs:
        print(f"  纯Claude:    ${costs['claude']:.2f}")
    if "deepseek" in costs:
        print(f"  纯DeepSeek:  ${costs['deepseek']:.2f} (节省 {(1-costs['deepseek']/costs['claude'])*100:.1f}%)")
    if "hybrid" in costs:
        print(f"  混合方案:    ${costs['hybrid']:.2f} (节省 {(1-costs['hybrid']/costs['claude'])*100:.1f}%)")

    print(f"\n月度成本 (30天):")
    if "claude" in costs:
        print(f"  纯Claude:    ${costs['claude']*30:.2f}/月")
    if "deepseek" in costs:
        print(f"  纯DeepSeek:  ${costs['deepseek']*30:.2f}/月")
    if "hybrid" in costs:
        print(f"  混合方案:    ${costs['hybrid']*30:.2f}/月")

    print(f"\n年度成本:")
    if "claude" in costs:
        print(f"  纯Claude:    ${costs['claude']*365:.2f}/年")
    if "deepseek" in costs:
        print(f"  纯DeepSeek:  ${costs['deepseek']*365:.2f}/年")
    if "hybrid" in costs:
        print(f"  混合方案:    ${costs['hybrid']*365:.2f}/年")


def test_routing_rules():
    """测试路由规则"""
    print("\n" + "="*60)
    print("测试4: 路由规则")
    print("="*60)

    for complexity in QueryComplexity:
        models = model_manager.routing_rules.get(complexity, [])
        print(f"\n{complexity}:")
        if models:
            for i, model in enumerate(models, 1):
                config = model_manager.models[model]
                print(f"  {i}. {model} (优先级: {config.priority})")
        else:
            print("  (无可用模型)")


def main():
    """运行所有测试"""
    print("="*60)
    print("Financial Asset QA System - 快速系统测试")
    print("="*60)

    try:
        test_configuration()
        test_query_routing()
        test_cost_calculation()
        test_routing_rules()

        print("\n" + "="*60)
        print("[OK] 所有测试完成")
        print("="*60)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
