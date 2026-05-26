# tests/test_build_site_data.py
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "build_site_data", ROOT / "scripts" / "build_site_data.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(model, category, library, rep, success, cost):
    return {"model": model, "category": category, "library": library,
            "rep": rep, "success": success, "cost_usd": cost, "status": "passed"}


def test_aggregate_collapses_reps_into_one_cell():
    bsd = _load()
    rows = [
        _row("m1", "data_validation", "pydantic", 0, True, 0.004),
        _row("m1", "data_validation", "pydantic", 1, True, 0.004),
        _row("m1", "data_validation", "pydantic", 2, False, 0.006),
    ]
    out = bsd.aggregate(rows)
    cell = out["cells"][0]
    assert cell["model"] == "m1"
    assert cell["library"] == "pydantic"
    assert cell["n"] == 3
    assert abs(cell["success_rate"] - 2 / 3) < 1e-9
    # median of [0.004, 0.004, 0.006] = 0.004 (not the mean 0.00467) — matches
    # agentic_fit.scoring.score_crosslab, which uses median cost.
    assert abs(cell["cost_usd"] - 0.004) < 1e-9


def test_aggregate_lists_sorted_deduped_dimensions():
    bsd = _load()
    rows = [
        _row("m2", "http_client", "httpx", 0, True, 0.01),
        _row("m1", "http_client", "requests", 0, True, 0.01),
        _row("m1", "data_validation", "pydantic", 0, True, 0.004),
    ]
    out = bsd.aggregate(rows)
    assert out["models"] == ["m1", "m2"]
    assert out["categories"] == ["data_validation", "http_client"]
    assert out["libraries_by_category"]["http_client"] == ["httpx", "requests"]


import json


def test_build_writes_envelope_with_snapshot(tmp_path):
    bsd = _load()
    src = tmp_path / "crosslab_reps3_2026-05-25.jsonl"
    src.write_text(
        json.dumps(_row("m1", "data_validation", "pydantic", 0, True, 0.004)) + "\n"
        + json.dumps(_row("m1", "data_validation", "pydantic", 1, True, 0.004)) + "\n"
    )
    out = tmp_path / "site" / "data.json"
    data = bsd.build(src, out, tasks_dir=tmp_path / "no_tasks")
    assert out.exists()
    on_disk = json.loads(out.read_text())
    assert on_disk["snapshot"] == "2026-05-25"
    assert set(on_disk) == {"snapshot", "models", "categories",
                            "libraries_by_category", "cells", "tasks"}
    assert data["snapshot"] == "2026-05-25"
    # task meta carries an entry per category; summary comes from the editorial
    # dict even when the task.yaml dir is absent (prompt then empty).
    assert on_disk["tasks"]["data_validation"]["summary"]
    assert on_disk["tasks"]["data_validation"]["prompt"] == ""


def test_build_embeds_task_prompt_from_yaml(tmp_path):
    bsd = _load()
    src = tmp_path / "crosslab_reps3_2026-05-25.jsonl"
    src.write_text(json.dumps(_row("m1", "cli_parsing", "argparse", 0, True, 0.004)) + "\n")
    tasks = tmp_path / "tasks" / "cli_parsing"
    tasks.mkdir(parents=True)
    (tasks / "task.yaml").write_text(
        "id: cli_parsing__parse_args\ncategory: cli_parsing\n"
        "prompt: |\n  Write a function parse(argv).\n"
        'candidate_libraries: ["argparse", "click", "typer"]\n'
    )
    data = bsd.build(src, src.parent / "site" / "data.json", tasks_dir=tmp_path / "tasks")
    t = data["tasks"]["cli_parsing"]
    assert t["prompt"] == "Write a function parse(argv)."
    assert t["candidate_libraries"] == ["argparse", "click", "typer"]
