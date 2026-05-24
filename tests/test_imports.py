from agentic_fit.imports import imported_modules, used_candidates

CANDS = ["requests", "httpx", "urllib3", "dateutil"]


def test_detects_plain_import():
    assert used_candidates("import requests\n", CANDS) == ["requests"]


def test_detects_aliased_import():
    assert used_candidates("import httpx as h\n", CANDS) == ["httpx"]


def test_detects_from_import_submodule():
    assert used_candidates("from dateutil.parser import parse\n", CANDS) == ["dateutil"]


def test_detects_multiple_candidates():
    code = "import requests\nimport httpx\n"
    assert used_candidates(code, CANDS) == ["httpx", "requests"]


def test_ignores_non_candidate_and_stdlib():
    assert used_candidates("import os\nimport json\n", CANDS) == []


def test_syntax_error_returns_empty():
    assert used_candidates("def (:\n", CANDS) == []


def test_ignores_relative_import_matching_candidate_name():
    # A relative import is never a third-party candidate, even if it shares a name.
    assert used_candidates("from .requests import thing\n", CANDS) == []


def test_imported_modules_returns_all_top_level_names():
    code = "import requests\nimport os\nfrom arrow import get\nfrom .local import x\n"
    assert imported_modules(code) == ["arrow", "os", "requests"]


def test_imported_modules_syntax_error_returns_empty():
    assert imported_modules("def (:\n") == []
