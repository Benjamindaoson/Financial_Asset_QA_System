"""
Quote Verifier for TrustRAG.
Validates that generated citations actually exist in the evidence.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QuoteValidationResult:
    """Result of quote validation."""
    is_valid: bool
    found_quotes: List[str]
    missing_quotes: List[str]
    validation_details: Dict[str, Any]
    confidence_score: float


@dataclass
class CitationReference:
    """A citation reference in generated text."""
    text: str
    doc_id: Optional[str] = None
    page: Optional[int] = None
    chunk_id: Optional[str] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None


class QuoteVerifier:
    """
    Validates that citations in generated answers actually exist in evidence.
    Implements fail-closed verification for production safety.
    """

    def __init__(self):
        # Citation patterns to detect in text
        self.citation_patterns = [
            # [doc_id] or [doc_id, page]
            r'\[([^\]]+)\]',
            # (Source: doc_id) or (Page X)
            r'\(Source:\s*([^)]+)\)',
            r'\(Page\s*(\d+)\)',
            # References like "According to [1]" or "See page X"
            r'See\s+page\s+(\d+)',
            r'According\s+to\s+\[([^\]]+)\]',
        ]

    def verify_quotes(
        self,
        answer_text: str,
        evidence_list: List[Dict[str, Any]],
        strict_mode: bool = True
    ) -> QuoteValidationResult:
        """
        Verify that all citations in the answer exist in the evidence.

        Args:
            answer_text: Generated answer text
            evidence_list: List of evidence chunks with metadata
            strict_mode: If True, any missing citation causes failure

        Returns:
            Validation result
        """
        # Extract citations from answer
        citations = self._extract_citations(answer_text)

        if not citations:
            if strict_mode:
                return QuoteValidationResult(
                    is_valid=False,
                    found_quotes=[],
                    missing_quotes=["NO_CITATIONS"],
                    validation_details={"no_citations": True},
                    confidence_score=0.0
                )
            return QuoteValidationResult(
                is_valid=True,
                found_quotes=[],
                missing_quotes=[],
                validation_details={"no_citations": True},
                confidence_score=1.0
            )

        # Build evidence index for fast lookup
        evidence_index = self._build_evidence_index(evidence_list)

        # Verify each citation
        found_quotes = []
        missing_quotes = []
        validation_details = {
            "total_citations": len(citations),
            "evidence_sources": len(evidence_list),
            "citation_matches": []
        }

        for citation in citations:
            match_found, match_details = self._verify_citation(citation, evidence_index)

            if match_found:
                found_quotes.append(citation.text)
                validation_details["citation_matches"].append({
                    "citation": citation.text,
                    "matched_evidence": match_details
                })
            else:
                missing_quotes.append(citation.text)
                validation_details["citation_matches"].append({
                    "citation": citation.text,
                    "matched_evidence": None,
                    "failure_reason": match_details
                })

        # Determine overall validity
        if strict_mode:
            is_valid = len(missing_quotes) == 0
        else:
            # Allow some missing citations if most are found
            valid_ratio = len(found_quotes) / len(citations) if citations else 1.0
            is_valid = valid_ratio >= 0.8  # 80% success rate

        # Calculate confidence score
        if not citations:
            confidence_score = 1.0
        else:
            confidence_score = len(found_quotes) / len(citations)

        return QuoteValidationResult(
            is_valid=is_valid,
            found_quotes=found_quotes,
            missing_quotes=missing_quotes,
            validation_details=validation_details,
            confidence_score=confidence_score
        )

    def _extract_citations(self, text: str) -> List[CitationReference]:
        """Extract citation references from text."""
        citations = []

        for pattern in self.citation_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                citation_text = match.group(0)

                # Try to parse the citation content
                citation = CitationReference(text=citation_text)

                # Parse content inside brackets/braces
                content_match = re.search(r'[\[\(]([^)\]]+)[\]\)]', citation_text)
                if content_match:
                    content = content_match.group(1).strip()
                    
                    # Try to extract doc_id and page
                    # Remove common prefixes
                    content = re.sub(r'^(Source|Page|Ref|Doc)[:\s]+', '', content, flags=re.IGNORECASE)
                    
                    parts = [p.strip() for p in content.split(',')]
                    if len(parts) >= 1:
                        citation.doc_id = parts[0]
                    if len(parts) >= 2 and parts[1].isdigit():
                        citation.page = int(parts[1])

                citations.append(citation)

        # Remove duplicates
        unique_citations = []
        seen_texts = set()
        for citation in citations:
            if citation.text not in seen_texts:
                unique_citations.append(citation)
                seen_texts.add(citation.text)

        return unique_citations

    def _build_evidence_index(self, evidence_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Build an index of evidence for fast citation lookup."""
        index = {}

        for evidence in evidence_list:
            # Index by doc_id
            doc_id = evidence.get('doc_id')
            if doc_id:
                if doc_id not in index:
                    index[doc_id] = []
                index[doc_id].append(evidence)

            # Index by evidence_id
            evidence_id = evidence.get('evidence_id')
            if evidence_id:
                index[evidence_id] = [evidence]

            # Index by page number
            page = evidence.get('page_number')
            if page:
                page_key = f"page_{page}"
                if page_key not in index:
                    index[page_key] = []
                index[page_key].append(evidence)

        return index

    def _verify_citation(
        self,
        citation: CitationReference,
        evidence_index: Dict[str, List[Dict[str, Any]]]
    ) -> Tuple[bool, str]:
        """
        Verify a single citation against the evidence index.

        Returns:
            (is_valid, details_or_failure_reason)
        """
        # Check by doc_id
        if citation.doc_id and citation.doc_id in evidence_index:
            evidence_items = evidence_index[citation.doc_id]
            if citation.page:
                # Check if any evidence from this doc has the specified page
                for evidence in evidence_items:
                    if evidence.get('page_number') == citation.page:
                        return True, f"Found evidence for doc {citation.doc_id}, page {citation.page}"
                return False, f"Doc {citation.doc_id} exists but page {citation.page} not found"
            else:
                return True, f"Found evidence for doc {citation.doc_id}"

        # Check by page number only
        if citation.page and not citation.doc_id:
            page_key = f"page_{citation.page}"
            if page_key in evidence_index:
                return True, f"Found evidence for page {citation.page}"

        # Check if citation text appears in any evidence content
        citation_lower = citation.text.lower()
        for evidence_list in evidence_index.values():
            for evidence in evidence_list:
                evidence_text = evidence.get('text', '').lower()
                if citation_lower in evidence_text:
                    return True, f"Citation text found in evidence {evidence.get('evidence_id')}"

        # If we get here, citation was not found
        if citation.doc_id:
            return False, f"No evidence found for doc_id: {citation.doc_id}"
        elif citation.page:
            return False, f"No evidence found for page: {citation.page}"
        else:
            return False, f"Citation '{citation.text}' not found in any evidence"

    def validate_answer_structure(
        self,
        answer_text: str,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate the overall structure of the answer for citation consistency.
        """
        result = {
            "has_citations": False,
            "citation_count": 0,
            "evidence_coverage": 0.0,
            "structural_issues": []
        }

        citations = self._extract_citations(answer_text)
        result["citation_count"] = len(citations)
        result["has_citations"] = len(citations) > 0

        if citations:
            # Calculate how many evidence items are actually cited
            cited_evidence_ids = set()
            for citation in citations:
                if citation.doc_id:
                    # Find evidence that matches this citation
                    for evidence in evidence_list:
                        if evidence.get('doc_id') == citation.doc_id:
                            cited_evidence_ids.add(evidence.get('evidence_id'))

            result["evidence_coverage"] = len(cited_evidence_ids) / len(evidence_list) if evidence_list else 0.0

            # Check for structural issues
            if result["evidence_coverage"] < 0.5:
                result["structural_issues"].append("Low evidence coverage - most evidence not cited")

            if len(citations) > len(evidence_list) * 2:
                result["structural_issues"].append("Too many citations relative to evidence")

        return result
