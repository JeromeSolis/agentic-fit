from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import RunResult
from .scoring import load_results


def cheapest_per_category(c1_results: list[RunResult]) -> dict[tuple[str, str], str]:
    """Per (category, model), the library with the lowest median total tokens in C1."""
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for r in c1_results:
        groups[(r.category, r.model, r.library)].append(r.total_tokens)
    by_cat_model: dict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    for (cat, model, lib), toks in groups.items():
        by_cat_model[(cat, model)].append((statistics.median(toks), lib))
    return {key: min(cands)[1] for key, cands in by_cat_model.items()}


def _median_tokens(results: list[RunResult]) -> float:
    return statistics.median(r.total_tokens for r in results) if results else 0.0


def _success_rate(results: list[RunResult]) -> float:
    return sum(r.success for r in results) / len(results) if results else 0.0


def token_reduction(treatment: float, control: float) -> float:
    """Fraction fewer tokens treatment uses vs control (positive = treatment cheaper)."""
    return (control - treatment) / control if control else 0.0


def verdict_for(token_reduction: float, success_gain_pp: float) -> str:
    if token_reduction >= 0.25 or success_gain_pp >= 10.0:
        return "GO"
    return "NO-GO"


@dataclass
class ArmComparison:
    token_reduction: float
    success_gain_pp: float
    verdict: str
    chosen_distribution: dict[str, int]


def _treatment_cells(c1: list[RunResult], cheapest: dict[tuple[str, str], str]) -> list[RunResult]:
    return [r for r in c1 if cheapest.get((r.category, r.model)) == r.library]


def _hard_cell(r: RunResult) -> bool:
    # Where success can discriminate: the weaker model (Sonnet saturates at 100%).
    return "haiku" in r.model


def compare(c1: list[RunResult], control: list[RunResult]) -> ArmComparison:
    # Empty inputs would yield a spurious 100% reduction / false GO — fail loudly
    # (e.g. a mismatched or missing result-file path).
    if not c1 or not control:
        raise ValueError("compare requires non-empty c1 and control result sets")
    cheapest = cheapest_per_category(c1)
    treat = _treatment_cells(c1, cheapest)
    tr = token_reduction(_median_tokens(treat), _median_tokens(control))
    hard_treat = [r for r in treat if _hard_cell(r)]
    hard_ctrl = [r for r in control if _hard_cell(r)]
    gain = (_success_rate(hard_treat) - _success_rate(hard_ctrl)) * 100
    dist: dict[str, int] = defaultdict(int)
    for r in control:
        dist[r.chosen_library or "stdlib/none"] += 1
    return ArmComparison(round(tr, 4), round(gain, 1), verdict_for(tr, gain), dict(dist))


def analyze(c1_path: str | Path, unconstrained_path: str | Path,
            constrained_path: str | Path) -> dict:
    c1 = load_results(Path(c1_path))
    return {
        "unconstrained": compare(c1, load_results(Path(unconstrained_path))),  # PRIMARY
        "constrained": compare(c1, load_results(Path(constrained_path))),      # secondary
    }
