"""Build the markdown and retro-styled HTML screening reports."""
from __future__ import annotations

from datetime import date

from jinja2 import Template

from models import IdeaBreakdown, PatentReportEntry
from theme import BG, CYAN, PINK, PINK_DARK, TEXT

DISCLAIMER = "Screening aid only. Not legal advice. Consult a patent attorney before selling."


def _sorted_entries(entries: list[PatentReportEntry]) -> list[PatentReportEntry]:
    return sorted(entries, key=lambda e: e.overlap_score, reverse=True)


def build_markdown_report(
    idea: IdeaBreakdown,
    entries: list[PatentReportEntry],
    sources_searched: dict[str, int],
) -> str:
    lines = [f"# Patent Screening Report", "", f"Generated: {date.today().isoformat()}", ""]
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


HTML_TEMPLATE = Template(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Patent Screening Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: {{ bg }};
    --text: {{ text }};
    --pink: {{ pink }};
    --pink-dark: {{ pink_dark }};
    --cyan: {{ cyan }};
  }
  * { box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'VT323', monospace;
    font-size: 20px;
    margin: 0;
    padding: 0 0 4rem;
    background-image:
      linear-gradient(rgba(5,215,250,0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(5,215,250,0.05) 1px, transparent 1px);
    background-size: 24px 24px;
  }
  .titlebar {
    background: #1a0f33;
    border-bottom: 2px solid var(--cyan);
    padding: 0.6rem 1rem;
    font-family: 'Press Start 2P', monospace;
    font-size: 11px;
    color: var(--pink);
    letter-spacing: 1px;
  }
  .wrap { max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem; }
  h1 {
    font-family: 'Press Start 2P', monospace;
    font-size: 22px;
    color: var(--text);
    line-height: 1.6;
  }
  h2 {
    font-family: 'Press Start 2P', monospace;
    font-size: 14px;
    color: var(--cyan);
    margin-top: 2.5rem;
    border-bottom: 2px solid var(--cyan);
    padding-bottom: 0.5rem;
  }
  .meta { color: rgba(243,236,255,0.75); margin-bottom: 0.3rem; }
  .card {
    border: 2px solid var(--pink);
    background: rgba(255,46,136,0.05);
    padding: 1.2rem 1.4rem;
    margin: 1.5rem 0;
  }
  .card h3 {
    font-family: 'Press Start 2P', monospace;
    font-size: 13px;
    color: var(--pink);
    margin-top: 0;
  }
  .badge {
    display: inline-block;
    font-family: 'Press Start 2P', monospace;
    font-size: 10px;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--cyan);
    color: var(--cyan);
  }
  .badge.low-risk { border-color: #4ade80; color: #4ade80; }
  table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 18px; }
  th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid rgba(243,236,255,0.2); }
  th { color: var(--cyan); font-family: 'Press Start 2P', monospace; font-size: 10px; }
  .present { color: #4ade80; }
  .absent { color: var(--pink); }
  .unclear { color: #facc15; }
  .design-around { color: var(--cyan); margin-top: 0.5rem; }
  .disclaimer {
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 2px dashed var(--pink);
    font-family: 'Press Start 2P', monospace;
    font-size: 10px;
    color: var(--pink);
    line-height: 1.8;
  }
</style>
</head>
<body>
  <div class="titlebar">PATENT-SCREENER.EXE &mdash; REPORT</div>
  <div class="wrap">
    <h1>Patent Screening Report</h1>
    <p class="meta">Generated: {{ generated }}</p>
    <p class="meta">Idea: {{ idea.summary }}</p>

    <h2>Coverage</h2>
    <ul class="meta">
      {% for source, count in sources_searched.items() %}
      <li>{{ source }}: {{ count }} result(s)</li>
      {% endfor %}
      {% if sources_searched|length <= 1 %}
      <li>Note: only one source was searched. Coverage is thin.</li>
      {% endif %}
    </ul>

    <h2>Ranked matches</h2>
    {% for entry in entries %}
    <div class="card">
      <h3>{{ entry.candidate.patent_number }} &mdash; {{ entry.candidate.title }}</h3>
      <p class="meta">Assignee: {{ entry.candidate.assignee or 'unknown' }}</p>
      <p class="meta">Filing date: {{ entry.candidate.filing_date or 'unknown' }}</p>
      <p class="meta">
        Status:
        <span class="badge {% if entry.candidate.status.value in ['expired','abandoned'] %}low-risk{% endif %}">
          {{ entry.candidate.status.value }}
        </span>
      </p>
      <p class="meta">Estimated expiry: {{ entry.candidate.estimated_expiry or 'unknown' }}</p>
      <p class="meta">Jurisdiction: {{ entry.candidate.jurisdiction }}</p>
      <p class="meta">Overlap score: {{ "%.0f"|format(entry.overlap_score * 100) }}%</p>

      {% for claim in entry.claims %}
      <p class="meta">Claim {{ loop.index }} &mdash; reads on idea: <strong>{{ 'yes' if claim.reads_on_idea else 'no' }}</strong></p>
      <table>
        <tr><th>Element</th><th>Presence</th><th>Note</th></tr>
        {% for el in claim.elements %}
        <tr>
          <td>{{ el.claim_element }}</td>
          <td class="{{ el.presence }}">{{ el.presence }}</td>
          <td>{{ el.note }}</td>
        </tr>
        {% endfor %}
      </table>
      <p class="design-around">Design-around: {{ claim.design_around }}</p>
      {% endfor %}
    </div>
    {% endfor %}

    <p class="disclaimer">{{ disclaimer }}</p>
  </div>
</body>
</html>
""")


def build_html_report(
    idea: IdeaBreakdown,
    entries: list[PatentReportEntry],
    sources_searched: dict[str, int],
) -> str:
    return HTML_TEMPLATE.render(
        idea=idea,
        entries=_sorted_entries(entries),
        sources_searched=sources_searched,
        generated=date.today().isoformat(),
        disclaimer=DISCLAIMER,
        bg=BG,
        text=TEXT,
        pink=PINK,
        pink_dark=PINK_DARK,
        cyan=CYAN,
    )
