"""
Stable Evidence ID Factory.
"""
import hashlib
import re

def normalize_text(text: str) -> str:
    """Normalize text for stable hashing."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Strip
    text = text.strip()
    # Remove invisible characters
    text = ''.join(c for c in text if c.isprintable() or c in '\n\t')
    return text

def generate_evidence_id(doc_id: str, page: int, block_index: int, text: str) -> str:
    """
    Generate a stable, reproducible evidence ID.
    Format: ev_<sha256(doc_id + page + block_index + normalized_text[:100])[:16]>
    """
    normalized = normalize_text(text)[:100]
    composite = f"{doc_id}|{page}|{block_index}|{normalized}"
    hash_val = hashlib.sha256(composite.encode('utf-8')).hexdigest()[:16]
    return f"ev_{hash_val}"
