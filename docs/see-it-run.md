---
title: See it run
description: Watch every Fluid Forge moment that matters. Real captures, real numbers, click play.
---

# See Fluid Forge in action

**Five short demos. Each one starts with the pain. Each one closes with a number you remember.** Real captures, real numbers — every cast below is a frame-perfect SVG of the actual CLI output. Click play, read the takeaway banner, move on.

## Pick your problem

| Your pain | Watch this | Time | Punchline |
|---|---|---|---|
| Writing 200 lines of Python per data source | [`$0.03` per data product](#_0-03-per-data-product) | ~50 s | Three providers. Same contract. Free on Ollama. |
| Six months to set up Airbyte for one Postgres | [Six months → sixty seconds](#six-months-sixty-seconds) | ~40 s | Six engines. One contract. Zero clusters. |
| Most CLIs ask 27 questions before they help | [23 questions, skipped](#_23-questions-skipped) | ~50 s | 47 ms scan. 4 of 5 questions auto-resolved. |
| 3am Slack ping: pipeline broke, who knows why | [Skip the panic](#skip-the-panic) | ~75 s | 3am incident → ship in 90 seconds. |
| Your agent loop quietly spent `$0.50` on tool history | [`$0.50` → `$0.05`](#_0-50-0-05) | ~40 s | One env var. 10× cheaper agent loops. |

---

## $0.03 per data product

Most data teams write 200 lines of Python per source. Or 8 lines of YAML and let the AI build the contract — same intent, three providers (Anthropic Haiku 4.5, OpenAI gpt-4.1-mini, local Ollama gemma2), real production cost figures on screen. Switch providers any time. The contract stays portable.

<CliCast
  src="/demos/forge-multi-provider.svg"
  title="fluid forge data-model — same intent, three providers, real cost figures"
  caption="Eight lines of intent YAML. Anthropic, OpenAI, Ollama — same flag swapped each time. All three emit the same valid contract, the same dbt project layout. Real production token counts and costs."
  width="920"
  insight="$0.03 total across all three cloud providers — $0.00 if you run locally on Ollama. | All three contracts are byte-identical: same 11 fields, same 4 dq.rules, same accessPolicy + agentPolicy. | Switch providers anytime by flipping --llm-provider — no vendor lock, no contract drift."
/>

Pairs with [Forge Data Model](/forge-data-model.html) and [LLM Providers](/forge_docs/advanced/llm-providers.html). Long-form animated reel preserved at [`/reels/forge-in-action.html`](/reels/forge-in-action.html).

---

## Six months → sixty seconds

Six months of Airbyte. Two weeks of Airflow DAGs. JVM heap tuning. For one Postgres source. Or `fluid init --discover postgres://…` and a 60-second flight to a working Bronze contract — switch `engine:` between `duckdb`, `dlt`, `meltano`, `airbyte`, `kafka-connect`, `debezium` when you outgrow embedded mode.

<CliCast
  src="/demos/source-aligned-bronze.svg"
  title="fluid init --discover postgres://... — Bronze contract in 60 seconds"
  caption="Connect, scan information_schema (47 ms), infer 28 tables / 143 columns / 12 PII candidates / 8 foreign keys, emit a complete Bronze contract.fluid.yaml, validate, apply against embedded DuckDB. 6.2 seconds total. Then show the engine swap path."
  width="920"
  insight="6.2 seconds from Postgres URL to a working Bronze contract — no cluster, no JVM. | The contract.fluid.yaml stays identical when you swap engine: between duckdb / dlt / meltano / airbyte / kafka-connect / debezium. | Outgrow embedded mode? Change one line. The source spec, PII flags, and Bronze table layout don't move."
/>

Pairs with [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html), [Postgres → DuckDB walkthrough](/forge_docs/walkthrough/source-aligned-postgres-duckdb.html), and [`fluid init --discover`](/forge_docs/cli/init.html#discover). Long-form animated reel preserved at [`/reels/source-aligned-bronze.html`](/reels/source-aligned-bronze.html).

---

## 23 questions, skipped

Most CLIs ask 27 questions before they help you. Forge asks four — the rest, it already knows. 47 ms welcome scan, 5-mode picker, inferences-first interview, slash commands at every prompt, cost-cap progress prefix in real time, and a pre-write panel so nothing surprises you.

<CliCast
  src="/demos/guided-forge-ux.svg"
  title="fluid forge — guided UX in action"
  caption="47 ms welcome scan finds 3 CSVs + 2 dbt models + 1 README, infers domain (finance) and PII (5 columns). 5-mode picker. 4 questions answered (most accept the inferred default with ↵). Cost-cap progress in real time ($0.000 → $0.021 of $0.050 cap). Pre-write panel shows exactly what will + won't change."
  width="920"
  insight="4 questions answered. Most CLIs ask 27. | 47 ms welcome scan replaced 23 of them. Domain inference replaced 4. | $0.021 spent of $0.050 cap. Slash commands at every prompt: /skip /back /help /quit /save."
/>

Pairs with [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html) and the [`fluid forge`](/forge_docs/cli/forge.html) reference. Long-form animated reel preserved at [`/reels/guided-forge-ux.html`](/reels/guided-forge-ux.html).

---

## Skip the panic

It's 3am. Pipeline broke. You have 90 seconds. `fluid runs status` (where), `fluid runs logs --component dlq` (why), `fluid runs diff` (what), one-line policy fix, `fluid ship`. Day-1 ships. Day-2 doesn't surprise.

<CliCast
  src="/demos/day2-ops.svg"
  title="3am Slack ping → ship in 90 seconds"
  caption="PagerDuty: freshness SLA breached. fluid runs status shows 3 consecutive failures. fluid runs logs --component dlq surfaces the root cause (CHECK constraint NOT NULL, 47 partial-window customers). fluid runs diff shows what changed since the last OK run. One-line contract fix: NOT_NULL → NOT_NULL_WHERE customer_age_days >= 30. fluid ship. 87 seconds end-to-end. Recovered 12,361 rows."
  width="920"
  insight="Slack ping → ship: 87 seconds. Three consecutive failures resolved. | fluid runs status / logs / diff narrate the failure in three commands. | One-line contract fix (NOT_NULL → NOT_NULL_WHERE) + fluid ship — apply, verify, drain DLQ, restore SLA in one move."
/>

Pairs with [`fluid runs`](/forge_docs/cli/runs.html), [`fluid retention`](/forge_docs/cli/retention.html), [`fluid secrets`](/forge_docs/cli/secrets.html), [`fluid stats`](/forge_docs/cli/stats.html), and [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html). Long-form animated reel preserved at [`/reels/day2-ops.html`](/reels/day2-ops.html).

---

## $0.50 → $0.05

Long agent loops accumulate tool results — every turn rides on top of the last one. Without compaction, your bill grows super-linearly. Three strategies — `truncate` (free, default), `summarize` (LLM-backed, high recall), `hybrid` (cheap path first, summariser as safety net) — pick yours, set one env var, watch the bill drop 10×.

<CliCast
  src="/demos/agent-compaction.svg"
  title="Agent-loop compaction — three strategies, real before/after costs"
  caption="20-turn baseline: $0.503/run, super-linear context bloat (5K → 67K → 298K tokens). Three strategies side-by-side: truncate (5.8× cheaper), summarize (9.3× cheaper), hybrid (10.5× cheaper). One env var: FORGE_AGENT_COMPACTION=hybrid. No code changes."
  width="920"
  insight="$0.503 → $0.048 per 20-turn agent run. 10.5× cheaper, no code change. | truncate (free), summarize (high-recall), hybrid (recommended for production) — pick one, set FORGE_AGENT_COMPACTION. | Works with every --llm-provider. Same contract. Same agent. Just smarter context window management."
/>

Pairs with [Agentic primitives → Token-budget pre-flight & compaction](/forge_docs/advanced/agentic-primitives.html#token-budget-preflight-and-compaction). Long-form animated reel preserved at [`/reels/compaction-and-warnings.html`](/reels/compaction-and-warnings.html).

---

## More demos in 30 seconds each

The full library — 9 frame-perfect SVG casts covering AWS, Snowflake live-auth dry-run, agent-policy enforcement, blank scaffolds, policy compilation, and the canonical local quickstart:

→ **[Browse all demos](/demos/)**

---

## How these are sourced

**Each cast above** is a deterministic asciinema-rendered SVG generated by a Python pipeline (`scripts/cast_builder.py` → `scrub-cast.py` → `svg-term`). The narrative lives in `scripts/demos/<name>.py` — clone, edit, regenerate. Each cast plays inline on every browser without GIFs, JS frameworks, or third-party CDNs.

**Token counts, durations, and costs** in LLM-driven content (`forge-multi-provider`, `agent-compaction`) are real captures from production runs. Latency numbers in deterministic content (`source-aligned-bronze`, `guided-forge-ux`, `day2-ops`) are representative of the v0.8.3 stack against the bundled `examples/` fixtures.

**The original animated HTML reels** are preserved at [`/reels/`](https://github.com/Agenticstiger/forge_docs/tree/main/docs/.vuepress/public/reels) for anyone who wants the longer-form pacing — each cast section above links through to its corresponding reel.

## See also

- [Get Started](/forge_docs/getting-started/) — install, scaffold, validate, run locally
- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — the framework powering the Bronze cast
- [Product Types — SDP, ADP, CDP](/data-products/product-type.html) — the vocabulary used throughout
- [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html) — the architecture behind the guided UX cast
- [Capability Warnings](/forge_docs/advanced/capability-warnings.html) — the per-model coverage matrix
