from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .imports import used_candidates

DISALLOWED_IMPORT = "Solution imported a disallowed library"
IMPORT_NOT_USED = "Solution did not import the assigned library"

# Env var names matching this are stripped before running untrusted generated
# code, so a solution can't read the API key (or other secrets) from os.environ.
_SECRET_ENV = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.IGNORECASE)


def _safe_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not _SECRET_ENV.search(k)}


@dataclass
class SandboxResult:
    passed: bool
    tests_passed: int
    tests_total: int
    stdout: str
    stderr: str
    status: str  # required: every construction site names the status explicitly
    version: str = ""  # resolved library version, filled in by the backend


def _count(stdout: str, word: str) -> int:
    m = re.search(rf"(\d+) {word}", stdout)
    return int(m.group(1)) if m else 0


def _parse_pytest(stdout: str) -> tuple[int, int]:
    # Parse ONLY pytest's terminal summary line (e.g. "1 failed, 2 passed in
    # 0.10s"), never the body, so words like "passed" inside a traceback can't
    # inflate counts. The summary is the last such line.
    summaries = re.findall(r"^([\w, ]+?) in \d+(?:\.\d+)?s", stdout, re.MULTILINE)
    if not summaries:
        return 0, 0
    summary = summaries[-1]
    passed = _count(summary, "passed")
    failed = _count(summary, "failed")
    errors = _count(summary, "error")
    return passed, passed + failed + errors


def _status_from_returncode(rc: int) -> str:
    # pytest exit codes: 0=ok, 1=tests failed, 2=interrupted/collection error,
    # 3=internal error, 4=usage error, 5=no tests collected. 3 and 4 fall back to "failed".
    return {0: "passed", 1: "failed", 2: "collection_error", 5: "no_tests"}.get(rc, "failed")


def run_solution(
    solution_code: str,
    test_path: str,
    allowed_library: str,
    competing_libraries: list[str],
    timeout: int = 60,
    *,
    python_executable: str = sys.executable,
    enforce_import: bool = False,
) -> SandboxResult:
    used = used_candidates(solution_code, competing_libraries)
    disallowed = [lib for lib in used if lib != allowed_library]
    if disallowed:
        return SandboxResult(False, 0, 0, "", DISALLOWED_IMPORT, status="disallowed_import")
    if enforce_import and allowed_library not in used:
        return SandboxResult(False, 0, 0, "", IMPORT_NOT_USED, status="import_not_used")

    workdir = Path(tempfile.mkdtemp(prefix="af_"))
    try:
        (workdir / "solution.py").write_text(solution_code)
        shutil.copy(test_path, workdir / "test_solution.py")
        proc = subprocess.run(
            [python_executable, "-m", "pytest", "test_solution.py", "-q",
             "--tb=short", "-p", "no:cacheprovider"],
            cwd=workdir, capture_output=True, text=True, timeout=timeout,
            env=_safe_env(),
        )
        passed_n, total_n = _parse_pytest(proc.stdout)
        status = _status_from_returncode(proc.returncode)
        return SandboxResult(proc.returncode == 0, passed_n, total_n,
                             proc.stdout, proc.stderr, status=status)
    except subprocess.TimeoutExpired:
        return SandboxResult(False, 0, 0, "", "timeout", status="timeout")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
