from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    provider: str = "none_sample_mode"


def estimate_llm_cost_usd(provider: str, model: str, usage: TokenUsage) -> float:
    if provider != "gemini":
        return 0.0

    if model == "gemini-2.5-flash-lite":
        input_per_million = 0.10
        output_per_million = 0.40
    else:
        return 0.0

    input_cost = usage.input_tokens * input_per_million / 1_000_000
    output_cost = usage.output_tokens * output_per_million / 1_000_000
    return round(input_cost + output_cost, 8)


ZERO_TOKEN_USAGE = TokenUsage()

