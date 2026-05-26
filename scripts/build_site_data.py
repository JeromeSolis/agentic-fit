# scripts/build_site_data.py
"""Aggregate cross-lab benchmark results into the JSON the showcase site renders.

    python scripts/build_site_data.py --in results/crosslab_reps3_2026-05-25.jsonl --out site/data.json

Reads one row per (model, library, category, rep) and collapses reps into a
single cell: success_rate, mean cost_usd, and rep count n. Pure stdlib so the
site build needs no extra dependencies.
"""
from __future__ import annotations

import argparse
import collections
import json
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
            "cost_usd": sum(r["cost_usd"] for r in rs) / n,
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
