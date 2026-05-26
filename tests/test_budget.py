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


def test_register_prices_adds_to_table():
    from agentic_fit import budget
    budget.register_prices([("test/model-x", 2.0, 8.0)])
    assert budget.run_cost("test/model-x", 1_000_000, 1_000_000) == 10.0


def test_estimate_crosslab_cost_totals():
    from agentic_fit import budget
    from agentic_fit.models import Task
    budget.register_prices([("a/model", 1.0, 1.0), ("b/model", 2.0, 2.0)])
    tasks = [Task("t__1", "t", "p", ("x", "y"), "solution.py", "tp")]  # 2 libs
    out = budget.estimate_crosslab_cost(
        tasks, [("a/model", "openrouter"), ("b/model", "openrouter")],
        reps=3, avg_input=1_000_000, avg_output=0,
    )
    # cells = 2 libs * 3 reps = 6; a/model: 6 * $1 = $6; b/model: 6 * $2 = $12
    assert out["cells_per_model"] == 6
    assert out["total_usd"] == 18.0
    assert {m["model"] for m in out["per_model"]} == {"a/model", "b/model"}
