"""
RAG 系统测试脚本
Test Script for RAG System

功能：
1. 测试基础检索
2. 测试智能缓存
3. 测试查询路由
4. 测试性能
5. 生成测试报告

使用方法：
    python test_rag_system.py
"""
import asyncio
import time
import json
from typing import List, Dict
import logging
from datetime import datetime

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RAGSystemTester:
    """RAG 系统测试器"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        初始化测试器

        Args:
            base_url: API 基础 URL
        """
        self.base_url = base_url
        self.api_v2_url = f"{base_url}/api/v2/rag"

        # 测试结果
        self.test_results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "tests": []
        }

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("="*60)
        logger.info("开始 RAG 系统测试")
        logger.info("="*60)

        # 测试 1: 健康检查
        logger.info("\n测试 1: 健康检查")
        self.test_health_check()

        # 测试 2: 基础检索
        logger.info("\n测试 2: 基础检索")
        self.test_basic_search()

        # 测试 3: 智能缓存
        logger.info("\n测试 3: 智能缓存")
        self.test_intelligent_cache()

        # 测试 4: 查询路由
        logger.info("\n测试 4: 查询路由")
        self.test_query_routing()

        # 测试 5: 性能测试
        logger.info("\n测试 5: 性能测试")
        self.test_performance()

        # 测试 6: 并发测试
        logger.info("\n测试 6: 并发测试")
        self.test_concurrent_requests()

        # 打印测试报告
        self.print_test_report()

    def test_health_check(self):
        """测试健康检查"""
        try:
            response = requests.get(f"{self.api_v2_url}/health", timeout=5)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"  ✓ 健康检查通过")
                logger.info(f"    状态: {data.get('status')}")
                logger.info(f"    组件: {list(data.get('components', {}).keys())}")

                self._record_test("健康检查", True, "系统健康")
            else:
                logger.error(f"  ✗ 健康检查失败: {response.status_code}")
                self._record_test("健康检查", False, f"状态码 {response.status_code}")

        except Exception as e:
            logger.error(f"  ✗ 健康检查异常: {e}")
            self._record_test("健康检查", False, str(e))

    def test_basic_search(self):
        """测试基础检索"""
        test_queries = [
            "什么是市盈率？",
            "如何计算 ROE？",
            "金融市场的功能"
        ]

        for query in test_queries:
            try:
                start_time = time.time()

                response = requests.post(
                    f"{self.api_v2_url}/search",
                    json={
                        "query": query,
                        "generate_answer": True,
                        "use_cache": False  # 第一次不用缓存
                    },
                    timeout=30
                )

                elapsed_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()

                    logger.info(f"  ✓ 查询成功: {query}")
                    logger.info(f"    耗时: {elapsed_ms:.0f}ms")
                    logger.info(f"    文档数: {len(data.get('documents', []))}")
                    logger.info(f"    答案长度: {len(data.get('answer', ''))}")

                    # 验证响应结构
                    has_answer = bool(data.get('answer'))
                    has_documents = len(data.get('documents', [])) > 0
                    has_classification = 'classification' in data

                    if has_answer and has_documents and has_classification:
                        self._record_test(
                            f"基础检索: {query}",
                            True,
                            f"{elapsed_ms:.0f}ms, {len(data['documents'])} 文档"
                        )
                    else:
                        self._record_test(
                            f"基础检索: {query}",
                            False,
                            "响应结构不完整"
                        )

                else:
                    logger.error(f"  ✗ 查询失败: {response.status_code}")
                    self._record_test(
                        f"基础检索: {query}",
                        False,
                        f"状态码 {response.status_code}"
                    )

            except Exception as e:
                logger.error(f"  ✗ 查询异常: {e}")
                self._record_test(f"基础检索: {query}", False, str(e))

    def test_intelligent_cache(self):
        """测试智能缓存"""
        query = "什么是市盈率？"

        try:
            # 第一次查询（无缓存）
            logger.info("  第一次查询（无缓存）...")
            start_time = time.time()

            response1 = requests.post(
                f"{self.api_v2_url}/search",
                json={"query": query, "use_cache": True},
                timeout=30
            )

            time1_ms = (time.time() - start_time) * 1000

            if response1.status_code != 200:
                self._record_test("智能缓存", False, "第一次查询失败")
                return

            data1 = response1.json()
            logger.info(f"    耗时: {time1_ms:.0f}ms")
            logger.info(f"    缓存命中: {data1.get('from_cache', False)}")

            # 第二次查询（应该命中缓存）
            logger.info("  第二次查询（应该命中缓存）...")
            time.sleep(0.5)  # 短暂等待

            start_time = time.time()

            response2 = requests.post(
                f"{self.api_v2_url}/search",
                json={"query": query, "use_cache": True},
                timeout=30
            )

            time2_ms = (time.time() - start_time) * 1000

            if response2.status_code != 200:
                self._record_test("智能缓存", False, "第二次查询失败")
                return

            data2 = response2.json()
            logger.info(f"    耗时: {time2_ms:.0f}ms")
            logger.info(f"    缓存命中: {data2.get('from_cache', False)}")

            # 验证缓存效果
            cache_hit = data2.get('from_cache', False)
            speedup = time1_ms / time2_ms if time2_ms > 0 else 0

            logger.info(f"  加速比: {speedup:.1f}x")

            if cache_hit and speedup > 2:
                logger.info(f"  ✓ 缓存测试通过")
                self._record_test(
                    "智能缓存",
                    True,
                    f"加速 {speedup:.1f}x ({time1_ms:.0f}ms → {time2_ms:.0f}ms)"
                )
            else:
                logger.warning(f"  ⚠ 缓存效果不明显")
                self._record_test(
                    "智能缓存",
                    False,
                    f"加速比仅 {speedup:.1f}x"
                )

            # 查看缓存统计
            stats_response = requests.get(f"{self.api_v2_url}/cache/stats", timeout=5)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                logger.info(f"  缓存统计:")
                logger.info(f"    总命中率: {stats.get('overall', {}).get('hit_rate', 0):.2%}")

        except Exception as e:
            logger.error(f"  ✗ 缓存测试异常: {e}")
            self._record_test("智能缓存", False, str(e))

    def test_query_routing(self):
        """测试查询路由"""
        test_cases = [
            {
                "query": "什么是市盈率？",
                "expected_type": "simple_definition",
                "expected_strategy": "simple"
            },
            {
                "query": "如何计算 ROE？",
                "expected_type": "calculation",
                "expected_strategy": "calculation"
            },
            {
                "query": "市盈率和市净率的区别",
                "expected_type": "comparison",
                "expected_strategy": "comparison"
            }
        ]

        for case in test_cases:
            try:
                response = requests.post(
                    f"{self.api_v2_url}/search",
                    json={
                        "query": case["query"],
                        "use_cache": False
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    classification = data.get('classification', {})

                    query_type = classification.get('query_type')
                    strategy = classification.get('strategy')

                    logger.info(f"  查询: {case['query']}")
                    logger.info(f"    识别类型: {query_type}")
                    logger.info(f"    使用策略: {strategy}")

                    # 验证分类是否正确
                    type_match = query_type == case['expected_type']
                    strategy_match = strategy == case['expected_strategy']

                    if type_match and strategy_match:
                        logger.info(f"    ✓ 路由正确")
                        self._record_test(
                            f"查询路由: {case['query'][:20]}",
                            True,
                            f"{query_type} → {strategy}"
                        )
                    else:
                        logger.warning(f"    ⚠ 路由不符合预期")
                        self._record_test(
                            f"查询路由: {case['query'][:20]}",
                            False,
                            f"预期 {case['expected_type']}, 实际 {query_type}"
                        )

                else:
                    self._record_test(
                        f"查询路由: {case['query'][:20]}",
                        False,
                        f"状态码 {response.status_code}"
                    )

            except Exception as e:
                logger.error(f"  ✗ 路由测试异常: {e}")
                self._record_test(f"查询路由: {case['query'][:20]}", False, str(e))

    def test_performance(self):
        """测试性能"""
        queries = [
            "什么是市盈率？",
            "如何计算 ROE？",
            "金融市场的功能",
            "市盈率和市净率的区别",
            "为什么金融市场会波动？"
        ]

        latencies = []

        logger.info(f"  测试 {len(queries)} 个查询的性能...")

        for query in queries:
            try:
                start_time = time.time()

                response = requests.post(
                    f"{self.api_v2_url}/search",
                    json={"query": query, "use_cache": False},
                    timeout=30
                )

                elapsed_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    latencies.append(elapsed_ms)
                    logger.info(f"    {query[:30]}: {elapsed_ms:.0f}ms")

            except Exception as e:
                logger.error(f"    {query[:30]}: 失败 ({e})")

        if latencies:
            # 计算统计指标
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(len(latencies) * 0.95)]
            avg = sum(latencies) / len(latencies)

            logger.info(f"\n  性能统计:")
            logger.info(f"    平均延迟: {avg:.0f}ms")
            logger.info(f"    P50 延迟: {p50:.0f}ms")
            logger.info(f"    P95 延迟: {p95:.0f}ms")

            # 验证性能目标
            if p50 < 2000 and p95 < 3000:
                logger.info(f"  ✓ 性能测试通过")
                self._record_test(
                    "性能测试",
                    True,
                    f"P50={p50:.0f}ms, P95={p95:.0f}ms"
                )
            else:
                logger.warning(f"  ⚠ 性能未达标")
                self._record_test(
                    "性能测试",
                    False,
                    f"P50={p50:.0f}ms (目标<2000ms)"
                )

        else:
            self._record_test("性能测试", False, "无有效数据")

    def test_concurrent_requests(self):
        """测试并发请求"""
        import concurrent.futures

        query = "什么是市盈率？"
        num_requests = 10

        logger.info(f"  发送 {num_requests} 个并发请求...")

        def send_request():
            try:
                start_time = time.time()
                response = requests.post(
                    f"{self.api_v2_url}/search",
                    json={"query": query, "use_cache": True},
                    timeout=30
                )
                elapsed_ms = (time.time() - start_time) * 1000
                return response.status_code == 200, elapsed_ms
            except Exception as e:
                return False, 0

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(send_request) for _ in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        total_time = time.time() - start_time

        # 统计结果
        success_count = sum(1 for success, _ in results if success)
        latencies = [latency for success, latency in results if success]

        logger.info(f"  总耗时: {total_time:.2f}s")
        logger.info(f"  成功率: {success_count}/{num_requests} ({success_count/num_requests*100:.0f}%)")

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            logger.info(f"  平均延迟: {avg_latency:.0f}ms")

        if success_count == num_requests:
            logger.info(f"  ✓ 并发测试通过")
            self._record_test(
                "并发测试",
                True,
                f"{num_requests} 个请求全部成功"
            )
        else:
            logger.warning(f"  ⚠ 部分请求失败")
            self._record_test(
                "并发测试",
                False,
                f"{success_count}/{num_requests} 成功"
            )

    def _record_test(self, name: str, passed: bool, details: str):
        """记录测试结果"""
        self.test_results["total_tests"] += 1

        if passed:
            self.test_results["passed"] += 1
        else:
            self.test_results["failed"] += 1

        self.test_results["tests"].append({
            "name": name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def print_test_report(self):
        """打印测试报告"""
        logger.info("\n" + "="*60)
        logger.info("测试报告")
        logger.info("="*60)

        logger.info(f"\n总测试数: {self.test_results['total_tests']}")
        logger.info(f"通过: {self.test_results['passed']}")
        logger.info(f"失败: {self.test_results['failed']}")
        logger.info(f"通过率: {self.test_results['passed']/self.test_results['total_tests']*100:.1f}%")

        logger.info("\n详细结果:")
        for test in self.test_results["tests"]:
            status = "✓" if test["passed"] else "✗"
            logger.info(f"  {status} {test['name']}: {test['details']}")

        # 保存报告
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)

        logger.info(f"\n测试报告已保存: {report_file}")

        logger.info("\n" + "="*60)

        if self.test_results["failed"] == 0:
            logger.info("✓ 所有测试通过！")
        else:
            logger.warning(f"⚠ {self.test_results['failed']} 个测试失败")

        logger.info("="*60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="测试 RAG 系统")
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000",
        help="API 基础 URL"
    )

    args = parser.parse_args()

    # 创建测试器
    tester = RAGSystemTester(base_url=args.url)

    # 运行测试
    tester.run_all_tests()


if __name__ == "__main__":
    main()
