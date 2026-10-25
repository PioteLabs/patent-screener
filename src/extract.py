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
synonyms, and your best guess at relevant CPC classification codes. You must call the
record_idea_breakdown tool with the result; do not reply in plain text."""


def extract_idea(
    idea_text: str,
    client: anthropic.Anthropic | None = None,
    tracker: UsageTracker | None = None,
) -> IdeaBreakdown:
    client = client or anthropic.Anthropic()
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[EXTRACT_TOOL],
        messages=[{"role": "user", "content": idea_text}],
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
