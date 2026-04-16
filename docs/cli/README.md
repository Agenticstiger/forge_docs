# CLI Reference

This section tracks the promoted command surface shown by `fluid --help` in `forge-cli` `0.7.9`.

## Read this first

- CLI release examples in this section use `0.7.9`
- Contract examples use `fluidVersion: 0.7.2`
- `fluid version` and `fluidVersion` are different things

## Core Workflow

| Command | What it is for |
| --- | --- |
| [`fluid init`](./init.md) | Create a new project quickly from a scaffold or template |
| [`fluid forge`](./forge.md) | AI-assisted scaffolding with optional discovery, memory, and domain hints |
| [`fluid validate`](./validate.md) | Validate a contract against bundled or fetched FLUID schemas |
| [`fluid plan`](./plan.md) | Preview planned execution and optionally write a plan JSON or HTML view |
| [`fluid apply`](./apply.md) | Run a contract or saved plan end-to-end |

The newcomer path is usually:

```bash
fluid init my-project --quickstart
cd my-project
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

## Generate

| Command | What it is for |
| --- | --- |
| [`fluid generate`](./generate.md) | Unified generation entry point |
| `fluid generate transformation` | Emit transformation artifacts such as dbt or SQL |
| `fluid generate schedule` | Emit Airflow, Dagster, or Prefect scheduling artifacts |
| `fluid generate ci` | Generate GitHub Actions, GitLab CI, or Jenkins templates |
| `fluid generate standard` | Export contracts to OPDS, ODCS, ODPS, or ODPS-Bitol |

Compatibility note:
[`fluid generate-airflow`](./generate-airflow.md) still exists, but the promoted orchestration path is `fluid generate schedule --scheduler airflow`.

## Integrations

| Command | What it is for |
| --- | --- |
| [`fluid publish`](./publish.md) | Publish contracts to configured catalogs |
| [`fluid market`](./market.md) | Search and browse discovered products and blueprints |
| [`fluid import`](./import.md) | Scan existing projects and generate FLUID contracts |

## Quality & Governance

| Command | What it is for |
| --- | --- |
| [`fluid policy-check`](./policy-check.md) | Run governance and compliance checks from the contract |
| [`fluid diff`](./diff.md) | Detect drift from desired state |
| [`fluid test`](./test.md) | Validate the contract against live resources |
| [`fluid verify`](./verify.md) | Verify deployed resources still match the contract |

## Utilities

| Command | What it is for |
| --- | --- |
| [`fluid config`](./config.md) | View and set workspace defaults |
| [`fluid split`](./split.md) | Split a flat contract into fragments |
| [`fluid bundle`](./bundle.md) | Resolve a multi-file contract into one bundled document |
| [`fluid auth`](./auth.md) | Manage provider authentication flows |
| [`fluid doctor`](./doctor.md) | Run built-in health checks |
| [`fluid providers`](./providers.md) | List registered providers |
| [`fluid version`](./version.md) | Show CLI version and environment details |

## Command discovery

```bash
fluid --help
fluid <command> -h
```

If a page in the docs uses an older command spelling such as `fluid forge --mode ...`, treat it as historical or compatibility-only unless the page explicitly says it is current.
