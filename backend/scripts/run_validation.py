"""
自动化测试脚本 - 验证系统准确率和召回率
Automated Testing Script - Validate system accuracy and recall
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent import AgentCore
from app.routing import QueryRouter


class SystemValidator:
    """系统验证器"""

    def __init__(self):
        self.agent = AgentCore()
        self.router = QueryRouter()
        self.results = []

    async def validate_single_query(self, test_case: Dict) -> Dict:
        """验证单个查询"""
        query = test_case["query"]
        expected_type = test_case["expected_type"]
        expected_symbols = test_case.get("expected_symbols", [])
        expected_contains = test_case.get("expected_answer_contains", [])

        print(f"\n[TEST] Query: {query}")

        # 1. 测试路由分类
        route = await self.router.classify_async(query)
        route_correct = route.query_type.value == expected_type or (
            expected_type == "hybrid" and route.query_type.value in ["market", "knowledge"]
        )

        # 2. 测试符号提取
        symbols_correct = set(route.symbols) == set(expected_symbols) if expected_symbols else True

        # 3. 测试完整响应
        response_text = ""
        try:
            async for event in self.agent.run(query):
                if event.type == "chunk":
                    response_text += event.text or ""
                elif event.type == "error":
                    response_text = f"ERROR: {event.message}"
                    break
        except Exception as e:
            response_text = f"EXCEPTION: {str(e)}"

        # 4. 检查响应内容
        contains_correct = all(
            keyword in response_text for keyword in expected_contains
        ) if expected_contains else True

        result = {
            "id": test_case["id"],
            "query": query,
            "expected_type": expected_type,
            "actual_type": route.query_type.value,
            "route_correct": route_correct,
            "symbols_correct": symbols_correct,
            "contains_correct": contains_correct,
            "response_length": len(response_text),
            "success": route_correct and symbols_correct and contains_correct,
        }

        status = "[PASS]" if result["success"] else "[FAIL]"
        print(f"{status} Type: {expected_type} -> {route.query_type.value}")
        print(f"  Symbols: {expected_symbols} -> {route.symbols}")
        print(f"  Response length: {len(response_text)} chars")

        return result

    async def run_validation(self, dataset_path: Path):
        """运行完整验证"""
        print(f"\n{'='*60}")
        print(f"Starting System Validation")
        print(f"{'='*60}")

        # 加载测试数据集
        with open(dataset_path, "r", encoding="utf-8") as f:
            test_cases = json.load(f)

        print(f"\n[INFO] Loaded {len(test_cases)} test cases")

        # 逐个测试
        for test_case in test_cases:
            result = await self.validate_single_query(test_case)
            self.results.append(result)

        # 生成报告
        self.generate_report()

    def generate_report(self):
        """生成测试报告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed

        route_correct = sum(1 for r in self.results if r["route_correct"])
        symbols_correct = sum(1 for r in self.results if r["symbols_correct"])
        contains_correct = sum(1 for r in self.results if r["contains_correct"])

        print(f"\n{'='*60}")
        print(f"Validation Report")
        print(f"{'='*60}")
        print(f"\nOverall Results:")
        print(f"  Total: {total}")
        print(f"  Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"  Failed: {failed} ({failed/total*100:.1f}%)")

        print(f"\nDetailed Metrics:")
        print(f"  Route Classification Accuracy: {route_correct}/{total} ({route_correct/total*100:.1f}%)")
        print(f"  Symbol Extraction Accuracy: {symbols_correct}/{total} ({symbols_correct/total*100:.1f}%)")
        print(f"  Response Content Accuracy: {contains_correct}/{total} ({contains_correct/total*100:.1f}%)")

        # 按类型统计
        type_stats = {}
        for r in self.results:
            t = r["expected_type"]
            if t not in type_stats:
                type_stats[t] = {"total": 0, "passed": 0}
            type_stats[t]["total"] += 1
            if r["success"]:
                type_stats[t]["passed"] += 1

        print(f"\nAccuracy by Query Type:")
        for t, stats in sorted(type_stats.items()):
            accuracy = stats["passed"] / stats["total"] * 100
            print(f"  {t}: {stats['passed']}/{stats['total']} ({accuracy:.1f}%)")

        # 保存详细结果
        output_file = Path(__file__).parent.parent / "tests" / "validation_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"\n[INFO] Detailed results saved to {output_file}")

        # 判断是否达标
        target_accuracy = 0.95  # 目标准确率 95%
        if passed / total >= target_accuracy:
            print(f"\n[SUCCESS] System meets target accuracy ({target_accuracy*100}%)")
            return 0
        else:
            print(f"\n[WARNING] System below target accuracy ({target_accuracy*100}%)")
            return 1


async def main():
    """主函数"""
    dataset_path = Path(__file__).parent.parent / "tests" / "datasets" / "qa_test_dataset.json"

    if not dataset_path.exists():
        print(f"[ERROR] Test dataset not found: {dataset_path}")
        print(f"[INFO] Please run: python scripts/test_dataset_builder.py")
        return 1

    validator = SystemValidator()
    return await validator.run_validation(dataset_path)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
