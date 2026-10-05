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

`fluid runs status bronze.orders` and the other [`fluid runs`](../cli/runs.md) commands read those records. They have the same shape for every engine.

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

With this binding the build writes `s3://acme-lake/bronze/orders/orders.parquet`. The Glue table that `fluid generate iac` emits for the same binding points at `s3://acme-lake/bronze/orders`, so the catalog and the data share one prefix. The destination's DuckDB extensions and credentials come from the destination, not from the source.

A binding that names no bucket stays on local disk. The build does not invent the `{account}-fluid-data` bucket that the IaC path falls back to, because moving data off the machine on the strength of a default would be a decision the CLI should not make for you.

`sink.format` takes `iceberg`, `delta`, `parquet`, `csv`, `json`, `snowflake_table`, `bigquery_table`, `redshift_table` or `duckdb_table`, with optional `catalog` and `partitionBy`. The DuckDB runner writes `parquet`, `csv` and `json` files.

### What the DuckDB sandbox allows

Every DuckDB connection the engine opens runs in DuckDB's own sandbox ([DuckDB sandbox](./duckdb-sandbox.md)). For an acquisition build that means:

- A local source and each landing path must sit in the contract's directory, its FLUID workspace, or a directory in `FLUID_DUCKDB_ALLOWED_DIRS`. Anything else is refused before the build runs:

  ```text
  ✗ The contract declares '/data/landing/orders.csv' (...), outside the directories it may read
  and write (...). The operator can allow a directory with FLUID_DUCKDB_ALLOWED_DIRS.
  fix  Move the file under the contract's directory or its workspace, or, as the operator, list
  its directory in FLUID_DUCKDB_ALLOWED_DIRS (separated by ':').
  ```

- Name a file or a glob as the source `uri`. As of 0.18.1, a `uri` that names a directory outside the contract's directory is refused even when `FLUID_DUCKDB_ALLOWED_DIRS` lists it; `<dir>/orders.csv` or `<dir>/*.csv` works.
- A `source.kind: http` source is read from the URL you declare, and a declared `s3://` location is reachable. These are acquisition builds; SQL written inside a contract cannot read an `http(s)` URL.

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

Masking is the DuckDB runner's. A build on another engine, or a Python `hybrid-reference` build, does not apply it.

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

At the start of a run, the engine compares the columns it reads with the expose's declared `contract.schema`. The first expose is the one compared. With an empty `schema: []` there is nothing to compare and the check does not run. When `schemaPolicy` is not set, the check runs as `evolve_safe`, which is not the schema's own default of `strict`.

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

Every acquisition run emits an OpenLineage `RunEvent` pair, a start and a complete, fail or abort, naming the source it read and the expose it wrote.

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

Discovery reads the database's `information_schema` for Postgres and MySQL, and walks the directory for a file source. As of 0.18.1, a Postgres URI whose server cannot be reached fails with `Unknown secret storage found: 'local_file'` under the heading `connectivity probe failed`, which hides the real connection error. A `file://` URI that points inside the contract's directory works. Secrets in the connection are replaced with `${ENV_VAR}` placeholders. The emitted contract uses `fluidVersion: 0.7.3`, and it validates as is.

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
