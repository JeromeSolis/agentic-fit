"""Holistic preflight: key, model ids resolve, Docker, registry, results dir."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .backends import docker_available
from .crosslab_models import CROSSLAB_MODELS


@dataclass
class CheckResult:
    ok: bool
    message: str
    name: str = ""


@dataclass
class SmokeSummary:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


def check_key() -> CheckResult:
    load_dotenv()
    val = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not val:
        return CheckResult(False, "OPENROUTER_API_KEY not set. Add it to .env.", "key")
    return CheckResult(True, "OPENROUTER_API_KEY is set.", "key")


def check_registry() -> CheckResult:
    bad = [s.model_id for s in CROSSLAB_MODELS if "<" in s.model_id or s.price_in <= 0]
    if bad:
        return CheckResult(False,
                           f"registry has {len(bad)} placeholder row(s); "
                           "run scripts/fetch_openrouter_models.py", "registry")
    return CheckResult(True, f"{len(CROSSLAB_MODELS)} models pinned with prices.", "registry")


def check_docker() -> CheckResult:
    return (CheckResult(True, "docker daemon reachable.", "docker")
            if docker_available()
            else CheckResult(False,
                             "docker daemon not reachable. Start Docker, or pass --no-docker.",
                             "docker"))


def check_results_dir() -> CheckResult:
    p = Path("results")
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".write-check"
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        return CheckResult(False, f"results/ is not writable: {exc}", "results_dir")
    return CheckResult(True, "results/ is writable.", "results_dir")


def check_model_ids() -> CheckResult:
    """Send a tiny request to each pinned model to confirm the id resolves."""
    from .agent import OpenRouterClient
    failures: list[str] = []
    for spec in CROSSLAB_MODELS:
        try:
            client = OpenRouterClient(spec.model_id, max_tokens=4)
            client.complete("Say OK.", [{"role": "user", "content": "Say OK."}])
        except Exception as exc:
            failures.append(f"{spec.model_id}: {type(exc).__name__}: {str(exc)[:80]}")
    if failures:
        return CheckResult(False, "models that did not resolve:\n  " + "\n  ".join(failures),
                           "model_ids")
    return CheckResult(True, f"all {len(CROSSLAB_MODELS)} model ids resolved.", "model_ids")


def holistic_smoke(skip_docker: bool = False) -> SmokeSummary:
    s = SmokeSummary()
    s.checks.append(check_key())
    s.checks.append(check_registry())
    s.checks.append(check_model_ids())
    if skip_docker:
        s.checks.append(CheckResult(True, "skipped (--no-docker).", "docker"))
    else:
        s.checks.append(check_docker())
    s.checks.append(check_results_dir())
    return s


def render_smoke(summary: SmokeSummary) -> list[str]:
    lines = []
    for c in summary.checks:
        mark = "ok" if c.ok else "FAIL"
        lines.append(f"  [{mark}] {c.name:12s} {c.message}")
    lines.append("")
    lines.append("all checks passed." if summary.ok else "fix the failing checks above before running.")
    return lines
