#!/usr/bin/env python3
"""
专业金融教材数据注入脚本
将MinerU处理的金融教材转换为RAG友好的格式
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Tuple


class FinancialTextbookProcessor:
    """金融教材处理器"""

    def __init__(self, source_dir: str, output_dir: str):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_all_textbooks(self):
        """处理所有教材"""
        md_files = list(self.source_dir.glob("*.md"))
        print(f"找到 {len(md_files)} 个Markdown文件")

        for md_file in md_files:
            print(f"\n处理: {md_file.name}")
            self.process_textbook(md_file)

    def process_textbook(self, md_file: Path):
        """处理单个教材"""
        # 读取内容
        content = md_file.read_text(encoding='utf-8')

        # 识别教材类型
        if "金融市场基础知识" in content:
            book_info = {
                "title": "金融市场基础知识",
                "category": "金融市场基础",
                "source": "中国证券业协会",
                "tags": ["证券从业", "金融市场", "基础知识", "考试教材"],
                "publisher": "中国财政经济出版社",
                "year": "2019"
            }
        elif "证券投资基金" in content:
            book_info = {
                "title": "证券投资基金基础知识",
                "category": "基金从业",
                "source": "基金从业资格考试专家组",
                "tags": ["基金从业", "证券投资基金", "习题解析", "考试教材"],
                "publisher": "中国金融出版社",
                "year": "2018"
            }
        else:
            book_info = {
                "title": "金融专业教材",
                "category": "金融知识",
                "source": "专业教材",
                "tags": ["金融", "教材"],
                "publisher": "未知",
                "year": "2020"
            }

        # 提取章节
        chapters = self.extract_chapters(content)
        print(f"  提取到 {len(chapters)} 个章节")

        # 保存章节
        for i, chapter in enumerate(chapters, 1):
            self.save_chapter(chapter, book_info, i)

    def extract_chapters(self, content: str) -> List[Dict[str, str]]:
        """提取章节内容"""
        chapters = []

        # 清理内容
        content = self.clean_content(content)

        # 按章节分割（匹配 "# 第X章" 或 "## 第X章"）
        chapter_pattern = r'#+\s*第[一二三四五六七八九十\d]+章[^\n]*'
        chapter_matches = list(re.finditer(chapter_pattern, content))

        if not chapter_matches:
            # 如果没有找到章节，尝试其他模式
            chapter_pattern = r'#+\s*第\s*\d+\s*章[^\n]*'
            chapter_matches = list(re.finditer(chapter_pattern, content))

        if not chapter_matches:
            print("  警告：未找到章节标记，将整个文档作为一章")
            chapters.append({
                "title": "完整内容",
                "content": content[:50000]  # 限制长度
            })
            return chapters

        # 提取每个章节
        for i, match in enumerate(chapter_matches):
            chapter_title = match.group().strip('#').strip()
            start_pos = match.end()

            # 确定章节结束位置
            if i < len(chapter_matches) - 1:
                end_pos = chapter_matches[i + 1].start()
            else:
                end_pos = len(content)

            chapter_content = content[start_pos:end_pos].strip()

            # 跳过太短的章节
            if len(chapter_content) < 200:
                continue

            # 提取章节内的小节
            sections = self.extract_sections(chapter_content)

            chapters.append({
                "title": chapter_title,
                "content": chapter_content[:30000],  # 限制单章长度
                "sections": sections
            })

        return chapters

    def extract_sections(self, chapter_content: str) -> List[Dict[str, str]]:
        """提取小节内容"""
        sections = []

        # 匹配小节标题（## 第X节 或 ### 一、二、三）
        section_pattern = r'##\s*第[一二三四五六七八九十\d]+节[^\n]*|###\s*[一二三四五六七八九十]+、[^\n]*'
        section_matches = list(re.finditer(section_pattern, chapter_content))

        if not section_matches:
            return sections

        for i, match in enumerate(section_matches):
            section_title = match.group().strip('#').strip()
            start_pos = match.end()

            if i < len(section_matches) - 1:
                end_pos = section_matches[i + 1].start()
            else:
                end_pos = len(chapter_content)

            section_content = chapter_content[start_pos:end_pos].strip()

            if len(section_content) < 100:
                continue

            sections.append({
                "title": section_title,
                "content": section_content[:10000]  # 限制小节长度
            })

        return sections

    def clean_content(self, content: str) -> str:
        """清理内容"""
        # 移除图片链接
        content = re.sub(r'!\[image\]\([^\)]+\)', '', content)

        # 移除多余空行
        content = re.sub(r'\n{3,}', '\n\n', content)

        # 移除版权信息等无关内容
        content = re.sub(r'ISBN.*?\n', '', content)
        content = re.sub(r'责任编辑.*?\n', '', content)
        content = re.sub(r'定价.*?\n', '', content)

        return content.strip()

    def save_chapter(self, chapter: Dict, book_info: Dict, chapter_num: int):
        """保存章节为独立文件"""
        # 生成文件名
        safe_title = re.sub(r'[^\w\s-]', '', chapter['title'])
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        filename = f"教材_{book_info['title']}_{safe_title}.md"
        filepath = self.output_dir / filename

        # 生成YAML frontmatter
        frontmatter = f"""---
category: {book_info['category']}
source: {book_info['source']}
tags: {book_info['tags']}
language: zh
update_date: 2026-03-11
difficulty: 入门
book_title: {book_info['title']}
publisher: {book_info['publisher']}
year: {book_info['year']}
chapter: {chapter_num}
---

"""

        # 生成内容
        content_parts = [frontmatter]
        content_parts.append(f"# {chapter['title']}\n\n")

        # 添加章节内容
        if 'sections' in chapter and chapter['sections']:
            for section in chapter['sections']:
                content_parts.append(f"## {section['title']}\n\n")
                content_parts.append(f"{section['content']}\n\n")
        else:
            content_parts.append(f"{chapter['content']}\n\n")

        # 添加学习要点
        content_parts.append(self.generate_study_points(chapter['title']))

        # 保存文件
        final_content = ''.join(content_parts)
        filepath.write_text(final_content, encoding='utf-8')
        print(f"  保存: {filename} ({len(final_content)} 字符)")

    def generate_study_points(self, chapter_title: str) -> str:
        """生成学习要点"""
        return f"""
## 学习要点

本章节涵盖了{chapter_title}的核心知识点，建议重点掌握：
1. 基本概念和定义
2. 核心原理和机制
3. 实际应用场景
4. 相关法规和规范

## 考试提示

- 本章内容为考试重点章节
- 建议结合实际案例理解
- 注意概念之间的联系和区别
- 多做练习题巩固知识点
"""


def main():
    """主函数"""
    print("=" * 60)
    print("金融教材数据注入脚本")
    print("=" * 60)

    # 设置路径
    source_dir = "../data/dealed_data"
    output_dir = "../data/knowledge"

    # 创建处理器
    processor = FinancialTextbookProcessor(source_dir, output_dir)

    # 处理所有教材
    processor.process_all_textbooks()

    print("\n" + "=" * 60)
    print("处理完成！")
    print(f"输出目录: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
