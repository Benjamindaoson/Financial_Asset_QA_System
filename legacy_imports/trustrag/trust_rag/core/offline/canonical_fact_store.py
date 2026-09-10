"""
Canonical Fact Store - Verified Facts for Fast Path Retrieval.

Supports:
- Multiple entities (companies)
- Multiple metrics
- Multiple periods
- Aliases for fuzzy matching
"""
import json
import re
import logging
from typing import List, Optional, Dict, Set
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CanonicalFact(BaseModel):
    """A verified fact from authoritative source."""
    entity: str
    metric: str
    period: str
    value: float
    unit: str
    source_evidence_ids: List[str] = Field(default_factory=list)
    authority_rank: int = 1
    aliases: List[str] = Field(default_factory=list)  # Alternative names for metric
    entity_aliases: List[str] = Field(default_factory=list)  # Alternative names for entity


class CanonicalFactStore:
    """
    Fast-path fact store for verified canonical facts.
    
    Features:
    - Exact and fuzzy matching
    - Entity and metric aliases
    - Period normalization
    - Authority-based ranking
    """
    
    # Common metric aliases
    METRIC_ALIASES = {
        "revenue": ["sales", "total revenue", "net sales", "收入", "营收", "营业收入"],
        "net_income": ["net profit", "net earnings", "profit", "净利润", "净收入", "纯利"],
        "gross_profit": ["gross margin", "毛利", "毛利润"],
        "operating_income": ["operating profit", "营业利润", "经营利润"],
        "ebitda": ["息税折旧摊销前利润"],
        "eps": ["earnings per share", "每股收益", "每股盈利"],
        "margin": ["profit margin", "利润率", "边际"],
    }
    
    # Common entity aliases
    ENTITY_ALIASES = {
        "Nvidia": ["nvidia", "nvda", "英伟达"],
        "Apple": ["apple", "aapl", "苹果", "苹果公司"],
        "Microsoft": ["microsoft", "msft", "微软", "微软公司"],
        "Google": ["google", "alphabet", "googl", "goog", "谷歌", "字母表"],
        "Amazon": ["amazon", "amzn", "亚马逊"],
        "Meta": ["meta", "facebook", "fb", "脸书", "元宇宙"],
        "Tesla": ["tesla", "tsla", "特斯拉"],
    }
    
    # Period normalization patterns
    PERIOD_PATTERNS = [
        (r'FY\s*(\d{4})', r'FY\1'),
        (r'fiscal\s*(?:year)?\s*(\d{4})', r'FY\1'),
        (r'(\d{4})\s*财年', r'FY\1'),
        (r'Q([1-4])\s*(?:FY)?(\d{4})', r'Q\1 \2'),
        (r'(\d{4})\s*[年]?\s*第?([1-4])\s*季度?', r'Q\2 \1'),
    ]
    
    def __init__(self, store_path: str):
        self.store_path = store_path
        self.facts: List[CanonicalFact] = []
        self._entity_index: Dict[str, List[int]] = {}  # entity_key -> fact indices
        self._metric_index: Dict[str, List[int]] = {}  # metric_key -> fact indices
        self._load()
        self._build_indices()
    
    def _load(self):
        """Load facts from JSONL file."""
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("type") == "header":
                            continue
                        
                        # Add default aliases from global mappings
                        if "aliases" not in data:
                            data["aliases"] = []
                        if "entity_aliases" not in data:
                            data["entity_aliases"] = []
                        
                        # Enrich with global aliases
                        metric = data.get("metric", "")
                        if metric in self.METRIC_ALIASES:
                            data["aliases"].extend(self.METRIC_ALIASES[metric])
                        
                        entity = data.get("entity", "")
                        if entity in self.ENTITY_ALIASES:
                            data["entity_aliases"].extend(self.ENTITY_ALIASES[entity])
                        
                        self.facts.append(CanonicalFact(**data))
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON at line {line_num}: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to parse fact at line {line_num}: {e}")
            
            logger.info(f"Loaded {len(self.facts)} facts from {self.store_path}")
            
        except FileNotFoundError:
            logger.warning(f"Fact store not found: {self.store_path}")
    
    def _build_indices(self):
        """Build indices for fast lookup."""
        self._entity_index = {}
        self._metric_index = {}
        
        for idx, fact in enumerate(self.facts):
            # Entity index
            entity_key = self._normalize_entity(fact.entity)
            if entity_key not in self._entity_index:
                self._entity_index[entity_key] = []
            self._entity_index[entity_key].append(idx)
            
            # Also index aliases
            for alias in fact.entity_aliases:
                alias_key = self._normalize_entity(alias)
                if alias_key not in self._entity_index:
                    self._entity_index[alias_key] = []
                self._entity_index[alias_key].append(idx)
            
            # Metric index
            metric_key = self._normalize_metric(fact.metric)
            if metric_key not in self._metric_index:
                self._metric_index[metric_key] = []
            self._metric_index[metric_key].append(idx)
            
            # Also index aliases
            for alias in fact.aliases:
                alias_key = self._normalize_metric(alias)
                if alias_key not in self._metric_index:
                    self._metric_index[alias_key] = []
                self._metric_index[alias_key].append(idx)
    
    def lookup(
        self,
        metric: str,
        period: str,
        entity: Optional[str] = None
    ) -> Optional[CanonicalFact]:
        """
        Look up a canonical fact.
        
        Args:
            metric: Metric name or alias
            period: Time period
            entity: Optional entity name or alias
            
        Returns:
            Matching CanonicalFact or None
        """
        # Normalize inputs
        norm_metric = self._normalize_metric(metric)
        norm_period = self._normalize_period(period)
        
        # Get candidate indices from metric index
        metric_candidates = set(self._metric_index.get(norm_metric, []))
        
        # If no direct match, try aliases
        if not metric_candidates:
            for m_key, aliases in self.METRIC_ALIASES.items():
                for alias in aliases:
                    if self._normalize_metric(alias) == norm_metric:
                        metric_candidates.update(self._metric_index.get(m_key, []))
                        break
        
        if not metric_candidates:
            return None
        
        # Filter by entity if specified
        if entity:
            norm_entity = self._normalize_entity(entity)
            entity_candidates = set(self._entity_index.get(norm_entity, []))
            
            # If no direct match, try aliases
            if not entity_candidates:
                for e_key, aliases in self.ENTITY_ALIASES.items():
                    for alias in aliases:
                        if self._normalize_entity(alias) == norm_entity:
                            entity_candidates.update(self._entity_index.get(e_key, []))
                            break
            
            candidates = metric_candidates & entity_candidates
        else:
            candidates = metric_candidates
        
        if not candidates:
            return None
        
        # Filter by period
        matching_facts = []
        for idx in candidates:
            fact = self.facts[idx]
            if self._period_matches(norm_period, self._normalize_period(fact.period)):
                matching_facts.append(fact)
        
        if not matching_facts:
            return None
        
        # Return highest authority
        matching_facts.sort(key=lambda f: f.authority_rank)
        return matching_facts[0]
    
    def search(
        self,
        entity: Optional[str] = None,
        metric: Optional[str] = None,
        period: Optional[str] = None
    ) -> List[CanonicalFact]:
        """
        Search for facts matching criteria.
        
        Args:
            entity: Optional entity filter
            metric: Optional metric filter
            period: Optional period filter
            
        Returns:
            List of matching facts
        """
        results = self.facts.copy()
        
        if entity:
            norm_entity = self._normalize_entity(entity)
            results = [
                f for f in results
                if self._normalize_entity(f.entity) == norm_entity or
                any(self._normalize_entity(a) == norm_entity for a in f.entity_aliases)
            ]
        
        if metric:
            norm_metric = self._normalize_metric(metric)
            results = [
                f for f in results
                if self._normalize_metric(f.metric) == norm_metric or
                any(self._normalize_metric(a) == norm_metric for a in f.aliases)
            ]
        
        if period:
            norm_period = self._normalize_period(period)
            results = [
                f for f in results
                if self._period_matches(norm_period, self._normalize_period(f.period))
            ]
        
        return results
    
    def add_fact(self, fact: CanonicalFact) -> bool:
        """
        Add a new fact to the store.
        
        Args:
            fact: Fact to add
            
        Returns:
            True if added, False if duplicate
        """
        # Check for duplicate
        existing = self.lookup(fact.metric, fact.period, fact.entity)
        if existing:
            if existing.authority_rank <= fact.authority_rank:
                logger.info(f"Fact already exists with equal or higher authority")
                return False
        
        self.facts.append(fact)
        self._build_indices()  # Rebuild indices
        return True
    
    def save(self):
        """Save facts back to file."""
        with open(self.store_path, "w", encoding="utf-8") as f:
            # Write header
            header = {"type": "header", "version": "1.0", "count": len(self.facts)}
            f.write(json.dumps(header) + "\n")
            
            # Write facts
            for fact in self.facts:
                f.write(json.dumps(fact.model_dump()) + "\n")
        
        logger.info(f"Saved {len(self.facts)} facts to {self.store_path}")
    
    def get_all_facts(self) -> List[CanonicalFact]:
        """Get all facts."""
        return self.facts
    
    def get_entities(self) -> Set[str]:
        """Get all unique entities."""
        return {f.entity for f in self.facts}
    
    def get_metrics(self) -> Set[str]:
        """Get all unique metrics."""
        return {f.metric for f in self.facts}
    
    def _normalize_entity(self, entity: str) -> str:
        """Normalize entity name for matching."""
        return entity.lower().strip()
    
    def _normalize_metric(self, metric: str) -> str:
        """Normalize metric name for matching."""
        return metric.lower().strip().replace("_", " ").replace("-", " ")
    
    def _normalize_period(self, period: str) -> str:
        """Normalize period for matching."""
        period = period.strip().upper()
        
        for pattern, replacement in self.PERIOD_PATTERNS:
            match = re.match(pattern, period, re.IGNORECASE)
            if match:
                return re.sub(pattern, replacement, period, flags=re.IGNORECASE).upper()
        
        return period
    
    def _period_matches(self, query_period: str, fact_period: str) -> bool:
        """Check if periods match (with fuzzy matching)."""
        if query_period == fact_period:
            return True
        
        # Strip whitespace and compare
        q = query_period.replace(" ", "")
        f = fact_period.replace(" ", "")
        
        if q == f:
            return True
        
        # Check if one contains the other
        if q in f or f in q:
            return True
        
        return False
