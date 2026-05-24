from pathlib import Path

from agentic_fit.agent import FakeLLMClient, LLMResponse, run_agent
from agentic_fit.models import Task
from agentic_fit.sandbox import SandboxResult

FIX = Path(__file__).parent / "fixtures" / "sample_task"
TASK = Task(
    id="sample__add", category="sample",
    prompt="Write add(a, b) returning their sum.",
    candidate_libraries=("math",), solution_filename="solution.py",
    test_path=str(FIX / "test_solution.py"),
)

GOOD = "```python\ndef add(a, b):\n    return a + b\n```"
BAD = "```python\ndef add(a, b):\n    return a - b\n```"


def test_succeeds_first_try():
    client = FakeLLMClient([LLMResponse(GOOD, 100, 40)])
    r = run_agent(client, TASK, "math", "fake", rep=0)
    assert r.success is True
    assert r.iterations == 1
    assert r.input_tokens == 100
    assert r.output_tokens == 40


def test_succeeds_after_one_retry_accumulates_tokens():
    client = FakeLLMClient([LLMResponse(BAD, 100, 40), LLMResponse(GOOD, 120, 30)])
    r = run_agent(client, TASK, "math", "fake", rep=0, max_iters=3)
    assert r.success is True
    assert r.iterations == 2
    assert r.input_tokens == 220
    assert r.output_tokens == 70


def test_exhausts_iterations_and_fails():
    client = FakeLLMClient([LLMResponse(BAD, 10, 10)] * 3)
    r = run_agent(client, TASK, "math", "fake", rep=0, max_iters=3)
    assert r.success is False
    assert r.iterations == 3


class _FakeBackend:
    def __init__(self, result):
        self._result = result

    def run(self, job):
        return self._result


def test_run_agent_records_category_and_version():
    client = FakeLLMClient([LLMResponse(GOOD, 100, 40)])
    backend = _FakeBackend(SandboxResult(True, 1, 1, "", "", status="passed", version="1.2.3"))
    r = run_agent(client, TASK, "math", "fake", rep=0, backend=backend)
    assert r.category == "sample"
    assert r.version == "1.2.3"
    assert r.chosen_library is None
    assert r.status == "passed"


def test_run_agent_uses_backend_result_status_on_failure():
    client = FakeLLMClient([LLMResponse(GOOD, 10, 5)])
    backend = _FakeBackend(
        SandboxResult(False, 0, 0, "", "", status="import_not_used", version="9.9.9")
    )
    r = run_agent(client, TASK, "math", "fake", rep=0, max_iters=1, backend=backend)
    assert r.success is False
    assert r.version == "9.9.9"
    assert r.status == "import_not_used"


class _CapturingBackend:
    def __init__(self):
        self.jobs = []

    def run(self, job):
        self.jobs.append(job)
        return SandboxResult(True, 1, 1, "", "", status="passed", version="x")


class _RaisingBackend:
    def run(self, job):
        raise RuntimeError("container crashed")


def test_run_agent_records_error_on_backend_failure_without_crashing():
    client = FakeLLMClient([LLMResponse(GOOD, 10, 5)])
    r = run_agent(client, TASK, "math", "fake", rep=0, max_iters=3, backend=_RaisingBackend())
    assert r.success is False
    assert r.status == "error"
    assert "container crashed" in (r.error or "")


def test_run_agent_sets_enforce_import_from_stdlib_membership():
    # Third-party library -> enforce_import True; stdlib -> False. Verifies the
    # job built by run_agent carries the right enforcement flag and library.
    third = _CapturingBackend()
    run_agent(FakeLLMClient([LLMResponse(GOOD, 1, 1)]), TASK, "requests", "fake",
              rep=0, backend=third)
    assert third.jobs[-1].library == "requests"
    assert third.jobs[-1].enforce_import is True

    std = _CapturingBackend()
    run_agent(FakeLLMClient([LLMResponse(GOOD, 1, 1)]), TASK, "math", "fake",
              rep=0, backend=std)
    assert std.jobs[-1].enforce_import is False


FREE_REQ = "```python\nimport requests\n\ndef add(a, b):\n    return a + b\n```"


def test_run_agent_unconstrained_detects_choice_and_builds_install_set():
    jobs = []

    class _Cap:
        def run(self, job):
            jobs.append(job)
            return SandboxResult(True, 1, 1, "", "", status="passed", version="x")

    client = FakeLLMClient([LLMResponse(FREE_REQ, 10, 5)])
    r = run_agent(client, TASK, "", "fake", rep=0, mode="free_unconstrained", backend=_Cap())
    job = jobs[-1]
    assert job.install_libraries == ["requests"]   # detected from the solution
    assert job.enforce_import is False              # no enforcement in free modes
    assert job.competing_libraries == []
    assert r.chosen_library == "requests"


def test_run_agent_free_pure_stdlib_records_empty_install_set():
    jobs = []

    class _Cap:
        def run(self, job):
            jobs.append(job)
            return SandboxResult(True, 1, 1, "", "", status="passed", version="py3.12")

    client = FakeLLMClient([LLMResponse(GOOD, 10, 5)])  # GOOD imports nothing
    r = run_agent(client, TASK, "", "fake", rep=0, mode="free_constrained", backend=_Cap())
    assert jobs[-1].install_libraries == []          # no third-party -> empty set (base interp)
    assert r.chosen_library is None


FREE_MULTI = "```python\nimport requests\nimport arrow\n\ndef add(a, b):\n    return a + b\n```"
FREE_STDLIB_ONLY = "```python\nimport collections\n\ndef add(a, b):\n    return a + b\n```"


def _capturing():
    jobs = []

    class _Cap:
        def run(self, job):
            jobs.append(job)
            return SandboxResult(True, 1, 1, "", "", status="passed", version="x")

    return jobs, _Cap()


def test_run_agent_free_multi_import_joins_chosen():
    jobs, backend = _capturing()
    r = run_agent(FakeLLMClient([LLMResponse(FREE_MULTI, 10, 5)]), TASK, "", "fake",
                  rep=0, mode="free_unconstrained", backend=backend)
    assert jobs[-1].install_libraries == ["arrow", "requests"]  # sorted by imported_modules
    assert r.chosen_library == "arrow+requests"


def test_free_mode_system_prompt_drops_single_library_constraint():
    captured = {}

    class _CapClient:
        def complete(self, system, messages):
            captured["system"] = system
            return LLMResponse(GOOD, 1, 1)

    _, backend = _capturing()
    run_agent(_CapClient(), TASK, "math", "fake", rep=0, backend=backend)
    assert "ONLY the specified library" in captured["system"]  # assigned: constrained

    _, backend2 = _capturing()
    run_agent(_CapClient(), TASK, "", "fake", rep=0, mode="free_unconstrained", backend=backend2)
    assert "ONLY the specified library" not in captured["system"]  # free: not constrained


def test_run_agent_free_non_curated_stdlib_not_recorded_as_choice():
    # `collections` is stdlib but not in the curated STDLIB set; it must NOT leak into
    # chosen_library/install_libraries (the comprehensive filter excludes it).
    jobs, backend = _capturing()
    r = run_agent(FakeLLMClient([LLMResponse(FREE_STDLIB_ONLY, 10, 5)]), TASK, "", "fake",
                  rep=0, mode="free_unconstrained", backend=backend)
    assert jobs[-1].install_libraries == []
    assert r.chosen_library is None
