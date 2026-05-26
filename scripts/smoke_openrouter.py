"""Smoke test: one tiny call per cross-lab model.

Confirms OpenRouter auth works and that every pinned model id in the registry
actually resolves, before spending on a full run. Each call caps output at a few
tokens, so the whole sweep costs ~1-2 cents. One bad id is reported and the sweep
continues.

Needs OPENROUTER_API_KEY in .env (BYOK routes the Anthropic models too).

    uv run python scripts/smoke_openrouter.py
"""
from __future__ import annotations

from dotenv import load_dotenv

from agentic_fit.agent import OpenRouterClient
from agentic_fit.crosslab_models import CROSSLAB_MODELS


def main() -> None:
    load_dotenv()
    ok = 0
    for spec in CROSSLAB_MODELS:
        try:
            client = OpenRouterClient(spec.model_id, max_tokens=16)
            r = client.complete(
                "Reply with the single word OK.",
                [{"role": "user", "content": "Say OK."}],
            )
            reply = r.text.strip()[:20]
            print(f"  ok    {spec.model_id:40s} {r.input_tokens}+{r.output_tokens} tok :: {reply!r}")
            ok += 1
        except Exception as exc:
            print(f"  FAIL  {spec.model_id:40s} {type(exc).__name__}: {str(exc)[:120]}")
    print(f"\n{ok}/{len(CROSSLAB_MODELS)} models reachable")


if __name__ == "__main__":
    main()
