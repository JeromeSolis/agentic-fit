from __future__ import annotations

import pytest

from agentic_fit.actionability import (
    cheapest_per_category,
    compare,
    token_reduction,
    verdict_for,
)
from agentic_fit.models import RunResult


def _r(category, library, model, success, tokens, chosen=None):
    return RunResult("t", library, 0, model, success, 0, 0, 1,
                     input_tokens=tokens, output_tokens=0, category=category,
                     chosen_library=chosen)


def test_cheapest_per_category_picks_min_median_tokens():
    c1 = [
        _r("http", "requests", "sonnet", True, 100),
        _r("http", "urllib3", "sonnet", True, 400),
        _r("http", "requests", "haiku", True, 500),
        _r("http", "urllib3", "haiku", True, 200),
    ]
    cheapest = cheapest_per_category(c1)
    assert cheapest[("http", "sonnet")] == "requests"
    assert cheapest[("http", "haiku")] == "urllib3"   # model-specific


def test_token_reduction_is_fraction_fewer():
    assert token_reduction(treatment=100.0, control=200.0) == 0.5
    assert token_reduction(treatment=200.0, control=100.0) == -1.0


def test_verdict_boundaries():
    assert verdict_for(token_reduction=0.25, success_gain_pp=0.0) == "GO"
    assert verdict_for(token_reduction=0.24, success_gain_pp=0.0) == "NO-GO"
    assert verdict_for(token_reduction=0.0, success_gain_pp=10.0) == "GO"
    assert verdict_for(token_reduction=0.0, success_gain_pp=9.0) == "NO-GO"


def test_compare_primary_go_on_token_reduction():
    c1 = [_r("http", "requests", "sonnet", True, 100),  # cheapest -> treatment
          _r("http", "urllib3", "sonnet", True, 400)]
    control = [_r("http", "urllib3", "sonnet", True, 400, chosen="urllib3")]
    cmp = compare(c1, control)
    assert cmp.token_reduction == 0.75      # 100 vs 400
    assert cmp.verdict == "GO"
    assert cmp.chosen_distribution == {"urllib3": 1}


def test_compare_no_go_when_free_agent_already_picks_cheapest():
    # Honest null: the free agent picks the same cheap library -> no token gain -> NO-GO.
    c1 = [_r("http", "requests", "sonnet", True, 400),  # cheapest -> treatment
          _r("http", "urllib3", "sonnet", True, 500)]
    control = [_r("http", "requests", "sonnet", True, 400, chosen="requests")]
    cmp = compare(c1, control)
    assert cmp.token_reduction == 0.0
    assert cmp.verdict == "NO-GO"
    assert cmp.chosen_distribution == {"requests": 1}


def test_compare_rejects_empty_inputs():
    with pytest.raises(ValueError):
        compare([], [_r("http", "requests", "sonnet", True, 100, chosen="requests")])
