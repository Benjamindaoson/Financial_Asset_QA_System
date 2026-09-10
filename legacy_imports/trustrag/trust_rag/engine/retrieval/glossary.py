"""
Entity Bridging for Cross-Language Precision.
Implements semantic glossary lookup and query rewriting.
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import os

@dataclass
class GlossaryEntry:
    """A single glossary term."""
    cn_term: str
    en_term: str
    scope: str  # "finance", "legal", "medical"
    semantic_weight: float = 1.0
    aliases: Dict[str, List[str]] = None  # {"cn": ["净利润"], "en": ["net income"]}

class SemanticGlossary:
    """
    In-memory glossary for term bridging.
    In production, this would be backed by Postgres/SQLite.
    """
    
    def __init__(self, glossary_path: Optional[str] = None):
        self.entries: List[GlossaryEntry] = []
        self.cn_index: Dict[str, GlossaryEntry] = {}
        self.en_index: Dict[str, GlossaryEntry] = {}
        
        if glossary_path and os.path.exists(glossary_path):
            self._load_from_file(glossary_path)
        else:
            self._load_default_entries()
    
    def _load_default_entries(self):
        """Load default finance/legal terms."""
        defaults = [
            GlossaryEntry("营业收入", "revenue", "finance", 1.0, {"cn": ["营收", "主营业务收入"], "en": ["operating revenue", "sales"]}),
            GlossaryEntry("净利润", "net profit", "finance", 1.0, {"cn": ["纯利润", "税后利润"], "en": ["net income", "earnings"]}),
            GlossaryEntry("毛利率", "gross margin", "finance", 1.0, {"cn": ["毛利润率"], "en": ["gross profit margin"]}),
            GlossaryEntry("资产负债表", "balance sheet", "finance", 1.0, {"cn": ["资产负债表"], "en": ["statement of financial position"]}),
            GlossaryEntry("现金流量表", "cash flow statement", "finance", 1.0, {"cn": ["现金流表"], "en": ["statement of cash flows"]}),
            GlossaryEntry("股东权益", "shareholders equity", "finance", 1.0, {"cn": ["所有者权益"], "en": ["owners equity"]}),
            GlossaryEntry("合同", "contract", "legal", 1.0, {"cn": ["协议", "契约"], "en": ["agreement"]}),
            GlossaryEntry("违约", "breach", "legal", 1.0, {"cn": ["违反合同"], "en": ["default", "breach of contract"]}),
        ]
        
        for entry in defaults:
            self.add_entry(entry)
    
    def _load_from_file(self, path: str):
        """Load glossary from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                entry = GlossaryEntry(
                    cn_term=item["cn_term"],
                    en_term=item["en_term"],
                    scope=item.get("scope", "general"),
                    semantic_weight=item.get("semantic_weight", 1.0),
                    aliases=item.get("aliases", {})
                )
                self.add_entry(entry)
    
    def add_entry(self, entry: GlossaryEntry):
        """Add entry to glossary and indices."""
        self.entries.append(entry)
        
        # Index by CN term
        self.cn_index[entry.cn_term.lower()] = entry
        if entry.aliases and "cn" in entry.aliases:
            for alias in entry.aliases["cn"]:
                self.cn_index[alias.lower()] = entry
        
        # Index by EN term
        self.en_index[entry.en_term.lower()] = entry
        if entry.aliases and "en" in entry.aliases:
            for alias in entry.aliases["en"]:
                self.en_index[alias.lower()] = entry
    
    def lookup(self, query: str) -> List[GlossaryEntry]:
        """
        Find glossary entries matching any term in the query.
        Returns list of matching entries.
        """
        matches = []
        query_lower = query.lower()
        
        # Check CN index
        for term, entry in self.cn_index.items():
            if term in query_lower:
                if entry not in matches:
                    matches.append(entry)
        
        # Check EN index
        for term, entry in self.en_index.items():
            if term in query_lower:
                if entry not in matches:
                    matches.append(entry)
        
        return matches

class QueryRewriter:
    """
    Rewrites queries by injecting bilingual terms from glossary.
    """
    
    def __init__(self, glossary: SemanticGlossary):
        self.glossary = glossary
    
    def rewrite(self, query: str) -> Tuple[str, List[str]]:
        """
        Rewrite query with bilingual term injection.
        
        Args:
            query: Original query
            
        Returns:
            Tuple of (enriched_query, matched_anchors)
        """
        matches = self.glossary.lookup(query)
        
        if not matches:
            return query, []
        
        # Collect terms to inject
        injections = []
        anchors = []
        
        for entry in matches:
            # Add both CN and EN terms
            injections.append(entry.cn_term)
            injections.append(entry.en_term)
            
            # Add high-weight aliases
            if entry.aliases:
                for alias in entry.aliases.get("cn", [])[:2]:
                    injections.append(alias)
                for alias in entry.aliases.get("en", [])[:2]:
                    injections.append(alias)
            
            # Build anchor string
            anchors.append(f"{entry.cn_term}|{entry.en_term}")
        
        # Dedupe and create enriched query
        unique_injections = list(dict.fromkeys(injections))
        enriched = f"{query} {' '.join(unique_injections)}"
        
        return enriched.strip(), anchors
    
    def extract_anchors(self, text: str) -> List[str]:
        """
        Extract glossary anchors from chunk text.
        Used during ingestion to tag chunks.
        """
        matches = self.glossary.lookup(text)
        anchors = []
        
        for entry in matches:
            anchors.append(f"{entry.cn_term}|{entry.en_term}")
        
        return anchors
