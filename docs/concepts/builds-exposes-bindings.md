---
title: Builds, Exposes, Bindings
description: The three core blocks of every contract — produce, surface, land.
---

# Builds, Exposes, Bindings

Every contract maps three questions onto three YAML blocks:

| Question | Block | Example |
|---------|-------|---------|
| **How is the data produced?** | `builds[]` | Embedded SQL, a dbt project, a Python script, a Spark job. |
| **What does the product expose to consumers?** | `exposes[]` | A table, a view, a file, a Kafka topic. |
| **Where does it physically land?** | `binding` (inside each expose) | `gcp/bigquery_table`, `aws/s3_file`, `local/parquet`, etc. |

You can have many of each. Every `expose` must declare exactly one `binding`.

## `builds[]` — production logic

```yaml
builds:
  - id: bitcoin_price_ingestion
    pattern: embedded-logic            # or hybrid-reference (dbt/python repo)
    engine: sql                        # or python, dbt, spark
    properties:
      sql: |
        SELECT CURRENT_TIMESTAMP AS price_timestamp,
               price AS price_usd
        FROM raw_btc_feed
```

Patterns supported in v0.7.2 (verified against `fluid-schema-0.7.2.json`):
- **`embedded-logic`** — SQL/code inline in the contract. `language` enum: `sql`, `flink_sql`, `pyspark`, `scala`, `python`, `r`.
- **`hybrid-reference`** — dbt-style: point at an external repo with a `model:` field and optional `vars:`.
- **`multi-stage`** — orchestration pattern with a `stages[]` array of named build steps. Schema description: "Multi-stage orchestration pattern" (introduced in v0.5.5).

## `exposes[]` — the consumer-facing API

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

The schema lives at `exposes[].contract.schema`. Quality rules live one level deeper at `exposes[].contract.dq.rules` (see [Quality, SLAs & Lineage](./quality-sla-lineage.md)).

`expose.kind` enum (verified against `fluid-schema-0.7.2.json`):
`table` · `view` · `api` · `file` · `stream` · `topic` · `feature_store` · `model` · `vector` · `graph` · `time_series` · `other`

## `binding` — the physical landing target

`binding.platform` enum (v0.7.2):
`gcp` · `aws` · `azure` · `snowflake` · `databricks` · `kafka` · `local` · `kubernetes` · `other`

`binding.format` enum (v0.7.2):
`bigquery_table` · `snowflake_table` · `gcs_file` · `s3_file` · `http_api` · `grpc_api` · `pubsub_topic` · `kafka_topic` · `delta_table` · `iceberg` · `parquet` · `csv` · `json` · `other`

`binding.location` shape varies per `format`:

| Format | Required `location` keys |
|--------|--------------------------|
| `bigquery_table` | `project`, `dataset`, `table` (region optional) |
| `snowflake_table` | `database`, `schema`, `table` |
| `s3_file` | `bucket`, `prefix` (region optional) |
| `parquet` / `csv` | `path` (relative or absolute) |

::: tip The "swap one line" trick
The whole point of bindings is that **`platform: local` → `platform: gcp` is the only change you need** to redeploy the same product to BigQuery. The `format` and `location` keys change to match the new platform's vocabulary, but everything else (schema, DQ rules, governance) stays identical.
:::

## Multi-expose products: one product, many surfaces

Most data products produce one output. Some produce several: a Gold table for analysts, a feature_store view for the ML team, a Kafka topic for downstream consumers. Add multiple `exposes[]` entries:

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
        readers: [group:analysts@company.com]

  - exposeId: customer_360_features       # for ML
    kind: feature_store
    binding:
      platform: gcp
      format: bigquery_table
      location: { project: prod, dataset: features, table: customer_360_v1 }
    policy:
      authz:
        readers: [group:ml-team@company.com, serviceAccount:training@…]

  - exposeId: customer_changes            # for downstream
    kind: stream
    binding:
      platform: gcp
      format: pubsub_topic
      location: { project: prod, topic: customer-changes }
```

The `builds[]` are shared. The compute happens once, the surfaces are independent. Each surface gets its own audience via `policy.authz`.

## `consumes[]` — declaring dependencies

When your product depends on another product (Silver consuming Bronze, Gold consuming Silver), declare it in `consumes[]`:

```yaml
consumes:
  - consumeId: bronze_orders
    productId: bronze.retail.orders_v1
    contract: { exposeId: orders_table }
```

`consumes[]` references compile to:
- **Lineage edges** in `fluid generate artifacts` (OPDS / ODCS / DataMesh Manager output)
- **Read grants** in `policy-apply` (the consumer's service principal gets read on the producer's expose)
- **Build-time validation** — `fluid validate` confirms the upstream product exists and the cited `exposeId` matches

You don't usually wire this by hand. `fluid forge` infers it from your SQL/dbt refs. Override only when crossing system boundaries.

## Build execution: where SQL/Python actually runs

`builds[].execution` controls the runtime environment:

```yaml
builds:
  - id: bitcoin_price_ingestion
    pattern: embedded-logic
    engine: python
    properties:
      script: ./ingest.py
    execution:
      runtime:
        image: python:3.11-slim
        dependencies: [boto3, requests, pyarrow]
        env: [AWS_REGION, S3_BUCKET]
      retries:
        count: 3
        backoff: exponential
      trigger:
        type: scheduled
        cron: "0 * * * *"             # hourly
```

For SQL builds (`engine: sql`), the runtime is the warehouse itself (BigQuery, Snowflake, DuckDB) — `execution.runtime` is unused. For Python and Spark, the runtime is a container image; the chosen orchestrator (Airflow, Dagster, etc.) provisions it.

## Where to look next

- [Providers vs platforms](./providers-vs-platforms.md) — how `binding.platform` resolves to actual cloud SDKs
- [Quality, SLAs & Lineage](./quality-sla-lineage.md) — the `dq.rules`, `slas`, and `lineage` blocks
- [Governance & Policy](./governance-policy.md) — the `accessPolicy` and `agentPolicy` blocks
- [`fluid plan` walkthrough](/forge_docs/cli/plan) — what the planner emits per binding
