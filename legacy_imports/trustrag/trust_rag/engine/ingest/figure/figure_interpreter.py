"""
Figure Semantic Interpretation Module.
Extracts weak semantics from charts/graphs WITHOUT CV inference.
"""
import logging
import hashlib
import re
from typing import List, Dict, Literal, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class FigureArtifact(BaseModel):
    """Semantic artifact for a figure/chart."""
    figure_id: str
    figure_type: Literal["bar", "line", "pie", "scatter", "unknown"]
    axis_labels: Dict[str, str]  # {"x": "Year", "y": "Revenue"}
    legend_text: List[str]
    semantic_summary: str  # One-sentence description
    source_page: int
    evidence_ids: List[str]
    metadata: Dict = {}

class FigureInterpreter:
    """
    Interprets figures using OCR text + caption + simple heuristics.
    Uses single LLM call for semantic summary (deterministic prompt).
    """
    
    # Keywords for figure type detection
    FIGURE_TYPE_KEYWORDS = {
        "bar": ["bar chart", "bar graph", "column chart", "histogram"],
        "line": ["line chart", "line graph", "trend", "time series"],
        "pie": ["pie chart", "pie graph", "distribution"],
        "scatter": ["scatter plot", "scatter chart", "correlation"]
    }
    
    def __init__(self, llm_provider=None):
        """
        Args:
            llm_provider: Optional LLM provider for semantic summary.
                         If None, will use mock summary.
        """
        self.llm_provider = llm_provider
    
    def interpret_figures(self, blocks: List) -> List[FigureArtifact]:
        """
        Interpret figure blocks into semantic artifacts.
        
        Args:
            blocks: List of Block objects with block_type=FIGURE/IMAGE
        
        Returns:
            List of FigureArtifact objects
        """
        figure_artifacts = []
        
        for block in blocks:
            # Check if block is a figure
            block_type = getattr(block, 'block_type', None) or block.metadata.get('block_type', '')
            if 'figure' not in str(block_type).lower() and 'image' not in str(block_type).lower():
                continue
            
            artifact = self._interpret_single_figure(block)
            if artifact:
                figure_artifacts.append(artifact)
        
        logger.info(f"Interpreted {len(figure_artifacts)} figures")
        return figure_artifacts
    
    def _interpret_single_figure(self, block) -> Optional[FigureArtifact]:
        """Interpret a single figure block."""
        # Extract text (OCR + caption)
        text = block.text if hasattr(block, 'text') else ""
        caption = block.metadata.get('caption', '') if hasattr(block, 'metadata') else ""
        
        combined_text = f"{text}\n{caption}".strip()
        
        if not combined_text:
            return None
        
        # Detect figure type
        figure_type = self._detect_figure_type(combined_text)
        
        # Extract axis labels
        axis_labels = self._extract_axis_labels(combined_text)
        
        # Extract legend
        legend_text = self._extract_legend(combined_text)
        
        # Generate semantic summary (LLM call or heuristic)
        semantic_summary = self._generate_semantic_summary(
            combined_text, figure_type, axis_labels, legend_text
        )
        
        # Generate figure ID
        figure_id = f"fig_{hashlib.sha256(combined_text.encode()).hexdigest()[:16]}"
        
        # Extract metadata
        page = block.provenance.page_number if hasattr(block, 'provenance') else 1
        evidence_id = block.evidence_id if hasattr(block, 'evidence_id') else ""
        
        return FigureArtifact(
            figure_id=figure_id,
            figure_type=figure_type,
            axis_labels=axis_labels,
            legend_text=legend_text,
            semantic_summary=semantic_summary,
            source_page=page,
            evidence_ids=[evidence_id] if evidence_id else [],
            metadata={"caption": caption}
        )
    
    def _detect_figure_type(self, text: str) -> str:
        """Detect figure type using keyword matching."""
        text_lower = text.lower()
        
        for fig_type, keywords in self.FIGURE_TYPE_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return fig_type
        
        return "unknown"
    
    def _extract_axis_labels(self, text: str) -> Dict[str, str]:
        """Extract axis labels using simple patterns."""
        axis_labels = {}
        
        # Common patterns: "X-axis: Year", "Y axis: Revenue"
        x_match = re.search(r'x[-\s]?axis[:\s]+([^\n,]+)', text, re.IGNORECASE)
        y_match = re.search(r'y[-\s]?axis[:\s]+([^\n,]+)', text, re.IGNORECASE)
        
        if x_match:
            axis_labels["x"] = x_match.group(1).strip()
        if y_match:
            axis_labels["y"] = y_match.group(1).strip()
        
        return axis_labels
    
    def _extract_legend(self, text: str) -> List[str]:
        """Extract legend items."""
        legend_items = []
        
        # Look for common legend patterns
        legend_match = re.search(r'legend[:\s]+([^\n]+)', text, re.IGNORECASE)
        if legend_match:
            items = legend_match.group(1).split(',')
            legend_items = [item.strip() for item in items if item.strip()]
        
        return legend_items
    
    def _generate_semantic_summary(
        self, text: str, figure_type: str, axis_labels: Dict, legend: List[str]
    ) -> str:
        """
        Generate one-sentence semantic summary.
        Uses LLM if available, otherwise heuristic.
        """
        if self.llm_provider:
            return self._llm_semantic_summary(text, figure_type, axis_labels, legend)
        else:
            return self._heuristic_semantic_summary(text, figure_type, axis_labels, legend)
    
    def _llm_semantic_summary(
        self, text: str, figure_type: str, axis_labels: Dict, legend: List[str]
    ) -> str:
        """Generate summary using LLM (single call, deterministic prompt)."""
        prompt = f"""Given a {figure_type} chart with the following information:
- OCR Text: {text[:500]}
- Axis Labels: {axis_labels}
- Legend: {legend}

Generate ONE sentence describing the main trend or comparison shown in this chart.
Focus on factual description, not interpretation.
Output only the sentence, nothing else."""
        
        try:
            response = self.llm_provider.generate(
                prompt=prompt,
                max_tokens=100,
                temperature=0.0  # Deterministic
            )
            summary = response.text.strip()
            return summary if summary else self._heuristic_semantic_summary(text, figure_type, axis_labels, legend)
        except Exception as e:
            logger.warning(f"LLM summary failed: {e}, using heuristic")
            return self._heuristic_semantic_summary(text, figure_type, axis_labels, legend)
    
    def _heuristic_semantic_summary(
        self, text: str, figure_type: str, axis_labels: Dict, legend: List[str]
    ) -> str:
        """Generate summary using heuristics (no LLM)."""
        x_label = axis_labels.get("x", "categories")
        y_label = axis_labels.get("y", "values")
        
        if figure_type == "bar":
            return f"Bar chart comparing {y_label} across {x_label}."
        elif figure_type == "line":
            return f"Line chart showing {y_label} trend over {x_label}."
        elif figure_type == "pie":
            return f"Pie chart showing distribution of {y_label}."
        elif figure_type == "scatter":
            return f"Scatter plot showing relationship between {x_label} and {y_label}."
        else:
            return f"Chart showing {y_label} data."
