# scripts/build_site_data.py
"""Aggregate cross-lab benchmark results into the JSON the showcase site renders.

    python scripts/build_site_data.py --in results/crosslab_reps3_2026-05-25.jsonl --out site/data.json

Reads one row per (model, library, category, rep) and collapses reps into a
single cell: success_rate, median cost_usd, and rep count n. Median (not mean)
matches the canonical metric in agentic_fit.scoring.score_crosslab, so the site
reproduces the published FINDINGS. Also embeds each category's task prompt and
candidate libraries (read from tasks/<category>/task.yaml) plus a short editorial
summary, so the site can show what each category actually asks the agent to do.

Needs pyyaml, already a project dependency.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path

import yaml

DEFAULT_IN = "results/crosslab_reps3_2026-05-25.jsonl"
DEFAULT_OUT = "site/data.json"
DEFAULT_TASKS = "tasks"

# Short editorial one-liners shown under the active category tab. The full task
# prompt and candidate libraries come from task.yaml; this is the human gloss.
SUMMARIES = {
    "cli_parsing": "Parse two command-line options: a required --name and an integer --count with a default.",
    "data_validation": "Validate and coerce a user record, converting a numeric age and raising on missing or invalid fields.",
    "date_handling": "Parse a human date/time string and return it as an ISO-8601 UTC string, raising on bad input.",
    "http_client": "Perform an HTTP GET, parse the JSON body, return its name field, and raise on a non-200 status.",
    "retrying": "Call a function with up to three retry attempts on failure, re-raising once they are exhausted.",
    "templating": "Render a title and a list of items to a formatted string using a templating library.",
    "yaml_config": "Parse two YAML documents and deep-merge them recursively, with override values winning conflicts.",
}


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


def load_task_meta(tasks_dir: Path, categories: list[str]) -> dict:
    """Per-category task prompt + candidate libraries (from task.yaml) and summary."""
    meta = {}
    for cat in categories:
        spec_file = tasks_dir / cat / "task.yaml"
        prompt, libs = "", []
        if spec_file.exists():
            spec = yaml.safe_load(spec_file.read_text())
            prompt = (spec.get("prompt") or "").strip()
            libs = list(spec.get("candidate_libraries") or [])
        meta[cat] = {"summary": SUMMARIES.get(cat, ""), "prompt": prompt,
                     "candidate_libraries": libs}
    return meta


def build(in_path: Path, out_path: Path, tasks_dir: Path = Path(DEFAULT_TASKS)) -> dict:
    rows = [json.loads(line) for line in in_path.read_text().splitlines() if line.strip()]
    stem = in_path.stem  # e.g. crosslab_reps3_2026-05-25
    snapshot = stem.split("_")[-1] if "_" in stem else ""
    agg = aggregate(rows)
    data = {"snapshot": snapshot, **agg,
            "tasks": load_task_meta(tasks_dir, agg["categories"])}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="in_path", default=DEFAULT_IN)
    ap.add_argument("--out", dest="out_path", default=DEFAULT_OUT)
    ap.add_argument("--tasks", dest="tasks_dir", default=DEFAULT_TASKS)
    args = ap.parse_args()
    data = build(Path(args.in_path), Path(args.out_path), Path(args.tasks_dir))
    print(f"wrote {args.out_path}: {len(data['cells'])} cells, "
          f"{len(data['models'])} models, {len(data['categories'])} categories")


if __name__ == "__main__":
    main()
