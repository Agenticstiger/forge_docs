# Fluid Forge Docs Baseline: CLI `0.11.0`

**Release Date:** July 13, 2026
**Status:** Superseded by [`0.12.0`](./RELEASE_NOTES_0.12.0.md)

## Headline

`0.11.0` is the **AI-ready + RAG** release. A data product can now expose a **vector /
embeddings output port** so it's directly consumable by retrieval-augmented generation
(`fluid generate vector`), the authoring copilot gains a **semantic-drift guard** that catches
renamed/dropped/retyped columns before they ship, the AWS provider learns
**emulator-compatible config** so `fluid apply` runs against LocalStack, and a built-in
**`ai_ready` agent** labels the columns that are safe to embed. It also folds blueprints into a
single guided `fluid init` Quickstart, adds `fluid verify --reconcile-dbt`, and lands a wave of
security hardening (redaction symmetry, SQL-literal safety, LLM exception-text containment).

Contract schema is **unchanged at `0.7.5`** and the default validation version is still the
prior stable — the new `vectorConfig` and streaming fields live in the **opt-in `0.7.5`
preview**, so existing contracts validate exactly as before. `pip install --upgrade
data-product-forge`.

::: tip Who should upgrade
Anyone building for AI/RAG consumption (the vector output port + `ai_ready` agent are the
headline), anyone authoring contracts with the copilot (semantic-drift guard), and anyone who
tests infrastructure locally (LocalStack emulator support). The change is **additive** — no
contract changes, no schema-default bump.
:::

## What changed in `v0.11.0`

### Added — vector / embeddings output port (preview)

- **New command [`fluid generate vector`](./cli/generate-vector.md).** Compiles a contract's
  `ai-embeddable` columns into a **pgvector** target — `CREATE EXTENSION vector`, a
  one-row-per-chunk embeddings table, and an ANN index (`hnsw` default / `ivfflat` / `none`) —
  plus a `vector_manifest.json` recording the embedding model, dimensions, and distance metric.
- Driven by a new `binding.vectorConfig` block. **Preview:** opt-in under
  `fluidVersion: "0.7.5"`. Graduates to default-on when `0.7.5` is promoted to stable.

### Added — semantic-drift guard in the copilot

- The authoring/refine copilot now runs a **semantic-drift guard** that flags when an
  LLM-authored or `--refine`-edited contract drifts from its source schema or prior version —
  dropped, renamed, or retyped columns. Asymmetric baselines: a dropped column is *breaking*
  against a prior version but a *legitimate projection* from source.
- Opt-in via **`FLUID_FORGE_DRIFT_GUARD=1`**. Fail-open and non-breaking. See
  [Environment Variables](./advanced/environment-variables.md).

### Added — AWS emulator-compatible config (LocalStack)

- When a **custom AWS endpoint** is set (`AWS_ENDPOINT_URL` / `AWS_ENDPOINT_URL_<SERVICE>`), the
  AWS IaC emitter now writes a `provider "aws"` block with path-style S3 addressing and the
  STS / IAM / metadata validation skips that emulators (LocalStack, moto) require. On real AWS
  the emitted output is **byte-for-byte unchanged**. See
  [AWS Provider → local testing](./providers/aws.md).

### Added — built-in `ai_ready` agent

- A built-in **`ai_ready`** Forge agent enforces AI-readiness metadata and labels
  `ai-embeddable: "true"` on the safe free-text columns the vector output port consumes.

### Added — AI-tools for the agent loop

- `fetch_sample_rows` (read-only, row-capped, redacted live DB lookups), a hosted-MCP delegation
  registry (GitHub / Snowflake MCP), and a lazy tool-search deferral pattern that keeps the
  `fluid --help` cold path light. All gated behind opt-in `FLUID_FORGE_*` flags.

### Added — `fluid verify --reconcile-dbt`

- `fluid verify` can now reconcile a contract's schema against a dbt project and report drift
  (missing/extra columns, type mismatches).

### Changed — simpler `fluid init`

- Blueprints are folded into a single guided **Quickstart** starter picker — the init menu drops
  from five rows to three (Quickstart / AI / Empty).

### Schema

- **Redshift Serverless + Kinesis** fields added to `bindingLocation` in the `0.7.5` preview
  (`stream`, `namespace`, `workgroup`, `iam_role_arn`, `external_schema`, `glue_database`).
  Additive; the `0.7.5` preview remains opt-in.

### Security & internals

- Redaction-symmetry gaps closed across both logging layers; SQL string-literals routed through
  the central `quote_string_literal`; LLM exception text no longer round-trips into model
  context or logs. Import cycles severed (copilot↔cli, build_runners→cli). DataHub registrar
  hardened with retry/backoff.

## Compatibility

- **Contract schema:** unchanged — default stays on the prior stable; `0.7.5` remains opt-in
  preview. Existing contracts validate identically.
- **SDK / custom-scaffold:** unchanged (`data-product-forge-sdk 0.10.0`,
  `data-product-forge-custom-scaffold 0.4.0`).
- **Install:** `pip install --upgrade data-product-forge` → `0.11.0`.
