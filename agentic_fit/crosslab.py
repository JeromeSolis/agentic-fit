from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from .agent import make_client, run_agent
from .backends import SandboxBackend
from .budget import estimate_crosslab_cost, run_cost
from .cli import select_backend
from .loader import load_tasks
from .models import RunResult, Task

AVG_INPUT, AVG_OUTPUT = 1500, 1200  # for the pre-model cap estimate
CONSECUTIVE_ERROR_LIMIT = 8  # abort an unattended run if this many cells error in a row


def run_crosslab(
    models: list[tuple[str, str]],
    tasks: list[Task],
    reps: int,
    out_path: Path,
    *,
    backend: SandboxBackend | None = None,
    max_spend: float = 25.0,
    on_result: Callable[..., None] | None = None,
) -> dict:
    """models: list of (model_id, provider). Caps spend at model boundaries."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cells = sum(len(t.candidate_libraries) for t in tasks) * reps
    spent = 0.0
    done, total = 0, cells * len(models)
    consecutive_errors = 0
    aborted = False
    with out_path.open("w") as f:
        for model_id, provider in models:
            if aborted:
                break
            est_next = cells * run_cost(model_id, AVG_INPUT, AVG_OUTPUT)
            if spent + est_next > max_spend:
                continue  # skip a model that won't fit; cheaper models later can still run
            client = make_client(provider, model_id)
            for task in tasks:
                if aborted:
                    break
                for library in task.candidate_libraries:
                    if aborted:
                        break
                    for rep in range(reps):
                        r = run_agent(client, task, library, model_id, rep,
                                      backend=backend, provider=provider)
                        f.write(r.to_json() + "\n")
                        f.flush()
                        done += 1
                        spent += r.cost_usd or 0.0
                        if on_result is not None:
                            on_result(done, total, r, spent, model_id)
                        consecutive_errors = consecutive_errors + 1 if r.status == "error" else 0
                        if consecutive_errors >= CONSECUTIVE_ERROR_LIMIT:
                            print(f"ABORT: {consecutive_errors} consecutive errored cells — likely a "
                                  f"systemic failure (sandbox down, API outage, or bad key). Stopping to "
                                  f"avoid wasted spend. Last error: {(r.error or '')[:160]}", flush=True)
                            aborted = True
                            break
    return {"cost_usd": round(spent, 4), "aborted": aborted}


def main() -> None:
    load_dotenv()  # ANTHROPIC_API_KEY + OPENROUTER_API_KEY
    from .crosslab_models import CROSSLAB_MODELS, register_crosslab_prices

    p = argparse.ArgumentParser(description="Run the agentic-fit matrix across labs via OpenRouter")
    p.add_argument("--tasks-dir", default="tasks")
    p.add_argument("--out", default="results/crosslab.jsonl")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--max-spend", type=float, default=25.0,
                   help="Cap on total spend (USD)")
    p.add_argument("--sandbox", choices=["local", "docker"], default="docker")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not args.dry_run and args.sandbox == "docker":
        from .backends import docker_available
        if not docker_available():
            raise SystemExit(
                "Docker selected (--sandbox docker) but the daemon isn't reachable. "
                "Start Docker, or re-run with --sandbox local. No spend incurred.")

    register_crosslab_prices()
    bad = [s.model_id for s in CROSSLAB_MODELS if "<" in s.model_id or s.price_in <= 0]
    if bad:
        raise SystemExit(
            "crosslab_models.py is not populated — run scripts/fetch_openrouter_models.py "
            f"and fill in real ids/prices first. Unpopulated rows: {bad}")
    tasks = load_tasks(Path(args.tasks_dir))
    models = [(s.model_id, s.provider) for s in CROSSLAB_MODELS]
    est = estimate_crosslab_cost(tasks, models, args.reps)

    if args.dry_run:
        print(f"dry-run: {est['cells_per_model']} cells/model · {len(models)} models · reps={args.reps}")
        for m in est["per_model"]:
            print(f"  {m['model']:40s} est ${m['est_cost_usd']}")
        print(f"total est ${est['total_usd']} (cap ${args.max_spend})")
        return

    out = Path(args.out)
    print(f"agentic-fit cross-lab: {len(models)} models · reps={args.reps} · "
          f"cap ${args.max_spend} · sandbox={args.sandbox}", flush=True)
    start = time.monotonic()

    def report(done, total, r, spent, model_id):
        m, s = divmod(int(time.monotonic() - start), 60)
        mark = "✓" if r.success else "✗"
        print(f"[{done:>4}/{total}] {model_id} {r.category}/{r.library} rep={r.rep} "
              f"{mark} {r.total_tokens:,} tok · ${spent:.2f} · {m}m{s:02d}s", flush=True)

    spent = run_crosslab(models, tasks, args.reps, out,
                         backend=select_backend(args.sandbox),
                         max_spend=args.max_spend, on_result=report)
    if spent.get("aborted"):
        print("run ABORTED early by the consecutive-error circuit breaker — review the log above.", flush=True)
    print(f"done: cost ${spent['cost_usd']} · results → {out}")


if __name__ == "__main__":
    main()
