"""Interpretation of what library a run chose, derived from captured imports.

Kept separate from the harness so the (expensive) run records raw evidence and
every interpretation question is answered offline, re-runnably. Callers pass the
canonical stdlib set (agentic_fit.venvs.STDLIB_ALL); this module trusts it.
"""
from __future__ import annotations

from collections.abc import Iterable


def effective_pick(
    imports: list[str] | None,
    candidate_libraries: Iterable[str],
    stdlib_set: set[str],
    *,
    fallback: str | None = None,
) -> str | None:
    """The library a solution effectively chose.

    Non-stdlib imports count, plus stdlib modules that are candidates for the task
    (argparse/dataclasses/datetime). Returns None for a pure-stdlib solution, or a
    "+"-joined sorted string when several libraries were used. When `imports` is
    None (not captured, e.g. pre-refactor data), returns `fallback`.
    """
    if imports is None:
        return fallback
    cands = set(candidate_libraries)
    picked = sorted({m for m in imports if m not in stdlib_set or m in cands})
    return "+".join(picked) if picked else None


def kind(pick: str | None, stdlib_set: set[str]) -> str:
    """'builtin' if the pick is pure standard library, else 'community'."""
    if pick is None:
        return "builtin"
    return "builtin" if all(part in stdlib_set for part in pick.split("+")) else "community"
