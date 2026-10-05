# `fluid init`

Create a new project: a working example, an empty skeleton, a bundled blueprint, or Bronze contracts discovered from an existing source.

## Syntax

```bash
fluid init [NAME] [OPTIONS]
```

With no mode flag, `fluid init NAME` starts the AI-assisted path (the same copilot as [`fluid forge`](./forge.md)). Every example below picks a mode explicitly, so none of them needs an AI key.

## Examples

```bash
# A working example with sample data
fluid init my-project --quickstart

# An empty skeleton
fluid init my-project --blank

# A bundled blueprint, with no network and no AI key
fluid init orders --blueprint fluid.starter --domain sales --owner-team growth --owner-email growth@example.com

# A provider starter: a Bronze product bound to a BigQuery or Snowflake table
fluid init my-project --quickstart --provider gcp
fluid init my-project --quickstart --provider snowflake

# A named template, and the templates `--list-templates` shows
fluid init my-project --template first-dag
fluid init --list-templates

# Bronze contracts from an existing source (see below)
fluid init shop --discover file:///data/csvs
```

After `--quickstart` the CLI prints (trimmed):

```text
Created fluid.workspace.yaml — workspace my-project
...
✅ Created project from customer-360 template

╭─────────────────────────────── ✅ Next steps ────────────────────────────────╮
│    fluid status                                see what you have             │
│    fluid validate                              check the contract            │
│    fluid plan --env dev                        preview a run                 │
│    fluid forge --ci github_actions             add CI                        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

The next-steps panel stops at `plan`. To run a scaffold, `cd` into it and `fluid apply contract.fluid.yaml`; what a local apply writes depends on the contract (see [Run what you scaffolded](#run-what-you-scaffolded)).

## What `fluid init` writes

`fluid init my-project --quickstart` writes into two directories. The directory you run it from becomes the workspace root, and `my-project/` is the product.

```text
.                                  # workspace root: the directory you ran init in
├── fluid.workspace.yaml           # kind: WorkspaceConfig
├── .gitignore                     # a managed block; see below
├── .fluid/
│   ├── init-receipt.json          # what init produced; ignored by the generated .gitignore
│   └── team-memory.yaml           # team conventions the copilot reads
└── my-project/
    ├── contract.fluid.yaml
    ├── README.md
    ├── data/                      # sample CSVs (customers, orders, interactions)
    └── .fluid/
        └── forge-receipt.json     # provenance record; ignored by the generated .gitignore
```

Commit `fluid.workspace.yaml`, `.gitignore`, `.fluid/team-memory.yaml` and everything in `my-project/` except the receipt. The generated `.gitignore` block excludes `.fluid/init-receipt.json`, `.fluid/forge-receipt.json`, `.fluid/copilot-memory.json`, `.fluid/logs/` and `runtime/`.

`--blank`, `--blueprint` and the provider starters write the same workspace files, and a product directory that holds `contract.fluid.yaml` and `.fluid/forge-receipt.json` only. Directory templates add their `README.md` and sample data.

## Options

| Option | Description |
| --- | --- |
| `NAME` | Project name. Default: auto-generated. |
| `--quickstart` | The recommended first project. With the default provider it scaffolds the `customer-360` template. With `--provider gcp` or `--provider snowflake` it scaffolds a provider starter from a bundled blueprint. |
| `--blank` | An empty project skeleton. |
| `--template NAME` | Create from a named template. See [Templates](#templates). |
| `--blueprint ID` | Create from a bundled marketplace blueprint: `fluid.starter`, `fluid.analytics-daily`, `fluid.starter-gcp` or `fluid.starter-snowflake`. See [Blueprints](../advanced/blueprints.md). |
| `--list-templates` | Show the code templates and exit. See [Templates](#templates) for why this list is shorter than what `--template` accepts. |
| `--discover URI` | Introspect a source and emit one Bronze acquisition contract per discovered stream. See [`--discover`](#discover-—-introspect-a-source-into-a-bronze-contract). |
| `--provider` | Infrastructure provider. Default: `local` (DuckDB, no cloud). With `--quickstart`, `gcp` or `snowflake` selects a provider starter. |
| `--domain`, `--owner-team`, `--owner-email` | Values written into the contract by `--blueprint` and `--discover`. |
| `--data-product-type` | `SDP`, `ADP` or `CDP` (or `Bronze`, `Silver`, `Gold`) for the first product. Carried into the init-to-forge handoff of the AI-assisted path. `--blank` writes Bronze/SDP regardless. |
| `--workspace-lock SDP\|ADP\|CDP` | Lock the workspace to one product type. Recorded as `workspace.data_product_type_lock` in `fluid.workspace.yaml`; later `fluid forge` runs default to it and reject a conflicting `--data-product-type`. |
| `--show-work` | Stream the agent's reasoning and tool calls during the init-to-forge handoff. Also saved under `.fluid/agents/<run-id>/`. |
| `--agent NAME` | Scaffold a custom domain agent spec in `.fluid/agents/`. See [Custom domain agents](./agents.md#custom-domain-agents). |
| `--yes`, `-y` | Skip confirmation prompts. |
| `--dry-run` | Preview what would be created. See the [known issues](#known-issues-as-of-0-18-1). |
| `--dir`, `-C` | Directory to initialize, or, with `--discover`, where the contracts are written. |
| `--quiet`, `-q` | Suppress the next-steps panel. |

## Which `fluidVersion` each path writes

Each contract declares its own `fluidVersion`, and `fluid validate` checks it against that version's schema, so an older version keeps validating. 0.7.5 is the latest stable version; 0.7.6 is a preview you opt into by hand.

| Path | `fluidVersion` |
| --- | --- |
| `--quickstart`, `--template` with a directory template, `--blank` | `0.7.5` |
| `--quickstart --provider gcp\|snowflake`, `--blueprint` (`fluid.starter`, `fluid.analytics-daily`) | `0.7.4` |
| `--template` with a code template (`analytics`, `etl_pipeline`, `ml_pipeline`, `starter`, `streaming`), `--discover` | `0.7.3` |

A blueprint writes the version its own file declares. The GCP starter's placeholder project and missing region are described on the [GCP provider](../providers/gcp.md) page. [`fluid product-new`](./product-new.md) and [`fluid import`](./import.md) also write `0.7.3`. To move a `0.7.3` or `0.7.4` contract to `0.7.5`, change the `fluidVersion` line and run [`fluid validate`](./validate.md). The fields each version adds are listed in the [contract concept page](../concepts/contract.md).

## Templates

`--template` accepts two families of names. Both write a project; they differ in how they are stored, which is why `--list-templates` shows only one of them.

**Directory templates** are folders of contract, README and sample data. They write `fluidVersion: 0.7.5`. `--list-templates` does not show them.

| Template | What it demonstrates |
| --- | --- |
| `hello-world` | A minimal Hello World contract. |
| `csv-basics` | Transforming a raw customer CSV into a validated product. |
| `multi-source` | Joining customers and orders into revenue metrics. |
| `external-sql-files` | Keeping SQL in separate files. |
| `data-quality-validation` | Quality checks on a product catalog. |
| `testing-your-contract` | An orders contract with quality tests. |
| `contract-documentation` | A contract with inline documentation. |
| `environment-configuration` | An environment-aware pipeline. |
| `incremental-processing` | Watermark-based incremental updates. |
| `multiple-outputs` | Bronze, Silver and Gold outputs from one contract. |
| `pipeline-orchestration` | Parallel stages and dependencies. |
| `first-dag` | A sales analytics pipeline with a generated Airflow DAG. |
| `customer-360` | RFM analysis, lifetime value and churn. This is the `--quickstart` template. |

**Code templates** are what `fluid init --list-templates` prints, and what [`fluid forge --template`](./forge.md) uses. They write `fluidVersion: 0.7.3`.

| Template | Description |
| --- | --- |
| `analytics` | Business intelligence and reporting products with SQL transforms. |
| `etl_pipeline` | Extract, transform, load workflows with error handling. |
| `ml_pipeline` | Machine learning workflows with feature engineering. |
| `starter` | A minimal template for a quick setup. |
| `streaming` | Real-time processing with an event-driven design. |

An unknown name fails and lists the names the code templates know. The `--template ml-features` example in `fluid init --help` is such a name: as of 0.18.1 it fails with `Available templates: ...`.

## Run what you scaffolded

Scaffolds differ in what `fluid apply` produces locally. These were measured on 0.18.1:

- `fluid.starter` (`--blueprint`): one embedded-SQL build with a local CSV output. `fluid apply contract.fluid.yaml --yes` writes `runtime/out/orders.csv` with a row of data.
- `customer-360` (`--quickstart`): `fluid validate` passes. `fluid apply` exits 0 but writes 24-byte placeholder files to `output/`, with `Build customer_360_pipeline has no SQL, skipping` in its log. The contract's SQL is declared per stage under `builds[].properties.stages[]`, and the local provider does not run it. Use the contract to explore `validate`, `plan` and `verify`, and use `fluid.starter` or `csv-basics` when you want a local file with data in it.

## `--discover` — introspect a source into a Bronze contract

Instead of writing the acquisition block by hand, point `fluid init` at a source URI. It emits one Bronze (SDP) contract per discovered stream:

```bash
fluid init shop --discover file:///data/csvs --dir found
```

```text
🔍 Discovering streams at file:///data/csvs…
  ✓ contract.orders.fluid.yaml  (2 cols)
  ✓ contract.payments.fluid.yaml  (2 cols)

✓ Emitted 2 contract(s). Next: `fluid validate <file>`.
```

```text
found/
├── contract.orders.fluid.yaml
└── contract.payments.fluid.yaml
```

What it does:

- Writes the contracts to the current directory, or to `--dir`. It does not create a `NAME/` directory.
- Names each file `contract.<stream>.fluid.yaml` and each product `bronze.<NAME>.<stream>` (`bronze.shop.orders` above). Without `NAME`, the name is derived from the URI path, which gives long ids for deep paths.
- Sets `metadata.layer: Bronze` and `metadata.productType: SDP` (both vocabularies; see [Product Types](/forge_docs/data-products/product-type.html)).
- Picks `engine: duckdb` for embedded ingestion, with no Airbyte cluster.
- Writes `fluidVersion: 0.7.3`. The file validates; bump it by hand if you need a later version's fields.
- Takes `--domain`, `--owner-team` and `--owner-email` for the contract's `domain` and `metadata.owner`. Without them it writes `data`, `data-platform` and `data-platform@example.com`, which you should replace.

The CLI registers discoverers for the file schemes `file`, `http`, `https`, `s3`, `gs` and `gcs`, and for the database schemes `postgres`, `postgresql`, `mysql` and `mariadb`. Any other scheme fails with `unsupported source scheme`. A discovered source is read again by the build that `apply` runs, and that build runs inside the [DuckDB sandbox](../advanced/duckdb-sandbox.md), which does not read `http(s)://` or `gs://` URLs from contract SQL. This page did not run an apply against a discovered `https://`, `gs://` or `gcs://` source.

::: danger A credential in the URI is written into the contract
For `postgres://` and `mysql://` URIs, the password in the URI is copied verbatim into `builds[].properties.source.connection.password`. Nothing is redacted, so the emitted file is not safe to commit. The command also prints the URI, password included, on its first line. A URI typed on the command line also lands in your shell history, and in the process list (`ps`) while the command runs. To keep the password out of both, leave it out of the URI. This page did not test discovery against a live server, so check that your setup authenticates without it.

Before you commit, delete the `password:` line and name the secret with a `secretRef`, the form [`fluid secrets`](./secrets.md#how-contracts-consume-secrets) documents for credentials:

```yaml
connection:
  host: db.example.com
  user: ingest
  secretRef: env://PGPASSWORD
```

The build resolves the `secretRef` when it runs. Delete the `password:` line first, because when both are present the literal `password` wins and the `secretRef` is ignored. A `{{ env.PGPASSWORD }}` placeholder is also resolved when the build runs, but `fluid apply` and `fluid publish` leave a placeholder whose name looks like a credential unresolved, so use `secretRef` for passwords. A literal `${VAR}` stays a literal string. Importers behave differently: [`fluid import`](./import.md) redacts secrets for the tools that carry them.
:::

### Run a discovered contract

A default `fluid apply` does not run the acquisition build. It writes a 24-byte placeholder to `out/<stream>.parquet`. Data lands with `--mode amend-and-build`:

```bash
fluid apply contract.orders.fluid.yaml --mode amend-and-build --yes
```

In a directory holding one CSV (`orders.csv` with `id,name` and two rows), the run wrote `out/orders.parquet` with those two rows. Two limits apply on 0.18.1:

- **The source must sit inside the contract's directory tree.** Contract SQL is limited to the contract directory, its workspace, `./runtime` and the locations the contract declares inside those. Discovering `file:///data/csvs` into `--dir found` and applying from `found/` failed with `file system operations are disabled by configuration`, because `csvs/` is outside `found/`. Run `fluid init --discover` from the directory that holds the data, or see the [DuckDB sandbox](../advanced/duckdb-sandbox.md) for how to widen the roots.
- **The build reads the whole directory.** Each emitted contract points `source.connection.uri` at the directory, so a directory whose CSVs have different columns fails the build with `Schema mismatch between globbed files`. Discover from a directory of files that share one schema, or edit `source.connection.uri` to a single file.

See [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) for the full framework, or [the Postgres → DuckDB walkthrough](/forge_docs/walkthrough/source-aligned-postgres-duckdb.html) for an end-to-end example.

## Known issues (as of 0.18.1)

- `--dry-run` prevents writes with `--blank` and with `fluid demo`, but `--quickstart`, `--template` and `--blueprint` still write the workspace files and the project.
- `fluid init --discover sqlite://...` fails with `unsupported source scheme`, although the error message lists `sqlite` as supported.
- `fluid init --discover postgres://...` against an unreachable host (`127.0.0.1:1`) failed with `Unknown secret storage found: 'local_file'` instead of a connection error. No live Postgres or MySQL server was available for this page, so those two schemes are untested end to end on 0.18.1; the `file://` example above is the measured one.
- `--provider azure` is rejected with `Unknown provider 'azure'`. The providers registered in the test install were `aws`, `datamesh_manager`, `gcp`, `local`, `redshift` and `snowflake`.
- Any `--provider gcp` run logs `Provider 'gcp' requires --project to be specified` unless the global `--project` is set. The scaffold is still written.
- `fluid init --agent NAME` fails with a missing `custom.yaml.template` in the 0.18.1 wheel. The workaround is in [Custom domain agents](./agents.md#custom-domain-agents).

## Notes

- The promoted newcomer path is `fluid init ... --quickstart`, then `validate`, `plan` and `apply`.
- For AI-assisted scaffolding, use [`fluid forge`](./forge.md).
- To see a local project without creating your own first, use [`fluid demo`](./demo.md).
