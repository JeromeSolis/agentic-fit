from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path

from .venvs import IMPORT_TO_DIST, STDLIB


def _dist(import_name: str) -> str:
    return IMPORT_TO_DIST.get(import_name, import_name)


def normalize_dist(dist: str) -> str:
    # PyPI canonical form used by pypistats URLs: lowercase, runs of -_. -> single "-".
    return re.sub(r"[-_.]+", "-", dist).lower()


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def fetch_recent_downloads(dist: str, getter: Callable[[str], dict] = _get_json) -> int:
    # pypistats rate-limits bulk callers (HTTP 429); retry with linear backoff.
    url = f"https://pypistats.org/api/packages/{normalize_dist(dist)}/recent"
    for attempt in range(5):
        try:
            return int(getter(url)["data"]["last_month"])
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(3 * (attempt + 1))  # 3, 6, 9, 12s
                continue
            raise
    raise RuntimeError("unreachable")


def load_popularity(
    import_names: Iterable[str],
    cache_path: str | Path,
    fetcher: Callable[[str], int] = fetch_recent_downloads,
    pause: float = 0.0,
) -> dict[str, int]:
    cache_path = Path(cache_path)
    if cache_path.exists():
        return json.loads(cache_path.read_text())["downloads"]

    third_party = [n for n in sorted(set(import_names)) if n not in STDLIB]
    downloads: dict[str, int] = {}
    for n in third_party:
        downloads[n] = fetcher(_dist(n))
        if pause:
            time.sleep(pause)  # space bulk requests so we don't trip the rate limit

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"snapshot_date": date.today().isoformat(), "downloads": downloads}, indent=2)
        + "\n"
    )
    return downloads
