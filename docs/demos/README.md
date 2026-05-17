---
title: CLI demos
description: Watch every Fluid Forge workflow in motion. 14 frame-perfect SVG casts — install through deploy, local through Snowflake, the AI copilot, agentPolicy enforcement, and the day-2 ops flow.
---

# 🎬 CLI demos

**14 frame-perfect SVG casts** — install through deploy, local through Snowflake, the AI copilot, agentPolicy enforcement, day-2 incident response, and agent-loop compaction. Each one carries a takeaway popup with the punchline numbers. Click play — the SVG only animates after you opt in (no autoplay, no JS).

> **Convinced? → [Install in 30 seconds](/forge_docs/getting-started/)**. Want longer-form proof of specific workflows? → [See it run](/forge_docs/see-it-run.html) (5 narrative scenarios, ~50 s each, with takeaway numbers).

---

## Install + run, locally

Start here. No cloud account, no credit card, ~30 seconds end-to-end.

<CliCast
  src="/forge_docs/demos/local-quickstart.svg"
  title="fluid init my-project --quickstart  →  validate  →  plan  →  apply"
  caption="Install the CLI, scaffold the Customer 360 Analytics contract from the quickstart template, validate it against the 0.7.2 schema, preview the plan, and apply it against the local DuckDB provider. Two exposes — a master table and a high-value-customer view — land as Parquet under output/."
  width="920"
  insight="30 seconds. No cloud account. No credit card. | The contract.fluid.yaml you wrote is the contract that ran. | Local DuckDB + Parquet artifact — exactly what production produces, but offline."
/>

---

## Same contract, different cloud

Swap `binding.platform` and re-deploy. The contract, schema, dq.rules, and the multi-stage build all stay byte-identical — only the cloud-specific binding fields change.

### GCP / BigQuery

<CliCast
  src="/forge_docs/demos/gcp-quickstart.svg"
  title="GCP quickstart — install, swap one line, deploy"
  caption="From the local Customer 360 contract to a fully-deployed BigQuery dataset, in seconds. The `git diff` shows only the binding block changing — schema, dq.rules, and the 5-stage build all stay byte-identical."
  width="920"
  insight="Same contract. One line changed (platform: local → platform: gcp). | BigQuery dataset, table, and view — all created from the YAML you already had. | Schema, dq.rules, the 5-stage build — byte-identical to the local run."
/>

### AWS / Athena

<CliCast
  src="/forge_docs/demos/aws-quickstart.svg"
  title="AWS quickstart — S3 + Glue + Athena"
  caption="Same Customer 360 contract, AWS provider extra installed, binding swapped to the AWS platform. S3 bucket provisioned, Glue catalog auto-created, Athena made queryable — all from fluid apply."
  width="920"
  insight="One YAML. S3 + Glue + Athena. Zero console clicks. | The S3 bucket, Glue database, and Glue table are all provisioned by fluid apply — every resource traceable to the contract. | Same contract works on GCP and Snowflake — change one line of YAML, redeploy."
/>

### Snowflake

<CliCast
  src="/forge_docs/demos/snowflake-quickstart.svg"
  title="Snowflake quickstart — dry-run flow"
  caption="The dry version: env-file credentials, contract validation, plan preview, and apply --mode dry-run rendering DDL without firing it. For the live-auth version see snowflake-real below."
  width="920"
  insight="Snowflake-ready in 4 commands — dry-run, zero side effects, nothing fired. | Use --mode dry-run for pre-flight on every PR; drop it for production. | CREATE DATABASE / SCHEMA / TABLE / VIEW DDL is rendered for review before a single statement fires."
/>

---

## AI copilot — full Gemini-powered flow

The `fluid forge` AI copilot generating a finance-domain contract end-to-end: project memory loaded, finance domain expertise pack applied (SOX + GDPR), local context discovered, a Gemini streaming call, and the contract emerging block-by-block with the agentPolicy gate. The hand-scripted version below mirrors the real-API flow at frame-perfect fidelity; a real-capture script (`scripts/demos/forge_gemini_real_capture.py`) is preserved for users who want to record an actual session.

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
  insight="The PR pre-flight you wish you had — every reviewer sees the deployed-state diff before merge, not after. | DDL rendered, RBAC bindings dry-checked, drift detected — zero side effects on the live account. | Drop this 4-command chain into your PR-merge GitHub Action and incidents shift left of merge."
/>

---

## AI copilot — interview shape only

`fluid forge --blank` skips the LLM call entirely and just scaffolds the structured stub for the chosen domain. Useful when you know what you want and don't need an LLM round-trip.

<CliCast
  src="/forge_docs/demos/forge-blank.svg"
  title="fluid forge --blank --domain finance"
  caption="The blank skeleton with finance-domain defaults pre-seeded: SOX/GDPR regulatory framework, 'training' and 'fine_tuning' denied use cases, Gold layer assignment. Fill in the expose blocks yourself — no LLM call."
  width="920"
  insight="Skeleton in 2 seconds — same governance defaults as AI mode. | SOX + GDPR, 'training' / 'fine_tuning' denied, Gold layer — pre-seeded for finance. | You fill the expose blocks; everything else is already opinionated."
/>

---

## Policy + IAM compilation

The `policy-check` → `generate artifacts` → `policy-apply --mode check` triple. Validates the access policy, compiles to native cloud IAM (BigQuery/Snowflake/AWS), and runs the bindings in check-only mode (no live IAM mutations).

<CliCast
  src="/forge_docs/demos/policy-flow.svg"
  title="policy-check → generate artifacts → policy-apply --mode check"
  caption="Three commands, full policy round-trip from declarative `accessPolicy.grants` in YAML to native cloud IAM JSON, then a dry-run that shows exactly which bindings would apply against the deployed state."
  width="920"
  insight="3 commands turn declarative YAML grants into native cloud IAM — auditable, reviewable, shippable. | One contract emits 4 artifacts: bindings.json (BigQuery/Snowflake) + opa-policies.rego (OPA) + ODCS + OPDS. Catalogs that already speak any of these can ingest yours without translation. | --mode check shows exactly what would change before it fires. Flip to --mode enforce only when the diff is clean and reviewed."
/>

---

## agentPolicy enforcement (LLM / AI governance)

Declare `agentPolicy` in YAML, validate it, see the enforcement summary, watch a replay of agent reads (allow/deny) against the policy.

<CliCast
  src="/forge_docs/demos/agent-policy.svg"
  title="agentPolicy — declare, validate, gate (validate → policy-check → audit)"
  caption="The YAML block (allowedModels, deniedUseCases, canStore, auditRequired) → validate → policy-check enforcement summary → 4 replayed agent reads (gpt-4 allowed, claude-3 + training denied, unlisted model denied, gemini summarization allowed)."
  width="920"
  insight="Declared in YAML. Enforced at read-time. Audited natively. | Models, use-cases, storage, token limits — every dimension checked per request. | auditRequired=true → records land in BigQuery audit log / Snowflake ACCESS_HISTORY / CloudTrail."
/>

---

## Long-form scenario casts

The 5 casts below pair with the [See it run](/forge_docs/see-it-run.html) page — each tells a story (problem → CLI flow → punchline) at ~30-50 seconds with takeaway numbers.

### `$0.03` per data product — three providers, one contract

<CliCast
  src="/forge_docs/demos/forge-multi-provider.svg"
  title="fluid forge data-model — same intent, three providers, real cost figures"
  caption="Eight lines of intent YAML. Anthropic, OpenAI, Ollama — same flag swapped each time. All three emit the same valid contract, the same dbt project layout. Real production token counts and costs."
  width="920"
  insight="$0.03 total across all three cloud providers — $0.00 if you run locally on Ollama. | All three contracts are byte-identical: same 11 fields, same 4 dq.rules, same accessPolicy + agentPolicy. | Switch providers anytime by flipping --llm-provider — no vendor lock, no contract drift."
/>

### Six months → sixty seconds — source-aligned Bronze

<CliCast
  src="/forge_docs/demos/source-aligned-bronze.svg"
  title="fluid init --discover postgres://... — Bronze contract in 60 seconds"
  caption="Connect, scan information_schema (47 ms), infer 28 tables / 143 columns / 12 PII candidates / 8 foreign keys, emit a complete Bronze contract.fluid.yaml, validate, apply against embedded DuckDB. 6.2 seconds total. Then show the engine swap path."
  width="920"
  insight="6.2 seconds from Postgres URL to a working Bronze contract — no cluster, no JVM. | The contract.fluid.yaml stays identical when you swap engine: between duckdb / dlt / meltano / airbyte / kafka-connect / debezium. | Outgrow embedded mode? Change one line. The source spec, PII flags, and Bronze table layout don't move."
/>

### 23 questions, skipped — guided UX

<CliCast
  src="/forge_docs/demos/guided-forge-ux.svg"
  title="fluid forge — guided UX in action"
  caption="47 ms welcome scan finds 3 CSVs + 2 dbt models + 1 README, infers domain (finance) and PII (5 columns). 5-mode picker. 4 questions answered (most accept the inferred default with ↵). Cost-cap progress in real time ($0.000 → $0.021 of $0.050 cap). Pre-write panel shows exactly what will + won't change."
  width="920"
  insight="4 questions answered. Most CLIs ask 27. | 47 ms welcome scan replaced 23 of them. Domain inference replaced 4. | $0.021 spent of $0.050 cap. Slash commands at every prompt: /skip /back /help /quit /save."
/>

### 3am Slack ping → ship in 90 seconds

<CliCast
  src="/forge_docs/demos/day2-ops.svg"
  title="3am Slack ping → ship in 90 seconds"
  caption="PagerDuty: freshness SLA breached. fluid runs status shows 3 consecutive failures. fluid runs logs --component dlq surfaces the root cause. fluid runs diff shows what changed since the last OK run. One-line contract fix. fluid ship. 87 seconds end-to-end. Recovered 12,361 rows."
  width="920"
  insight="Slack ping → ship: 87 seconds. Three consecutive failures resolved. | fluid runs status / logs / diff narrate the failure in three commands. | One-line contract fix + fluid ship — apply, verify, drain DLQ, restore SLA in one move."
/>

### `$0.50` → `$0.05` — agent-loop compaction

<CliCast
  src="/forge_docs/demos/agent-compaction.svg"
  title="Agent-loop compaction — three strategies, real before/after costs"
  caption="20-turn baseline: $0.503/run, super-linear context bloat (5K → 67K → 298K tokens). Three strategies side-by-side: truncate (5.8× cheaper), summarize (9.3× cheaper), hybrid (10.5× cheaper). One env var: FLUID_COMPACTION_STRATEGY=hybrid."
  width="920"
  insight="$0.503 → $0.048 per 20-turn agent run. 10.5× cheaper, no code change. | truncate (free), summarize (high-recall), hybrid (recommended for production). | Works with every --llm-provider. Same contract. Same agent. Just smarter context window management."
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
