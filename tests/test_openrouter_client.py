import httpx
import openai
import pytest

from agentic_fit.agent import OpenRouterClient, LLMResponse


class _Msg:
    def __init__(self, content): self.message = type("M", (), {"content": content})


class _Usage:
    def __init__(self, p, c): self.prompt_tokens = p; self.completion_tokens = c


class _Resp:
    def __init__(self, text, p, c): self.choices = [_Msg(text)]; self.usage = _Usage(p, c)


def _client_with(create):
    c = OpenRouterClient.__new__(OpenRouterClient)   # bypass __init__/network
    c._model = "vendor/model"
    c._max_tokens = 256
    c._client = type("FakeOpenAI", (), {"chat": type("C", (), {"completions": type("Co", (), {"create": staticmethod(create)})()})()})()
    return c


def test_parses_text_and_tokens():
    def create(**kw): return _Resp("hello", 12, 7)
    r = _client_with(create).complete("sys", [{"role": "user", "content": "hi"}])
    assert isinstance(r, LLMResponse)
    assert r.text == "hello" and r.input_tokens == 12 and r.output_tokens == 7


def test_handles_missing_usage_and_choices():
    class _NoUsage:
        choices = []
        usage = None
    def create(**kw): return _NoUsage()
    r = _client_with(create).complete("sys", [{"role": "user", "content": "hi"}])
    assert r.text == "" and r.input_tokens == 0 and r.output_tokens == 0


def test_folds_system_into_user_on_bad_request():
    calls = []
    def create(**kw):
        calls.append(kw["messages"])
        if len(calls) == 1:
            raise openai.BadRequestError(
                "system role not supported",
                response=httpx.Response(400, request=httpx.Request("POST", "http://x")),
                body=None,
            )
        return _Resp("ok", 1, 1)
    r = _client_with(create).complete("SYSPROMPT", [{"role": "user", "content": "hi"}])
    assert r.text == "ok"
    assert len(calls) == 2
    assert calls[0][0]["role"] == "system"
    assert all(m["role"] != "system" for m in calls[1])
    assert "SYSPROMPT" in calls[1][0]["content"]


def test_client_configured_with_retries_and_timeout(monkeypatch):
    import agentic_fit.agent as agent_mod
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    agent_mod.OpenRouterClient("vendor/model")
    assert captured["max_retries"] == 6
    assert captured["timeout"] == 120.0
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["api_key"] == "test-key"
