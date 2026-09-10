"""
Answer Generation - Evidence-Based Template Rendering.
All answers are automatically rendered from core evidence.
No hardcoded if-else branches for specific queries.
"""
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from trust_rag.config import get_config
from .quote_verifier import QuoteVerifier

logger = logging.getLogger(__name__)

@dataclass
class ExtractedValue:
    """A value extracted from evidence text."""
    raw_value: str
    normalized_value: str
    unit: str
    context: str  # Surrounding text snippet
    confidence: float

@dataclass
class EvidenceExtraction:
    """Extraction result from a single evidence item."""
    evidence_id: str
    source: str
    page: Optional[int]
    values: List[ExtractedValue]
    text_snippet: str
    modality: str

@dataclass
class GenerationPrompt:
    """Final prompt ready for LLM (if needed)."""
    system_prompt: str
    user_prompt: str
    metadata: Dict[str, Any]


class ValueExtractor:
    """
    Extracts numeric values and facts from evidence text.
    Rule-based, no LLM dependency.
    """
    
    def __init__(self):
        config = get_config()
        self.patterns = config.patterns.value_extraction_patterns
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile extraction patterns."""
        self.compiled_patterns = []
        
        # Currency and large numbers
        self.compiled_patterns.append(
            (re.compile(r'(\$?[\d,]+\.?\d*)\s*(billion|million|trillion|B|M|T)', re.I), 'currency')
        )
        
        # Percentages
        self.compiled_patterns.append(
            (re.compile(r'(\d+\.?\d*)\s*[%％]', re.I), 'percentage')
        )
        
        # Revenue/profit/margin with values
        self.compiled_patterns.append(
            (re.compile(r'(revenue|profit|income|margin|sales|earnings)[:\s]+(\$?[\d,]+\.?\d*)\s*(billion|million|B|M)?', re.I), 'metric')
        )
        
        # Year patterns
        self.compiled_patterns.append(
            (re.compile(r'(FY|fiscal year|Q[1-4])\s*(\d{4})', re.I), 'period')
        )
        
        # Chinese currency
        self.compiled_patterns.append(
            (re.compile(r'([\d,]+\.?\d*)\s*(万|亿|元|人民币)', re.I), 'currency_zh')
        )
        
        # Generic numbers with units
        self.compiled_patterns.append(
            (re.compile(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(USD|CNY|RMB|EUR|GBP)?', re.I), 'number')
        )
    
    def extract_values(self, text: str) -> List[ExtractedValue]:
        """Extract all values from text."""
        values = []
        seen = set()  # Avoid duplicates
        
        for pattern, value_type in self.compiled_patterns:
            for match in pattern.finditer(text):
                raw = match.group(0)
                
                if raw in seen:
                    continue
                seen.add(raw)
                
                # Get context (surrounding words)
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                
                # Parse components
                groups = match.groups()
                if len(groups) >= 2:
                    main_value = groups[0]
                    unit = groups[1] if len(groups) > 1 and groups[1] else ""
                else:
                    main_value = groups[0] if groups else raw
                    unit = ""
                
                # Normalize
                normalized = self._normalize_value(main_value, unit)
                
                values.append(ExtractedValue(
                    raw_value=raw,
                    normalized_value=normalized,
                    unit=unit,
                    context=context,
                    confidence=0.8 if value_type in ['currency', 'metric'] else 0.6
                ))
        
        # Sort by confidence
        values.sort(key=lambda v: v.confidence, reverse=True)
        
        return values
    
    def _normalize_value(self, value: str, unit: str) -> str:
        """Normalize value representation."""
        # Remove commas for numbers
        clean_value = value.replace(',', '').replace('$', '')
        
        # Unit normalization
        unit_map = {
            'billion': 'B', 'million': 'M', 'trillion': 'T',
            '亿': 'B CNY', '万': '0K CNY',
            'b': 'B', 'm': 'M', 't': 'T'
        }
        
        norm_unit = unit_map.get(unit.lower(), unit) if unit else ""
        
        return f"{clean_value} {norm_unit}".strip()


class AnswerPromptGenerator:
    """
    Generates evidence-based answers through template rendering.
    
    Key principles:
    1. All answers derived from core_evidence
    2. No hardcoded query-specific branches
    3. Traceable to source documents
    4. Conclusion-first format
    """
    
    SYSTEM_PROMPT = """You are an evidence-centric professional answer generator for financial Q&A.

**Core Principles:**
1. Answer only based on given context, no speculation
2. Conclusion-first: Give the answer directly
3. Professional, restrained tone
4. Do not explain internal system mechanisms

**Output Structure:**
Answer: <Provide conclusive answer directly>
"""
    
    def __init__(self):
        self.extractor = ValueExtractor()
        self.quote_verifier = QuoteVerifier()
        config = get_config()
        self.max_snippet_length = config.answer.max_snippet_length
        self.max_values = config.answer.max_extracted_values
    
    def generate_answer(self, query: str, bindings: Dict[str, Any]) -> str:
        """
        Generate answer from evidence bindings with quote verification.

        Args:
            query: Original user query
            bindings: Dict containing core_evidence and supporting_evidence

        Returns:
            Rendered answer string with verified citations
        """
        core_evidence = bindings.get("core_evidence", [])

        if not core_evidence:
            logger.warning("No core evidence for answer generation")
            return "Unable to provide an answer: no supporting evidence found in the document corpus."

        # Extract information from all core evidence
        extractions = self._extract_from_evidence(core_evidence)

        if not extractions:
            # No values extracted, return text snippet
            answer = self._render_snippet_answer(query, core_evidence)
        else:
            # Determine answer type based on query
            answer_type = self._classify_query(query)

            # Render appropriate answer format
            if answer_type == "numeric":
                answer = self._render_numeric_answer(query, extractions)
            elif answer_type == "comparison":
                answer = self._render_comparison_answer(query, extractions)
            else:
                answer = self._render_general_answer(query, extractions)

        # Verify quotes and citations
        verification_result = self._verify_answer_citations(answer, core_evidence)

        if not verification_result.is_valid:
            logger.warning(f"Quote verification failed: {verification_result.missing_quotes}")
            return "Unable to provide a verified answer: citation validation failed."

        return answer
    
    def _extract_from_evidence(self, evidence_list: List[Any]) -> List[EvidenceExtraction]:
        """Extract values from all evidence items."""
        extractions = []
        
        for ev in evidence_list:
            # Get text
            text = self._get_text(ev)
            if not text:
                continue
            
            # Extract values
            values = self.extractor.extract_values(text)
            
            # Get metadata
            source = self._get_source(ev)
            page = self._get_page(ev)
            evidence_id = self._get_evidence_id(ev)
            modality = self._get_modality(ev)
            
            # Create snippet
            snippet = text[:self.max_snippet_length]
            if len(text) > self.max_snippet_length:
                snippet += "..."
            
            extractions.append(EvidenceExtraction(
                evidence_id=evidence_id,
                source=source,
                page=page,
                values=values[:self.max_values],
                text_snippet=snippet,
                modality=modality
            ))
        
        return extractions
    
    def _classify_query(self, query: str) -> str:
        """Classify query type for appropriate rendering."""
        query_lower = query.lower()
        
        # Numeric indicators
        numeric_indicators = [
            'how much', 'what was', 'what is the', 'revenue', 'profit',
            'income', 'margin', 'rate', 'percentage', 'amount', 'value',
            '多少', '收入', '利润', '比例'
        ]
        
        # Comparison indicators
        comparison_indicators = [
            'compare', 'vs', 'versus', 'difference', 'between',
            'growth', 'change', 'increase', 'decrease',
            '比较', '对比', '变化', '增长'
        ]
        
        for indicator in comparison_indicators:
            if indicator in query_lower:
                return "comparison"
        
        for indicator in numeric_indicators:
            if indicator in query_lower:
                return "numeric"
        
        return "general"
    
    def _render_numeric_answer(self, query: str, extractions: List[EvidenceExtraction]) -> str:
        """Render answer for numeric queries."""
        primary = extractions[0]
        
        if not primary.values:
            return self._render_snippet_answer(query, [primary])
        
        # Get the best value
        best_value = primary.values[0]
        
        # Identify what we're reporting
        metric = self._identify_metric(query)
        entity = self._identify_entity(query, primary)
        
        # Build answer
        parts = []
        
        if entity:
            parts.append(entity)
        if metric:
            parts.append(metric)
        
        value_str = best_value.raw_value
        
        # Source citation
        source_str = f" (Source: {primary.source}"
        if primary.page:
            source_str += f", Page {primary.page}"
        source_str += ")"
        
        if parts:
            subject = " ".join(parts)
            return f"Based on verified evidence, {subject} was {value_str}.{source_str}"
        else:
            return f"Based on verified evidence: {value_str}.{source_str}"
    
    def _render_comparison_answer(self, query: str, extractions: List[EvidenceExtraction]) -> str:
        """Render answer for comparison queries."""
        if len(extractions) < 2:
            # Not enough data for comparison
            return self._render_general_answer(query, extractions)
        
        parts = []
        for i, ext in enumerate(extractions[:2]):
            if ext.values:
                val = ext.values[0]
                parts.append(f"{ext.source}: {val.raw_value}")
        
        if len(parts) >= 2:
            return f"Comparison based on verified evidence:\n• {parts[0]}\n• {parts[1]}"
        else:
            return self._render_general_answer(query, extractions)
    
    def _render_general_answer(self, query: str, extractions: List[EvidenceExtraction]) -> str:
        """Render answer for general queries."""
        primary = extractions[0]
        
        # Combine key values
        value_parts = []
        for val in primary.values[:2]:
            value_parts.append(val.raw_value)
        
        if value_parts:
            values_str = ", ".join(value_parts)
            answer = f"Based on {primary.source}: {values_str}."
        else:
            answer = f"Based on {primary.source}: {primary.text_snippet}"
        
        return answer
    
    def _render_snippet_answer(self, query: str, evidence: List[Any]) -> str:
        """Render answer from text snippet when no values extracted."""
        if not evidence:
            return "Unable to provide an answer based on available evidence."
        
        first = evidence[0]
        text = self._get_text(first)
        source = self._get_source(first)
        
        if not text:
            return "Unable to extract information from available evidence."
        
        snippet = text[:250].strip()
        if len(text) > 250:
            snippet += "..."
        
        return f"Based on {source}: \"{snippet}\""
    
    def _identify_metric(self, query: str) -> str:
        """Identify the metric being asked about."""
        query_lower = query.lower()
        
        metric_map = {
            'revenue': 'revenue',
            'net income': 'net income',
            'profit': 'profit',
            'margin': 'profit margin',
            'earnings': 'earnings',
            'sales': 'sales',
            'gross profit': 'gross profit',
            '收入': 'revenue',
            '利润': 'profit',
        }
        
        for keyword, metric in metric_map.items():
            if keyword in query_lower:
                return metric
        
        return ""
    
    def _identify_entity(self, query: str, extraction: EvidenceExtraction) -> str:
        """Identify the entity (company, etc.) being asked about."""
        query_lower = query.lower()
        
        # Common company names
        companies = ['nvidia', 'apple', 'microsoft', 'google', 'amazon', 'meta', 'tesla']
        
        for company in companies:
            if company in query_lower:
                return company.capitalize()
        
        # Try to get from source
        source = extraction.source.lower()
        for company in companies:
            if company in source:
                return company.capitalize()
        
        return ""
    
    # Helper methods to extract data from evidence objects
    
    def _get_text(self, evidence) -> str:
        """Get text from evidence object."""
        if hasattr(evidence, 'text'):
            return evidence.text
        if isinstance(evidence, dict):
            return evidence.get('text', '')
        return str(evidence)
    
    def _get_source(self, evidence) -> str:
        """Get source from evidence object."""
        default = "verified document"
        
        if hasattr(evidence, 'doc_id'):
            return evidence.doc_id
        if hasattr(evidence, 'metadata') and evidence.metadata:
            return evidence.metadata.get('source', evidence.metadata.get('doc_id', default))
        if isinstance(evidence, dict):
            return evidence.get('doc_id', evidence.get('source', default))
        return default
    
    def _get_page(self, evidence) -> Optional[int]:
        """Get page number from evidence object."""
        if hasattr(evidence, 'metadata') and evidence.metadata:
            page = evidence.metadata.get('page_number')
            if page is not None:
                return int(page)
        if isinstance(evidence, dict):
            page = evidence.get('page_number') or evidence.get('page')
            if page is not None:
                return int(page)
        return None
    
    def _get_evidence_id(self, evidence) -> str:
        """Get evidence ID from evidence object."""
        if hasattr(evidence, 'evidence_id'):
            return evidence.evidence_id
        if isinstance(evidence, dict):
            return evidence.get('evidence_id', '')
        return ''
    
    def _get_modality(self, evidence) -> str:
        """Get modality from evidence object."""
        if hasattr(evidence, 'metadata') and evidence.metadata:
            return evidence.metadata.get('modality', 'text_native')
        if isinstance(evidence, dict):
            return evidence.get('modality', 'text_native')
        return 'text_native'
    
    def build_llm_prompt(self, query: str, bindings: Dict[str, Any]) -> GenerationPrompt:
        """
        Build prompt for LLM-based answer generation (if needed).
        Currently not used - answers are template-rendered.
        """
        core_evidence = bindings.get("core_evidence", [])
        
        # Build context from evidence
        context_parts = []
        for ev in core_evidence[:3]:
            text = self._get_text(ev)
            source = self._get_source(ev)
            context_parts.append(f"[Source: {source}]\n{text[:500]}")
        
        context = "\n\n".join(context_parts)
        
        user_prompt = f"""Question: {query}

Evidence Context:
{context}

Please provide a concise, evidence-based answer."""
        
        return GenerationPrompt(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            metadata={
                "evidence_count": len(core_evidence),
                "query": query
            }
        )

    def _verify_answer_citations(self, answer_text: str, evidence_list: List[Any]) -> Any:
        """
        Verify that citations in the answer are valid.
        """
        # Convert evidence to dict format for verifier
        evidence_dicts = []
        for ev in evidence_list:
            evidence_dicts.append({
                'evidence_id': getattr(ev, 'evidence_id', ''),
                'doc_id': getattr(ev, 'doc_id', ''),
                'text': self._get_text(ev),
                'page_number': getattr(ev, 'page_number', None),
            })

        # Run verification
        result = self.quote_verifier.verify_quotes(answer_text, evidence_dicts, strict_mode=True)

        return result
