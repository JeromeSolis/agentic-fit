"""CLI shim. Logic lives in agentic_fit.smoke."""
from __future__ import annotations

from agentic_fit.smoke import holistic_smoke, render_smoke


def main() -> None:
    summary = holistic_smoke()
    for line in render_smoke(summary):
        print(line)
    raise SystemExit(0 if summary.ok else 1)


if __name__ == "__main__":
    main()
