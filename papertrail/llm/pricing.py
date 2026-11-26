"""Approximate per-token prices, used to report "cost per check".

Prices are USD per million tokens (input, output) at Anthropic first-party rates, cached
2026-11. Bedrock pricing is set by AWS and can differ, so treat these numbers as estimates. Unknown
models (local Ollama, mock) cost 0.
"""

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def _base_model_id(model: str) -> str:
    """Strip provider prefixes, e.g. Bedrock's 'anthropic.' or a regional 'apac.' prefix."""
    return model.rsplit("anthropic.", 1)[-1]


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICES_PER_MTOK.get(_base_model_id(model))
    if price is None:
        return 0.0
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000
