"""Research real-world products/companies that might already cover an idea.

Uses Claude's hosted web search tool (billed ~$0.01/search plus normal token
cost, through the same ANTHROPIC_API_KEY) instead of a separate search vendor.
This exists because keyword search alone misses prior art that uses different
wording than the idea text (patent claims say "inertial measurement unit",
not "motion sensor") -- but a competitor's name, once known, finds it directly.
"""
from __future__ import annotations

import json
import os
import re

import anthropic
from pydantic import BaseModel, Field

from usage import UsageTracker

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}

SYSTEM_PROMPT = """You research whether a product idea already has real-world competitors, to help a
patent prior-art search use better search terms. Search the web for existing products or companies
that closely match the idea. Prefer specific company or product names over generic results.

When you are done searching, reply with ONLY a single JSON object (no other text, no markdown
fences) matching this shape:
{
  "likely_assignees": ["Company Name", ...],
  "technical_terms": ["term", ...],
  "notes": "one or two sentences on what you found, or that nothing relevant turned up"
}
likely_assignees: real company names that plausibly hold a patent on this, based on what you found.
Empty list if none found -- never guess a company that your search did not surface.
technical_terms: patent-style technical terms or synonyms seen in search results that differ from
the idea's own wording (e.g. "inertial measurement unit" instead of "motion sensor"). Empty if none.
Keep both lists to at most 6 items."""


class ResearchFindings(BaseModel):
    likely_assignees: list[str] = Field(default_factory=list)
    technical_terms: list[str] = Field(default_factory=list)
    notes: str = ""


def research_idea(
    idea_text: str,
    client: anthropic.Anthropic | None = None,
    tracker: UsageTracker | None = None,
) -> ResearchFindings:
    client = client or anthropic.Anthropic()
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[WEB_SEARCH_TOOL],
        messages=[{"role": "user", "content": f"Product idea: {idea_text}"}],
    )

    if tracker is not None:
        server_tool_use = getattr(response.usage, "server_tool_use", None)
        search_requests = getattr(server_tool_use, "web_search_requests", 0) or 0
        tracker.record(
            DEFAULT_MODEL,
            response.usage.input_tokens,
            response.usage.output_tokens,
            search_requests=search_requests,
        )

    text = "".join(block.text for block in response.content if block.type == "text")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return ResearchFindings(notes="Could not parse research findings from the model's response.")
    try:
        return ResearchFindings.model_validate(json.loads(match.group(0)))
    except Exception:
        return ResearchFindings(notes="Could not parse research findings from the model's response.")
