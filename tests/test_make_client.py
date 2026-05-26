import pytest

from agentic_fit import agent


def test_make_client_routes_by_provider(monkeypatch):
    made = {}

    class FakeA:
        def __init__(self, model): made["anthropic"] = model

    class FakeO:
        def __init__(self, model): made["openrouter"] = model

    monkeypatch.setattr(agent, "_CLIENTS", {"anthropic": FakeA, "openrouter": FakeO})
    assert isinstance(agent.make_client("anthropic", "claude-x"), FakeA)
    assert isinstance(agent.make_client("openrouter", "openai/y"), FakeO)
    assert made == {"anthropic": "claude-x", "openrouter": "openai/y"}


def test_make_client_rejects_unknown_provider():
    with pytest.raises(ValueError, match="unknown provider"):
        agent.make_client("nope", "m")
