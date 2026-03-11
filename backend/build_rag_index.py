#!/usr/bin/env python
"""
RAG数据处理和索引构建脚本
Build RAG Index from Raw Data

使用方法:
    python build_rag_index.py --clear  # 清空现有索引并重建
    python build_rag_index.py          # 增量更新
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.rag.index_builder import create_index_from_raw_data


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('rag_index_build.log', encoding='utf-8')
        ]
    )


def print_banner():
    """打印横幅"""
    print("\n" + "="*60)
    print("RAG索引构建工具")
    print("Build RAG Index from Raw Data")
    print("="*60 + "\n")


def print_report(report: dict):
    """打印构建报告"""
    print("\n" + "="*60)
    print("索引构建报告")
    print("="*60)

    # 处理统计
    processing = report.get('processing', {})
    print(f"\n📁 数据处理:")
    print(f"  - 总文件数: {processing.get('total_files', 0)}")
    print(f"  - 成功处理: {processing.get('processed_files', 0)}")
    print(f"  - 处理失败: {processing.get('failed_files', 0)}")
    print(f"  - 总文档块: {processing.get('total_chunks', 0)}")

    # 索引统计
    indexing = report.get('indexing', {})
    print(f"\n🔍 索引构建:")
    print(f"  - 索引文档块: {indexing.get('indexed_chunks', 0)}")
    print(f"  - 失败文档块: {indexing.get('failed_chunks', 0)}")
    print(f"  - 批次数量: {indexing.get('batches', 0)}")

    # 集合统计
    collection = report.get('collection', {})
    print(f"\n📊 向量数据库:")
    print(f"  - 集合名称: {collection.get('collection_name', 'N/A')}")
    print(f"  - 文档总数: {collection.get('document_count', 0)}")
    print(f"  - 状态: {collection.get('status', 'unknown')}")

    print("\n" + "="*60 + "\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='从raw_data构建RAG索引'
    )

    parser.add_argument(
        '--clear',
        action='store_true',
        help='清空现有索引并重建'
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
    print(f"  - 清空现有索引: {'是' if args.clear else '否'}")
    print()

    # 确认操作
    if args.clear:
        print("⚠️  警告: 将清空现有索引并重建！")
        response = input("确认继续? (y/N): ")
        if response.lower() != 'y':
            print("操作已取消")
            return 0

    try:
        # 执行索引构建
        print("🚀 开始构建索引...\n")

        report = create_index_from_raw_data(
            raw_data_dir=args.raw_data_dir,
            output_dir=args.output_dir,
            chroma_persist_dir=args.chroma_dir,
            clear_existing=args.clear
        )

        # 打印报告
        print_report(report)

        # 检查是否有失败
        processing = report.get('processing', {})
        indexing = report.get('indexing', {})

        if processing.get('failed_files', 0) > 0 or indexing.get('failed_chunks', 0) > 0:
            print("⚠️  部分文件处理失败，请查看日志文件: rag_index_build.log")
            return 1

        print("✅ 索引构建成功完成！")
        return 0

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        logging.exception("索引构建失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
