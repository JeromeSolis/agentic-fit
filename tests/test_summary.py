from agentic_fit.models import RunResult
from agentic_fit.summary import default_tax, render_default_tax, render_summary, summarize


def _ri(model, category, imports):
    return RunResult("t", "", 0, model, True, 1, 1, 1, input_tokens=0, output_tokens=0,
                     category=category, imports=imports)


def _cr(model, category, library, success, cost):
    # a constrained (assigned-library) result row, with its measured cost
    return RunResult("t", library, 0, model, success, 1, 1, 1, input_tokens=0,
                     output_tokens=0, category=category, cost_usd=cost)


def test_summarize_from_package():
    rows = [_ri("m1", "data_validation", ["pydantic"]),
            _ri("m2", "data_validation", ["dataclasses"]),
            _ri("m3", "data_validation", ["os"])]
    cands = {"data_validation": {"pydantic", "marshmallow", "dataclasses"}}
    s = summarize(rows, cands)
    assert s["n_cells"] == 3
    assert s["community_rate"] == round(1 / 3, 3)
    assert any("data_validation" in line for line in render_summary(s))


def test_default_tax():
    # Constrained costs: tenacity is the best (cheapest reliable); backoff costs 3x.
    # date_handling: dateutil best at 0.004; datetime (the candidate) costs 0.008 (2x).
    constrained = [
        _cr("m1", "retrying", "tenacity", True, 0.002),
        _cr("m1", "retrying", "backoff", True, 0.006),
        _cr("m2", "retrying", "tenacity", True, 0.002),
        _cr("m3", "date_handling", "dateutil", True, 0.004),
        _cr("m3", "date_handling", "datetime", True, 0.008),
    ]
    cands = {"retrying": {"tenacity", "backoff", "stamina"},
             "date_handling": {"datetime", "dateutil", "arrow"}}
    free = [
        _ri("m1", "retrying", ["backoff"]),     # not its best (tenacity) -> tax 3x
        _ri("m2", "retrying", ["tenacity"]),    # picked its best -> match
        _ri("m3", "date_handling", ["datetime"]),  # not best (dateutil) -> tax 2x
        _ri("m1", "date_handling", ["os"]),     # pure stdlib -> off-menu (m1 has no date_handling constrained)
    ]
    t = default_tax(free, cands, constrained)
    assert t["n_match"] == 1                    # m2 retrying
    assert t["n_diff"] == 2                     # m1 retrying, m3 date_handling
    assert t["median_tax"] == 2.5               # median(3.0, 2.0)
    assert t["max_tax"] == 3.0
    assert any("default tax" in line.lower() for line in render_default_tax(t))


def test_render_default_tax_includes_interpretation_and_next_steps():
    t = {"n_match": 42, "n_diff": 37, "n_off_menu": 33,
         "median_tax": 1.22, "mean_tax": 1.3, "max_tax": 2.07}
    lines = render_default_tax(t)
    body = "\n".join(lines)
    assert "default tax" in body.lower()
    # interpretation line
    assert "1.22x default tax" in body
    assert "~22% more" in body
    # Next-steps stanza
    assert "Next:" in body
    assert "agentic-fit results inspect <file>" in body
    assert "agentic-fit run --free --only <id>" in body
    assert "Explorer: https://jeromesolis.github.io/agentic-fit/" in body


def test_render_default_tax_no_interpretation_when_no_tax():
    # When there is nothing taxed (no n_diff), do not print interpretation/Next.
    t = {"n_match": 5, "n_diff": 0, "n_off_menu": 0,
         "median_tax": None, "mean_tax": None, "max_tax": None}
    body = "\n".join(render_default_tax(t))
    assert "Next:" not in body
    assert "default tax" in body.lower()
