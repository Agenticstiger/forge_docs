# `fluid import`

Convert existing tooling into FLUID contracts. Two modes: scan an existing dbt / Terraform / SQL directory, or import a foreign tool project (Meltano, Airbyte, dlt, Singer, dbt).

## Syntax

```bash
fluid import [<engine> <source>] [options]
```

## Mode 1 — directory scan

```bash
fluid import
fluid import --dir ./legacy-dbt
fluid import --provider snowflake
fluid import --yes
```

| Option | Description |
| --- | --- |
| `--provider` | Provider for the generated contracts |
| `--dir`, `-C` | Directory to scan |
| `--yes`, `-y` | Skip the confirmation prompt |

This is the promoted migration path for existing Terraform or SQL projects. A dbt project that has a `target/manifest.json` is routed to the [dbt manifest importer](#importing-a-dbt-project) automatically.

## Mode 2 — foreign tool importer

Convert an existing tool project into FLUID contracts (one per discovered tap / connector / source for the ingestion tools; one per project for dbt):

```bash
fluid import meltano <project-dir>       # Meltano project
fluid import airbyte <workspace-id>      # Airbyte OSS / Cloud workspace
fluid import dlt <pipeline-name>         # dlt pipeline
fluid import singer <tap-config.json>    # Singer tap + target
fluid import dbt <project-dir|manifest>  # dbt project (target/manifest.json)
```

| Option | Description |
| --- | --- |
| `<engine> <source>` | Importer mode + source identifier |
| `--out PATH` | Output contract path (default: one `contract.<id>.fluid.yaml` per discovered source in cwd); with `--split-by` producing multiple products, `--out` is the output **directory** |
| `--split-by {project\|folder\|group}` | dbt import product boundary: one contract per project (default), per top-level `models/` subfolder, or per dbt group — cross-split `ref()`s become cross-product `consumes[]`. *(since `0.13.1`)* |
| `--provider {local\|gcp\|snowflake\|aws\|azure}` | Infrastructure provider for generated contracts. Default `local`. |
| `--yes`, `-y` | Skip the confirmation prompt |

What each importer does:

| Importer | Reads | Emits |
|---|---|---|
| `meltano` | `meltano.yml` + `extract:` block | One `engine: meltano` acquisition contract per tap |
| `airbyte` | Workspace config from REST API | One `engine: airbyte` acquisition contract per source |
| `dlt` | `@dlt.source` modules in the pipeline | One `engine: dlt` acquisition contract per source |
| `singer` | Tap + target config files | One `engine: meltano` acquisition contract (Meltano runs Singer protocol) |
| `dbt` | `target/manifest.json` (+ optional `catalog.json`) | One contract per project by default; `--split-by folder`/`group` splits along product boundaries — see below |

**Secrets are auto-redacted** to `${ENV_VAR}` placeholders so the emitted contracts are safe to commit. Run [`fluid secrets login`](/forge_docs/cli/secrets.html) afterward to populate the keychain backend.

### Example — migrating from Meltano

```bash
fluid import meltano ./my-meltano-project --provider local --yes
fluid validate *.fluid.yaml
fluid apply contract.tap_postgres.fluid.yaml --yes
```

The generated contract preserves Meltano's tap selections and the `state`/`incremental` mode mapping. See [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) for engine-specific properties.

## Importing a dbt project

*(since `0.12.0`)* `fluid import dbt` performs a **faithful brownfield conversion** of a real
dbt project by reading `target/manifest.json` — the artifact `dbt parse` produces without any
warehouse access. The parse is stdlib-only (no dbt-core dependency) and emits **one DataProduct
contract per dbt project** by default — see [`--split-by`](#splitting-one-project-into-multiple-products-split-by-since-0-13-1)
for multi-product splits.

```bash
cd my-dbt-project
dbt parse                                  # refresh target/manifest.json (no warehouse needed)
fluid import dbt . --provider snowflake    # or point at the manifest file directly
fluid validate contract.*.fluid.yaml
```

::: tip Run `dbt parse` first
The importer reads `target/manifest.json`, so make sure it is fresh — a stale manifest imports
the project as it was when last parsed. `dbt parse` needs no warehouse connection. If
`target/catalog.json` exists (from `dbt docs generate`), it is used as an overlay for
warehouse-accurate column types.
:::

What the importer recovers:

| dbt artifact | FLUID contract |
|---|---|
| Models / seeds / snapshots + `depends_on` | One expose each (no model cap); the `ref()`-derived DAG recorded per expose and as `builds[].transformations` |
| Generic tests (`not_null`, `unique`, `accepted_values`, …) | `dq.rules[]` via the same shared test mapping the dbt generators use; `relationships` / range tests become column `validationRules` (FK + bounds) |
| Sources (+ source freshness) | `consumes[]`, freshness mapped to `qosExpectations.freshnessMax` |
| `config.materialized` | Expose kind + build materialization hints; adapter-aware binding (snowflake / bigquery / redshift / databricks / duckdb) |
| Folder layout (`staging` / `intermediate` / `marts`) | `metadata.layer` + `metadata.productType` (staging→Bronze/SDP, marts→Gold/CDP) |
| `catalog.json` / schema.yml `data_type` | Column types (catalog overlay wins; schema.yml is the fallback) |

Primary keys are inferred with the same precedence dbt itself uses
(`ModelNode.infer_primary_key`); foreign keys are recovered from `relationships` tests.

### Splitting one project into multiple products (`--split-by`, since `0.13.1`)

By default (`--split-by project`) the importer emits one contract for the whole project —
byte-stable with earlier releases. Two more boundaries split a monolithic dbt project along
data-product lines:

| Boundary | One DataProduct per… |
|---|---|
| `project` (default) | dbt project — the single-contract output above, unchanged |
| `folder` | top-level `models/` subfolder (models outside any subfolder land in a reported `root` product) |
| `group` | dbt group — the dbt-mesh-native boundary; ungrouped models land in a reported `ungrouped` product, and a fully groupless manifest fails loudly suggesting `folder` mode |

Cross-split `ref()`s are rewritten to cross-product `consumes[]` against the sibling product,
so the inter-product DAG survives the split. With multiple products, `--out` names the output
**directory**:

```bash
fluid import dbt . --split-by folder --out ./products/
```

**Requirements:** manifest schema **v9 or newer** (dbt-core 1.5, May 2023); the primary target
is v12 (dbt 1.8+). Older manifests are rejected with a clear error. dbt >= 1.10 manifests
(with `arguments:`-nested test params) are supported since `0.13.1` alongside the legacy
flat-kwargs shape.

Like all importers, the command prints an **import report** alongside the written contract —
what mapped 1:1, where defaults were used, and what is unsupported and must be re-authored.
After importing, [`fluid generate transformation`](./generate.md) can regenerate a dbt project
from the contract — test mappings are shared, so the round-trip stays symmetric.

## Notes

- Mode 1 (`fluid import` with no engine arg) is the existing migration path for dbt / Terraform / SQL projects.
- Mode 2 (`fluid import <engine> <source>`) is the explicit tool importer — Meltano / Airbyte / dlt / Singer since `0.8.3`, dbt since `0.12.0`.
- Since `0.14.0` the Snowflake round-trip is verified end-to-end: `import dbt` → [`apply`](./apply.md) creates no duplicate lowercase shadow namespace and a second apply is a no-op (`+0 ~2 -0`); [`fluid verify`](./verify.md) reads the deployed objects.
- If you want a clean greenfield start instead, use [`fluid init`](./init.md) or [`fluid forge`](./forge.md).
- For source-aligned ingestion from scratch (no existing tool project), [`fluid init --discover`](./init.md#discover-—-introspect-a-source-into-a-bronze-contract) is the one-shot path.
