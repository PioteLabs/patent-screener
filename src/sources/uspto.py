"""USPTO Open Data Portal (ODP) adapter.

PatentsView's legacy search API (api.patentsview.org / search.patentsview.org)
is being retired and folded into the USPTO Open Data Portal. As of writing,
getting an ODP API key requires a full USPTO.gov account with MFA enabled
(see https://www.uspto.gov/subscription-center for the current process).

Endpoint paths below match ODP's documented patent application search API.
ODP is new and still settling; re-check https://data.uspto.gov/apis before
relying on this in production, and update this adapter if paths change.
"""
from __future__ import annotations

import os

import httpx

from models import ClaimData, PatentCandidate, PatentStatus
from sources.base import MissingAPIKeyError, PatentSource

BASE_URL = "https://api.uspto.gov/api/v1/patent/applications"


class USPTOSource(PatentSource):
    name = "uspto_odp"

    def __init__(self, api_key: str | None = None, timeout: float = 15.0):
        self.api_key = api_key or os.environ.get("USPTO_API_KEY")
        if not self.api_key:
            raise MissingAPIKeyError(
                "USPTO_API_KEY is not set. Get one at https://data.uspto.gov/apis "
                "(requires a USPTO.gov account with MFA). Skipping this source."
            )
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"X-API-KEY": self.api_key, "Accept": "application/json"},
            timeout=timeout,
        )

    def search(self, keywords: list[str], cpc_classes: list[str]) -> list[PatentCandidate]:
        query = " OR ".join(f'"{kw}"' for kw in keywords)
        candidates: dict[str, PatentCandidate] = {}
        for variant_query in self._query_variants(query, cpc_classes):
            response = self._client.post(
                "/search",
                json={"q": variant_query, "rows": 25},
            )
            response.raise_for_status()
            for doc in response.json().get("patentFileWrapperDataBag", []):
                candidate = self._parse_candidate(doc)
                if candidate:
                    candidates[candidate.patent_number] = candidate
        return list(candidates.values())

    def get_claims(self, patent_number: str) -> ClaimData:
        response = self._client.get(f"/{patent_number}/claims")
        response.raise_for_status()
        data = response.json()
        claims = [
            c["claimText"]
            for c in data.get("claims", [])
            if c.get("claimType") == "independent"
        ]
        return ClaimData(patent_number=patent_number, independent_claims=claims)

    def _query_variants(self, keyword_query: str, cpc_classes: list[str]) -> list[str]:
        variants = [keyword_query]
        for cpc in cpc_classes:
            variants.append(f"cpcClassificationBag:{cpc}")
        return variants

    def _parse_candidate(self, doc: dict) -> PatentCandidate | None:
        meta = doc.get("applicationMetaData", {})
        patent_number = meta.get("patentNumber") or doc.get("applicationNumberText")
        if not patent_number:
            return None
        status_text = (meta.get("applicationStatusDescriptionText") or "").lower()
        if "abandon" in status_text:
            status = PatentStatus.ABANDONED
        elif "patented" in status_text or "active" in status_text:
            status = PatentStatus.ACTIVE
        elif "pending" in status_text:
            status = PatentStatus.PENDING
        else:
            status = PatentStatus.UNKNOWN
        return PatentCandidate(
            patent_number=patent_number,
            title=meta.get("inventionTitle", "Unknown title"),
            assignee=(meta.get("firstApplicantName") or None),
            filing_date=meta.get("filingDate"),
            status=status,
            estimated_expiry=meta.get("patentExpirationDate"),
            jurisdiction="US",
            source=self.name,
        )
