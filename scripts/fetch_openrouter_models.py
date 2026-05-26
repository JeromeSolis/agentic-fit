"""List OpenRouter models and prices to help pin the cross-lab registry.

OpenRouter's /models endpoint is public (no auth). Pricing fields are USD per
single token as strings; this prints USD per 1M tokens.

Usage:
    python scripts/fetch_openrouter_models.py claude gpt gemini deepseek qwen kimi glm command mistral
"""
from __future__ import annotations

import sys
import urllib.request
import json

URL = "https://openrouter.ai/api/v1/models"


def fetch() -> list[dict]:
    with urllib.request.urlopen(URL, timeout=30) as resp:
        return json.loads(resp.read())["data"]


def main(fragments: list[str]) -> None:
    frags = [f.lower() for f in fragments] or [""]
    rows = []
    for m in fetch():
        mid = m["id"]
        if not any(f in mid.lower() for f in frags):
            continue
        pricing = m.get("pricing", {})
        p_in = float(pricing.get("prompt", 0) or 0) * 1_000_000
        p_out = float(pricing.get("completion", 0) or 0) * 1_000_000
        rows.append((mid, p_in, p_out))
    for mid, p_in, p_out in sorted(rows):
        print(f"{mid:55s}  in=${p_in:7.3f}/M  out=${p_out:7.3f}/M")


if __name__ == "__main__":
    main(sys.argv[1:])
