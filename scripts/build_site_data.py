# scripts/build_site_data.py
"""Aggregate cross-lab benchmark results into the JSON the showcase site renders.

    python scripts/build_site_data.py --in results/crosslab_assigned_reps3_2026-05-25.jsonl --out site/data.json

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
import sys
from pathlib import Path

import yaml

from agentic_fit.loader import load_tasks
from agentic_fit.scoring import crosslab_best, load_results, score_crosslab
from agentic_fit.summary import _modal_pick

DEFAULT_IN = "results/crosslab_assigned_reps3_2026-05-25.jsonl"
DEFAULT_FREE_IN = "results/crosslab_free_reps3_2026-05-27.jsonl"
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


def build_free_entries(constrained_path: Path, free_path: Path, tasks_dir: Path) -> list[dict]:
    """One entry per (model, category) free-run cell.

    Tax semantics:
      - In-set pick: tax = constrained_median(pick) / constrained_median(best).
        This is the same library tax the site already plots, so the free-arm
        view stays comparable to the constrained-arm view.
      - Off-menu pick (stdlib, compound, or any library outside the candidate
        set): tax = free_median_cost / best_cost, with tax_is_soft=True.
        Soft because we have no matched constrained baseline for that library,
        so the comparison apples-to-pears across the candidate-set boundary.
    """
    constrained_results = load_results(constrained_path)
    free_results = load_results(free_path)

    tasks = load_tasks(tasks_dir)
    candidate_libraries: dict[str, set[str]] = {}
    for t in tasks:
        candidate_libraries.setdefault(t.category, set()).update(t.candidate_libraries)

    crosslab_scores = score_crosslab(constrained_results)
    best_map = crosslab_best(crosslab_scores)
    constrained_cost: dict[tuple[str, str, str], float] = {
        (s.model, s.category, s.library): s.median_cost_usd for s in crosslab_scores
    }

    free_groups: dict[tuple[str, str], list] = collections.defaultdict(list)
    for r in free_results:
        free_groups[(r.model, r.category)].append(r)

    entries: list[dict] = []
    for (model, category), rs in sorted(free_groups.items()):
        candidates = candidate_libraries.get(category, set())
        pick = _modal_pick(rs, candidates)
        best = best_map.get((model, category))
        if best is None:
            print(f"warning: no constrained best for ({model}, {category}); skipping",
                  file=sys.stderr)
            continue
        free_costs = [r.cost_usd for r in rs if r.cost_usd is not None]
        free_cost = statistics.median(free_costs) if free_costs else 0.0
        pick_off_menu = pick not in candidates or (model, category, pick) not in constrained_cost
        if pick_off_menu:
            tax = free_cost / best.median_cost_usd if best.median_cost_usd else 0.0
            tax_is_soft = True
        else:
            tax = constrained_cost[(model, category, pick)] / best.median_cost_usd if best.median_cost_usd else 0.0
            tax_is_soft = False
        entries.append({
            "model": model,
            "category": category,
            "pick": pick,
            "pick_off_menu": pick_off_menu,
            "best_library": best.library,
            "tax": tax,
            "tax_is_soft": tax_is_soft,
            "free_cost_usd": free_cost,
            "best_cost_usd": best.median_cost_usd,
            "n": len(rs),
        })
    return entries


def build(in_path: Path, out_path: Path, tasks_dir: Path = Path(DEFAULT_TASKS),
          free_path: Path | None = None) -> dict:
    rows = [json.loads(line) for line in in_path.read_text().splitlines() if line.strip()]
    stem = in_path.stem  # e.g. crosslab_assigned_reps3_2026-05-25
    snapshot = stem.split("_")[-1] if "_" in stem else ""
    agg = aggregate(rows)
    data = {"snapshot": snapshot, **agg,
            "tasks": load_task_meta(tasks_dir, agg["categories"])}
    if free_path is not None:
        data["free"] = build_free_entries(in_path, free_path, tasks_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="in_path", default=DEFAULT_IN)
    ap.add_argument("--free-in", dest="free_path", default=DEFAULT_FREE_IN)
    ap.add_argument("--out", dest="out_path", default=DEFAULT_OUT)
    ap.add_argument("--tasks", dest="tasks_dir", default=DEFAULT_TASKS)
    args = ap.parse_args()
    free_path = Path(args.free_path) if args.free_path else None
    data = build(Path(args.in_path), Path(args.out_path), Path(args.tasks_dir),
                 free_path=free_path)
    free_n = len(data.get("free", []))
    print(f"wrote {args.out_path}: {len(data['cells'])} cells, "
          f"{free_n} free entries, "
          f"{len(data['models'])} models, {len(data['categories'])} categories")


if __name__ == "__main__":
    main()
