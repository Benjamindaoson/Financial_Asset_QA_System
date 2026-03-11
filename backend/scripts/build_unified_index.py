"""
统一索引构建脚本 - 处理所有数据并构建向量索引
Unified Index Builder - Process All Data and Build Vector Index

功能：
1. 加载所有格式的数据（MD/PDF/JSON/HTML）
2. 清洗和标准化
3. 智能切分
4. 提取元数据
5. 构建向量索引（ChromaDB）
6. 构建 BM25 索引
"""
import sys
import os
import logging
import argparse
from pathlib import Path
from typing import List, Dict
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.data_loader import UnifiedDataLoader
from app.rag.data_cleaner import AdvancedCleaner
from app.rag.chunk_strategy import ChunkStrategy, ChunkType
from app.rag.metadata_extractor import MetadataExtractor
from app.rag.bge_embedding import BGEEmbedding
from app.config import settings

import chromadb
from chromadb.config import Settings as ChromaSettings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedIndexBuilder:
    """统一索引构建器"""

    def __init__(
        self,
        data_dir: str,
        chroma_dir: str,
        output_dir: str = None
    ):
        """
        初始化构建器

        Args:
            data_dir: 数据目录
            chroma_dir: ChromaDB 存储目录
            output_dir: 处理后数据输出目录（可选）
        """
        self.data_dir = Path(data_dir)
        self.chroma_dir = Path(chroma_dir)
        self.output_dir = Path(output_dir) if output_dir else None

        # 初始化组件
        self.loader = UnifiedDataLoader()
        self.cleaner = AdvancedCleaner()
        self.chunker = ChunkStrategy()
        self.metadata_extractor = MetadataExtractor()

        # 初始化 Embedding 模型
        logger.info(f"加载 Embedding 模型: {settings.EMBEDDING_MODEL}")
        self.embedding_model = BGEEmbedding(model_name=settings.EMBEDDING_MODEL)

        # 初始化 ChromaDB
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # 统计信息
        self.stats = {
            "files_loaded": 0,
            "files_failed": 0,
            "documents_cleaned": 0,
            "chunks_created": 0,
            "chunks_indexed": 0,
            "start_time": None,
            "end_time": None
        }

    def build(
        self,
        recursive: bool = True,
        deduplicate: bool = True,
        create_collections: bool = True
    ):
        """
        构建索引

        Args:
            recursive: 是否递归子目录
            deduplicate: 是否去重
            create_collections: 是否创建多个 collection
        """
        self.stats["start_time"] = datetime.now()

        logger.info("="*60)
        logger.info("开始构建统一索引")
        logger.info("="*60)
        logger.info(f"数据目录: {self.data_dir}")
        logger.info(f"ChromaDB 目录: {self.chroma_dir}")
        logger.info(f"递归: {recursive}")
        logger.info(f"去重: {deduplicate}")

        # 阶段 1: 加载数据
        logger.info("\n" + "="*60)
        logger.info("阶段 1: 加载数据")
        logger.info("="*60)
        documents = self._load_all_data(recursive)

        if not documents:
            logger.error("未加载到任何文档，退出")
            return

        # 阶段 2: 清洗数据
        logger.info("\n" + "="*60)
        logger.info("阶段 2: 清洗数据")
        logger.info("="*60)
        cleaned_docs = self._clean_documents(documents, deduplicate)

        # 阶段 3: 切分文档
        logger.info("\n" + "="*60)
        logger.info("阶段 3: 切分文档")
        logger.info("="*60)
        chunks = self._chunk_documents(cleaned_docs)

        # 阶段 4: 提取元数据
        logger.info("\n" + "="*60)
        logger.info("阶段 4: 提取元数据")
        logger.info("="*60)
        enriched_chunks = self._extract_metadata(chunks)

        # 阶段 5: 构建索引
        logger.info("\n" + "="*60)
        logger.info("阶段 5: 构建向量索引")
        logger.info("="*60)
        self._build_vector_index(enriched_chunks, create_collections)

        # 完成
        self.stats["end_time"] = datetime.now()
        self._print_summary()

    def _load_all_data(self, recursive: bool) -> List:
        """加载所有数据"""
        logger.info(f"从目录加载数据: {self.data_dir}")

        documents = []

        # 遍历子目录
        subdirs = [
            "knowledge",      # 教材知识
            "raw_data/knowledge",  # 原始知识
            "dealed_data"     # 已处理数据（MinerU）
        ]

        for subdir in subdirs:
            subdir_path = self.data_dir / subdir
            if subdir_path.exists():
                logger.info(f"加载子目录: {subdir}")
                docs = self.loader.load_directory(str(subdir_path), recursive=False)
                documents.extend(docs)
                logger.info(f"  加载 {len(docs)} 个文件")

        self.stats["files_loaded"] = len(documents)
        self.stats["files_failed"] = self.loader.error_count

        logger.info(f"\n加载完成:")
        logger.info(f"  成功: {self.stats['files_loaded']} 个文件")
        logger.info(f"  失败: {self.stats['files_failed']} 个文件")

        return documents

    def _clean_documents(self, documents: List, deduplicate: bool) -> List:
        """清洗文档"""
        logger.info(f"清洗 {len(documents)} 个文档")

        cleaned_docs = self.cleaner.clean_batch(documents, deduplicate=deduplicate)

        self.stats["documents_cleaned"] = len(cleaned_docs)

        logger.info(f"\n清洗完成:")
        logger.info(f"  清洗: {self.cleaner.cleaned_count} 个文档")
        logger.info(f"  去重: {self.cleaner.duplicate_count} 个重复")
        logger.info(f"  保留: {len(cleaned_docs)} 个文档")

        return cleaned_docs

    def _chunk_documents(self, documents: List) -> List:
        """切分文档"""
        logger.info(f"切分 {len(documents)} 个文档")

        all_chunks = []

        for doc in documents:
            chunks = self.chunker.chunk_document(
                content=doc.content,
                metadata=doc.metadata,
                doc_id=doc.doc_id
            )
            all_chunks.extend(chunks)

        self.stats["chunks_created"] = len(all_chunks)

        logger.info(f"\n切分完成:")
        logger.info(f"  总块数: {len(all_chunks)}")
        logger.info(f"  平均每文档: {len(all_chunks) / len(documents):.1f} 个块")

        return all_chunks

    def _extract_metadata(self, chunks: List) -> List[Dict]:
        """提取元数据"""
        logger.info(f"提取 {len(chunks)} 个块的元数据")

        enriched_chunks = []

        for chunk in chunks:
            metadata = self.metadata_extractor.extract_metadata(
                chunk_content=chunk.content,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                source_file=chunk.parent_doc_id,
                source_type=chunk.metadata.get("source_type", "unknown"),
                base_metadata=chunk.metadata
            )

            enriched_chunks.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "metadata": metadata
            })

        logger.info(f"\n元数据提取完成: {len(enriched_chunks)} 个块")

        return enriched_chunks

    def _build_vector_index(self, chunks: List[Dict], create_collections: bool):
        """构建向量索引"""
        logger.info(f"构建向量索引: {len(chunks)} 个块")

        if create_collections:
            # 创建多个 collection
            self._build_multiple_collections(chunks)
        else:
            # 创建单个 collection
            self._build_single_collection(chunks)

        self.stats["chunks_indexed"] = len(chunks)

    def _build_single_collection(self, chunks: List[Dict]):
        """构建单个 collection"""
        collection_name = "all_knowledge"

        logger.info(f"创建 collection: {collection_name}")

        # 删除旧 collection
        try:
            self.chroma_client.delete_collection(collection_name)
            logger.info(f"删除旧 collection: {collection_name}")
        except:
            pass

        # 创建新 collection
        collection = self.chroma_client.create_collection(
            name=collection_name,
            metadata={"description": "全部知识库"}
        )

        # 批量添加
        self._add_chunks_to_collection(collection, chunks)

    def _build_multiple_collections(self, chunks: List[Dict]):
        """构建多个 collection"""
        # 按类型分组
        collections_config = {
            "textbook_knowledge": {
                "description": "教材知识",
                "filter": lambda c: c["metadata"].book_title in ["证券投资基金基础知识", "金融市场基础知识"]
            },
            "finance_reports": {
                "description": "财务报告",
                "filter": lambda c: "报告" in c["metadata"].source_file or "财报" in c["metadata"].source_file
            },
            "exercises": {
                "description": "习题解析",
                "filter": lambda c: c["metadata"].chunk_type == "question"
            }
        }

        for coll_name, config in collections_config.items():
            # 过滤块
            filtered_chunks = [c for c in chunks if config["filter"](c)]

            if not filtered_chunks:
                logger.info(f"跳过空 collection: {coll_name}")
                continue

            logger.info(f"\n创建 collection: {coll_name} ({len(filtered_chunks)} 个块)")

            # 删除旧 collection
            try:
                self.chroma_client.delete_collection(coll_name)
            except:
                pass

            # 创建新 collection
            collection = self.chroma_client.create_collection(
                name=coll_name,
                metadata={"description": config["description"]}
            )

            # 添加块
            self._add_chunks_to_collection(collection, filtered_chunks)

        # 创建主索引（全部）
        logger.info(f"\n创建主索引: all_knowledge ({len(chunks)} 个块)")
        self._build_single_collection(chunks)

    def _add_chunks_to_collection(self, collection, chunks: List[Dict], batch_size: int = 100):
        """批量添加块到 collection"""
        logger.info(f"添加 {len(chunks)} 个块到 collection: {collection.name}")

        total_batches = (len(chunks) + batch_size - 1) // batch_size

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1

            logger.info(f"  处理批次 {batch_num}/{total_batches} ({len(batch)} 个块)")

            # 准备数据
            ids = [c["chunk_id"] for c in batch]
            documents = [c["content"] for c in batch]

            # 生成 embeddings
            embeddings = self.embedding_model.encode_batch(documents)

            # 准备元数据（转换为字典）
            metadatas = []
            for c in batch:
                meta = c["metadata"]
                # 转换为简单字典（ChromaDB 要求）
                meta_dict = {
                    "source_file": meta.source_file,
                    "source_type": meta.source_type,
                    "chunk_type": meta.chunk_type,
                    "book_title": meta.book_title or "",
                    "chapter": meta.chapter or "",
                    "difficulty": meta.difficulty,
                    "content_length": meta.content_length,
                    "has_formula": str(meta.has_formula),
                    "has_table": str(meta.has_table)
                }
                metadatas.append(meta_dict)

            # 添加到 collection
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )

        logger.info(f"完成添加到 collection: {collection.name}")

    def _print_summary(self):
        """打印总结"""
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()

        logger.info("\n" + "="*60)
        logger.info("索引构建完成")
        logger.info("="*60)
        logger.info(f"总耗时: {duration:.2f} 秒")
        logger.info(f"\n统计信息:")
        logger.info(f"  文件加载: {self.stats['files_loaded']} 个")
        logger.info(f"  文件失败: {self.stats['files_failed']} 个")
        logger.info(f"  文档清洗: {self.stats['documents_cleaned']} 个")
        logger.info(f"  块创建: {self.stats['chunks_created']} 个")
        logger.info(f"  块索引: {self.stats['chunks_indexed']} 个")
        logger.info(f"\n索引位置: {self.chroma_dir}")
        logger.info("="*60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="构建统一向量索引")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=r"F:\Financial_Asset_QA_System_cyx-master\data",
        help="数据目录"
    )
    parser.add_argument(
        "--chroma-dir",
        type=str,
        default=r"F:\Financial_Asset_QA_System_cyx-master\backend\data\chroma_db",
        help="ChromaDB 存储目录"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="处理后数据输出目录（可选）"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="不递归子目录"
    )
    parser.add_argument(
        "--no-deduplicate",
        action="store_true",
        help="不去重"
    )
    parser.add_argument(
        "--single-collection",
        action="store_true",
        help="只创建单个 collection"
    )

    args = parser.parse_args()

    # 创建构建器
    builder = UnifiedIndexBuilder(
        data_dir=args.data_dir,
        chroma_dir=args.chroma_dir,
        output_dir=args.output_dir
    )

    # 构建索引
    builder.build(
        recursive=not args.no_recursive,
        deduplicate=not args.no_deduplicate,
        create_collections=not args.single_collection
    )


if __name__ == "__main__":
    main()
