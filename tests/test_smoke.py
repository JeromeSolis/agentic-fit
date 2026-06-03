from agentic_fit.smoke import (CheckResult, check_key, check_registry,
                               check_results_dir, holistic_smoke)


def test_check_key_missing(monkeypatch):
    from agentic_fit import smoke
    # Neutralize repo-local .env that load_dotenv would otherwise re-read.
    monkeypatch.setattr(smoke, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = check_key()
    assert r.ok is False
    assert "OPENROUTER_API_KEY" in r.message


def test_check_key_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-xxx")
    assert check_key().ok is True


def test_check_registry_clean():
    assert check_registry().ok is True


def test_check_results_dir_writable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert check_results_dir().ok is True


def test_holistic_smoke_reports_each_check(monkeypatch, tmp_path):
    from agentic_fit import smoke
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke, "check_model_ids",
                        lambda: CheckResult(True, "all 16 model ids resolved", "model_ids"))
    monkeypatch.setattr(smoke, "check_docker",
                        lambda: CheckResult(True, "docker reachable", "docker"))
    summary = holistic_smoke(skip_docker=False)
    names = [c.name for c in summary.checks]
    assert {"key", "registry", "model_ids", "docker", "results_dir"} <= set(names)
    assert summary.ok is True
