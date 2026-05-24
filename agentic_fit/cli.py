from __future__ import annotations

import argparse
import time
from pathlib import Path

from dotenv import load_dotenv

from .agent import AnthropicClient
from .backends import DockerBackend, LocalBackend, SandboxBackend
from .budget import estimate_matrix_cost, total_cost
from .loader import load_tasks
from .runner import run_matrix
from .scoring import category_variance_summary, load_results, score_categories
from .venvs import ensure_venv


def format_category_summary(summary: dict) -> list[str]:
    lines = []
    for category, s in summary.items():
        lines.append(
            # best/worst rank by (success_rate, then fewer tokens); token_ratio is the
            # pure cost spread. Label them best/worst — NOT cheapest/costliest — since
            # when success rates differ the best library may not be the cheapest.
            f"{category}: spread={s['success_spread_pp']}pp "
            f"token_ratio={s['token_ratio']} "
            f"best={s['best'][0]}({s['best'][1]:.0%} success, {s['best'][2]:.0f} tok) "
            f"worst={s['worst'][0]}({s['worst'][1]:.0%} success, {s['worst'][2]:.0f} tok)"
        )
    return lines


def format_progress_line(done: int, total: int, r, spent: float, elapsed_s: float) -> str:
    mark = "✓" if r.success else "✗"
    outcome = "passed" if r.success else (r.error or "failed")
    m, s = divmod(int(elapsed_s), 60)
    return (f"[{done:>3}/{total}] {r.category}/{r.library} rep={r.rep} "
            f"{mark} {outcome[:24]} · {r.iterations} iter · {r.total_tokens:,} tok "
            f"· ${spent:.2f} · {m}m{s:02d}s")


def select_backend(name: str) -> SandboxBackend:
    return DockerBackend() if name == "docker" else LocalBackend()


def prewarm_envs(tasks) -> None:
    libs = sorted({lib for t in tasks for lib in t.candidate_libraries})
    for lib in libs:
        info = ensure_venv(lib)
        kind = "stdlib" if info.is_stdlib else info.version
        print(f"  env ready: {lib} ({kind})", flush=True)


def _make_reporter(start: float):
    def report(done, total, r, spent):
        print(format_progress_line(done, total, r, spent, time.monotonic() - start), flush=True)
    return report


def main() -> None:
    load_dotenv()  # read ANTHROPIC_API_KEY (and friends) from a local .env if present
    p = argparse.ArgumentParser(description="Run the agentic-fit matrix")
    p.add_argument("--tasks-dir", default="tasks")
    p.add_argument("--out", default="results/run.jsonl")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--reps", type=int, default=5)
    p.add_argument("--max-spend", type=float, default=30.0,
                   help="Abort once spend (USD) reaches this cap")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the matrix size and cost estimate, then exit")
    p.add_argument("--sandbox", choices=["local", "docker"], default="local",
                   help="Execution backend: local host subprocess or hardened Docker container")
    args = p.parse_args()

    tasks = load_tasks(Path(args.tasks_dir))
    est = estimate_matrix_cost(tasks, args.model, args.reps)

    if args.dry_run:
        print(f"dry-run: {est['cells']} cells · model={args.model} "
              f"· reps={args.reps} · est ${est['est_cost_usd']} (cap ${args.max_spend})")
        return

    out = Path(args.out)
    print(f"agentic-fit: {est['cells']} cells · model={args.model} · reps={args.reps} "
          f"· est ${est['est_cost_usd']} · cap ${args.max_spend} · sandbox={args.sandbox}", flush=True)
    if args.sandbox == "local":
        # Pre-warm doubles as the fail-before-spend guard: it builds every candidate's
        # isolated venv up front, so an uninstallable/typo'd library aborts here —
        # before any API budget is spent — rather than mid-run.
        print("preparing isolated environments…", flush=True)
        prewarm_envs(tasks)
    else:
        print("sandbox=docker: per-library envs build in-container on first use", flush=True)

    start = time.monotonic()
    client = AnthropicClient(model=args.model)
    run_matrix(client, tasks, args.model, args.reps, out,
               backend=select_backend(args.sandbox),
               max_spend=args.max_spend, on_result=_make_reporter(start))

    results = load_results(out)
    summary = category_variance_summary(score_categories(results))
    print(f"\n=== agentic-fit summary ({args.model}, reps={args.reps}) ===")
    for line in format_category_summary(summary):
        print(line)
    elapsed = int(time.monotonic() - start)
    print(f"done: {len(results)} runs · ${total_cost(results):.2f} "
          f"· {elapsed // 60}m{elapsed % 60:02d}s · results → {out}")


if __name__ == "__main__":
    main()
