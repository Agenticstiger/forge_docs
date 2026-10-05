---
title: CLI demos
description: "Recorded terminal sessions of Fluid Forge workflows: install through deploy, local through Snowflake, the AI copilot, agentPolicy enforcement, and the day-2 ops flow."
---

# CLI demos

Terminal recordings, rendered as SVG: install through deploy, local through Snowflake, the AI copilot, agentPolicy enforcement, day-2 incident response, and agent-loop compaction. Each one carries a takeaway popup with the numbers from that recording. Click play; the SVG only animates after you opt in (no autoplay, no JS).

::: warning Recorded against CLI 0.10.0
The recordings were made with CLI 0.10.0 and have not been re-recorded for 0.18.1. The output, versions, timings and costs on screen are from that recording. Where this page and a recording disagree about what the CLI does today, the page is right: see the notes under each section. For current output, follow [Get Started](/forge_docs/getting-started/).
:::

> **Convinced? → [Install in 30 seconds](/forge_docs/getting-started/)**. Want longer-form proof of specific workflows? → [See it run](/forge_docs/see-it-run.html) (narrative scenarios, ~50 s each, with takeaway numbers).

---

## Install + run, locally

Start here. No cloud account is needed.

On the CLI that this site documents (0.18.1), `fluid init my-project --quickstart` scaffolds the template with `fluidVersion: 0.7.5` and also writes a workspace file next to the project. The recording predates both; the contract it validates carries an older `fluidVersion`. See [Get Started](/forge_docs/getting-started/) for the files the current CLI writes.

<CliCast
  src="/forge_docs/demos/local-quickstart.svg"
  title="fluid init my-project --quickstart  →  validate  →  plan  →  apply"
  caption="Install the CLI, scaffold the Customer 360 Analytics contract from the quickstart template, validate it, preview the plan, and apply it against the local DuckDB provider. Two exposes — a master table and a high-value-customer view — land as Parquet under output/."
  width="920"
  insight="About 30 seconds, no cloud account. | The contract.fluid.yaml you scaffolded is the contract that ran. | A local DuckDB and Parquet artifact, produced offline."
/>

---

## Same contract, different cloud

Change the `binding` block and re-deploy. The schema, dq.rules and build stages stay as they were; the cloud-specific fields in `binding` change. Changing `binding.platform` alone is not enough: the platform, the `format` and the `location` have to agree. For example, `platform: gcp` with a `parquet` format and a local path produces a plan that emits nothing, and `fluid validate` warns that `apply` would emit nothing for that port. See [Switch clouds](/forge_docs/cli/tasks/switch-clouds.html) for the three keys that move together.

### GCP / BigQuery

<CliCast
  src="/forge_docs/demos/gcp-quickstart.svg"
  title="GCP quickstart — install, change the binding, deploy"
  caption="From the local Customer 360 contract to a BigQuery dataset. The `git diff` in the recording shows the binding block changing; the schema, dq.rules and build stages stay as they were."
  width="920"
  insight="Same contract, new binding block (platform, format and location change together). | A BigQuery dataset, table and view are created from the YAML. | Schema, dq.rules and the build stages are unchanged from the local run."
/>

### AWS / Athena

<CliCast
  src="/forge_docs/demos/aws-quickstart.svg"
  title="AWS quickstart — S3 + Glue + Athena"
  caption="Same Customer 360 contract, AWS provider extra installed, binding swapped to the AWS platform. S3 bucket provisioned, Glue catalog auto-created, Athena made queryable — all from fluid apply."
  width="920"
  insight="One YAML, S3 + Glue + Athena, no console clicks in the recording. | The S3 bucket, Glue database and Glue table are provisioned by fluid apply. | The same contract can target GCP or Snowflake by changing its binding block."
/>

### Snowflake

<CliCast
  src="/forge_docs/demos/snowflake-quickstart.svg"
  title="Snowflake quickstart — dry-run flow"
  caption="The dry version: env-file credentials, contract validation, plan preview, and apply --mode dry-run rendering DDL without firing it. For the live-auth version see snowflake-real below."
  width="920"
  insight="Four commands, dry-run, nothing fired. | --mode dry-run renders the DDL without running it, so it fits a pre-flight check on a PR. | CREATE DATABASE / SCHEMA / TABLE / VIEW DDL is rendered for review before any statement runs."
/>

---

## AI copilot — full Gemini-powered flow

The `fluid forge` AI copilot generating a finance-domain contract end-to-end: project memory loaded, finance domain expertise pack applied (SOX + GDPR), local context discovered, a Gemini streaming call, and the contract emerging block-by-block with the agentPolicy gate. The version below is hand-scripted to follow the real-API flow; a real-capture script (`scripts/demos/forge_gemini_real_capture.py`) is kept for recording an actual session.

<CliCast
  src="/forge_docs/demos/forge-gemini.svg"
  title="fluid forge --domain finance --llm-provider gemini --llm-model gemini-2.5-flash"
  caption="The full agent flow: memory → domain pack → discovery → streaming → contract emit (schema, dq.rules, accessPolicy, agentPolicy, sovereignty) → auto-validation → memory persist."
  width="920"
  insight="11.4 s · 1834 tokens · ~$0.0021 — full data product spec generated. | 11 schema fields tagged · 4 dq.rules · 3 RBAC grants · agentPolicy gating LLM access. | Memory persisted — the next fluid forge call inherits this vocabulary."
/>

---

## Snowflake live-auth dry-run

The `snowflake-biz-lab` flow at full fidelity: env credentials sourced, real `validate --strict`, `plan` against the live account, `apply --mode dry-run` rendering DDL without firing it, then `policy-apply --mode check` over the compiled IAM bindings.

<CliCast
  src="/forge_docs/demos/snowflake-real.svg"
  title="Snowflake — validate → plan → apply --mode dry-run → policy-apply --mode check"
  caption="Live auth (account=acme-demo placeholder; the scrubber substitutes the real account name). No DDL fires, no RBAC mutates — just the auth + connectivity + dry-render flow you'd run before a real production deploy."
  width="920"
  insight="A pre-flight a reviewer can read before merge. | DDL rendered, RBAC bindings dry-checked, drift detected, with no changes to the live account. | The four commands can run in a PR check."
/>

---

## AI copilot — interview shape only

`fluid forge --blank` skips the LLM call entirely and just scaffolds the structured stub for the chosen domain. Useful when you know what you want and don't need an LLM round-trip.

<CliCast
  src="/forge_docs/demos/forge-blank.svg"
  title="fluid forge --blank --domain finance"
  caption="The blank skeleton with finance-domain defaults pre-seeded: SOX/GDPR regulatory framework, 'training' and 'fine_tuning' denied use cases, Gold layer assignment. Fill in the expose blocks yourself — no LLM call."
  width="920"
  insight="A skeleton in about 2 seconds, with the governance defaults that AI mode seeds. | SOX + GDPR, 'training' / 'fine_tuning' denied, Gold layer, pre-seeded for finance. | You fill in the expose blocks."
/>

---

## Policy + IAM compilation

The `policy-check` → `generate artifacts` → `policy-apply --mode check` triple. Validates the access policy, compiles to cloud IAM bindings (BigQuery/Snowflake/AWS), and hands the bindings to the provider in check mode (no live IAM mutations; as of 0.18.1 `--mode enforce` makes none either).

<CliCast
  src="/forge_docs/demos/policy-flow.svg"
  title="policy-check → generate artifacts → policy-apply --mode check"
  caption="Three commands, full policy round-trip from declarative `accessPolicy.grants` in YAML to native cloud IAM JSON, then a check-mode run that reports the bindings the provider received."
  width="920"
  insight="Three commands turn declarative YAML grants into native cloud IAM bindings. | The recording shows four artifacts from one contract: bindings.json (BigQuery/Snowflake), opa-policies.rego (OPA), ODCS and ODPS. | --mode check reports the bindings the provider received; as of 0.18.1 --mode enforce changes no permissions either."
/>

---

## agentPolicy enforcement (LLM / AI governance)

Declare `agentPolicy` in YAML, validate it, see the enforcement summary, watch a replay of agent reads (allow/deny) against the policy.

<CliCast
  src="/forge_docs/demos/agent-policy.svg"
  title="agentPolicy — declare, validate, gate (validate → policy-check → audit)"
  caption="The YAML block (allowedModels, deniedUseCases, canStore, auditRequired) → validate → policy-check enforcement summary → 4 replayed agent reads (gpt-4 allowed, claude-3 + training denied, unlisted model denied, gemini summarization allowed)."
  width="920"
  insight="Declared in YAML, checked per request in the replay, audited. | The replay checks models, use cases, storage and token limits. | auditRequired=true routes records to the platform's audit log (BigQuery audit log, Snowflake ACCESS_HISTORY, CloudTrail)."
/>

---

## Long-form scenario casts

The casts below pair with the [See it run](/forge_docs/see-it-run.html) page. Each tells a story (problem, CLI flow, result) in about 30-50 seconds, with takeaway numbers from the recording.

### `$0.03` per data product — three providers, one contract

<CliCast
  src="/forge_docs/demos/forge-multi-provider.svg"
  title="fluid forge data-model — same intent, three providers, real cost figures"
  caption="Eight lines of intent YAML. Anthropic, OpenAI, Ollama — same flag swapped each time. The recording shows all three producing a valid contract and the same dbt project layout, with the token counts and costs of that run."
  width="920"
  insight="$0.03 total across the three providers in this run, $0.00 on local Ollama. | The three contracts in this recording have the same 11 fields, 4 dq.rules, accessPolicy and agentPolicy. | The provider is one flag: --llm-provider."
/>

### Six months → sixty seconds — source-aligned Bronze

<CliCast
  src="/forge_docs/demos/source-aligned-bronze.svg"
  title="fluid init --discover postgres://... — Bronze contract in 60 seconds"
  caption="Connect, scan information_schema (47 ms), infer 28 tables / 143 columns / 12 PII candidates / 8 foreign keys, emit a complete Bronze contract.fluid.yaml, validate, apply against embedded DuckDB. 6.2 seconds total. Then show the engine swap path."
  width="920"
  insight="6.2 seconds from Postgres URL to a Bronze contract in this recording, on embedded DuckDB. | The engine is the contract's engine: field. | The source spec, PII flags and Bronze table layout live in the contract, separate from the runner."
/>

### 23 questions, skipped — guided UX

<CliCast
  src="/forge_docs/demos/guided-forge-ux.svg"
  title="fluid forge — guided UX in action"
  caption="47 ms welcome scan finds 3 CSVs + 2 dbt models + 1 README, infers domain (finance) and PII (5 columns). 5-mode picker. 4 questions answered (most accept the inferred default with ↵). Cost-cap progress in real time ($0.000 → $0.021 of $0.050 cap). Pre-write panel shows exactly what will + won't change."
  width="920"
  insight="4 questions answered in this recording. | The 47 ms welcome scan and domain inference supplied the other answers. | $0.021 spent of a $0.050 cap. Slash commands at the prompts: /skip /back /help /quit /save."
/>

### 3am Slack ping → ship in 90 seconds

<CliCast
  src="/forge_docs/demos/day2-ops.svg"
  title="3am Slack ping → ship in 90 seconds"
  caption="PagerDuty: freshness SLA breached. fluid runs status shows 3 consecutive failures. fluid runs logs --component dlq surfaces the root cause. fluid runs diff shows what changed since the last OK run. One-line contract fix. fluid ship. 87 seconds end-to-end. Recovered 12,361 rows."
  width="920"
  insight="Slack ping to ship: 87 seconds in this recording. | fluid runs status / logs / diff trace the failure in three commands. | One-line contract fix and fluid ship."
/>

### `$0.50` → `$0.05` — agent-loop compaction

<CliCast
  src="/forge_docs/demos/agent-compaction.svg"
  title="Agent-loop compaction — three strategies, real before/after costs"
  caption="20-turn baseline: $0.503/run, super-linear context bloat (5K → 67K → 298K tokens). Three strategies side-by-side: truncate (5.8× cheaper), summarize (9.3× cheaper), hybrid (10.5× cheaper). One env var: FLUID_COMPACTION_STRATEGY=hybrid."
  width="920"
  insight="$0.503 to $0.048 per 20-turn run in this recording (10.5x), with no code change. | truncate, summarize and hybrid are set with FLUID_COMPACTION_STRATEGY. | The contract and the agent are unchanged; only context-window handling differs."
/>

---

## How the casts are produced

The pipeline that built each SVG above:

```text
   scripts/demos/<name>.py            ← cast generator
                ↓
        /tmp/casts/<name>.cast.raw    ← raw asciinema cast (gitignored)
                ↓
        scripts/cast-v3-to-v2.py      ← format conversion (asciinema 3.x → 2.x)
                ↓
        scripts/scrub-cast.py         ← strip API keys, JWTs, env-shaped secrets
                ↓
        svg-term --in <cast>          ← render to animated SVG (no --window;
                                          our <CliCast> component supplies
                                          the terminal chrome)
                ↓
   docs/.vuepress/public/demos/<name>.svg   ← the only file that gets committed
```

Two passes of secret-scanning happen:
1. **`scrub-cast.py`** redacts known formats (`AIza…`, `sk-…`, `sk-ant-…`, JWTs, `KEY=…`/`SECRET=…`/`PASSWORD=…` 16+ char values) and substitutes literal `$SNOWFLAKE_ACCOUNT`/`$SNOWFLAKE_USER`/`$GEMINI_API_KEY` env values for friendly placeholders.
2. **Final-SVG grep** in `generate-demos.sh` re-scans the output before keeping the file. If any leak pattern matches in the post-scrub SVG, the file is deleted and the build fails.

The `.cast.raw` working files live in `/tmp/casts/` (gitignored) and are deleted at the end of each render.

To regenerate everything:

```bash
scripts/generate-demos.sh                 # regenerate every cast
scripts/generate-demos.sh --safe-only     # only the credential-free casts
scripts/generate-demos.sh forge-gemini    # one specific cast
```

Source for each cast lives at `scripts/demos/<name>.py` — review or fork freely.
