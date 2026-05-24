import os
import shutil
import sys
from pathlib import Path

import pytest

from agentic_fit.venvs import VenvInfo, ensure_venv, ensure_venv_for, resolve_job_env


def test_stdlib_short_circuits_to_base_interpreter():
    info = ensure_venv("datetime", cache_root=None, builder=_unused_builder)
    assert info.is_stdlib is True
    assert info.python == sys.executable


def _unused_builder(library, venv_dir):  # pragma: no cover - must never be called
    raise AssertionError("builder should not run for stdlib")


def test_third_party_builds_once_then_reuses_cache(tmp_path):
    calls = []

    def fake_builder(library, venv_dir):
        calls.append(library)
        (venv_dir).mkdir(parents=True, exist_ok=True)
        return "9.9.9"

    first = ensure_venv("arrow", cache_root=tmp_path, builder=fake_builder)
    second = ensure_venv("arrow", cache_root=tmp_path, builder=fake_builder)

    assert first.version == "9.9.9"
    assert second.version == "9.9.9"
    assert first.is_stdlib is False
    assert first.python == second.python  # same cached interpreter both times
    assert calls == ["arrow"]  # built once, second call hit the marker cache


def test_returns_absolute_python_path_even_with_relative_cache(tmp_path, monkeypatch):
    # The sandbox runs pytest with cwd=tempdir, so a relative interpreter path
    # would break. ensure_venv must return an absolute path regardless of cache_root.
    monkeypatch.chdir(tmp_path)

    def fake_builder(library, venv_dir):
        venv_dir.mkdir(parents=True, exist_ok=True)
        return "1.0.0"

    info = ensure_venv("arrow", cache_root=Path("relcache"), builder=fake_builder)
    assert os.path.isabs(info.python)


def _must_not_build(libraries, venv_dir):  # pragma: no cover
    raise AssertionError("builder should not run for an all-stdlib set")


def test_ensure_venv_for_empty_or_stdlib_is_base(tmp_path):
    info = ensure_venv_for([], cache_root=tmp_path, builder=_must_not_build)
    assert info.is_stdlib is True
    info2 = ensure_venv_for(["os", "json"], cache_root=tmp_path, builder=_must_not_build)
    assert info2.is_stdlib is True  # all stdlib filtered out -> base interpreter


def test_ensure_venv_for_multi_builds_once_keyed_on_sorted_set(tmp_path):
    calls = []

    def fake_builder(libraries, venv_dir):
        calls.append(tuple(libraries))
        venv_dir.mkdir(parents=True, exist_ok=True)
        return "arrow==1.0,requests==2.0"

    a = ensure_venv_for(["requests", "arrow"], cache_root=tmp_path, builder=fake_builder)
    b = ensure_venv_for(["arrow", "requests"], cache_root=tmp_path, builder=fake_builder)
    assert a.is_stdlib is False and a.version == "arrow==1.0,requests==2.0"
    assert a.python == b.python  # same cached venv regardless of input order
    assert calls == [("arrow", "requests")]  # built once, sorted, third-party only


def test_ensure_venv_for_single_lib_records_bare_version(tmp_path):
    # A single-lib set shares ensure_venv's cache dir, so the marker must match
    # ensure_venv's bare-version format, not "arrow==1.4.0".
    def fake_builder(libraries, venv_dir):
        venv_dir.mkdir(parents=True, exist_ok=True)
        return "arrow==1.4.0"

    info = ensure_venv_for(["arrow"], cache_root=tmp_path, builder=fake_builder)
    assert info.version == "1.4.0"


def test_resolve_job_env_routes_assigned_vs_free():
    assigned = resolve_job_env("math", None)
    assert assigned.is_stdlib is True
    free = resolve_job_env("", [])
    assert free.is_stdlib is True


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_real_uv_build_isolates_and_reports_version(tmp_path):
    info = ensure_venv("arrow", cache_root=tmp_path)
    assert info.version[0].isdigit()
    # The isolated interpreter has arrow but NOT a competing third-party lib.
    import subprocess

    ok = subprocess.run([info.python, "-c", "import arrow"], capture_output=True)
    assert ok.returncode == 0
    no_req = subprocess.run([info.python, "-c", "import requests"], capture_output=True)
    assert no_req.returncode != 0
    # pytest must be installed so the sandbox can run the hidden test in the venv.
    has_pytest = subprocess.run([info.python, "-m", "pytest", "--version"], capture_output=True)
    assert has_pytest.returncode == 0


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_ensure_venv_for_real_multi_build(tmp_path):
    info = ensure_venv_for(["arrow", "chevron"], cache_root=tmp_path)
    assert info.is_stdlib is False
    import subprocess
    ok = subprocess.run([info.python, "-c", "import arrow, chevron"], capture_output=True)
    assert ok.returncode == 0
