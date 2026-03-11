"""
BGE向量化配置
BGE Embedding Configuration

使用BAAI/bge-large-zh-v1.5作为向量化模型
专门针对中文金融领域优化
"""
import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class BGEEmbedding:
    """BGE向量化模型"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-zh-v1.5",
        device: str = "cpu"
    ):
        """
        初始化BGE向量化模型

        Args:
            model_name: 模型名称
            device: 设备 (cpu/cuda)
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self._load_model()

    def _load_model(self):
        """加载模型"""
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"BGE模型加载成功: {self.model_name} on {self.device}")

        except ImportError:
            logger.error("sentence-transformers未安装")
            logger.error("安装: pip install sentence-transformers")
            raise

        except Exception as e:
            logger.error(f"BGE模型加载失败: {e}")
            raise

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        向量化文档

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if not self.model:
            raise RuntimeError("模型未加载")

        try:
            # BGE模型建议为文档添加指令前缀
            # 但对于检索任务，通常不需要
            embeddings = self.model.encode(
                texts,
                normalize_embeddings=True,  # 归一化向量
                show_progress_bar=len(texts) > 100
            )

            return embeddings.tolist()

        except Exception as e:
            logger.error(f"文档向量化失败: {e}")
            raise

    def embed_query(self, text: str) -> List[float]:
        """
        向量化查询

        Args:
            text: 查询文本

        Returns:
            向量
        """
        if not self.model:
            raise RuntimeError("模型未加载")

        try:
            # BGE模型建议为查询添加指令前缀
            # 对于中文检索，可以添加"为这个句子生成表示以用于检索相关文章："
            instruction = "为这个句子生成表示以用于检索相关文章："
            query_with_instruction = instruction + text

            embedding = self.model.encode(
                query_with_instruction,
                normalize_embeddings=True
            )

            return embedding.tolist()

        except Exception as e:
            logger.error(f"查询向量化失败: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """获取向量维度"""
        if not self.model:
            return 1024  # BGE-large默认维度

        return self.model.get_sentence_embedding_dimension()


class BGEChromaEmbeddingFunction:
    """
    ChromaDB兼容的BGE向量化函数

    用于替换ChromaDB默认的embedding function
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-zh-v1.5",
        device: str = "cpu"
    ):
        self.bge = BGEEmbedding(model_name, device)

    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        ChromaDB调用接口

        Args:
            input: 文本列表

        Returns:
            向量列表
        """
        return self.bge.embed_documents(input)


def create_bge_collection(
    client,
    collection_name: str = "financial_knowledge_bge",
    model_name: str = "BAAI/bge-large-zh-v1.5",
    device: str = "cpu"
):
    """
    创建使用BGE向量化的ChromaDB集合

    Args:
        client: ChromaDB客户端
        collection_name: 集合名称
        model_name: BGE模型名称
        device: 设备

    Returns:
        ChromaDB集合
    """
    try:
        # 创建BGE向量化函数
        embedding_function = BGEChromaEmbeddingFunction(model_name, device)

        # 创建集合
        collection = client.create_collection(
            name=collection_name,
            embedding_function=embedding_function,
            metadata={
                "description": "Financial knowledge base with BGE embeddings",
                "embedding_model": model_name
            }
        )

        logger.info(f"BGE集合创建成功: {collection_name}")
        return collection

    except Exception as e:
        logger.error(f"BGE集合创建失败: {e}")
        raise


def migrate_to_bge(
    client,
    old_collection_name: str = "financial_knowledge",
    new_collection_name: str = "financial_knowledge_bge",
    model_name: str = "BAAI/bge-large-zh-v1.5",
    device: str = "cpu",
    batch_size: int = 100
):
    """
    将现有集合迁移到BGE向量化

    Args:
        client: ChromaDB客户端
        old_collection_name: 旧集合名称
        new_collection_name: 新集合名称
        model_name: BGE模型名称
        device: 设备
        batch_size: 批处理大小

    Returns:
        迁移统计信息
    """
    logger.info(f"开始迁移: {old_collection_name} -> {new_collection_name}")

    try:
        # 获取旧集合
        old_collection = client.get_collection(old_collection_name)
        total_docs = old_collection.count()

        logger.info(f"旧集合文档数: {total_docs}")

        # 创建新集合
        new_collection = create_bge_collection(
            client,
            new_collection_name,
            model_name,
            device
        )

        # 批量迁移
        migrated = 0
        failed = 0

        # 获取所有文档
        results = old_collection.get()

        if not results or not results.get("documents"):
            logger.warning("旧集合为空")
            return {"migrated": 0, "failed": 0, "total": 0}

        documents = results["documents"]
        metadatas = results.get("metadatas", [{}] * len(documents))
        ids = results["ids"]

        # 分批处理
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            try:
                # 添加到新集合（自动使用BGE向量化）
                new_collection.add(
                    documents=batch_docs,
                    metadatas=batch_metas,
                    ids=batch_ids
                )

                migrated += len(batch_docs)
                logger.info(f"已迁移: {migrated}/{total_docs}")

            except Exception as e:
                logger.error(f"批次迁移失败: {e}")
                failed += len(batch_docs)

        logger.info(f"迁移完成: 成功{migrated}, 失败{failed}")

        return {
            "migrated": migrated,
            "failed": failed,
            "total": total_docs
        }

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        raise


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    # 测试BGE向量化
    print("测试BGE向量化...")

    try:
        bge = BGEEmbedding()

        # 测试文档向量化
        docs = [
            "苹果公司2025年Q4营收为1245亿美元",
            "特斯拉2024年全年交付量达到180万辆"
        ]

        doc_embeddings = bge.embed_documents(docs)
        print(f"文档向量维度: {len(doc_embeddings[0])}")

        # 测试查询向量化
        query = "苹果公司的营收是多少"
        query_embedding = bge.embed_query(query)
        print(f"查询向量维度: {len(query_embedding)}")

        # 计算相似度
        from numpy import dot
        from numpy.linalg import norm

        similarity = dot(query_embedding, doc_embeddings[0]) / (
            norm(query_embedding) * norm(doc_embeddings[0])
        )
        print(f"查询与文档1的相似度: {similarity:.4f}")

        print("\n✅ BGE向量化测试成功")

    except Exception as e:
        print(f"\n❌ BGE向量化测试失败: {e}")
        print("请安装: pip install sentence-transformers")

    # 测试ChromaDB集成
    print("\n测试ChromaDB集成...")

    try:
        import chromadb

        client = chromadb.Client()

        # 创建BGE集合
        collection = create_bge_collection(client, "test_bge")

        # 添加文档
        collection.add(
            documents=["测试文档1", "测试文档2"],
            ids=["doc1", "doc2"]
        )

        # 查询
        results = collection.query(
            query_texts=["测试"],
            n_results=2
        )

        print(f"查询结果数: {len(results['documents'][0])}")
        print("\n✅ ChromaDB集成测试成功")

    except Exception as e:
        print(f"\n❌ ChromaDB集成测试失败: {e}")
