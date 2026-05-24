from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from .sandbox import run_solution
from .venvs import resolve_job_env


def main() -> None:
    job = json.loads(sys.stdin.read())
    env = resolve_job_env(job["library"], job.get("install_libraries"))
    workdir = Path(tempfile.mkdtemp(prefix="af_run_"))
    try:
        test_path = workdir / "test_solution.py"
        test_path.write_text(job["test_code"])
        result = run_solution(
            job["solution_code"], str(test_path), job["library"],
            job.get("competing_libraries", []), timeout=job.get("timeout", 60),
            python_executable=env.python, enforce_import=job.get("enforce_import", False),
        )
        out = asdict(result)
        out["version"] = env.version
        print(json.dumps(out))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
