# `fluid generate`

Unified artifact generation from FLUID contracts.

## Syntax

```bash
fluid generate <transformation|schedule|ci|standard>
```

## Subcommands

### `fluid generate transformation`

Generate transformation artifacts such as dbt projects or SQL output.

Key options:

- `contract`
- `--output`, `-o`
- `--build-index`
- `--overwrite`
- `--env`
- `--list`
- `--verbose`

### `fluid generate schedule`

Generate orchestration artifacts such as Airflow DAGs, Dagster pipelines, or Prefect flows.

Key options:

- `contract`
- `--output`, `-o`
- `--scheduler`
- `--overwrite`
- `--env`
- `--list`
- `--verbose`

This is the promoted path for orchestration generation.

### `fluid generate ci`

Generate CI/CD pipeline configuration for GitHub Actions, GitLab CI, or Jenkins.

Key options:

- `contract`
- `--system`
- `--out`

### `fluid generate standard`

Export to data product standards.

Key options:

- `contract`
- `--format`, `-f`
- `--out`, `-o`
- `--env`
- `--list`

Supported formats:

| `--format` | What it is | Use it when |
| --- | --- | --- |
| `opds` | Open Data Product Specification (OPDS) JSON, v1.0 | Publishing to OPDS-aware catalogs (Collibra, generic catalogs). Rich product metadata, lineage, SLA, and governance under a single document. Preserves FLUID-specific fields under an `x-fluid` namespace. |
| `odcs` | Open Data Contract Standard (ODCS) v3.1.0 — the Bitol.io standard | Publishing **contract-level** specs (schema, quality, SLA) to Bitol-aligned tooling. Where OPDS describes a whole data product, ODCS focuses on the consumer-facing contract. |
| `odps` | Open Data Product Standard — Bitol variant, input-port lineage | When upstream data-product lineage matters (maps FLUID `consumes[]` to ODPS-Bitol `inputPorts`). Commonly used with Entropy Data / Data Mesh Manager publishing. |
| `odps-bitol` | Standards-compliant Bitol ODPS payload, stricter than `odps` | Strict conformance — fields that are not explicitly declared on a `consumes[]` entry are omitted (no synthetic `contractId`, no default `required: True`). |

### Examples of each format

```bash
fluid generate standard contract.fluid.yaml --format opds        # FLUID -> OPDS v1.0
fluid generate standard contract.fluid.yaml --format odcs        # FLUID -> ODCS v3.1.0
fluid generate standard contract.fluid.yaml --format odps        # FLUID -> ODPS (Bitol)
fluid generate standard contract.fluid.yaml --format odps-bitol  # FLUID -> ODPS (strict)
```

### OPDS environment tuning

The OPDS exporter reads a few environment variables for output shape:

| Env var | Default | Purpose |
| --- | --- | --- |
| `OPDS_INCLUDE_BUILD_INFO` | `true` | Include build information (engine, pattern) |
| `OPDS_INCLUDE_EXECUTION_DETAILS` | `false` | Include execution details (triggers, runtime) |
| `OPDS_TARGET_PLATFORM` | `generic` | Platform-specific tuning (`collibra`, etc.) |
| `OPDS_VALIDATE_OUTPUT` | `true` | Validate the emitted JSON |

All four formats are deterministic — identical input yields byte-identical output, so the result is safe to check into version control.

## Examples

```bash
fluid generate transformation
fluid generate transformation contract.fluid.yaml -o ./dbt_project
fluid generate schedule contract.fluid.yaml --scheduler airflow -o dags
fluid generate ci --system github
fluid generate standard contract.fluid.yaml --format opds
```

## Compatibility note

[`fluid generate-airflow`](./generate-airflow.md) still works for Airflow generation, but current docs lead with `fluid generate schedule --scheduler airflow`.
