# `fluid import`

Convert existing tooling into FLUID contracts. Two modes: scan an existing dbt / Terraform / SQL directory, or import a foreign tool project (Meltano, Airbyte, dlt, Singer, dbt). *(since 0.37.0)* The same command proposes products from PySpark jobs and Airflow DAGs. *(since 0.31.0, [forge-cli #939](https://github.com/Agenticstiger/forge-cli/pull/939))* A schema registry subject can seed a contract too.

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
fluid import pyspark <jobs-dir> [--dags <dags-dir>]       # PySpark jobs (since 0.37.0)
fluid import airflow <dags-dir>                           # Airflow DAG files (since 0.37.0)
```

| Option | Description |
| --- | --- |
| `<engine> <source>` | Importer mode + source identifier |
| `--server-url URL` | Airbyte API base URL, for `fluid import airbyte`. There is no default. Falls back to `FLUID_IMPORT_AIRBYTE_URL`. |
| `--out PATH` | Output contract path (default: one `contract.<id>.fluid.yaml` in the current directory); with `--split-by` producing multiple products, `--out` is the output **directory** |
| `--split-by {project\|folder\|group\|table\|job\|dag\|task}` | Product boundary. dbt: `project` (the default), `folder` or `group`, as described [below](#splitting-one-project-into-multiple-products-split-by-since-0-13-1). *(since `0.13.1`)* `pyspark` and `airflow`: see [the PySpark and Airflow section](#importing-pyspark-jobs-and-airflow-dags). There is no default in the parser: each importer picks its own. |
| `--dags DIR` | *(since 0.37.0)* `fluid import pyspark` only: the DAGs directory, so each task is joined to the script it submits. |
| `--conventions FILE` | *(since 0.37.0)* `fluid import pyspark` and `airflow`: your layout as data. See [the conventions file](../advanced/importing-existing-pipelines.md#the-conventions-file). |
| `--registry {confluent\|glue}`, `--url`, `--registry-name`, `--version` | `fluid import schema-registry`, and, *(since 0.37.0)* `fluid import pyspark` with `--registry`: read a written topic's columns from a registry (see [below](#importing-pyspark-jobs-and-airflow-dags)). |
| `--dry-run` | *(since 0.37.0)* For every importer: print the proposal and the report, and write nothing. |
| `--force` | *(since 0.37.0)* Replace a contract file that already exists and differs from what the import writes. Only `pyspark` and `airflow` need it (see [Writing files](#writing-files)). |
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
| `pyspark` | *(since 0.37.0)* PySpark job files under `<jobs-dir>`, and DAG files under `--dags` | One product per output table or topic. See [below](#importing-pyspark-jobs-and-airflow-dags). |
| `airflow` | *(since 0.37.0)* DAG files under `<dags-dir>`, and the scripts they submit through `script_roots` | One product per output table or topic. |

The ingestion importers set `mode: full_refresh` and `fluidVersion: 0.7.3`, and use `owner.team: imported` as a placeholder. The dbt importer also writes `0.7.3`. A `0.7.3` contract validates; change the version line to `0.7.5` when you want a later version's fields.

### Importing a schema registry subject

*(since 0.31.0, [forge-cli #939](https://github.com/Agenticstiger/forge-cli/pull/939))* `fluid import schema-registry` reads one subject from a schema registry and writes a consumer contract: a `0.7.7` contract with one build whose `properties.stream` (topic, format, schema and registry) comes from the subject. [Schema registry](../advanced/schema-registry.md) says what the contract does with it.

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

Captured on 0.31.0 against a Confluent-compatible registry on loopback, for the subject `commerce.orders-value` (Avro, version 3):

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

## Importing PySpark jobs and Airflow DAGs

*(since 0.37.0)* `fluid import pyspark` and `fluid import airflow` propose contracts from code that already runs. The files are parsed and never run, and Airflow is never loaded. The [guide](../advanced/importing-existing-pipelines.md) says what is read, how products are proposed, and what the conventions file holds.

```bash
fluid import pyspark ./jobs --dags ./dags --dry-run
fluid import pyspark ./jobs --dags ./dags --conventions conventions.yaml --split-by job --out ./products/
fluid import airflow ./dags --conventions conventions.yaml
fluid import pyspark ./jobs --registry confluent --url https://sr.example.com --dry-run
```

| Option | Description |
| --- | --- |
| `<jobs-dir>` | `fluid import pyspark`: the directory of PySpark job files. |
| `<dags-dir>` | `fluid import airflow`: the directory of DAG files. `--dags` and `--version` are not accepted here. |
| `--dags DIR` | `fluid import pyspark`: join each DAG task to the script it submits. This adds the schedule, owner, tasks and dependencies to the build. Without it, the DAG facts are not read by `pyspark`. |
| `--conventions FILE` | Your layout as data: script and data prefixes, helper functions, environments, owners, layers, what to ignore, the product id rule. Read strictly, and no code in it runs. See [the conventions file](../advanced/importing-existing-pipelines.md#the-conventions-file). |
| `--split-by {table\|job\|dag\|task\|folder\|project}` | One product per output table or topic (`table`, the default), per job file (`job`), per Airflow DAG (`dag`), per DAG task (`task`: the outputs of every job one task runs, a driver's job list included, with the id `<domain>.<dag>.<task>`, and a job no task runs is a product of its own), per top-level folder (`folder`), or one for everything (`project`). `group` is a dbt boundary and is refused here. `task` *(since 0.37.0)*. |
| `--registry {confluent\|glue}` | `fluid import pyspark`: read the columns of a written topic through the schema-registry importer. Only when asked. `confluent` needs `--url`, and `glue` takes `--registry-name`. |
| `--out PATH` | The output file for one product, or the output directory for several. |
| `--dry-run` | Print the proposal and the report, and write nothing. |
| `--force` | Replace an existing file that differs from what the import would write. |

Every proposal is checked against the schema before anything is written. A schema error stops the import. [`fluid validate`](./validate.md)'s contract rules also run on it: what they find that no code can give (the columns, a Databricks schema, a Snowflake warehouse) is listed in the report and the contract is still written.

After the import, run [`fluid validate`](./validate.md) on the files. Complete the entries under **Used defaults** in the report, then run again.

### Writing files

All importers follow these rules *(since 0.37.0)*:

- An output path is looked at without following links. A symbolic link, a directory or a device at an output path is refused with or without `--force`, and nothing is written. A write is all-or-nothing.
- A file is written whole to a temporary file next to it, then renamed over the target. A file it replaces keeps its permission bits. A new file gets what the umask allows.
- `--out` naming an existing file is refused when several products are written. With several products, `--out` is a directory.
- `--split-by table`, `job`, `dag` and `task` are refused for `dbt`, `meltano`, `airbyte`, `dlt`, `singer`, `schema-registry` and the legacy scan.

`pyspark` and `airflow` also never replace a file that differs from what they would write, unless you give `--force`. The other importers always overwrite. An existing file is compared only as far as it could equal the proposal, so a different line-ending style still counts as unchanged. Importer plugins can ask for the same guard (see [the plugin guide](../advanced/importing-existing-pipelines.md#importer-plugins)).

`--dry-run` labels each file `new`, `unchanged`, `replaces the existing file (--force)` or `refused`, and counts them.

### Errors and troubleshooting

| Message | What to do |
| --- | --- |
| ``--split-by group does not apply to `fluid import pyspark` `` | Use `table`, `job`, `dag`, `task`, `folder` or `project`. |
| `refusing to overwrite N existing file(s) that differ from this import` | Review the differences, then run with `--force`, or choose another `--out`. |
| `refusing to write over N path(s) that are not regular files` | A link, directory or device is at an output path. Remove it or choose another `--out`. |
| `too much to propose from ...` | Point at a smaller directory, or add `ignore.files` to the conventions. `--split-by job` also lowers what one proposal holds. |
| ``... it has more than 50,000 '{' characters`` | A generated file. Add it to `ignore.files`. |
| `the scan has read 64 MB of source` | Point at a smaller directory. |
| `<path> leaves the directory of the conventions file and the directories named on the command line: keep what the scan reads inside one of them` | Keep `script_roots`, `config_modules` and `drivers` paths next to the conventions file, or inside the directories you name. See [where a path may point](../advanced/importing-existing-pipelines.md#where-a-path-may-point). |
| `the conventions file ... has a problem` | The message names the key and the line. A key that is not known, a key given twice, an environment value that is not text, and a platform or format the schema does not have are all refused. |
| `is not named under environments or airflow_variables` | `environment` must name an environment that one of the two blocks has. |
| `expected text: write "" for an empty value, put anything YAML would read as a number, a yes/no or a date in quotes, or leave the variable out` | An environment value was null, a list or a mapping. Quote it, or remove it. |
| `the proposal ... is not a valid contract` | A conventions value the schema refuses, or a bug. Check the value it names. |
| `... is not a constant` (report) | A name did not fold. Name a helper under `helpers`, or the variable under `environments` or `airflow_variables`. |
| `joined to a job file by file name only` (report) | Map the deployed prefix under `script_roots`. |
| A task that is not joined (report) | Map its prefix under `script_roots`, or run `pyspark` with `--dags`. For a driver, check the `drivers` entry: its script, `--job-list` as a constant, the list file, plain job names, and a directory inside the allowed ones. |
| `several job files match it equally` (report) | Two job files share a name. Map a prefix under `script_roots`. |

[The guide](../advanced/importing-existing-pipelines.md#the-report) lists the other report lines and says what to do about each. The [limits](../advanced/importing-existing-pipelines.md#limits) and the [credential masking rules](../advanced/importing-existing-pipelines.md#credential-masking) are there too.

### Importer plugins

*(since 0.37.0)* A package can add `fluid import <tool>` through the `fluid_build.importers` entry-point group. The names come from a registry: the built-in importers first, then plugins. [`fluid plugins`](./plugins.md#importer-plugins) lists them under the role `importer`. See the [plugin guide](../advanced/importing-existing-pipelines.md#importer-plugins).

## Notes

- Mode 1 (`fluid import` with no engine arg) is the existing migration path for dbt / Terraform / SQL projects.
- Mode 2 (`fluid import <engine> <source>`) is the explicit tool importer — Meltano / Airbyte / dlt / Singer since `0.8.3`, dbt since `0.12.0`, PySpark and Airflow since `0.37.0`.
- Since `0.14.0` the Snowflake round-trip is verified end-to-end: `import dbt` → [`apply`](./apply.md) creates no duplicate lowercase shadow namespace and a second apply is a no-op (`+0 ~2 -0`); [`fluid verify`](./verify.md) reads the deployed objects.
- If you want a clean greenfield start instead, use [`fluid init`](./init.md) or [`fluid forge`](./forge.md).
- For source-aligned ingestion from scratch (no existing tool project), [`fluid init --discover`](./init.md#discover-—-introspect-a-source-into-a-bronze-contract) is the one-shot path.
