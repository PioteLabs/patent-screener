"""The full idea -> extract -> search -> compare pipeline, shared by the CLI and the web UI."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from compare import compare_claim, overlap_score
from extract import extract_idea
from models import IdeaBreakdown, PatentReportEntry
from sources.base import MissingAPIKeyError, PatentSource
from sources.uspto import USPTOSource
from usage import UsageTracker

ALL_SOURCES: list[type[PatentSource]] = [USPTOSource]


@dataclass
class PipelineResult:
    idea: IdeaBreakdown
    entries: list[PatentReportEntry]
    sources_searched: dict[str, int]
    skipped: list[str] = field(default_factory=list)
    usage: UsageTracker = field(default_factory=UsageTracker)


ProgressCallback = Callable[[str, int, int], None]


def run_pipeline(
    idea_text: str,
    on_event: Callable[[str], None] | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    log = on_event or (lambda _msg: None)
    progress = on_progress or (lambda _phase, _completed, _total: None)
    tracker = UsageTracker()
    skipped: list[str] = []

    progress("extract", 0, 1)
    log("Extracting idea elements with Claude...")
    idea = extract_idea(idea_text, tracker=tracker)
    log(f"  summary: {idea.summary}")
    progress("extract", 1, 1)

    progress("search", 0, 1)
    log("Loading configured patent sources...")
    sources: list[PatentSource] = []
    for source_cls in ALL_SOURCES:
        try:
            sources.append(source_cls())
        except MissingAPIKeyError as exc:
            skipped.append(str(exc))
            log(f"  [skip] {exc}")

    log("Searching...")
    candidates_by_number = {}
    sources_searched: dict[str, int] = {}
    for source in sources:
        try:
            results = source.search(idea.keywords, idea.cpc_classes)
        except Exception as exc:  # noqa: BLE001 - a bad source must not kill the run
            skipped.append(f"{source.name} search failed: {exc}")
            log(f"  [skip] {source.name} failed: {exc}")
            continue
        sources_searched[source.name] = len(results)
        for candidate in results:
            candidates_by_number[candidate.patent_number] = (candidate, source)
        log(f"  {source.name}: {len(results)} result(s)")
    progress("search", 1, 1)

    total_candidates = len(candidates_by_number)
    progress("compare", 0, total_candidates)
    log("Fetching claims and comparing...")
    entries: list[PatentReportEntry] = []
    for i, (patent_number, (candidate, source)) in enumerate(candidates_by_number.items(), start=1):
        try:
            claim_data = source.get_claims(patent_number)
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"{patent_number}: could not fetch claims ({exc})")
            log(f"  [skip] {patent_number}: could not fetch claims ({exc})")
            progress("compare", i, total_candidates)
            continue
        comparisons = [
            compare_claim(idea, claim_text, tracker=tracker)
            for claim_text in claim_data.independent_claims
        ]
        if comparisons:
            entries.append(
                PatentReportEntry(
                    candidate=candidate,
                    claims=comparisons,
                    overlap_score=overlap_score(comparisons),
                )
            )
            log(f"  compared {patent_number} ({len(comparisons)} independent claim(s))")
        progress("compare", i, total_candidates)

    progress("finalize", 1, 1)
    return PipelineResult(
        idea=idea,
        entries=entries,
        sources_searched=sources_searched,
        skipped=skipped,
        usage=tracker,
    )
