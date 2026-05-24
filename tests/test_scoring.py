from agentic_fit.models import RunResult
from agentic_fit.scoring import (
    category_variance_summary,
    score_categories,
    score_cells,
    variance_summary,
)


def _r(task_id, library, success, tokens):
    return RunResult(task_id, library, 0, "m", success, 0, 0, 1,
                     input_tokens=tokens, output_tokens=0)


def test_score_cells_aggregates_success_and_median_tokens():
    results = [
        _r("t1", "fast", True, 100), _r("t1", "fast", True, 200),
        _r("t1", "slow", False, 500), _r("t1", "slow", True, 700),
    ]
    cells = {(c.task_id, c.library): c for c in score_cells(results)}
    assert cells[("t1", "fast")].success_rate == 1.0
    assert cells[("t1", "fast")].median_tokens == 150
    assert cells[("t1", "slow")].success_rate == 0.5


def test_variance_summary_reports_spread():
    results = [
        _r("t1", "fast", True, 100), _r("t1", "fast", True, 100),
        _r("t1", "slow", False, 800), _r("t1", "slow", False, 800),
    ]
    summary = variance_summary(score_cells(results))
    assert summary["t1"]["best"][0] == "fast"
    assert summary["t1"]["worst"][0] == "slow"
    assert summary["t1"]["success_spread_pp"] == 100.0


def test_variance_summary_token_ratio_is_cost_spread():
    results = [
        _r("t1", "cheap", True, 100), _r("t1", "cheap", True, 100),
        _r("t1", "pricey", True, 400), _r("t1", "pricey", True, 400),
    ]
    summary = variance_summary(score_cells(results))
    assert summary["t1"]["token_ratio"] == 4.0


def test_variance_summary_tiebreak_prefers_cheaper_best():
    results = [
        _r("t1", "lean", True, 100),
        _r("t1", "heavy", True, 900),
    ]
    summary = variance_summary(score_cells(results))
    assert summary["t1"]["best"][0] == "lean"
    assert summary["t1"]["worst"][0] == "heavy"


def test_empty_inputs():
    assert score_cells([]) == []
    assert variance_summary([]) == {}
    assert score_categories([]) == []
    assert category_variance_summary([]) == {}


def _rc(category, library, success, tokens):
    return RunResult("t", library, 0, "m", success, 0, 0, 1,
                     input_tokens=tokens, output_tokens=0, category=category)


def test_score_categories_rolls_up_multiple_tasks():
    results = [
        _rc("http", "requests", True, 100), _rc("http", "requests", True, 300),
        _rc("http", "urllib3", True, 900),
    ]
    cells = {(c.category, c.library): c for c in score_categories(results)}
    assert cells[("http", "requests")].median_tokens == 200
    assert cells[("http", "requests")].success_rate == 1.0
    assert cells[("http", "urllib3")].median_tokens == 900


def test_category_variance_summary_reports_cost_spread():
    results = [
        _rc("http", "requests", True, 100), _rc("http", "urllib3", True, 400),
    ]
    summary = category_variance_summary(score_categories(results))
    assert summary["http"]["token_ratio"] == 4.0
    assert summary["http"]["best"][0] == "requests"
    assert summary["http"]["worst"][0] == "urllib3"


def test_category_variance_summary_success_spread():
    results = [
        _rc("http", "requests", True, 100), _rc("http", "requests", True, 100),
        _rc("http", "urllib3", False, 100), _rc("http", "urllib3", False, 100),
    ]
    summary = category_variance_summary(score_categories(results))
    assert summary["http"]["success_spread_pp"] == 100.0
    assert summary["http"]["best"][0] == "requests"
    assert summary["http"]["worst"][0] == "urllib3"
