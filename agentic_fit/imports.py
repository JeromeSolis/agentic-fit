from __future__ import annotations

import ast
from collections.abc import Iterable


def imported_modules(code: str) -> list[str]:
    """Return all distinct top-level module names `code` imports (absolute only).

    Unlike used_candidates, this is not limited to a candidate set — it is how the
    free-choice arms discover whatever library the agent actually reached for.
    """
    found: set[str] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return sorted(found)


def used_candidates(code: str, candidates: Iterable[str]) -> list[str]:
    """Return the sorted subset of `candidates` that `code` imports.

    Matches on the top-level module name, so `from dateutil.parser import parse`
    counts as using `dateutil` and `import httpx as h` counts as `httpx`.
    """
    cand = set(candidates)
    found: set[str] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in cand:
                    found.add(top)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top = node.module.split(".")[0]
            if top in cand:
                found.add(top)
    return sorted(found)
