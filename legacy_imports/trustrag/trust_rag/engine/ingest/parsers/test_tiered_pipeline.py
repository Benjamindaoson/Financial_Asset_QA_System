#!/usr/bin/env python3
"""
TieredDocumentParser 验收测试脚本

测试三种典型场景：
1. 纯文本文档 -> 应该路由到 TIER_1
2. 普通发票扫描件 -> 应该路由到 TIER_2
3. 复杂财报嵌套表 -> 应该路由到 TIER_3

输出对比报告，验证路由决策的准确性
"""
import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

# 添加项目根目录到路径
# 动态计算正确的项目根目录
current_file = Path(__file__)
parsers_dir = current_file.parent  # trust_rag/engine/ingest/parsers
ingest_dir = parsers_dir.parent   # trust_rag/engine/ingest
engine_dir = ingest_dir.parent    # trust_rag/engine
trust_rag_dir = engine_dir.parent # trust_rag (包)
project_root = trust_rag_dir.parent # D:\trust_rag (项目根目录)

# 添加路径
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(trust_rag_dir))

print(f"项目根目录: {project_root}")
print(f"TrustRAG包目录: {trust_rag_dir}")
print(f"当前工作目录: {os.getcwd()}")

try:
    from trust_rag.engine.ingest.parsers.tiered_parser import (
        TieredDocumentParser,
        DocumentLayoutAnalyzer,
        ParserTier,
        DocumentComplexity
    )
    from trust_rag.engine.ingest.parsers.base_parser import ParsedDocument
    print("✅ 模块导入成功")
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)

@dataclass
class TestResult:
    """测试结果"""
    test_name: str
    file_path: str
    expected_tier: ParserTier
    actual_tier: ParserTier
    routing_correct: bool
    processing_time: float
    confidence: float
    content_length: int
    complexity_analysis: Dict[str, Any]
    cost_estimation: Dict[str, Any]
    error: str = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "file_path": self.file_path,
            "expected_tier": self.expected_tier.value,
            "actual_tier": self.actual_tier.value,
            "routing_correct": self.routing_correct,
            "processing_time": self.processing_time,
            "confidence": self.confidence,
            "content_length": self.content_length,
            "complexity_analysis": self.complexity_analysis,
            "cost_estimation": self.cost_estimation,
            "error": self.error
        }


class TieredPipelineTester:
    """
    三层梯度解析引擎测试器
    """

    def __init__(self):
        # 测试配置
        self.test_config = {
            'analyzer_config': {
                'max_sample_pages': 3,  # 测试时减少采样页数
            },
            'cost_config': {
                'cost_threshold': 0.05,  # 降低成本阈值用于测试
            },
            'tier1_config': {},
            'tier2_config': {
                'use_mineru': False,  # 测试时优先使用PaddleOCR
                'max_workers': 2,
            },
            'tier3_config': {
                'device': 'cpu',  # 测试环境使用CPU
                'max_tokens': 1024,  # 减少token限制
            }
        }

        self.parser = TieredDocumentParser(self.test_config)
        self.analyzer = DocumentLayoutAnalyzer(self.test_config.get('analyzer_config', {}))

        # 测试结果
        self.results: List[TestResult] = []

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """
        运行综合测试
        """
        print("🚀 开始 TieredDocumentParser 验收测试")
        print("=" * 60)

        # 测试用例定义 - 使用真实的PDF文件
        # 直接使用绝对路径，因为项目结构比较复杂
        test_cases = [
            {
                "name": "NVIDIA财报测试",
                "file_path": r"D:\trust_rag\demo_data\raw_docs\nvidia_fy2023.pdf",
                "expected_tier": ParserTier.TIER_3,  # 财务报表，复杂度高
                "description": "NVIDIA年度财务报表，包含复杂表格和图表"
            },
            {
                "name": "Apple 10-K测试",
                "file_path": r"D:\trust_rag\artifacts\raw_docs\apple\2023\10-K_FY2023.pdf",
                "expected_tier": ParserTier.TIER_3,  # 10-K报告，复杂度高
                "description": "Apple 10-K年度报告，复杂财务文档"
            },
            {
                "name": "Apple 10-Q测试",
                "file_path": r"D:\trust_rag\artifacts\raw_docs\apple\2024\10-Q_Q2_2024.pdf",
                "expected_tier": ParserTier.TIER_2,  # 季度报告，中等复杂度
                "description": "Apple 10-Q季度报告，包含表格但相对简单"
            }
        ]

        # 执行测试
        for test_case in test_cases:
            print(f"\n📋 执行测试: {test_case['name']}")
            print(f"   描述: {test_case['description']}")
            print(f"   文件: {test_case['file_path']}")

            result = self._run_single_test(test_case)
            self.results.append(result)

            # 输出结果
            self._print_test_result(result)

        # 生成报告
        report = self._generate_report()
        self._save_report(report)

        return report

    def _run_single_test(self, test_case: Dict[str, Any]) -> TestResult:
        """
        运行单个测试用例
        """
        test_name = test_case["name"]
        file_path = test_case["file_path"]
        expected_tier = test_case["expected_tier"]

        start_time = time.time()

        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return TestResult(
                    test_name=test_name,
                    file_path=file_path,
                    expected_tier=expected_tier,
                    actual_tier=ParserTier.TIER_1,  # 默认值
                    routing_correct=False,
                    processing_time=0.0,
                    confidence=0.0,
                    content_length=0,
                    complexity_analysis={},
                    cost_estimation={},
                    error=f"测试文件不存在: {file_path}"
                )

            # 执行分析
            analysis = self.analyzer.analyze_document(file_path)

            # 执行解析
            result = self.parser.parse(file_path, document_type='financial')

            processing_time = time.time() - start_time

            # 判断路由是否正确
            actual_tier = ParserTier(result.usage_metrics.get("final_tier", "tier_1"))
            routing_correct = (actual_tier == expected_tier)

            return TestResult(
                test_name=test_name,
                file_path=file_path,
                expected_tier=expected_tier,
                actual_tier=actual_tier,
                routing_correct=routing_correct,
                processing_time=round(processing_time, 3),
                confidence=result.confidence_score,
                content_length=len(result.content),
                complexity_analysis=analysis.to_dict(),
                cost_estimation={
                    "estimated_cost": result.usage_metrics.get("estimated_cost", 0),
                    "cost_warnings": result.usage_metrics.get("cost_warnings", [])
                }
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return TestResult(
                test_name=test_name,
                file_path=file_path,
                expected_tier=expected_tier,
                actual_tier=ParserTier.TIER_1,  # 默认值
                routing_correct=False,
                processing_time=round(processing_time, 3),
                confidence=0.0,
                content_length=0,
                complexity_analysis={},
                cost_estimation={},
                error=str(e)
            )

    def _get_test_file(self, filename: str) -> str:
        """
        获取测试文件路径

        使用现有的demo文件进行测试
        """
        # 优先使用demo_data中的文件
        demo_dir = Path(__file__).parent.parent.parent.parent / "demo_data" / "raw_docs"
        if demo_dir.exists():
            # 查找可用的PDF文件
            pdf_files = list(demo_dir.glob("*.pdf"))
            if pdf_files:
                return str(pdf_files[0])  # 使用第一个找到的PDF

        # 其次使用artifacts中的文件
        artifacts_dir = Path(__file__).parent.parent.parent.parent / "artifacts" / "raw_docs"
        if artifacts_dir.exists():
            # 递归查找PDF文件
            pdf_files = list(artifacts_dir.rglob("*.pdf"))
            if pdf_files:
                return str(pdf_files[0])  # 使用第一个找到的PDF

        # 如果都没有，返回一个不存在的路径（测试会处理这个情况）
        return f"/tmp/{filename}"

    def _print_test_result(self, result: TestResult):
        """
        打印测试结果
        """
        status = "✅ 通过" if result.routing_correct else "❌ 失败"

        print(f"   结果: {status}")
        print(f"   期望层级: {result.expected_tier.value}")
        print(f"   实际层级: {result.actual_tier.value}")
        print(".2f")
        print(".2f")
        print(f"   内容长度: {result.content_length} 字符")

        if result.cost_estimation.get("estimated_cost", 0) > 0:
            print(".4f")

        if result.error:
            print(f"   错误: {result.error}")

        # 显示复杂度分析摘要
        if result.complexity_analysis:
            complexity = result.complexity_analysis.get("complexity", "unknown")
            confidence = result.complexity_analysis.get("confidence", 0)
            print(f"   复杂度: {complexity} (置信度: {confidence:.2f})")

    def _generate_report(self) -> Dict[str, Any]:
        """
        生成测试报告
        """
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.routing_correct and not r.error)
        failed_tests = total_tests - passed_tests

        # 统计各层级路由情况
        tier_stats = {}
        for result in self.results:
            tier = result.actual_tier.value
            if tier not in tier_stats:
                tier_stats[tier] = {"count": 0, "correct": 0, "avg_time": 0}
            tier_stats[tier]["count"] += 1
            if result.routing_correct:
                tier_stats[tier]["correct"] += 1
            tier_stats[tier]["avg_time"] += result.processing_time

        for tier in tier_stats:
            tier_stats[tier]["avg_time"] /= tier_stats[tier]["count"]
            tier_stats[tier]["accuracy"] = tier_stats[tier]["correct"] / tier_stats[tier]["count"]

        # 性能统计
        total_time = sum(r.processing_time for r in self.results)
        avg_time = total_time / total_tests if total_tests > 0 else 0
        total_cost = sum(r.cost_estimation.get("estimated_cost", 0) for r in self.results)

        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "total_processing_time": round(total_time, 3),
                "average_processing_time": round(avg_time, 3),
                "total_estimated_cost": round(total_cost, 4)
            },
            "tier_routing_stats": tier_stats,
            "detailed_results": [r.to_dict() for r in self.results],
            "system_info": {
                "available_tiers": self.parser.get_available_tiers(),
                "parser_capabilities": self.parser.get_parser_capabilities()
            },
            "test_timestamp": time.time(),
            "test_version": "2.0.0"
        }

        return report

    def _save_report(self, report: Dict[str, Any]):
        """
        保存测试报告
        """
        report_dir = Path(__file__).parent / "test_reports"
        report_dir.mkdir(exist_ok=True)

        timestamp = int(time.time())
        report_file = report_dir / f"tiered_pipeline_test_{timestamp}.json"

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n📄 测试报告已保存: {report_file}")

        # 打印摘要
        summary = report["test_summary"]
        print("\n" + "=" * 60)
        print("📊 测试摘要")
        print("=" * 60)
        print(f"总测试数: {summary['total_tests']}")
        print(f"通过测试: {summary['passed_tests']}")
        print(f"失败测试: {summary['failed_tests']}")
        print(".1%")
        print(".2f")
        print(".3f")
        print(".4f")

        # 打印各层级统计
        print("\n📈 各层级路由统计")
        for tier, stats in report["tier_routing_stats"].items():
            print(f"  {tier}: {stats['count']} 次路由, "
                  ".1%")

    def run_routing_accuracy_test(self):
        """
        专门测试路由准确性
        """
        print("\n🎯 路由准确性专项测试")
        print("-" * 40)

        # 使用不同的路由配置测试
        routing_configs = [
            {"name": "智能路由", "force_tier": None, "enable_auto_routing": True},
            {"name": "强制TIER_1", "force_tier": ParserTier.TIER_1, "enable_auto_routing": False},
            {"name": "强制TIER_2", "force_tier": ParserTier.TIER_2, "enable_auto_routing": False},
            {"name": "强制TIER_3", "force_tier": ParserTier.TIER_3, "enable_auto_routing": False},
        ]

        for config in routing_configs:
            print(f"\n测试配置: {config['name']}")

            # 临时修改配置
            original_force = self.parser.force_tier
            original_auto = self.parser.enable_auto_routing

            self.parser.force_tier = config["force_tier"]
            self.parser.enable_auto_routing = config["enable_auto_routing"]

            try:
                # 运行简单测试
                test_file = self._get_test_file("simple_text.pdf")
                if os.path.exists(test_file):
                    result = self.parser.parse(test_file)
                    actual_tier = result.usage_metrics.get("final_tier", "tier_1")
                    print(f"  结果层级: {actual_tier}")
                else:
                    print("  测试文件不存在，跳过")

            except Exception as e:
                print(f"  错误: {e}")

            finally:
                # 恢复原始配置
                self.parser.force_tier = original_force
                self.parser.enable_auto_routing = original_auto


def main():
    """
    主函数
    """
    print("TrustRAG 2.0 三层梯度解析引擎验收测试")
    print("测试目标：验证智能路由决策的准确性")
    print()

    # 创建测试器
    tester = TieredPipelineTester()

    try:
        # 运行综合测试
        report = tester.run_comprehensive_test()

        # 运行路由准确性测试
        tester.run_routing_accuracy_test()

        # 检查整体成功率
        success_rate = report["test_summary"]["success_rate"]
        if success_rate >= 0.8:  # 80%以上通过
            print("\n🎉 测试完成！路由准确率达标。")
            return 0
        else:
            print("\n⚠️  测试完成，但路由准确率未达标。")
            return 1

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
