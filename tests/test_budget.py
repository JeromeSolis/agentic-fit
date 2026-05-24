from agentic_fit.budget import estimate_matrix_cost, run_cost, total_cost
from agentic_fit.models import RunResult, Task


def test_run_cost_uses_per_model_prices():
    # sonnet: $3/1M in, $15/1M out
    assert round(run_cost("claude-sonnet-4-6", 1_000_000, 1_000_000), 2) == 18.0


def test_total_cost_sums_runs():
    # One run priced on input ($3), one on output ($15) -> exercises both terms.
    rs = [
        RunResult("t", "x", 0, "claude-sonnet-4-6", True, 0, 0, 1, 1_000_000, 0),
        RunResult("t", "x", 1, "claude-sonnet-4-6", True, 0, 0, 1, 0, 1_000_000),
    ]
    assert round(total_cost(rs), 2) == 18.0


def test_estimate_matrix_cost_scales_with_cells():
    task = Task("t", "c", "p", ("a", "b", "c"), "solution.py", "tp")
    est = estimate_matrix_cost([task], "claude-sonnet-4-6", reps=5)
    assert est["cells"] == 15  # 3 libs x 5 reps
    # Pin the value so a change to the default avg token counts is caught.
    assert est["est_cost_usd"] == round(15 * run_cost("claude-sonnet-4-6", 1500, 1200), 2)
