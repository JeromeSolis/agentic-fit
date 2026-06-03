"""Summarize a free-choice run: what library each model picks when free.

Pure interpretation over captured results; used by the `summarize` CLI command
and by `run`'s auto-summary.
"""
from __future__ import annotations

import collections

from agentic_fit.picks import effective_pick, kind
from agentic_fit.venvs import STDLIB_ALL

STDLIB_LABEL = "<stdlib>"


def _row_pick(r, candidate_set) -> str | None:
    return effective_pick(r.imports, candidate_set, STDLIB_ALL, fallback=r.chosen_library)


def _modal_pick(rows, candidate_set) -> str:
    counts = collections.Counter((_row_pick(r, candidate_set) or STDLIB_LABEL) for r in rows)
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def summarize(rows, candidate_sets: dict[str, set], constrained_best: dict | None = None) -> dict:
    by_cell: dict[tuple, list] = collections.defaultdict(list)
    for r in rows:
        by_cell[(r.model, r.category)].append(r)

    picks = {key: _modal_pick(rs, candidate_sets.get(key[1], set())) for key, rs in by_cell.items()}
    by_category: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    in_set = out_set = stdlib = 0
    for (model, cat), pick in picks.items():
        by_category[cat][pick] += 1
        if pick == STDLIB_LABEL:
            stdlib += 1
        elif pick in candidate_sets.get(cat, set()):
            in_set += 1
        else:
            out_set += 1
    n = len(picks)
    builtin = sum(1 for p in picks.values()
                  if kind(None if p == STDLIB_LABEL else p, STDLIB_ALL) == "builtin")
    community = n - builtin

    agreement_rate = None
    if constrained_best:
        comparable = matches = 0
        for key, pick in picks.items():
            if key in constrained_best:
                comparable += 1
                if pick == constrained_best[key]:
                    matches += 1
        agreement_rate = (matches / comparable) if comparable else None

    return {
        "by_category": {c: dict(by_category[c]) for c in sorted(by_category)},
        "out_of_set_rate": round(out_set / n, 3) if n else 0.0,
        "stdlib_rate": round(stdlib / n, 3) if n else 0.0,
        "builtin_rate": round(builtin / n, 3) if n else 0.0,
        "community_rate": round(community / n, 3) if n else 0.0,
        "agreement_rate": round(agreement_rate, 3) if agreement_rate is not None else None,
        "n_cells": n,
    }


def default_tax(rows, candidate_sets: dict[str, set], constrained_rows) -> dict:
    """How much more a model's free pick costs than its own best library.

    For each (model, category) cell where the model has a measured best library
    (from the constrained run) and freely picked a *priced* candidate, the tax is
    constrained_cost(free pick) / constrained_cost(best). Cells where the free pick
    is the standard library, a compound, or any library we did not price are counted
    "off-menu" (no comparable cost). Cells with no constrained best are skipped.
    """
    import statistics

    from agentic_fit.scoring import crosslab_best, score_crosslab

    scores = score_crosslab(constrained_rows)
    cost = {(s.model, s.category, s.library): s.median_cost_usd for s in scores}
    best = crosslab_best(scores)  # {(model, category): CrossLabScore}

    by_cell: dict[tuple, list] = collections.defaultdict(list)
    for r in rows:
        by_cell[(r.model, r.category)].append(r)

    ratios = []
    n_match = n_off_menu = 0
    for key, rs in by_cell.items():
        if key not in best:
            continue  # no constrained measurement for this cell
        pick = _modal_pick(rs, candidate_sets.get(key[1], set()))
        if pick == best[key].library:
            n_match += 1
            continue
        free_cost = cost.get((key[0], key[1], pick))
        best_cost = best[key].median_cost_usd
        if free_cost is None or best_cost <= 0:
            n_off_menu += 1  # stdlib / compound / unpriced library
            continue
        ratios.append(free_cost / best_cost)

    return {
        "n_match": n_match,
        "n_diff": len(ratios),
        "n_off_menu": n_off_menu,
        "median_tax": round(statistics.median(ratios), 2) if ratios else None,
        "mean_tax": round(statistics.mean(ratios), 2) if ratios else None,
        "max_tax": round(max(ratios), 2) if ratios else None,
    }


def render_default_tax(t: dict) -> list[str]:
    total = t["n_match"] + t["n_diff"] + t["n_off_menu"]
    lines = [f"default tax (free pick vs each model's best library) · {total} comparable cells"]
    lines.append(f"  picked their best library: {t['n_match']}/{total}")
    if t["median_tax"] is not None:
        lines.append(f"  picked a costlier measured library in {t['n_diff']} cells: "
                     f"median {t['median_tax']}x, mean {t['mean_tax']}x, max {t['max_tax']}x more")
    if t["n_off_menu"]:
        lines.append(f"  went off-menu (stdlib / unpriced) in {t['n_off_menu']} cells: no cost comparison")
    if t["median_tax"] is not None:
        pct = round((t["median_tax"] - 1) * 100)
        lines.append("")
        lines.append(f"A median {t['median_tax']}x default tax means models pay ~{pct}% more on average "
                     "by not picking their cheapest reliable library.")
        lines.append("")
        lines.append("Next:")
        lines.append("  agentic-fit results inspect <file>         re-render this summary")
        lines.append("  agentic-fit run --free --only <id>         drill into a specific model")
        lines.append("  Explorer: https://jeromesolis.github.io/agentic-fit/")
    return lines


def render_summary(s: dict) -> list[str]:
    lines = [f"free-choice picks · {s['n_cells']} (model, category) cells"]
    for cat, dist in s["by_category"].items():
        parts = " · ".join(f"{lib} x{cnt}" for lib, cnt in
                           sorted(dist.items(), key=lambda kv: (-kv[1], kv[0])))
        lines.append(f"  {cat:16s} {parts}")
    lines.append(f"out-of-set rate: {s['out_of_set_rate']:.0%}  ·  stdlib rate: {s['stdlib_rate']:.0%}")
    lines.append(f"community libraries: {s['community_rate']:.0%}  ·  built-in: {s['builtin_rate']:.0%}")
    if s["agreement_rate"] is not None:
        lines.append(f"agreement with constrained best: {s['agreement_rate']:.0%}")
    return lines
