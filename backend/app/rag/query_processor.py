"""
查询预处理器 - 查询清洗、同义词扩展、术语标准化
Query Processor - Cleaning, Synonym Expansion, Term Normalization
"""
import re
from typing import List, Set, Dict
from pathlib import Path
from app.config import settings


class QueryProcessor:
    """查询预处理器"""

    # 金融术语同义词映射
    SYNONYM_MAP = {
        "pe": ["市盈率", "price-to-earnings", "p/e ratio"],
        "pb": ["市净率", "price-to-book", "p/b ratio"],
        "ps": ["市销率", "price-to-sales"],
        "roe": ["净资产收益率", "return on equity"],
        "roa": ["资产收益率", "return on assets"],
        "eps": ["每股收益", "earnings per share"],
        "市盈率": ["pe", "price-to-earnings"],
        "市净率": ["pb", "price-to-book"],
    }

    def __init__(self):
        self.financial_terms = self._load_financial_dictionary()

    def _load_financial_dictionary(self) -> Set[str]:
        """加载金融词典"""
        dict_path = Path(settings.FINANCIAL_DICT_PATH)
        if not dict_path.exists():
            return set()

        terms = set()
        with open(dict_path, 'r', encoding='utf-8') as f:
            for line in f:
                term = line.strip()
                if term:
                    terms.add(term)
        return terms

    def clean_query(self, query: str) -> str:
        """清洗查询文本"""
        # 移除多余空格（包括中文之间的空格）
        cleaned = re.sub(r'\s+', '', query)
        cleaned = cleaned.strip()

        # 标准化标点符号
        cleaned = re.sub(r'[？?]+', '？', cleaned)
        cleaned = re.sub(r'[！!]+', '！', cleaned)
        cleaned = re.sub(r'[。.]+', '。', cleaned)

        return cleaned

    def expand_synonyms(self, query: str) -> str:
        """扩展同义词"""
        query_lower = query.lower()
        expanded = query

        for term, synonyms in self.SYNONYM_MAP.items():
            if term in query_lower or term in query:
                # 找到第一个同义词进行替换
                for synonym in synonyms:
                    if synonym not in query and synonym not in query_lower:
                        expanded = query + " " + synonym
                        break
                break

        return expanded

    def normalize_financial_terms(self, query: str) -> str:
        """标准化金融术语"""
        normalized = query

        # 将英文缩写转换为中文全称
        term_map = {
            "PE": "市盈率",
            "PB": "市净率",
            "PS": "市销率",
            "ROE": "净资产收益率",
            "ROA": "资产收益率",
            "EPS": "每股收益",
        }

        for abbr, full_name in term_map.items():
            # 匹配独立的缩写词（不在其他单词中）
            pattern = r'\b' + abbr + r'\b'
            normalized = re.sub(pattern, full_name, normalized, flags=re.IGNORECASE)

        return normalized

    def process(self, query: str) -> Dict[str, any]:
        """
        完整的查询预处理流程

        Args:
            query: 原始查询

        Returns:
            处理结果字典
        """
        # 1. 清洗
        cleaned = self.clean_query(query)

        # 2. 标准化术语
        normalized = self.normalize_financial_terms(cleaned)

        # 3. 扩展同义词（可选）
        expanded_queries = [normalized]
        if settings.QUERY_SYNONYM_EXPANSION:
            expanded = self.expand_synonyms(normalized)
            if expanded != normalized:
                expanded_queries.append(expanded)

        return {
            "original": query,
            "cleaned": cleaned,
            "normalized": normalized,
            "expanded_queries": expanded_queries,
        }
