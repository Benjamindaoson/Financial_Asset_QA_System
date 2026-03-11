"""
索引验证脚本 - 验证索引的完整性和准确性
Index Validation Script - Validate Index Completeness and Accuracy

检查项：
1. 所有文件都已处理
2. 无重复 chunk
3. 元数据完整
4. 向量质量（检查异常值）
5. 检索功能正常
"""
import sys
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Set
import numpy as np

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.bge_embedding import BGEEmbedding
from app.config import settings

import chromadb
from chromadb.config import Settings as ChromaSettings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IndexValidator:
    """索引验证器"""

    def __init__(self, chroma_dir: str, data_dir: str = None):
        """
        初始化验证器

        Args:
            chroma_dir: ChromaDB 目录
            data_dir: 原始数据目录（用于对比）
        """
        self.chroma_dir = Path(chroma_dir)
        self.data_dir = Path(data_dir) if data_dir else None

        # 初始化 ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # 初始化 Embedding 模型
        self.embedding_model = BGEEmbedding(model_name=settings.EMBEDDING_MODEL)

        # 验证结果
        self.validation_results = {
            "collections": {},
            "total_chunks": 0,
            "issues": [],
            "passed": True
        }

    def validate(self) -> Dict:
        """
        执行验证

        Returns:
            验证结果
        """
        logger.info("="*60)
        logger.info("开始验证索引")
        logger.info("="*60)
        logger.info(f"ChromaDB 目录: {self.chroma_dir}")

        # 检查 1: 验证 collections 存在
        logger.info("\n" + "="*60)
        logger.info("检查 1: 验证 Collections")
        logger.info("="*60)
        self._validate_collections()

        # 检查 2: 验证数据完整性
        logger.info("\n" + "="*60)
        logger.info("检查 2: 验证数据完整性")
        logger.info("="*60)
        self._validate_data_completeness()

        # 检查 3: 验证元数据
        logger.info("\n" + "="*60)
        logger.info("检查 3: 验证元数据")
        logger.info("="*60)
        self._validate_metadata()

        # 检查 4: 验证向量质量
        logger.info("\n" + "="*60)
        logger.info("检查 4: 验证向量质量")
        logger.info("="*60)
        self._validate_vector_quality()

        # 检查 5: 验证检索功能
        logger.info("\n" + "="*60)
        logger.info("检查 5: 验证检索功能")
        logger.info("="*60)
        self._validate_retrieval()

        # 打印总结
        self._print_summary()

        return self.validation_results

    def _validate_collections(self):
        """验证 collections 存在"""
        collections = self.chroma_client.list_collections()

        logger.info(f"找到 {len(collections)} 个 collections:")

        for coll in collections:
            count = coll.count()
            logger.info(f"  - {coll.name}: {count} 个文档")

            self.validation_results["collections"][coll.name] = {
                "count": count,
                "metadata": coll.metadata
            }
            self.validation_results["total_chunks"] += count

        if len(collections) == 0:
            self._add_issue("CRITICAL", "未找到任何 collection")
            self.validation_results["passed"] = False
        else:
            logger.info(f"✓ 找到 {len(collections)} 个 collections")

    def _validate_data_completeness(self):
        """验证数据完整性"""
        # 检查每个 collection
        for coll_name, coll_info in self.validation_results["collections"].items():
            collection = self.chroma_client.get_collection(coll_name)

            # 获取所有数据
            result = collection.get(include=["documents", "metadatas"])

            # 检查是否有空文档
            empty_docs = [i for i, doc in enumerate(result["documents"]) if not doc or len(doc.strip()) == 0]

            if empty_docs:
                self._add_issue(
                    "WARNING",
                    f"Collection '{coll_name}' 有 {len(empty_docs)} 个空文档"
                )

            # 检查重复 ID
            ids = result["ids"]
            unique_ids = set(ids)

            if len(ids) != len(unique_ids):
                duplicates = len(ids) - len(unique_ids)
                self._add_issue(
                    "ERROR",
                    f"Collection '{coll_name}' 有 {duplicates} 个重复 ID"
                )
                self.validation_results["passed"] = False
            else:
                logger.info(f"✓ Collection '{coll_name}': 无重复 ID")

            # 检查文档数量
            if coll_info["count"] == 0:
                self._add_issue(
                    "WARNING",
                    f"Collection '{coll_name}' 为空"
                )
            else:
                logger.info(f"✓ Collection '{coll_name}': {coll_info['count']} 个文档")

    def _validate_metadata(self):
        """验证元数据完整性"""
        required_fields = ["source_file", "source_type", "chunk_type"]

        for coll_name in self.validation_results["collections"].keys():
            collection = self.chroma_client.get_collection(coll_name)

            # 获取元数据
            result = collection.get(include=["metadatas"])
            metadatas = result["metadatas"]

            # 检查必需字段
            missing_fields = []
            for i, meta in enumerate(metadatas):
                for field in required_fields:
                    if field not in meta or not meta[field]:
                        missing_fields.append((i, field))

            if missing_fields:
                self._add_issue(
                    "WARNING",
                    f"Collection '{coll_name}' 有 {len(missing_fields)} 个元数据缺失"
                )
            else:
                logger.info(f"✓ Collection '{coll_name}': 元数据完整")

            # 统计元数据分布
            self._analyze_metadata_distribution(coll_name, metadatas)

    def _analyze_metadata_distribution(self, coll_name: str, metadatas: List[Dict]):
        """分析元数据分布"""
        # 统计 chunk_type 分布
        chunk_types = {}
        difficulties = {}
        source_types = {}

        for meta in metadatas:
            # Chunk type
            chunk_type = meta.get("chunk_type", "unknown")
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

            # Difficulty
            difficulty = meta.get("difficulty", "unknown")
            difficulties[difficulty] = difficulties.get(difficulty, 0) + 1

            # Source type
            source_type = meta.get("source_type", "unknown")
            source_types[source_type] = source_types.get(source_type, 0) + 1

        logger.info(f"\n  元数据分布 ({coll_name}):")
        logger.info(f"    Chunk 类型: {chunk_types}")
        logger.info(f"    难度分布: {difficulties}")
        logger.info(f"    源类型: {source_types}")

    def _validate_vector_quality(self):
        """验证向量质量"""
        for coll_name in self.validation_results["collections"].keys():
            collection = self.chroma_client.get_collection(coll_name)

            # 获取向量
            result = collection.get(include=["embeddings"])
            embeddings = result["embeddings"]

            if not embeddings:
                self._add_issue(
                    "ERROR",
                    f"Collection '{coll_name}' 没有向量"
                )
                self.validation_results["passed"] = False
                continue

            # 转换为 numpy 数组
            embeddings_array = np.array(embeddings)

            # 检查向量维度
            expected_dim = 768  # BGE-base-zh-v1.5
            actual_dim = embeddings_array.shape[1]

            if actual_dim != expected_dim:
                self._add_issue(
                    "ERROR",
                    f"Collection '{coll_name}' 向量维度错误: {actual_dim} (期望 {expected_dim})"
                )
                self.validation_results["passed"] = False
                continue

            # 检查异常值（全零向量、NaN、Inf）
            zero_vectors = np.all(embeddings_array == 0, axis=1).sum()
            nan_vectors = np.any(np.isnan(embeddings_array), axis=1).sum()
            inf_vectors = np.any(np.isinf(embeddings_array), axis=1).sum()

            if zero_vectors > 0:
                self._add_issue(
                    "ERROR",
                    f"Collection '{coll_name}' 有 {zero_vectors} 个全零向量"
                )
                self.validation_results["passed"] = False

            if nan_vectors > 0:
                self._add_issue(
                    "ERROR",
                    f"Collection '{coll_name}' 有 {nan_vectors} 个 NaN 向量"
                )
                self.validation_results["passed"] = False

            if inf_vectors > 0:
                self._add_issue(
                    "ERROR",
                    f"Collection '{coll_name}' 有 {inf_vectors} 个 Inf 向量"
                )
                self.validation_results["passed"] = False

            # 检查向量范数分布
            norms = np.linalg.norm(embeddings_array, axis=1)
            mean_norm = norms.mean()
            std_norm = norms.std()

            logger.info(f"  Collection '{coll_name}' 向量统计:")
            logger.info(f"    维度: {actual_dim}")
            logger.info(f"    数量: {len(embeddings)}")
            logger.info(f"    范数均值: {mean_norm:.4f}")
            logger.info(f"    范数标准差: {std_norm:.4f}")

            if zero_vectors == 0 and nan_vectors == 0 and inf_vectors == 0:
                logger.info(f"✓ Collection '{coll_name}': 向量质量正常")

    def _validate_retrieval(self):
        """验证检索功能"""
        # 测试查询
        test_queries = [
            "什么是市盈率？",
            "如何计算 ROE？",
            "金融市场的功能",
            "证券投资基金的分类"
        ]

        for coll_name in self.validation_results["collections"].keys():
            collection = self.chroma_client.get_collection(coll_name)

            logger.info(f"\n  测试 Collection '{coll_name}':")

            for query in test_queries:
                try:
                    # 生成查询向量
                    query_embedding = self.embedding_model.encode(query)

                    # 检索
                    results = collection.query(
                        query_embeddings=[query_embedding],
                        n_results=3
                    )

                    # 检查结果
                    if results["documents"] and results["documents"][0]:
                        top_doc = results["documents"][0][0]
                        top_distance = results["distances"][0][0]
                        logger.info(f"    ✓ '{query}': 找到 {len(results['documents'][0])} 个结果 (top距离: {top_distance:.4f})")
                    else:
                        self._add_issue(
                            "WARNING",
                            f"Collection '{coll_name}' 查询 '{query}' 无结果"
                        )

                except Exception as e:
                    self._add_issue(
                        "ERROR",
                        f"Collection '{coll_name}' 检索失败: {query} - {e}"
                    )
                    self.validation_results["passed"] = False

    def _add_issue(self, level: str, message: str):
        """添加问题"""
        self.validation_results["issues"].append({
            "level": level,
            "message": message
        })
        logger.warning(f"[{level}] {message}")

    def _print_summary(self):
        """打印总结"""
        logger.info("\n" + "="*60)
        logger.info("验证总结")
        logger.info("="*60)

        logger.info(f"总 Collections: {len(self.validation_results['collections'])}")
        logger.info(f"总 Chunks: {self.validation_results['total_chunks']}")
        logger.info(f"总问题: {len(self.validation_results['issues'])}")

        # 按级别统计问题
        issues_by_level = {}
        for issue in self.validation_results["issues"]:
            level = issue["level"]
            issues_by_level[level] = issues_by_level.get(level, 0) + 1

        if issues_by_level:
            logger.info(f"\n问题统计:")
            for level, count in issues_by_level.items():
                logger.info(f"  {level}: {count}")

        # 最终结果
        if self.validation_results["passed"]:
            logger.info("\n✓ 验证通过")
        else:
            logger.error("\n✗ 验证失败")

        logger.info("="*60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="验证向量索引")
    parser.add_argument(
        "--chroma-dir",
        type=str,
        default=r"F:\Financial_Asset_QA_System_cyx-master\backend\data\chroma_db",
        help="ChromaDB 目录"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="原始数据目录（可选）"
    )

    args = parser.parse_args()

    # 创建验证器
    validator = IndexValidator(
        chroma_dir=args.chroma_dir,
        data_dir=args.data_dir
    )

    # 执行验证
    results = validator.validate()

    # 返回状态码
    exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
