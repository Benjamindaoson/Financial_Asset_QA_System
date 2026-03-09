"""SEC EDGAR search helpers."""

from __future__ import annotations

from typing import Dict, List, Optional

import httpx

from app.models import SearchResult, WebSearchResult


SEC_HEADERS = {
    "User-Agent": "FinancialAssetQASystem/1.0 support@example.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov",
}


class SECFilingsService:
    """Small SEC EDGAR client for recent filings lookup."""

    def __init__(self):
        self._company_map: Optional[Dict[str, dict]] = None

    async def _load_company_map(self) -> Dict[str, dict]:
        if self._company_map is not None:
            return self._company_map

        async with httpx.AsyncClient(timeout=15, headers=SEC_HEADERS) as client:
            response = await client.get("https://www.sec.gov/files/company_tickers.json")
            response.raise_for_status()
            raw = response.json()

        company_map: Dict[str, dict] = {}
        for item in raw.values():
            ticker = str(item.get("ticker") or "").upper()
            title = str(item.get("title") or "")
            cik_str = str(item.get("cik_str") or "").zfill(10)
            if ticker:
                company_map[ticker] = {"ticker": ticker, "title": title, "cik": cik_str}
        self._company_map = company_map
        return company_map

    async def search(self, query: str, symbols: Optional[List[str]] = None, max_results: int = 5) -> WebSearchResult:
        company_map = await self._load_company_map()
        candidates: List[dict] = []

        for symbol in symbols or []:
            record = company_map.get(symbol.upper())
            if record:
                candidates.append(record)

        if not candidates:
            lowered = query.lower()
            for record in company_map.values():
                if record["ticker"].lower() in lowered or record["title"].lower() in lowered:
                    candidates.append(record)
                if len(candidates) >= 2:
                    break

        if not candidates:
            return WebSearchResult(results=[], search_query=query)

        results: List[SearchResult] = []
        async with httpx.AsyncClient(timeout=15, headers=SEC_HEADERS) as client:
            for candidate in candidates[:2]:
                submissions_url = f"https://data.sec.gov/submissions/CIK{candidate['cik']}.json"
                try:
                    response = await client.get(submissions_url)
                    response.raise_for_status()
                    payload = response.json()
                except Exception:
                    continue

                recent = payload.get("filings", {}).get("recent", {})
                forms = recent.get("form", [])
                filing_dates = recent.get("filingDate", [])
                accession_numbers = recent.get("accessionNumber", [])
                primary_documents = recent.get("primaryDocument", [])

                for form, filing_date, accession, document in zip(forms, filing_dates, accession_numbers, primary_documents):
                    accession_no_dash = accession.replace("-", "")
                    filing_url = (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{int(candidate['cik'])}/{accession_no_dash}/{document}"
                    )
                    results.append(
                        SearchResult(
                            title=f"{candidate['ticker']} {form} filing",
                            snippet=f"{candidate['title']} filed {form} on {filing_date}.",
                            url=filing_url,
                            published=filing_date,
                            source="sec_edgar",
                        )
                    )
                    if len(results) >= max_results:
                        return WebSearchResult(results=results, search_query=query)

        return WebSearchResult(results=results, search_query=query)
