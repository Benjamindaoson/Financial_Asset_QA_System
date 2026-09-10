"""
QueryProfiler: Lightweight, rule-based query understanding.
Target: <2ms pure Python, 0 LLM by default.
"""
import re
from typing import List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

class QueryIntent(str, Enum):
    FACTUAL = "factual"
    SUMMARY = "summary"
    COMPARATIVE = "comparative"
    PROCEDURAL = "procedural"
    UNKNOWN = "unknown"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Language(str, Enum):
    ZH = "zh"
    EN = "en"
    MIXED = "mixed"

class PolicyAction(str, Enum):
    APPROVE = "approve"
    CONDITIONAL = "conditional"  # Requires disclosure
    REJECT = "reject"

@dataclass
class PolicyDecision:
    action: PolicyAction
    reasons: List[str] = field(default_factory=list)

@dataclass
class QueryProfile:
    """Multi-label query profile."""
    raw_query: str
    language: Language = Language.EN
    intents: List[QueryIntent] = field(default_factory=list)
    numeric_sensitive: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    cross_lingual: bool = False
    multi_modal: bool = False
    glossary_hits: List[str] = field(default_factory=list)
    confidence: float = 1.0
    signals: dict = field(default_factory=dict)  # Debug info

class QueryProfiler:
    """
    Rule-based query profiler. No LLM by default.
    """
    
    # Patterns
    NUMERIC_PATTERNS = [
        r'\d+[%％]',           # Percentages
        r'[\$¥€£]\s*[\d,]+',   # Currency
        r'\d{4}年',            # Year in Chinese
        r'\d{4}[/-]\d{1,2}',   # Dates YYYY-MM
        r'\d+\s*(万|亿|千|百|million|billion|k|m|b)', # Units
        r'\d+\.?\d*\s*(元|美元|港币|RMB|USD|CNY)',
        r'FY\d{4}',            # Fiscal year
    ]
    
    FACTUAL_KEYWORDS = [
        r'是多少', r'what is', r'how much', r'数字', r'金额', r'比例',
        r'收入', r'利润', r'revenue', r'profit', r'margin', r'rate',
        r'条款', r'clause', r'定义', r'definition', r'第.*条',
    ]
    
    SUMMARY_KEYWORDS = [
        r'总结', r'概述', r'summarize', r'summary', r'overview',
        r'什么是', r'介绍', r'explain', r'describe',
    ]
    
    COMPARATIVE_KEYWORDS = [
        r'比较', r'对比', r'compare', r'vs', r'versus', r'相比',
        r'增长', r'下降', r'变化', r'increase', r'decrease', r'change',
    ]
    
    PROCEDURAL_KEYWORDS = [
        r'如何', r'怎么', r'how to', r'步骤', r'流程', r'process',
    ]
    
    TABLE_KEYWORDS = [
        r'表', r'table', r'如上表', r'见表', r'表格',
    ]
    
    CHART_KEYWORDS = [
        r'图', r'chart', r'graph', r'如上图', r'见图',
    ]
    
    HIGH_RISK_KEYWORDS = [
        r'法律', r'legal', r'合规', r'compliance', r'监管', r'regulatory',
        r'责任', r'liability', r'违约', r'breach', r'处罚', r'penalty',
    ]
    
    def __init__(self, glossary=None):
        self.glossary = glossary
        self._compile_patterns()
    
    def _compile_patterns(self):
        self.numeric_re = [re.compile(p, re.I) for p in self.NUMERIC_PATTERNS]
        self.factual_re = [re.compile(p, re.I) for p in self.FACTUAL_KEYWORDS]
        self.summary_re = [re.compile(p, re.I) for p in self.SUMMARY_KEYWORDS]
        self.comparative_re = [re.compile(p, re.I) for p in self.COMPARATIVE_KEYWORDS]
        self.procedural_re = [re.compile(p, re.I) for p in self.PROCEDURAL_KEYWORDS]
        self.table_re = [re.compile(p, re.I) for p in self.TABLE_KEYWORDS]
        self.chart_re = [re.compile(p, re.I) for p in self.CHART_KEYWORDS]
        self.risk_re = [re.compile(p, re.I) for p in self.HIGH_RISK_KEYWORDS]
    
    def profile(self, query: str, context: dict = None) -> QueryProfile:
        """
        Profile a query using rule-based signals.
        Target: <2ms execution.
        """
        context = context or {}
        profile = QueryProfile(raw_query=query)
        signals = {}
        
        # 1. Language detection
        profile.language = self._detect_language(query)
        signals["language"] = profile.language.value
        
        # 2. Numeric sensitivity
        profile.numeric_sensitive = self._has_numeric(query)
        signals["numeric_patterns"] = profile.numeric_sensitive
        
        # 3. Intent classification (multi-label)
        profile.intents = self._classify_intents(query)
        signals["intents"] = [i.value for i in profile.intents]
        
        # 4. Risk level
        profile.risk_level = self._assess_risk(query, profile)
        signals["risk"] = profile.risk_level.value
        
        # 5. Multi-modal hints
        profile.multi_modal = self._has_multimodal_hints(query)
        signals["multi_modal"] = profile.multi_modal
        
        # 6. Glossary lookup (cross-lingual)
        if self.glossary:
            hits = self.glossary.lookup(query)
            profile.glossary_hits = [f"{h.cn_term}|{h.en_term}" for h in hits]
            profile.cross_lingual = len(hits) > 0 or profile.language == Language.MIXED
        signals["glossary_hits"] = len(profile.glossary_hits)
        
        # 7. Confidence (lower if ambiguous)
        if QueryIntent.UNKNOWN in profile.intents or len(profile.intents) > 2:
            profile.confidence = 0.5
        elif profile.numeric_sensitive and QueryIntent.FACTUAL in profile.intents:
            profile.confidence = 0.9
        
        profile.signals = signals
        return profile
    
    def _detect_language(self, text: str) -> Language:
        """Detect language by character ratio."""
        zh_count = len(re.findall(r'[\u4e00-\u9fff]', text))
        en_count = len(re.findall(r'[a-zA-Z]', text))
        total = zh_count + en_count
        
        if total == 0:
            return Language.EN
        
        zh_ratio = zh_count / total
        if zh_ratio > 0.7:
            return Language.ZH
        elif zh_ratio < 0.3:
            return Language.EN
        return Language.MIXED
    
    def _has_numeric(self, text: str) -> bool:
        """Check for numeric patterns."""
        return any(r.search(text) for r in self.numeric_re)
    
    def _classify_intents(self, text: str) -> List[QueryIntent]:
        """Multi-label intent classification."""
        intents = []
        
        if any(r.search(text) for r in self.factual_re):
            intents.append(QueryIntent.FACTUAL)
        if any(r.search(text) for r in self.summary_re):
            intents.append(QueryIntent.SUMMARY)
        if any(r.search(text) for r in self.comparative_re):
            intents.append(QueryIntent.COMPARATIVE)
        if any(r.search(text) for r in self.procedural_re):
            intents.append(QueryIntent.PROCEDURAL)
        
        if not intents:
            intents.append(QueryIntent.UNKNOWN)
        
        return intents
    
    def _assess_risk(self, text: str, profile: QueryProfile) -> RiskLevel:
        """Assess query risk level."""
        # High risk patterns
        if any(r.search(text) for r in self.risk_re):
            return RiskLevel.HIGH
        
        # Numeric + Factual = Medium+
        if profile.numeric_sensitive and QueryIntent.FACTUAL in profile.intents:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _has_multimodal_hints(self, text: str) -> bool:
        """Check for table/chart references."""
        return (any(r.search(text) for r in self.table_re) or 
                any(r.search(text) for r in self.chart_re))
