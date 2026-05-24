from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from .models import RunResult
from .popularity import load_popularity
from .scoring import load_results, score_categories


@dataclass
class Pair:
    category: str
    model: str
    cheaper: str
    costlier: str
    concordant: bool  # the cheaper-for-agent library is also the more-downloaded one


@dataclass
class ConcordanceResult:
    concordant: int
    discordant: int
    excluded_ties: int
    rate: float | None
    pairs: list[Pair]


@dataclass
class NoveltyReport:
    concordant: int
    discordant: int
    excluded_ties: int
    rate: float | None
    n_inversions: int
    verdict: str
    pairs: list[Pair]
    inversions: list[tuple]


def median_cost_by_category(results: list[RunResult]) -> dict[tuple[str, str], float]:
    # Cost scalar = median total tokens across ALL reps (failures included), matching
    # the C1 headline metric; a failing library's retries inflate it, which is intended.
    return {(c.category, c.library): c.median_tokens for c in score_categories(results)}


def pairwise_concordance(cost_by_model: dict, popularity: dict[str, int]) -> ConcordanceResult:
    pairs: list[Pair] = []
    concordant = discordant = ties = 0
    for model, costs in cost_by_model.items():
        by_cat: dict[str, dict[str, float]] = defaultdict(dict)
        for (cat, lib), med in costs.items():
            if lib in popularity:  # third-party only; stdlib never appears in popularity
                by_cat[cat][lib] = med
        for cat, libs in by_cat.items():
            for a, b in combinations(sorted(libs), 2):
                ca, cb, pa, pb = libs[a], libs[b], popularity[a], popularity[b]
                if ca == cb or pa == pb:
                    ties += 1
                    continue
                cheaper, costlier = (a, b) if ca < cb else (b, a)
                more_popular = a if pa > pb else b
                conc = cheaper == more_popular
                pairs.append(Pair(cat, model, cheaper, costlier, conc))
                concordant += conc
                discordant += not conc
    total = concordant + discordant
    rate = concordant / total if total else None
    return ConcordanceResult(concordant, discordant, ties, rate, pairs)


def cross_model_inversions(pairs: list[Pair]) -> list[tuple]:
    by_key: dict[tuple, dict[str, bool]] = defaultdict(dict)
    for p in pairs:
        by_key[(p.category, frozenset({p.cheaper, p.costlier}))][p.model] = p.concordant
    return [key for key, by_model in by_key.items()
            if len(by_model) >= 2 and len(set(by_model.values())) > 1]


def verdict_for(rate: float | None, n_inversions: int) -> str:
    if rate is None:
        return "INSUFFICIENT_DATA"
    if rate <= 0.65:
        return "GO"
    if rate >= 0.85:
        return "NO-GO"
    return "AMBIGUOUS->GO" if n_inversions >= 3 else "AMBIGUOUS->NO-GO"


def analyze(results_by_model: dict[str, list[RunResult]], popularity: dict[str, int]) -> NoveltyReport:
    cost_by_model = {m: median_cost_by_category(rs) for m, rs in results_by_model.items()}
    conc = pairwise_concordance(cost_by_model, popularity)
    inv = cross_model_inversions(conc.pairs)
    return NoveltyReport(conc.concordant, conc.discordant, conc.excluded_ties,
                         conc.rate, len(inv), verdict_for(conc.rate, len(inv)),
                         conc.pairs, inv)


def main() -> None:
    results_by_model = {
        "sonnet": load_results(Path("results/phase2_c1.jsonl")),
        "haiku": load_results(Path("results/phase2_c1_haiku.jsonl")),
    }
    import_names = sorted({r.library for rs in results_by_model.values() for r in rs})
    popularity = load_popularity(import_names, Path("data/pypi_downloads.json"), pause=1.0)

    report = analyze(results_by_model, popularity)
    rate_str = f"{report.rate:.0%}" if report.rate is not None else "N/A"
    print("\n=== C2 novelty: pooled concordance ===")
    print(f"concordant={report.concordant} discordant={report.discordant} "
          f"ties_excluded={report.excluded_ties} rate={rate_str} "
          f"inversions={report.n_inversions} -> {report.verdict}")
    for p in sorted(report.pairs, key=lambda x: (x.category, x.model)):
        mark = "ok " if p.concordant else "DISC"
        print(f"  [{mark}] {p.category}/{p.model}: cheaper={p.cheaper} costlier={p.costlier}")
    if report.inversions:
        print("cross-model inversions:")
        for cat, libs in report.inversions:
            print(f"  {cat}: {set(libs)}")


if __name__ == "__main__":
    main()
