import subprocess

import agentic_fit.backends as backends


def test_docker_available_true_on_zero_exit(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, b"", b""))
    assert backends.docker_available() is True


def test_docker_available_false_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1, b"", b"err"))
    assert backends.docker_available() is False


def test_docker_available_false_when_docker_missing(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("docker not found")
    monkeypatch.setattr(subprocess, "run", boom)
    assert backends.docker_available() is False


def test_docker_available_false_on_timeout(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="docker", timeout=15)
    monkeypatch.setattr(subprocess, "run", boom)
    assert backends.docker_available() is False
