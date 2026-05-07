---
title: CLI demos
description: Watch every Fluid Forge workflow in motion. 8 short asciinema-rendered casts — install through deploy, local through Snowflake, and the AI copilot calling a real LLM.
---

# 🎬 CLI demos

Eight short demos, each under 30 seconds, showing what the canonical workflow looks like end-to-end. Click play on any cast — the SVG only animates after you opt in (no autoplay, no JS).

---

## Install + run, locally

Start here. No cloud account, no credit card, ~30 seconds end-to-end.

<CliCast
  src="/forge_docs/demos/local-quickstart.svg"
  title="fluid init my-project --quickstart  →  validate  →  plan  →  apply"
  caption="Install the CLI, scaffold a Bitcoin tracker contract from the quickstart template, validate it against the 0.7.2 schema, preview the plan, and apply it against the local DuckDB provider. The data product lands at runtime/out/bitcoin_prices.parquet."
  width="920"
  insight="30 seconds. No cloud account. No credit card. | The contract.fluid.yaml you wrote is the contract that ran. | Local DuckDB + Parquet artifact — exactly what production produces, but offline."
/>

---

## Same contract, different cloud

Swap `binding.platform` and re-deploy. The contract, schema, IAM grants, and AI policy all stay byte-identical — only the cloud-specific fields change.

### GCP / BigQuery

<CliCast
  src="/forge_docs/demos/gcp-quickstart.svg"
  title="GCP quickstart — install, swap one line, deploy"
  caption="From the local contract to a fully-deployed BigQuery table with IAM bindings, in 30 seconds. Note the `git diff` showing only the four lines that change — schema, dq.rules, accessPolicy.grants, agentPolicy all stay identical."
  width="920"
  insight="Same contract. One line changed (platform: local → platform: gcp). | BigQuery dataset, table, IAM grants — all created from the YAML you already had. | Schema, dq.rules, agentPolicy, sovereignty — byte-identical to the local run."
/>

### AWS / Athena

<CliCast
  src="/forge_docs/demos/aws-quickstart.svg"
  title="AWS quickstart — S3 + Glue + Athena"
  caption="Same contract, AWS provider extra installed, binding swapped to s3_file with a bucket + prefix. Glue catalog auto-created, Athena workgroup wired up, IAM resource policies applied."
  width="920"
  insight="Same contract. New cloud. S3 + Glue + Athena from one YAML. | IAM resource policies compiled from accessPolicy.grants — no console clicks. | Drop in --env staging or --env prod for environment promotion."
/>

### Snowflake

<CliCast
  src="/forge_docs/demos/snowflake-quickstart.svg"
  title="Snowflake quickstart — dry-run flow"
  caption="The dry version: env-file credentials, contract validation, plan preview, and apply --mode dry-run rendering DDL without firing it. For the live-auth version see snowflake-real below."
  width="920"
  insight="Snowflake-ready in 4 commands. Live auth, real DDL, zero side effects. | Use --mode dry-run for pre-flight on every PR; drop it for production. | RBAC grants from accessPolicy.grants compile to native GRANT statements."
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
  insight="4 commands. Live auth. Zero mutations. The PR pre-flight you wish you had. | DDL rendered, RBAC bindings checked, drift detected — without touching production. | Flip --mode dry-run → --mode enforce when the diff is clean and reviewed."
/>

---

## AI copilot — interview shape only

`fluid forge --blank` skips the LLM call entirely and just scaffolds the structured stub for the chosen domain. Useful when you know what you want and don't need an LLM round-trip.

<CliCast
  src="/forge_docs/demos/forge-blank.svg"
  title="fluid forge --blank --domain finance"
  caption="The blank skeleton with finance-domain defaults pre-seeded: SOX/GDPR regulatory framework, 'training' and 'fine-tuning' denied use cases, Gold layer assignment. Fill in the expose blocks yourself — no LLM call."
  width="920"
  insight="Skeleton in 2 seconds — same governance defaults as AI mode. | SOX + GDPR, 'training' / 'fine-tuning' denied, Gold layer — pre-seeded for finance. | You fill the expose blocks; everything else is already opinionated."
/>

---

## Policy + IAM compilation

The `policy-check` → `generate artifacts` → `policy-apply --mode check` triple. Validates the access policy, compiles to native cloud IAM (BigQuery/Snowflake/AWS), and runs the bindings in check-only mode (no live IAM mutations).

<CliCast
  src="/forge_docs/demos/policy-flow.svg"
  title="policy-check → generate artifacts → policy-apply --mode check"
  caption="Three commands, full policy round-trip from declarative `accessPolicy.grants` in YAML to native cloud IAM JSON, then a dry-run that shows exactly which bindings would apply against the deployed state."
  width="920"
  insight="YAML grants → real cloud IAM. Compiled, audited, shippable. | bindings.json (BigQuery / Snowflake) + opa-policies.rego (OPA) + ODCS / OPDS standards. | --mode check first (never fires) — flip to --mode enforce when reviewed."
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
scripts/generate-demos.sh                 # all 8
scripts/generate-demos.sh --safe-only     # the 6 scripted (no creds)
scripts/generate-demos.sh forge-gemini    # one specific cast
```

Source for each cast lives at `scripts/demos/<name>.py` — review or fork freely.
