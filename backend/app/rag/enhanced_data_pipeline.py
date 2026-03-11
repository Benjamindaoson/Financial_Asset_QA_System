"""
增强的数据处理管道
Enhanced Data Processing Pipeline

整合所有优化功能:
1. 增强的文档解析（表格提取）
2. BGE向量化
3. 结构保留分块
4. 财务指标提取
"""
import logging
from pathlib import Path
from typing import List, Dict, Optional
import json

from app.rag.enhanced_document_parser import EnhancedDocumentParser
from app.rag.data_pipeline import MarkdownProcessor, HTMLProcessor

logger = logging.getLogger(__name__)


class EnhancedRAGDataPipeline:
    """增强的RAG数据处理管道"""

    def __init__(self, raw_data_dir: str, output_dir: str):
        """
        初始化增强数据管道

        Args:
            raw_data_dir: 原始数据目录
            output_dir: 输出目录
        """
        self.raw_data_dir = Path(raw_data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化增强解析器
        self.enhanced_parser = EnhancedDocumentParser()

        # 初始化基础处理器（用于Markdown和HTML）
        self.markdown_processor = MarkdownProcessor()
        self.html_processor = HTMLProcessor()

        self.processed_documents = []
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "total_chunks": 0,
            "total_tables": 0,
            "files_with_metrics": 0
        }

    def process_all(self) -> Dict:
        """
        处理所有文件

        Returns:
            处理统计信息
        """
        logger.info(f"开始处理数据目录: {self.raw_data_dir}")

        # 遍历所有文件
        for file_path in self.raw_data_dir.rglob('*'):
            if file_path.is_file():
                self.stats["total_files"] += 1
                self._process_file(file_path)

        # 保存处理结果
        self._save_results()

        # 更新统计
        self.stats["processed_files"] = len(self.processed_documents)
        self.stats["failed_files"] = self.stats["total_files"] - self.stats["processed_files"]
        self.stats["total_chunks"] = sum(
            len(doc["chunks"]) for doc in self.processed_documents
        )
        self.stats["total_tables"] = sum(
            doc.get("table_count", 0) for doc in self.processed_documents
        )
        self.stats["files_with_metrics"] = sum(
            1 for doc in self.processed_documents
            if any(
                chunk["metadata"].get("financial_metrics")
                for chunk in doc["chunks"]
            )
        )

        logger.info(f"处理完成: {self.stats}")

        return self.stats

    def _process_file(self, file_path: Path):
        """处理单个文件"""
        suffix = file_path.suffix.lower()

        try:
            if suffix == '.pdf':
                # 使用增强解析器处理PDF
                result = self.enhanced_parser.parse_and_chunk(str(file_path))
                self.processed_documents.append(result)
                logger.info(
                    f"成功处理PDF: {file_path.name} "
                    f"({len(result['chunks'])} chunks, "
                    f"{result.get('table_count', 0)} tables)"
                )

            elif suffix == '.md':
                # 使用基础Markdown处理器
                result = self.markdown_processor.process(str(file_path))
                if result:
                    self.processed_documents.append(result)
                    logger.info(f"成功处理Markdown: {file_path.name} ({len(result['chunks'])} chunks)")

            elif suffix == '.html':
                # 使用基础HTML处理器
                result = self.html_processor.process(str(file_path))
                if result:
                    self.processed_documents.append(result)
                    logger.info(f"成功处理HTML: {file_path.name} ({len(result['chunks'])} chunks)")

            else:
                logger.debug(f"跳过不支持的文件类型: {file_path}")

        except Exception as e:
            logger.error(f"处理文件失败 {file_path}: {e}")

    def _save_results(self):
        """保存处理结果"""
        output_file = self.output_dir / "enhanced_processed_documents.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.processed_documents, f, ensure_ascii=False, indent=2)

        logger.info(f"处理结果已保存到: {output_file}")

        # 保存统计信息
        stats_file = self.output_dir / "enhanced_processing_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)

    def get_all_chunks(self) -> List[Dict]:
        """
        获取所有文档块

        Returns:
            所有文档块的列表
        """
        all_chunks = []

        for doc in self.processed_documents:
            for chunk in doc["chunks"]:
                # 合并文档元数据和块信息
                chunk_with_metadata = {
                    "content": chunk["content"],
                    "metadata": {
                        "source_file": doc["file_name"],
                        "file_type": doc["file_type"],
                        "chunk_index": chunk["metadata"]["chunk_index"],
                        "chunk_type": chunk["metadata"].get("chunk_type", "text"),
                        "is_table": chunk["metadata"].get("is_table", False),
                        **doc.get("metadata", {})
                    }
                }

                # 添加财务指标（如果有）
                if chunk["metadata"].get("financial_metrics"):
                    chunk_with_metadata["metadata"]["financial_metrics"] = chunk["metadata"]["financial_metrics"]

                all_chunks.append(chunk_with_metadata)

        return all_chunks


class EnhancedVectorIndexBuilder:
    """增强的向量索引构建器（使用BGE）"""

    def __init__(
        self,
        chroma_client,
        collection_name: str = "financial_knowledge_enhanced",
        use_bge: bool = True,
        bge_model: str = "BAAI/bge-large-zh-v1.5"
    ):
        """
        初始化增强索引构建器

        Args:
            chroma_client: ChromaDB客户端
            collection_name: 集合名称
            use_bge: 是否使用BGE向量化
            bge_model: BGE模型名称
        """
        self.client = chroma_client
        self.collection_name = collection_name
        self.use_bge = use_bge
        self.bge_model = bge_model
        self.collection = None

    def create_or_get_collection(self):
        """创建或获取集合"""
        try:
            # 尝试获取现有集合
            self.collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"使用现有集合: {self.collection_name}")

        except Exception:
            # 创建新集合
            if self.use_bge:
                from app.rag.bge_embedding import create_bge_collection
                self.collection = create_bge_collection(
                    self.client,
                    self.collection_name,
                    self.bge_model
                )
                logger.info(f"创建BGE集合: {self.collection_name}")
            else:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Enhanced financial knowledge base"}
                )
                logger.info(f"创建标准集合: {self.collection_name}")

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
            "batches": 0,
            "table_chunks": 0,
            "text_chunks": 0
        }

        logger.info(f"开始构建索引，共 {len(chunks)} 个文档块")

        # 批量处理
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            try:
                self._index_batch(batch, start_index=i)
                stats["indexed_chunks"] += len(batch)
                stats["batches"] += 1

                # 统计表格和文本块
                for chunk in batch:
                    if chunk["metadata"].get("is_table"):
                        stats["table_chunks"] += 1
                    else:
                        stats["text_chunks"] += 1

                if (i + batch_size) % 500 == 0:
                    logger.info(f"已处理 {i + batch_size}/{len(chunks)} 个文档块")

            except Exception as e:
                logger.error(f"批次 {i}-{i+batch_size} 索引失败: {e}")
                stats["failed_chunks"] += len(batch)

        logger.info(f"索引构建完成: {stats}")
        return stats

    def _index_batch(self, batch: List[Dict], start_index: int):
        """索引一批文档"""
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

    def clear_collection(self):
        """清空集合"""
        if self.collection:
            try:
                self.client.delete_collection(name=self.collection_name)
                logger.info(f"已删除集合: {self.collection_name}")
                self.collection = None
            except Exception as e:
                logger.error(f"删除集合失败: {e}")

    def get_collection_stats(self) -> Dict:
        """获取集合统计信息"""
        if not self.collection:
            return {"error": "Collection not initialized"}

        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "uses_bge": self.use_bge,
                "bge_model": self.bge_model if self.use_bge else None,
                "status": "ready"
            }
        except Exception as e:
            return {
                "collection_name": self.collection_name,
                "error": str(e),
                "status": "error"
            }


def create_enhanced_index(
    raw_data_dir: str = "f:/Financial_Asset_QA_System_cyx-master/data/raw_data",
    output_dir: str = "f:/Financial_Asset_QA_System_cyx-master/data/processed",
    chroma_persist_dir: str = "f:/Financial_Asset_QA_System_cyx-master/data/chroma_db",
    collection_name: str = "financial_knowledge_enhanced",
    use_bge: bool = True,
    clear_existing: bool = False
) -> Dict:
    """
    创建增强索引的便捷函数

    Args:
        raw_data_dir: 原始数据目录
        output_dir: 输出目录
        chroma_persist_dir: ChromaDB持久化目录
        collection_name: 集合名称
        use_bge: 是否使用BGE向量化
        clear_existing: 是否清空现有索引

    Returns:
        构建报告
    """
    import chromadb

    # 初始化ChromaDB客户端
    client = chromadb.PersistentClient(path=chroma_persist_dir)

    # 创建数据管道
    pipeline = EnhancedRAGDataPipeline(raw_data_dir, output_dir)

    # 创建索引构建器
    index_builder = EnhancedVectorIndexBuilder(
        client,
        collection_name,
        use_bge=use_bge
    )

    # 清空现有索引（如果需要）
    if clear_existing:
        logger.info("清空现有索引...")
        index_builder.clear_collection()

    # 处理所有文档
    logger.info("处理原始数据...")
    processing_stats = pipeline.process_all()

    # 获取所有文档块
    logger.info("提取文档块...")
    chunks = pipeline.get_all_chunks()

    # 构建向量索引
    logger.info("构建向量索引...")
    indexing_stats = index_builder.build_index(chunks)

    # 获取最终统计
    collection_stats = index_builder.get_collection_stats()

    # 生成报告
    report = {
        "processing": processing_stats,
        "indexing": indexing_stats,
        "collection": collection_stats
    }

    # 保存报告
    report_file = Path(output_dir) / "enhanced_build_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"增强索引构建完成，报告已保存到: {report_file}")

    return report


if __name__ == "__main__":
    # 测试
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 执行增强索引构建
    report = create_enhanced_index(
        use_bge=False,  # 先不使用BGE，避免依赖问题
        clear_existing=True
    )

    print("\n" + "="*60)
    print("增强索引构建报告")
    print("="*60)
    print(f"处理文件数: {report['processing']['processed_files']}")
    print(f"失败文件数: {report['processing']['failed_files']}")
    print(f"总文档块数: {report['processing']['total_chunks']}")
    print(f"表格数量: {report['processing']['total_tables']}")
    print(f"包含财务指标的文件: {report['processing']['files_with_metrics']}")
    print(f"索引文档块数: {report['indexing']['indexed_chunks']}")
    print(f"  - 表格块: {report['indexing']['table_chunks']}")
    print(f"  - 文本块: {report['indexing']['text_chunks']}")
    print(f"集合文档数: {report['collection']['document_count']}")
    print("="*60)
