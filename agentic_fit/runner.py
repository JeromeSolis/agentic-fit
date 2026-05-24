from __future__ import annotations

from pathlib import Path

from collections.abc import Callable

from .agent import LLMClient, run_agent
from .backends import SandboxBackend
from .budget import run_cost
from .models import RunResult, Task


def run_control_arm(
    client: LLMClient,
    tasks: list[Task],
    model: str,
    reps: int,
    out_path: Path,
    mode: str,
    *,
    backend: SandboxBackend | None = None,
    max_spend: float | None = None,
    on_result: Callable[[int, int, RunResult, float], None] | None = None,
) -> list[RunResult]:
    results: list[RunResult] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(tasks) * reps
    done = 0
    spent = 0.0
    with out_path.open("w") as f:
        for task in tasks:
            for rep in range(reps):
                r = run_agent(client, task, "", model, rep, mode=mode, backend=backend)
                f.write(r.to_json() + "\n")
                f.flush()
                results.append(r)
                done += 1
                spent += run_cost(model, r.input_tokens, r.output_tokens)
                if on_result is not None:
                    on_result(done, total, r, spent)
                if max_spend is not None and spent >= max_spend:
                    return results
    return results


def run_matrix(
    client: LLMClient,
    tasks: list[Task],
    model: str,
    reps: int,
    out_path: Path,
    *,
    backend: SandboxBackend | None = None,
    max_spend: float | None = None,
    on_result: Callable[[int, int, RunResult, float], None] | None = None,
) -> list[RunResult]:
    results: list[RunResult] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = sum(len(t.candidate_libraries) for t in tasks) * reps
    done = 0
    spent = 0.0
    # "w": fresh file per run (flushed per line for crash durability). The
    # harness has no resume logic, so appending would only risk mixing runs.
    with out_path.open("w") as f:
        for task in tasks:
            for library in task.candidate_libraries:
                for rep in range(reps):
                    r = run_agent(client, task, library, model, rep, backend=backend)
                    f.write(r.to_json() + "\n")
                    f.flush()
                    results.append(r)
                    done += 1
                    spent += run_cost(model, r.input_tokens, r.output_tokens)
                    if on_result is not None:
                        on_result(done, total, r, spent)
                    if max_spend is not None and spent >= max_spend:
                        return results
    return results
