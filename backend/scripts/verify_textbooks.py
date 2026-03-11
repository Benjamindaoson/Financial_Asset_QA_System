#!/usr/bin/env python3
"""
验证新教材数据加载情况
"""

import sys
from pathlib import Path

# 添加backend目录到Python路径
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))


def main():
    """主函数"""
    print("=" * 60)
    print("教材数据验证脚本")
    print("=" * 60)

    # 检查知识库目录
    knowledge_dir = backend_dir / "data" / "knowledge"
    print(f"\n[1/3] 检查知识库目录: {knowledge_dir}")

    if not knowledge_dir.exists():
        print("  ❌ 知识库目录不存在！")
        return

    # 统计文件
    all_files = list(knowledge_dir.glob("*.md"))
    textbook_files = [f for f in all_files if f.name.startswith("教材_")]
    other_files = [f for f in all_files if not f.name.startswith("教材_")]

    print(f"\n[2/3] 文件统计:")
    print(f"  - 总文件数: {len(all_files)}")
    print(f"  - 教材文件: {len(textbook_files)}")
    print(f"  - 其他文件: {len(other_files)}")

    # 列出教材文件
    print(f"\n[3/3] 教材文件列表:")
    for i, file in enumerate(sorted(textbook_files), 1):
        # 读取文件前几行获取metadata
        try:
            content = file.read_text(encoding='utf-8')
            lines = content.split('\n')

            # 提取category
            category = "未知"
            for line in lines[:20]:
                if line.startswith('category:'):
                    category = line.split(':', 1)[1].strip()
                    break

            # 提取title
            title = "未知"
            for line in lines:
                if line.strip().startswith('# ') and not line.strip().startswith('##'):
                    title = line.strip().lstrip('#').strip()
                    break

            file_size = len(content)
            print(f"  {i}. {file.name}")
            print(f"     分类: {category}")
            print(f"     标题: {title}")
            print(f"     大小: {file_size:,} 字符")

        except Exception as e:
            print(f"  {i}. {file.name} (读取失败: {e})")

    print("\n" + "=" * 60)
    print("验证完成！")
    print("\n提示: 请启动后端服务后，系统会自动加载这些文件到向量数据库")
    print("命令: cd backend && uvicorn app.main:app --reload --port 8001")
    print("=" * 60)


if __name__ == "__main__":
    main()
