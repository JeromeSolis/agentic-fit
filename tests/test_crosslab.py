from pathlib import Path

from agentic_fit import crosslab, agent, budget
from agentic_fit.agent import FakeLLMClient, LLMResponse
from agentic_fit.models import Task, RunResult
from agentic_fit.sandbox import SandboxResult

GOOD = "```python\ndef add(a, b):\n    return a + b\n```"
FIX = Path(__file__).parent / "fixtures" / "sample_task"
TASK = Task("sample__add", "sample", "add", ("math",), "solution.py", str(FIX / "test_solution.py"))


class _OkBackend:
    def run(self, job):
        return SandboxResult(True, 1, 1, "", "", status="passed", version="x")


def _patch_clients(monkeypatch):
    # Every model gets a fresh FakeLLMClient that always returns GOOD.
    monkeypatch.setattr(agent, "make_client",
                        lambda provider, model: FakeLLMClient([LLMResponse(GOOD, 1000, 0)] * 50))
    monkeypatch.setattr(crosslab, "make_client",
                        lambda provider, model: FakeLLMClient([LLMResponse(GOOD, 1000, 0)] * 50))


def test_runs_all_models_into_one_file(tmp_path, monkeypatch):
    _patch_clients(monkeypatch)
    budget.register_prices([("m/a", 1.0, 0.0), ("m/b", 1.0, 0.0)])
    out = tmp_path / "crosslab.jsonl"
    res = crosslab.run_crosslab([("m/a", "openrouter"), ("m/b", "openrouter")],
                                [TASK], reps=2, out_path=out, backend=_OkBackend(), max_spend=999.0)
    rows = [RunResult.from_json(l) for l in out.read_text().splitlines() if l.strip()]
    assert {r.model for r in rows} == {"m/a", "m/b"}
    assert all(r.provider == "openrouter" for r in rows)
    assert len(rows) == 4  # 2 models * 1 lib * 2 reps
    assert res["aborted"] is False
    assert res["cost_usd"] == round(sum(r.cost_usd or 0 for r in rows), 4)  # single cost figure


def test_complete_models_on_cap_stops_at_boundary(tmp_path, monkeypatch):
    _patch_clients(monkeypatch)
    # Cap-estimate uses AVG tokens (1500 in): est/model = 2 cells * $0.0015 = $0.003.
    # Actual runs use 1000 input tokens: actual/model = 2 cells * $0.001 = $0.002.
    budget.register_prices([("m/a", 1.0, 0.0), ("m/b", 1.0, 0.0)])
    out = tmp_path / "crosslab.jsonl"
    spent = crosslab.run_crosslab(
        [("m/a", "openrouter"), ("m/b", "openrouter")],
        [TASK], reps=2, out_path=out, backend=_OkBackend(), max_spend=0.004,
    )
    rows = [RunResult.from_json(l) for l in out.read_text().splitlines() if l.strip()]
    # m/a: est 0.003 <= cap 0.004 => runs (actual spend 0.002). m/b: 0.002 + est 0.003 = 0.005 > 0.004 => skip.
    assert {r.model for r in rows} == {"m/a"}
    assert len(rows) == 2  # m/a complete, m/b not started


def test_skips_unaffordable_model_but_continues_to_cheaper(tmp_path, monkeypatch):
    _patch_clients(monkeypatch)
    budget.register_prices([("m/a", 1.0, 0.0), ("m/expensive", 100.0, 0.0), ("m/c", 1.0, 0.0)])
    out = tmp_path / "crosslab.jsonl"
    crosslab.run_crosslab(
        [("m/a", "openrouter"), ("m/expensive", "openrouter"), ("m/c", "openrouter")],
        [TASK], reps=2, out_path=out, backend=_OkBackend(), max_spend=0.01,
    )
    rows = [RunResult.from_json(l) for l in out.read_text().splitlines() if l.strip()]
    # a: est 0.003 fits -> runs (spend ~0.002). expensive: est 0.30 -> skipped.
    # c: est 0.003 + spent ~0.002 = ~0.005 <= 0.01 -> still runs (continue, not break).
    assert {r.model for r in rows} == {"m/a", "m/c"}


def test_circuit_breaker_aborts_on_consecutive_errors(tmp_path, monkeypatch):
    _patch_clients(monkeypatch)
    budget.register_prices([("m/x", 1.0, 0.0)])
    out = tmp_path / "crosslab.jsonl"

    class _RaisingBackend:
        def run(self, job):
            raise RuntimeError("sandbox down")

    res = crosslab.run_crosslab([("m/x", "openrouter")], [TASK], reps=10,
                                out_path=out, backend=_RaisingBackend(), max_spend=999.0)
    rows = [l for l in out.read_text().splitlines() if l.strip()]
    assert res["aborted"] is True
    # stopped at the limit (TASK has 1 library, reps=10 -> 10 potential cells)
    assert len(rows) == crosslab.CONSECUTIVE_ERROR_LIMIT
