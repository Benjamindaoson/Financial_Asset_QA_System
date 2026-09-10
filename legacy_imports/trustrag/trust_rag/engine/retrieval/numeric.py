import re
from typing import List
from trust_rag.engine.retrieval.types import NumericSignature

class NumericSignatureExtractor:
    def extract(self, text: str) -> List[NumericSignature]:
        sigs = []
        
        # 1. Percent (e.g., 12%, 0.5%)
        # Regex: number optionally followed by %
        for match in re.finditer(r"(\d+(\.\d+)?)\s?%", text):
            sigs.append(NumericSignature(
                type="percent",
                value=float(match.group(1)),
                unit="%",
                raw=match.group(0),
                span=match.span()
            ))

        # 2. Currency (Simple: $100, 100 USD)
        for match in re.finditer(r"[\$￥](\d+(\.\d+)?)", text):
            sigs.append(NumericSignature(
                type="currency",
                value=float(match.group(1)),
                unit=match.group(0)[0], # $ or ￥
                raw=match.group(0),
                span=match.span()
            ))
            
        # 3. Currency Suffix (100 USD)
        for match in re.finditer(r"(\d+(\.\d+)?)\s?(USD|RMB|EUR)", text):
             sigs.append(NumericSignature(
                type="currency",
                value=float(match.group(1)),
                unit=match.group(3),
                raw=match.group(0),
                span=match.span()
            ))
            
        # 4. Duration (3 months, 2 years)
        for match in re.finditer(r"(\d+)\s?(months|years|days|weeks)", text, re.IGNORECASE):
             sigs.append(NumericSignature(
                type="duration",
                value=float(match.group(1)),
                unit=match.group(2).lower(),
                raw=match.group(0),
                span=match.span()
            ))
            
        # 5. Date (YYYY-MM-DD)
        for match in re.finditer(r"\d{4}-\d{2}-\d{2}", text):
             sigs.append(NumericSignature(
                type="date",
                value=match.group(0), # Keep string for date
                unit=None,
                raw=match.group(0),
                span=match.span()
            ))

        return sigs
