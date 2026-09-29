"""Per-token prices, used to compute cost from measured token counts.

USD per million tokens. Checked 2026-09-27:
  jev-1.13.0: docs.typesafe.ai/models.md ($0.042 / Mtok input; output tokens free)
  claude-haiku-4-5: platform.claude.com/docs/en/about-claude/pricing ($1 in / $5 out)
When a price changes, add a new entry; don't rewrite old ones.
"""
PRICES = {
    "jev-1.13.0": {"input": 0.042, "output": 0.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
}
ALIASES = {"jev-latest": "jev-1.13.0", "jev-preview": "jev-1.13.0"}
AS_OF = "2026-09-27"


def price(model):
    if model is None:
        return None
    m = ALIASES.get(model, model)
    if m in PRICES:
        return PRICES[m]
    for k, v in PRICES.items():  # dated snapshot ids, e.g. claude-haiku-4-5-20251001
        if m.startswith(k):
            return v
    return None


def cost_usd(model, input_tokens, output_tokens):
    p = price(model)
    if p is None or input_tokens is None:
        return None
    return (input_tokens * p["input"] + (output_tokens or 0) * p["output"]) / 1e6
