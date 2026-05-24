from agentic_fit.models import RunResult
from agentic_fit.novelty import (
    analyze,
    cross_model_inversions,
    pairwise_concordance,
    verdict_for,
)


def test_pairwise_concordance_counts_and_rate():
    # One category, one model, 3 libs. Cost order a<b<c; popularity a>b>c -> all concordant.
    cost_by_model = {"m1": {("cat", "a"): 100, ("cat", "b"): 200, ("cat", "c"): 300}}
    popularity = {"a": 30, "b": 20, "c": 10}
    res = pairwise_concordance(cost_by_model, popularity)
    assert (res.concordant, res.discordant, res.excluded_ties) == (3, 0, 0)
    assert res.rate == 1.0


def test_pairwise_concordance_discordant_and_ties():
    # cost a<b ; popularity a<b -> cheaper(a) is LESS popular -> discordant.
    # b vs c: equal popularity -> tie excluded.
    cost_by_model = {"m1": {("cat", "a"): 100, ("cat", "b"): 200, ("cat", "c"): 300}}
    popularity = {"a": 10, "b": 20, "c": 20}
    res = pairwise_concordance(cost_by_model, popularity)
    # pairs: (a,b) discordant; (a,c) a cheaper & a less popular -> discordant; (b,c) tie
    assert (res.concordant, res.discordant, res.excluded_ties) == (0, 2, 1)
    assert res.rate == 0.0


def test_stdlib_like_library_absent_from_popularity_is_skipped():
    cost_by_model = {"m1": {("cat", "a"): 100, ("cat", "std"): 50}}
    popularity = {"a": 5}  # "std" not in popularity -> excluded from pairs
    res = pairwise_concordance(cost_by_model, popularity)
    assert (res.concordant, res.discordant, res.excluded_ties) == (0, 0, 0)
    assert res.rate is None  # no non-tie pairs -> undefined rate


def test_pairwise_concordance_pools_across_categories():
    # Two categories in one model: one concordant, one discordant -> pooled rate 0.5.
    cost_by_model = {
        "m1": {
            ("c1", "a"): 100, ("c1", "b"): 200,  # a cheaper
            ("c2", "x"): 200, ("c2", "y"): 100,  # y cheaper
        }
    }
    popularity = {"a": 50, "b": 10, "x": 50, "y": 10}  # a and x are more popular
    res = pairwise_concordance(cost_by_model, popularity)
    # c1: cheaper a is more popular -> concordant; c2: cheaper y is less popular -> discordant
    assert (res.concordant, res.discordant) == (1, 1)
    assert res.rate == 0.5


def test_cross_model_inversions_none_when_consistent():
    cost_by_model = {
        "m1": {("cat", "a"): 100, ("cat", "b"): 200},  # a cheaper
        "m2": {("cat", "a"): 150, ("cat", "b"): 300},  # a still cheaper
    }
    popularity = {"a": 30, "b": 10}
    res = pairwise_concordance(cost_by_model, popularity)
    assert cross_model_inversions(res.pairs) == []


def test_cross_model_inversions_detected():
    # Same pair {a,b} in "cat": concordant under m1, discordant under m2 -> 1 inversion.
    cost_by_model = {
        "m1": {("cat", "a"): 100, ("cat", "b"): 200},  # a cheaper
        "m2": {("cat", "a"): 200, ("cat", "b"): 100},  # b cheaper (cost flipped)
    }
    popularity = {"a": 30, "b": 10}  # a more popular (fixed)
    res = pairwise_concordance(cost_by_model, popularity)
    inv = cross_model_inversions(res.pairs)
    assert inv == [("cat", frozenset({"a", "b"}))]


def test_verdict_boundaries():
    assert verdict_for(0.65, 0) == "GO"
    assert verdict_for(0.64, 0) == "GO"
    assert verdict_for(0.85, 0) == "NO-GO"
    assert verdict_for(0.86, 0) == "NO-GO"
    assert verdict_for(0.70, 3) == "AMBIGUOUS->GO"
    assert verdict_for(0.70, 2) == "AMBIGUOUS->NO-GO"
    assert verdict_for(None, 0) == "INSUFFICIENT_DATA"


def test_analyze_end_to_end_on_synthetic_runresults():
    def rr(model, category, library, tokens):
        return RunResult("t", library, 0, model, True, 1, 1, 1,
                         input_tokens=tokens, output_tokens=0, category=category)

    sonnet = [rr("sonnet", "cat", "a", 100), rr("sonnet", "cat", "b", 300)]
    haiku = [rr("haiku", "cat", "a", 300), rr("haiku", "cat", "b", 100)]
    popularity = {"a": 50, "b": 10}  # a more popular
    report = analyze({"sonnet": sonnet, "haiku": haiku}, popularity)
    # sonnet: a cheaper & more popular -> concordant; haiku: b cheaper but a more popular -> discordant
    assert report.concordant == 1 and report.discordant == 1
    assert report.rate == 0.5
    assert report.n_inversions == 1
    assert report.verdict == "GO"  # rate 0.5 <= 0.65
