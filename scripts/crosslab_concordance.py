"""Cross-lab popularity concordance: does PyPI download rank predict which library
is cheapest for an agent? Reuses the C2 pairwise-concordance logic across every
model in a cross-lab results file.

    python scripts/crosslab_concordance.py results/crosslab_reps3_2026-05-25.jsonl
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

from agentic_fit.novelty import analyze
from agentic_fit.popularity import load_popularity
from agentic_fit.scoring import load_results


def main(path: str) -> None:
    rows = load_results(Path(path))
    by_model: dict[str, list] = collections.defaultdict(list)
    for r in rows:
        by_model[r.model].append(r)
    libs = sorted({r.library for r in rows})
    popularity = load_popularity(libs, Path("data/pypi_downloads.json"), pause=1.0)
    rep = analyze(dict(by_model), popularity)
    rate = f"{rep.rate:.0%}" if rep.rate is not None else "N/A"
    print(f"cross-lab concordance: {rate}  "
          f"({rep.concordant} concordant / {rep.discordant} discordant, "
          f"{rep.excluded_ties} ties excluded) · "
          f"{rep.n_inversions} cross-model inversions · verdict {rep.verdict}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/crosslab_reps3_2026-05-25.jsonl")
