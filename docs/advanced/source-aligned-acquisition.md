# Source-Aligned Acquisition

Schema **0.7.3** introduces a first-class `acquisition` build pattern for source-aligned (Bronze / SDP) data products. Instead of writing imperative ingestion code or stitching together a 200-line Airflow DAG, you describe **what** to ingest and **how** to deliver it; Forge picks the right engine and runs it under a uniform protocol.

<iframe
  src="/reels/source-aligned-bronze.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Six months → sixty seconds — Fluid Forge source-aligned Bronze">
</iframe>

Six months of Airbyte cluster setup, or sixty seconds of `fluid init --discover`. The reel above shows the full flow; this page covers the framework underneath.

::: tip Where this fits
This page covers the framework that makes source-aligned ingestion declarative — engines, deployment modes, delivery guarantees, schema evolution, quality gates, and lineage emission. Pair it with [Product Types](/data-products/product-type.html) (the SDP/ADP/CDP vocabulary) and the [Postgres → DuckDB walkthrough](/forge_docs/walkthrough/source-aligned-postgres-duckdb.html) (a worked example).
:::

## The acquisition build pattern

A source-aligned contract has one `builds[]` entry whose `pattern: acquisition`. Everything else hangs off the `properties:` block of that build:

```yaml
fluidVersion: 0.7.3
kind: DataProduct
metadata:
  name: customer-orders-bronze
  productType: SDP        # or layer: Bronze — either is sufficient
  owner: { team: ingestion }

builds:
  - id: ingest_orders
    pattern: acquisition
    properties:
      source:              # WHERE to read from
        kind: postgres
        connection: { url: ${POSTGRES_URL} }
        tables: [public.orders, public.customers]
      sink:                # WHERE to land it
        format: parquet
        location: s3://acme-bronze/customer-orders/
      engine:              # WHICH engine runs the ingestion
        type: duckdb       # duckdb | dlt | meltano | airbyte | kafka-connect | debezium
      delivery:            # Delivery guarantee
        mode: at_least_once
      schemaEvolution:
        policy: discover_and_freeze
      quality:
        rules: [...]
        maxAllowedErrors: 100
      cost:
        budget: { monthly: 50 }
        onExceed: warn
      catalog:
        registrar: snowflake_horizon
      lineage:
        enabled: true
      preLand:
        hooks: [tokenize_pii, dlp_scan]
      deployment:
        mode: embedded
```

The schema constraints, sub-defs, and engine-specific properties are catalogued in `fluid_build/schemas/fluid-schema-0.7.3.json` under `$defs/acquisitionPattern`.

## Six ingestion engines, one protocol

All six engines conform to the public `Runner` Protocol in `fluid_build.api.runner` (see [API Stability](/forge_docs/advanced/api-stability.html)). They share the same `validate → plan → apply` lifecycle, the same exit-code contract, and the same run-record JSON shape, so day-2 ops (`fluid runs status`, `fluid runs logs`, `fluid runs diff`) work identically across all of them.

| Engine | Best for | Ships with |
|---|---|---|
| **`duckdb`** | Zero-infra ingestion from CSV, Parquet, JSON, Postgres, MySQL, SQLite, HTTP | Embedded — no extra service to run |
| **`dlt`** | Python-native sources, custom `@dlt.source` modules, plus dlt verified sources (filesystem, sql_database) | `pip install 'data-product-forge[dlt]'` |
| **`meltano`** | Singer-protocol ELT — one runner unlocks 600+ Singer taps | `pip install 'data-product-forge[meltano]'` |
| **`airbyte`** | Airbyte OSS / Cloud connectors with REST control + Cosign image signature verification | `pip install 'data-product-forge[airbyte]'` |
| **`kafka-connect`** | Stream ingestion via Kafka Connect — JDBC / S3 / Salesforce / Mongo sources, JDBC / S3 / Snowflake / Iceberg / BigQuery sinks | `pip install 'data-product-forge[kafka-connect]'` |
| **`debezium`** | CDC from Postgres / MySQL / MongoDB / SQL Server / Oracle in Kafka Connect or Debezium Server mode | `pip install 'data-product-forge[debezium]'` |

Pick the engine via `properties.engine.type`. The generated plan and apply behavior is the same shape; only the engine-specific config under `properties.engine.properties` differs.

## Three deployment modes

`properties.deployment.mode` decides how the engine runs at apply time:

| Mode | Runs where | Use it when |
|---|---|---|
| **`embedded`** *(default)* | Inside the `fluid` process — no extra service | Local dev, CI, simple Bronze ingestion. Lowest latency, no infra to maintain. |
| **`bring-your-own`** | Existing Airbyte / Meltano / Kafka Connect cluster you already operate | You already run one of these stacks and want Forge to drive it via REST. |
| **`managed`** | Forge generates infra (Docker Compose / Helm / OpenTofu) and provisions a managed runner | New project, willing to let Forge own the engine lifecycle. |

For `managed`, the platform sub-mode picks the artifact:

```yaml
deployment:
  mode: managed
  managed:
    platform: docker      # docker | kubernetes | terraform
```

The infra layer is hyperscaler-agnostic — no `boto3`, `google.cloud`, or `azure` imports. `kubernetes` mode emits Helm with Flux-style HelmRelease CRs and ExternalSecret + NetworkPolicy resources; `terraform` mode emits OpenTofu modules. Sovereignty constraints (`metadata.dataResidency`) propagate into the values overlay automatically.

## Delivery guarantees

```yaml
delivery:
  mode: at_least_once     # at_most_once | at_least_once | exactly_once
  dlq:
    maxRecordsBeforeAbort: 1000
    alertOn: [schemaDrift, infraFailure]
```

Each engine declares which guarantees it supports via its capability set (`RunnerCapability` enum on the public API). At plan time, Forge negotiates: if the contract asks for `exactly_once` against a runner that only supports `at_least_once`, the validator raises a typed `CapabilityMismatchError` rather than silently degrading.

The DLQ block is honored uniformly across all engines: records that fail to land are written to the configured dead-letter location; if `maxRecordsBeforeAbort` is exceeded, the run aborts with a `DLQOverflowError` instead of silently dropping records or hanging.

## Schema evolution

```yaml
schemaEvolution:
  policy: discover_and_freeze    # strict | discover_and_freeze | evolve_safe
```

| Policy | Behavior on a schema change in the source |
|---|---|
| **`strict`** | Run aborts with `SchemaDriftError`. The drift fingerprint is logged for review. |
| **`discover_and_freeze`** *(default for first run)* | First-ever run discovers the schema and pins it; subsequent runs require strict matching. |
| **`evolve_safe`** | Additive changes (new nullable columns, widened types) are accepted; breaking changes (column drop, type narrow) abort. |

Decisions are deterministic — the same input fingerprint always yields the same accept/abort decision, so CI replays are reproducible.

## Quality gates

```yaml
quality:
  rules:
    - column: order_id
      check: not_null
    - column: amount
      check: numeric_in_range
      args: { min: 0, max: 1_000_000 }
  maxAllowedErrors: 100
  anomaly:
    method: iqr            # ewma | iqr | exact
    onAnomaly: warn        # warn | abort
```

Quality runs **before** records land, via the pre-land hook chain (`preLand.hooks`). Built-in hooks ship in `fluid_build/build_runners/hooks/`:

- `quality_gate` — Apply DQ rules, abort or warn per `maxAllowedErrors`
- `dlp_scan` — Scan for PII / sensitive data
- `tokenize_pii` — Tokenize PII columns before they hit the sink
- `emit_lineage_input` — Emit OpenLineage `RunEvent` for the input read

Anomaly detection (`quality.anomaly`) compares this run's stats (row count, null rate, distinct values) against the historical baseline. Three methods: EWMA (smoothed), IQR (interquartile range), or exact (deterministic match). Useful for catching upstream regressions early.

## Cost tracking + budget gates

```yaml
cost:
  budget: { monthly: 100 }
  onExceed: fail           # fail | warn
  chargeback:
    label: ingestion-team
```

Every run records cost in the run-record JSON (`fluid_build.api.cost.CostTracker`). `fluid stats` ([page](/forge_docs/cli/stats.html)) aggregates across runs by provider, type, or engine. The monthly budget is enforced at run start — if the projected total would exceed budget and `onExceed: fail`, the run aborts with `BudgetExceededError`.

Chargeback labels propagate into cloud tags and catalog metadata for finance teams to slice cost by team.

## Lineage emission

```yaml
lineage:
  enabled: true
  emitter:
    type: openlineage_http
    endpoint: https://marquez.example.com/api/v1
```

Every acquisition run emits an OpenLineage `RunEvent` covering inputs (sources read), outputs (sink written), and run state (start, complete, fail). Three built-in emitters live in `fluid_build/build_runners/_lineage.py`:

| Emitter | When to use |
|---|---|
| **`null`** *(default)* | No emission. Useful for local dev when you don't run a Marquez. |
| **`buffered`** | Collects events in-memory; useful in tests or when you want to inspect via the run record. |
| **`http`** | POSTs to an OpenLineage HTTP endpoint (Marquez, DataHub, OpenMetadata, etc.). |

Out-of-tree emitters subclass `LineageEmitter` from `fluid_build.api.lineage` (public API).

## Image signature verification (Cosign)

For `airbyte` and any other engine that runs container images, you can require Cosign signature verification:

```yaml
imageSignature:
  required: true
  cosign:
    publicKey: ${COSIGN_PUBLIC_KEY}
  slsa:
    required: true
```

Five verification paths are supported and tested: signed / unsigned / wrong-key / SLSA-provenance-required-and-missing / SLSA-provenance-required-and-present. Failed verification aborts the run before any pull or apply happens.

## Catalog registration

```yaml
catalog:
  registrar: snowflake_horizon  # datahub | openmetadata | unity | glue | snowflake_horizon | datamesh_manager
  options: { ... }
```

After a successful apply, Forge registers the produced dataset with the configured catalog. Five built-in registrars cover the major catalogs:

| Registrar | Wire | What it propagates |
|---|---|---|
| `datahub` | GMS REST | Glossary terms, classifications, lineage |
| `openmetadata` | OpenMetadata REST | Tags, classifications, lineage |
| `unity` | Databricks REST | Table parameters, column tags |
| `glue` | AWS Glue HTTP (no boto3 dep) | Table parameters, column comments |
| `snowflake_horizon` | Snowflake SQL | Object tags, classifications |
| `datamesh_manager` | Data Mesh Manager REST | ODPS-Bitol entries, ownership |

Out-of-tree registrars implement the `CatalogRegistrar` Protocol from `fluid_build.api.catalog`.

## Concurrency + state

```yaml
concurrency:
  lock: { onContended: queue }     # queue | fail
```

Forge holds a single-flight lock per `(product, build, env)` triple. If a run is already in flight, `onContended: queue` waits for the lock; `onContended: fail` raises `LockHeldError` immediately. Useful in CI to prevent two GitHub Actions runs from clobbering each other.

The state store backing locks, watermarks, and run records is `FileStateStore` by default (under `.fluid/runs/`). Out-of-tree state stores (Redis, Postgres) implement the `StateStore` Protocol from `fluid_build.api.state`.

## Top-level retention

The 0.7.3 contract gains a top-level `retention:` block that controls how long Forge keeps run records, logs, lineage events, and DLQ entries:

```yaml
retention:
  runState: 90d
  runLogs: 30d
  lineage: 365d
  dlq: 14d
```

Sweep with [`fluid retention sweep`](/forge_docs/cli/retention.html). The sweeper deletes any record older than its respective horizon and emits a structured summary.

## Authoring an acquisition contract

You don't have to write the YAML by hand. The flagship onboarding path for source-aligned ingestion is `fluid init --discover`:

```bash
fluid init --discover postgres://user:pass@host:5432/dbname
fluid init --discover mysql://user:pass@host:3306/dbname
fluid init --discover file:///path/to/csv-tree
```

Discover introspects the source — runs `\dt` on Postgres, `SHOW TABLES` on MySQL, walks the directory tree for filesystem sources — and emits a deterministic, valid 0.7.3 SDP contract per discovered stream. Secrets are auto-redacted to `${ENV_VAR}` placeholders.

For migrating existing tooling, [`fluid import`](/forge_docs/cli/import.html) converts Meltano projects, Airbyte workspaces, dlt pipelines, or Singer tap configs into FLUID acquisition contracts.

## See also

- [Product Types — SDP, ADP, CDP](/data-products/product-type.html) — the vocabulary that gates composition
- [Postgres → DuckDB walkthrough](/forge_docs/walkthrough/source-aligned-postgres-duckdb.html) — end-to-end worked example
- [`fluid init --discover`](/forge_docs/cli/init.html#discover) — flagship onboarding for source-aligned ingestion
- [`fluid import`](/forge_docs/cli/import.html) — Meltano / Airbyte / dlt / Singer importers
- [`fluid runs`](/forge_docs/cli/runs.html), [`fluid retention`](/forge_docs/cli/retention.html), [`fluid secrets`](/forge_docs/cli/secrets.html) — day-2 ops for acquisition pipelines
- [API Stability](/forge_docs/advanced/api-stability.html) — `fluid_build.api` v1.0 surface for out-of-tree runners and registrars
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html) — error catalog (CapabilityMismatchError, SchemaDriftError, BudgetExceededError, etc.)
