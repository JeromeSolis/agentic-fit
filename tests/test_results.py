import json
from pathlib import Path

from agentic_fit import cli


def _write_run(path: Path, mode: str, cost: float = 0.0):
    row = {"task_id": "data_validation__x",
           "library": "" if mode == "free" else "pydantic",
           "rep": 0, "model": "m1", "success": True, "tests_passed": 1,
           "tests_total": 1, "iterations": 1, "input_tokens": 0,
           "output_tokens": 0, "category": "data_validation",
           "status": "passed", "cost_usd": cost, "provider": "openrouter",
           "imports": ["pydantic"] if mode == "free" else None}
    path.write_text(json.dumps(row) + "\n")


def test_results_lists_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results").mkdir()
    _write_run(tmp_path / "results" / "crosslab_free_reps3_2026-05-27.jsonl", "free", 0.10)
    _write_run(tmp_path / "results" / "crosslab_assigned_reps3_2026-05-26.jsonl", "assigned", 0.20)
    cli.main(["results"])
    out = capsys.readouterr().out
    assert "crosslab_free_reps3_2026-05-27.jsonl" in out
    assert "crosslab_assigned_reps3_2026-05-26.jsonl" in out
    assert "free" in out and "assigned" in out


def test_results_inspect_renders_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results").mkdir()
    f = tmp_path / "results" / "crosslab_free_reps3_2026-05-27.jsonl"
    _write_run(f, "free", 0.10)
    cli.main(["results", "inspect", str(f)])
    out = capsys.readouterr().out
    assert "free-choice picks" in out


def test_results_listing_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results").mkdir()
    _write_run(tmp_path / "results" / "crosslab_free_reps3_2026-05-27.jsonl", "free", 0.10)
    cli.main(["results", "--json"])
    out = capsys.readouterr().out
    rows = json.loads(out)
    assert isinstance(rows, list) and rows[0]["mode"] == "free"
