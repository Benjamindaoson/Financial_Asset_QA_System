"""
简化的知识库索引构建脚本 - 用于Railway部署
Build Knowledge Index for Railway Deployment
"""
import sys
import os
import logging
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 设置HuggingFace镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


def build_index():
    """构建知识库索引"""
    logger.info("="*60)
    logger.info("开始构建知识库索引")
    logger.info("="*60)

    # 打印当前工作目录
    cwd = Path.cwd()
    logger.info(f"当前工作目录: {cwd}")

    # 打印脚本位置
    script_dir = Path(__file__).parent
    logger.info(f"脚本目录: {script_dir}")

    from app.rag.hybrid_pipeline import HybridRAGPipeline
    from app.config import settings

    # 检查知识库目录
    knowledge_dir = Path(__file__).parent.parent / "data" / "knowledge"
    logger.info(f"知识库目录路径: {knowledge_dir}")
    logger.info(f"知识库目录存在: {knowledge_dir.exists()}")

    if not knowledge_dir.exists():
        logger.error(f"知识库目录不存在: {knowledge_dir}")
        # 尝试列出父目录内容
        parent_dir = knowledge_dir.parent
        if parent_dir.exists():
            logger.info(f"父目录 {parent_dir} 内容:")
            for item in parent_dir.iterdir():
                logger.info(f"  - {item.name}")
        return False

    # 统计知识文件
    md_files = list(knowledge_dir.glob("*.md"))
    logger.info(f"找到 {len(md_files)} 个知识文件")

    # 列出前5个文件
    for i, f in enumerate(md_files[:5]):
        logger.info(f"  [{i+1}] {f.name}")

    if len(md_files) == 0:
        logger.error("没有找到任何知识文件")
        return False

    # 初始化RAG pipeline
    logger.info("初始化RAG pipeline...")
    pipeline = HybridRAGPipeline()

    # 加载文档
    logger.info("加载文档到向量数据库...")
    documents_loaded = 0

    for md_file in md_files:
        try:
            logger.info(f"处理文件: {md_file.name}")
            content = md_file.read_text(encoding='utf-8')

            # 简单切分（按段落）
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip() and len(p.strip()) > 20]

            logger.info(f"  切分为 {len(paragraphs)} 个段落")

            # 添加到向量数据库
            for idx, para in enumerate(paragraphs):
                chunk_id = f"{md_file.stem}_{idx}"
                metadata = {
                    "source": md_file.name,
                    "source_type": "knowledge",
                    "chunk_type": "paragraph",
                    "file_path": str(md_file)
                }

                # 使用pipeline的collection添加文档
                try:
                    pipeline.collection.add(
                        ids=[chunk_id],
                        documents=[para],
                        metadatas=[metadata]
                    )
                    documents_loaded += 1
                except Exception as e:
                    logger.warning(f"  添加文档失败 {chunk_id}: {e}")

        except Exception as e:
            logger.error(f"处理文件失败 {md_file.name}: {e}")
            continue

    logger.info("="*60)
    logger.info(f"索引构建完成！共加载 {documents_loaded} 个文档块")
    logger.info("="*60)

    return documents_loaded > 0


if __name__ == "__main__":
    success = build_index()
    sys.exit(0 if success else 1)
