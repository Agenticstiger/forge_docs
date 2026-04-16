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

Fluid Forge also supports standards and publishing/export workflows such as:

- OPDS
- ODCS
- ODPS
- ODPS-Bitol

## Notes

- Use [provider-specific guides](./gcp.md) when you need deep target details.
- Use [CLI Reference](/cli/) for command syntax.
- Use [Getting Started](/getting-started/) for the local-first workflow.
