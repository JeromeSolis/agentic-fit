"""Curated cross-lab model registry.

Every model routes through OpenRouter (`provider="openrouter"`). The Anthropic
(Claude) models use OpenRouter's BYOK: the account's own Anthropic key is stored
on OpenRouter, so those runs bill to prepaid Anthropic credit (plus OpenRouter's
~5% BYOK fee) while still going through the single OpenRouter path. This means
the harness needs only OPENROUTER_API_KEY.

`model_id` is recorded as RunResult.model, is the key into the budget price
table, and is the OpenRouter id passed to the client. Prices are the OpenRouter
catalog snapshot (USD per 1M tokens), so every model is priced on one basis.

Versions are PINNED (no `-latest` aliases) for reproducibility. Refresh via:
    python scripts/fetch_openrouter_models.py claude gpt gemini deepseek qwen kimi glm command mistral

Snapshot date: 2026-05-24
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    model_id: str       # recorded as RunResult.model; budget price-table key; OpenRouter id
    provider: str       # "anthropic" | "openrouter"
    price_in: float     # USD per 1M input tokens (OpenRouter snapshot)
    price_out: float    # USD per 1M output tokens


# 16 models, all via OpenRouter. Pinned versions; prices = OpenRouter 2026-05-24 snapshot.
CROSSLAB_MODELS: list[ModelSpec] = [
    # Anthropic (OpenRouter BYOK -> prepaid Anthropic credit)
    ModelSpec("anthropic/claude-opus-4.7",   "openrouter", 5.0, 25.0),
    ModelSpec("anthropic/claude-sonnet-4.6", "openrouter", 3.0, 15.0),
    ModelSpec("anthropic/claude-haiku-4.5",  "openrouter", 1.0, 5.0),
    # OpenAI
    ModelSpec("openai/gpt-5.5",      "openrouter", 5.0, 30.0),
    ModelSpec("openai/gpt-5.4-mini", "openrouter", 0.75, 4.5),
    # Google
    ModelSpec("google/gemini-3.1-pro-preview", "openrouter", 2.0, 12.0),
    ModelSpec("google/gemini-3.5-flash",       "openrouter", 1.5, 9.0),
    # Moonshot
    ModelSpec("moonshotai/kimi-k2.6", "openrouter", 0.73, 3.49),
    # DeepSeek (flagship + cheaper alt)
    ModelSpec("deepseek/deepseek-v4-pro", "openrouter", 0.435, 0.87),
    ModelSpec("deepseek/deepseek-v3.2",   "openrouter", 0.252, 0.378),
    # Qwen (flagship + coder-tuned alt)
    ModelSpec("qwen/qwen3.7-max",      "openrouter", 2.5, 7.5),
    ModelSpec("qwen/qwen3-coder-plus", "openrouter", 0.65, 3.25),
    # GLM
    ModelSpec("z-ai/glm-5.1", "openrouter", 0.98, 3.08),
    # Cohere
    ModelSpec("cohere/command-a", "openrouter", 2.5, 10.0),
    # Mistral (flagship + code-tuned alt)
    ModelSpec("mistralai/mistral-large-2512", "openrouter", 0.5, 1.5),
    ModelSpec("mistralai/codestral-2508",     "openrouter", 0.3, 0.9),
]


def register_crosslab_prices() -> None:
    """Load the registry's prices into the budget price table."""
    from .budget import register_prices
    register_prices([(s.model_id, s.price_in, s.price_out) for s in CROSSLAB_MODELS])
