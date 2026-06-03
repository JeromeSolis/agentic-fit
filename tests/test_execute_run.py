from pathlib import Path
from agentic_fit import crosslab, budget
from agentic_fit.crosslab_models import CROSSLAB_MODELS


def _prices():
    budget.register_prices([(s.model_id, s.price_in, s.price_out) for s in CROSSLAB_MODELS])


def test_dry_run_does_not_invoke_runner():
    called = {"n": 0}
    def fake_runner(*a, **k):
        called["n"] += 1
        return {"cost_usd": 0.0, "aborted": False}
    res = crosslab.execute_run(mode="free", reps=1, sandbox="local", dry_run=True,
                               runner=fake_runner, summarize=False)
    assert called["n"] == 0
    assert res.get("dry_run") is True


def test_decline_confirmation_aborts(tmp_path):
    called = {"n": 0}
    def fake_runner(*a, **k):
        called["n"] += 1
        return {"cost_usd": 0.0, "aborted": False}
    res = crosslab.execute_run(mode="free", reps=1, sandbox="local",
                               out=str(tmp_path / "o.jsonl"),
                               runner=fake_runner, confirm=lambda total: False, summarize=False)
    assert called["n"] == 0
    assert res.get("confirmed") is False


def test_only_filters_models(tmp_path):
    seen = {}
    def fake_runner(models, tasks, reps, out_path, **k):
        seen["models"] = models
        Path(out_path).write_text("")
        return {"cost_usd": 0.0, "aborted": False}
    crosslab.execute_run(mode="free", reps=1, sandbox="local",
                         only="anthropic/claude-opus-4.7", out=str(tmp_path / "o.jsonl"),
                         runner=fake_runner, confirm=lambda total: True, summarize=False)
    assert [m for m, _ in seen["models"]] == ["anthropic/claude-opus-4.7"]


def test_only_unknown_id_errors(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        crosslab.execute_run(mode="free", reps=1, sandbox="local", only="no/such-model",
                             out=str(tmp_path / "o.jsonl"),
                             runner=lambda *a, **k: {}, confirm=lambda t: True, summarize=False)


def test_auto_named_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results").mkdir()
    seen = {}
    def fake_runner(models, tasks, reps, out_path, **k):
        seen["out"] = Path(out_path)
        Path(out_path).write_text("")
        return {"cost_usd": 0.0, "aborted": False}
    crosslab.execute_run(mode="free", reps=3, sandbox="local",
                         runner=fake_runner, confirm=lambda t: True, summarize=False)
    assert seen["out"].name.startswith("crosslab_free_reps3_")
    assert seen["out"].suffix == ".jsonl"


def test_free_run_auto_summarizes(tmp_path, capsys):
    import json
    out = tmp_path / "free.jsonl"
    def fake_runner(models, tasks, reps, out_path, **k):
        row = {"task_id": "data_validation__x", "library": "", "rep": 0, "model": "m1",
               "success": True, "tests_passed": 1, "tests_total": 1, "iterations": 1,
               "input_tokens": 0, "output_tokens": 0, "category": "data_validation",
               "status": "passed", "cost_usd": 0.0, "provider": "openrouter",
               "imports": ["pydantic"]}
        Path(out_path).write_text(json.dumps(row) + "\n")
        return {"cost_usd": 0.0, "aborted": False}
    crosslab.execute_run(mode="free", reps=1, sandbox="local", out=str(out),
                         runner=fake_runner, confirm=lambda t: True, summarize=True)
    assert "free-choice picks" in capsys.readouterr().out


def test_dry_run_prints_matrix_shape_and_eta(capsys):
    crosslab.execute_run(mode="free", reps=3, sandbox="local", dry_run=True,
                         runner=lambda *a, **k: {}, summarize=False)
    out = capsys.readouterr().out
    assert "cells/model" in out
    assert "categories" in out
    assert "ETA" in out


def test_live_progress_includes_eta_after_warmup(tmp_path, capsys):
    """Run a fake matrix of 12 cells across 2 models; assert the progress line
    includes 'ETA' after the warmup window and that a per-model divider prints
    when the active model changes."""
    import time
    from agentic_fit.models import RunResult

    def fake_runner(models, tasks, reps, out_path, *, mode, backend, max_spend, on_result):
        from pathlib import Path
        Path(out_path).write_text("")
        spent = 0.0
        for mi, (mid, _) in enumerate(models):
            for c in range(6):
                r = RunResult("t", "lib", 0, mid, True, 1, 1, 1,
                              input_tokens=10, output_tokens=10,
                              category="cli_parsing", cost_usd=0.01)
                spent += 0.01
                on_result(mi * 6 + c + 1, 12, r, spent, mid)
                time.sleep(0.001)
        return {"cost_usd": 0.12, "aborted": False}

    crosslab.execute_run(
        mode="free", reps=1, sandbox="local",
        only="anthropic/claude-opus-4.7,anthropic/claude-sonnet-4.6",
        out=str(tmp_path / "o.jsonl"),
        runner=fake_runner, confirm=lambda t: True, summarize=False,
    )
    out = capsys.readouterr().out
    assert "ETA" in out
    assert "model done" in out
