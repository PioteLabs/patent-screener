from models import (
    ClaimComparison,
    ElementMatch,
    IdeaBreakdown,
    IdeaElement,
    PatentCandidate,
    PatentReportEntry,
    PatentStatus,
)
from report import DISCLAIMER, build_html_report, build_markdown_report


def _sample_entry(patent_number: str, status: PatentStatus, score: float) -> PatentReportEntry:
    return PatentReportEntry(
        candidate=PatentCandidate(
            patent_number=patent_number,
            title="Known patent",
            assignee="Acme Corp",
            filing_date="2010-01-01",
            status=status,
            estimated_expiry="2030-01-01",
            jurisdiction="US",
            source="uspto_odp",
        ),
        claims=[
            ClaimComparison(
                claim_text="a widget comprising A and B",
                reads_on_idea=False,
                elements=[
                    ElementMatch(claim_element="A", presence="present", note=""),
                    ElementMatch(claim_element="B", presence="absent", note="no close substitute"),
                ],
                design_around="Drop element B",
            )
        ],
        overlap_score=score,
    )


def _idea() -> IdeaBreakdown:
    return IdeaBreakdown(
        summary="A test idea",
        elements=[IdeaElement(name="A", description="part A", kind="component")],
        keywords=["widget"],
        cpc_classes=["A45F3/04"],
    )


def test_markdown_report_ranks_by_overlap_and_includes_disclaimer():
    low = _sample_entry("US1", PatentStatus.ACTIVE, 0.3)
    high = _sample_entry("US2", PatentStatus.EXPIRED, 0.9)
    report = build_markdown_report(_idea(), [low, high], {"uspto_odp": 2})
    assert report.index("US2") < report.index("US1")
    assert DISCLAIMER in report
    assert "unknown" not in report.split("## Coverage")[0]


def test_markdown_report_flags_thin_coverage():
    report = build_markdown_report(_idea(), [], {"uspto_odp": 0})
    assert "only one source was searched" in report


def test_html_report_renders_without_error_and_includes_patent_number():
    entry = _sample_entry("US123456", PatentStatus.ACTIVE, 0.5)
    html = build_html_report(_idea(), [entry], {"uspto_odp": 1})
    assert "US123456" in html
    assert DISCLAIMER in html
