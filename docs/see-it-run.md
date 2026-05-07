---
title: See it run
description: Watch every Fluid Forge moment that matters. Real captures, real numbers, click play.
---

# See Fluid Forge in action

**Three things you should believe in 90 seconds.** Real captures, real numbers — every demo below is a frame-perfect cast of the actual CLI output. Click play, read the takeaway banner, move on.

---

## 1️⃣ One contract → working data product, in 30 seconds

**No cloud. No credit card.** Install with the `[local]` extra, scaffold a Bitcoin tracker contract from the quickstart template, validate against the v0.7.2 schema, preview the plan, apply against the local DuckDB provider. The data product lands at `runtime/out/bitcoin_prices.parquet` — 24 rows, 3 columns, repeatable.

<CliCast
  src="/forge_docs/demos/local-quickstart.svg"
  title="fluid init my-project --quickstart  →  validate  →  plan  →  apply"
  caption="Pure local — DuckDB does the work, Parquet lands the artifact, no cloud touched."
  width="920"
  insight="30 seconds end-to-end. | The contract.fluid.yaml you wrote is the contract that ran. | Local DuckDB + Parquet — exactly what production produces, but offline."
/>

**Try it now:** `pip install "data-product-forge[local]"` → `fluid init my-project --quickstart`. Full walkthrough at [Getting Started](/forge_docs/getting-started/).

---

## 2️⃣ Same contract → four clouds, zero rewrites

**Change one line of YAML, redeploy.** The schema, `dq.rules`, `accessPolicy.grants`, `agentPolicy`, sovereignty — all stay **byte-identical**. Only the cloud-specific binding fields move.

<CliCast
  src="/forge_docs/demos/gcp-quickstart.svg"
  title="GCP / BigQuery — same contract, swap one line, deploy"
  caption="Watch the git diff: 4 lines change (binding.platform, format, location). The other 200 lines of governance + schema + IAM stay identical."
  width="920"
  insight="Same contract. One line changed (platform: local → platform: gcp). | BigQuery dataset, table, IAM grants — all from the YAML you already had. | Schema, dq.rules, agentPolicy — byte-identical to the local run."
/>

The same proof works on **AWS Glue + Athena**, **Snowflake**, and any custom provider you register. See the dedicated walkthroughs at [GCP](/forge_docs/walkthrough/gcp), [Snowflake](/forge_docs/walkthrough/snowflake), and the [AWS provider](/forge_docs/providers/aws).

---

## 3️⃣ AI copilot → full data-product spec in one prompt

**11.4 seconds. 1,834 tokens. ~$0.0021.** `fluid forge --domain finance --llm-provider gemini` loads project memory, applies the finance domain expertise pack (SOX + GDPR, denied use-cases), discovers local context (CSVs + dbt models + PII candidates), streams a Gemini call, and emits a fully-validated contract — schema, `dq.rules`, `accessPolicy`, `agentPolicy`, sovereignty — all in one shot. Memory persists for the next call.

<CliCast
  src="/forge_docs/demos/forge-gemini.svg"
  title="fluid forge --domain finance --llm-provider gemini --llm-model gemini-2.5-flash"
  caption="Full agent flow: memory → domain pack → discovery → streaming → contract emit → auto-validation → memory persist."
  width="920"
  insight="11.4 s · 1834 tokens · ~$0.0021 — full data product spec generated. | 11 schema fields tagged · 4 dq.rules · 3 RBAC grants · agentPolicy gating LLM access. | Memory persisted — the next fluid forge call inherits this vocabulary."
/>

The same flow works with `--llm-provider openai`, `--llm-provider anthropic`, or `--llm-provider ollama` (local, free).

---

## More demos in 30 seconds each

The full library — 9 frame-perfect SVG casts covering AWS, Snowflake live-auth dry-run, agent-policy enforcement, blank scaffolds, policy compilation:

→ **[Browse all 9 demos](/forge_docs/demos/)**

---

## Deeper cuts — long-form reels (60 s each)

Five longer reels for the moments where the punchline takes a minute to land. Pure HTML/CSS, no frameworks, no autoplay. Use **←/→** to step scenes, **space** to pause, **r** to restart.

### `$0.03` per data product — three providers, one contract

Most data teams write 200 lines of Python per source. Or 8 lines of YAML and let the AI build the contract — same intent, three providers (Anthropic Haiku 4.5, OpenAI gpt-4.1-mini, local Ollama), real production cost figures on screen.

<iframe
  src="/forge_docs/reels/forge-in-action.html"
  width="100%"
  height="540"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the glue code — Fluid Forge in action">
</iframe>

[Open standalone](/forge_docs/reels/forge-in-action.html) · pairs with [Forge Data Model](/forge_docs/forge-data-model.html) and [LLM Providers](/forge_docs/advanced/llm-providers.html).

### Six months → sixty seconds — source-aligned Bronze

Six months of Airbyte. Two weeks of Airflow DAGs. JVM heap tuning. For one Postgres source. Or `fluid init --discover postgres://…` and a 60-second flight to a working Bronze contract — switch `engine:` between `duckdb`, `dlt`, `meltano`, `airbyte`, `kafka-connect`, `debezium` when you outgrow embedded mode.

<iframe
  src="/forge_docs/reels/source-aligned-bronze.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the cluster — source-aligned Bronze in 60 seconds">
</iframe>

[Open standalone](/forge_docs/reels/source-aligned-bronze.html) · pairs with [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html), [Postgres → DuckDB walkthrough](/forge_docs/walkthrough/source-aligned-postgres-duckdb.html), and [`fluid init --discover`](/forge_docs/cli/init.html#discover).

### 23 questions, skipped — guided UX

Most CLIs ask 27 questions before they help you. Forge asks four — the rest, it already knows. 47 ms welcome scan, 5-mode picker, inferences-first interview, slash commands at every prompt, cost-cap progress prefix in real time, pre-write panel.

<iframe
  src="/forge_docs/reels/guided-forge-ux.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the questions — Fluid Forge guided UX">
</iframe>

[Open standalone](/forge_docs/reels/guided-forge-ux.html) · pairs with [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html) and the [`fluid forge`](/forge_docs/cli/forge.html) reference.

### 3am Slack ping → ship in 90 seconds

It's 3am. Pipeline broke. You have 90 seconds. `fluid runs status` (where), `fluid runs logs --component dlq` (why), `fluid runs diff` (what), one-line policy fix, `fluid ship`. Day-1 ships. Day-2 doesn't surprise.

<iframe
  src="/forge_docs/reels/day2-ops.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the panic — Fluid Forge day-2 ops">
</iframe>

[Open standalone](/forge_docs/reels/day2-ops.html) · pairs with [`fluid runs`](/forge_docs/cli/runs.html), [`fluid retention`](/forge_docs/cli/retention.html), [`fluid secrets`](/forge_docs/cli/secrets.html), [`fluid stats`](/forge_docs/cli/stats.html), and [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html).

### `$0.50` → `$0.05` — agent-loop compaction

Long agent loops accumulate tool results — every turn rides on top of the last one. Without compaction, your bill grows super-linearly. Three strategies — `truncate` (free, default), `summarize` (LLM-backed, high recall), `hybrid` (cheap path first, summariser as safety net). Set one env var, watch the bill drop 10×.

<iframe
  src="/forge_docs/reels/compaction-and-warnings.html"
  width="100%"
  height="480"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the runaway bill — Fluid Forge compaction strategies">
</iframe>

[Open standalone](/forge_docs/reels/compaction-and-warnings.html) · pairs with [Agentic primitives → Token-budget pre-flight & compaction](/forge_docs/advanced/agentic-primitives.html#token-budget-preflight-and-compaction).

---

## How these are sourced

**The 3 short demos at the top** are deterministic asciinema-rendered SVG casts generated by a Python pipeline (`scripts/cast_builder.py` → `scrub-cast.py` → `svg-term`). Each one is frame-perfect to what `fluid` actually emits — you're seeing the real CLI output, not a recreation. Full library + pipeline docs at [/demos/](/forge_docs/demos/).

**The 5 long reels below** render from a `SCENES = [...]` array in a single self-contained HTML file under [`docs/.vuepress/public/reels/`](https://github.com/Agenticstiger/forge_docs/tree/main/docs/.vuepress/public/reels). No external CDNs, no JS frameworks, no images — just terminal-styled HTML/CSS/JS that auto-advances. ~27 KB per reel, lazy-loaded so the page stays fast on first paint.

**Token counts, durations, and costs** in LLM-driven content are real captures from production runs. Latency numbers in deterministic reels are representative of the v0.8.0 stack against the included `examples/` fixtures.
