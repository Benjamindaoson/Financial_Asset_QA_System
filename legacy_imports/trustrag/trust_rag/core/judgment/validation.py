"""
Post-Binding Verification - Grounding checks after answer generation.
Ensures all claims in answers are supported by evidence.
"""
import re
import logging
from typing import Any, List, Dict, Optional, Set
from pydantic import BaseModel, Field

from trust_rag.config import get_config

logger = logging.getLogger(__name__)


class VerificationIssue(BaseModel):
    """A single verification issue found."""
    issue_type: str  # ungrounded_number, missing_source, hallucination_risk
    description: str
    severity: str  # low, medium, high
    evidence: str = ""  # Supporting details


class VerificationResult(BaseModel):
    """Result of post-binding verification."""
    passed: bool = True
    issues: List[VerificationIssue] = Field(default_factory=list)
    confidence_adjustment: float = 0.0  # How much to adjust confidence
    requires_disclosure: bool = False
    verification_notes: List[str] = Field(default_factory=list)
    
    def add_issue(self, issue: VerificationIssue):
        """Add an issue and update passed status."""
        self.issues.append(issue)
        if issue.severity == "high":
            self.passed = False
        elif issue.severity == "medium" and len([i for i in self.issues if i.severity == "medium"]) >= 2:
            self.passed = False


class PostBindingVerifier:
    """
    Verifies that generated answer is grounded in provided evidence.
    
    Checks:
    1. All numbers in answer appear in evidence
    2. Entity/metric alignment
    3. No hallucinated claims
    4. Temporal consistency
    """
    
    def __init__(self):
        config = get_config()
        self.patterns = config.patterns
    
    def verify(
        self,
        answer: str,
        bindings: Dict[str, Any],
        query: str = ""
    ) -> VerificationResult:
        """
        Verify that answer is grounded in evidence.
        
        Args:
            answer: Generated answer text
            bindings: Dict containing core_evidence and supporting_evidence
            query: Original query (for context)
            
        Returns:
            VerificationResult with passed status and any issues
        """
        result = VerificationResult()
        
        if not answer or not answer.strip():
            result.add_issue(VerificationIssue(
                issue_type="empty_answer",
                description="Answer is empty",
                severity="high"
            ))
            return result
        
        core_evidence = bindings.get("core_evidence", [])
        
        if not core_evidence:
            result.add_issue(VerificationIssue(
                issue_type="no_evidence",
                description="No evidence provided for verification",
                severity="high"
            ))
            return result
        
        # Extract text from all evidence
        evidence_texts = self._collect_evidence_texts(core_evidence)
        evidence_combined = " ".join(evidence_texts)
        
        # Run verification checks
        self._check_numeric_grounding(answer, evidence_combined, result)
        self._check_entity_alignment(answer, query, evidence_combined, result)
        self._check_temporal_consistency(answer, evidence_combined, result)
        self._check_claim_support(answer, evidence_combined, result)
        
        # Calculate confidence adjustment
        if result.issues:
            high_count = sum(1 for i in result.issues if i.severity == "high")
            medium_count = sum(1 for i in result.issues if i.severity == "medium")
            result.confidence_adjustment = -(high_count * 0.3 + medium_count * 0.1)
        
        if result.passed:
            result.verification_notes.append("All claims verified against evidence")
        
        logger.info(f"Verification: passed={result.passed}, issues={len(result.issues)}")
        
        return result
    
    def _collect_evidence_texts(self, evidence_list: List[Any]) -> List[str]:
        """Extract text from all evidence items."""
        texts = []
        
        for ev in evidence_list:
            if hasattr(ev, 'text'):
                texts.append(ev.text)
            elif isinstance(ev, dict) and 'text' in ev:
                texts.append(ev['text'])
            elif isinstance(ev, str):
                texts.append(ev)
        
        return texts
    
    def _check_numeric_grounding(
        self,
        answer: str,
        evidence: str,
        result: VerificationResult
    ):
        """Verify all numbers in answer appear in evidence."""
        # Extract numbers from answer
        answer_numbers = self._extract_numbers(answer)
        evidence_numbers = self._extract_numbers(evidence)
        
        if not answer_numbers:
            return  # No numbers to verify
        
        # Check each number
        ungrounded = []
        for num in answer_numbers:
            if not self._number_in_evidence(num, evidence_numbers, evidence):
                ungrounded.append(num)
        
        if ungrounded:
            result.add_issue(VerificationIssue(
                issue_type="ungrounded_number",
                description=f"Numbers not found in evidence: {', '.join(ungrounded[:3])}",
                severity="high",
                evidence=f"Answer numbers: {answer_numbers[:5]}, Evidence numbers: {list(evidence_numbers)[:10]}"
            ))
    
    def _extract_numbers(self, text: str) -> List[str]:
        """Extract significant numbers from text."""
        # Match numbers with optional decimals, currency, percentages
        pattern = r'[\$€£¥]?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s*(?:billion|million|B|M|%|万|亿))?'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        # Normalize and filter
        numbers = []
        for m in matches:
            # Remove currency symbols and commas for comparison
            normalized = re.sub(r'[\$€£¥,]', '', m).strip()
            if normalized and len(normalized) > 0:
                # Skip single digits (too common)
                core_num = re.search(r'\d+\.?\d*', normalized)
                if core_num and len(core_num.group()) > 1:
                    numbers.append(normalized)
        
        return numbers
    
    def _number_in_evidence(
        self,
        number: str,
        evidence_numbers: List[str],
        evidence_text: str
    ) -> bool:
        """Check if a number appears in evidence (with normalization)."""
        # Extract just the numeric part
        core_match = re.search(r'(\d+\.?\d*)', number)
        if not core_match:
            return True  # Can't parse, skip
        
        core_num = core_match.group(1)
        
        # Direct match in evidence numbers
        for ev_num in evidence_numbers:
            if core_num in ev_num:
                return True
        
        # Check in full text (handles different formatting)
        if core_num in evidence_text:
            return True
        
        # Check with commas removed
        evidence_clean = evidence_text.replace(',', '')
        if core_num in evidence_clean:
            return True
        
        return False
    
    def _check_entity_alignment(
        self,
        answer: str,
        query: str,
        evidence: str,
        result: VerificationResult
    ):
        """Verify entities in answer match query and evidence."""
        # Extract entity from query
        query_entities = self._extract_entities(query)
        answer_entities = self._extract_entities(answer)
        evidence_entities = self._extract_entities(evidence)
        
        # Check if answer mentions entities not in query or evidence
        for entity in answer_entities:
            if entity not in query_entities and entity not in evidence_entities:
                result.add_issue(VerificationIssue(
                    issue_type="entity_mismatch",
                    description=f"Entity '{entity}' in answer not found in query or evidence",
                    severity="medium"
                ))
                break
    
    def _extract_entities(self, text: str) -> Set[str]:
        """Extract potential entity names from text."""
        entities = set()
        
        # Common company names
        companies = [
            'nvidia', 'apple', 'microsoft', 'google', 'alphabet', 'amazon',
            'meta', 'tesla', 'netflix', 'ibm', 'intel', 'amd'
        ]
        
        text_lower = text.lower()
        for company in companies:
            if company in text_lower:
                entities.add(company)
        
        # Capitalized words (potential proper nouns)
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        for word in words:
            if len(word) > 2 and word.lower() not in ['the', 'for', 'and', 'based', 'source']:
                entities.add(word.lower())
        
        return entities
    
    def _check_temporal_consistency(
        self,
        answer: str,
        evidence: str,
        result: VerificationResult
    ):
        """Verify time periods in answer match evidence."""
        # Extract periods from answer
        answer_periods = self._extract_periods(answer)
        evidence_periods = self._extract_periods(evidence)
        
        if not answer_periods:
            return  # No periods to verify
        
        for period in answer_periods:
            if period not in evidence_periods:
                # Check for equivalent representations
                if not self._period_equivalent(period, evidence_periods):
                    result.add_issue(VerificationIssue(
                        issue_type="temporal_mismatch",
                        description=f"Time period '{period}' in answer not found in evidence",
                        severity="medium"
                    ))
                    break
    
    def _extract_periods(self, text: str) -> Set[str]:
        """Extract time period references from text."""
        periods = set()
        
        # Fiscal year patterns
        fy_matches = re.findall(r'FY\s*\d{4}', text, re.IGNORECASE)
        for m in fy_matches:
            periods.add(m.upper().replace(' ', ''))
        
        # Quarter patterns
        q_matches = re.findall(r'Q[1-4]\s*\d{4}', text, re.IGNORECASE)
        for m in q_matches:
            periods.add(m.upper().replace(' ', ''))
        
        # Year only
        year_matches = re.findall(r'\b(20\d{2})\b', text)
        for m in year_matches:
            periods.add(m)
        
        return periods
    
    def _period_equivalent(self, period: str, evidence_periods: Set[str]) -> bool:
        """Check if period has equivalent in evidence."""
        period_upper = period.upper().replace(' ', '')
        
        for ev_period in evidence_periods:
            ev_upper = ev_period.upper().replace(' ', '')
            
            # Direct match
            if period_upper == ev_upper:
                return True
            
            # FY2023 == 2023
            if period_upper.replace('FY', '') in ev_upper or ev_upper.replace('FY', '') in period_upper:
                return True
        
        return False
    
    def _check_claim_support(
        self,
        answer: str,
        evidence: str,
        result: VerificationResult
    ):
        """Check for potentially unsupported claims."""
        # Dangerous patterns that might indicate hallucination
        risky_patterns = [
            r'I think',
            r'probably',
            r'might be',
            r'approximately',  # Could be valid, but flag for review
            r'in my opinion',
            r'based on my knowledge',
            r'generally speaking',
        ]
        
        for pattern in risky_patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                result.add_issue(VerificationIssue(
                    issue_type="uncertain_language",
                    description=f"Answer contains uncertain language: '{pattern}'",
                    severity="low"
                ))
                result.requires_disclosure = True
                break
        
        # Check for claims not in evidence (simplified check)
        # Flag if answer is significantly longer than any evidence snippet
        answer_words = len(answer.split())
        evidence_words = len(evidence.split())
        
        if answer_words > evidence_words * 0.5 and answer_words > 50:
            result.verification_notes.append(
                "Answer length may indicate content beyond evidence"
            )


class VerificationGate:
    """
    Gate that enforces verification before final output.
    Used in process_query to block unverified answers.
    """
    
    def __init__(self, verifier: PostBindingVerifier = None):
        self.verifier = verifier or PostBindingVerifier()
    
    def check(
        self,
        answer: str,
        bindings: Dict[str, Any],
        query: str = "",
        original_confidence: float = 1.0
    ) -> tuple:
        """
        Run verification and return (should_proceed, adjusted_confidence, refusal_reason).
        
        Returns:
            Tuple of (proceed: bool, confidence: float, reason: Optional[str])
        """
        result = self.verifier.verify(answer, bindings, query)
        
        if not result.passed:
            # Collect reasons
            reasons = [issue.description for issue in result.issues if issue.severity == "high"]
            reason = "; ".join(reasons) if reasons else "Verification failed"
            return (False, 0.0, reason)
        
        # Adjust confidence
        adjusted = max(0.0, min(1.0, original_confidence + result.confidence_adjustment))
        
        return (True, adjusted, None)
