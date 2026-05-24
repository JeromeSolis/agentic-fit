from pathlib import Path

from agentic_fit.agent import FakeLLMClient, LLMResponse
from agentic_fit.models import RunResult, Task
from agentic_fit.runner import run_control_arm, run_matrix

FIX = Path(__file__).parent / "fixtures" / "sample_task"
TASK = Task(
    id="sample__add", category="sample",
    prompt="Write add(a, b) returning their sum.",
    candidate_libraries=("math",), solution_filename="solution.py",
    test_path=str(FIX / "test_solution.py"),
)
GOOD = "```python\ndef add(a, b):\n    return a + b\n```"


def test_run_matrix_writes_jsonl_per_run(tmp_path):
    out = tmp_path / "results.jsonl"
    client = FakeLLMClient([LLMResponse(GOOD, 10, 5)] * 2)  # 1 lib x 2 reps
    results = run_matrix(client, [TASK], "fake", reps=2, out_path=out)

    assert len(results) == 2
    lines = [line for line in out.read_text().splitlines() if line.strip()]
    assert len(lines) == 2
    assert RunResult.from_json(lines[0]).success is True
    assert {r.rep for r in results} == {0, 1}


def test_run_matrix_records_category_and_version(tmp_path):
    out = tmp_path / "cat.jsonl"
    client = FakeLLMClient([LLMResponse(GOOD, 10, 5)] * 2)
    results = run_matrix(client, [TASK], "fake", reps=2, out_path=out)
    assert all(r.category == "sample" for r in results)
    assert all(r.version is not None for r in results)


def test_run_matrix_covers_all_libraries(tmp_path):
    out = tmp_path / "multi.jsonl"
    task = Task(
        id="sample__add", category="sample",
        prompt="Write add(a, b) returning their sum.",
        candidate_libraries=("math", "statistics"),
        solution_filename="solution.py",
        test_path=str(FIX / "test_solution.py"),
    )
    client = FakeLLMClient([LLMResponse(GOOD, 1, 1)] * 4)  # 2 libs x 2 reps
    results = run_matrix(client, [task], "fake", reps=2, out_path=out)

    assert len(results) == 4
    assert {r.library for r in results} == {"math", "statistics"}
    lines = [line for line in out.read_text().splitlines() if line.strip()]
    assert len(lines) == 4


def test_run_matrix_aborts_at_spend_cap(tmp_path):
    out = tmp_path / "capped.jsonl"
    # Each run reports 1M input tokens -> $3 on sonnet pricing. After run 1 spent=$3
    # (< $5, continues); after run 2 spent=$6 (>= $5 cap) -> abort with 2 results.
    client = FakeLLMClient([LLMResponse(GOOD, 1_000_000, 0)] * 5)
    results = run_matrix(client, [TASK], "claude-sonnet-4-6", reps=5,
                         out_path=out, max_spend=5.0)
    assert len(results) == 2


def test_run_matrix_invokes_on_result_callback(tmp_path):
    out = tmp_path / "cb.jsonl"
    seen = []
    client = FakeLLMClient([LLMResponse(GOOD, 10, 5)] * 2)
    run_matrix(client, [TASK], "fake", reps=2, out_path=out,
               on_result=lambda done, total, r, spent: seen.append((done, total, r.library)))
    assert seen[0][0] == 1 and seen[0][1] == 2   # (done, total) on first cell
    assert seen[-1][0] == 2                       # done increments to 2


def test_run_control_arm_loops_tasks_and_reps_no_library_dim(tmp_path):
    out = tmp_path / "ctrl.jsonl"
    client = FakeLLMClient([LLMResponse(GOOD, 10, 5)] * 4)  # 1 task x 2 reps (+slack)
    results = run_control_arm(client, [TASK], "fake", reps=2, out_path=out,
                              mode="free_constrained")
    assert len(results) == 2                 # task x rep, NO library dimension
    assert {r.rep for r in results} == {0, 1}
    lines = [ln for ln in out.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2


def test_run_control_arm_aborts_at_spend_cap(tmp_path):
    out = tmp_path / "capped.jsonl"
    # 1M input tokens/run -> $3 sonnet; cap $5 stops after 2 (spent $3 then $6).
    client = FakeLLMClient([LLMResponse(GOOD, 1_000_000, 0)] * 5)
    results = run_control_arm(client, [TASK], "claude-sonnet-4-6", reps=5, out_path=out,
                              mode="free_constrained", max_spend=5.0)
    assert len(results) == 2
