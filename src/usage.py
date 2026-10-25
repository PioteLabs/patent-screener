"""Track Claude API token usage and estimate cost across a single run.

Costs are read off every API response's `usage` field, which Anthropic returns
for free with every call. Tracking it adds no extra requests and no extra cost.

Prices below are per million tokens and were current as of October 2026.
Verify against https://platform.claude.com/docs/en/about-claude/pricing before
relying on this for budgeting -- Anthropic changes prices over time.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# (input $/M tokens, output $/M tokens)
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (15.00, 75.00),
}
FALLBACK_PRICING = (3.00, 15.00)  # used for an unrecognized model, so cost is never silently zero
WEB_SEARCH_PRICE_PER_SEARCH = 0.01  # $10 per 1,000 searches, billed per use regardless of result count


@dataclass
class UsageTracker:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    search_requests: int = 0
    by_model: dict[str, tuple[int, int]] = field(default_factory=dict)

    def record(self, model: str, input_tokens: int, output_tokens: int, search_requests: int = 0) -> None:
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.search_requests += search_requests
        prev_in, prev_out = self.by_model.get(model, (0, 0))
        self.by_model[model] = (prev_in + input_tokens, prev_out + output_tokens)

    def estimated_cost_usd(self) -> float:
        total = self.search_requests * WEB_SEARCH_PRICE_PER_SEARCH
        for model, (in_tok, out_tok) in self.by_model.items():
            in_price, out_price = PRICING.get(model, FALLBACK_PRICING)
            total += (in_tok / 1_000_000) * in_price + (out_tok / 1_000_000) * out_price
        return total

    def summary(self) -> dict:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "search_requests": self.search_requests,
            "estimated_cost_usd": round(self.estimated_cost_usd(), 4),
        }
