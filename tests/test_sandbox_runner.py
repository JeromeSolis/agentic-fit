import json
import subprocess
import sys
from pathlib import Path

SAMPLE_TEST = (Path(__file__).parent / "fixtures" / "sample_task" / "test_solution.py").read_text()


def _run_runner(job: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "agentic_fit.sandbox_runner"],
        input=json.dumps(job), text=True, capture_output=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.splitlines()[-1])


def test_runner_passes_stdlib_cell():
    out = _run_runner({
        "solution_code": "def add(a, b):\n    return a + b\n",
        "test_code": SAMPLE_TEST,
        "library": "math",
        "competing_libraries": ["math"],
        "enforce_import": False,
        "timeout": 60,
    })
    assert out["passed"] is True
    assert out["status"] == "passed"
    assert out["version"].startswith("py")


def test_runner_reports_failing_cell():
    out = _run_runner({
        "solution_code": "def add(a, b):\n    return a - b\n",  # wrong
        "test_code": SAMPLE_TEST,
        "library": "math",
        "competing_libraries": ["math"],
        "enforce_import": False,
        "timeout": 60,
    })
    assert out["passed"] is False
    assert out["status"] == "failed"


def test_runner_free_choice_stdlib_solution_uses_base():
    # install_libraries=[] (free, pure-stdlib pick) -> base interpreter, runs fine.
    out = _run_runner({
        "solution_code": "def add(a, b):\n    return a + b\n",
        "test_code": SAMPLE_TEST,
        "library": "",
        "competing_libraries": [],
        "enforce_import": False,
        "install_libraries": [],
        "timeout": 60,
    })
    assert out["passed"] is True
    assert out["status"] == "passed"
    assert out["version"].startswith("py")  # base interpreter via ensure_venv_for([])


def test_runner_bad_input_exits_nonzero_with_empty_stdout():
    # The DockerBackend treats empty stdout as an error; lock that contract in.
    proc = subprocess.run(
        [sys.executable, "-m", "agentic_fit.sandbox_runner"],
        input="not json", text=True, capture_output=True, timeout=10,
    )
    assert proc.returncode != 0
    assert proc.stdout == ""
