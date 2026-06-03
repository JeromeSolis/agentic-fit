from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from .agent import make_client, run_agent
from .backends import SandboxBackend
from .budget import estimate_crosslab_cost, run_cost
from .loader import load_tasks
from .models import Task

AVG_INPUT, AVG_OUTPUT = 1500, 1200  # for the pre-model cap estimate
CONSECUTIVE_ERROR_LIMIT = 8  # abort an unattended run if this many cells error in a row
SECONDS_PER_CELL = 15  # rough average from probe runs; used only for the dry-run ETA


def run_crosslab(
    models: list[tuple[str, str]],
    tasks: list[Task],
    reps: int,
    out_path: Path,
    *,
    mode: str = "assigned",
    backend: SandboxBackend | None = None,
    max_spend: float = 25.0,
    on_result: Callable[..., None] | None = None,
) -> dict:
    """models: list of (model_id, provider). Caps spend at model boundaries.

    mode="assigned" sweeps each task's candidate libraries (one run per library).
    mode="free" runs once per task with run_agent's free_unconstrained mode, so the
    model picks its own library (recorded as chosen_library).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_mode = "free_unconstrained" if mode == "free" else "assigned"
    # Flatten the work into (task, library) cells so the run loop stays uniform.
    if mode == "free":
        cell_specs = [(t, "") for t in tasks]
    else:
        cell_specs = [(t, lib) for t in tasks for lib in t.candidate_libraries]
    cells = len(cell_specs) * reps
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
            for task, library in cell_specs:
                if aborted:
                    break
                for rep in range(reps):
                    r = run_agent(client, task, library, model_id, rep,
                                  mode=run_mode, backend=backend, provider=provider)
                    f.write(r.to_json() + "\n")
                    f.flush()
                    done += 1
                    spent += r.cost_usd or 0.0
                    if on_result is not None:
                        on_result(done, total, r, spent, model_id)
                    consecutive_errors = consecutive_errors + 1 if r.status == "error" else 0
                    if consecutive_errors >= CONSECUTIVE_ERROR_LIMIT:
                        print(f"ABORT: {consecutive_errors} consecutive errored cells, likely a "
                              f"systemic failure (sandbox down, API outage, or bad key). Stopping to "
                              f"avoid wasted spend. Last error: {(r.error or '')[:160]}", flush=True)
                        aborted = True
                        break
    return {"cost_usd": round(spent, 4), "aborted": aborted}


def _select_models(only: str | None) -> list[tuple[str, str]]:
    from .crosslab_models import CROSSLAB_MODELS
    bad = [s.model_id for s in CROSSLAB_MODELS if "<" in s.model_id or s.price_in <= 0]
    if bad:
        raise SystemExit("crosslab registry not populated; run scripts/fetch_openrouter_models.py. "
                         f"Unpopulated: {bad}")
    specs = CROSSLAB_MODELS
    if only:
        wanted = [w.strip() for w in only.split(",") if w.strip()]
        by_id = {s.model_id: s for s in specs}
        missing = [w for w in wanted if w not in by_id]
        if missing:
            raise SystemExit(f"unknown model id(s): {missing}. See `agentic-fit models`.")
        specs = [by_id[w] for w in wanted]
    return [(s.model_id, s.provider) for s in specs]


def _default_out(mode: str, reps: int) -> Path:
    base = Path(f"results/crosslab_{mode}_reps{reps}_{date.today().isoformat()}.jsonl")
    if not base.exists():
        return base
    i = 2
    while (cand := base.with_name(f"{base.stem}-{i}.jsonl")).exists():
        i += 1
    return cand


def _prompt_confirm(total_usd: float) -> bool:
    return input(f"About to spend up to ~${total_usd} of OpenRouter credit. Proceed? [y/N] "
                 ).strip().lower() in ("y", "yes")


def _auto_summary(out_path: Path, tasks, mode: str, constrained: str | None) -> None:
    from .scoring import load_results
    rows = load_results(out_path)
    if not rows:
        return
    if mode == "free":
        from .summary import default_tax, render_default_tax, render_summary, summarize
        candidate_sets = {t.category: set(t.candidate_libraries) for t in tasks}
        constrained_rows = constrained_best = None
        if constrained and Path(constrained).exists():
            from .scoring import crosslab_best, score_crosslab
            constrained_rows = load_results(Path(constrained))
            best = crosslab_best(score_crosslab(constrained_rows))
            constrained_best = {k: v.library for k, v in best.items()}
        print("\n=== summary ===")
        for line in render_summary(summarize(rows, candidate_sets, constrained_best)):
            print(line)
        if constrained_rows:
            print()
            for line in render_default_tax(default_tax(rows, candidate_sets, constrained_rows)):
                print(line)
    else:
        import collections
        passed = sum(1 for r in rows if r.success)
        by_cat = collections.Counter(r.category for r in rows)
        cost = sum(r.cost_usd or 0.0 for r in rows)
        print("\n=== summary ===")
        print(f"{passed}/{len(rows)} cells passed · ${cost:.2f} · {len(by_cat)} categories")


def execute_run(*, mode: str = "free", reps: int = 3, only: str | None = None,
                sandbox: str = "docker", out: str | None = None, max_spend: float = 25.0,
                tasks_dir: str = "tasks", assume_yes: bool = False, dry_run: bool = False,
                summarize: bool = True, constrained: str | None = None,
                runner=run_crosslab, confirm=None) -> dict:
    """One entry point for a cross-lab run: select models, estimate, gate on
    confirmation, run, auto-summarize. `runner` and `confirm` are injectable for tests."""
    load_dotenv()
    from .crosslab_models import register_crosslab_prices
    register_crosslab_prices()
    models = _select_models(only)
    tasks = load_tasks(Path(tasks_dir))
    est = estimate_crosslab_cost(tasks, models, reps, mode=mode)
    print(f"agentic-fit run [{mode}]: {est['cells_per_model']} cells/model · "
          f"{len(models)} models · reps={reps}", flush=True)
    for m in est["per_model"]:
        print(f"  {m['model']:40s} est ${m['est_cost_usd']}")
    print(f"total est ${est['total_usd']} (cap ${max_spend})")
    total_cells = est["cells_per_model"] * len(models)
    eta_min = max(1, round(total_cells * SECONDS_PER_CELL / 60))
    cats = sorted({t.category for t in tasks})
    print(f"matrix: {total_cells} cells over {len(cats)} categories ({', '.join(cats)})")
    print(f"ETA ~{eta_min} min at {SECONDS_PER_CELL}s/cell")
    if dry_run:
        return {"dry_run": True, "total_usd": est["total_usd"]}

    if sandbox == "docker":
        from .backends import docker_available
        if not docker_available():
            raise SystemExit("Docker selected (--sandbox docker) but the daemon isn't reachable. "
                             "Start Docker, or re-run with --sandbox local. No spend incurred.")

    out_path = Path(out) if out else _default_out(mode, reps)
    confirm = confirm or _prompt_confirm
    if not assume_yes and not confirm(est["total_usd"]):
        print("aborted: not confirmed. No spend incurred.")
        return {"aborted": True, "confirmed": False}

    from .cli import select_backend
    start = time.monotonic()

    state = {"prev_model": None, "model_started_at": start, "model_cost_at_start": 0.0}

    def report(done, total, r, spent, model_id):
        now = time.monotonic()
        cell_cost = r.cost_usd or 0.0

        if state["prev_model"] is None:
            state["prev_model"] = model_id
            state["model_cost_at_start"] = spent - cell_cost
        elif state["prev_model"] != model_id:
            prev = state["prev_model"]
            # Spend for the just-finished model excludes the current cell's cost
            # (which belongs to the new model).
            d_cost = (spent - cell_cost) - state["model_cost_at_start"]
            d_min = (now - state["model_started_at"]) / 60
            print(f"=== model done · {prev}: ${d_cost:.2f}, {d_min:.1f}m ===", flush=True)
            state["prev_model"] = model_id
            state["model_started_at"] = now
            state["model_cost_at_start"] = spent - cell_cost

        elapsed_total = now - start
        eta_part = ""
        if done >= 6:
            remaining = total - done
            avg = elapsed_total / done
            eta_min = max(1, round(avg * remaining / 60))
            eta_part = f" · ETA {eta_min}m"

        m, s = divmod(int(elapsed_total), 60)
        mark = "✓" if r.success else "✗"
        lib = r.library or ("+".join(r.imports) if r.imports else "stdlib")
        print(f"[{done:>4}/{total}] {model_id} {r.category}/{lib} rep={r.rep} "
              f"{mark} {r.total_tokens:,} tok · ${spent:.2f}{eta_part} · {m}m{s:02d}s",
              flush=True)

    result = runner(models, tasks, reps, out_path, mode=mode,
                    backend=select_backend(sandbox), max_spend=max_spend, on_result=report)
    print(f"done: cost ${result['cost_usd']} · results → {out_path}", flush=True)
    if summarize:
        _auto_summary(out_path, tasks, mode, constrained)
    return {**result, "out": str(out_path)}


def main() -> None:
    p = argparse.ArgumentParser(description="Run the agentic-fit cross-lab matrix via OpenRouter")
    p.add_argument("--mode", choices=["assigned", "free"], default="assigned")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--only", default=None, help="comma-separated model ids to restrict to")
    p.add_argument("--sandbox", choices=["local", "docker"], default="docker")
    p.add_argument("--out", default=None)
    p.add_argument("--tasks-dir", default="tasks")
    p.add_argument("--max-spend", type=float, default=25.0)
    p.add_argument("--probe", action="store_true", help="cheap reps=1 validation pass")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true", help="skip the confirm-before-spend prompt")
    p.add_argument("--no-summary", action="store_true")
    p.add_argument("--constrained", default=None, help="constrained results file for the agreement metric")
    args = p.parse_args()
    execute_run(mode=args.mode, reps=1 if args.probe else args.reps, only=args.only,
                sandbox=args.sandbox, out=args.out, tasks_dir=args.tasks_dir,
                max_spend=args.max_spend, assume_yes=args.yes, dry_run=args.dry_run,
                summarize=not args.no_summary, constrained=args.constrained)


if __name__ == "__main__":
    main()
