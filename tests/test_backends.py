import json
import shutil
from pathlib import Path

import pytest

from agentic_fit.backends import DockerBackend, LocalBackend, SandboxJob

SAMPLE_TEST = (Path(__file__).parent / "fixtures" / "sample_task" / "test_solution.py").read_text()


def test_local_backend_runs_stdlib_cell_and_reports_version():
    job = SandboxJob(
        solution_code="def add(a, b):\n    return a + b\n",
        test_code=SAMPLE_TEST,
        library="math",            # stdlib -> base interpreter, no venv build
        competing_libraries=["math"],
        enforce_import=False,
    )
    r = LocalBackend().run(job)
    assert r.passed is True
    assert r.tests_passed == 1
    assert r.status == "passed"
    assert r.version.startswith("py")  # stdlib version marker from ensure_venv


def test_local_backend_failing_solution():
    job = SandboxJob(
        solution_code="def add(a, b):\n    return a - b\n",
        test_code=SAMPLE_TEST,
        library="math", competing_libraries=["math"], enforce_import=False,
    )
    r = LocalBackend().run(job)
    assert r.passed is False
    assert r.status == "failed"


def test_local_backend_passes_enforce_import_through():
    # enforce_import=True + a solution that never imports the assigned library
    # must round-trip to a pre-run rejection (status import_not_used).
    job = SandboxJob(
        solution_code="def add(a, b):\n    return a + b\n",
        test_code=SAMPLE_TEST,
        library="math", competing_libraries=["math"], enforce_import=True,
    )
    r = LocalBackend().run(job)
    assert r.passed is False
    assert r.status == "import_not_used"


def test_docker_backend_builds_hardened_command_and_parses_result(monkeypatch):
    captured = {}

    class _Proc:
        returncode = 0
        stderr = ""
        stdout = json.dumps({
            "passed": True, "tests_passed": 1, "tests_total": 1,
            "stdout": "1 passed", "stderr": "", "status": "passed", "version": "2.0.0",
        })

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["input"] = kwargs.get("input")
        captured["env"] = kwargs.get("env")
        return _Proc()

    monkeypatch.setattr("agentic_fit.backends.subprocess.run", fake_run)

    job = SandboxJob(solution_code="x=1", test_code="def test(): assert True",
                     library="arrow", competing_libraries=["arrow"], enforce_import=True)
    r = DockerBackend().run(job)

    assert r.passed is True and r.version == "2.0.0"
    argv = captured["argv"]
    assert argv[0] == "docker" and argv[1] == "run"
    for flag in ["--rm", "--read-only", "--cap-drop", "--security-opt", "--pids-limit", "--user"]:
        assert flag in argv
    assert "agentic-fit-sandbox:latest" in argv
    payload = json.loads(captured["input"])
    assert payload["library"] == "arrow"
    assert payload["install_libraries"] is None  # assigned job -> forwarded as null
    # The backend forwards no host env vars into the container (no --env/-e flags),
    # so secrets never cross the boundary.
    assert "--env" not in argv and "-e" not in argv


def test_docker_backend_timeout_returns_timeout_status(monkeypatch):
    import subprocess as sp

    def boom(*a, **k):
        raise sp.TimeoutExpired(cmd="docker", timeout=1)

    monkeypatch.setattr("agentic_fit.backends.subprocess.run", boom)
    r = DockerBackend().run(SandboxJob("x=1", "t", "math"))
    assert r.passed is False
    assert r.status == "timeout"


def test_docker_backend_raises_on_non_json_output(monkeypatch):
    class _Proc:
        returncode = 1
        stderr = "Traceback ... boom"
        stdout = "not json at all"

    monkeypatch.setattr("agentic_fit.backends.subprocess.run", lambda *a, **k: _Proc())
    with pytest.raises(RuntimeError, match="not valid JSON"):
        DockerBackend().run(SandboxJob("x=1", "t", "math"))


def test_local_backend_free_choice_installs_detected_set(monkeypatch):
    # install_libraries given (free mode) -> resolve_job_env routes to ensure_venv_for.
    seen = {}

    def fake_resolve(library, install_libraries):
        seen["library"] = library
        seen["install"] = install_libraries
        from agentic_fit.venvs import VenvInfo
        import sys
        return VenvInfo(sys.executable, "free", is_stdlib=True)

    monkeypatch.setattr("agentic_fit.backends.resolve_job_env", fake_resolve)
    job = SandboxJob(solution_code="def add(a,b):\n    return a+b\n", test_code=SAMPLE_TEST,
                     library="", competing_libraries=[], enforce_import=False,
                     install_libraries=["arrow"])
    r = LocalBackend().run(job)
    assert seen["install"] == ["arrow"]
    assert r.version == "free"


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_docker_backend_runs_real_cell():
    # Requires the image: docker build -t agentic-fit-sandbox:latest .
    job = SandboxJob(
        solution_code="def add(a, b):\n    return a + b\n",
        test_code=SAMPLE_TEST, library="math",
        competing_libraries=["math"], enforce_import=False,
    )
    r = DockerBackend().run(job)
    assert r.passed is True
    assert r.status == "passed"


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_docker_backend_builds_third_party_venv_in_container():
    # Exercises uv install of a third-party lib in-container (needs the writable
    # uv-cache tmpfs under the read-only rootfs). Uses arrow + its own test.
    job = SandboxJob(
        solution_code="import arrow\n\ndef now_iso():\n    return arrow.get('2020-01-01').isoformat()\n",
        test_code="from solution import now_iso\n\ndef test_iso():\n    assert now_iso().startswith('2020-01-01')\n",
        library="arrow", competing_libraries=["arrow"], enforce_import=True,
    )
    r = DockerBackend().run(job)
    assert r.passed is True
    assert r.status == "passed"
    assert r.version and r.version[0].isdigit()  # resolved arrow version
