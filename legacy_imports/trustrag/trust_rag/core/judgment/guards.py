"""
Pre-Judgment Gates - Early refusal mechanisms.
Filters out-of-scope or malformed requests before processing.
"""
import re
import logging
from typing import List, Set
from pydantic import BaseModel

from trust_rag.config import get_config

logger = logging.getLogger(__name__)


class PreJudgmentVerdict(BaseModel):
    """Result of pre-judgment gate check."""
    status: str  # ALLOW, REFUSE
    reason: str
    category: str = ""  # out_of_scope, malformed, blocked_topic


class PreJudgmentGate:
    """
    Pre-query filtering for out-of-scope or malformed requests.
    Runs before any retrieval or LLM calls to save resources.
    """
    
    # Financial domain indicators
    FINANCIAL_INDICATORS = [
        # English
        r'revenue', r'profit', r'income', r'margin', r'earnings', r'sales',
        r'eps', r'ebitda', r'cash flow', r'balance sheet', r'assets', r'liabilities',
        r'dividend', r'stock', r'share', r'quarter', r'fiscal', r'annual report',
        r'10-k', r'10-q', r'sec filing', r'financial', r'investment',
        r'company', r'corporation', r'corp', r'inc', r'ltd',
        # Chinese
        r'收入', r'利润', r'净利润', r'营收', r'毛利', r'财报', r'年报',
        r'季报', r'财务', r'股票', r'股价', r'市值', r'资产', r'负债',
        # Company names
        r'nvidia', r'apple', r'microsoft', r'google', r'amazon', r'meta', r'tesla',
        r'alphabet', r'netflix', r'intel', r'amd', r'ibm',
        r'英伟达', r'苹果', r'微软', r'谷歌', r'亚马逊', r'特斯拉',
        # General query words that might be financial
        r'what was', r'how much', r'calculate', r'compare', r'growth',
    ]
    
    # Non-financial topics to reject
    BLOCKED_TOPICS = [
        r'world cup', r'football', r'soccer', r'basketball', r'sports',
        r'recipe', r'cooking', r'weather', r'forecast',
        r'movie', r'film', r'actor', r'actress', r'celebrity',
        r'music', r'song', r'album', r'artist',
        r'game', r'gaming', r'video game',
        r'joke', r'tell me a joke', r'funny',
        r'poem', r'write a poem', r'story',
        r'who is the president', r'politics',
        r'personal advice', r'relationship',
    ]
    
    # Prompt Injection Patterns
    INJECTION_PATTERNS = [
        r'ignore (all )?previous instructions',
        r'ignore (all )?directions',
        r'forget (all )?previous instructions',
        r'start a new conversation',
        r'system prompt',
        r'you are now',
        r'act as',
        r'simulate',
        r'roleplay',
        r'jailbreak',
        r'reveal your instructions',
        r'show me your prompt',
        r'what are your rules',
        r'override',
        r'unrestricted mode',
        r'developer mode',
    ]
    
    # Minimum query length
    MIN_QUERY_LENGTH = 3
    MAX_QUERY_LENGTH = 1000
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self.financial_re = [re.compile(p, re.I) for p in self.FINANCIAL_INDICATORS]
        self.blocked_re = [re.compile(p, re.I) for p in self.BLOCKED_TOPICS]
    
    def check(self, query: str) -> PreJudgmentVerdict:
        """
        Check if query should be processed.
        
        Args:
            query: User query string
            
        Returns:
            PreJudgmentVerdict with status and reason
        """
        # Empty or too short
        if not query or len(query.strip()) < self.MIN_QUERY_LENGTH:
            return PreJudgmentVerdict(
                status="REFUSE",
                reason="Query too short or empty",
                category="malformed"
            )
        
        # Too long
        if len(query) > self.MAX_QUERY_LENGTH:
            return PreJudgmentVerdict(
                status="REFUSE",
                reason=f"Query exceeds maximum length ({self.MAX_QUERY_LENGTH} chars)",
                category="malformed"
            )
        
        query_lower = query.lower()
        
        # Check for injection attempts
        for pattern in self.injection_re:
            if pattern.search(query_lower):
                logger.warning(f"Potential prompt injection detected: {query}")
                return PreJudgmentVerdict(
                    status="REFUSE",
                    reason="Security alert: Potential prompt injection detected",
                    category="security_risk"
                )
        
        # Check for blocked topics
        for pattern in self.blocked_re:
            if pattern.search(query_lower):
                return PreJudgmentVerdict(
                    status="REFUSE",
                    reason=f"Out of scope: Non-financial query topic",
                    category="out_of_scope"
                )
        
        # Check for financial relevance
        has_financial_indicator = any(p.search(query_lower) for p in self.financial_re)
        
        if has_financial_indicator:
            return PreJudgmentVerdict(
                status="ALLOW",
                reason="Query is in scope (financial domain)",
                category="financial"
            )
        
        # Check if it looks like a question
        is_question = any(q in query_lower for q in ['what', 'how', 'when', 'where', 'which', 'why', '?'])
        
        if is_question:
            # Allow questions that might be financial
            return PreJudgmentVerdict(
                status="ALLOW",
                reason="Query appears to be a valid question",
                category="general_question"
            )
        
        # Default: allow but log for review
        logger.debug(f"Query allowed by default: {query[:50]}...")
        return PreJudgmentVerdict(
            status="ALLOW",
            reason="Query allowed for processing",
            category="default"
        )
    
    def is_financial_query(self, query: str) -> bool:
        """Check if query is clearly financial."""
        query_lower = query.lower()
        return any(p.search(query_lower) for p in self.financial_re)
    
    def get_blocked_reason(self, query: str) -> str:
        """Get specific reason why query would be blocked."""
        query_lower = query.lower()
        
        for pattern in self.blocked_re:
            match = pattern.search(query_lower)
            if match:
                return f"Query contains blocked topic: '{match.group()}'"
        
        return ""


class RateLimitGate:
    """
    Rate limiting gate for API protection.
    Tracks request counts per client.
    """
    
    def __init__(self, max_requests_per_minute: int = 60):
        self.max_rpm = max_requests_per_minute
        self._request_counts: dict = {}
    
    def check(self, client_id: str) -> PreJudgmentVerdict:
        """Check if client has exceeded rate limit."""
        import time
        
        current_minute = int(time.time() / 60)
        key = f"{client_id}:{current_minute}"
        
        count = self._request_counts.get(key, 0)
        
        if count >= self.max_rpm:
            return PreJudgmentVerdict(
                status="REFUSE",
                reason=f"Rate limit exceeded ({self.max_rpm} requests/minute)",
                category="rate_limit"
            )
        
        # Increment count
        self._request_counts[key] = count + 1
        
        # Clean old entries
        self._cleanup_old_entries(current_minute)
        
        return PreJudgmentVerdict(status="ALLOW", reason="Within rate limit")
    
    def _cleanup_old_entries(self, current_minute: int):
        """Remove entries older than 2 minutes."""
        old_keys = [
            k for k in self._request_counts 
            if int(k.split(':')[1]) < current_minute - 1
        ]
        for k in old_keys:
            del self._request_counts[k]
