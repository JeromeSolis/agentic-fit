from agentic_fit import cli


def test_build_parser_has_subcommands():
    ns = cli.build_parser().parse_args(["run", "--free", "--dry-run"])
    assert ns.cmd == "run"
    assert ns.mode == "free"
    assert ns.dry_run is True


def test_run_handler_calls_execute_run(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "execute_run", lambda **kw: captured.update(kw) or {})
    cli.main(["run", "--free", "--probe", "--only", "x/y", "--yes", "--dry-run"])
    assert captured["mode"] == "free"
    assert captured["reps"] == 1
    assert captured["only"] == "x/y"
    assert captured["assume_yes"] is True
    assert captured["dry_run"] is True


def test_select_backend_still_exported():
    from agentic_fit.cli import select_backend
    assert select_backend("local").__class__.__name__ == "LocalBackend"


def test_summarize_handler_renders(tmp_path, capsys):
    import json
    f = tmp_path / "free.jsonl"
    f.write_text(json.dumps({
        "task_id": "data_validation__x", "library": "", "rep": 0, "model": "m1",
        "success": True, "tests_passed": 1, "tests_total": 1, "iterations": 1,
        "input_tokens": 0, "output_tokens": 0, "category": "data_validation",
        "status": "passed", "cost_usd": 0.0, "provider": "openrouter",
        "imports": ["pydantic"]}) + "\n")
    cli.main(["summarize", str(f)])
    assert "free-choice picks" in capsys.readouterr().out


def test_models_list(capsys):
    cli.main(["models"])
    assert "anthropic/claude-opus-4.7" in capsys.readouterr().out


def test_info_handler_runs(capsys):
    cli.main(["info"])
    out = capsys.readouterr().out
    assert "agentic-fit" in out
    assert "Categories" in out
    assert "Two modes" in out
    assert "First steps" in out
    assert "https://jeromesolis.github.io/agentic-fit/" in out


def test_bare_invocation_runs_info(capsys):
    cli.main([])
    out = capsys.readouterr().out
    assert "Categories" in out
    assert "Two modes" in out


def test_tasks_lists_categories_with_summaries(capsys):
    cli.main(["tasks"])
    out = capsys.readouterr().out
    assert "cli_parsing" in out and "argparse" in out
    assert "yaml_config" in out and "omegaconf" in out
    assert "Validate and coerce a user record" in out


def test_summarize_json_emits_valid_json(tmp_path, capsys):
    import json
    f = tmp_path / "free.jsonl"
    f.write_text(json.dumps({
        "task_id": "data_validation__x", "library": "", "rep": 0, "model": "m1",
        "success": True, "tests_passed": 1, "tests_total": 1, "iterations": 1,
        "input_tokens": 0, "output_tokens": 0, "category": "data_validation",
        "status": "passed", "cost_usd": 0.0, "provider": "openrouter",
        "imports": ["pydantic"]}) + "\n")
    cli.main(["summarize", str(f), "--json"])
    obj = json.loads(capsys.readouterr().out)
    assert "summary" in obj
    assert "n_cells" in obj["summary"]


def test_run_requires_explicit_mode(capsys):
    import pytest
    with pytest.raises(SystemExit):
        cli.main(["run", "--dry-run"])
    err_out = capsys.readouterr()
    msg = (err_out.err or "") + (err_out.out or "")
    assert "--free" in msg and "--assigned" in msg


def test_run_assigned_dispatches_correctly(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "execute_run", lambda **kw: captured.update(kw) or {})
    cli.main(["run", "--assigned", "--dry-run"])
    assert captured["mode"] == "assigned"
    assert captured["dry_run"] is True
