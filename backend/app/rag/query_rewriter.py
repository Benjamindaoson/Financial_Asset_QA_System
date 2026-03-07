"""Query rewriting for improved RAG retrieval."""
from typing import List, Dict, Optional
import re


class QueryRewriter:
    """
    Rewrites user queries to improve RAG retrieval.

    Implements:
    - Query expansion with synonyms
    - Financial term normalization
    - Multi-query generation for better recall
    """

    # Financial term synonyms
    SYNONYMS = {
        "股票": ["股份", "证券", "股权"],
        "价格": ["股价", "市价", "报价"],
        "涨": ["上涨", "增长", "升高"],
        "跌": ["下跌", "下降", "降低"],
        "市盈率": ["PE", "P/E", "市盈比"],
        "市净率": ["PB", "P/B", "市净比"],
        "净利润": ["净收益", "净盈利"],
        "营收": ["营业收入", "收入", "销售额"],
        "基金": ["投资基金", "证券投资基金"],
        "债券": ["固定收益证券", "债务证券"],
    }

    # English-Chinese mappings
    EN_CN_MAP = {
        "pe": "市盈率",
        "pb": "市净率",
        "roe": "净资产收益率",
        "eps": "每股收益",
        "revenue": "营收",
        "profit": "利润",
        "stock": "股票",
        "fund": "基金",
        "bond": "债券",
    }

    def __init__(self):
        self.synonym_map = self._build_synonym_map()

    def _build_synonym_map(self) -> Dict[str, List[str]]:
        """Build bidirectional synonym map."""
        synonym_map = {}
        for key, synonyms in self.SYNONYMS.items():
            synonym_map[key] = synonyms
            for syn in synonyms:
                if syn not in synonym_map:
                    synonym_map[syn] = [key] + [s for s in synonyms if s != syn]
        return synonym_map

    def normalize_query(self, query: str) -> str:
        """
        Normalize query by converting English terms to Chinese.

        Args:
            query: Original query

        Returns:
            Normalized query
        """
        normalized = query.lower()

        # Replace English financial terms
        for en_term, cn_term in self.EN_CN_MAP.items():
            normalized = re.sub(
                r'\b' + en_term + r'\b',
                cn_term,
                normalized,
                flags=re.IGNORECASE
            )

        return normalized

    def expand_query(self, query: str) -> List[str]:
        """
        Expand query with synonyms.

        Args:
            query: Original query

        Returns:
            List of expanded queries
        """
        expanded = [query]

        # Find terms that have synonyms
        for term, synonyms in self.synonym_map.items():
            if term in query:
                for synonym in synonyms[:2]:  # Limit to 2 synonyms per term
                    expanded_query = query.replace(term, synonym)
                    if expanded_query not in expanded:
                        expanded.append(expanded_query)

        return expanded[:5]  # Limit total expansions

    def generate_multi_queries(self, query: str) -> List[str]:
        """
        Generate multiple query variations for better recall.

        Args:
            query: Original query

        Returns:
            List of query variations
        """
        queries = []

        # Original query
        queries.append(query)

        # Normalized query
        normalized = self.normalize_query(query)
        if normalized != query:
            queries.append(normalized)

        # Expanded queries
        expanded = self.expand_query(query)
        queries.extend(expanded)

        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)

        return unique_queries[:5]  # Limit to 5 variations

    def extract_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from query.

        Args:
            query: Query text

        Returns:
            List of keywords
        """
        # Remove common stop words
        stop_words = {
            "的", "是", "在", "有", "和", "与", "或", "了", "吗", "呢",
            "什么", "怎么", "如何", "为什么", "哪个", "哪些",
            "the", "is", "are", "what", "how", "why", "which"
        }

        # Split into words - handle both Chinese and English
        # For Chinese, split by common punctuation and spaces
        # For English, use word boundaries
        words = []

        # Split by punctuation and spaces
        parts = re.split(r'[，。！？、；：\s]+', query)

        for part in parts:
            if not part:
                continue
            # For parts with mixed content, further split English words
            english_words = re.findall(r'[a-zA-Z]+', part)
            chinese_parts = re.sub(r'[a-zA-Z]+', '', part)

            # Add English words
            words.extend([w.lower() for w in english_words if len(w) > 1])

            # Add Chinese part as a whole if it's meaningful
            if chinese_parts and len(chinese_parts) > 1:
                words.append(chinese_parts)

        # Filter stop words and short words
        keywords = [
            word for word in words
            if word not in stop_words and len(word) > 1
        ]

        return keywords

    def rewrite(self, query: str) -> Dict[str, any]:
        """
        Rewrite query with all enhancements.

        Args:
            query: Original query

        Returns:
            Dictionary with rewritten queries and metadata
        """
        return {
            "original": query,
            "normalized": self.normalize_query(query),
            "expanded": self.expand_query(query),
            "multi_queries": self.generate_multi_queries(query),
            "keywords": self.extract_keywords(query)
        }
