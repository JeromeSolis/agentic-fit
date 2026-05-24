from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_fit.popularity import (
    fetch_recent_downloads,
    load_popularity,
    normalize_dist,
)


def test_normalize_dist_canonicalizes_for_pypistats():
    assert normalize_dist("ruamel.yaml") == "ruamel-yaml"
    assert normalize_dist("python-dateutil") == "python-dateutil"
    assert normalize_dist("PyYAML") == "pyyaml"


def test_load_popularity_maps_imports_skips_stdlib_and_caches(tmp_path):
    calls = []

    # load_popularity passes the DIST name (via IMPORT_TO_DIST) to the fetcher:
    # yaml->pyyaml, ruamel->ruamel.yaml, requests->requests. (URL normalization to
    # "ruamel-yaml" happens only inside the real fetch_recent_downloads.)
    def fake_fetcher(dist):
        calls.append(dist)
        return {"requests": 1000, "pyyaml": 500, "ruamel.yaml": 200}[dist]

    cache = tmp_path / "pop.json"
    # "datetime" is stdlib -> excluded entirely
    names = ["requests", "yaml", "ruamel", "datetime"]
    pop = load_popularity(names, cache, fetcher=fake_fetcher)

    assert pop == {"requests": 1000, "yaml": 500, "ruamel": 200}
    assert "datetime" not in pop
    assert sorted(calls) == ["pyyaml", "requests", "ruamel.yaml"]  # dist names, stdlib skipped
    assert cache.exists()
    snapshot = json.loads(cache.read_text())
    assert "snapshot_date" in snapshot and snapshot["downloads"] == pop


def test_load_popularity_reuses_cache_without_fetching(tmp_path):
    cache = tmp_path / "pop.json"
    cache.write_text(json.dumps({"snapshot_date": "2026-05-23", "downloads": {"requests": 7}}))

    def boom(dist):
        raise AssertionError("should not fetch when cache exists")

    assert load_popularity(["requests"], cache, fetcher=boom) == {"requests": 7}


def test_fetch_recent_downloads_retries_on_429(monkeypatch):
    import urllib.error

    monkeypatch.setattr("agentic_fit.popularity.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def flaky_getter(url):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", None, None)
        return {"data": {"last_month": 4242}}

    assert fetch_recent_downloads("requests", getter=flaky_getter) == 4242
    assert calls["n"] == 2  # retried once after the 429


@pytest.mark.slow
def test_fetch_recent_downloads_real():
    import urllib.error

    from agentic_fit.popularity import fetch_recent_downloads

    try:
        n = fetch_recent_downloads("requests")
    except urllib.error.URLError:
        pytest.skip("no network")
    assert isinstance(n, int) and n > 0
