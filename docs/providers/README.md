# Providers

Fluid Forge uses one contract format across local and provider-backed execution targets.

## Docs baseline

- CLI release covered by the primary docs: `0.8.6`
- Default scaffold (`fluid init --quickstart`) emits `fluidVersion: 0.7.2`
- Discovery-based scaffolds (`fluid init --discover`, `fluid forge`, `fluid product-new`) emit `fluidVersion: 0.7.4` — the latest bundled schema

Some deep-dive provider pages still preserve older `0.7.1` snippets for backward-compatibility context. Those examples should not be read as “current version” guidance.

## Provider overview

Fluid Forge registers four apply-capable cloud providers and two standards providers:

| Provider | Plan / Apply | Scheduling docs stance | Status |
| --- | --- | --- | --- |
| [GCP](./gcp.md) | Yes | Prefer `fluid generate schedule` | Production |
| [AWS](./aws.md) | Yes | Prefer `fluid generate schedule` | Production |
| [Snowflake](./snowflake.md) | Yes | Prefer `fluid generate schedule` | Production |
| [Local](./local.md) | Yes | Local-first onboarding | Production |
| ODCS | Bidirectional at provider layer (`render` + `import_contract` + `validate`) | n/a — standards exchange | Production |
| Bitol ODPS (`odps_bitol`) | Bidirectional at provider layer (`render` + `import_contract` + `validate`) | n/a — standards exchange | Production |

::: tip Runtime requirement for cloud apply
On `v0.8.6`, `fluid apply` against `aws` / `gcp` / `snowflake` auto-compiles the contract to OpenTofu and delegates to the `tofu` binary — install `tofu ≥ 1.6.0` on `PATH`. `local` keeps its native DuckDB apply, no `tofu` needed. See [`fluid generate iac`](/forge_docs/cli/generate-iac.html).
:::

The CLI surface today is asymmetric for the two standards providers — `fluid odcs` exposes `export` / `import` / `validate` / `info`, while `fluid odps-bitol` exposes only `export` / `validate` / `info`. The unified `fluid opds` command added in `0.8.3` covers both specs and adds an `import` subcommand for Bitol — see [`fluid opds`](../cli/odps-bitol.md) and [`fluid odcs`](../cli/odcs.md).

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

Beyond the cloud and local providers, Fluid Forge round-trips contracts against public data-product standards and **publishes** them to catalogs.

### Standards exchange — `fluid opds`

`v0.8.3` introduced a unified `fluid opds` command that dispatches both export and import across the ODPS specs via `--spec`. The standards providers themselves are bidirectional at the provider layer (`render` + `import_contract` + `validate`).

| Spec | Command | What it is |
| --- | --- | --- |
| ODPS — Bitol 1.0.0 | `fluid opds export … --spec bitol-1.0.0` / `fluid opds import` | Bitol variant — 1 ODPS doc + N sibling ODCS contracts (one per output port). |
| ODPS — ODPI 4.1 | `fluid opds export … --spec odpi-4.1` | Open Data Product Initiative single-file variant. Export-only. |
| ODCS | `fluid odcs export` / `fluid odcs import` | Open Data Contract Standard v3.1.0 (Bitol.io). |

Legacy shortcuts remain: [`fluid export-opds`](/forge_docs/cli/export-opds.html), [`fluid odps-bitol`](/forge_docs/cli/odps-bitol.html), [`fluid odps`](/forge_docs/cli/odps.html). New scripts should prefer `fluid opds` with `--spec`.

### Publishing — catalog registrars

`v0.8.3` consolidated catalog publishing under one registry. Contracts opt in via `properties.catalog.register: [<name>]`; three publish-side registrars are active:

| Catalog | Reference |
| --- | --- |
| DataHub | [`catalog overview`](/forge_docs/cli/catalogs/overview.html) → [DataHub publish](/forge_docs/cli/catalogs/datahub.html#publishing-to-datahub) |
| OpenMetadata | [OpenMetadata publish](/forge_docs/cli/catalogs/openmetadata.html) |
| Data Mesh Manager / Entropy Data | [DMM publish](/forge_docs/cli/catalogs/datamesh-manager.html#publishing-to-data-mesh-manager) |
| FLUID Command Center | [`fluid publish`](/forge_docs/cli/publish.html) |

The previously-shipped `glue` and `snowflake_horizon` registrars were retired in `v0.8.3` and folded into the IaC layer — catalog metadata for those targets is now emitted as `aws_glue_catalog_table` / `snowflake_table` resources via [`fluid generate iac`](/forge_docs/cli/generate-iac.html). One source of truth, drift-detected by `tofu plan`.

## Notes

- Use [provider-specific guides](./gcp.md) when you need deep target details.
- Use [CLI Reference](/forge_docs/cli/) for command syntax.
- Use [Getting Started](/forge_docs/getting-started/) for the local-first workflow.

---

> Need a hand with a specific provider? [Start a discussion](https://github.com/Agenticstiger/forge-cli/discussions) or [open an issue](https://github.com/Agenticstiger/forge-cli/issues).
