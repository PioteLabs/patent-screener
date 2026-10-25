"""USPTO Open Data Portal (ODP) adapter.

PatentsView's legacy search API (api.patentsview.org / search.patentsview.org)
is being retired and folded into the USPTO Open Data Portal. As of writing,
getting an ODP API key requires a full USPTO.gov account with MFA enabled
(see https://www.uspto.gov/subscription-center for the current process).

ODP's application search endpoint returns bibliographic metadata and legal
status, but not claim text. Claim text comes from the official USPTO patent
grant XML (the same bulk full-text data USPTO publishes), fetched per patent
via the `fileLocationURI` the search result points to. This is first-party
USPTO data, not a third-party scrape.

Re-check https://data.uspto.gov/apis before relying on this in production;
ODP is new and still settling, and endpoint shapes have changed before.
"""
from __future__ import annotations

import os
from xml.etree import ElementTree

import httpx

from models import ClaimData, PatentCandidate, PatentStatus
from sources.base import MissingAPIKeyError, PatentSource

BASE_URL = "https://api.uspto.gov/api/v1/patent/applications"


def _extract_independent_claims(xml_bytes: bytes) -> list[str]:
    """Parse a USPTO patent grant XML document for independent claim text.

    A claim is dependent if it contains a <claim-ref> anywhere in its body
    (it refers back to another claim); independent claims have none.
    """
    root = ElementTree.fromstring(xml_bytes)
    independent: list[str] = []
    for claim in root.iter("claim"):
        if claim.find(".//claim-ref") is not None:
            continue
        text = "".join(claim.itertext()).strip()
        text = " ".join(text.split())
        if text:
            independent.append(text)
    return independent


class USPTOSource(PatentSource):
    name = "uspto_odp"

    def __init__(self, api_key: str | None = None, timeout: float = 20.0):
        self.api_key = api_key or os.environ.get("USPTO_API_KEY")
        if not self.api_key:
            raise MissingAPIKeyError(
                "USPTO_API_KEY is not set. Get one at https://data.uspto.gov/apis "
                "(requires a USPTO.gov account with MFA). Skipping this source."
            )
        headers = {"X-API-KEY": self.api_key, "Accept": "application/json"}
        self._client = httpx.Client(base_url=BASE_URL, headers=headers, timeout=timeout)
        self._files_client = httpx.Client(headers=headers, timeout=timeout, follow_redirects=True)
        self._grant_xml_url_by_number: dict[str, str] = {}

    def search(
        self, keywords: list[str], cpc_classes: list[str], assignees: list[str] | None = None
    ) -> list[PatentCandidate]:
        query = " OR ".join(f'"{kw}"' for kw in keywords)
        candidates: dict[str, PatentCandidate] = {}
        for variant_query in self._query_variants(query, cpc_classes, assignees or []):
            response = self._client.post(
                "/search",
                json={"q": variant_query, "pagination": {"offset": 0, "limit": 25}},
            )
            if response.status_code == 404:
                continue  # ODP returns 404 (not an empty 200) when a query variant matches nothing
            response.raise_for_status()
            for doc in response.json().get("patentFileWrapperDataBag", []):
                candidate = self._parse_candidate(doc)
                if candidate:
                    candidates[candidate.patent_number] = candidate
        return list(candidates.values())

    def get_claims(self, patent_number: str) -> ClaimData:
        grant_xml_url = self._grant_xml_url_by_number.get(patent_number)
        if not grant_xml_url:
            raise RuntimeError(
                f"No grant document on file for {patent_number} (it may not be granted yet, "
                "or search() was not called first)."
            )
        response = self._files_client.get(grant_xml_url)
        response.raise_for_status()
        claims = _extract_independent_claims(response.content)
        return ClaimData(patent_number=patent_number, independent_claims=claims)

    def _query_variants(self, keyword_query: str, cpc_classes: list[str], assignees: list[str]) -> list[str]:
        variants = [keyword_query]
        for cpc in cpc_classes:
            variants.append(f"cpcClassificationBag:{cpc}")
        for name in assignees:
            safe_name = name.replace('"', "")
            variants.append(f'applicationMetaData.firstApplicantName:"{safe_name}"')
        return variants

    def _parse_candidate(self, doc: dict) -> PatentCandidate | None:
        meta = doc.get("applicationMetaData", {})
        patent_number = meta.get("patentNumber")
        if not patent_number:
            return None  # not granted yet, so there is no claim text to compare

        grant_xml_url = doc.get("grantDocumentMetaData", {}).get("fileLocationURI")
        if grant_xml_url:
            self._grant_xml_url_by_number[patent_number] = grant_xml_url

        status_text = (meta.get("applicationStatusDescriptionText") or "").lower()
        if "abandon" in status_text:
            status = PatentStatus.ABANDONED
        elif "patent" in status_text:
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
            estimated_expiry=meta.get("patentExpirationDate"),  # often absent; see docstring
            jurisdiction="US",
            source=self.name,
        )
