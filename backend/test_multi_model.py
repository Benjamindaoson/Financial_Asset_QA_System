"""
测试多模型系统
Test Multi-Model System
"""
import asyncio
import sys
import os

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.models.multi_model import model_manager, QueryComplexity


def test_model_loading():
    """测试模型加载"""
    print("\n=== 测试模型加载 ===")
    print(f"已加载模型数量: {len(model_manager.models)}")

    for name, config in model_manager.models.items():
        print(f"\n模型: {name}")
        print(f"  提供商: {config.provider}")
        print(f"  模型名: {config.model_name}")
        print(f"  支持工具: {config.supports_tool_use}")
        print(f"  输入成本: ${config.cost_per_1m_input}/M tokens")
        print(f"  输出成本: ${config.cost_per_1m_output}/M tokens")
        print(f"  优先级: {config.priority}")


def test_query_classification():
    """测试查询分类"""
    print("\n=== 测试查询分类 ===")

    test_queries = [
        ("苹果股价", QueryComplexity.SIMPLE),
        ("特斯拉最近一个月的走势", QueryComplexity.MEDIUM),
        ("分析美联储加息对科技股的影响", QueryComplexity.COMPLEX),
        ("什么是市盈率", QueryComplexity.SIMPLE),
        ("对比微软和谷歌的财务状况", QueryComplexity.COMPLEX),
    ]

    for query, expected in test_queries:
        result = model_manager.classify_query(query)
        status = "[OK]" if result == expected else "[FAIL]"
        print(f"{status} '{query}' -> {result} (期望: {expected})")


def test_model_selection():
    """测试模型选择"""
    print("\n=== 测试模型选择 ===")

    for complexity in QueryComplexity:
        model = model_manager.select_model(complexity)
        print(f"{complexity}: {model}")


def test_usage_tracking():
    """测试使用统计"""
    print("\n=== 测试使用统计 ===")

    # 模拟一些使用
    model_manager.record_usage("claude-opus", 1000, 500, True)
    model_manager.record_usage("claude-opus", 2000, 1000, True)

    if "deepseek-chat" in model_manager.models:
        model_manager.record_usage("deepseek-chat", 1500, 800, True)
        model_manager.record_usage("deepseek-chat", 1000, 600, False)

    # 获取报告
    report = model_manager.get_usage_report()

    print(f"\n总请求数: {report['total_requests']}")
    print(f"总成本: ${report['total_cost']:.4f}")

    print("\n各模型统计:")
    for model_name, stats in report['models'].items():
        print(f"\n{model_name}:")
        print(f"  请求数: {stats['total_requests']}")
        print(f"  输入tokens: {stats['total_tokens_input']:,}")
        print(f"  输出tokens: {stats['total_tokens_output']:,}")
        print(f"  成本: ${stats['total_cost']:.4f}")
        print(f"  错误数: {stats['errors']}")


def test_routing_rules():
    """测试路由规则"""
    print("\n=== 测试路由规则 ===")

    for complexity, models in model_manager.routing_rules.items():
        print(f"\n{complexity}:")
        for i, model in enumerate(models, 1):
            print(f"  {i}. {model}")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("多模型系统测试")
    print("=" * 60)

    try:
        test_model_loading()
        test_query_classification()
        test_model_selection()
        test_routing_rules()
        test_usage_tracking()

        print("\n" + "=" * 60)
        print("[OK] 所有测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
