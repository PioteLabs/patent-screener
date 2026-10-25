"""Compare an idea's elements against a patent's independent claims."""
from __future__ import annotations

import os

import anthropic

from models import ClaimComparison, IdeaBreakdown
from usage import UsageTracker

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

COMPARE_TOOL = {
    "name": "record_claim_comparison",
    "description": "Record an element-by-element comparison of one patent claim against the idea.",
    "input_schema": ClaimComparison.model_json_schema(),
}

SYSTEM_PROMPT = """You compare a product idea against one independent patent claim, element by element.
Rules:
- Break the claim into its elements yourself; compare each against the idea.
- A claim only reads on the idea if EVERY element is present in the idea. Set reads_on_idea accordingly.
- Mark each element "present", "absent", or "unclear". Use "unclear" instead of guessing when claim
  language is ambiguous or the idea text does not say enough to judge.
- When an element is absent, note it clearly and flag doctrine-of-equivalents risk in `note` if the
  idea has a close substitute for that element.
- design_around: name the single claim element that, if the idea dropped or changed it, would most
  cleanly avoid this claim.
Compare against claim language only. Do not consider the patent's title or abstract.
Call record_claim_comparison with the result."""


def compare_claim(
    idea: IdeaBreakdown,
    claim_text: str,
    client: anthropic.Anthropic | None = None,
    tracker: UsageTracker | None = None,
) -> ClaimComparison:
    client = client or anthropic.Anthropic()
    idea_description = "\n".join(f"- {e.name}: {e.description}" for e in idea.elements)
    user_message = (
        f"Idea summary: {idea.summary}\n\nIdea elements:\n{idea_description}\n\n"
        f"Patent claim:\n{claim_text}"
    )
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[COMPARE_TOOL],
        tool_choice={"type": "tool", "name": "record_claim_comparison"},
        messages=[{"role": "user", "content": user_message}],
    )
    if tracker is not None:
        tracker.record(DEFAULT_MODEL, response.usage.input_tokens, response.usage.output_tokens)
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_claim_comparison":
            return ClaimComparison.model_validate(block.input)
    raise RuntimeError("Claude did not return a structured claim comparison")


def overlap_score(comparisons: list[ClaimComparison]) -> float:
    """Highest share of 'present' elements across all compared claims."""
    best = 0.0
    for comparison in comparisons:
        if not comparison.elements:
            continue
        present = sum(1 for e in comparison.elements if e.presence == "present")
        best = max(best, present / len(comparison.elements))
    return best
