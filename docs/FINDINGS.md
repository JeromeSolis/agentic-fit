# agentic-fit: Findings

**Snapshot:** May 2026 (constrained 2026-05-25, free-choice 2026-05-27) · **Models:** 16, across nine vendors (Anthropic, OpenAI, Google, DeepSeek, Qwen, Moonshot, Mistral, Cohere, Z.ai)

## The question

When a coding agent solves a task, it has to choose a library. For parsing dates it might reach for the standard library, or dateutil, or arrow. agentic-fit asks a narrow, practical question: for a given model, which library produces a reliable solution at the lowest cost?

The narrow question serves a larger one. As agents take over more of that choosing, the developers who build good libraries lose the signal that used to reward them, a person deciding their work was worth adopting. Seeing clearly which libraries agents reach for, and how well those libraries serve them, is a first step toward a fairer incentive structure between agents and the people building the libraries they rely on.

## How it works

Each cell of the matrix pairs one model, one task, and one assigned library. The agent solves the task using that library, the solution is checked against a pytest gate, and we record whether it passed and what it cost in US dollars. Every cell runs three times. We use cost rather than raw token counts because tokens are not comparable across tokenizers, and we route every model through one provider so the measurement is identical for all of them. The libraries in a category compete head to head: for HTTP work, requests against httpx against urllib3, and so on.

## What we found

**The library you pick changes the bill, even when several would work.** Look only at libraries that solve a task reliably for a given model, so capability is not in question, and the cost still varies. The gap between the cheapest and costliest reliable library is typically about 1.7 times, passes 2 times in roughly 40 percent of cases, and reaches 24 times at the extreme. Choosing well inside a category is worth real money.

**The right library depends on the model.** This is the finding the benchmark exists for, and it holds across vendors. In six of the seven categories the best library changes from one model to the next. Only command-line parsing is unanimous, where every model does best with the standard library. Everywhere else the field splits: HTTP work lands on requests for ten models, httpx for five, urllib3 for one; retries divide across tenacity, backoff, and stamina; validation across pydantic, stdlib dataclasses, and marshmallow. There is no single best library for agents. There is only a best library for a given model.

**Popularity does not tell you the answer.** Across all sixteen models, the agreement between a library's PyPI download rank and its cost rank for the agent is 54 percent, barely above chance, with 129 concordant and 110 discordant pairs. The library a model uses best is often not the popular one: eleven of sixteen models handle configuration best with omegaconf rather than the far more common PyYAML, and several do validation best with the standard library rather than pydantic. The download counts as a proxy do not predict which library an agent uses efficiently. The only way to know is to measure it.

**Knowing this is worth something.** If you ignored the model and picked each category's most popular winner for everyone, you would pay a median of 1.25 times, and a mean of 1.54 times, more than choosing per model, in the cases where that default even works. In five model-and-category cases the popular default is not reliable for a given model while a per-model choice is. A per-model recommendation buys both lower cost and fewer outright failures.

## Free-choice picks

Free-choice mode removes the constraint and asks the question from the other direction: with no candidate prescribed, which library does each model actually reach for? This is the cleanest reading of a model's library preference, because nothing in the prompt nudges it toward a name.

The free pick lands on the model's measured-best library in 37.5 percent of cells, 42 of 112. Less than half the time, the library a model picks on its own is the one that serves it best in the constrained run.

When the two come apart and both are priced, the gap is real but bounded. Across the 37 in-set cells where the free pick differs from the best, the cost ratio runs at a median of 1.22 times and a mean of 1.30, with a worst case at 2.07. Read plainly: the library a model reaches for on its own costs about 22 percent more than the library that serves it best. The default tax is visible without being catastrophic.

The pattern underneath is convergence. Within a category, the free picks pile onto one or two libraries far more tightly than the constrained-best run does, where each model lands on its own answer. Every one of the sixteen models reaches for argparse on command-line parsing; typer, the most-downloaded candidate, draws zero picks. Templating splits ten to jinja2 and six to the standard library, with mako, the highest-downloaded option, absent. Validation lands ten on dataclasses and six on the standard library, and pydantic does not show up. Retries, where the task is to wrap a callable so it re-runs up to three times on failure, are where convergence and download rank coincide: tenacity is both the pile-up at fourteen of sixteen and the most-downloaded candidate. Across all 70 diff cells, the free pick coincides with the most-downloaded library only about a quarter of the time. The driver looks like ecosystem familiarity, the library a model has seen most often in well-formed code, rather than download rank. This is independent confirmation, from a different angle, of finding three.

The convergence is not a stdlib reflex either. Across all free picks, 57 percent are community libraries and 43 percent are built-in, so the pile-up is a mix of the two depending on category.

This is three runs per cell on one snapshot of model versions. The pile-ups, the agreement rate, and the size of the default tax are visible. Fine ordering between models that sit close together is not.

## What this does not claim

These tasks are small and self-contained, single functions rather than large codebases, and nearly every model passes nearly all of them. That is by design: the benchmark isolates the library-selection signal rather than ranking models on problem solving, so nothing here speaks to how capable a model is on hard or large work. The cost figures also include reasoning tokens, which is honest about what a task really costs but means a talkative model looks more expensive regardless of its library skill. And this is three runs per cell on one snapshot of model versions, enough to see the shape of each result but not to separate models that sit close together.

## Origins

This started as a two-model study, Claude Sonnet and Haiku, that first showed the cheapest library could differ between models. The cross-lab snapshot above generalizes that result across nine vendors. The original token-cost write-up and its C1 through C3 data remain in the repo for reference.
