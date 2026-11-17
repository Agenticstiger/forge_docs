# `fluid import`

Convert existing tooling into FLUID contracts. Two modes: scan an existing dbt / Terraform / SQL directory, or import a foreign tool project (Meltano, Airbyte, dlt, Singer, dbt). *On forge-cli `main`, not yet in a release ([forge-cli #939](https://github.com/Agenticstiger/forge-cli/pull/939)).* A schema registry subject can seed a contract too.

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
| `--provider` | Provider for the generated contracts. The value must be a registered provider; `azure` is rejected as `Unknown provider 'azure'` in 0.18.1. `gcp` logs `Provider 'gcp' requires --project to be specified` unless the global `--project` or `FLUID_PROJECT` is set. |
| `--dir`, `-C` | Directory to scan |
| `--yes`, `-y` | Skip the confirmation prompt |

This is the promoted migration path for existing Terraform or SQL projects. A dbt project that has a `target/manifest.json` is routed to the [dbt manifest importer](#importing-a-dbt-project) automatically.

## Mode 2 — foreign tool importer

Convert an existing tool project into a FLUID contract. The ingestion importers (Meltano, Airbyte, dlt, Singer) write one Bronze acquisition contract each. The dbt importer writes one contract per dbt project by default.

```bash
fluid import meltano <project-dir>                        # Meltano project (meltano.yml)
fluid import airbyte <workspace-id> --server-url https://airbyte.example.com
fluid import dlt <pipeline-name-or-dir>                   # dlt pipeline (state.json)
fluid import singer <tap-config.json>[:<target-config.json>]
fluid import dbt <project-dir|manifest>                   # dbt project (target/manifest.json)
fluid import schema-registry <subject> --registry confluent --url https://sr.example.com
```

| Option | Description |
| --- | --- |
| `<engine> <source>` | Importer mode + source identifier |
| `--server-url URL` | Airbyte API base URL, for `fluid import airbyte`. There is no default. Falls back to `FLUID_IMPORT_AIRBYTE_URL`. |
| `--out PATH` | Output contract path (default: one `contract.<id>.fluid.yaml` in the current directory); with `--split-by` producing multiple products, `--out` is the output **directory** |
| `--split-by {project\|folder\|group}` | dbt import product boundary: one contract per project (default), per top-level `models/` subfolder, or per dbt group — cross-split `ref()`s become cross-product `consumes[]`. *(since `0.13.1`)* |
| `--provider NAME` | Infrastructure provider for generated contracts. Default `local`. Same rules as in Mode 1. |
| `--yes`, `-y` | Skip the confirmation prompt |

What each importer reads and writes:

| Importer | Reads | Emits |
|---|---|---|
| `meltano` | `plugins.extractors` in `meltano.yml`, and `plugins.loaders` for the report | One `engine: meltano` contract, from the first extractor only. Streams come from the extractor's `select` entries. |
| `airbyte` | The first source in a workspace, over the Airbyte REST API | One `engine: airbyte` contract, from the first source. `streams` is empty. |
| `dlt` | `state.json` in the pipeline directory | One `engine: dlt` contract. Streams are the schema names in `state.json`. A bare name resolves to `$DLT_DATA_DIR/pipelines/<name>` (default `~/.dlt/pipelines/<name>`); a path containing `/` is used as given. |
| `singer` | A tap config JSON, and optionally a target config after a colon | One `engine: meltano` contract (Meltano runs Singer taps). The tap kind comes from the file name (`tap-postgres.json` gives `postgres`). |
| `dbt` | `target/manifest.json` (+ optional `catalog.json`) | One contract per project by default; `--split-by folder`/`group` splits along product boundaries — see below |

The ingestion importers set `mode: full_refresh` and `fluidVersion: 0.7.3`, and use `owner.team: imported` as a placeholder. The dbt importer also writes `0.7.3`. A `0.7.3` contract validates; change the version line to `0.7.5` when you want a later version's fields.

### Importing a schema registry subject

*On forge-cli `main`, not yet in a release ([forge-cli #939](https://github.com/Agenticstiger/forge-cli/pull/939)).* `fluid import schema-registry` reads one subject from a schema registry and writes a consumer contract: a `0.7.7` contract with one build whose `properties.stream` (topic, format, schema and registry) comes from the subject. [Schema registry](../advanced/schema-registry.md) says what the contract does with it.

```bash
fluid import schema-registry <subject> --registry confluent --url https://sr.example.com [--version N]
fluid import schema-registry <subject> --registry glue [--registry-name NAME] [--version N]
```

| Option | Description |
| --- | --- |
| `<subject>` | The subject. On Glue, the schema's name. |
| `--registry {confluent\|glue}` | Required: the registry kind. |
| `--url URL` | The Confluent registry's https URL. Required with `--registry confluent`, and refused with `glue`. |
| `--registry-name NAME` | The Glue registry's name. Default: Glue's default registry. Refused with `confluent`. |
| `--version N` | The subject version to read. Default: the latest. |
| `--out PATH` | Output contract path. Default `contract.<id>.fluid.yaml` in the current directory. |
| `--yes`, `-y` | Skip the confirmation prompt |

The registry options are refused with any other tool, and with the directory scan.

**What it does.** It reads the subject and sends no credential: a registry that needs one has to be read another way. The egress rules run before any request: a link-local host is always refused, and a public host is read only when the operator lists it in `FLUID_ACQUISITION_DEPLOYMENT_HOST_ALLOWLIST` (see [Schema registry](../advanced/schema-registry.md#operator-settings)). A loopback registry needs no entry. The topic is the subject without a `-value` suffix. The contract's registry block names the version that was read, for a latest read too, so it records what it was seeded from. It writes the contract only when `fluid validate` and `fluid plan` would accept it: the contract is validated in process before anything is written, and the columns go through the same parse `fluid plan` uses.

Captured on forge-cli `main` against a Confluent-compatible registry on loopback, for the subject `commerce.orders-value` (Avro, version 3):

```text
📥 Importing schema-registry configuration from commerce.orders-value…
✓ Wrote imported.fluid.yaml

  Mapped 1:1 (2):
    • topic commerce.orders
    • schema version 3 read (3 columns, format avro-confluent)

  Used defaults (1):
    • exposes[0] binds platform: other (no sink chosen); builds[0] sets no engine

  Notes:
    – Choose the engine and the sink, replace `properties.sql`, then run `fluid validate`.
```

The file it wrote has this build:

```yaml
builds:
- id: consume-commerce-orders
  pattern: embedded-logic
  outputs:
  - commerce_orders
  properties:
    sql: '-- TODO: transform the stream into the output'
    stream:
      kind: kafka
      topic: commerce.orders
      format: avro-confluent
      schema:
      - name: order_id
        type: string
        required: true
      - name: amount
        type: decimal(18,2)
        required: true
      - name: note
        type: string
        required: false
      registry:
        kind: confluent
        url: http://127.0.0.1:18081
        version: 3
```

The contract validates, with two warnings: its description and its `properties.sql` carry a `TODO`, so `fluid validate --strict` fails until you choose the engine and the sink and replace the placeholder. The expose binds `platform: other`.

**Refusals.** Each names the subject and the version, and nothing is written:

- a subject that gives no valid Kafka topic;
- field names that are not identifiers;
- a subject with no fields;
- a schema with no FLUID column type;
- a Protobuf subject, because `0.7.7` has no consumed Protobuf stream format.

Without `--registry`, `fluid import schema-registry` stops with `` `fluid import schema-registry` requires --registry ``, and `--registry confluent` without `--url` with `--registry confluent requires --url`. A subject that does not exist stops with `could not read subject '<subject>' (latest) from the confluent registry`, and `HTTP 404 (40401): Subject not found`.

**The Glue region.** A Glue read takes the environment's region in the AWS SDK's order: `AWS_REGION`, then `AWS_DEFAULT_REGION`, then the profile. boto3 1.x reads only `AWS_DEFAULT_REGION`, so forge applies the order itself. A not-found names the region it read in, which is the first thing to check.

### Airbyte needs a server URL

`fluid import airbyte` reads the workspace over the Airbyte REST API, and since 0.16.0 it has no default endpoint. Without `--server-url` or `FLUID_IMPORT_AIRBYTE_URL` it stops before opening a connection:

```bash
fluid import airbyte ws-123
```

```text
✗ `fluid import airbyte` has no Airbyte server URL
  why  Importing a workspace reads it over the Airbyte REST API, and no base URL was supplied on the command line, in the environment, or by the calling code. There is no default to fall back on.
  fix  Pass `--server-url https://airbyte.example.com`, or set FLUID_IMPORT_AIRBYTE_URL in the environment.
```

```bash
fluid import airbyte ws-123 --server-url https://airbyte.example.com
# or
export FLUID_IMPORT_AIRBYTE_URL=https://airbyte.example.com
fluid import airbyte ws-123
```

The option wins over the variable. The importer sends no `Authorization` header, and 0.18.1 has no flag or environment variable that sets one, so it can read only a server that answers unauthenticated requests. An unreachable server fails with the connection error, for example `[Errno 61] Connection refused`.

### Secrets become `{{ env.<NAME> }}` placeholders

The `meltano`, `airbyte` and `singer` importers replace the value of any connection key whose name contains `token`, `password`, `secret`, `key` or `credential` with `{{ env.<KEY_UPPERCASED> }}`:

```yaml
connection:
  host: db.internal
  user: reader
  password: '{{ env.PASSWORD }}'
```

In a contract, `{{ env.NAME }}` is the form the loader substitutes; a literal `${NAME}` would stay a literal string. Export the variable before `fluid apply`. Review the file anyway: the match is on the key name, so a secret under a key named something else is copied as written. The `dlt` importer writes an empty `connection`, and the `dbt` importer carries no connection. This is different from [`fluid init --discover`](./init.md#discover-—-introspect-a-source-into-a-bronze-contract), which does not redact.

### Example — migrating from Meltano

```bash
fluid import meltano proj --provider local --yes
```

```text
📥 Importing meltano configuration from proj…
✓ Wrote contract.bronze.dev_postgres.fluid.yaml

  Mapped 1:1 (2):
    • extractor.tap-postgres
    • loader.target-jsonl
```

```bash
fluid validate contract.bronze.dev_postgres.fluid.yaml
```

```text
✅ Valid FLUID contract (schema v0.7.3)
```

The file name and id come from the project's `default_environment` and the tap (`dev` and `tap-postgres` give `bronze.dev_postgres`). Run [`fluid apply`](./apply.md) once the connection values resolve. See [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) for engine-specific properties.

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
