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
