from __future__ import annotations

from .models import RunResult, Task

# Approximate USD per 1M tokens (input, output). Estimates for budgeting only.
PRICES = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "fake": (0.0, 0.0),
}
# Fail high on an unknown model: use the priciest known rate so an unrecognized
# model over-estimates cost and trips the spend cap early rather than overspending.
_DEFAULT_PRICE = (3.0, 15.0)


def run_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p_in, p_out = PRICES.get(model, _DEFAULT_PRICE)
    return input_tokens / 1_000_000 * p_in + output_tokens / 1_000_000 * p_out


def total_cost(results: list[RunResult]) -> float:
    return sum(run_cost(r.model, r.input_tokens, r.output_tokens) for r in results)


def estimate_matrix_cost(
    tasks: list[Task], model: str, reps: int,
    avg_input: int = 1500, avg_output: int = 1200,
) -> dict:
    cells = sum(len(t.candidate_libraries) for t in tasks) * reps
    cost = cells * run_cost(model, avg_input, avg_output)
    return {"cells": cells, "est_cost_usd": round(cost, 2)}
