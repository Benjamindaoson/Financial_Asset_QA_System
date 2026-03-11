"""
检索测试脚本 - 测试检索效果
Retrieval Test Script - Test Retrieval Performance

功能：
1. 测试不同查询的检索效果
2. 评估检索质量（召回率、精确率、MRR）
3. 对比不同检索策略
4. 生成测试报告
"""
import sys
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import time
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.enhanced_rag_pipeline import EnhancedRAGPipeline
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RetrievalTester:
    """检索测试器"""

    # 测试查询集
    TEST_QUERIES = [
        {
            "query": "什么是市盈率？",
            "category": "概念定义",
            "expected_keywords": ["市盈率", "股价", "每股收益", "P/E"]
        },
        {
            "query": "如何计算 ROE？",
            "category": "计算方法",
            "expected_keywords": ["ROE", "净资产收益率", "净利润", "净资产"]
        },
        {
            "query": "金融市场的功能有哪些？",
            "category": "知识问答",
            "expected_keywords": ["金融市场", "功能", "资金融通", "价格发现"]
        },
        {
            "query": "证券投资基金的分类",
            "category": "知识问答",
            "expected_keywords": ["基金", "分类", "股票型", "债券型"]
        },
        {
            "query": "债券的久期是什么？",
            "category": "概念定义",
            "expected_keywords": ["久期", "债券", "利率", "风险"]
        },
        {
            "query": "市净率和市盈率的区别",
            "category": "对比分析",
            "expected_keywords": ["市净率", "市盈率", "区别", "P/B", "P/E"]
        },
        {
            "query": "如何分析财务报表？",
            "category": "方法论",
            "expected_keywords": ["财务报表", "分析", "资产负债表", "利润表"]
        },
        {
            "query": "什么是系统性风险？",
            "category": "概念定义",
            "expected_keywords": ["系统性风险", "市场风险", "不可分散"]
        }
    ]

    def __init__(self, chroma_dir: str = None):
        """
        初始化测试器

        Args:
            chroma_dir: ChromaDB 目录（可选）
        """
        # 初始化 RAG 管道
        logger.info("初始化 RAG 管道...")
        self.pipeline = EnhancedRAGPipeline(
            enable_query_rewriting=True,
            enable_observability=True,
            enable_quality_control=True
        )

        # 测试结果
        self.test_results = []

    def test_retrieval(
        self,
        queries: List[Dict] = None,
        top_k: int = 5,
        test_strategies: List[str] = None
    ) -> Dict:
        """
        测试检索

        Args:
            queries: 测试查询列表（None=使用默认）
            top_k: 返回结果数
            test_strategies: 测试策略列表

        Returns:
            测试结果
        """
        queries = queries or self.TEST_QUERIES
        test_strategies = test_strategies or ["hybrid", "enhanced"]

        logger.info("="*60)
        logger.info("开始检索测试")
        logger.info("="*60)
        logger.info(f"测试查询数: {len(queries)}")
        logger.info(f"Top-K: {top_k}")
        logger.info(f"测试策略: {test_strategies}")

        # 测试每个查询
        for i, query_info in enumerate(queries, 1):
            query = query_info["query"]
            category = query_info["category"]
            expected_keywords = query_info["expected_keywords"]

            logger.info(f"\n{'='*60}")
            logger.info(f"测试 {i}/{len(queries)}: {query}")
            logger.info(f"类别: {category}")
            logger.info(f"{'='*60}")

            result = {
                "query": query,
                "category": category,
                "expected_keywords": expected_keywords,
                "strategies": {}
            }

            # 测试不同策略
            for strategy in test_strategies:
                logger.info(f"\n策略: {strategy}")
                strategy_result = self._test_single_query(
                    query, expected_keywords, strategy, top_k
                )
                result["strategies"][strategy] = strategy_result

            self.test_results.append(result)

        # 生成报告
        report = self._generate_report()

        return report

    def _test_single_query(
        self,
        query: str,
        expected_keywords: List[str],
        strategy: str,
        top_k: int
    ) -> Dict:
        """测试单个查询"""
        start_time = time.time()

        try:
            if strategy == "hybrid":
                # 混合检索（不使用查询改写）
                result = self.pipeline.search(query, use_hybrid=True, top_k=top_k)
                documents = result.documents
            elif strategy == "enhanced":
                # 增强检索（使用查询改写）
                result = self.pipeline.search_enhanced(
                    query=query,
                    use_query_rewriting=True,
                    rewrite_strategy="multi_query",
                    generate_answer=False
                )
                documents = result["documents"]
            else:
                logger.error(f"未知策略: {strategy}")
                return None

            duration = (time.time() - start_time) * 1000

            # 评估结果
            evaluation = self._evaluate_results(documents, expected_keywords)

            strategy_result = {
                "duration_ms": duration,
                "documents_count": len(documents),
                "evaluation": evaluation,
                "top_documents": [
                    {
                        "content": doc.content[:200] + "...",
                        "score": doc.score,
                        "source": doc.metadata.get("source_file", "unknown")
                    }
                    for doc in documents[:3]
                ]
            }

            # 打印结果
            logger.info(f"  耗时: {duration:.2f}ms")
            logger.info(f"  文档数: {len(documents)}")
            logger.info(f"  关键词匹配: {evaluation['keyword_match_count']}/{len(expected_keywords)}")
            logger.info(f"  相关性分数: {evaluation['relevance_score']:.2f}")

            if documents:
                logger.info(f"  Top-1 分数: {documents[0].score:.4f}")
                logger.info(f"  Top-1 内容: {documents[0].content[:100]}...")

            return strategy_result

        except Exception as e:
            logger.error(f"测试失败: {e}", exc_info=True)
            return {
                "error": str(e),
                "duration_ms": (time.time() - start_time) * 1000
            }

    def _evaluate_results(
        self,
        documents: List,
        expected_keywords: List[str]
    ) -> Dict:
        """评估检索结果"""
        if not documents:
            return {
                "keyword_match_count": 0,
                "relevance_score": 0.0,
                "has_relevant_doc": False
            }

        # 检查关键词匹配
        matched_keywords = set()
        for doc in documents[:5]:  # 只检查 top-5
            content_lower = doc.content.lower()
            for keyword in expected_keywords:
                if keyword.lower() in content_lower:
                    matched_keywords.add(keyword)

        # 计算相关性分数（基于关键词匹配率和文档分数）
        keyword_match_rate = len(matched_keywords) / len(expected_keywords)
        avg_doc_score = sum(doc.score for doc in documents[:5]) / min(5, len(documents))

        relevance_score = (keyword_match_rate * 0.6 + avg_doc_score * 0.4) * 100

        return {
            "keyword_match_count": len(matched_keywords),
            "keyword_match_rate": keyword_match_rate,
            "relevance_score": relevance_score,
            "has_relevant_doc": len(matched_keywords) >= len(expected_keywords) * 0.5,
            "avg_doc_score": avg_doc_score
        }

    def _generate_report(self) -> Dict:
        """生成测试报告"""
        logger.info("\n" + "="*60)
        logger.info("生成测试报告")
        logger.info("="*60)

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_queries": len(self.test_results),
            "strategies": {},
            "category_performance": {},
            "test_results": self.test_results
        }

        # 统计每个策略的性能
        strategies = set()
        for result in self.test_results:
            strategies.update(result["strategies"].keys())

        for strategy in strategies:
            strategy_stats = self._calculate_strategy_stats(strategy)
            report["strategies"][strategy] = strategy_stats

            logger.info(f"\n策略: {strategy}")
            logger.info(f"  平均耗时: {strategy_stats['avg_duration_ms']:.2f}ms")
            logger.info(f"  平均相关性: {strategy_stats['avg_relevance_score']:.2f}")
            logger.info(f"  关键词匹配率: {strategy_stats['avg_keyword_match_rate']:.2%}")
            logger.info(f"  成功率: {strategy_stats['success_rate']:.2%}")

        # 统计每个类别的性能
        categories = set(r["category"] for r in self.test_results)
        for category in categories:
            category_stats = self._calculate_category_stats(category)
            report["category_performance"][category] = category_stats

        logger.info("\n" + "="*60)
        logger.info("测试完成")
        logger.info("="*60)

        return report

    def _calculate_strategy_stats(self, strategy: str) -> Dict:
        """计算策略统计"""
        durations = []
        relevance_scores = []
        keyword_match_rates = []
        success_count = 0

        for result in self.test_results:
            strategy_result = result["strategies"].get(strategy)
            if not strategy_result or "error" in strategy_result:
                continue

            durations.append(strategy_result["duration_ms"])

            eval_data = strategy_result["evaluation"]
            relevance_scores.append(eval_data["relevance_score"])
            keyword_match_rates.append(eval_data["keyword_match_rate"])

            if eval_data["has_relevant_doc"]:
                success_count += 1

        return {
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "avg_relevance_score": sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0,
            "avg_keyword_match_rate": sum(keyword_match_rates) / len(keyword_match_rates) if keyword_match_rates else 0,
            "success_rate": success_count / len(self.test_results) if self.test_results else 0,
            "total_tests": len(self.test_results)
        }

    def _calculate_category_stats(self, category: str) -> Dict:
        """计算类别统计"""
        category_results = [r for r in self.test_results if r["category"] == category]

        if not category_results:
            return {}

        # 统计该类别下所有策略的平均性能
        avg_relevance = []
        avg_match_rate = []

        for result in category_results:
            for strategy_result in result["strategies"].values():
                if "error" not in strategy_result:
                    eval_data = strategy_result["evaluation"]
                    avg_relevance.append(eval_data["relevance_score"])
                    avg_match_rate.append(eval_data["keyword_match_rate"])

        return {
            "query_count": len(category_results),
            "avg_relevance_score": sum(avg_relevance) / len(avg_relevance) if avg_relevance else 0,
            "avg_keyword_match_rate": sum(avg_match_rate) / len(avg_match_rate) if avg_match_rate else 0
        }

    def save_report(self, report: Dict, output_file: str):
        """保存报告到文件"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"\n报告已保存: {output_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="测试检索效果")
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="单个查询（可选）"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="返回结果数"
    )
    parser.add_argument(
        "--strategies",
        type=str,
        nargs="+",
        default=["hybrid", "enhanced"],
        help="测试策略"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="logs/retrieval_test_report.json",
        help="报告输出文件"
    )

    args = parser.parse_args()

    # 创建测试器
    tester = RetrievalTester()

    # 执行测试
    if args.query:
        # 单个查询测试
        queries = [{
            "query": args.query,
            "category": "custom",
            "expected_keywords": []
        }]
        report = tester.test_retrieval(
            queries=queries,
            top_k=args.top_k,
            test_strategies=args.strategies
        )
    else:
        # 完整测试
        report = tester.test_retrieval(
            top_k=args.top_k,
            test_strategies=args.strategies
        )

    # 保存报告
    tester.save_report(report, args.output)


if __name__ == "__main__":
    main()
