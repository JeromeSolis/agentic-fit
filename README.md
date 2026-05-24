# agentic-fit

**agentic-fit** is a benchmark that measures how efficiently a coding agent uses a given Python library, expressed as token-cost-to-success and first-try success rate per `(library × version × model)`. For each task category it runs the agent once per candidate library in a fully isolated environment, scores the output with a pytest gate, and records token usage. The result is a per-model, per-library efficiency profile rather than a single aggregate score.

---

## Motivation

The bigger question behind this project is how we build a positive feedback loop between AI agents and the people whose work those agents depend on. Agents lean heavily on original human content to function: documentation, open-source libraries, and the writing that ties everything together. The people who produce and maintain that material carry the cost of it, yet the channels that used to reward good work have not kept pace with the value agents now pull from it.

There is a useful precedent in how the web learned to rank itself. Early search engines mostly counted keywords and raw links, and PageRank's contribution was to treat the link graph as a richer signal of which pages were genuinely valuable, going beyond raw popularity. Software has its own raw-popularity signals in download counts and GitHub stars, and they matter doubly for AI agents. The most adopted libraries are also the most written about, so they dominate the tutorials, documentation, and source code that models train on. An agent's instinct to reach for a particular library is shaped as much by what filled its training corpus as by what fits the task in front of it, which makes popularity quietly self-reinforcing. Yet raw popularity turns out not to predict how efficiently an agent actually uses a library (see the findings below), so a signal derived from behavior captures something the counts miss.

That corner is what this benchmark measures, and it is deliberately a modest one. The deeper worry is what this dynamic does to innovation. If agents keep reaching for whatever is already popular and well-represented in their training data, a genuinely better library that arrives later starts at a disadvantage regardless of its quality, and the people who might build the next good thing have less reason to try. The question worth sitting with is how we keep innovation flowing: how to motivate developers to create better libraries and better content, and how to close a positive feedback loop in which agents surface and reward the work that serves them best. agentic-fit does not solve that. What it offers is a repeatable, model-specific reading of how agents behave, one that can be rerun as new models ship, so the conversation about that loop rests on measurement rather than intuition alone.

---

## Quickstart

```bash
uv sync
cp .env.example .env        # set ANTHROPIC_API_KEY
uv run agentic-fit --model claude-sonnet-4-6 --reps 5 --out results/run.jsonl
```

Add `--sandbox docker` to run each generated solution in a hardened container (build it from the `Dockerfile` first).

---

## The task set

Eight categories, each testing agent competence with a specific class of Python library:

| Category | What it tests |
|---|---|
| `cli_parsing` | Parsing named command-line options with a required argument and an integer default (argparse, click, typer) |
| `data_validation` | Validating and coercing a flat user record with type conversion and error raising (pydantic, marshmallow, dataclasses) |
| `data_validation_hard` | Validating a nested order dict with per-item coercion and field-level error conditions, a harder nested-schema variant (pydantic, marshmallow, dataclasses) |
| `date_handling` | Parsing a human date/time string and returning an ISO-8601 UTC string, with error on unparseable input (datetime, dateutil, arrow) |
| `http_client` | Making an HTTP GET, parsing the JSON body, and returning a named field, raising on non-200 status (requests, httpx, urllib3) |
| `retrying` | Wrapping a callable with up to 3 retry attempts on ValueError, re-raising after exhaustion, using a retry library (tenacity, backoff, stamina) |
| `templating` | Rendering a title and a list of items to a formatted string using a templating library, not string concatenation (jinja2, mako, chevron) |
| `yaml_config` | Parsing two YAML documents and deep-merging them with override semantics for conflicting keys (yaml/PyYAML, ruamel.yaml, omegaconf) |

---

## Findings summary

Snapshot: **May 2026** | Models: **`claude-sonnet-4-6`**, **`claude-haiku-4-5`**

| Claim | Result |
|---|---|
| **C1, variance is real** | Within-category token spread up to 3.97× (Sonnet) and 11.86× (Haiku); the cheapest library inverts between models in 3 of 7 categories |
| **C2, not explained by popularity** | 50% pooled pairwise concordance with PyPI download rank (chance level); 7 cross-model inversions that a static popularity signal cannot produce |
| **C3, actionable for weaker models** | Steering Haiku to the model-specific cheapest library saves ~36% tokens; steering Sonnet saves ~0% (it already self-selects efficiently) |

Full methodology, per-category numbers, and caveats: [`docs/FINDINGS.md`](docs/FINDINGS.md)

Raw results: [`results/`](results/). See [`results/README.md`](results/README.md) for the schema.

---

## License

MIT. See [`LICENSE`](LICENSE).
