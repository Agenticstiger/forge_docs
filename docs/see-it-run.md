---
title: See it run
description: Five recorded terminal sessions of Fluid Forge workflows, with the numbers each recording shows.
---

# See Fluid Forge in action

Five short demos. Each one starts with a problem and ends with a number from the recording. They are terminal recordings rendered as SVG: some were captured from a live run, some were scripted against the bundled `examples/` fixtures. Click play, read the takeaway banner, move on.

::: warning Recorded against CLI 0.10.0
The recordings were made with CLI 0.10.0 and have not been re-recorded for 0.18.1. Command names and flags in them still exist in 0.18.1 (the commands shown were checked against `fluid --help`), but the output, timings and costs on screen are what the recording showed, not what 0.18.1 prints today. For current output, follow [Get Started](/forge_docs/getting-started/).
:::

## Pick your problem

| Your problem | Watch this | Time | What the recording shows |
|---|---|---|---|
| Writing a data contract per source by hand | [`$0.03` per data product](#_0-03-per-data-product) | ~50 s | Three LLM providers, one flag swapped, the same contract shape. |
| Setting up acquisition for one Postgres source | [Six months → sixty seconds](#six-months-→-sixty-seconds) | ~40 s | A Bronze contract from a Postgres URL, run on embedded DuckDB. |
| An interview that asks what it could infer | [23 questions, skipped](#_23-questions-skipped) | ~50 s | A 47 ms scan answers most of the interview, four questions are asked. |
| A pipeline broke and you need the cause | [Skip the panic](#skip-the-panic) | ~75 s | `fluid runs` narrows a failure to a fix and `fluid ship` redeploys it. |
| An agent loop that accumulates tool history | [`$0.50` → `$0.05`](#_0-50-→-0-05) | ~40 s | One env var selects the compaction strategy. |

---

## $0.03 per data product

`fluid forge data-model` turns eight lines of intent YAML into a contract. The recording runs the same intent through three providers (Anthropic Haiku 4.5, OpenAI gpt-4.1-mini, local Ollama gemma2) and shows the token counts and costs it measured. You choose the provider with `--llm-provider`.

<CliCast
  src="/forge_docs/demos/forge-multi-provider.svg"
  title="fluid forge data-model — same intent, three providers, real cost figures"
  caption="Eight lines of intent YAML. Anthropic, OpenAI, Ollama — same flag swapped each time. The recording shows all three producing a valid contract and the same dbt project layout, with the token counts and costs of that run."
  width="920"
  insight="$0.03 total across the three providers in this run, $0.00 on local Ollama. | The three contracts in this recording have the same 11 fields, 4 dq.rules, accessPolicy and agentPolicy. | The provider is one flag: --llm-provider."
/>

Pairs with [Forge Data Model](/forge_docs/forge-data-model.html) and [LLM Providers](/forge_docs/advanced/llm-providers.html). Long-form animated reel preserved at [`/forge_docs/reels/forge-in-action.html`](/forge_docs/reels/forge-in-action.html).

---

## Six months → sixty seconds

`fluid init --discover postgres://…` introspects a Postgres source and writes a Bronze acquisition contract. The recording validates it and applies it against embedded DuckDB. The contract's `engine:` field selects the runner (`duckdb`, `dlt`, `meltano`, `airbyte`, `kafka-connect` and `debezium` are build runners in the CLI), so moving off embedded mode is a contract edit; whether a given engine accepts a given source is a question for that engine's page.

<CliCast
  src="/forge_docs/demos/source-aligned-bronze.svg"
  title="fluid init --discover postgres://... — Bronze contract in 60 seconds"
  caption="Connect, scan information_schema (47 ms), infer 28 tables / 143 columns / 12 PII candidates / 8 foreign keys, emit a complete Bronze contract.fluid.yaml, validate, apply against embedded DuckDB. 6.2 seconds total. Then show the engine swap path."
  width="920"
  insight="6.2 seconds from Postgres URL to a Bronze contract in this recording, on embedded DuckDB. | The engine is the contract's engine: field. | The source spec, PII flags and Bronze table layout live in the contract, separate from the runner."
/>

Pairs with [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html), [Postgres → DuckDB walkthrough](/forge_docs/walkthrough/source-aligned-postgres-duckdb.html), and [`fluid init --discover`](/forge_docs/cli/init.html#discover). Long-form animated reel preserved at [`/forge_docs/reels/source-aligned-bronze.html`](/forge_docs/reels/source-aligned-bronze.html).

---

## 23 questions, skipped

`fluid forge` scans the working directory before it asks anything. In the recording the scan takes 47 ms, offers a 5-mode picker, asks four questions (most accept an inferred default), shows cost-cap progress as it runs, and shows a pre-write panel listing what will and will not change.

<CliCast
  src="/forge_docs/demos/guided-forge-ux.svg"
  title="fluid forge — guided UX in action"
  caption="47 ms welcome scan finds 3 CSVs + 2 dbt models + 1 README, infers domain (finance) and PII (5 columns). 5-mode picker. 4 questions answered (most accept the inferred default with ↵). Cost-cap progress in real time ($0.000 → $0.021 of $0.050 cap). Pre-write panel shows exactly what will + won't change."
  width="920"
  insight="4 questions answered in this recording. | The 47 ms welcome scan and domain inference supplied the other answers. | $0.021 spent of a $0.050 cap. Slash commands at the prompts: /skip /back /help /quit /save."
/>

Pairs with [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html) and the [`fluid forge`](/forge_docs/cli/forge.html) reference. Long-form animated reel preserved at [`/forge_docs/reels/guided-forge-ux.html`](/forge_docs/reels/guided-forge-ux.html).

---

## Skip the panic

A freshness SLA breaches overnight. The recording uses `fluid runs status` to see the failing runs, `fluid runs logs --component dlq` for the cause, `fluid runs diff` for what changed since the last good run, a one-line contract fix, and `fluid ship` to redeploy.

<CliCast
  src="/forge_docs/demos/day2-ops.svg"
  title="3am Slack ping → ship in 90 seconds"
  caption="PagerDuty: freshness SLA breached. fluid runs status shows 3 consecutive failures. fluid runs logs --component dlq surfaces the root cause (CHECK constraint NOT NULL, 47 partial-window customers). fluid runs diff shows what changed since the last OK run. One-line contract fix: NOT_NULL → NOT_NULL_WHERE customer_age_days >= 30. fluid ship. 87 seconds end-to-end. Recovered 12,361 rows."
  width="920"
  insight="Slack ping to ship: 87 seconds in this recording. | fluid runs status / logs / diff trace the failure in three commands. | One-line contract fix (NOT_NULL → NOT_NULL_WHERE) and fluid ship."
/>

Pairs with [`fluid runs`](/forge_docs/cli/runs.html), [`fluid retention`](/forge_docs/cli/retention.html), [`fluid secrets`](/forge_docs/cli/secrets.html), [`fluid stats`](/forge_docs/cli/stats.html), and [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html). Long-form animated reel preserved at [`/forge_docs/reels/day2-ops.html`](/forge_docs/reels/day2-ops.html).

---

## $0.50 → $0.05

A long agent loop accumulates tool results, and each turn carries the previous ones, so cost grows faster than the number of turns. `FLUID_COMPACTION_STRATEGY` selects how the loop compacts: `truncate`, `summarize` (LLM-backed) or `hybrid` (cheap path first, summariser as a safety net). The recording compares them on a 20-turn run.

<CliCast
  src="/forge_docs/demos/agent-compaction.svg"
  title="Agent-loop compaction — three strategies, real before/after costs"
  caption="20-turn baseline: $0.503/run, super-linear context bloat (5K → 67K → 298K tokens). Three strategies side-by-side: truncate (5.8× cheaper), summarize (9.3× cheaper), hybrid (10.5× cheaper). One env var: FLUID_COMPACTION_STRATEGY=hybrid. No code changes."
  width="920"
  insight="$0.503 to $0.048 per 20-turn run in this recording (10.5x), with no code change. | truncate, summarize and hybrid are set with FLUID_COMPACTION_STRATEGY. | The contract and the agent are unchanged; only context-window handling differs."
/>

Pairs with [Agentic primitives → Token-budget pre-flight & compaction](/forge_docs/advanced/agentic-primitives.html#token-budget-pre-flight-compaction). Long-form animated reel preserved at [`/forge_docs/reels/compaction-and-warnings.html`](/forge_docs/reels/compaction-and-warnings.html).

---

## More demos in 30 seconds each

The full library covers AWS, a Snowflake live-auth dry-run, agent-policy enforcement, blank scaffolds, policy compilation, and the local quickstart:

→ **[Browse all demos](/forge_docs/demos/)**

---

## How these are sourced

**Each cast above** is a deterministic asciinema-rendered SVG generated by a Python pipeline (`scripts/cast_builder.py` → `scrub-cast.py` → `svg-term`). The narrative lives in `scripts/demos/<name>.py` — clone, edit, regenerate. Each cast plays inline in the browser without GIFs, a JS framework or third-party CDNs.

**Token counts, durations, and costs** in the LLM-driven recordings (`forge-multi-provider`, `agent-compaction`) were captured from runs on the dates they were recorded; prices change, so treat them as that run's figures. The latency numbers in the other recordings (`source-aligned-bronze`, `guided-forge-ux`, `day2-ops`) come from the v0.10.0 stack against the bundled `examples/` fixtures.

**The original animated HTML reels** are preserved at [`/reels/`](https://github.com/Agenticstiger/forge_docs/tree/main/docs/.vuepress/public/reels) for anyone who wants the longer-form pacing — each cast section above links through to its corresponding reel.

## See also

- [Get Started](/forge_docs/getting-started/) — install, scaffold, validate, run locally
- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — the framework powering the Bronze cast
- [Product Types — SDP, ADP, CDP](/forge_docs/data-products/product-type.html) — the vocabulary used throughout
- [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html) — the architecture behind the guided UX cast
- [Capability Warnings](/forge_docs/advanced/capability-warnings.html) — the per-model coverage matrix
