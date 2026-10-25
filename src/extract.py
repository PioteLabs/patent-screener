"""Break a plain-text idea into elements and search terms using Claude."""
from __future__ import annotations

import json
import os

import anthropic

from models import IdeaBreakdown
from usage import UsageTracker

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

EXTRACT_TOOL = {
    "name": "record_idea_breakdown",
    "description": "Record the structured breakdown of a product idea for patent screening.",
    "strict": True,
    "input_schema": IdeaBreakdown.model_json_schema(),
}

SYSTEM_PROMPT = """You break a product idea into discrete elements for patent prior-art screening.
Identify components, relationships between components, and functions. Be literal and specific;
do not invent elements the idea text does not describe. Generate keyword search terms including
synonyms, and your best guess at relevant CPC classification codes.

The user message may include web research findings (possible competitor companies, and patent-style
technical terms found in similar real-world patents or products). When present, fold the technical
terms into your keywords -- patent claims use formal engineering language, not consumer wording, so
those terms often matter more than the idea's own phrasing. Put any company names from that research
into likely_assignees only if they plausibly make this kind of product; otherwise leave it empty.
When no research findings are given, leave likely_assignees as an empty list.

You must call the record_idea_breakdown tool with the result; do not reply in plain text."""


def extract_idea(
    idea_text: str,
    client: anthropic.Anthropic | None = None,
    tracker: UsageTracker | None = None,
    likely_assignees: list[str] | None = None,
    technical_terms: list[str] | None = None,
) -> IdeaBreakdown:
    client = client or anthropic.Anthropic()
    user_message = idea_text
    if likely_assignees or technical_terms:
        user_message += (
            "\n\nWeb research on existing products related to this idea found:\n"
            f"- Possibly relevant companies: {', '.join(likely_assignees) if likely_assignees else 'none found'}\n"
            f"- Patent-style technical terms seen: {', '.join(technical_terms) if technical_terms else 'none found'}"
        )
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[EXTRACT_TOOL],
        messages=[{"role": "user", "content": user_message}],
    )
    if tracker is not None:
        tracker.record(DEFAULT_MODEL, response.usage.input_tokens, response.usage.output_tokens)
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_idea_breakdown":
            return IdeaBreakdown.model_validate(block.input)
    raise RuntimeError("Claude did not return a structured idea breakdown")


if __name__ == "__main__":
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "A sample product idea."
    print(json.dumps(extract_idea(text).model_dump(), indent=2))
