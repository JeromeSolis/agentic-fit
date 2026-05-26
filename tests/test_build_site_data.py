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
    assert abs(cell["cost_usd"] - (0.004 + 0.004 + 0.006) / 3) < 1e-9


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
