# CLI Reference

This section tracks the promoted command surface shown by `fluid --help` in `forge-cli` `0.7.11`.

## Read this first

- CLI release examples in this section use `0.7.11`
- Contract examples use `fluidVersion: 0.7.2`
- `fluid version` and `fluidVersion` are different things
- The pinned CLI version is recorded in [`docs/.vuepress/cli-version.json`](../.vuepress/cli-version.json) and enforced by the [`cli-consistency`](https://github.com/Agenticstiger/forge_docs/actions/workflows/cli-consistency.yml) workflow.

## Core Workflow

| Command | What it is for |
| --- | --- |
| [`fluid init`](./init.md) | Create a new project |
| [`fluid demo`](./demo.md) | Zero-setup, ~30 second customer-360 example on local DuckDB |
| [`fluid forge`](./forge.md) | AI-assisted scaffolding |
| [`fluid skills`](./skills.md) | Industry knowledge packs that augment `fluid forge` |
| [`fluid validate`](./validate.md) | Validate a contract against bundled or fetched FLUID schemas |
| [`fluid plan`](./plan.md) | Preview planned execution |
| [`fluid apply`](./apply.md) | Run a contract or saved plan end-to-end |
| [`fluid status`](./status.md) | One-page summary of the product in the current directory |

The newcomer path is usually:

```bash
fluid init my-project --quickstart
cd my-project
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

## Generate & Visualize

| Command | What it is for |
| --- | --- |
| [`fluid generate`](./generate.md) | Unified generation entry point (transformations, schedules, CI, standards) |
| [`fluid generate-pipeline`](./generate-pipeline.md) | Universal pipeline scaffolds (legacy alias) |
| [`fluid generate-airflow`](./generate-airflow.md) | Compatibility shim for `generate schedule --scheduler airflow` |
| [`fluid viz-graph`](./viz-graph.md) | Render the contract as an interactive lineage graph (SVG/HTML/PNG/DOT) |

The promoted orchestration path is `fluid generate schedule --scheduler airflow`.

## Standards & Interop

| Command | What it is for |
| --- | --- |
| [`fluid odps`](./odps.md) | Export, validate, and inspect the official ODPS (Linux Foundation) format |
| [`fluid odps-bitol`](./odps-bitol.md) | Bitol.io's ODPS variant (Entropy Data marketplace) |
| [`fluid odcs`](./odcs.md) | Bidirectional FLUID <-> Open Data Contract Standard (ODCS v3.1.0) |
| [`fluid export`](./export.md) | Export to executable orchestration code (Airflow, Dagster, Prefect) |
| [`fluid export-opds`](./export-opds.md) | One-shot ODPS file export shortcut |

## Integrations

| Command | What it is for |
| --- | --- |
| [`fluid publish`](./publish.md) | Publish contracts to configured catalogs |
| [`fluid datamesh-manager`](./datamesh-manager.md) | Publish products and contracts to Entropy Data / Data Mesh Manager |
| [`fluid market`](./market.md) | Search and browse discovered products and blueprints |
| [`fluid import`](./import.md) | Scan existing projects and generate FLUID contracts |

## Quality & Governance

| Command | What it is for |
| --- | --- |
| [`fluid policy-check`](./policy-check.md) | Run governance and compliance checks from the contract |
| [`fluid policy-compile`](./policy-compile.md) | Compile policy bundles |
| [`fluid policy-apply`](./policy-apply.md) | Apply compiled policies |
| [`fluid contract-tests`](./contract-tests.md) | Run contract-level test scenarios |
| [`fluid contract-validation`](./contract-validation.md) | Validate contract structure and references |
| [`fluid diff`](./diff.md) | Detect drift from desired state |
| [`fluid test`](./test.md) | Validate the contract against live resources |
| [`fluid verify`](./verify.md) | Verify deployed resources still match the contract |

## Project & Workspace

| Command | What it is for |
| --- | --- |
| [`fluid product-new`](./product-new.md) | Scaffold a new data product |
| [`fluid product-add`](./product-add.md) | Add a product to an existing workspace |
| [`fluid workspace`](./workspace.md) | Manage multi-product workspaces |
| [`fluid ide`](./ide.md) | IDE integration helpers |
| [`fluid ai`](./ai.md) | AI provider configuration |

## CI & Scaffolding

| Command | What it is for |
| --- | --- |
| [`fluid scaffold-ci`](./scaffold-ci.md) | Generate CI/CD scaffolds |
| [`fluid scaffold-composer`](./scaffold-composer.md) | Generate Cloud Composer scaffolds |
| [`fluid docs`](./docs.md) | Build / index in-product documentation |

## Utilities

| Command | What it is for |
| --- | --- |
| [`fluid config`](./config.md) | View and set workspace defaults |
| [`fluid split`](./split.md) | Split a flat contract into fragments |
| [`fluid bundle`](./bundle.md) | Resolve a multi-file contract into one bundled document |
| [`fluid auth`](./auth.md) | Manage provider authentication flows |
| [`fluid doctor`](./doctor.md) | Run built-in health checks |
| [`fluid providers`](./providers.md) | List registered providers |
| [`fluid provider-init`](./provider-init.md) | Initialize provider-specific configuration |
| [`fluid version`](./version.md) | Show CLI version and environment details |

## Command discovery

```bash
fluid --help
fluid <command> -h
```

If a page in the docs uses an older command spelling such as `fluid forge --mode ...`, treat it as historical or compatibility-only unless the page explicitly says it is current.

---

> Need a hand with a specific command, or noticing something out of date? [Start a discussion](https://github.com/Agenticstiger/forge-cli/discussions) or [open an issue](https://github.com/Agenticstiger/forge-cli/issues) - docs PRs welcome.
