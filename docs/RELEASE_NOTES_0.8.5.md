# Fluid Forge Docs Baseline: CLI `0.8.5`

**Release Date:** May 28, 2026
**Status:** Superseded by [`0.8.6`](./RELEASE_NOTES_0.8.6.md) (supersedes [`0.8.4`](./RELEASE_NOTES_0.8.4.md))

## Headline

`0.8.5` is the **agentic world-class uplift**. The LLM layer moves to a true LiteLLM **Router** with cross-cloud fallback, automatic Anthropic prompt-caching, and accurate per-call cost accounting; a new **JudgeAgent** scores every generated contract on a 6-axis rubric and can gate CI; `fluid forge` runs become **pausable and resumable** (Ctrl-C now writes a checkpoint instead of losing work); a post-synthesis **enrichment** pass adds dbt tests, freshness, and physical-layout hints without overwriting your fields; and the model registry plus the three-tier (project / team / personal) memory and catalog adapters are hardened. It also lands the **describe surface** (`fluid describe --self`, `fluid_build.describe`, `FluidSchemaManager.latest_schema_path()`). No schema break vs `v0.8.4`.

---

## What changed in `v0.8.5`

### 1 — LiteLLM Router with cross-cloud fallback + cache_control

`fluid forge`'s LLM calls now route through a LiteLLM **Router** rather than a single client.

- **Cross-cloud fallback chain** — opt in with `FLUID_LLM_FALLBACK_CHAIN` (e.g. `anthropic→bedrock→vertex`). When the primary provider errors or rate-limits, the Router transparently retries the next link.
- **Automatic Anthropic `cache_control`** — cache points are injected automatically so repeated system / context blocks are billed at the cached rate.
- **3-token cost tracking** — cost accounting now splits cache-**creation** (1.25×) and cache-**read** (0.10×) multipliers from ordinary input/output tokens, and persists the breakdown to `cost.json`. `fluid stats` aggregates it.

### 2 — JudgeAgent + CI judge-gate

A new **JudgeAgent** scores generated contracts on a 6-axis chain-of-thought rubric: **correctness, completeness, security, governance, performance, documentation**.

- An optional **Self-Refine** self-critique pass lets the agent revise before emitting a verdict.
- Ships with a 10-contract eval set and a **snapshot regression gate** so a model or prompt change that degrades output quality fails CI.
- Surfaced to operators via **`fluid stats --judge`**.

### 3 — Pause / resume + the `fluid agents` namespace

Long `fluid forge` runs are now interruptible without losing progress.

- **Ctrl-C writes a `.paused` checkpoint marker** mid-run; the next `fluid forge` auto-detects it and offers to resume. Use **`--resume`** to resume explicitly.
- Checkpointing uses a LangGraph-shape `BaseCheckpointSaver` with a **JSON-only file backend (no pickle)** — checkpoints are inspectable and safe to commit/transport.
- New **`fluid agents list / show / prune`** namespace manages saved runs, with safe-by-default archiving (prune archives rather than hard-deletes).

### 4 — Post-synthesis enrichment (Wave 2)

A deterministic enrichment pass runs *after* the contract is synthesised, adding the fields a human reviewer usually adds by hand:

- **`dbt_test_generator`** — proposes dbt tests for the modelled columns.
- **`freshness_emitter`** — adds freshness expectations.
- **`physical_layout`** — emits platform-appropriate physical-layout hints for **Snowflake / BigQuery / Athena / Redshift**.

Run it with **`fluid forge --apply-enrichment`**. Every change is shown as a **diff preview** and **never overwrites a field you set** — enrichment only fills gaps.

### 5 — 15-class PII classifier on both intake paths

A 15-class PII classifier (pattern borrowed from Presidio / piicatcher / GCP DLP / AWS Glue) is now wired into **both** the catalog intake path and the JDBC intake path, so sensitive columns are flagged consistently regardless of where the schema came from.

### 6 — Catalog-driven model registry + 3-tier memory hardening

- **Model registry is now catalog-driven** — the static, hand-maintained model tables are retired in favour of `cli/llm_models.json` (weekly-refreshed). New models show up without a code change.
- **Three-tier memory** (project / team / personal) gets a documented **precedence ladder**; inspect the resolved view with **`fluid forge --show-memory`**.
- **`fluid doctor --env`** enumerates the `FLUID_*` kill switches so you can see which behaviours are toggled in your environment.

### 7 — Describe surface (CC alignment)

A new programmatic + CLI surface for "what is this install capable of":

- **`FluidSchemaManager.latest_schema_path()`** — returns the absolute path to the newest bundled schema JSON without hardcoding a filename.
- **`fluid_build.describe.self_describe()`** — a flat, JSON-serialisable snapshot of the installed environment (version, schema, providers, build engines, templates, capability flags), importable in-process. Capability flags are **derived from importable backing modules** (à la `pulumi about`), never hardcoded.
- **`fluid describe --self [--json]`** — human-readable summary by default, JSON with `--json`.

---

## Notable for upgraders

- **No schema break.** Contracts that validated on `v0.8.4` validate unchanged on `v0.8.5`.
- **Fallback chains are opt-in.** `FLUID_LLM_FALLBACK_CHAIN` is unset by default — behaviour is unchanged unless you configure it. Each link must have working credentials.
- **Ctrl-C behaviour changed.** Interrupting `fluid forge` now writes a checkpoint and exits cleanly instead of aborting. Run `fluid agents prune` periodically (or rely on the safe-by-default archiving) to keep the checkpoint directory tidy.
- **Enrichment is non-destructive but opt-in.** `--apply-enrichment` only fills empty fields and always previews a diff; it will not silently rewrite a value you authored.
- **Model tables moved to `cli/llm_models.json`.** If you patched the old in-code model tables downstream, re-point at the JSON registry.

---

## What changed in the docs

- **[`fluid stats`](./cli/stats.md)** — documents the new `--judge` view and the cache-split cost columns.
- **[LiteLLM Backend](./advanced/litellm-backend.md)** — Router, `FLUID_LLM_FALLBACK_CHAIN`, automatic `cache_control`, and 3-token cost accounting.
- **[Guided Forge UX](./advanced/guided-forge-ux.md)** — pause/resume, `--resume`, the `fluid agents` namespace, `--apply-enrichment`, and `--show-memory`.
- **[Environment Variables](./advanced/environment-variables.md)** — new `FLUID_*` toggles surfaced by `fluid doctor --env`.
- **`RELEASE_NOTES_0.8.5.md`** — this file.

---

## Installing

```bash
pip install --upgrade data-product-forge
pip install "data-product-forge==0.8.5"

# Verify
fluid version
# -> 0.8.5
```

---

## Archive note

Older release notes remain available: [`0.8.4`](./RELEASE_NOTES_0.8.4.md), [`0.8.3`](./RELEASE_NOTES_0.8.3.md), [`0.8.0`](./RELEASE_NOTES_0.8.0.md), [`0.7.11`](./RELEASE_NOTES_0.7.11.md), [`0.7.9`](./RELEASE_NOTES_0.7.9.md), [`0.7.1`](./RELEASE_NOTES_0.7.1.md).
