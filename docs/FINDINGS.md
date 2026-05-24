# agentic-fit Findings

**Snapshot:** May 2026  
**Models:** `claude-sonnet-4-6`, `claude-haiku-4-5`

---

## Method

Each benchmark run works as follows.

**Cell structure.** The matrix is (task × library). Each cell assigns the agent one specific library and one task prompt. For each cell the runner creates an isolated virtual environment containing only that library (pinned to the version recorded at run time) and injects AST-level import enforcement so the generated solution cannot silently fall back to a competing library or to stdlib outside the allowed set. All cells for a given run use the same model.

**Execution and scoring.** The agent generates a Python solution file. The solution is scored by running the category's pytest test file inside the cell's venv. A cell passes if all tests pass, and fails otherwise. Token usage (prompt + completion) is recorded per cell and used as the primary efficiency metric: *tokens-to-success* for passing cells.

**Repetitions.** Each cell is repeated `reps = 5` times. The median token count across reps is used in all aggregations. Failures are included in the median calculation.

**Models.** All claims in this document come from two-model runs: `claude-sonnet-4-6` (frontier) and `claude-haiku-4-5` (smaller and cheaper). The snapshot date is May 2026.

**Token accounting.** Total tokens = prompt tokens + completion tokens, as reported by the Anthropic API. No cost normalization is applied; comparisons within a model are on raw token counts.

**Optional Docker sandbox.** Adding `--sandbox docker` runs each generated solution inside a hardened container instead of the host venv. This is used for the C3 control arms and is available for all runs via the `Dockerfile` in the repo root.

---

## C1: Variance is real and model-specific

**Claim:** within a single task category, the token cost to produce a passing solution varies substantially across candidate libraries, and that variation is not consistent between models.

### Sonnet, within-category token spread

| Category | Token ratio (costliest / cheapest) | Cheapest → costliest library |
|---|---|---|
| data_validation | **3.97×** | pydantic (556) → marshmallow (2,208) |
| date_handling | **3.35×** | dateutil (455) → datetime (1,524) |
| cli_parsing | **2.53×** | argparse (262) → typer (662) |
| templating | 1.83× | jinja2 (239) → mako (437) |
| retrying | 1.45× | backoff (258) → stamina (375) |
| http_client | 1.42× | requests (258) → urllib3 (366) |
| yaml_config | 1.25× | omegaconf (343) → yaml (430) |

*data_validation aggregates two tasks (a simpler parse_user task and a harder nested parse_order task) per library.*

On Haiku the spreads are substantially larger, up to **11.86×** (cli_parsing) and **8.91×** (retrying), and four cells failed outright: `arrow` in date_handling (40% success rate) and `typer` in cli_parsing (80% success rate). Sonnet had zero failures across all 120 cells.

### The cost ranking is model-specific

In three of seven categories the cheapest-library ranking **fully inverts** between Sonnet and Haiku:

| Category | Cheapest on Sonnet | Cheapest on Haiku |
|---|---|---|
| retrying | backoff | stamina |
| data_validation | pydantic | marshmallow |
| date_handling | dateutil | datetime (stdlib) |

Notable inversion: `backoff` costs 258 tokens on Sonnet but 2,906 tokens on Haiku, while `stamina` costs 375 on Sonnet and 326 on Haiku, so the ranking flips entirely. Similarly, `marshmallow` is the costliest library for Sonnet (2,208 tokens) but the cheapest for Haiku (734 tokens).

Rankings are stable in http_client; in cli_parsing, templating, and yaml_config the cheapest library stays the same across models but the costliest shifts.

**Confidence:** the large gaps (≥2×) are robust at n=5. The smaller gaps, http_client (1.42×) and yaml_config (1.25×) on Sonnet, are real but partly noise at this sample size.

---

## C2: Not explained by popularity

**Claim:** agentic-fit cost-rank is independent of PyPI download popularity.

### How C2 was computed

C2 derives entirely from the C1 run data plus a PyPI download snapshot (`data/pypi_downloads.json`, committed to the repo). No separate evaluation runs were done, and no additional API spend was incurred.

For each `(category, model)`, third-party candidate libraries were ranked by median tokens-to-success (from C1) and by PyPI last-month download count. For every within-category pair, the pair is **concordant** if the cheaper-for-the-agent library is also the more-downloaded one, and **discordant** otherwise. Stdlib candidates (argparse, datetime, dataclasses) were excluded because they have no PyPI download figures. All pairs were pooled across 7 categories and both models.

### Result

| Metric | Value |
|---|---|
| Pooled pairs | 30 (15 concordant, 15 discordant) |
| **Concordance rate** | **50%**, chance baseline |
| Cross-model inversions | 7 |
| Pre-registered GO threshold | ≤ 65% concordance |
| **Verdict** | GO, independent of popularity |

50% pooled concordance means knowing a library's PyPI download rank tells you nothing about whether it is cheaper or more expensive for an agent to use. The categories pull in opposite directions and cancel out.

### Sharpest divergences

- **urllib3** is the most-downloaded package in the set (1.63 billion downloads/month, more than `requests`), yet it is the costliest http_client library under both models.
- **omegaconf** has the lowest download count among yaml libraries (37M vs PyYAML's 1.05B) but is the cheapest for the agent. The yaml_config category has a 1/6 concordance rate, the most popularity-defiant result.
- **dateutil** and **jinja2** are highly popular *and* cheapest in their categories. The correlation is not uniformly negative, it simply fails to predict cost on average.

### Cross-model inversions confirm the gap

Seven pairs whose cost ordering flips between Sonnet and Haiku: cli_parsing {click, typer}, data_validation {marshmallow, pydantic}, retrying {backoff, stamina}, {backoff, tenacity}, {stamina, tenacity}, templating {chevron, mako}, yaml_config {ruamel, yaml}. PyPI downloads are model-invariant, so a popularity signal cannot produce rankings that change by model.

**Confidence note:** 30 pairs is a modest sample. The direction (independence) is well-supported; the precise concordance figure (50.0%) should be read as "around chance" rather than a precise correlation estimate. A larger matrix with more libraries or categories would tighten the estimate.

---

## C3: Actionable for weaker models

**Claim:** steering the agent to the model-specific cheapest library saves tokens for Haiku but not for Sonnet.

### Experimental design

Three arms per model:

- **Treatment:** the C1 cheapest-library cells (reused from the C1 run, so same model, same tasks, same reps).
- **Control-U (unconstrained):** the agent is given the task prompt with no library constraint, and chooses freely. Fresh runs, Docker sandbox.
- **Control-C (constrained to a non-recommended library):** the agent is constrained to a library that is not the recommended one. Fresh runs, Docker sandbox.

160 new runs (4 arms × 8 tasks × 5 reps).

### Result

| Model | Treatment (median tokens) | Control-U | Delta vs Control-U | Verdict |
|---|---|---|---|---|
| Haiku | 460 | 720 | **−36%** | GO |
| Sonnet | 296 | 288 | +2.8% (free choice is cheaper) | NO-GO |

The pre-registered threshold was ≥25% token reduction or ≥10pp success gain on hard cells. Haiku clears it on tokens, and Sonnet does not.

**Success axis:** zero failures in all control arms, so the ≥10pp-success criterion was never exercised. The verdict rests entirely on token efficiency.

### Why the split makes sense

Unconstrained Sonnet defaults to stdlib for 15 of 40 runs and otherwise picks mainstream, token-efficient libraries (pydantic, dateutil, tenacity, jinja2). It even chose `deepmerge` (outside the candidate set) for yaml_config and ran it successfully. Sonnet's free choices are already at or below the recommended token cost, so the recommendation adds nothing.

Unconstrained Haiku makes similar choices (stdlib×15, pydantic, requests, tenacity, jinja2, yaml) but executes them less efficiently. Steering it to the model-specific low-cost library reduces its token spend by roughly a third.

---

## Caveats

The following limitations apply to all three claims and should not be softened:

1. **Pooled-median weighting.** The 36% token reduction for C3 (and the C2 concordance rate) use a pooled median across categories. High-token categories (data_validation, date_handling) carry more weight than low-token ones. The direction of each result is robust, but the exact percentages are approximate.

2. **Success criterion was never exercised.** All control cells in C3 passed, so the ≥10pp-success arm of the GO rule was never tested. On harder tasks or more obscure libraries it might discriminate.

3. **n = 5 per cell.** Gaps of ≥2× are trustworthy. Smaller gaps (http_client at 1.42×, yaml_config at 1.25× on Sonnet) are real signals but partly noise at this sample size.

4. **Two models only.** The model-specificity finding is striking enough to trust directionally, but properly mapping the ranking-shift across the model capability spectrum would require more models.

5. **C3 treatment reused from C1.** The treatment arm was run in an earlier session, and the control arms are fresh. This is a minor temporal asymmetry.

6. **The "recommendation" is cheapest by tokens, not a composite pick.** A production-grade recommendation would also weight success rate and version stability. The current metric is tokens-to-success (median), failures included.

7. **30 pairs (C2) is modest.** The independence claim is well-supported, but the exact concordance rate should not be taken as a precise numerical estimate.

8. **Version-bound results.** Several signals are version-specific. For example, marshmallow 4.x API changes drove Sonnet's marshmallow cost. The correct unit of measurement is `(library × version × model × snapshot date)`.
