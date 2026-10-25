"""Adapter interface that every patent data source implements."""
from __future__ import annotations

from abc import ABC, abstractmethod

from models import ClaimData, PatentCandidate


class MissingAPIKeyError(RuntimeError):
    """Raised when a source's required credentials are not configured."""


class PatentSource(ABC):
    name: str

    @abstractmethod
    def search(
        self, keywords: list[str], cpc_classes: list[str], assignees: list[str] | None = None
    ) -> list[PatentCandidate]:
        """Return deduplicated candidate patents for the given query terms.

        assignees, when given, are searched for directly by name in addition to the
        keyword/CPC search -- useful when a known competitor is likely to hold the patent.
        """

    @abstractmethod
    def get_claims(self, patent_number: str) -> ClaimData:
        """Return the independent claims for a patent number."""
