"""Entry point: `patent-screener screen idea.txt`"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.theme import Theme

from cache import Cache
from compare import compare_claim, overlap_score
from extract import extract_idea
from models import PatentReportEntry
from report import build_html_report, build_markdown_report
from sources.base import MissingAPIKeyError, PatentSource
from sources.uspto import USPTOSource
from theme import BANNER, CYAN, PINK, TEXT

console = Console(theme=Theme({"pink": PINK, "cyan": CYAN, "text": TEXT}))

ALL_SOURCES: list[type[PatentSource]] = [USPTOSource]


def _print_banner() -> None:
    console.print(f"[pink]{BANNER}[/pink]")
    console.print("[cyan]patent-screener.exe[/cyan] [text]-- idea screening pipeline[/text]\n")


def _load_sources() -> list[PatentSource]:
    sources: list[PatentSource] = []
    for source_cls in ALL_SOURCES:
        try:
            sources.append(source_cls())
        except MissingAPIKeyError as exc:
            console.print(f"[pink][skip][/pink] {exc}")
    return sources


@click.group()
def main() -> None:
    """Screen a product idea against existing patents."""


@main.command()
@click.argument("idea_path", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=Path("reports"))
@click.option("--html/--no-html", default=True, help="Also write a styled HTML report.")
def screen(idea_path: Path, out_dir: Path, html: bool) -> None:
    """Screen IDEA_PATH (a text file) against existing patents."""
    load_dotenv()
    _print_banner()
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = Cache()

    idea_text = idea_path.read_text()
    console.print("[cyan][1/4][/cyan] Extracting idea elements with Claude...")
    idea = extract_idea(idea_text)
    console.print(f"  summary: {idea.summary}")
    console.print(f"  keywords: {', '.join(idea.keywords)}")

    console.print("[cyan][2/4][/cyan] Searching patent sources...")
    sources = _load_sources()
    if not sources:
        console.print("[pink]No sources are configured. Set API keys in .env and retry.[/pink]")
        sys.exit(1)

    candidates_by_number = {}
    sources_searched: dict[str, int] = {}
    for source in sources:
        try:
            results = source.search(idea.keywords, idea.cpc_classes)
        except Exception as exc:  # noqa: BLE001 - a bad source must not kill the run
            console.print(f"[pink][skip][/pink] {source.name} failed: {exc}")
            continue
        sources_searched[source.name] = len(results)
        for candidate in results:
            candidates_by_number[candidate.patent_number] = (candidate, source)
        console.print(f"  {source.name}: {len(results)} result(s)")

    console.print("[cyan][3/4][/cyan] Fetching claims and comparing...")
    entries: list[PatentReportEntry] = []
    for patent_number, (candidate, source) in candidates_by_number.items():
        try:
            claim_data = source.get_claims(patent_number)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[pink][skip][/pink] {patent_number}: could not fetch claims ({exc})")
            continue
        comparisons = [compare_claim(idea, claim_text) for claim_text in claim_data.independent_claims]
        if not comparisons:
            continue
        entries.append(
            PatentReportEntry(
                candidate=candidate,
                claims=comparisons,
                overlap_score=overlap_score(comparisons),
            )
        )
        console.print(f"  compared {patent_number} ({len(comparisons)} independent claim(s))")

    console.print("[cyan][4/4][/cyan] Writing report...")
    markdown = build_markdown_report(idea, entries, sources_searched)
    md_path = out_dir / f"{idea_path.stem}.md"
    md_path.write_text(markdown)
    console.print(f"  wrote {md_path}")

    if html:
        html_report = build_html_report(idea, entries, sources_searched)
        html_path = out_dir / f"{idea_path.stem}.html"
        html_path.write_text(html_report)
        console.print(f"  wrote {html_path}")

    cache.close()
    console.print("\n[pink]done.[/pink] Screening aid only. Not legal advice.")


if __name__ == "__main__":
    main()
