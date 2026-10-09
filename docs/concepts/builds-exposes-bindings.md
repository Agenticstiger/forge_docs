---
title: Builds, Exposes, Bindings
description: The three core blocks of a contract - produce, surface, land - plus consumes[], which names the products a build reads.
---

# Builds, Exposes, Bindings

Every contract maps three questions onto three YAML blocks:

| Question | Block | Example |
|---------|-------|---------|
| **How is the data produced?** | `builds[]` | Embedded SQL, a dbt project, a Python script, an ingestion job. |
| **What does the product expose to consumers?** | `exposes[]` | A table, a view, a file, a Kafka topic. |
| **Where does it physically land?** | `binding` (inside each expose) | `gcp/bigquery_table`, `aws/s3_file`, `local/parquet`, etc. |

You can have many of each. Every `expose` must declare exactly one `binding`.

The examples on this page validate against schema `0.7.5`, the latest stable version. Fields that need `0.7.6` (preview) are in [their own section](#fields-that-need-fluidversion-0-7-6).

## `builds[]` - production logic

```yaml
builds:
  - id: load_orders
    pattern: embedded-logic            # or hybrid-reference, multi-stage, acquisition
    engine: sql
    properties:
      sql: SELECT order_id, customer_id, amount, region FROM raw_orders
      parameters:
        inputs:                        # which file backs the name raw_orders
          - name: raw_orders
            path: data/orders.csv
            format: csv
```

`pattern` decides which keys `properties` may hold. The schema rejects any other key:

| Pattern | `properties` keys | What runs it |
|---|---|---|
| `embedded-logic` | `sql` (required), `language` (`sql`, `flink_sql`, `pyspark`, `scala`, `python`, `r`), `parameters` | The local DuckDB engine, or the platform named in `execution.runtime.platform`. |
| `hybrid-reference` | `model` (required), `target`, `select`, `models`, `vars`, `materializations` | A dbt project at `repository`, or, with `engine: python`, the script `<repository>/<model>.py`. |
| `multi-stage` | `stages[]`: each has `name`, `pattern`, `properties`, `dependsOn`, `outputs` | Orchestration of named build steps. |
| `acquisition` | `source` (required), `sink`, `delivery`, `schemaEvolution`, `quality`, and engine blocks | An ingestion engine. See [Source-Aligned Acquisition](../advanced/source-aligned-acquisition.md). |

A build with `properties` and no `pattern` fails validation: the schema cannot tell which key set applies, so it reports the missing and unexpected keys of several patterns at once (`'model' is a required property`, `'source' is a required property`, and `'sql' was unexpected`). Name the `pattern`.

There is no `script` key on `embedded-logic`: a build that carries `properties.script` fails validation with `properties: Additional properties are not allowed ('script' was unexpected)` and `'sql' is a required property`. A Python script is a `hybrid-reference` build, shown in [Build execution](#build-execution-where-sql-and-python-run).

### Which builds `fluid apply` runs

In the default `--mode amend`, the local provider runs the inline SQL of an embedded-SQL build itself. It binds `parameters.inputs`, and it does not resolve `consumes[]`. A Python build or an acquisition build is not run: the expose gets a placeholder file (`id,value` and `1,materialized`) and the apply reports success. `--mode amend-and-build` runs each build through its own runner:

```bash
fluid apply contract.fluid.yaml --yes --mode amend-and-build
```

Under `--mode amend-and-build`, each build goes to the runner that matches it:

- an `acquisition` build runs on its ingestion engine;
- a build with `engine: sql`, or `pattern: embedded-logic` with `properties.sql`, runs as embedded SQL;
- a dbt build runs the dbt project at `repository`;
- any other build runs the Python script `<repository>/<model>.py`.

An embedded-SQL build runs on the platform its `execution.runtime.platform` declares. `local`, `duckdb`, or no value means the local DuckDB engine; `snowflake` runs on the declared warehouse. Any other platform, `gcp` for example, fails before the SQL runs:

```text
❌ Build 'summarize' declares execution.runtime.platform: 'gcp', which has no
embedded-SQL executor. forge-cli will not downgrade a declared platform to the
local DuckDB engine. Supported: duckdb, local, snowflake.
```

On the local DuckDB engine the SQL runs inside the [DuckDB sandbox](../advanced/duckdb-sandbox.md): it reads the contract's directory and the locations the contract declares, and nothing else.

### Naming the files a SQL build reads: `parameters.inputs`

Under `builds[].properties.parameters.inputs`, each `{name, path}` entry registers a file as a DuckDB view called `name`. Your SQL reads `name`:

```yaml
parameters:
  inputs:
    - name: raw_orders
      path: data/orders.csv
```

Four rules, each measured on 0.18.1:

- **The reader depends on the mode.** Under `--mode amend-and-build` it comes from the file extension: a `.csv` path is read as CSV, a `.parquet` path as Parquet, and the `format:` key, though the schema accepts it, is not read. A Parquet file named `orders.bin` with `format: parquet` fails there with `Invalid Input Error: Error when sniffing file "orders.bin"`, because it was read as CSV. A plain `fluid apply` honours `format:` for the same input and loads it as Parquet. Name the file with its real extension and both agree.
- **The path resolves against the directory you run `fluid` from**, not the contract's directory. `fluid apply orders/contract.fluid.yaml` from the parent directory fails with `Input file not found: data/orders.csv`. The same is true of a relative path you write inside the SQL (`read_csv_auto('./data/orders.csv')`).
- **`{{ env.NAME }}` works in `path`**, so a shared data directory can be set per run (`path: "{{ env.SHOP_DATA }}/orders.csv"`).
- **An input named like a `consumes[]` entry's `exposeId` wins over that entry.** See [`consumes[]`](#consumes-depending-on-another-product).

### `outputs`: which expose a build writes

`builds[].outputs` lists the `exposeId`s a build produces. What it does depends on the runner:

- **Acquisition builds** write to the first expose whose `exposeId` appears in the build's `outputs`, and to `exposes[0]` when it names none. As of 0.18.1 their schema-drift check still compares the source with `exposes[0]`'s declared schema, so a second build whose source differs fails with `source schema drift detected` when `exposes[0]` has `schemaPolicy: discover_and_freeze`, the policy `fluid init --discover` writes. With `evolve_safe` on `exposes[0]` the second build lands in its own expose.
- **Embedded-SQL builds on the local DuckDB engine** write one result, to `exposes[0]`, whatever `outputs` says. Naming a second expose prints a warning and writes nothing there.
- **Streaming Iceberg sinks.** *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* A Kafka Connect or embedded Debezium Server build whose Iceberg sink config forge-cli derives writes the Iceberg exposes its `outputs` name: exactly one for Kafka Connect, and for Debezium Server one or more that share a database and a catalog. `fluid validate` refuses a build whose outputs its sink cannot write that way. See [Which exposes a streaming sink writes](../advanced/source-aligned-acquisition.md#which-exposes-a-streaming-sink-writes).

As of 0.18.1, two embedded-SQL builds in one contract therefore share a destination. Each names its own expose in `outputs`; both run; and the second overwrites the first's file:

```text
⚠️  expose by_customer is named in the build's outputs, but this path writes
only the first expose (by_region); by_customer is not written by this build
```

After that run `out/by_region.parquet` held the second build's rows (`customer_id`, `revenue`). Until this changes, give each embedded-SQL build its own contract. An extra expose bound to a cloud store or a warehouse is refused instead of skipped (from the v0.18.1 source).

## `exposes[]` - the consumer-facing API

```yaml
exposes:
  - exposeId: bitcoin_prices
    title: Bitcoin Hourly Prices
    kind: table                        # see expose.kind enum below
    binding:
      platform: local
      format: parquet
      location:
        path: ./runtime/out/bitcoin_prices.parquet
    contract:
      schema:
        - name: price_timestamp
          type: TIMESTAMP
          required: true
        - name: price_usd
          type: NUMERIC
          required: true
```

An expose needs `exposeId`, `kind`, `binding` and `contract`. The schema lives at `exposes[].contract.schema`. Quality rules live one level deeper at `exposes[].contract.dq.rules` (see [Quality, SLAs & Lineage](./quality-sla-lineage.md)).

`expose.kind` is one of:
`table` · `view` · `api` · `file` · `stream` · `topic` · `feature_store` · `model` · `vector` · `graph` · `time_series` · `other`

## `binding` - the physical landing target

`binding.platform` is one of (schema `0.7.5`):
`gcp` · `aws` · `azure` · `snowflake` · `databricks` · `kafka` · `confluent` · `local` · `kubernetes` · `postgres` · `pgvector` · `other`

`binding.format` is one of (schema `0.7.5`):
`bigquery_table` · `snowflake_table` · `snowflake_view` · `gcs_file` · `s3_file` · `http_api` · `grpc_api` · `pubsub_topic` · `kafka_topic` · `delta_table` · `iceberg` · `parquet` · `csv` · `json` · `redshift_table` · `redshift_serverless` · `redshift_external_schema` · `postgres_table` · `athena_table` · `glue_table` · `pgvector_table` · `other`

`binding.location` is a closed set of keys: any key outside the schema, such as `prefix`, fails with `exposes[0].binding.location: Additional properties are not allowed`. The keys each format reads:

| Format | `location` keys to set |
|--------|--------------------------|
| `bigquery_table` | `project`, `dataset`, `table` (`region` optional) |
| `snowflake_table` | `database`, `schema`, `table` |
| `s3_file` | `bucket`, `path` (`region` recommended). `path` is the bucket-relative prefix. |
| `parquet` / `csv` on `aws` | `bucket`, `path`, plus `database` and `table` for the Glue table, and `region` |
| `parquet` / `csv` on `local` | `path` |

For `s3_file`, the key is `path`, and `prefix` is not a key. `fluid generate iac` with `bucket`, `path` and `region` writes the bucket; with `prefix` the contract does not validate.

### Where a local `path` points

The rules for every local path, inputs included, are in [Local provider: where paths resolve](../providers/local.md#where-paths-resolve).

A relative `location.path` on `platform: local` resolves against the **contract's directory**, not the directory you run `fluid` from. That holds for the build, for the local provider, and for `fluid verify` and `fluid diff`, so a relative output lands under the contract's directory:

```bash
fluid apply orders/contract.fluid.yaml --yes --mode amend-and-build   # from the parent directory
ls orders/out
```

```text
orders.parquet
```

`{{ env.NAME }}` in a local `path` resolves the same way in the writer, `verify` and `diff`, so products built in separate CI workspaces can share a data directory:

```yaml
location:
  path: "{{ env.SHOP_DATA }}/orders.parquet"
```

An absolute path outside the directories the engine may read and write is refused by the [DuckDB sandbox](../advanced/duckdb-sandbox.md). Declaring `/tmp/out/orders.parquet` as an output path fails with `The contract declares '/tmp/out/orders.parquet' ..., outside the directories it may read and write`.

### Moving a product to another platform

Changing `platform: local` to `platform: gcp` and nothing else does not retarget a contract. On 0.18.1, `fluid validate` passes with a warning, and `fluid generate iac` and `fluid apply` would emit nothing for the port:

```text
⚠️  1 warning(s)
 1. expose 'orders': platform=gcp resolves to no GCP resource — binding.format
is 'parquet' and binding.location names none of dataset (BigQuery), bucket
(Cloud Storage), topic (Pub/Sub). `fluid generate iac` and `fluid apply` would
emit nothing for this port.
```

The platform, the format and the location all change. Keep them out of the base contract by putting each cloud's binding in an overlay file beside it ([Environments and overlays](./environments-and-overlays.md) says how `--env` finds and merges it; [One contract, two clouds](../recipes/one-contract-two-clouds.md) deploys the result to both). The base stays on `local`:

```yaml
# contract.fluid.yaml (excerpt)
exposes:
  - exposeId: orders
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: out/orders.parquet
```

```yaml
# overlays/aws.yaml
exposes:
  - binding:
      platform: aws
      format: parquet
      location:
        bucket: <your-lake-bucket>
        path: bronze/orders/
        database: shop
        table: orders
        region: eu-west-1
```

```bash
fluid validate contract.fluid.yaml --env aws
fluid generate iac contract.fluid.yaml --env aws --out iac
```

```text
Wrote OpenTofu module: iac/main.tf.json  (provider: aws, 3 resources)
```

The three resources are a Glue database, a Glue table whose location is `s3://<your-lake-bucket>/bronze/orders/`, and the S3 bucket. The schema, quality rules and governance blocks stay as they are in the base file. The overlay patches `exposes[0]` by position and changes only the binding; see [Per-environment overlays](../recipes/per-environment-overlays.md) for the merge rules. The [switch-clouds recipe](../recipes/switch-clouds.md) covers `--provider`.

## Multi-expose products: one product, many surfaces

Most data products produce one output. Some produce several: a Gold table for analysts, a feature_store view for the ML team, a Pub/Sub topic for downstream consumers. Add multiple `exposes[]` entries:

```yaml
exposes:
  - exposeId: customer_360_table          # for analysts
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location: { project: prod, dataset: analytics, table: customer_360 }
    policy:
      authz:
        readers: [group:analysts@company.example.com]
    contract:
      schema:
        - { name: customer_id, type: STRING }

  - exposeId: customer_360_features       # for ML
    kind: feature_store
    binding:
      platform: gcp
      format: bigquery_table
      location: { project: prod, dataset: features, table: customer_360_v1 }
    policy:
      authz:
        readers: [group:ml-team@company.example.com, "serviceAccount:training@<project>.iam.gserviceaccount.com"]
    contract:
      schema:
        - { name: customer_id, type: STRING }

  - exposeId: customer_changes            # for downstream
    kind: stream
    binding:
      platform: gcp
      format: pubsub_topic
      location: { project: prod, topic: customer-changes }
    contract:
      schema:
        - { name: customer_id, type: STRING }
```

`builds[]` is a list on the contract, not on an expose, and each expose gets its own audience through `policy.authz`. Which build writes which expose is the `outputs` rule [above](#outputs-which-expose-a-build-writes).

## `consumes[]` - depending on another product

When your product depends on another product (Silver reading Bronze, Gold reading Silver), declare it in `consumes[]`. Each entry is a logical address, the upstream's `productId` and the `exposeId` you read:

```yaml
consumes:
  - productId: bronze.shop.orders_v1
    exposeId: orders
    purpose: Revenue by region
    versionConstraint: "^1.0.0"
```

`productId` and `exposeId` are required. The entry also accepts `versionConstraint`, `qosExpectations`, `requiredPolicies`, `purpose`, `tags` and `labels`, and nothing else: a `consumeId`, a `contract:` block, or an `alias`/`product`/`expose` key fails validation with `consumes[0]: Additional properties are not allowed`. There is no `{{ alias }}` templating in SQL. An entry carries no physical address; it is resolved when a build runs.

### Worked example: a Silver product reading a Bronze product

Two contracts in one workspace ([Workspaces](./workspaces.md) covers the file and how a build finds its upstream). `fluid.workspace.yaml` marks the workspace root (create it by hand, or let `fluid init` write one beside a project it scaffolds):

```text
shop/
├── fluid.workspace.yaml
├── orders/
│   ├── contract.fluid.yaml
│   └── data/orders.csv
└── order-summary/
    └── contract.fluid.yaml
```

```yaml
# shop/fluid.workspace.yaml
schema_version: 1
kind: WorkspaceConfig
workspace:
  name: shop
  provider: local
```

`orders/contract.fluid.yaml` is the upstream. It reads a CSV and lands `out/orders.parquet`:

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: bronze.shop.orders_v1
name: Shop Orders
metadata:
  layer: Bronze
  owner:
    team: shop-data
    email: shop-data@example.com
builds:
  - id: load_orders
    pattern: embedded-logic
    engine: sql
    properties:
      sql: SELECT order_id, customer_id, amount, region FROM raw_orders
      parameters:
        inputs:
          - name: raw_orders
            path: data/orders.csv
            format: csv
exposes:
  - exposeId: orders
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: out/orders.parquet
    contract:
      schema:
        - name: order_id
          type: INTEGER
        - name: customer_id
          type: STRING
        - name: amount
          type: NUMERIC
        - name: region
          type: STRING
```

`order-summary/contract.fluid.yaml` is the downstream. Its SQL reads the upstream by `exposeId`, `FROM orders`:

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: silver.shop.order_summary_v1
name: Order Summary by Region
metadata:
  layer: Silver
  owner:
    team: shop-analytics
    email: shop-analytics@example.com
consumes:
  - productId: bronze.shop.orders_v1
    exposeId: orders
    purpose: Revenue by region
builds:
  - id: summarize
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT region, COUNT(*) AS orders, SUM(amount) AS revenue
        FROM orders
        GROUP BY region
exposes:
  - exposeId: order_summary
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: out/order_summary.parquet
    contract:
      schema:
        - name: region
          type: STRING
        - name: orders
          type: INTEGER
        - name: revenue
          type: NUMERIC
```

Build the upstream, then the downstream, with `--mode amend-and-build`:

```bash
cd shop/orders && fluid apply contract.fluid.yaml --yes --mode amend-and-build
cd ../order-summary && fluid apply contract.fluid.yaml --yes --mode amend-and-build
```

```text
🔷 Build 'summarize' (embedded-SQL / local DuckDB)
   ⬅ consumes bronze.shop.orders_v1/orders as view "orders": .../shop/orders/out/orders.parquet
   ...
   ✅ Completed in 0.03s — 1 action(s) executed
```

`out/order_summary.parquet` holds one row per region:

| region | orders | revenue |
|---|---|---|
| eu | 2 | 162.25 |
| us | 1 | 80.5 |

Plain `fluid apply` (the default `--mode amend`) does not resolve `consumes[]`. The same downstream contract fails there, because nothing created a view called `orders`:

```text
❌ Deployment failed: Unknown error

Action Errors:
  1. ✗ unknown: Catalog Error: Table with name orders does not exist!
Did you mean "pg_prepared_statements"?
```

### How an embedded-SQL build resolves each entry

On the local DuckDB engine, `--mode amend-and-build` resolves `consumes[]` like this:

- **Which entries.** An entry is read when the SQL names a relation equal to its `exposeId`, as DuckDB's own parser sees the query. Each entry the SQL reads becomes a view named by its `exposeId`. An entry the SQL does not read is lineage only: the build prints `lineage only, the SQL reads no relation named 'ghost', so it is not resolved` and carries on.
- **Which contract.** The one declaring `id: <productId>` in a file named `contract.fluid.yaml` or `contract.fluid.json`, found under the nearest directory above the downstream contract that holds `fluid.workspace.yaml`, up to four directories deep. Directories such as `dist`, `build`, `out`, `runtime` and `.fluid` are skipped. Add other roots, colon-separated, with `FLUID_UPSTREAM_CONTRACTS`; an upstream kept outside the workspace builds when its root is listed there. An id declared by two files fails the build, naming both.
- **Which binding.** The upstream is loaded with the same `--env` overlay as the run, so `--env aws` reads the upstream's `aws` binding and a local run reads its local one. A local binding is read at the `location.path`, relative to the **upstream** contract's directory. An `aws` binding with `bucket` and `path` is read as `s3://<bucket>/<path>/*.<ext>`. A `gcp` `bigquery_table` binding is read from that table. Another warehouse's table, a stream, or a GCS or Azure prefix cannot be read and fails naming the platform. The AWS and BigQuery reads are described from the v0.18.1 source and were not run against a cloud.
- **An explicit input wins.** A `parameters.inputs` entry whose `name` equals the `exposeId` binds that view by hand, and the `consumes[]` entry is not resolved at all. This is how an upstream the engine cannot read, such as a federated one, is still bound.
- **Unresolved fails before any SQL runs.** An entry the SQL reads that matches no contract fails the build:

  ```text
  ❌ consumes bronze.shop.nope_v9/orders: no contract in the workspace declares id 'bronze.shop.nope_v9'
     why: Looked in .../shop (the workspace root), four directories deep, in files named contract.fluid.yaml or contract.fluid.json.
     fix: Check the productId, keep the upstream contract under the directory holding fluid.workspace.yaml, or add its repository to FLUID_UPSTREAM_CONTRACTS.
  Or bind it by hand: a builds[].properties.parameters.inputs entry named 'orders' (with the path to read) wins over the consumes entry and is used as is.
  ```

  An entry that names the contract's own `id` fails the same way (`the contract consumes its own id`), because it would read the file the build is about to overwrite.

A contract saved as `silver.orders.fluid.yaml` is not found by this walk. The composition check in `fluid validate` scans `*.fluid.yaml` instead, so the two lookups can disagree about the same file.

### What `consumes[]` does elsewhere

| Where | What it does with `consumes[]` |
|---|---|
| `fluid validate` | Checks the entry's shape. Does not check that the upstream exists: a `productId` that no contract declares validates. Applies the [composition rule](../data-products/product-type.md#composition-rules) when it can find the upstream's product type. |
| `fluid plan` | Nothing. A contract that consumes a product that does not exist plans and saves the plan. |
| `fluid apply --mode amend-and-build` | Resolves entries for embedded-SQL builds on DuckDB, as above. |
| `fluid generate transformation` (dbt engine) | Writes the entries as dbt `sources` in `models/sources.yml`. |
| `fluid generate transformation` (other engines) | Warns `consumes_not_wired`: the engine does not read `consumes[]`, so nothing it generates comes from the declared upstreams. |
| `fluid generate artifacts` | Writes each entry as a reference to the upstream product in the ODCS, ODPS-Bitol and OPDS output. |
| `fluid policy-compile` | Nothing. It derives grants from `accessPolicy` only, so a Silver product does not get read access on its upstream from `consumes[]`. |

`fluid forge` can pre-fill `consumes[]` from existing products with `--from-product`; see [Consume a data product](../data-products/consume.md).

## Build execution: where SQL and Python run

`builds[].execution` holds the trigger, retries and runtime. This `hybrid-reference` build runs a Python script and a schedule trigger:

```yaml
builds:
  - id: bitcoin_price_ingestion
    pattern: hybrid-reference
    engine: python
    repository: ./scripts
    properties:
      model: ingest                    # runs ./scripts/ingest.py
    execution:
      retries:
        maxAttempts: 3
        backoffStrategy: exponential   # fixed | exponential | linear
      trigger:
        type: schedule
        schedule: "0 * * * *"          # hourly
        timezone: UTC
```

`trigger.type` is one of `schedule`, `event`, `manual`, `dependency`, `dataset`, `schedule_and_dataset`, `timetable`; `scheduled` is not a value, and the cron expression goes in `schedule` (`cron` is also accepted). `fluid apply --mode amend-and-build` runs the script with the contract's directory as its working directory.

With a `schedule` trigger, `fluid generate schedule contract.fluid.yaml --out <dir>` writes an Airflow DAG with `SCHEDULE = '0 * * * *'`. The DAG's task runs `fluid apply ... --mode amend-and-build --build-id <id> --yes`.

`execution.runtime` selects where the build runs. For an embedded-SQL build the key that matters is `platform`, described [above](#which-builds-fluid-apply-runs). The schema also defines `image`, `environment`, `resources`, `timeout`, `serviceAccount` and `executor` under `runtime`.

## Fields that need `fluidVersion` 0.7.6

Schema `0.7.6` is a preview. It validates only when the file names it, and the same fields fail on `0.7.5` with `Additional properties are not allowed`.

- **`consumers[]`** (top level) declares the dashboards, notebooks, analyses, ML jobs and applications built on this product: `name` and `type` (`dashboard`, `notebook`, `analysis`, `ml`, `application`) are required, and `label`, `owner`, `url`, `maturity` (`high`, `medium`, `low`), `description` and `exposeIds[]` are optional. It is shaped like a dbt exposure. Nothing reads it: the schema marks it reserved, and it is carried into `plan.json` unchanged.

  ```yaml
  consumers:
    - name: weekly_revenue_dashboard
      type: dashboard
      owner:
        team: finance
        email: finance@example.com
      maturity: high
      exposeIds: [revenue]
  ```

- **`consumes[].upstreamWorkspace` and `upstreamDigest`** pin an upstream that lives in another mesh ([Federated upstreams](./federation.md)). `upstreamWorkspace` is the federated workspace's id; `upstreamDigest` is the `sha256:<64 hex>` digest of the upstream contract, which `fluid contract digest <file>` prints. `fluid apply` compares it with the upstream's live digest.
- **`binding.principals`, `binding.encryption`, `binding.packaging`** (the first two, with `exposes[].lifecycle.expire`, are covered in [Governance parity](./governance-parity.md)) map the contract's logical principals to identities on a platform, set encryption at rest for S3 and BigQuery, and override packaging per expose.
- **`exposes[].lifecycle.expire`** deletes stored data once it is older than `retention`; it is `false` unless you set it.

## Where to look next

- [Contract reference](../reference/README.md) - the field tables for each schema version, and [preview fields](../reference/preview-fields.md)
- [Semantic layer](./semantic-layer.md) - `exposes[].semantics`: entities, measures, dimensions and metrics
- [Contract fragments](./fragments.md) - split a contract into a root plus fragment files
- [Providers vs platforms](./providers-vs-platforms.md) - how `binding.platform` resolves to actual cloud SDKs
- [Quality, SLAs & Lineage](./quality-sla-lineage.md) - the `dq.rules`, `qos`, and `lineage` blocks
- [Governance & Policy](./governance-policy.md) - the `accessPolicy` and `agentPolicy` blocks
- [Product types](../data-products/product-type.md) - what an SDP, ADP or CDP may consume
- [DuckDB sandbox](../advanced/duckdb-sandbox.md) - what contract SQL may read and write
- [`fluid plan` walkthrough](/forge_docs/cli/plan) - what the planner emits per binding
