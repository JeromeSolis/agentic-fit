from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Candidate import-names that ship with CPython — no venv needed, no enforcement.
STDLIB = {
    "datetime", "dataclasses", "json", "os", "re", "math", "statistics",
    "urllib", "csv", "argparse", "string", "uuid", "hashlib", "sqlite3",
}

# Candidates whose import name differs from their PyPI distribution name.
IMPORT_TO_DIST = {
    "dateutil": "python-dateutil",
    "yaml": "pyyaml",
    "ruamel": "ruamel.yaml",
}

DEFAULT_CACHE = Path(".cache/venvs")


@dataclass
class VenvInfo:
    python: str
    version: str
    is_stdlib: bool


def _dist_name(library: str) -> str:
    return IMPORT_TO_DIST.get(library, library)


def _venv_python(venv_dir: Path) -> str:
    # Unix layout (bin/); the project targets macOS/Linux and requires uv.
    return str(venv_dir / "bin" / "python")


def _build_venv(library: str, venv_dir: Path) -> str:
    """Create an isolated venv with `library` (and pytest) installed; return its version.

    pytest is installed so the sandbox can run the hidden test inside the venv;
    it is neutral test infrastructure, not a competing candidate, so it does not
    weaken isolation. This is the one place that touches the real `uv` tool; the
    cache/reuse logic in ensure_venv is tested with a fake builder instead.
    """
    dist = _dist_name(library)
    subprocess.run(["uv", "venv", str(venv_dir), "-q"], check=True)
    py = _venv_python(venv_dir)
    subprocess.run(["uv", "pip", "install", "--python", py, "pytest", dist, "-q"], check=True)
    out = subprocess.run(
        [py, "-c", f"import importlib.metadata as m; print(m.version({dist!r}))"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def ensure_venv(
    library: str,
    cache_root: Path | None = DEFAULT_CACHE,
    builder: Callable[[str, Path], str] = _build_venv,
) -> VenvInfo:
    if library in STDLIB:
        v = f"py{sys.version_info.major}.{sys.version_info.minor}"
        return VenvInfo(python=sys.executable, version=v, is_stdlib=True)

    # Absolute so the interpreter path stays valid when the sandbox runs pytest
    # from a different working directory (cwd=tempdir).
    root = (Path(cache_root) if cache_root is not None else DEFAULT_CACHE).resolve()
    venv_dir = root / library
    marker = venv_dir / ".af_version"
    if marker.exists():
        return VenvInfo(python=_venv_python(venv_dir), version=marker.read_text().strip(), is_stdlib=False)

    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    version = builder(library, venv_dir)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(version)
    return VenvInfo(python=_venv_python(venv_dir), version=version, is_stdlib=False)


# Comprehensive stdlib filter: the curated STDLIB set (for candidate naming) plus
# every module CPython ships, so the unconstrained arm never tries to pip-install
# a stdlib module the agent happened to import.
STDLIB_ALL = set(sys.stdlib_module_names) | STDLIB


def _build_venv_multi(libraries: list[str], venv_dir: Path) -> str:
    dists = [_dist_name(lib) for lib in libraries]
    subprocess.run(["uv", "venv", str(venv_dir), "-q"], check=True)
    py = _venv_python(venv_dir)
    subprocess.run(["uv", "pip", "install", "--python", py, "pytest", *dists, "-q"], check=True)
    out = subprocess.run(
        [py, "-c",
         "import importlib.metadata as m, sys; "
         "print(','.join(f'{d}=={m.version(d)}' for d in sys.argv[1:]))",
         *dists],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def ensure_venv_for(
    libraries: list[str],
    cache_root: Path | None = DEFAULT_CACHE,
    builder: Callable[[list[str], Path], str] = _build_venv_multi,
) -> VenvInfo:
    third = sorted({lib for lib in libraries if lib not in STDLIB_ALL})
    if not third:
        v = f"py{sys.version_info.major}.{sys.version_info.minor}"
        return VenvInfo(python=sys.executable, version=v, is_stdlib=True)

    root = (Path(cache_root) if cache_root is not None else DEFAULT_CACHE).resolve()
    venv_dir = root / "+".join(third)  # single lib -> root/<lib>, shared with ensure_venv
    marker = venv_dir / ".af_version"
    if marker.exists():
        return VenvInfo(python=_venv_python(venv_dir), version=marker.read_text().strip(), is_stdlib=False)

    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    version = builder(third, venv_dir)
    # A single-lib set shares ensure_venv's cache dir/marker, so record the bare
    # version (e.g. "1.4.0") to match ensure_venv's format rather than "arrow==1.4.0".
    if len(third) == 1 and "==" in version:
        version = version.split("==", 1)[1]
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(version)
    return VenvInfo(python=_venv_python(venv_dir), version=version, is_stdlib=False)


def resolve_job_env(library: str, install_libraries: list[str] | None) -> VenvInfo:
    """Assigned mode (install_libraries is None) -> ensure_venv(library), unchanged.
    Free-choice mode (a list, possibly empty) -> ensure_venv_for that set."""
    if install_libraries is None:
        return ensure_venv(library)
    return ensure_venv_for(install_libraries)
