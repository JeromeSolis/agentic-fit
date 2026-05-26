from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import RunResult


@dataclass
class CellScore:
    task_id: str
    library: str
    n: int
    success_rate: float
    median_tokens: float


def load_results(path: Path) -> list[RunResult]:
    return [RunResult.from_json(l) for l in path.read_text().splitlines() if l.strip()]


def score_cells(results: list[RunResult]) -> list[CellScore]:
    groups: dict[tuple[str, str], list[RunResult]] = defaultdict(list)
    for r in results:
        groups[(r.task_id, r.library)].append(r)
    scores: list[CellScore] = []
    for (task_id, library), rs in sorted(groups.items()):
        success_rate = sum(r.success for r in rs) / len(rs)
        median_tokens = statistics.median(r.total_tokens for r in rs)
        scores.append(CellScore(task_id, library, len(rs), success_rate, median_tokens))
    return scores


def variance_summary(scores: list[CellScore]) -> dict:
    by_task: dict[str, list[CellScore]] = defaultdict(list)
    for s in scores:
        by_task[s.task_id].append(s)
    summary: dict[str, dict] = {}
    for task_id, cells in by_task.items():
        best = max(cells, key=lambda c: (c.success_rate, -c.median_tokens))
        worst = min(cells, key=lambda c: (c.success_rate, -c.median_tokens))
        token_values = [c.median_tokens for c in cells]
        lo, hi = min(token_values), max(token_values)
        summary[task_id] = {
            "best": (best.library, best.success_rate, best.median_tokens),
            "worst": (worst.library, worst.success_rate, worst.median_tokens),
            "success_spread_pp": round((best.success_rate - worst.success_rate) * 100, 1),
            # Token-cost spread across ALL libraries (>= 1), independent of the
            # success-based best/worst ranking: costliest median / cheapest median.
            "token_ratio": round(hi / lo, 2) if lo else None,
        }
    return summary


@dataclass
class CategoryScore:
    category: str
    library: str
    n: int
    success_rate: float
    median_tokens: float


def score_categories(results: list[RunResult]) -> list[CategoryScore]:
    groups: dict[tuple[str, str], list[RunResult]] = defaultdict(list)
    for r in results:
        groups[(r.category, r.library)].append(r)
    scores: list[CategoryScore] = []
    for (category, library), rs in sorted(groups.items()):
        success_rate = sum(r.success for r in rs) / len(rs)
        median_tokens = statistics.median(r.total_tokens for r in rs)
        scores.append(CategoryScore(category, library, len(rs), success_rate, median_tokens))
    return scores


def category_variance_summary(scores: list[CategoryScore]) -> dict:
    by_category: dict[str, list[CategoryScore]] = defaultdict(list)
    for s in scores:
        by_category[s.category].append(s)
    summary: dict[str, dict] = {}
    for category, cells in by_category.items():
        best = max(cells, key=lambda c: (c.success_rate, -c.median_tokens))
        worst = min(cells, key=lambda c: (c.success_rate, -c.median_tokens))
        token_values = [c.median_tokens for c in cells]
        lo, hi = min(token_values), max(token_values)
        summary[category] = {
            "best": (best.library, best.success_rate, best.median_tokens),
            "worst": (worst.library, worst.success_rate, worst.median_tokens),
            "success_spread_pp": round((best.success_rate - worst.success_rate) * 100, 1),
            # Token-cost spread across ALL libraries (>= 1), independent of the
            # success-based best/worst ranking: costliest median / cheapest median.
            "token_ratio": round(hi / lo, 2) if lo else None,
        }
    return summary


@dataclass
class CrossLabScore:
    model: str
    category: str
    library: str
    n: int
    success_rate: float
    median_cost_usd: float
    median_tokens: float


def score_crosslab(results: list[RunResult]) -> list[CrossLabScore]:
    groups: dict[tuple[str, str, str], list[RunResult]] = defaultdict(list)
    for r in results:
        groups[(r.model, r.category, r.library)].append(r)
    scores: list[CrossLabScore] = []
    for (model, category, library), rs in sorted(groups.items()):
        success_rate = sum(r.success for r in rs) / len(rs)
        costs = [r.cost_usd for r in rs if r.cost_usd is not None]
        median_cost = statistics.median(costs) if costs else 0.0
        median_tokens = statistics.median(r.total_tokens for r in rs)
        scores.append(CrossLabScore(model, category, library, len(rs),
                                    success_rate, median_cost, median_tokens))
    return scores


def crosslab_best(scores: list[CrossLabScore]) -> dict[tuple[str, str], CrossLabScore]:
    """Best library per (model, category): highest success rate, then lowest cost."""
    by_key: dict[tuple[str, str], list[CrossLabScore]] = defaultdict(list)
    for s in scores:
        by_key[(s.model, s.category)].append(s)
    return {
        key: max(cells, key=lambda c: (c.success_rate, -c.median_cost_usd))
        for key, cells in by_key.items()
    }
