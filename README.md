# agentic-fit

**agentic-fit** is a benchmark that measures, for a given model, which Python library a coding agent uses most reliably and at the lowest cost. For each task category it runs the agent once per candidate library in an isolated environment, scores the output with a pytest gate, and records success and cost per `(library × model)`. The result is a per-model, per-library profile of which library to reach for in each category.

**Live explorer** ([jeromesolis.github.io/agentic-fit](https://jeromesolis.github.io/agentic-fit/)): pick a task, flip between cost and success rate, and see which library each model uses best.

---

## Motivation

The bigger question behind this project is how we build a positive feedback loop between AI agents and the people whose work those agents depend on. Agents lean heavily on original human content to function: documentation, open-source libraries, and the writing that ties everything together. The people who produce and maintain that material carry the cost of it, yet the channels that used to reward good work have not kept pace with the value agents now pull from it.

There is a useful precedent in how the web learned to rank itself. Early search engines mostly counted keywords and raw links, and PageRank's contribution was to treat the link graph as a richer signal of which pages were genuinely valuable, going beyond raw popularity. Software has its own raw-popularity signals in download counts and GitHub stars, and they matter doubly for AI agents. The most adopted libraries are also the most written about, so they dominate the tutorials, documentation, and source code that models train on. An agent's instinct to reach for a particular library is shaped as much by what filled its training corpus as by what fits the task in front of it, which makes popularity quietly self-reinforcing. Yet raw popularity turns out not to predict how efficiently an agent actually uses a library (see the findings below), so a signal derived from behavior captures something the counts miss.

That corner is what this benchmark measures, and it is deliberately a modest one. The deeper worry is what this dynamic does to innovation. If agents keep reaching for whatever is already popular and well-represented in their training data, a genuinely better library that arrives later starts at a disadvantage regardless of its quality, and the people who might build the next good thing have less reason to try. The question worth sitting with is how we keep innovation flowing: how to motivate developers to create better libraries and better content, and how to close a positive feedback loop in which agents surface and reward the work that serves them best. agentic-fit does not solve that. What it offers is a repeatable, model-specific reading of how agents behave, one that can be rerun as new models ship, so the conversation about that loop rests on measurement rather than intuition alone.

---

## Quickstart

```bash
uv sync
cp .env.example .env        # set OPENROUTER_API_KEY
python -m agentic_fit.crosslab --dry-run      # the model set and a cost estimate
python -m agentic_fit.crosslab --reps 3 --sandbox docker
```

A full 16-model run costs roughly $16 of OpenRouter credit, so trim `agentic_fit/crosslab_models.py` to a subset for a cheaper pass. `python scripts/smoke_openrouter.py` validates your key and that the model ids resolve first. Add `--sandbox local` if you do not have Docker. The single-model `agentic-fit --model …` path still works for one model at a time.

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

Snapshot: **May 2026** | 16 models across nine vendors

| Finding | Result |
|---|---|
| The best library is model-specific | the best library differs by model in 6 of 7 categories |
| The choice matters | cost varies a median 1.7×, up to 24×, even among libraries that all work |
| Popularity does not predict it | 54% concordance with PyPI download rank, barely above chance |
| The per-model signal is actionable | one universal default costs ~1.25× more, and fails where a per-model pick works |

### Best library by category

Each count is how many of the 16 models reached their most reliable, lowest-cost solution with that library. Only command-line parsing is unanimous; everywhere else the models disagree.

| Category | Best library, by model |
|---|---|
| `cli_parsing` | argparse (16) |
| `data_validation` | pydantic (9) · dataclasses (4) · marshmallow (3) |
| `date_handling` | dateutil (9) · datetime (6) · arrow (1) |
| `http_client` | requests (10) · httpx (5) · urllib3 (1) |
| `retrying` | tenacity (8) · backoff (6) · stamina (2) |
| `templating` | jinja2 (7) · mako (5) · chevron (4) |
| `yaml_config` | omegaconf (11) · PyYAML (5) |

Full methodology, per-category numbers, and caveats: [`docs/FINDINGS.md`](docs/FINDINGS.md)

Raw results: [`results/`](results/). See [`results/README.md`](results/README.md) for the schema.

---

## Acknowledgments

The harness, experiments, and analysis behind agentic-fit were built in collaboration with Claude (Anthropic). The research questions, product decisions, and final direction are the author's own.

---

## License

MIT. See [`LICENSE`](LICENSE).
