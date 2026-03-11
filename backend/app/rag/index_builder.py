"""
向量数据库索引构建器
Vector Database Index Builder

将处理后的文档块导入ChromaDB
"""
import logging
from typing import List, Dict, Optional
from pathlib import Path
import json

from app.rag.data_pipeline import RAGDataPipeline

logger = logging.getLogger(__name__)


class VectorIndexBuilder:
    """向量数据库索引构建器"""

    def __init__(self, chroma_client, collection_name: str = "financial_knowledge"):
        """
        初始化索引构建器

        Args:
            chroma_client: ChromaDB客户端
            collection_name: 集合名称
        """
        self.client = chroma_client
        self.collection_name = collection_name
        self.collection = None

    def create_or_get_collection(self):
        """创建或获取集合"""
        try:
            # 尝试获取现有集合
            self.collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"使用现有集合: {self.collection_name}")
        except Exception:
            # 创建新集合
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Financial knowledge base with reports and documents"}
            )
            logger.info(f"创建新集合: {self.collection_name}")

    def build_index(self, chunks: List[Dict], batch_size: int = 100) -> Dict:
        """
        构建向量索引

        Args:
            chunks: 文档块列表
            batch_size: 批处理大小

        Returns:
            构建统计信息
        """
        if not self.collection:
            self.create_or_get_collection()

        stats = {
            "total_chunks": len(chunks),
            "indexed_chunks": 0,
            "failed_chunks": 0,
            "batches": 0
        }

        logger.info(f"开始构建索引，共 {len(chunks)} 个文档块")

        # 批量处理
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            try:
                self._index_batch(batch, start_index=i)
                stats["indexed_chunks"] += len(batch)
                stats["batches"] += 1

                if (i + batch_size) % 500 == 0:
                    logger.info(f"已处理 {i + batch_size}/{len(chunks)} 个文档块")

            except Exception as e:
                logger.error(f"批次 {i}-{i+batch_size} 索引失败: {e}")
                stats["failed_chunks"] += len(batch)

        logger.info(f"索引构建完成: {stats}")
        return stats

    def _index_batch(self, batch: List[Dict], start_index: int):
        """
        索引一批文档

        Args:
            batch: 文档批次
            start_index: 起始索引
        """
        documents = []
        metadatas = []
        ids = []

        for idx, chunk in enumerate(batch):
            doc_id = f"doc_{start_index + idx}"

            documents.append(chunk["content"])
            metadatas.append(chunk["metadata"])
            ids.append(doc_id)

        # 添加到ChromaDB
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def get_collection_stats(self) -> Dict:
        """获取集合统计信息"""
        if not self.collection:
            return {"error": "Collection not initialized"}

        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "status": "ready"
            }
        except Exception as e:
            return {
                "collection_name": self.collection_name,
                "error": str(e),
                "status": "error"
            }

    def clear_collection(self):
        """清空集合"""
        if self.collection:
            try:
                self.client.delete_collection(name=self.collection_name)
                logger.info(f"已删除集合: {self.collection_name}")
                self.collection = None
            except Exception as e:
                logger.error(f"删除集合失败: {e}")


class RAGIndexManager:
    """RAG索引管理器"""

    def __init__(self, raw_data_dir: str, output_dir: str, chroma_client):
        """
        初始化索引管理器

        Args:
            raw_data_dir: 原始数据目录
            output_dir: 输出目录
            chroma_client: ChromaDB客户端
        """
        self.pipeline = RAGDataPipeline(raw_data_dir, output_dir)
        self.index_builder = VectorIndexBuilder(chroma_client)
        self.output_dir = Path(output_dir)

    def rebuild_index(self, clear_existing: bool = False) -> Dict:
        """
        重建索引

        Args:
            clear_existing: 是否清空现有索引

        Returns:
            重建统计信息
        """
        logger.info("开始重建RAG索引")

        # 1. 清空现有索引（如果需要）
        if clear_existing:
            logger.info("清空现有索引...")
            self.index_builder.clear_collection()

        # 2. 处理所有文档
        logger.info("处理原始数据...")
        processing_stats = self.pipeline.process_all()

        # 3. 获取所有文档块
        logger.info("提取文档块...")
        chunks = self.pipeline.get_all_chunks()

        # 4. 构建向量索引
        logger.info("构建向量索引...")
        indexing_stats = self.index_builder.build_index(chunks)

        # 5. 获取最终统计
        collection_stats = self.index_builder.get_collection_stats()

        # 6. 保存完整报告
        report = {
            "processing": processing_stats,
            "indexing": indexing_stats,
            "collection": collection_stats
        }

        report_file = self.output_dir / "rebuild_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"索引重建完成，报告已保存到: {report_file}")

        return report

    def incremental_update(self, file_paths: List[str]) -> Dict:
        """
        增量更新索引

        Args:
            file_paths: 需要更新的文件路径列表

        Returns:
            更新统计信息
        """
        logger.info(f"增量更新 {len(file_paths)} 个文件")

        # 处理指定文件
        new_chunks = []
        for file_path in file_paths:
            # 这里需要实现单文件处理逻辑
            pass

        # 添加到索引
        if new_chunks:
            stats = self.index_builder.build_index(new_chunks)
            return stats

        return {"message": "No new chunks to index"}

    def get_status(self) -> Dict:
        """获取索引状态"""
        return {
            "collection_stats": self.index_builder.get_collection_stats(),
            "output_dir": str(self.output_dir),
            "processed_documents_file": str(self.output_dir / "processed_documents.json")
        }


def create_index_from_raw_data(
    raw_data_dir: str = "f:/Financial_Asset_QA_System_cyx-master/data/raw_data",
    output_dir: str = "f:/Financial_Asset_QA_System_cyx-master/data/processed",
    chroma_persist_dir: str = "f:/Financial_Asset_QA_System_cyx-master/data/chroma_db",
    clear_existing: bool = False
) -> Dict:
    """
    从原始数据创建索引的便捷函数

    Args:
        raw_data_dir: 原始数据目录
        output_dir: 输出目录
        chroma_persist_dir: ChromaDB持久化目录
        clear_existing: 是否清空现有索引

    Returns:
        构建报告
    """
    import chromadb

    # 初始化ChromaDB客户端
    client = chromadb.PersistentClient(path=chroma_persist_dir)

    # 创建索引管理器
    manager = RAGIndexManager(raw_data_dir, output_dir, client)

    # 重建索引
    report = manager.rebuild_index(clear_existing=clear_existing)

    return report


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 执行索引构建
    report = create_index_from_raw_data(clear_existing=True)

    print("\n" + "="*50)
    print("索引构建报告")
    print("="*50)
    print(f"处理文件数: {report['processing']['processed_files']}")
    print(f"失败文件数: {report['processing']['failed_files']}")
    print(f"总文档块数: {report['processing']['total_chunks']}")
    print(f"索引文档块数: {report['indexing']['indexed_chunks']}")
    print(f"集合文档数: {report['collection']['document_count']}")
    print("="*50)
