# Providers

Fluid Forge uses one contract format across local and provider-backed execution targets.

## Docs baseline

- CLI release covered by the primary docs: `0.7.9`
- Current scaffolded contract examples: `fluidVersion: 0.7.2`

Some deep-dive provider pages still preserve older `0.7.1` snippets for backward-compatibility context. Those examples should not be read as “current version” guidance.

## Provider overview

| Provider | Plan / Apply | Scheduling docs stance | Status |
| --- | --- | --- | --- |
| [GCP](./gcp.md) | Yes | Prefer `fluid generate schedule` | Production |
| [AWS](./aws.md) | Yes | Prefer `fluid generate schedule` | Production |
| [Snowflake](./snowflake.md) | Yes | Prefer `fluid generate schedule` | Production |
| [Local](./local.md) | Yes | Local-first onboarding | Production |

Compatibility note:
`fluid generate-airflow` still exists, but the primary docs path is `fluid generate schedule --scheduler airflow`.

## Quick start by provider

### GCP

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
fluid apply contract.fluid.yaml --provider gcp --yes
```

### AWS

```bash
aws configure
fluid apply contract.fluid.yaml --provider aws --yes
```

### Snowflake

```bash
export SNOWFLAKE_ACCOUNT=your_account
export SNOWFLAKE_USER=your_user
fluid apply contract.fluid.yaml --provider snowflake --yes
```

### Local

```bash
fluid init my-project --quickstart
cd my-project
fluid apply contract.fluid.yaml --yes
```

## Standards and catalogs

Beyond the apply-capable providers above, Fluid Forge can **export** contracts to public data-product standards and **publish** them to catalogs. Both surfaces live inside existing CLI commands rather than as separate provider pages.

### Export formats — `fluid generate standard`

| Format | What it is | Reference |
| --- | --- | --- |
| OPDS | Open Data Product Specification JSON v1.0 | [`generate standard`](/cli/generate.html#fluid-generate-standard) |
| ODCS | Open Data Contract Standard v3.1.0 (Bitol.io) | [`generate standard`](/cli/generate.html#fluid-generate-standard) |
| ODPS | Open Data Product Standard — Bitol variant, input-port lineage | [`generate standard`](/cli/generate.html#fluid-generate-standard) |
| ODPS-Bitol | ODPS in strict-conformance mode | [`generate standard`](/cli/generate.html#fluid-generate-standard) |

Shortcut: `fluid export-opds contract.fluid.yaml` — equivalent to `fluid generate standard --format opds`.

### Publishing — `fluid publish`

| Catalog | Reference |
| --- | --- |
| FLUID Command Center | [`fluid publish`](/cli/publish.html) |
| Data Mesh Manager / Entropy Data | [`fluid publish` → DMM section](/cli/publish.html#publishing-to-data-mesh-manager-entropy-data) |

## Notes

- Use [provider-specific guides](./gcp.md) when you need deep target details.
- Use [CLI Reference](/cli/) for command syntax.
- Use [Getting Started](/getting-started/) for the local-first workflow.

---

> Need a hand with a specific provider? [Start a discussion](https://github.com/Agenticstiger/forge-cli/discussions) or [open an issue](https://github.com/Agenticstiger/forge-cli/issues).
