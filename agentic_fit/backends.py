from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .sandbox import SandboxResult, run_solution
from .venvs import resolve_job_env


def docker_available() -> bool:
    """True if the Docker daemon is reachable. Used as a preflight before a docker run."""
    import subprocess

    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=15)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


@dataclass
class SandboxJob:
    solution_code: str
    test_code: str
    library: str
    competing_libraries: list[str] = field(default_factory=list)
    enforce_import: bool = False
    timeout: int = 60
    install_libraries: list[str] | None = None  # None=assigned (ensure_venv); list=free-choice


class SandboxBackend(Protocol):
    def run(self, job: SandboxJob) -> SandboxResult: ...


class LocalBackend:
    """Runs the install + test on the host (today's behavior). Default for dev/CI."""

    def run(self, job: SandboxJob) -> SandboxResult:
        env = resolve_job_env(job.library, job.install_libraries)
        workdir = Path(tempfile.mkdtemp(prefix="af_job_"))
        try:
            # run_solution takes a test *path* (it stages into its own workdir),
            # so write the job's test_code to a file for it to consume.
            test_path = workdir / "test_solution.py"
            test_path.write_text(job.test_code)
            result = run_solution(
                job.solution_code, str(test_path), job.library,
                job.competing_libraries, timeout=job.timeout,
                python_executable=env.python, enforce_import=job.enforce_import,
            )
            result.version = env.version
            return result
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


class DockerBackend:
    """Runs the install + test inside an ephemeral, hardened container."""

    def __init__(self, image: str = "agentic-fit-sandbox:latest",
                 volume: str = "agentic_fit_venvs",
                 memory: str = "1g", cpus: str = "2", pids: int = 256):
        self.image = image
        self.volume = volume
        self.memory = memory
        self.cpus = cpus
        self.pids = pids

    def _argv(self) -> list[str]:
        return [
            "docker", "run", "--rm", "-i",
            "--user", "1000:1000",
            "--read-only", "--tmpfs", "/tmp:rw,size=256m,noexec",
            # uv writes its wheel-download cache here during venv builds; the
            # read-only rootfs would otherwise block third-party installs.
            "--tmpfs", "/home/sandbox/.cache:rw,size=512m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.pids),
            "--memory", self.memory,
            "--memory-swap", self.memory,  # swap == memory disables swap
            "--cpus", self.cpus,
            "-v", f"{self.volume}:/app/.cache/venvs",
            self.image,
        ]

    def run(self, job: SandboxJob) -> SandboxResult:
        payload = json.dumps({
            "solution_code": job.solution_code, "test_code": job.test_code,
            "library": job.library, "competing_libraries": job.competing_libraries,
            "enforce_import": job.enforce_import, "timeout": job.timeout,
            "install_libraries": job.install_libraries,
        })
        try:
            proc = subprocess.run(
                self._argv(), input=payload, text=True, capture_output=True,
                timeout=job.timeout + 120,
            )
        except subprocess.TimeoutExpired:
            # A hung container must not crash the whole matrix run.
            return SandboxResult(False, 0, 0, "", "host-side container timeout", status="timeout")
        if not proc.stdout.strip():
            raise RuntimeError(
                f"sandbox produced no result (exit {proc.returncode}). "
                f"stderr:\n{proc.stderr[-1000:]}"
            )
        raw = proc.stdout.splitlines()[-1]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"sandbox result is not valid JSON (exit {proc.returncode}): {raw!r}\n"
                f"stderr:\n{proc.stderr[-1000:]}"
            ) from exc
        return SandboxResult(**data)
