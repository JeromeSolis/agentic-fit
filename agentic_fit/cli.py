from __future__ import annotations

import argparse
import re

from .backends import DockerBackend, LocalBackend, SandboxBackend
from .crosslab import execute_run

_RESULTS_NAME = re.compile(
    r"crosslab_(?P<mode>assigned|free)_reps(?P<reps>\d+)_(?P<date>\d{4}-\d{2}-\d{2})(?:-\d+)?\.jsonl$"
)

_INFO_PARAGRAPH = (
    "agentic-fit measures which Python library a coding agent uses most reliably and at "
    "the lowest cost, for a given model. It compares candidate libraries head-to-head per "
    "task category, in an isolated sandbox, and records success and cost per "
    "(library × model). Live explorer: https://jeromesolis.github.io/agentic-fit/."
)


def select_backend(name: str) -> SandboxBackend:
    return DockerBackend() if name == "docker" else LocalBackend()


def _add_run(sub) -> None:
    r = sub.add_parser("run", help="run the cross-lab benchmark")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--free", action="store_const", dest="mode", const="free")
    g.add_argument("--assigned", action="store_const", dest="mode", const="assigned")
    r.add_argument("--reps", type=int, default=3)
    r.add_argument("--probe", action="store_true", help="cheap reps=1 validation pass")
    r.add_argument("--only", default=None, help="comma-separated model ids to restrict to")
    r.add_argument("--sandbox", choices=["local", "docker"], default="docker")
    r.add_argument("--out", default=None)
    r.add_argument("--tasks-dir", default="tasks")
    r.add_argument("--max-spend", type=float, default=25.0)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--yes", action="store_true", help="skip the confirm-before-spend prompt")
    r.add_argument("--no-summary", action="store_true")
    r.add_argument("--constrained", default=None)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentic-fit", description="agentic-fit benchmark CLI")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("info", help="orientation: what is this benchmark")
    sub.add_parser("tasks", help="list categories with their summaries and candidate libraries")
    res = sub.add_parser("results", help="list past run files or inspect one")
    res.add_argument("inspect_action", nargs="?", choices=["inspect"], default=None)
    res.add_argument("file", nargs="?")
    res.add_argument("--json", action="store_true", dest="as_json")
    _add_run(sub)
    sp = sub.add_parser("summarize", help="summarize a results file")
    sp.add_argument("free_path")
    sp.add_argument("--tasks-dir", default="tasks")
    sp.add_argument("--constrained", default=None)
    sp.add_argument("--json", action="store_true", dest="as_json")
    sm = sub.add_parser("smoke", help="validate OPENROUTER_API_KEY, model ids, Docker, registry, results dir")
    sm.add_argument("--no-docker", action="store_true")
    m = sub.add_parser("models", help="list the pinned registry")
    m.add_argument("--refresh", action="store_true")
    c = sub.add_parser("curate", help="curate a results file for publishing")
    c.add_argument("src")
    c.add_argument("dst")
    return p


def _handle_info(ns) -> None:
    from pathlib import Path
    from .crosslab_models import CROSSLAB_MODELS
    from .loader import load_tasks
    cats = sorted({t.category for t in load_tasks(Path("tasks"))})
    print(_INFO_PARAGRAPH)
    print()
    print(f"Categories ({len(cats)}): " + ", ".join(cats))
    print(f"Models ({len(CROSSLAB_MODELS)}): see `agentic-fit models`")
    print()
    print("Two modes:")
    print("  --free       each model picks its own library (the free-choice signal)")
    print("  --assigned   sweep each candidate library per model (the constrained head-to-head)")
    print("Free runs cost about one third of assigned runs.")
    print()
    print("First steps:")
    print("  agentic-fit smoke                                          validate setup")
    print("  agentic-fit run --free --dry-run                           estimate cost")
    print("  agentic-fit run --free --probe --sandbox docker --yes      cheap probe")


def _handle_run(ns) -> None:
    if ns.mode is None:
        import sys
        print("pick a mode: --free (model picks its own library) or "
              "--assigned (sweep each candidate). See 'agentic-fit info'.",
              file=sys.stderr)
        raise SystemExit(2)
    execute_run(mode=ns.mode, reps=1 if ns.probe else ns.reps, only=ns.only,
                sandbox=ns.sandbox, out=ns.out, tasks_dir=ns.tasks_dir,
                max_spend=ns.max_spend, assume_yes=ns.yes, dry_run=ns.dry_run,
                summarize=not ns.no_summary, constrained=ns.constrained)


def _handle_summarize(ns) -> None:
    from pathlib import Path
    from .loader import load_tasks
    from .scoring import crosslab_best, load_results, score_crosslab
    from .summary import default_tax, render_default_tax, render_summary, summarize
    rows = load_results(Path(ns.free_path))
    candidate_sets = {t.category: set(t.candidate_libraries) for t in load_tasks(Path(ns.tasks_dir))}
    constrained_rows = constrained_best = None
    if ns.constrained:
        constrained_rows = load_results(Path(ns.constrained))
        best = crosslab_best(score_crosslab(constrained_rows))
        constrained_best = {k: v.library for k, v in best.items()}
    s = summarize(rows, candidate_sets, constrained_best)
    tax = default_tax(rows, candidate_sets, constrained_rows) if constrained_rows else None
    if ns.as_json:
        import json
        payload = {"summary": s, **({"default_tax": tax} if tax else {})}
        print(json.dumps(payload, indent=2))
        return
    for line in render_summary(s):
        print(line)
    if tax:
        print()
        for line in render_default_tax(tax):
            print(line)


def _handle_models(ns) -> None:
    import subprocess
    import sys
    if ns.refresh:
        raise SystemExit(subprocess.call([sys.executable, "scripts/fetch_openrouter_models.py"]))
    from .crosslab_models import CROSSLAB_MODELS
    for s in CROSSLAB_MODELS:
        print(f"{s.model_id:40s} {s.provider}")


def _handle_tasks(ns) -> None:
    from pathlib import Path
    from .loader import load_tasks
    from .tasks_meta import SUMMARIES
    for t in sorted(load_tasks(Path("tasks")), key=lambda t: t.category):
        summary = SUMMARIES.get(t.category, "")
        libs = ", ".join(t.candidate_libraries)
        print(t.category)
        if summary:
            print(f"  {summary}")
        print(f"  candidates: {libs}")


def _list_results_files(results_dir):
    from .scoring import load_results
    out = []
    if not results_dir.exists():
        return out
    for f in sorted(results_dir.glob("crosslab_*.jsonl"), reverse=True):
        m = _RESULTS_NAME.search(f.name)
        if not m:
            continue
        rows = load_results(f)
        out.append({
            "file": f.name,
            "mode": m.group("mode"),
            "date": m.group("date"),
            "reps": int(m.group("reps")),
            "n_cells": len(rows),
            "total_cost": round(sum(r.cost_usd or 0.0 for r in rows), 2),
        })
    return out


def _inspect_results_file(path, as_json=False):
    import json
    from pathlib import Path
    from .loader import load_tasks
    from .scoring import load_results
    from .summary import render_summary, summarize
    rows = load_results(path)
    candidate_sets = {t.category: set(t.candidate_libraries) for t in load_tasks(Path("tasks"))}
    s = summarize(rows, candidate_sets)
    if as_json:
        print(json.dumps(s, indent=2))
        return
    for line in render_summary(s):
        print(line)


def _handle_results(ns) -> None:
    import json
    from pathlib import Path
    if ns.inspect_action == "inspect":
        if not ns.file:
            raise SystemExit("usage: agentic-fit results inspect <file>")
        _inspect_results_file(Path(ns.file), as_json=ns.as_json)
        return
    rows = _list_results_files(Path("results"))
    if ns.as_json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("no results files in results/.")
        return
    print(f"{'file':50s} {'mode':9s} {'date':12s} {'cells':>6s} {'cost':>8s}")
    for r in rows:
        print(f"{r['file']:50s} {r['mode']:9s} {r['date']:12s} {r['n_cells']:>6d} ${r['total_cost']:>7.2f}")


def _handle_smoke(ns) -> None:
    from .smoke import holistic_smoke, render_smoke
    summary = holistic_smoke(skip_docker=ns.no_docker)
    for line in render_smoke(summary):
        print(line)
    raise SystemExit(0 if summary.ok else 1)


def _handle_script(script: str, *script_args: str) -> None:
    import subprocess
    import sys
    raise SystemExit(subprocess.call([sys.executable, f"scripts/{script}", *script_args]))


def main(argv: list[str] | None = None) -> None:
    ns = build_parser().parse_args(argv)
    if ns.cmd is None or ns.cmd == "info":
        _handle_info(ns)
        return
    if ns.cmd == "run":
        _handle_run(ns)
    elif ns.cmd == "summarize":
        _handle_summarize(ns)
    elif ns.cmd == "models":
        _handle_models(ns)
    elif ns.cmd == "smoke":
        _handle_smoke(ns)
    elif ns.cmd == "tasks":
        _handle_tasks(ns)
    elif ns.cmd == "results":
        _handle_results(ns)
    elif ns.cmd == "curate":
        _handle_script("curate_results.py", ns.src, ns.dst)


if __name__ == "__main__":
    main()
