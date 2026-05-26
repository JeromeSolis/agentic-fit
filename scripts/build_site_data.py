# scripts/build_site_data.py
"""Aggregate cross-lab benchmark results into the JSON the showcase site renders.

    python scripts/build_site_data.py --in results/crosslab_reps3_2026-05-25.jsonl --out site/data.json

Reads one row per (model, library, category, rep) and collapses reps into a
single cell: success_rate, median cost_usd, and rep count n. Median (not mean)
matches the canonical metric in agentic_fit.scoring.score_crosslab, so the site
reproduces the published FINDINGS. Pure stdlib so the build needs no extra deps.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path

DEFAULT_IN = "results/crosslab_reps3_2026-05-25.jsonl"
DEFAULT_OUT = "site/data.json"


def aggregate(rows: list[dict]) -> dict:
    groups: dict[tuple, list[dict]] = collections.defaultdict(list)
    for r in rows:
        groups[(r["model"], r["category"], r["library"])].append(r)

    cells = []
    libs_by_cat: dict[str, set] = collections.defaultdict(set)
    models: set = set()
    categories: set = set()
    for (model, category, library), rs in groups.items():
        n = len(rs)
        successes = sum(1 for r in rs if r["success"])
        cells.append({
            "model": model,
            "category": category,
            "library": library,
            "success_rate": successes / n,
            "cost_usd": statistics.median(r["cost_usd"] for r in rs),
            "n": n,
        })
        libs_by_cat[category].add(library)
        models.add(model)
        categories.add(category)

    cells.sort(key=lambda c: (c["category"], c["library"], c["model"]))
    return {
        "models": sorted(models),
        "categories": sorted(categories),
        "libraries_by_category": {c: sorted(libs_by_cat[c]) for c in sorted(libs_by_cat)},
        "cells": cells,
    }


def build(in_path: Path, out_path: Path) -> dict:
    rows = [json.loads(line) for line in in_path.read_text().splitlines() if line.strip()]
    stem = in_path.stem  # e.g. crosslab_reps3_2026-05-25
    snapshot = stem.split("_")[-1] if "_" in stem else ""
    data = {"snapshot": snapshot, **aggregate(rows)}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="in_path", default=DEFAULT_IN)
    ap.add_argument("--out", dest="out_path", default=DEFAULT_OUT)
    args = ap.parse_args()
    data = build(Path(args.in_path), Path(args.out_path))
    print(f"wrote {args.out_path}: {len(data['cells'])} cells, "
          f"{len(data['models'])} models, {len(data['categories'])} categories")


if __name__ == "__main__":
    main()
