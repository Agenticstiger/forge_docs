# CLI Reference

This section tracks the promoted command surface shown by `fluid --help` in `forge-cli` `0.8.0`.

## Read this first

- CLI release examples in this section use `0.8.0`
- Contract examples use `fluidVersion: 0.7.2`
- `fluid version` and `fluidVersion` are different things
- The pinned CLI version is recorded in [`docs/.vuepress/cli-version.json`](../.vuepress/cli-version.json) and enforced by the [`cli-consistency`](https://github.com/Agenticstiger/forge_docs/actions/workflows/cli-consistency.yml) workflow.
- Install: `pip install data-product-forge`. Pre-release candidates live on TestPyPI — see [Getting Started](../getting-started/README.md#install-the-cli) for the full install matrix.

## The 11-stage pipeline

`0.8.0` promotes an eleven-stage production pipeline — each stage is a CI gate that exits non-zero on failure. Each command below maps to exactly one stage:

```
1. bundle → 2. validate → 3. generate-artifacts → 4. validate-artifacts
      → 5. diff (drift gate) → 6. plan → 7. apply → 8. policy-apply
      → 9. verify → 10. publish → 11. schedule-sync (Path A only)
```

See [Walkthrough → 11-stage pipeline](../walkthrough/11-stage-pipeline.md) for the full end-to-end flow.

## Core Workflow

| Command | What it is for |
| --- | --- |
| [`fluid init`](./init.md) | Create a new project |
| [`fluid demo`](./demo.md) | Zero-setup ~30 second customer-360 example on local DuckDB |
| [`fluid forge`](./forge.md) | AI-assisted scaffolding |
| [`fluid skills`](./skills.md) | Industry knowledge packs that augment `fluid forge` |
| [`fluid validate`](./validate.md) | Check contract syntax and provider rules |
| [`fluid plan`](./plan.md) | Plan execution (`--html`, `--env`, `--out`) |
| [`fluid apply`](./apply.md) | Deploy end-to-end (`--mode`, `--yes`, `--dry-run`) |
| [`fluid status`](./status.md) | One-page summary of the product in the current directory |

The newcomer path is usually:

```bash
fluid init my-project --quickstart
cd my-project
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

## Pipeline Stages

These commands each map to one stage of the 11-stage production pipeline. Most users trigger them via a generated CI pipeline (`fluid generate ci`) rather than running them by hand, but every stage is usable standalone.

| # | Command | What it does |
| --- | --- | --- |
| 1 | [`fluid bundle`](./bundle.md) | Package contract + sources into a signed tgz bundle (`--sign`, `--attest`, `--format tgz`) |
| 2 | [`fluid validate`](./validate.md) | Check contract syntax and provider rules (`--strict`, `--report`) |
| 3 | [`fluid generate artifacts`](./generate-artifacts.md) | Fanout: ODCS + ODPS-Bitol + schedule + policy bindings |
| 4 | [`fluid validate-artifacts`](./validate-artifacts.md) | Verify MANIFEST SHA-256 + per-format schema checks |
| 5 | [`fluid diff`](./diff.md) | Detect drift from deployed state (`--exit-on-drift`) |
| 6 | [`fluid plan`](./plan.md) | Plan execution (`--html` mermaid DAG, `--env`, `--out`) |
| 7 | [`fluid apply`](./apply.md) | Deploy (`--mode`, `--allow-data-loss`, `--yes`) |
| 8 | [`fluid policy-apply`](./policy-apply.md) | Enforce IAM/GRANT bindings (`--mode check|enforce`) |
| 9 | [`fluid verify`](./verify.md) | Confirm deployed state matches the contract (`--strict`) |
| 10 | [`fluid publish`](./publish.md) | Publish to enterprise data catalogs (`--target` repeatable) |
| 11 | [`fluid schedule-sync`](./schedule-sync.md) | Push DAGs to airflow / composer / mwaa / astronomer / prefect / dagster |

## Safety & Supply Chain

These commands are for production-safety concerns that live alongside the pipeline rather than inside it.

| Command | What it is for |
| --- | --- |
| [`fluid rollback`](./rollback.md) | Restore from the auto-snapshot taken before `apply --mode replace` (use `--list` for read-only discovery) |
| [`fluid verify-signature`](./verify-signature.md) | Verify a Sigstore cosign signature + SLSA attestation on a tgz bundle |

## Generate & Visualize

| Command | What it is for |
| --- | --- |
| [`fluid generate`](./generate.md) | Unified generation entry point (transformations, schedules, CI, standards, artifacts) |
| [`fluid generate artifacts`](./generate-artifacts.md) | Stage 3 fanout — ODCS + ODPS-Bitol + schedule + policy bindings |
| [`fluid generate-pipeline`](./generate-pipeline.md) | Universal pipeline scaffolds (legacy alias) |
| [`fluid generate-airflow`](./generate-airflow.md) | Compatibility shim for `generate schedule --scheduler airflow` |
| [`fluid viz-graph`](./viz-graph.md) | Render the contract as an interactive lineage graph (SVG/HTML/PNG/DOT) |

The promoted orchestration path is `fluid generate schedule --scheduler airflow`.

## Standards & Interop

| Command | What it is for |
| --- | --- |
| [`fluid odps`](./odps.md) | Export, validate, and inspect the official ODPS (Linux Foundation) format |
| [`fluid odps-bitol`](./odps-bitol.md) | Bitol.io's ODPS variant (Entropy Data marketplace) |
| [`fluid odcs`](./odcs.md) | Bidirectional FLUID ↔ Open Data Contract Standard (ODCS v3.1.0) |
| [`fluid export`](./export.md) | Export to executable orchestration code (Airflow, Dagster, Prefect) |
| [`fluid export-opds`](./export-opds.md) | One-shot ODPS file export shortcut |

## Integrations

| Command | What it is for |
| --- | --- |
| [`fluid publish`](./publish.md) | Publish to enterprise data catalogs (`--target` repeatable) |
| [`fluid datamesh-manager`](./datamesh-manager.md) | Publish products, contracts, and Access lineage to Entropy Data / Data Mesh Manager |
| [`fluid market`](./market.md) | Search and browse discovered products and blueprints |
| [`fluid import`](./import.md) | Scan existing projects and generate FLUID contracts |

## Quality & Governance

`0.8.0` introduces a unified `fluid policy {check,compile,apply}` subcommand group; the existing hyphenated commands stay registered as one-release compatibility aliases.

| Command | What it is for |
| --- | --- |
| [`fluid policy check`](./policy-check.md) | Static lint of the contract's policy declarations (same surface as `fluid policy-check`) |
| [`fluid policy compile`](./policy-compile.md) | Compile `accessPolicy` → provider IAM bindings (`runtime/policy/bindings.json`) |
| [`fluid policy apply`](./policy-apply.md) | Deploy compiled IAM bindings to the target warehouse (stage 8) |
| [`fluid contract-tests`](./contract-tests.md) | Run contract-level test scenarios |
| [`fluid contract-validation`](./contract-validation.md) | Validate contract structure and references |
| [`fluid diff`](./diff.md) | Detect drift from deployed state |
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
| [`fluid generate ci`](./generate.md) | Generate parameterised 11-stage CI pipelines, including Jenkins publish/verify defaults |
| [`fluid scaffold-ci`](./scaffold-ci.md) | Legacy CI/CD scaffolds (superseded by `generate ci` for 11-stage) |
| [`fluid scaffold-composer`](./scaffold-composer.md) | Generate Cloud Composer scaffolds |
| [`fluid docs`](./docs.md) | Build / index in-product documentation |

## Utilities

| Command | What it is for |
| --- | --- |
| [`fluid config`](./config.md) | View and set workspace defaults |
| [`fluid split`](./split.md) | Split a flat contract into fragments |
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

If a page in the docs uses an older command spelling such as `fluid compile ...` or `fluid publish --catalog ...`, treat it as historical:

- `fluid compile` → use `fluid bundle --format yaml` (renamed in `0.7.3`; bundle is now also the tgz+sign+attest command)
- `fluid publish --catalog X,Y` → use `fluid publish --target X --target Y` (renamed + made repeatable in `0.7.3`)
- `fluid policy-check` / `policy-compile` / `policy-apply` → still work; new idiomatic form is `fluid policy {check,compile,apply}`

---

> Need a hand with a specific command, or noticing something out of date? [Start a discussion](https://github.com/Agenticstiger/forge-cli/discussions) or [open an issue](https://github.com/Agenticstiger/forge-cli/issues) — docs PRs welcome.
