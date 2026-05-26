from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from .backends import LocalBackend, SandboxBackend, SandboxJob
from .budget import run_cost
from .imports import imported_modules
from .models import RunResult, Task
from .sandbox import SandboxResult
from .venvs import STDLIB, STDLIB_ALL

SYSTEM = (
    "You are a Python coding agent. Solve the task using ONLY the specified "
    "library plus the Python standard library. Output a single complete Python "
    "file inside one ```python code block. Define everything the tests need."
)

# Free-choice modes must NOT carry the "ONLY the specified library" constraint —
# that would contradict the free-choice user prompt and bias the control arms.
SYSTEM_FREE = (
    "You are a Python coding agent. Solve the task as described. Output a single "
    "complete Python file inside one ```python code block. Define everything the "
    "tests need."
)

_CODE_BLOCK = re.compile(r"```(?:python)?\n(.*?)```", re.DOTALL)


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    def complete(self, system: str, messages: list[dict]) -> LLMResponse: ...


class FakeLLMClient:
    """Returns canned responses in order; for tests only."""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, system: str, messages: list[dict]) -> LLMResponse:
        resp = self._responses[self.calls]
        self.calls += 1
        return resp


class AnthropicClient:
    def __init__(self, model: str, max_tokens: int = 4096):
        import anthropic

        self._client = anthropic.Anthropic()
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system: str, messages: list[dict]) -> LLMResponse:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[{"type": "text", "text": system,
                     "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        usage = resp.usage
        input_tokens = (
            usage.input_tokens
            + (usage.cache_read_input_tokens or 0)
            + (usage.cache_creation_input_tokens or 0)
        )
        return LLMResponse(text, input_tokens, usage.output_tokens)


class OpenRouterClient:
    """LLMClient over OpenRouter (OpenAI-compatible). Returns text + token counts.

    Cost is NOT read from OpenRouter here; it is computed downstream from the
    unified price table, so every model is priced on the same basis.
    """

    def __init__(self, model: str, max_tokens: int = 4096):
        import os

        from openai import OpenAI

        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            max_retries=6,   # SDK retries connection errors / 429 / 5xx with exponential backoff
            timeout=120.0,   # per-request ceiling so a hung call can't stall an overnight run
        )
        self._model = model
        self._max_tokens = max_tokens

    @staticmethod
    def _with_system(system: str, messages: list[dict], fold: bool) -> list[dict]:
        if not fold:
            return [{"role": "system", "content": system}, *messages]
        # Fold system text into the first user message for models without a system role.
        out = [dict(m) for m in messages]
        if out and out[0].get("role") == "user":
            out[0]["content"] = f"{system}\n\n{out[0]['content']}"
        else:
            out.insert(0, {"role": "user", "content": system})
        return out

    def _create(self, msgs: list[dict]):
        return self._client.chat.completions.create(
            model=self._model, max_tokens=self._max_tokens, messages=msgs
        )

    def complete(self, system: str, messages: list[dict]) -> LLMResponse:
        import openai

        try:
            resp = self._create(self._with_system(system, messages, fold=False))
        except openai.BadRequestError:
            # Likely an unsupported system role/param; retry once with system folded in.
            resp = self._create(self._with_system(system, messages, fold=True))
        text = (resp.choices[0].message.content if resp.choices else "") or ""
        usage = resp.usage
        in_tok = (getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        out_tok = (getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        return LLMResponse(text, in_tok, out_tok)


_CLIENTS = {"anthropic": AnthropicClient, "openrouter": OpenRouterClient}


def make_client(provider: str, model: str) -> LLMClient:
    try:
        cls = _CLIENTS[provider]
    except KeyError:
        raise ValueError(f"unknown provider: {provider!r}")
    return cls(model=model)


def extract_code(text: str) -> str:
    m = _CODE_BLOCK.search(text)
    return m.group(1).strip() if m else text.strip()


def _user_prompt(task: Task, library: str, mode: str) -> str:
    if mode == "free_unconstrained":
        return (f"Task:\n{task.prompt}\n\nSolve it using any Python library you "
                f"choose. Write your solution as `solution.py`.")
    if mode == "free_constrained":
        opts = ", ".join(f"`{c}`" for c in task.candidate_libraries)
        return (f"Task:\n{task.prompt}\n\nSolve it using whichever of these "
                f"libraries you prefer: {opts}. Write your solution as `solution.py`.")
    return (f"Task:\n{task.prompt}\n\nYou MUST use the `{library}` library (plus the "
            f"Python standard library) and no other third-party library. Write your "
            f"solution as `solution.py`.")


def run_agent(
    client: LLMClient,
    task: Task,
    library: str,
    model: str,
    rep: int,
    max_iters: int = 3,
    *,
    mode: Literal["assigned", "free_unconstrained", "free_constrained"] = "assigned",
    backend: SandboxBackend | None = None,
    provider: str = "",
) -> RunResult:
    backend = backend or LocalBackend()
    free = mode != "assigned"
    system = SYSTEM_FREE if free else SYSTEM
    competing = [] if free else list(task.candidate_libraries)
    enforce = (not free) and (library not in STDLIB)
    test_code = Path(task.test_path).read_text()
    messages: list[dict] = [{"role": "user", "content": _user_prompt(task, library, mode)}]
    in_tok = out_tok = 0
    last = None
    chosen: str | None = None

    for i in range(1, max_iters + 1):
        try:
            resp = client.complete(system, messages)
        except Exception as exc:
            # Provider/API failure (rate limit, null usage, malformed response, etc.).
            # Record a per-cell error and stop, so one bad cell can't crash a whole
            # multi-model run. Not LLM-fixable.
            return RunResult(task.id, library, rep, model, False, 0, 0, i, in_tok, out_tok,
                             error=f"client error: {exc}"[:200], category=task.category,
                             status="error", chosen_library=chosen,
                             cost_usd=run_cost(model, in_tok, out_tok), provider=provider)
        in_tok += resp.input_tokens
        out_tok += resp.output_tokens
        code = extract_code(resp.text)
        if free:
            # Filter with the comprehensive stdlib set (same one ensure_venv_for uses),
            # so chosen_library/install_libraries never record a stdlib module as a "choice".
            detected = [m for m in imported_modules(code) if m not in STDLIB_ALL]
            install: list[str] | None = detected
            if not detected:
                chosen = None
            elif len(detected) == 1:
                chosen = detected[0]
            else:
                chosen = "+".join(detected)
        else:
            install = None
        job = SandboxJob(solution_code=code, test_code=test_code, library=library,
                         competing_libraries=competing, enforce_import=enforce,
                         install_libraries=install)
        try:
            last = backend.run(job)
        except Exception as exc:
            # Backend/infra failure (e.g. a crashed container) — record it and stop
            # so one bad cell can't crash the whole matrix run. Not LLM-fixable.
            last = SandboxResult(False, 0, 0, "", str(exc)[:300], status="error")
            break
        if last.passed:
            return RunResult(task.id, library, rep, model, True,
                             last.tests_passed, last.tests_total, i, in_tok, out_tok,
                             category=task.category, version=last.version,
                             status=last.status, chosen_library=chosen,
                             cost_usd=run_cost(model, in_tok, out_tok), provider=provider)
        messages.append({"role": "assistant", "content": resp.text})
        retry = "Fix solution.py." if free else f"Fix solution.py. Still use only `{library}`."
        messages.append({"role": "user", "content":
            f"The tests failed:\n{last.stdout[-1500:]}\n{last.stderr[-500:]}\n{retry}"})

    return RunResult(task.id, library, rep, model, False,
                     last.tests_passed, last.tests_total, max_iters,
                     in_tok, out_tok, error=(last.stderr or "tests failed")[:200],
                     category=task.category, version=last.version,
                     status=last.status, chosen_library=chosen,
                     cost_usd=run_cost(model, in_tok, out_tok), provider=provider)
