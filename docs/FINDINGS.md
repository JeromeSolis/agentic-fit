# agentic-fit: Findings

**Snapshot:** May 2026 · **Models:** 16, across nine vendors (Anthropic, OpenAI, Google, DeepSeek, Qwen, Moonshot, Mistral, Cohere, Z.ai)

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

## Models have library preferences

Sometimes a model told to use a particular library quietly declines and reaches for the standard library or a competitor instead. We count that as a miss against the assigned task, but read another way it is a preference, a sign of which libraries a model gravitates toward and which it resists. Measuring that directly, by letting each model choose freely, is the natural next step and the cleanest form of the library-selection question.

## What this does not claim

These tasks are small and self-contained, single functions rather than large codebases, and nearly every model passes nearly all of them. That is by design: the benchmark isolates the library-selection signal rather than ranking models on problem solving, so nothing here speaks to how capable a model is on hard or large work. The cost figures also include reasoning tokens, which is honest about what a task really costs but means a talkative model looks more expensive regardless of its library skill. And this is three runs per cell on one snapshot of model versions, enough to see the shape of each result but not to separate models that sit close together.

## Origins

This started as a two-model study, Claude Sonnet and Haiku, that first showed the cheapest library could differ between models. The cross-lab snapshot above generalizes that result across nine vendors. The original token-cost write-up and its C1 through C3 data remain in the repo for reference.
