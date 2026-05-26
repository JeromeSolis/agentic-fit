# Results data

Raw agentic-fit runs, one JSON object per line. **Snapshot: 2026-05** for models
`claude-sonnet-4-6` and `claude-haiku-4-5`. agentic-fit is model-specific and
tied to training cutoffs — read this as a point-in-time snapshot, not a current
or universal ranking.

## Files

| File | Experiment |
|---|---|
| `phase2_c1.jsonl` | C1 — assigned-library matrix, Sonnet |
| `phase2_c1_haiku.jsonl` | C1 — assigned-library matrix, Haiku |
| `c3_unconstrained_sonnet.jsonl` | C3 control arm — free choice, Sonnet |
| `c3_unconstrained_haiku.jsonl` | C3 control arm — free choice, Haiku |
| `c3_constrained_sonnet.jsonl` | C3 control arm — pick-from-candidates, Sonnet |
| `c3_constrained_haiku.jsonl` | C3 control arm — pick-from-candidates, Haiku |

C2 (novelty) has no data file of its own: it is derived from the C1 runs above
plus the PyPI download snapshot in `data/pypi_downloads.json`.

## Row schema

| Field | Meaning |
|---|---|
| `task_id` | task identifier (`<category>__<name>`) |
| `library` | the assigned library for this cell (empty in free-choice arms) |
| `rep` | repetition index |
| `model` | model id |
| `success` | did the solution pass the task's pytest gate |
| `status` | run outcome detail (e.g. `passed`, `import_not_used`, `error`); present in the C3 arm files |
| `tests_passed` / `tests_total` | test counts |
| `iterations` | agent attempts used (1 = first-try success) |
| `input_tokens` / `output_tokens` | cumulative tokens across iterations |
| `error` | failure detail if any (host paths redacted) |
| `category` | task category |
| `version` | resolved library version (or `py3.12` for stdlib) |
| `chosen_library` | in free-choice arms, what the agent actually imported |

## Cross-lab dataset (May 2026)

`crosslab_reps3_2026-05-25.jsonl` — the 8 task categories run across 16 models
from nine vendors, reps=3, every model routed through OpenRouter so the
measurement is identical. A snapshot of specific model versions; re-pin and
re-run with `scripts/fetch_openrouter_models.py` as models ship.

Additional row fields beyond the C1/C3 schema:

| Field | Meaning |
|---|---|
| `cost_usd` | tokens times the model's OpenRouter list price (the cross-lab cost metric) |
| `provider` | routing provider for the row (`openrouter`) |
| `status` | run outcome (`passed`, `failed`, `import_not_used`, `disallowed_import`, `collection_error`, `error`) |
