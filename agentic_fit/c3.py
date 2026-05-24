from __future__ import annotations

import argparse
import time
from pathlib import Path

from dotenv import load_dotenv

from .agent import AnthropicClient
from .cli import _make_reporter, select_backend
from .loader import load_tasks
from .runner import run_control_arm


def arm_mode_and_out(arm: str, model: str) -> tuple[str, str]:
    mode = "free_unconstrained" if arm == "unconstrained" else "free_constrained"
    # Use a known family nickname; fall back to the full model so an unexpected
    # model is never silently mislabeled (e.g. opus -> "sonnet").
    short = next((n for n in ("haiku", "sonnet", "opus") if n in model), model)
    return mode, f"results/c3_{arm}_{short}.jsonl"


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="Run a C3 control arm (free-choice)")
    p.add_argument("--arm", choices=["unconstrained", "constrained"], required=True)
    p.add_argument("--tasks-dir", default="tasks")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--reps", type=int, default=5)
    p.add_argument("--max-spend", type=float, default=15.0)
    p.add_argument("--sandbox", choices=["local", "docker"], default="docker")
    args = p.parse_args()

    tasks = load_tasks(Path(args.tasks_dir))
    mode, out = arm_mode_and_out(args.arm, args.model)
    print(f"c3 control: arm={args.arm} mode={mode} model={args.model} "
          f"reps={args.reps} sandbox={args.sandbox} -> {out}", flush=True)

    start = time.monotonic()
    client = AnthropicClient(model=args.model)
    run_control_arm(client, tasks, args.model, args.reps, Path(out), mode,
                    backend=select_backend(args.sandbox),
                    max_spend=args.max_spend, on_result=_make_reporter(start))
    elapsed = int(time.monotonic() - start)
    print(f"done: arm={args.arm} · {elapsed // 60}m{elapsed % 60:02d}s · results -> {out}")


if __name__ == "__main__":
    main()
