#!/usr/bin/env python
"""
增强的RAG索引构建脚本
Enhanced RAG Index Builder

功能亮点:
1. 表格提取和结构化
2. BGE向量化（可选）
3. 财务指标识别
4. 结构保留分块

使用方法:
    python build_enhanced_rag_index.py --clear --use-bge  # 使用BGE重建
    python build_enhanced_rag_index.py --clear            # 不使用BGE重建
    python build_enhanced_rag_index.py                    # 增量更新
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.rag.enhanced_data_pipeline import create_enhanced_index


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('enhanced_rag_index_build.log', encoding='utf-8')
        ]
    )


def print_banner():
    """打印横幅"""
    print("\n" + "="*60)
    print("增强的RAG索引构建工具")
    print("Enhanced RAG Index Builder")
    print("="*60 + "\n")


def print_report(report: dict):
    """打印构建报告"""
    print("\n" + "="*60)
    print("增强索引构建报告")
    print("="*60)

    # 处理统计
    processing = report.get('processing', {})
    print(f"\n📁 数据处理:")
    print(f"  - 总文件数: {processing.get('total_files', 0)}")
    print(f"  - 成功处理: {processing.get('processed_files', 0)}")
    print(f"  - 处理失败: {processing.get('failed_files', 0)}")
    print(f"  - 总文档块: {processing.get('total_chunks', 0)}")
    print(f"  - 提取表格: {processing.get('total_tables', 0)}")
    print(f"  - 包含财务指标的文件: {processing.get('files_with_metrics', 0)}")

    # 索引统计
    indexing = report.get('indexing', {})
    print(f"\n🔍 索引构建:")
    print(f"  - 索引文档块: {indexing.get('indexed_chunks', 0)}")
    print(f"    • 表格块: {indexing.get('table_chunks', 0)}")
    print(f"    • 文本块: {indexing.get('text_chunks', 0)}")
    print(f"  - 失败文档块: {indexing.get('failed_chunks', 0)}")
    print(f"  - 批次数量: {indexing.get('batches', 0)}")

    # 集合统计
    collection = report.get('collection', {})
    print(f"\n📊 向量数据库:")
    print(f"  - 集合名称: {collection.get('collection_name', 'N/A')}")
    print(f"  - 文档总数: {collection.get('document_count', 0)}")
    print(f"  - 使用BGE: {'是' if collection.get('uses_bge') else '否'}")
    if collection.get('uses_bge'):
        print(f"  - BGE模型: {collection.get('bge_model', 'N/A')}")
    print(f"  - 状态: {collection.get('status', 'unknown')}")

    print("\n" + "="*60 + "\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='构建增强的RAG索引（支持表格提取、BGE向量化、财务指标识别）'
    )

    parser.add_argument(
        '--clear',
        action='store_true',
        help='清空现有索引并重建'
    )

    parser.add_argument(
        '--use-bge',
        action='store_true',
        help='使用BGE向量化模型（BAAI/bge-large-zh-v1.5）'
    )

    parser.add_argument(
        '--raw-data-dir',
        type=str,
        default='f:/Financial_Asset_QA_System_cyx-master/data/raw_data',
        help='原始数据目录'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='f:/Financial_Asset_QA_System_cyx-master/data/processed',
        help='处理后数据输出目录'
    )

    parser.add_argument(
        '--chroma-dir',
        type=str,
        default='f:/Financial_Asset_QA_System_cyx-master/data/chroma_db',
        help='ChromaDB持久化目录'
    )

    parser.add_argument(
        '--collection-name',
        type=str,
        default='financial_knowledge_enhanced',
        help='集合名称'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细日志'
    )

    args = parser.parse_args()

    # 配置日志
    setup_logging(args.verbose)

    # 打印横幅
    print_banner()

    # 检查目录
    raw_data_path = Path(args.raw_data_dir)
    if not raw_data_path.exists():
        print(f"❌ 错误: 原始数据目录不存在: {args.raw_data_dir}")
        return 1

    # 显示配置
    print("📋 配置信息:")
    print(f"  - 原始数据目录: {args.raw_data_dir}")
    print(f"  - 输出目录: {args.output_dir}")
    print(f"  - ChromaDB目录: {args.chroma_dir}")
    print(f"  - 集合名称: {args.collection_name}")
    print(f"  - 使用BGE向量化: {'是' if args.use_bge else '否'}")
    print(f"  - 清空现有索引: {'是' if args.clear else '否'}")
    print()

    # BGE依赖检查
    if args.use_bge:
        try:
            import sentence_transformers
            print("✅ BGE依赖已安装")
        except ImportError:
            print("⚠️  警告: sentence-transformers未安装")
            print("   安装命令: pip install sentence-transformers")
            response = input("是否继续使用标准向量化? (y/N): ")
            if response.lower() != 'y':
                print("操作已取消")
                return 0
            args.use_bge = False

    # 确认操作
    if args.clear:
        print("⚠️  警告: 将清空现有索引并重建！")
        response = input("确认继续? (y/N): ")
        if response.lower() != 'y':
            print("操作已取消")
            return 0

    try:
        # 执行索引构建
        print("🚀 开始构建增强索引...\n")

        report = create_enhanced_index(
            raw_data_dir=args.raw_data_dir,
            output_dir=args.output_dir,
            chroma_persist_dir=args.chroma_dir,
            collection_name=args.collection_name,
            use_bge=args.use_bge,
            clear_existing=args.clear
        )

        # 打印报告
        print_report(report)

        # 检查是否有失败
        processing = report.get('processing', {})
        indexing = report.get('indexing', {})

        if processing.get('failed_files', 0) > 0 or indexing.get('failed_chunks', 0) > 0:
            print("⚠️  部分文件处理失败，请查看日志文件: enhanced_rag_index_build.log")
            return 1

        print("✅ 增强索引构建成功完成！")
        print("\n🎯 亮点功能:")
        print(f"  ✓ 表格提取: {report['processing']['total_tables']}个表格")
        print(f"  ✓ 财务指标识别: {report['processing']['files_with_metrics']}个文件")
        print(f"  ✓ 结构保留分块: {report['indexing']['table_chunks']}个表格块 + {report['indexing']['text_chunks']}个文本块")
        if args.use_bge:
            print(f"  ✓ BGE向量化: {report['collection']['bge_model']}")

        return 0

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        logging.exception("索引构建失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
