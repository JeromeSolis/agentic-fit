from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    prompt: str
    candidate_libraries: tuple[str, ...]
    solution_filename: str
    test_path: str
    difficulty: str = "easy"


@dataclass
class RunResult:
    task_id: str
    library: str
    rep: int
    model: str
    success: bool
    tests_passed: int
    tests_total: int
    iterations: int
    input_tokens: int
    output_tokens: int
    error: str | None = None
    category: str = ""
    version: str | None = None
    chosen_library: str | None = None  # reserved for the C3 free-choice arm; unset for now
    status: str = ""  # final SandboxResult.status: passed/failed/collection_error/timeout/import_not_used/...
    cost_usd: float | None = None  # tokens * unified OpenRouter list price (budget.run_cost)
    provider: str = ""             # "anthropic" | "openrouter"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, line: str) -> "RunResult":
        return cls(**json.loads(line))
