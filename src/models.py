"""Shared data models for the patent screener pipeline."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class IdeaElement(BaseModel):
    name: str = Field(description="Short label for this element, e.g. 'belt-loop anchor'")
    description: str = Field(description="What the element is or does")
    kind: Literal["component", "relationship", "function"]


class IdeaBreakdown(BaseModel):
    summary: str = Field(description="One-sentence summary of the idea")
    elements: list[IdeaElement]
    keywords: list[str] = Field(description="Search keywords, including synonyms")
    cpc_classes: list[str] = Field(description="Likely CPC classification codes, e.g. 'A45F3/04'")


class PatentStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    ABANDONED = "abandoned"
    PENDING = "pending"
    UNKNOWN = "unknown"


class PatentCandidate(BaseModel):
    patent_number: str
    title: str
    assignee: str | None = None
    filing_date: str | None = None
    status: PatentStatus = PatentStatus.UNKNOWN
    estimated_expiry: str | None = None
    jurisdiction: str = "US"
    source: str = Field(description="Which adapter found this candidate")


class ClaimData(BaseModel):
    patent_number: str
    independent_claims: list[str]


class ElementMatch(BaseModel):
    claim_element: str
    presence: Literal["present", "absent", "unclear"]
    note: str = Field(description="Why it's present/absent/unclear; equivalents risk if relevant")


class ClaimComparison(BaseModel):
    claim_text: str
    reads_on_idea: bool = Field(description="True only if every element is present")
    elements: list[ElementMatch]
    design_around: str = Field(description="One element that could be dropped or changed")


class PatentReportEntry(BaseModel):
    candidate: PatentCandidate
    claims: list[ClaimComparison]
    overlap_score: float = Field(description="0-1, share of claim elements marked present, max across claims")
