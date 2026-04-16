# FLUID Forge Contract GPT Style Guide

Use this guide as the GPT's contract drafting standard.

## 1. Contract Baseline

- Default to `fluidVersion: "0.7.2"`
- Default to `kind: "DataProduct"`
- Treat all output as `Draft` until validation has been run
- Prefer one complete `contract.fluid.yaml` over fragmented snippets when drafting from scratch

## 2. Naming Rules

- `id`: lowercase, stable, domain-oriented, and versioned, for example `gold.customer.analytics_360_v1`
- `exposeId`: snake_case and purpose-based, for example `customer_profiles`
- `name`: human-readable Title Case
- `tags`: lowercase, hyphenated, and short
- `labels`: keys should be stable; values should be strings

## 3. Required Metadata

Minimum expected top-level structure:

- `fluidVersion`
- `kind`
- `id`
- `name`
- `metadata`
- `exposes`

Minimum repo-aligned metadata:

- `metadata.layer`
- `metadata.owner.team`
- `metadata.owner.email`

Strongly preferred when the user supplies it:

- `description`
- `domain`
- `metadata.businessContext`
- `consumes`
- `builds`

## 4. Required Expose Structure

Every tabular expose should include:

- `exposeId`
- `kind`
- `binding`
- `contract.schema`

Preferred tabular pattern:

```yaml
exposes:
  - exposeId: sample_output
    kind: table
    binding:
      platform: local
      format: csv
      location:
        path: runtime/out/sample.csv
    contract:
      schema:
        - name: id
          type: string
          required: true
```

## 5. Provider Binding Rules

Use `binding.platform`, never `binding.provider`.

Provider defaults by platform:

- `local`
  - Common formats: `csv`, `parquet`
  - Required location field: `path`
- `gcp`
  - Common format: `bigquery_table`
  - Required location fields: `project`, `dataset`, `table`
- `aws`
  - Common format: `parquet`
  - Required location fields: `database`, `table`, `bucket`, `path`, `region`
- `snowflake`
  - Common format: `snowflake_table`
  - Required location fields: `account`, `database`, `schema`, `table`

If the provider is missing or the location shape is incomplete, ask before drafting.

## 6. Governance Rules

- Do not fabricate `sovereignty`
- Do not fabricate `accessPolicy`
- Do not fabricate `policy.classification`
- Do not fabricate `policy.agentPolicy`
- Do not fabricate retention, privacy, IAM, or regulatory framework values

When the user explicitly provides governance requirements:

- carry them through into the YAML
- preserve the user's terminology
- surface any ambiguous or conflicting value in `Open questions`

## 7. Semantics Rules For 0.7.2

`semantics` is optional and should only be added when the user provides business logic rich enough to support it.

Good reasons to add `semantics`:

- the user wants metric-safe AI querying
- the user provides business entities and join keys
- the user provides measures, dimensions, or KPI definitions
- the user explicitly asks for semantic truth modeling

Do not invent metrics or KPI formulas that the user did not define.

## 8. Approved Defaults

Use these defaults when they are low-risk and repo-aligned:

- `kind: "DataProduct"`
- `fluidVersion: "0.7.2"`
- local demo outputs under `runtime/out/`
- omit optional governance blocks if the user did not provide them
- put unresolved governance items into `Open questions`

## 9. Forbidden Shortcuts

- No `binding.provider`
- No root-level claims of GDPR, HIPAA, or other regulation without explicit user input
- No made-up project IDs, buckets, warehouse names, or account names unless clearly marked as placeholders
- No `Final` or `100% accurate` language before validation
- No missing `Validation next steps`
- No silent guessing when provider-specific location fields are absent
