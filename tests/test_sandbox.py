from pathlib import Path

from agentic_fit.sandbox import (
    DISALLOWED_IMPORT,
    IMPORT_NOT_USED,
    _parse_pytest,
    _safe_env,
    _status_from_returncode,
    run_solution,
)

TEST_FILE = str(Path(__file__).parent / "fixtures" / "sample_task" / "test_solution.py")


def test_passing_solution():
    code = "def add(a, b):\n    return a + b\n"
    r = run_solution(code, TEST_FILE, allowed_library="math", competing_libraries=["math"])
    assert r.passed is True
    assert r.tests_passed == 1
    assert r.tests_total == 1


def test_failing_solution():
    code = "def add(a, b):\n    return a - b\n"
    r = run_solution(code, TEST_FILE, allowed_library="math", competing_libraries=["math"])
    assert r.passed is False
    assert r.tests_passed == 0
    assert r.tests_total == 1


def test_disallowed_import_is_rejected():
    code = "import requests\n\ndef add(a, b):\n    return a + b\n"
    r = run_solution(
        code, TEST_FILE, allowed_library="httpx",
        competing_libraries=["httpx", "requests"],
    )
    assert r.passed is False
    assert r.stderr == DISALLOWED_IMPORT


def test_parse_pytest_all_passed():
    assert _parse_pytest("..\n2 passed in 0.01s\n") == (2, 2)


def test_parse_pytest_mixed():
    assert _parse_pytest("1 failed, 2 passed in 0.10s\n") == (2, 3)


def test_parse_pytest_no_tests():
    assert _parse_pytest("no tests ran in 0.00s\n") == (0, 0)


def test_parse_pytest_ignores_traceback_word():
    out = "F\nE   assert log == '3 passed'\n1 failed in 0.02s\n"
    assert _parse_pytest(out) == (0, 1)


def test_status_passed_and_failed():
    good = run_solution("def add(a, b):\n    return a + b\n", TEST_FILE,
                        allowed_library="math", competing_libraries=["math"])
    assert good.status == "passed"
    bad = run_solution("def add(a, b):\n    return a - b\n", TEST_FILE,
                       allowed_library="math", competing_libraries=["math"])
    assert bad.status == "failed"


def test_import_not_used_is_rejected_for_third_party():
    # Solution does not import the assigned third-party lib -> rejected pre-run.
    code = "def add(a, b):\n    return a + b\n"
    r = run_solution(code, TEST_FILE, allowed_library="httpx",
                     competing_libraries=["httpx", "requests"], enforce_import=True)
    assert r.passed is False
    assert r.status == "import_not_used"
    assert r.stderr == IMPORT_NOT_USED


def test_enforcement_skipped_when_disabled():
    code = "def add(a, b):\n    return a + b\n"
    r = run_solution(code, TEST_FILE, allowed_library="math",
                     competing_libraries=["math"], enforce_import=False)
    assert r.status == "passed"


def test_disallowed_import_sets_status():
    code = "import requests\n\ndef add(a, b):\n    return a + b\n"
    r = run_solution(code, TEST_FILE, allowed_library="httpx",
                     competing_libraries=["httpx", "requests"])
    assert r.status == "disallowed_import"
    assert r.stderr == DISALLOWED_IMPORT


def test_status_from_returncode_maps_pytest_exit_codes():
    assert _status_from_returncode(0) == "passed"
    assert _status_from_returncode(1) == "failed"
    assert _status_from_returncode(2) == "collection_error"
    assert _status_from_returncode(5) == "no_tests"
    assert _status_from_returncode(4) == "failed"  # usage error falls through


def test_safe_env_strips_secrets_keeps_benign(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("MY_TOKEN", "t")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = _safe_env()
    assert "ANTHROPIC_API_KEY" not in env
    assert "MY_TOKEN" not in env
    assert "DB_PASSWORD" not in env
    assert env["PATH"] == "/usr/bin"


def test_run_solution_subprocess_env_excludes_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    captured = {}

    class _Proc:
        returncode = 0
        stdout = "1 passed in 0.01s\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["env"] = kwargs.get("env")
        return _Proc()

    monkeypatch.setattr("agentic_fit.sandbox.subprocess.run", fake_run)
    run_solution("def add(a, b):\n    return a + b\n", TEST_FILE,
                 allowed_library="math", competing_libraries=["math"])
    assert captured["env"] is not None
    assert "ANTHROPIC_API_KEY" not in captured["env"]
