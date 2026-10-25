"""Build the markdown and retro-styled HTML screening reports.

The HTML rendering lives in src/templates/ and is shared with the local web UI
(web.py) via the same Jinja environment, so the file report and the browser
view always look identical.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from models import IdeaBreakdown, PatentReportEntry
from theme import BG, CYAN, PINK, PINK_DARK, TEXT

DISCLAIMER = "Screening aid only. Not legal advice. Consult a patent attorney before selling."

TEMPLATES_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)

THEME_VARS = {"bg": BG, "text": TEXT, "pink": PINK, "pink_dark": PINK_DARK, "cyan": CYAN}


def _sorted_entries(entries: list[PatentReportEntry]) -> list[PatentReportEntry]:
    return sorted(entries, key=lambda e: e.overlap_score, reverse=True)


def build_markdown_report(
    idea: IdeaBreakdown,
    entries: list[PatentReportEntry],
    sources_searched: dict[str, int],
) -> str:
    lines = ["# Patent Screening Report", "", f"Generated: {date.today().isoformat()}", ""]
    lines.append(f"**Idea:** {idea.summary}")
    lines.append("")
    lines.append("## Coverage")
    for source, count in sources_searched.items():
        lines.append(f"- {source}: {count} result(s)")
    if len(sources_searched) <= 1:
        lines.append("- Note: only one source was searched. Coverage is thin.")
    lines.append("")
    lines.append("## Ranked matches")
    for entry in _sorted_entries(entries):
        c = entry.candidate
        lines.append("")
        lines.append(f"### {c.patent_number} - {c.title}")
        lines.append(f"- Reference: {c.reference_url()}")
        lines.append(f"- Assignee: {c.assignee or 'unknown'}")
        lines.append(f"- Filing date: {c.filing_date or 'unknown'}")
        lines.append(f"- Status: **{c.status.value}**" + (" (lower risk)" if c.status.value in ("expired", "abandoned") else ""))
        lines.append(f"- Estimated expiry: {c.estimated_expiry or 'unknown'}")
        lines.append(f"- Jurisdiction: {c.jurisdiction}")
        lines.append(f"- Overlap score: {entry.overlap_score:.0%}")
        for i, claim in enumerate(entry.claims, start=1):
            lines.append("")
            lines.append(f"**Claim {i}** (reads on idea: {'yes' if claim.reads_on_idea else 'no'})")
            lines.append("")
            lines.append("| Element | Presence | Note |")
            lines.append("|---|---|---|")
            for el in claim.elements:
                note = el.note.replace("|", "\\|")
                lines.append(f"| {el.claim_element} | {el.presence} | {note} |")
            lines.append("")
            lines.append(f"Design-around: {claim.design_around}")
    lines.append("")
    lines.append("---")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def build_html_report(
    idea: IdeaBreakdown,
    entries: list[PatentReportEntry],
    sources_searched: dict[str, int],
) -> str:
    template = jinja_env.get_template("report.html")
    return template.render(
        idea=idea,
        entries=_sorted_entries(entries),
        sources_searched=sources_searched,
        generated=date.today().isoformat(),
        disclaimer=DISCLAIMER,
        **THEME_VARS,
    )
