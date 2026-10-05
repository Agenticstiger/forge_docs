# CLI Reference

This section tracks the command surface of `forge-cli` `0.18.1`, the release `pip install data-product-forge` installs. `fluid --help` shows the promoted commands.

::: tip Looking up *how to do something* (not *what a command does*)?
The page you actually want is [**CLI by task →**](./tasks/) — narrative walkthroughs organized around things you might be trying to accomplish, like "deploy to a new cloud", "add quality rules", "debug a failed run", or "add agent governance". Each task page links to the relevant commands. **This** page is the command index, grouped by purpose — better for lookup, worse for onboarding.
:::

## Read this first

- CLI release examples in this section use `0.18.1`
- Contract examples use `fluidVersion: 0.7.5`, the stable schema, which `fluid init --quickstart` emits. `0.7.6` is a preview you opt into per contract
- `fluid version` and `fluidVersion` are different things
- The pinned CLI version is recorded in [`docs/.vuepress/cli-version.json`](https://github.com/Agenticstiger/forge_docs/blob/main/docs/.vuepress/cli-version.json) and enforced by the [`cli-consistency`](https://github.com/Agenticstiger/forge_docs/actions/workflows/cli-consistency.yml) workflow.
- Install: `pip install data-product-forge` installs `0.18.1`; TestPyPI is only for release validation and intentional next-release candidates — see [Getting Started](../getting-started/README.md#install-the-cli) for the full install matrix.

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
| [`fluid forge data-model`](../forge-data-model.md) | Forge a reviewable data model from an intent file, DDL, or source catalog |
| [`fluid skills`](./skills.md) | Industry knowledge packs that augment `fluid forge` |
| [Source catalogs](./catalogs/README.md) | Forge directly from Snowflake / Unity / BigQuery / Dataplex / Glue / DataHub / DMM metadata |
| [`fluid validate`](./validate.md) | Check contract syntax and provider rules |
| [`fluid plan`](./plan.md) | Plan execution (`--html`, `--env`, `--out`) |
| [`fluid apply`](./apply.md) | Deploy end-to-end (`--mode`, `--yes`, `--dry-run`) |
| [`fluid status`](./status.md) | One-page summary of the product in the current directory |
| [`fluid ship`](./ship.md) | Run validate, bundle, plan and apply in one command |

The newcomer path is usually:

```bash
fluid init my-project --quickstart
cd my-project
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

## Pipeline Stages

These commands each map to one stage of the 11-stage production pipeline. Most users trigger them via a generated CI pipeline (`fluid generate ci`) rather than running them by hand; each can also be run on its own.

| # | Command | What it does |
| --- | --- | --- |
| 1 | [`fluid bundle`](./bundle.md) | Package contract + sources into a signed tgz bundle (`--sign`, `--attest`, `--format tgz`); [`fluid split`](./split.md) is the inverse for a fragment layout |
| 2 | [`fluid validate`](./validate.md) | Check contract syntax and provider rules (`--strict`, `--report`) |
| 3 | [`fluid generate artifacts`](./generate-artifacts.md) | Fanout: ODCS + ODPS-Bitol + schedule + policy bindings |
| 4 | [`fluid validate-artifacts`](./validate-artifacts.md) | Verify MANIFEST SHA-256 + per-format schema checks |
| 5 | [`fluid diff`](./diff.md) | Detect drift from deployed state (`--exit-on-drift`) |
| 6 | [`fluid plan`](./plan.md) | Plan execution (`--html` mermaid DAG, `--env`, `--out`) |
| 7 | [`fluid apply`](./apply.md) | Deploy (`--mode`, `--allow-data-loss`, `--yes`) |
| 8 | [`fluid policy-apply`](./policy-apply.md) | Hand compiled IAM bindings to the provider (`--mode check\|enforce`). In 0.18.1 GCP reports them and the other providers have no applier; `fluid apply` provisions access resources |
| 9 | [`fluid verify`](./verify.md) | Confirm deployed state matches the contract (`--strict`) |
| 10 | [`fluid publish`](./publish.md) | Publish to enterprise data catalogs (`--target` repeatable) |
| 11 | [`fluid schedule-sync`](./schedule-sync.md) | Push DAGs to airflow / composer / mwaa / astronomer / prefect / dagster |

## Safety & Supply Chain

These commands are for production-safety concerns that live alongside the pipeline rather than inside it.

| Command | What it is for |
| --- | --- |
| [`fluid rollback`](./rollback.md) | Restore from a snapshot recorded in `.fluid/rollback-state.json` (use `--list` for read-only discovery). Not every apply records one; see [the availability note](./rollback.md) |
| [`fluid verify-signature`](./verify-signature.md) | Verify a Sigstore cosign signature + SLSA attestation on a tgz bundle |

## Generate & Visualize

| Command | What it is for |
| --- | --- |
| [`fluid generate`](./generate.md) | Unified generation entry point (transformations, schedules, CI, standards, artifacts) |
| [`fluid generate artifacts`](./generate-artifacts.md) | Stage 3 fanout — ODCS + ODPS-Bitol + schedule + policy bindings |
| [`fluid generate-pipeline`](./generate-pipeline.md) | Universal pipeline scaffolds (legacy alias) |
| [`fluid generate-airflow`](./generate-airflow.md) | Compatibility shim for `generate schedule --scheduler airflow` |
| [`fluid generate iac`](./generate-iac.md) | Review-only emit of an OpenTofu module from a contract |
| [`fluid generate vector`](./generate-vector.md) | Review-only emit of a pgvector RAG target from a contract |
| [`fluid viz-graph`](./viz-graph.md) | Render the contract as a lineage graph (SVG/HTML/PNG/DOT; DOT only when Graphviz is missing) |

The promoted orchestration path is `fluid generate schedule --scheduler airflow`.

## Standards & Interop

| Command | What it is for |
| --- | --- |
| [`fluid exporters`](./exporters.md) | List the spec-export formats (ODCS / ODPS / ODPS-Bitol) a contract can be serialized to |
| [`fluid odps`](./odps.md) | Export, import, validate and inspect Open Data Product Standard documents: Bitol v1.0.0 by default, LF/ODPI v4.1 with `--spec odps-4.1` |
| [`fluid odps-bitol`](./odps-bitol.md) | Bitol-only ODPS export, validation and info (Entropy Data marketplace) |
| [`fluid odcs`](./odcs.md) | Bidirectional FLUID ↔ Open Data Contract Standard (ODCS v3.1.0) |
| [`fluid export`](./export.md) | Export to executable orchestration code (Airflow, Dagster, Prefect) |
| [`fluid export-opds`](./export-odps.md) | Deprecated one-shot export to LF/ODPI ODPS v4.1 (the page is named `export-odps`; the command is spelled `export-opds`) |

ODPS and ODCS are **spec exporters**, not cloud providers — they serialize a contract to an open standard and do not deploy infrastructure. List them with [`fluid exporters`](./exporters.md); for deployment targets see [`fluid providers`](./providers.md).

## Integrations

| Command | What it is for |
| --- | --- |
| [`fluid publish`](./publish.md) | Publish to enterprise data catalogs (`--target` repeatable) |
| [`fluid datamesh-manager`](./datamesh-manager.md) | Publish products, contracts, and Access lineage to Entropy Data / Data Mesh Manager |
| [`fluid market`](./market.md) | Search and browse discovered products and blueprints |
| [`fluid import`](./import.md) | Scan existing projects and generate FLUID contracts |

## Quality & Governance

`0.8.0` introduced the unified `fluid policy {check,compile,apply}` subcommand group. The hyphenated commands (`policy-check`, `policy-compile`, `policy-apply`) are still registered in 0.18.1.

| Command | What it is for |
| --- | --- |
| [`fluid policy`](./policy.md) | The umbrella for the three verbs below |
| [`fluid policy check`](./policy-check.md) | Static lint of the contract's policy declarations (same surface as `fluid policy-check`) |
| [`fluid policy compile`](./policy-compile.md) | Compile `accessPolicy` → provider IAM bindings (`runtime/policy/bindings.json`) |
| [`fluid policy apply`](./policy-apply.md) | Hand compiled IAM bindings to the provider (stage 8); GCP reports them, other providers print that they have no applier |
| [`fluid contract-tests`](./contract-tests.md) | Compare each expose's schema with a saved baseline (`--write-baseline` creates it). Without `--baseline` it skips and exits 0 |
| [`fluid contract-validation`](./contract-validation.md) | Inspect deployed resources against the contract |
| [`fluid diff`](./diff.md) | Detect drift from deployed state |
| [`fluid test`](./test.md) | Check the contract against live resources and run its `dq.rules` |
| [`fluid verify`](./verify.md) | Verify deployed resources still match the contract |
| [`fluid mission`](./mission.md) | Declarative goals with deterministic success criteria; `mission check` is a zero-LLM CI gate |
| [`fluid contract`](./contract.md) | Inspect and mutate contracts: `apply-suggestion`, `digest`, `migrate-product-type` |

## Project & Workspace

| Command | What it is for |
| --- | --- |
| [`fluid product-new`](./product-new.md) | Scaffold a new data product |
| [`fluid product-add`](./product-add.md) | Add a product to an existing workspace |
| [`fluid workspace`](./workspace.md) | Team collaboration store in `./.fluid-workspace/` (members, versions, change requests); also documents `fluid.workspace.yaml` |
| [`fluid ide`](./ide.md) | IDE integration helpers |
| [`fluid ai`](./ai.md) | AI provider configuration |
| [`fluid memory`](./memory.md) | Inspect and manage forge memory namespaces |
| [`fluid mcp`](./mcp.md) | `serve` offers forge authoring tools to MCP clients; `output-port serve` gives agents governed read access to one expose |
| [`fluid agents`](./agents.md) | List, show and prune the `.fluid/agents/` records that `fluid forge` runs write |
| [`fluid runs`](./runs.md) | Inspect run history: `status`, `logs`, `diff` |
| [`fluid retention`](./retention.md) | Sweep run records, logs and DLQ entries past their retention horizons |
| [`fluid secrets`](./secrets.md) | Manage secrets for acquisition pipelines |
| [`fluid stats`](./stats.md) | Aggregate cost and token usage across forge runs |

## CI & Scaffolding

| Command | What it is for |
| --- | --- |
| [`fluid generate ci`](./generate.md) | Generate parameterised 11-stage CI pipelines, including Jenkins publish/verify defaults |
| [`fluid scaffold-ci`](./scaffold-ci.md) | Legacy CI/CD scaffolds (superseded by `generate ci` for 11-stage) |
| [`fluid scaffold-composer`](./scaffold-composer.md) | Generate Cloud Composer scaffolds |
| [`fluid scaffold-ide`](./scaffold-ide.md) | Generate agentic-IDE configuration for Kiro, Cursor, Claude Code, Cline or a generic `AGENTS.md` |
| [`fluid docs`](./docs.md) | Build / index in-product documentation |

## Utilities

| Command | What it is for |
| --- | --- |
| [`fluid config`](./config.md) | Read and write `provider`, `project` and `region` in `.fluid/context.json` |
| [`fluid split`](./split.md) | Split a flat contract into fragment files joined by `$ref`; [`fluid bundle`](./bundle.md) is the inverse. See [Composing a contract with `$ref`](../concepts/contract-refs.md) |
| [`fluid describe`](./describe.md) | Machine-readable description of the local install: CLI and schema versions, providers, engines, templates |
| [`fluid auth`](./auth.md) | Manage provider authentication flows |
| [`fluid doctor`](./doctor.md) | Run built-in health checks |
| [`fluid providers`](./providers.md) | List registered infrastructure providers; explains the `ERR_PROVIDER_*` errors |
| [`fluid plugins`](./plugins.md) | List installed plugins per role with allow/block governance status |
| [`fluid provider-init`](./provider-init.md) | Scaffold a new provider package with an entry point and a conformance test |
| [`fluid roadmap`](./roadmap.md) | Print the engineering roadmap bundled with the CLI |
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
