# Source-Aligned Acquisition

A source-aligned (Bronze, SDP) data product copies data out of a source system and lands it as it is. The `acquisition` build pattern lets you declare that copy in the contract, rather than writing the ingestion code or an Airflow DAG: you say what to read, which engine reads it, and where the result goes.

Acquisition arrived with schema `0.7.3`. The examples on this page use `0.7.5`, the current stable schema.

<iframe
  src="/forge_docs/reels/source-aligned-bronze.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Six months → sixty seconds — Fluid Forge source-aligned Bronze">
</iframe>

::: tip Where this fits
This page is the reference for the acquisition block: engines, where data lands, what each key does, and what the CLI enforces today. Pair it with [Product Types](../data-products/product-type.md) (the SDP/ADP/CDP vocabulary) and the [Postgres → DuckDB walkthrough](../walkthrough/source-aligned-postgres-duckdb.md) (a worked example).
:::

## Example: a CSV file to Parquet

Save this as `contract.fluid.yaml` next to a `data/orders.csv`, and install the local engine with `pip install "data-product-forge[local]"`.

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: bronze.orders
name: Orders Bronze
domain: sales
metadata:
  layer: Bronze
  owner:
    team: ingestion
    email: ingestion@example.com

builds:
  - id: ingest_orders
    pattern: acquisition
    engine: duckdb            # a build-level key, not under properties
    properties:
      source:
        kind: filesystem
        connection:
          uri: data/orders.csv
        mode: full_refresh
        streams: [orders]
      sink:
        format: parquet
      quality:
        gates:
          - rule: not_null
            columns: [order_id]
            severity: error
        onError: route_to_dlq
    outputs:
      - orders_raw

exposes:
  - exposeId: orders_raw
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: out/orders.parquet
    contract:
      schema: []
```

A source requires `kind` and `mode`. The build names the expose it fills in `outputs`, and that expose's `binding` decides where the data lands (see [Where the build lands data](#where-the-build-lands-data)).

```bash
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --mode amend-and-build --build-id ingest_orders --yes
```

```text
✅ Valid FLUID contract (schema v0.7.5)
...
duckdb.run stream=orders sql_chars=294
...
✅ Executed: 1
❌ Failed: 0
```

`--mode amend-and-build` is what runs the build. A plain `fluid apply` on a local contract takes the local provider's materialisation path and does not run the acquisition engine.

The run writes the Parquet file and one run record, next to a `.fluid/run-id.txt` that holds the run's id:

```text
.fluid/run-id.txt
.fluid/runs/bronze.orders/ingest_orders/runs/<run-id>.json
out/orders.parquet
```

`fluid runs status bronze.orders` and the other [`fluid runs`](../cli/runs.md) commands read those records.

## Ingestion engines

The engine is the build's `engine` key. The values the schema accepts for an acquisition build are `duckdb`, `dlt`, `meltano`, `airbyte`, `kafka-connect` and `debezium`. All of them implement the public `Runner` protocol in `fluid_build.api.runner` (see [API stability](./api-stability.md)).

| Engine | Reads | Needs |
|---|---|---|
| `duckdb` | `source.kind` of `filesystem` (CSV, Parquet, JSON), `postgres`, `mysql` or `mariadb`, `sqlite`, `http` | `pip install "data-product-forge[local]"` (DuckDB 1.5.0 or newer) |
| `dlt` | A dlt verified source, or your own `@dlt.source` module named in `properties.dlt.source_module` | The `dlt` package, for example `pip install "dlt[sql_database]"` for SQL sources |
| `meltano` | A Singer tap | The tap installed in the same environment, or an existing Meltano project named in `properties.meltano.project_dir` |
| `airbyte` | An Airbyte connector, through an Airbyte server or PyAirbyte | A reachable Airbyte server for `bring-your-own` and `managed`; the `airbyte` package for `embedded` |
| `kafka-connect` | A Kafka Connect source connector, driven over the Connect REST API | A Kafka Connect cluster |
| `debezium` | Change data capture from a database, through Kafka Connect or Debezium Server | A Kafka Connect cluster, or the `debezium-server` binary for `embedded` |

There are no `dlt`, `meltano`, `airbyte`, `kafka-connect` or `debezium` extras on the `data-product-forge` package: `pip install "data-product-forge[dlt]"` installs nothing extra. Install the engine's own dependency as shown.

Each runner declares which capabilities and deployment modes it supports. These are the values in the 0.18.1 runner classes:

| Engine | Capabilities | Deployment modes |
|---|---|---|
| `duckdb` | `full_refresh`, `incremental_append`, `schema_discovery`, `at_least_once` | `embedded` |
| `dlt` | `full_refresh`, `incremental_append`, `incremental_merge`, `schema_evolution`, `schema_discovery`, `at_least_once` | `embedded` |
| `meltano` | `full_refresh`, `incremental_append`, `incremental_dedup`, `schema_discovery`, `at_least_once` | `embedded`, `bring-your-own` |
| `airbyte` | `full_refresh`, `incremental_append`, `incremental_dedup`, `cdc`, `schema_discovery`, `at_least_once` | `embedded`, `bring-your-own`, `managed` |
| `kafka-connect` | `streaming`, `cdc`, `schema_discovery`, `at_least_once`, `exactly_once` | `bring-your-own`, `managed` |
| `debezium` | `streaming`, `cdc`, `schema_discovery`, `at_least_once` | `embedded`, `bring-your-own`, `managed` |

### Asking for a capability

A build lists the capabilities it needs in `builds[].capabilities`. At apply time, the CLI compares that list with the engine's declared set and refuses a mismatch before running anything. `fluid validate` does not make this check.

```yaml
    engine: duckdb
    capabilities: [exactly_once]
```

```text
✗ runner `duckdb` does not support capability ['exactly_once']
why  build asks for capabilities=['exactly_once']; runner declares ['at_least_once',
'full_refresh', 'incremental_append', 'schema_discovery'].
fix  Switch engine to one declaring ['exactly_once'], or remove from build.capabilities.
```

This is the typed `CapabilityMismatchError`. Its `doc` link prints [Capability warnings](./capability-warnings.md), which is about LLM model capabilities for `fluid forge`, not about runners. The runner check is the one above.

## Three deployment modes

Airbyte, Meltano, Kafka Connect and Debezium take a `deployment` block under their own properties key (`properties.airbyte.deployment`, `properties.meltano.deployment`, and so on). `duckdb` and `dlt` run inside the `fluid` process and have no `deployment` key.

| `deployment.mode` | Runs where |
|---|---|
| `embedded` *(schema default)* | Inside the `fluid` process, or for Debezium as a local Debezium Server. |
| `bring-your-own` | On a server you already run. Set `server_url`, and `auth.secretRef` for the credential. |
| `managed` | On infrastructure the contract describes in a `managed` block. |

```yaml
      airbyte:
        connector_image: airbyte/source-postgres
        deployment:
          mode: managed
          managed:
            target: kubernetes     # docker | kubernetes | terraform | opentofu
            profile: small         # small | medium | large
```

`managed.target` is required when the mode is `managed`. The block also accepts `chart`, `values_overlay`, `secrets` and `network.egressAllowList`.

When `deployment.mode` is not set, the Airbyte runner uses `bring-your-own`, not the schema's `embedded` default.

## Where the build lands data

The expose binding that the build lists in `outputs` decides where a DuckDB build writes. `sink` only decides the file format. There is no `location` key under `sink`, and a contract that sets one fails validation.

The destination is chosen in this order:

| Binding | The build writes |
|---|---|
| A BigQuery table | A staging file, which a load job then loads into the table. |
| `platform` of `aws`, `gcp` or `azure`, with `location.bucket` | `<s3, gs or azure>://<bucket>/<path>/<table>.<ext>`. `path` is relative to the bucket and is always treated as a prefix. `<table>` is `location.table`, or the stream name when the binding has none. |
| `location.path` and no bucket | A local file at that path, relative to the contract's directory. |
| Neither | `out/<stream>.<ext>` in the contract's directory. |

A `path` that is already a full URI (`s3://...`) is used as written. When the build reads more than one stream, `location.path` is not used and each stream lands at `out/<stream>.<ext>`.

```yaml
exposes:
  - exposeId: orders_raw
    kind: table
    binding:
      platform: aws
      format: parquet
      location:
        bucket: acme-lake
        path: bronze/orders
        database: bronze
        table: orders
        region: eu-west-1
```

With this binding the build writes `s3://acme-lake/bronze/orders/orders.parquet`. The Glue table that `fluid generate iac` emits for the same binding points at `s3://acme-lake/bronze/orders`, so the catalog and the data share one prefix. The destination's DuckDB extensions and credentials come from the destination, not from the source. The AWS-side view of the same landing is in [Where a build lands data](../providers/aws.md#where-a-build-lands-data).

A binding that names no bucket stays on local disk. The build does not invent the `{account}-fluid-data` bucket that the IaC path falls back to, because moving data off the machine on the strength of a default would be a decision the CLI should not make for you.

`sink.format` takes `iceberg`, `delta`, `parquet`, `csv`, `json`, `snowflake_table`, `bigquery_table`, `redshift_table` or `duckdb_table`, with optional `catalog` and `partitionBy`. The DuckDB runner writes `parquet`, `csv` and `json` files. A streaming build's `sink.catalog` must name the same Iceberg catalog as the expose it writes *(forge-cli [#707](https://github.com/Agenticstiger/forge-cli/pull/707), unreleased)*; see [Iceberg catalogs](#iceberg-catalogs-location-catalog).

### What the DuckDB sandbox allows

For the DuckDB engine, each connection runs in DuckDB's own sandbox ([DuckDB sandbox](./duckdb-sandbox.md)). For an acquisition build that means:

- A local source and each landing path must sit in the contract's directory, its FLUID workspace, or a directory in `FLUID_DUCKDB_ALLOWED_DIRS`. Anything else is refused before the build runs:

  ```text
  ✗ The contract declares '/data/landing/orders.csv' (...), outside the directories it may read
  and write (...). The operator can allow a directory with FLUID_DUCKDB_ALLOWED_DIRS.
  fix  Move the file under the contract's directory or its workspace, or, as the operator, list
  its directory in FLUID_DUCKDB_ALLOWED_DIRS (separated by ':').
  ```

- Name a file or a glob as the source `uri`. As of 0.18.1, a `uri` that names a directory outside the contract's directory is refused even when `FLUID_DUCKDB_ALLOWED_DIRS` lists it; `<dir>/orders.csv` or `<dir>/*.csv` works.
- A `source.kind: http` source is read from the URL you declare, and a declared `s3://` location is reachable. These are acquisition builds; SQL written inside a contract cannot read an `http(s)` URL.

## Iceberg catalogs (`location.catalog`)

::: warning Not in a release yet
This section describes forge-cli [PR #707](https://github.com/Agenticstiger/forge-cli/pull/707) and the follow-up fixes in [forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), marked *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)*, and in [forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), marked *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)*. No release includes any of them yet. forge-cli 0.19.0 and earlier behave as described in [On 0.19.0 and earlier](#on-0-19-0-and-earlier), at the end of this section.
:::

An Iceberg expose names the catalog that owns its table in `binding.location.catalog`. The streaming sinks (Kafka Connect and Debezium Server), dbt's `catalogs.yml`, the AWS and Confluent modules, `fluid policy compile`, `fluid diff`, `fluid test` and `fluid validate` read the value through one table in forge-cli (`fluid_build/providers/_iceberg_catalog.py`), so they agree on which catalog holds the table. The Snowflake module reads it for the Iceberg prerequisites only: the EXTERNAL VOLUME and the Glue catalog integration follow the table. It still emits a `snowflake_database`, `snowflake_schema` and `snowflake_table` for the expose's `location.database`, `location.schema` and `location.table`, whatever the catalog.

### Example: stream into Lakekeeper

A Kafka Connect build streams Postgres changes into an Iceberg table that Lakekeeper catalogs, stored in S3:

```yaml
fluidVersion: 0.7.5
kind: DataProduct
id: bronze.orders_stream
name: Orders stream
domain: sales
metadata:
  layer: Bronze
  owner:
    team: data-platform
exposes:
  - exposeId: orders
    kind: table
    binding:
      platform: aws
      format: iceberg
      location:
        catalog: lakekeeper
        uri: http://lakekeeper:8181/catalog   # Lakekeeper's Iceberg REST endpoint
        warehouse: analytics                  # a Lakekeeper warehouse NAME, not s3://
        database: streaming                   # the Iceberg namespace
        table: orders
        bucket: acme-lake                     # the S3 bucket behind the warehouse
        region: eu-west-1
    contract:
      schema:
        - name: order_id
          type: integer
          required: true
        - name: amount_cents
          type: integer
builds:
  - id: stream_orders
    pattern: acquisition
    engine: kafka-connect
    outputs: [orders]
    properties:
      source:
        kind: postgres
        mode: incremental_append
        streams: [public.orders]
      sink:
        format: iceberg
      kafka-connect:
        streamingSink:
          autoCreate: true
          commitIntervalMs: 5000
```

The contract validates as written. `fluid validate` requires `uri` and `warehouse` for a REST catalog such as Lakekeeper; without `uri` it fails:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
Validation completed in 0.001s

Validation Errors:
==================
 1. iceberg sink (build 'stream_orders'): lakekeeper catalog requires binding.location.uri
```

These are the table and catalog keys of the sink config the Kafka Connect runner derives from it:

```json
{
  "iceberg.tables": "streaming.orders",
  "iceberg.catalog.type": "rest",
  "iceberg.catalog.warehouse": "analytics",
  "iceberg.catalog.client.region": "eu-west-1",
  "iceberg.catalog.uri": "http://lakekeeper:8181/catalog"
}
```

There is no `iceberg.catalog.io-impl` and no storage credential. forge-cli picks a FileIO only for a warehouse with an object-store scheme (`s3://`, `gs://`, `abfss://`); a catalog addressed by warehouse name returns the table's storage settings with its metadata. With `autoCreate: true`, the Apache Iceberg sink creates the table and its namespace itself, as it has since Iceberg 1.6.0 ([apache/iceberg#10186](https://github.com/apache/iceberg/pull/10186)). It ignores a refusal to create the namespace, so if the catalog principal the sink uses may not create namespaces, create the `streaming` namespace for it first.

On AWS, the module holds the bucket and nothing in Glue, because the table lives in Lakekeeper:

```bash
fluid generate iac contract.fluid.yaml --out infra
```

```text
Wrote OpenTofu module: infra/main.tf.json  (provider: aws, 1 resources)
```

The one resource is `aws_s3_bucket.bronze_orders_stream_acme_lake`. Without `bucket` the module would hold nothing, and `fluid generate iac` fails with `generate_iac_empty_module` (pass `--allow-empty` if that is what you want).

### How a value is read

- **Spelling.** Case, surrounding whitespace, and `-` against `_` are folded, so `Lakekeeper` is `lakekeeper` and `SNOWFLAKE_MANAGED` is `snowflake-managed`. Two spellings are aliases: `iceberg-rest` (or `iceberg_rest`) is `rest`, and `snowflake` is `snowflake-managed`.
- **No value.** An Iceberg expose with no `location.catalog` gets its platform's default: `glue` on `platform: aws` and `platform: confluent`, `snowflake-managed` on `platform: snowflake`, and `rest` on any other platform. *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* `platform: confluent` reads as `glue` because the Tableflow module publishes such a table to AWS Glue, so `fluid policy compile` and dbt read the catalog the table is in. With #707 and #709 alone it read as `rest`, and `fluid policy compile` dropped the expose's grants with a warning that the table was cataloged in `rest`; see [Other commands](#other-commands). On `platform: gcp` the default means two things: a streaming sink writes through a REST catalog, while dbt-bigquery and the GCP module create a BigLake table. *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* So a `platform: gcp` Iceberg expose that a streaming sink writes must name its catalog. Without one, `fluid validate` fails, and so does the Kafka Connect or embedded Debezium Server run before it creates anything. Set `catalog: bigquery`, or the REST kind your catalog is. #707 alone accepted it. An expose that no streaming sink writes may still leave the catalog out. The error, for a Kafka Connect build `stream_events` writing a GCP expose with no catalog:

  ```text
   1. iceberg sink (build 'stream_events'): the GCP Iceberg expose sets no binding.location.catalog, so it is read two ways: the sink would write through a REST catalog (the 'gcp' platform default) while dbt-bigquery and the GCP IaC, which read only binding.location.catalog, create a BigLake metastore table. Set binding.location.catalog: bigquery, or the REST kind your catalog is (e.g. rest, lakekeeper)
  ```

  Without `uri` and `warehouse`, the same build also draws the `rest` errors for them. When `sink.catalog`, `iceberg_catalog_overrides` or a hand-written sink config sets the catalog, the parentheses name it instead of the platform default. The check reads the catalog that reaches the worker, whether a `type` or a `catalog-impl` class selects it, and refuses every catalog but BigLake (`type=bigquery`, or `catalog-impl=org.apache.iceberg.gcp.bigquery.BigQueryMetastoreCatalog`). A Glue catalog is refused too, from `sink.catalog: glue` or from a hand-written `iceberg.catalog.catalog-impl: org.apache.iceberg.aws.glue.GlueCatalog`. For `sink.catalog: glue`:

  ```text
   1. iceberg sink (build 'stream_events'): the GCP Iceberg expose sets no binding.location.catalog, so it is read two ways: the sink would write through a glue catalog (sink.catalog 'glue') while dbt-bigquery and the GCP IaC, which read only binding.location.catalog, create a BigLake metastore table. Set binding.location.catalog: bigquery, or the REST kind your catalog is (e.g. rest, lakekeeper)
  ```

  Once the expose names its catalog, a hand-written sink config must select that same catalog (below).
- **`sink.catalog`.** A streaming build may set `properties.sink.catalog`, but it must name the expose's catalog, because dbt and the modules read only the expose. Spellings are compared after folding. Leave it unset and the sink uses the expose's catalog.
- **Any other value** is refused by `fluid validate` on every Iceberg expose, with the accepted spellings. A `platform: confluent` expose has its own rule, [below](#other-commands). `fluid apply` on AWS refuses the value too, as `unknown-iceberg-catalog`, because whether a Glue table exists depends on it. *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* So does the native AWS planner that [`fluid diff`](../cli/diff.md) runs; on #707 alone it planned the S3 buckets and no Glue table. A typo on an expose that also declares `governance.lakeFormation` draws only the two errors below, not a Lake Formation refusal that names the typo as a catalog.

```text
❌ Invalid FLUID contract (2 error(s)) (schema v0.7.5)
Validation completed in 0.001s

Validation Errors:
==================
 1. iceberg sink (build 'stream_orders'): unknown Iceberg catalog 'lakekeper' in binding.location.catalog; use one of: bigquery, dynamodb, glue, hadoop, hive, jdbc, lakekeeper, nessie, polaris, rest, snowflake-managed, unity, iceberg-rest, snowflake
 2. expose 'orders': binding.location.catalog 'lakekeper' is not a catalog kind FLUID knows. Use one of: bigquery, dynamodb, glue, hadoop, hive, jdbc, lakekeeper, nessie, polaris, rest, snowflake-managed, unity, iceberg-rest, snowflake. Each emitter guesses differently for an unknown value (the streaming sink writes over Iceberg REST, dbt and the Snowflake IaC treat it as Snowflake-managed), so the table would be written to two different catalogs.
```

A `sink.catalog` that names another catalog than the expose:

```text
 1. iceberg sink (build 'stream_orders'): sink.catalog 'glue' disagrees with the expose's catalog 'lakekeeper' (binding.location.catalog); the sink would write through glue while dbt and the IaC read lakekeeper. Set binding.location.catalog: glue and drop sink.catalog
```

*([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* A hand-written sink config or an override must select the expose's catalog too. A `sink_connector_config` or `iceberg_catalog_overrides` on a Kafka Connect build, or a `server.sink.config` on an embedded Debezium Server build, whose `type` or `catalog-impl` selects another catalog than the expose's is an error on every platform: the sink would write one catalog while dbt and the modules read the other. They are compared as the catalog the worker builds, so `type=rest` matches `rest`, `lakekeeper`, `polaris`, `unity` and `snowflake-managed`, and `glue` matches `type=glue` or `catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog`. #707 alone accepted such a config. A hand-written `iceberg.catalog.type: rest` for an AWS expose with no `location.catalog`, whose catalog is Glue:

```text
 1. iceberg sink (build 'stream_orders'): sink_connector_config sets iceberg.catalog.type='rest', so the sink would write through a REST catalog while dbt and the IaC read the expose's catalog 'glue' (the 'aws' platform default). Declare the catalog the sink writes to in binding.location.catalog; a REST endpoint that fronts Glue (Glue's Iceberg REST endpoint) is catalog: rest
```

Declare the catalog the sink writes to in `binding.location.catalog`. A REST endpoint that fronts Glue, such as Glue's Iceberg REST endpoint, is `catalog: rest`, with its `uri` and `warehouse`. On `platform: aws` the expose is then [a table in another catalog](#on-aws-a-table-in-another-catalog): the module creates its bucket and nothing in Glue, and Lake Formation governance on it is refused.

### What each kind produces

| `location.catalog` | Sink catalog selector | dbt `catalogs.yml` on Snowflake | Snowflake module | AWS module | A streaming sink needs |
|---|---|---|---|---|---|
| `glue` | `catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog` | `iceberg_rest` | Glue `CATALOG INTEGRATION` | the bucket, a Glue database and a Glue table | nothing (warns without `region`) |
| `rest` | `type=rest` | `iceberg_rest` | nothing; validate warns | the bucket only | `uri`, `warehouse` |
| `lakekeeper` | `type=rest` | `iceberg_rest` | nothing; validate warns | the bucket only | `uri`, `warehouse` |
| `polaris` | `type=rest` | `iceberg_rest` | nothing; validate warns | the bucket only | `uri`, `warehouse` |
| `unity` | `type=rest` | `iceberg_rest` | nothing; validate warns | the bucket only | `uri`, `warehouse` |
| `nessie` | `type=nessie` | `iceberg_rest` | nothing; validate warns | the bucket only | `uri`, `warehouse` |
| `bigquery` | `type=bigquery` | `iceberg_rest` | nothing; validate warns | the bucket only | `project` (warns with no `gs://` warehouse to derive, and on a Kafka Connect build) |
| `hive` | `type=hive` | left out, with a warning | nothing; validate errors | the bucket only | nothing |
| `jdbc` | `type=jdbc` | left out, with a warning | nothing; validate errors | the bucket only | `uri`, and `warehouse` or a `bucket` to derive it from |
| `hadoop` | `type=hadoop` | left out, with a warning | nothing; validate errors | the bucket only | `warehouse` |
| `dynamodb` | `catalog-impl=org.apache.iceberg.aws.dynamodb.DynamoDbCatalog` | left out, with a warning | nothing; validate errors | the bucket only | `warehouse`, or a `bucket` to derive it from |
| `snowflake-managed` | `type=rest` | `built_in` | `EXTERNAL VOLUME` | the bucket only | `uri`, `warehouse` |

How to read the columns:

- **Sink catalog selector.** Kafka Connect takes the key with the `iceberg.catalog.` prefix (`iceberg.catalog.type`, `iceberg.catalog.catalog-impl`), and Debezium Server with `debezium.sink.iceberg.`. The `type` values are catalog types Apache Iceberg defines. Iceberg has no `lakekeeper`, `polaris` or `unity` type, so those catalogs are reached over Iceberg REST, and no `dynamodb` type, so DynamoDB is selected by class. `type=bigquery` needs an Iceberg runtime of 1.10 or later. For `nessie` the sink uses Iceberg's Nessie client, which the stock Apache Iceberg Kafka Connect runtime does not bundle, so `fluid validate` warns on a `kafka-connect` build. *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* A `kafka-connect` build that sends `type=bigquery` draws a warning too, because the published Apache Iceberg Kafka Connect sink predates it:

  ```text
   1. iceberg sink (build 'stream_events'): the sink config sets iceberg.catalog.type=bigquery, which the published Apache Iceberg Kafka Connect sink (1.9.2 on Confluent Hub) cannot load: Iceberg's CatalogUtil gains the bigquery type in 1.10, so on that sink the connector fails at start. Run a sink built from Iceberg >= 1.10
  ```

  Both warnings follow the catalog that reaches the worker, selected by `type` or by a `catalog-impl` class (`org.apache.iceberg.nessie.NessieCatalog`, `org.apache.iceberg.gcp.bigquery.BigQueryMetastoreCatalog`), after `iceberg_catalog_overrides` and a hand-written `sink_connector_config` are merged in. A hand-written config that sets `iceberg.catalog.type: rest` for a `bigquery` or `nessie` expose draws neither, and is an error instead, because it selects another catalog than the expose's ([How a value is read](#how-a-value-is-read)).
- **dbt `catalogs.yml` on Snowflake** and **Snowflake module** apply to `platform: snowflake`. The **Snowflake module** column lists the Iceberg prerequisite the module creates; for every kind it also emits the database, schema and `snowflake_table` the binding's `location` names. Apart from `glue`, Snowflake reaches the `iceberg_rest` kinds through a catalog integration that authenticates with a secret. The module is credential-free, so it creates none, and `fluid validate` warns (an error under `--strict`). Snowflake has no catalog integration for `hive`, `jdbc`, `hadoop` or `dynamodb`, so an expose naming one fails `fluid validate`. The prerequisites each emitted object needs are in [Iceberg tables via dbt](../providers/snowflake.md#iceberg-tables-via-dbt-since-0-13-1).
- **AWS module** applies to `platform: aws`: the bucket is the one the binding names. See [On AWS](#on-aws-a-table-in-another-catalog).
- **A streaming sink needs** the listed `binding.location` keys when a Kafka Connect build, or a Debezium Server build in `embedded` mode, writes the expose. *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* A `dynamodb` or `jdbc` warehouse may instead derive from a `bucket` or come from an override, and a `bigquery` project from an override; see [What a DynamoDB, JDBC or BigQuery sink needs](#what-a-dynamodb-jdbc-or-bigquery-sink-needs). Debezium in `bring-your-own` or `managed` mode creates only the source connector, so these checks do not apply to it. The Kafka Connect runner and the embedded Debezium Server runner run the same checks before they create anything, so a contract `fluid validate` refuses also fails its run, for these builds:
  - *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* a build that declares `sink.format: iceberg`, whether the runner derives the sink config or pushes a hand-written one: `sink_connector_config` on Kafka Connect, `server.sink.config` on an embedded Debezium Server build whose `server.sink.type` is `iceberg` (the default). On #707 alone the runners checked only a config they derived, so a hand-written config that `fluid validate` refuses was still deployed;
  - an embedded Debezium Server build that derives its sink: `server.sink.type: iceberg` (the default) with no hand-written `server.sink.config`, or with `server.sink.iceberg_sink_enabled: true`.

  *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* In a contract with several builds, each of these two runners reads its properties from the build it runs, the build the checks read. They used to read the first build's.

### What a DynamoDB, JDBC or BigQuery sink needs

*([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* Apache Iceberg's `DynamoDbCatalog` and `JdbcCatalog` refuse to start without a warehouse, and its `BigQueryMetastoreCatalog` refuses to start without `gcp.bigquery.project-id`. A sink config forge-cli derives now carries them, and `fluid validate` and the run preflight refuse a build whose sink would start without them. With #707 and #709 alone forge-cli derived neither and checked for neither, so the connector failed when it started.

**DynamoDB and JDBC.** The warehouse is `location.warehouse`. Without one, forge-cli derives it from an explicit `location.bucket` on `platform: aws` (`s3://`) or `platform: gcp` (`gs://`): `<scheme>://<bucket>/<path>`, where `path` defaults to `<database>/<table>/`. A bucket on any other platform derives nothing, and the account-derived bucket a Glue table falls back to is never used, because no module creates it for a table in another catalog. A DynamoDB expose that a Kafka Connect build writes:

```yaml
exposes:
  - exposeId: orders
    kind: table
    binding:
      platform: aws
      format: iceberg
      location:
        catalog: dynamodb
        bucket: acme-lake        # the warehouse derives from it
        database: streaming
        table: orders
        region: eu-west-1
```

The table and catalog keys of the sink config the Kafka Connect runner derives from it:

```json
{
  "iceberg.tables": "streaming.orders",
  "iceberg.catalog.catalog-impl": "org.apache.iceberg.aws.dynamodb.DynamoDbCatalog",
  "iceberg.catalog.warehouse": "s3://acme-lake/streaming/orders/",
  "iceberg.catalog.io-impl": "org.apache.iceberg.aws.s3.S3FileIO",
  "iceberg.catalog.client.region": "eu-west-1"
}
```

The sink's own `warehouse` property counts too: `iceberg.catalog.warehouse` in `iceberg_catalog_overrides` or `sink_connector_config` on Kafka Connect, `warehouse` in `server.sink.config` on embedded Debezium Server. With no `location.warehouse`, no bucket to derive one from and no override, `fluid validate` fails, and so does the run, before it creates anything:

```text
 1. iceberg sink (build 'stream_orders'): dynamodb catalog requires binding.location.warehouse (an object-store location), or a binding.location.bucket on platform aws or gcp to derive it from, or the sink's warehouse property in an override; the dynamodb catalog refuses to start without a warehouse
```

`jdbc` needs `location.uri` as well. A `location.warehouse` of only whitespace counts as unset.

**BigQuery.** A `catalog: bigquery` expose maps to the catalog's own properties:

| `binding.location` | Derived sink config |
|---|---|
| `project` | `gcp.bigquery.project-id`. Required: without it, or with only whitespace, `fluid validate` and the run refuse the build, unless an override sets that property |
| `region` | `gcp.bigquery.location`. The config sets no `client.region` for this catalog |
| a `gs://` `warehouse`, else `bucket` and `path` | `warehouse`: the `gs://` storage dbt-bigquery and the GCP module use, `gs://<bucket>` plus `path` when it is set |

The Kafka Connect runner passes them with the `iceberg.catalog.` prefix, and the embedded Debezium Server runner with `debezium.sink.iceberg.`. [Iceberg on BigQuery via dbt](../providers/gcp.md#iceberg-on-bigquery-via-dbt-since-0-14-0) shows the derived config for its example binding. Without `project`:

```text
 1. iceberg sink (build 'stream_events'): bigquery catalog requires binding.location.project (the sink's gcp.bigquery.project-id), or that property in an override; the bigquery catalog refuses to start without it
```

A `warehouse` with another scheme, or no `gs://` warehouse and no bucket, derives no warehouse: the config sets none, and `fluid validate` warns without refusing. On Kafka Connect, table auto-create then fails: with `iceberg.tables.auto-create-enabled` the sink calls `createNamespace` for each table it creates, which `BigQueryMetastoreCatalog` refuses without a warehouse, even in a dataset that exists. Tables that exist need no warehouse. Embedded Debezium Server does not boot without `debezium.sink.iceberg.warehouse`, which has no default. On `platform: gcp` the [Iceberg prerequisite checks](../cli/validate.md#iceberg-prerequisite-checks-since-0-14-0) already require a `bucket` or a `gs://` warehouse.

**A bucket written as a `{{ env.* }}` template.** `fluid validate` reads such a bucket as written. When a variable it names, such as `LAKE_ENV` in `acme-{{ env.LAKE_ENV }}-lake`, is unset or empty where validate runs, the warehouse cannot be derived there, and validate warns and names the variable instead of asking for a bucket:

```text
 1. iceberg sink (build 'stream_orders'): the dynamodb catalog's warehouse derives from binding.location.bucket 'acme-{{ env.LAKE_ENV }}-lake', and LAKE_ENV is unset or empty here, so it cannot be derived at validate time. Set it where the sink runs: the runner refuses the build when the bucket does not resolve there, because the dynamodb catalog refuses to start without a warehouse
```

The run preflight checks the variable again where the sink config is derived. When it is unset or empty there, the preflight refuses the build instead of pushing a warehouse in a bucket the contract does not name, such as `acme--lake`. That includes a run from a plan, whose embedded contract it reads as written:

```text
iceberg sink preflight failed: iceberg sink (build 'stream_orders'): the dynamodb catalog's warehouse derives from binding.location.bucket 'acme-{{ env.LAKE_ENV }}-lake', and LAKE_ENV is unset or empty in the runner's environment, so the bucket does not resolve: the sink would get a warehouse in a bucket the contract does not name, or none, and the dynamodb catalog refuses to start without a warehouse. Set it here, or set binding.location.warehouse
```

The preflight refuses a DynamoDB or JDBC sink, a BigQuery sink on embedded Debezium Server, and a BigQuery sink on Kafka Connect with auto-create on (`streamingSink.autoCreate: true`, or `iceberg.tables.auto-create-enabled` in an override). A Kafka Connect BigQuery sink reads the warehouse only to create tables, so without auto-create the run warns and pushes no warehouse. A warehouse an override sets is kept, and the bucket's variables are not checked then. They are not checked for a hand-written sink config forge-cli does not derive either.

### Which exposes a streaming sink writes

*([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* A Kafka Connect or embedded Debezium Server build whose Iceberg sink config forge-cli derives writes the Iceberg exposes its `outputs` name. An Iceberg expose here is one with an Iceberg format whose `binding.platform` is not `confluent`: a Tableflow expose is published by its own module. `fluid validate`, the run preflight and both runners resolve the exposes the same way, so they name the same tables. On 0.19.0 and earlier, and with #707 and #709 alone, a derived sink wrote the contract's first Iceberg expose, whatever the build's `outputs` named.

Two Kafka Connect builds, one per expose (each expose's `contract` and each build's `source` are left out):

```yaml
exposes:
  - exposeId: orders
    kind: table
    binding:
      platform: aws
      format: iceberg
      location: {bucket: acme-lake, database: sales, table: orders, region: eu-west-1}
  - exposeId: refunds
    kind: table
    binding:
      platform: aws
      format: iceberg
      location: {bucket: acme-lake, database: sales, table: refunds, region: eu-west-1}
builds:
  - id: stream_orders
    pattern: acquisition
    engine: kafka-connect
    outputs: [orders]
    properties:
      sink: {format: iceberg}
  - id: stream_refunds
    pattern: acquisition
    engine: kafka-connect
    outputs: [refunds]
    properties:
      sink: {format: iceberg}
```

`stream_orders` pushes `iceberg.tables=sales.orders` and `stream_refunds` pushes `iceberg.tables=sales.refunds`. With #707 and #709 alone, `stream_refunds` pushed `iceberg.tables=sales.orders` too, and `fluid validate`, the preflight and the run all passed.

- **Kafka Connect** writes one expose, because the derived config carries one `iceberg.tables` entry. The build's `outputs` must name exactly one Iceberg expose; a build with no `outputs` is accepted only when the contract has exactly one. Otherwise `fluid validate` and the run preflight refuse it. With `outputs: [orders, refunds]` on `stream_refunds`:

  ```text
   1. iceberg sink (build 'stream_refunds'): its outputs ['orders', 'refunds'] name 2 of the Iceberg sink exposes ['orders (sales.orders)', 'refunds (sales.refunds)']; a derived Kafka Connect sink writes one expose (one iceberg.tables entry). List exactly one of them in the build's outputs, split the build into one build per expose, or hand-write the sink config (properties.kafka-connect.sink_connector_config)
  ```

  Outputs that name no Iceberg expose are refused the same way. With #707 and #709 alone they drew only a warning that the join is implicit.
- **Embedded Debezium Server** writes every captured table under one `table-namespace`, through one catalog. It writes the Iceberg exposes its `outputs` name, or all of the contract's with no `outputs`, and is refused when:
  - its outputs name none of them;
  - they sit in more than one `binding.location.database`;
  - they resolve to different catalogs. The error names the settings that differ, such as `catalog`, `uri` or `warehouse`. A Glue warehouse is a per-table prefix, so it is not compared, and the sink takes the first expose's;
  - they are DynamoDB or JDBC exposes whose warehouses, derived from `location.bucket`, differ. Such a catalog creates every missing table under the one warehouse the sink is given, and each derived warehouse is that expose's own table prefix. Set one `location.warehouse` on those exposes, or split the build.

  One embedded Debezium Server build over both exposes above (its `source` left out), with `refunds` moved to `database: finance`:

  ```yaml
  - id: cdc_sales
    pattern: acquisition
    engine: debezium
    outputs: [orders, refunds]
    properties:
      sink: {format: iceberg}
      debezium:
        deployment: {mode: embedded}
  ```

  `fluid validate` refuses it:

  ```text
   1. iceberg sink (build 'cdc_sales'): a derived Debezium Server sink writes every captured table under one table-namespace, but the exposes its outputs ['orders', 'refunds'] name, ['orders (sales.orders)', 'refunds (finance.refunds)'], sit in the databases ['finance', 'sales']. Give them one binding.location.database, split the build into one build per database, or hand-write the sink config (properties.debezium.server.sink.config)
  ```

- **A config that names its own tables.** A hand-written `sink_connector_config` or `server.sink.config` that forge-cli does not derive from, and an override that sets `iceberg.tables` (Kafka Connect) or `table-namespace` (Debezium Server), behave as before: the config is checked against the first Iceberg expose, and outputs that name no Iceberg expose draw the warning that the join is implicit.

### Kafka Connect: `catalog-impl` or `type`, never both

Apache Iceberg refuses a catalog configured with both `type` and `catalog-impl`. On 0.19.0 and earlier the Kafka Connect sink config for a Glue table carried both, and the sink failed at startup with:

```text
java.lang.IllegalArgumentException: Cannot create catalog iceberg, both type and catalog-impl are set
```

The derived config now carries one selector, as the Debezium Server config already did. The table and catalog keys for a Glue expose (`bucket: acme-lake`, `path: bronze/orders`, `database: bronze`, `table: orders`, `region: eu-west-1`, no `location.catalog`):

```json
{
  "iceberg.tables": "bronze.orders",
  "iceberg.catalog.catalog-impl": "org.apache.iceberg.aws.glue.GlueCatalog",
  "iceberg.catalog.warehouse": "s3://acme-lake/bronze/orders",
  "iceberg.catalog.io-impl": "org.apache.iceberg.aws.s3.S3FileIO",
  "iceberg.catalog.client.region": "eu-west-1"
}
```

`iceberg_catalog_overrides` and a hand-written `sink_connector_config` are merged over the derived config, so an override that sets the other selector key would bring the failure back. `fluid validate` refuses it:

```text
 1. iceberg sink (build 'stream_orders'): the sink config would carry both iceberg.catalog.type (from iceberg_catalog_overrides) and iceberg.catalog.catalog-impl (from the derived glue catalog config); Iceberg's CatalogUtil refuses a catalog with both type and catalog-impl set, so the sink never starts. Keep one, and change catalogs with binding.location.catalog rather than an override
```

To move a sink to another catalog, change `binding.location.catalog`, not the selector keys.

### On AWS: a table in another catalog

An Iceberg expose on `platform: aws` whose `location.catalog` is anything other than `glue`:

- **Gets its S3 bucket and nothing in Glue.** The module creates no Glue database, Glue table or Lake Formation resource for it, and does not import a Glue table of the same name into state. `fluid policy compile` writes the bucket entry with no `glue.table` entry. An expose with no `location.catalog`, or `catalog: glue`, emits exactly what it did before.
- **Is not looked up in Glue.** `fluid diff` reports it `not_checked` (`table lives in Iceberg catalog lakekeeper; Glue is not inspected`), and `fluid test` reports `Table not checked` instead of failing on a Glue table that does not exist.
- **Cannot carry Lake Formation governance.** `governance.lakeFormation`, `policy.authz.columnRestrictions` and `policy.authz.rowFilters` are refused by catalog name at `fluid validate` and at apply (`lake-formation-needs-glue-catalog`, `column-restriction-unenforceable`, `row-filter-unenforceable`), instead of being written against a Glue table that does not exist:

  ```text
   1. exposes[orders] declares governance.lakeFormation, but its Iceberg table lives in the 'lakekeeper' catalog (location.catalog), not in AWS Glue. Lake Formation governs only Glue Data Catalog tables, so its grants, LF-tags and filters would have no table to name and would not be applied. Govern access in the lakekeeper catalog itself and remove governance.lakeFormation from this binding. Remove location.catalog (or set it to 'glue') to keep the table in the Glue catalog under Lake Formation.
  ```

- **Has `accessPolicy.grants` reported as unenforced**, with a warning that points at the catalog rather than at Lake Formation grants:

  ```text
   1. accessPolicy.grants are not enforced on aws binding(s) orders (lakekeeper): their Iceberg tables live in a catalog other than Glue, and the AWS emitter writes access only as Lake Formation grants on a Glue table. Grant access in that catalog.
  ```

Grant access in the catalog itself; forge-cli writes no grant there.

### Upgrading an AWS contract that names another catalog

0.19.0 and earlier created a Glue database and table for every AWS Iceberg expose that names `location.database` and `location.table`, whatever its `location.catalog`. After the upgrade, the OpenTofu state of such a contract still holds them while the module no longer declares them, so the next `tofu plan` would destroy them, and destroying a Glue database deletes every table in it, including tables created outside FLUID. `fluid apply` stops before it plans (the `remediation` list, which repeats the commands, is abridged):

```text
❌ iceberg_catalog_move_blocked  [ERR_ICEBERG_CATALOG_MOVE_BLOCKED]
  kind: iceberg-catalog-move
  error: iceberg catalog move blocked — this contract's OpenTofu state holds 2 Glue catalog resource(s) for Iceberg table(s) that now live in another catalog:

  exposes[orders]: location.catalog lakekeeper

  aws_glue_catalog_database.bronze_orders_stream_streaming
  aws_glue_catalog_table.bronze_orders_stream_streaming_orders

forge-cli no longer creates a Glue table for an Iceberg table in a non-Glue catalog (it was a second claim on the table's name, without its metadata), so applying now would plan to DESTROY these resources, and destroying a Glue database deletes every table in it, including tables created outside FLUID.

Drop each from this contract's state, then re-run apply:

  tofu -chdir=.fluid/iac/aws/bronze_orders_stream state rm aws_glue_catalog_database.bronze_orders_stream_streaming
  tofu -chdir=.fluid/iac/aws/bronze_orders_stream state rm aws_glue_catalog_table.bronze_orders_stream_streaming_orders

`tofu state rm` touches ZERO bytes of infrastructure: the resources stay in AWS, and only this contract's claim on them is released. Delete a Glue table by hand once nothing reads it, and a Glue database only once it holds nothing else. If the table belongs in Glue, remove location.catalog (or set it to 'glue') instead.
  remediation: [...]
```

*([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* The `exposes[orders]` line keeps its expose id, and each printed `tofu state rm` command stays on one line, so a copied line runs with its address. On #707 alone the line printed as `exposes: location.catalog lakekeeper`, and a long command could wrap onto a second line.

1. Run the `tofu state rm` commands it prints, one per Glue resource, in the form `tofu -chdir=<module directory> state rm <address>` (each argument shell-quoted when it needs to be). For the example contract:

   ```bash
   tofu -chdir=.fluid/iac/aws/bronze_orders_stream state rm aws_glue_catalog_database.bronze_orders_stream_streaming
   tofu -chdir=.fluid/iac/aws/bronze_orders_stream state rm aws_glue_catalog_table.bronze_orders_stream_streaming_orders
   ```

   `tofu state rm` changes nothing in AWS. It releases this contract's claim on the resources, which stay where they are.
2. Run `fluid apply` again.
3. Delete the Glue table by hand once nothing reads it, and the Glue database only once it holds nothing else.

If the table belongs in Glue after all, remove `location.catalog` (or set it to `glue`) instead. There is no flag that skips the guard. Before it raises, the apply logs a structured `iceberg_catalog_move_blocked` event with the addresses, the exposes and the commands. On AWS the guard concerns an Iceberg expose that names a `location.database` and a catalog other than Glue. The same guard covers [Snowflake](#upgrading-a-snowflake-contract-that-names-another-catalog).

*([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* A moved expose's Glue resources are flagged when its own Glue table is in state, which shows that an earlier release created them for this expose. A Glue database that only a since-removed expose created, a parquet expose say, is not a catalog move: the plan's destroy of it is left to the [OpenTofu data-loss gate](../cli/apply.md#opentofu-data-loss-gate). On #707 alone the guard flagged such a database, and the apply could not get past it. An expose that names a `location.database` and no `location.table` has no Glue table to show this: an earlier release created only its Glue database, so that database is flagged when state holds it and the module no longer declares it.

*([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* When the guard cannot read the state, or its check fails, the apply continues without it and logs an `iceberg_catalog_move_probe_skipped` WARNING that names the reason and the exposes, for example:

```text
{"time": "...", "level": "WARNING", "name": "fluid.cli", "message": "iceberg_catalog_move_probe_skipped", "provider": "aws", "reason": "the state could not be read: `tofu state pull` failed: Error: Failed to load state: AccessDenied: Access Denied", "exposes": [{"expose": "orders", "catalog": "lakekeeper"}], "remedy": "if the plan below destroys resources an older forge-cli created for these exposes, do NOT pass --allow-data-loss: release them with `tofu state rm` and re-run apply"}
```

The [OpenTofu data-loss gate](../cli/apply.md#opentofu-data-loss-gate) still stops a plan that would destroy the resources. Release them with `tofu state rm` as above rather than passing `--allow-data-loss`. On #707 alone a failed check was logged at debug level, and a state that could not be read was not reported. The same pattern guards [packaging ownership transitions](../cli/generate-iac.md#ownership-transitions).

### Upgrading a Snowflake contract that names another catalog

*([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), unreleased)* 0.19.0 and earlier created a Snowflake EXTERNAL VOLUME for a `platform: snowflake` Iceberg expose whose `location.catalog` is `lakekeeper` or `bigquery`, or is spelled `iceberg-rest`, and dbt wrote the table onto it as a Snowflake-managed table. The module now creates no volume for those catalogs, since Snowflake does not manage them. The guard covers `hive`, `jdbc`, `hadoop` and `dynamodb` too, which also got a volume and which `fluid validate` now refuses. A volume the expose names itself, in `binding.icebergConfig.properties.external_volume`, is not concerned: no release created it. When the contract's state still holds the volume, `fluid apply` stops before it plans instead of dropping it (the `remediation` list is abridged):

```text
❌ iceberg_catalog_move_blocked  [ERR_ICEBERG_CATALOG_MOVE_BLOCKED]
  kind: iceberg-catalog-move
  error: iceberg catalog move blocked — this contract's OpenTofu state holds 1 Snowflake EXTERNAL VOLUME(s) that this contract's configuration no longer declares:

  snowflake_external_volume.sales_orders_lake_vol_FLUID_SALES_ORDERS_LAKE_VOL

The volume is named for the contract, not for an expose, so the state does not say which expose it was created for. Possible causes: this contract was applied by a forge-cli release that gave an Iceberg table in a catalog Snowflake does not manage an EXTERNAL VOLUME (this release gives it none, and dbt writes it as an externally cataloged table); or this change removed a Snowflake-managed Iceberg expose, or moved one to another catalog. Applying now would plan to DROP the volume, and any Snowflake-managed Iceberg table written onto it still uses it.

Iceberg exposes whose catalog earlier releases gave an EXTERNAL VOLUME:

  exposes[orders_iceberg]: location.catalog lakekeeper

Drop each from this contract's state, then re-run apply:

  tofu -chdir=.fluid/iac/snowflake/sales_orders_lake state rm snowflake_external_volume.sales_orders_lake_vol_FLUID_SALES_ORDERS_LAKE_VOL

`tofu state rm` touches ZERO bytes of infrastructure: the resources stay in Snowflake, and only this contract's claim on them is released. Drop a volume by hand (DROP EXTERNAL VOLUME) only once no Iceberg table uses it. If an Iceberg table belongs in Snowflake's own catalog, remove its location.catalog (or set it to 'snowflake') instead.
  remediation: [...]
```

*([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* The message names both possible causes because the state cannot tell them apart: an earlier release that gave the volume to an expose in a catalog Snowflake does not manage, or a Snowflake-managed Iceberg expose that this change removed or moved to another catalog. The guard blocks the same applies as before. With #707 and #709 alone the message said forge-cli no longer creates such a volume, and listed the moved exposes as the tables it was held for.

1. Run the printed command, `tofu -chdir=.fluid/iac/snowflake/<safe-id> state rm snowflake_external_volume.<name>`. It changes nothing in Snowflake.
2. Run `fluid apply` again.
3. Drop the volume by hand (`DROP EXTERNAL VOLUME`) only once no Iceberg table uses it. A Snowflake-managed table written onto it still does.

If the table belongs in Snowflake's own catalog, remove `location.catalog` (or set it to `snowflake`) instead. The volume is named per contract (`FLUID_<PRODUCT_ID>_VOL`), not per expose, so the Snowflake guard has no per-expose resource to check: the volume is flagged when it is in state, an expose moved, and the module no longer declares it. The guard finds the volume by the name derived from the contract id, not from the expose's `location`, so it also stops an upgrade whose edit changed `location.warehouse` to the catalog's warehouse name (`warehouse: analytics`) or removed `location.iam_role_arn`.

### Other commands

- **dbt-bigquery.** An expose that names a catalog other than `bigquery` is left out of `catalogs.yml`, with a warning, instead of becoming a BigLake table. On `platform: gcp`, `fluid validate` accepts such a catalog's warehouse name and refuses a warehouse in another object store (`s3://`, `abfss://`).
- **Confluent Tableflow.** A `platform: confluent` expose publishes only to AWS Glue. A `location.catalog` other than `glue` is a `fluid validate` error, and the module creates no catalog integration for it. *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* With no `location.catalog` the expose reads as `glue`, so dbt-snowflake's `catalogs.yml` writes `catalog_linked_database_type: glue` for it.
- **`fluid policy compile`.** A Snowflake-managed Iceberg table compiles to Snowflake grants. A table in another catalog gets no Glue grant, and a warning to enforce access in that catalog. *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* A Confluent Tableflow expose compiles to its S3 bucket and the Glue table Tableflow publishes. The Tableflow module names that table for the topic (`location.topic`, else `location.table`, else the expose id) and publishes it into `location.database`, or, with none, into the database Tableflow names after the Kafka cluster id. For this binding, which sets no `database` (`fluid validate` warns about that):

  ```yaml
  binding:
    platform: confluent
    format: iceberg
    location:
      environment_id: env-abc123
      kafka_cluster_id: lkc-xyz789
      topic: orders
      bucket: acme-tableflow
      region: eu-west-1
      confluent_role_arn: arn:aws:iam::123456789012:role/tableflow
  ```

  a `read` grant compiles to an `s3.bucket` binding on `acme-tableflow` and this Glue binding:

  ```json
  {
    "provider": "aws",
    "resource_type": "glue.table",
    "resource_id": "lkc-xyz789.orders",
    "database": "lkc-xyz789",
    "table": "orders",
    "region": "eu-west-1",
    "principal": "group:analysts@acme.com",
    "actions": ["glue:GetTable", "glue:GetDatabase", "athena:StartQueryExecution", "athena:GetQueryResults"]
  }
  ```

  With neither `database` nor `kafka_cluster_id`, the database is unknown: the expose gets the bucket binding only, and a warning. [`fluid policy compile`](../cli/policy-compile.md#warnings) prints each warning.
- **`fluid validate`.** A crash inside the Iceberg sink, Confluent or Iceberg prerequisite check is an error ("the contract was NOT checked for ..."), not a note printed only with `--verbose`. Two `catalog: snowflake` exposes that derive one EXTERNAL VOLUME on different storage are refused at validate instead of failing `fluid apply` mid-emit. The full list is in [Iceberg catalog checks](../cli/validate.md#iceberg-catalog-checks).

### On 0.19.0 and earlier

Each emitter classified `location.catalog` by hand, and they disagreed:

- `catalog: lakekeeper` streamed over REST, while dbt's `catalogs.yml` wrote a Snowflake-managed (`built_in`) table and the AWS module created a Glue database and table of the same name.
- The streaming-sink check required `uri` and `warehouse` only for the literal `rest`.
- On Snowflake, `hive`, `jdbc`, `hadoop` and `dynamodb` became Snowflake-managed tables, and `fluid validate` asked a `lakekeeper` expose for an `s3://` or `gs://` warehouse.
- A Confluent binding published to Glue whatever catalog it named, and dbt-bigquery made a BigLake table for any catalog.
- A Kafka Connect sink on Glue failed at startup, as shown above.
- An unknown value fell back differently in each emitter, so a typo split one table across catalogs.
- `fluid policy compile` compiled every Iceberg expose off GCP to AWS S3 and Glue grants, whatever its platform.
- A Kafka Connect or Debezium Server sink config forge-cli derived wrote the contract's first Iceberg expose, whatever the build's `outputs` named.
- A derived DynamoDB, JDBC or BigQuery sink config carried no warehouse unless `location.warehouse` set one, and a BigQuery one no `gcp.bigquery.project-id`.
- A crash inside an Iceberg or Confluent check of `fluid validate` was printed only with `--verbose`, and the contract passed unchecked.
- Neither streaming runner checked its Iceberg sink before it created anything.

## Masking at landing

`exposes[].policy.privacy.masking` is applied by the DuckDB runner inside the same `COPY` that lands the data, after the quality gates have judged the source values. The local file, the S3 object, the file a BigQuery load job reads, and the dead-letter file all hold the treated values.

```yaml
exposes:
  - exposeId: orders_raw
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: out/orders.parquet
    policy:
      privacy:
        masking:
          - column: customer_email
            strategy: hash
          - column: amount
            strategy: mask
            params: { keepLast: 2 }
    contract:
      schema: []
```

Set the salt in the build's environment, never in the contract:

```bash
export FLUID_PII_HASH_SECRET="$(openssl rand -hex 32)"
fluid apply contract.fluid.yaml --mode amend-and-build --build-id ingest_orders --yes
```

```text
customer_email   6c70c366520af6f72a1bad762aa6ee64689255873a371818e8c858271d3548c8
amount           **.9
```

| Strategy | What lands | Parameters and secret |
|---|---|---|
| `hash` | Lowercase hex SHA-256 of the salt followed by the value. The same value hashes the same, so joins across products that share the salt still work. | Salt from the variable `params.saltEnv` names, default `FLUID_PII_HASH_SECRET`. At least 16 bytes. |
| `mask` | Every character replaced by `*` except the first `keepFirst` (default 0) and last `keepLast` (default 4). Length is kept. A value no longer than `keepFirst + keepLast` is masked entirely. | `keepFirst`, `keepLast`. No secret. |
| `tokenize` | 32 hex characters of an HMAC-SHA256 of the value. The same token the `tokenize_pii` pre-land hook produces. | Key from the variable `params.keyEnv` names, default `FLUID_PII_TOKENIZATION_KEY`. At least 32 bytes. |
| `encrypt` | `aesgcm:v1:` followed by AES-GCM output. Reversible with the key, not deterministic, so joins on it do not work. | Key from the variable `params.keyEnv` names, default `FLUID_PII_ENCRYPTION_SECRET_KEY`: base64 of 16, 24 or 32 bytes (`openssl rand -base64 32`). |

The build refuses to land rather than land a column untreated. These are all refused:

- `k_anonymity`, which is a property of a whole table and not of one value
- a parameter the strategy does not take, and a literal `salt`, `key` or `secret` parameter
- a secret variable that is unset or too short
- a masked column that the expose declares with a type other than a string type, because a treated column always lands as a string

```text
duckdb.refused masking: masking hash on column 'customer_email' needs a salt in the environment
variable FLUID_PII_HASH_SECRET, which is unset or empty. Refusing to land the column untreated ...
```

If the expose declares its columns, write each masked column as `varchar`. The refusal message above offers `string`, but the schema-drift check compares the type names DuckDB reports for the source, so a column declared `string` fails the run with `source schema drift detected` (measured on 0.18.1, with and without `schemaPolicy` set). See [Schema evolution](#schema-evolution).

Masking is the DuckDB runner's. A build on another engine, or a Python `hybrid-reference` build, does not apply it. A build with inline SQL (`properties.sql`) whose expose declares masking is refused with `MaskingNotAppliedError` rather than landed in cleartext; see [Production troubleshooting](./production-troubleshooting.md#builds-and-masking). The strategies and the `policy.privacy.masking` schema are described in [Governance policy](../concepts/governance-policy.md#masking-policy-privacy-masking).

`fluid verify` checks the landed result whatever wrote it. It reads every non-null value of each masked column and fails the column if a value lacks its strategy's shape. It does this for local files, for S3 with Glue through Athena, and for BigQuery:

```text
🔍 Dimension 2: Masking
   ✅ PASS - every non-null value has its strategy's shape: customer_email (hash), amount (mask)
```

Platform-native dynamic masking, such as a BigQuery policy tag that masks at query time, is a different mechanism and is not emitted from this block. See [Governance](./governance.md).

## Delivery guarantees

```yaml
delivery:
  guarantee: at_least_once     # at_most_once | at_least_once | exactly_once
  dlq:
    enabled: true
    maxRecordsBeforeAbort: 1000
    alertOn: [quality_gate_failed, destination_write_failed]
```

`alertOn` accepts `pii_classification_failed`, `schema_violation`, `destination_write_failed` and `quality_gate_failed`.

As of 0.18.1, the `duckdb` engine does not read `delivery`: a build with `guarantee: exactly_once` runs, because capability negotiation reads `builds[].capabilities` (see [Asking for a capability](#asking-for-a-capability)). The `delivery.dlq` keys are read by other engines and by `fluid verify`, not by the DuckDB runner (see [Quality gates and the dead-letter queue](#quality-gates-and-the-dead-letter-queue)).

## Schema evolution

What happens when the source's columns change is decided by the **expose**, not by a key under the build:

```yaml
exposes:
  - exposeId: orders_raw
    kind: table
    binding: { ... }
    contract:
      schemaPolicy: strict      # strict | discover_and_freeze | evolve_safe | evolve_all
      schema:
        - { name: order_id, type: bigint }
        - { name: customer_email, type: varchar }
```

At the start of a run, the engine compares the columns it reads with the expose's declared `contract.schema`. The first expose in `exposes` is the one compared. `builds[].outputs` decides which expose the DuckDB build writes, but as of 0.18.1 it does not change which expose the drift check reads: a second build whose expose is not `exposes[0]` is compared against `exposes[0]`, so when its source columns differ from the schema declared on `exposes[0]` and `exposes[0]` sets `schemaPolicy: discover_and_freeze`, that build fails with `source schema drift detected`. With an empty `schema: []` there is nothing to compare and the check does not run. When `schemaPolicy` is not set, the check runs as `evolve_safe`, which is not the schema's own default of `strict`.

| Change in the source | `strict` | `discover_and_freeze` | `evolve_safe` | `evolve_all` |
|---|---|---|---|---|
| Column added | Fails | Fails | Included | Included |
| Column removed | Fails | Fails | Warns | Dropped |
| Numeric type widened | Fails | Fails | Accepted | Accepted |
| Numeric type narrowed | Fails | Fails | Fails | Cast |

A failure raises `SchemaDriftError`, before anything is written:

```text
✗ source schema drift detected
why  baseline=sha256:ef7417...; current=sha256:c41252...; created_at/removed→fail
fix  Review contract.exposes[].contract.schemaPolicy; if policy=evolve_safe, this is expected.
If strict/discover_and_freeze, update the contract or fix the source.
```

Decisions are deterministic: the same two column sets always give the same outcome.

::: warning `properties.schemaEvolution` is not enforced
`properties.schemaEvolution.policy`, `onAddedColumn`, `onRemovedColumn` and `onTypeChange` validate, but as of 0.18.1 no runner reads them. A build with `schemaEvolution.policy: strict` and a source that gained a column runs and lands the new column. Set `schemaPolicy` on the expose instead.
:::

## Quality gates and the dead-letter queue

```yaml
quality:
  gates:
    - rule: not_null
      columns: [order_id]
      severity: error
    - rule: range
      column: amount
      min: 0
      max: 1000000
      severity: error
  onError: route_to_dlq
```

On the `duckdb` engine, the gates run inside the `COPY`. A row that passes every gate lands; a row that fails any gate does not, and goes to the dead-letter queue instead. The run still succeeds. With one blank `order_id` in the CSV:

```text
duckdb.dlq stream=orders bad_records=1 on_error=route_to_dlq
```

```json
{"reason": "not_null gate failed on column 'order_id'", "record": {"amount": 5.0, "created_at": "2026-10-02", "customer_email": "grace@example.com", "order_id": null}, "run_id": "<run-id>", "stream": "orders", "timestamp": "2026-10-05T00:58:29Z", "hook_trace": []}
```

The file is `.fluid/dlq/<run-id>/<stream>.ndjson`. Masked columns are masked in it too.

What the DuckDB runner evaluates, as of 0.18.1:

- **Rules:** `not_null` (with `columns`), `range` (`column`, `min`, `max`) and `regex` (`column`, `pattern`). The schema also accepts `unique`, `row_count_anomaly` and `freshness`; the DuckDB runner skips those without a message.
- **`severity`** is required by the schema and does not change what the DuckDB runner does with a failing row.
- **`onError`** takes `route_to_dlq`, `abort_run` or `best_effort`, and `fail` is rejected by the schema. The DuckDB runner behaves the same for all three: bad rows go to the dead-letter queue and the run succeeds. A run is only promoted to failed on the value `fail`, which `fluid validate` does not accept.
- **`delivery.dlq.maxRecordsBeforeAbort` and `delivery.dlq.sink`** are not read. The queue is always `.fluid/dlq/` and its size is not capped. A contract with `maxRecordsBeforeAbort: 0` and one bad row runs to completion.
- **`quality.anomalies`** (`record_count_drop` and the other signals) are accepted by the schema and are not read.

`fluid verify` prints three probes for each acquisition build after the run: `run_state_succeeded`, `records_landed` and `no_unexpected_dlq_overflow`. As of 0.18.1 the DuckDB run record has no `dlq_records` field, so the third probe always reports `dlq_records=0`, whatever went to the queue.

### Pre-land hooks

`preLand` is a list of hook names: `dlp_scan`, `tokenize_pii`, `quality_gate` and `emit_lineage_input`.

```yaml
      preLand: [dlp_scan, quality_gate]
```

On the `duckdb` engine, `quality_gate` selects the gate logic above and needs no hook of its own, and `emit_lineage_input` is skipped. `dlp_scan` and `tokenize_pii` run after the file has landed, on a sample of up to 1000 rows. They report which columns look like PII (in the run record's `facets.pii_findings`) and do not change what was written. To change landed values, use [masking at landing](#masking-at-landing).

## Cost tracking and budget gates

```yaml
cost:
  budget:
    monthly: { rows: 1000000 }     # rows, bytes ("50GB") and computeMinutes
    onExceed: abort                # warn | abort
  chargeback:
    team: ingestion
```

As of 0.18.1, no engine enforces `cost.budget` while it runs. A build with `monthly.rows: 1`, `onExceed: abort` and a three-row source runs and lands all three rows. The only place the budget is read is the `cost_within_budget` probe of `fluid verify`, which compares the run's row count with `monthly.rows` and ignores `bytes` and `computeMinutes`:

```text
❌ cost_within_budget: records_used=3.0 row_cap=1
```

A failed probe counts as a mismatch. `fluid verify --strict` downgrades it to a warning, and `--fail-on-warning` makes it fail the command.

`BudgetExceededError` exists, and its message points to [Cost tracking](./cost-tracking.md). That page covers the per-run cost of the LLM-backed `fluid forge` commands, not the acquisition budget described here. `chargeback` is accepted and not read.

## Lineage emission

A DuckDB acquisition run emits an OpenLineage `RunEvent` pair, a start and a complete or fail, naming the source it read and the expose it wrote.

The emitter is chosen by environment, not by a key in the contract. With no endpoint configured the events are dropped:

```bash
export OPENLINEAGE_URL=https://marquez.example.com
```

`FLUID_OPENLINEAGE_URL` takes precedence over `OPENLINEAGE_URL`. The endpoint path defaults to `api/v1/lineage` (change it with `FLUID_OPENLINEAGE_ENDPOINT`), and `OPENLINEAGE_API_KEY` or `FLUID_OPENLINEAGE_API_KEY` sets the bearer token. A private or loopback endpoint is allowed unless `FLUID_OPENLINEAGE_ALLOW_PRIVATE=false`; link-local addresses, such as cloud metadata endpoints, are blocked either way.

The schema's `lineage` block has one key, `emit`, and no runner reads it. A build with `lineage: { emit: false }` still emits when `OPENLINEAGE_URL` is set. Out-of-tree emitters subclass `LineageEmitter` from `fluid_build.api.lineage`.

## Image signature verification (Cosign)

`properties.airbyte.image_signature` and `properties.kafka-connect.image_signature` accept a verifier (`cosign`), a `publicKey`, and `slsaProvenance` (`required`, `optional` or `disabled`):

```yaml
      airbyte:
        connector_image: airbyte/source-postgres
        image_signature:
          verifier: cosign
          publicKey: ${COSIGN_PUBLIC_KEY}
          slsaProvenance: required
```

As of 0.18.1, `fluid apply` does not run this check. The Airbyte runner verifies an image only when a verifier object is passed to it, and the build dispatcher that `fluid apply` goes through does not pass one. No runner reads the Kafka Connect block. A contract with `image_signature` validates and applies without a Cosign check, so do not rely on it as a gate yet. When a check does run and fails, the build raises `SupplyChainViolationError`, whose `doc` link prints [`fluid verify-signature`](../cli/verify-signature.md); that page covers signing `fluid bundle` archives and not connector images.

## Catalog registration

```yaml
catalog:
  register: [datahub, openmetadata]
  documentation: auto            # auto | manual | none
```

`register` accepts `datahub`, `openmetadata`, `datamesh_manager`, `unity`, `glue` and `snowflake_horizon`. The CLI registers each target when you run [`fluid publish`](../cli/publish.md), not at apply time. `fluid publish --dry-run` prints `acquisition publish (plan only) <product>/<build> → <target>` for each one. A target with no endpoint configured in the environment is reported as not configured, and the other targets still run.

Out-of-tree registrars implement the `CatalogRegistrar` protocol in `fluid_build.api.catalog`.

## Concurrency and state

```yaml
concurrency:
  lock:
    scope: product         # product | build
    onContended: abort     # abort | queue | replace
    timeout: PT10M
```

As of 0.18.1 the block validates and nothing acquires the lock: no runner calls the state store's `acquire_lock`, so two concurrent runs of one build both proceed. `LockHeldError` and its `queue` hint exist for when it is wired in.

Run records, cursors and the dead-letter queue live in `.fluid/` next to the contract. The default store is `FileStateStore`; an out-of-tree store implements the `StateStore` protocol in `fluid_build.api.state`.

## Top-level retention

The top-level `retention:` block declares how long run records, run logs, lineage events and dead-letter entries should be kept. Durations are ISO-8601, so `P90D`, not `90d`; a value like `90d` fails validation.

```yaml
retention:
  runState: P30D
  runLogs: P90D
  lineage: P365D
  dlq: P180D
```

These four values are also the defaults.

[`fluid retention sweep`](../cli/retention.md) deletes records older than a horizon. As of 0.18.1 it does not read the contract:

```bash
fluid retention sweep --state-root .fluid --json
```

The command takes only `--state-root` and `--json`. It applies the four defaults above to every product under the state root. A product that declares `runState: P365D` still has its run records deleted after 30 days, and a key you leave out gets its default, not "never sweep". Declaring a longer horizon does not protect a run record today.

## Authoring an acquisition contract

You do not have to write the YAML by hand. `fluid init --discover` introspects a source and emits one Bronze contract per discovered stream:

```bash
fluid init demo --discover file:///data/csv-tree
fluid init demo --discover "postgres://user@host:5432/dbname"
```

```text
🔍 Discovering streams at file:///data/csv-tree…
  ✓ contract.orders.fluid.yaml  (4 cols)

✓ Emitted 1 contract(s). Next: `fluid validate <file>`.
```

Discovery reads the database's `information_schema` for Postgres and MySQL, and walks the directory for a file source. As of 0.18.1, a Postgres URI whose server cannot be reached fails with `Unknown secret storage found: 'local_file'` under the heading `connectivity probe failed`, which hides the real connection error. A `file://` URI that points inside the contract's directory works. For `postgres://` and `mysql://` URIs, nothing in the connection is redacted: the password in the URI is written verbatim into `builds[].properties.source.connection.password`, so delete that `password:` line and add `secretRef: env://<NAME>` before you commit the file (see [`fluid init --discover`](../cli/init.md#discover-—-introspect-a-source-into-a-bronze-contract)). The emitted contract uses `fluidVersion: 0.7.3`, and it validates as is.

A discovered contract that points at a file source outside its own directory is subject to the sandbox rules above. A `file://` URI that is outside the contract's directory fails with DuckDB's own `Permission Error ... file system operations are disabled by configuration`, without the `FLUID_DUCKDB_ALLOWED_DIRS` hint that a plain path gets. Move the contract next to the data, or write the source as a plain path and allow its directory.

To migrate existing tooling, [`fluid import`](../cli/import.md) converts Meltano projects, Airbyte workspaces, dlt pipelines and Singer tap configs into acquisition contracts.

## See also

- [Product Types: SDP, ADP, CDP](../data-products/product-type.md): the vocabulary that gates composition
- [Postgres → DuckDB walkthrough](../walkthrough/source-aligned-postgres-duckdb.md): an end-to-end example
- [DuckDB sandbox](./duckdb-sandbox.md): what contract SQL and acquisition builds can read and write
- [`fluid init --discover`](../cli/init.md): onboarding for source-aligned ingestion
- [`fluid runs`](../cli/runs.md), [`fluid retention`](../cli/retention.md), [`fluid secrets`](../cli/secrets.md): day-2 operations
- [API stability](./api-stability.md): the `fluid_build.api` surface for out-of-tree runners and registrars
- [Typed CLI errors](./typed-cli-errors.md): the error catalog, including `CapabilityMismatchError`, `SchemaDriftError` and `BudgetExceededError`
