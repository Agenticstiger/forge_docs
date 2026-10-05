# Source-Aligned: Postgres → DuckDB → Parquet

A minimal end-to-end walkthrough of a source-aligned Bronze (`SDP`) data product. We'll start a local Postgres with seeded data, run `fluid validate` and `fluid apply` against the included contract, and verify the output Parquet file. No Airbyte cluster, no Airflow, no cloud setup — DuckDB does the ingestion in-process.

<iframe
  src="/forge_docs/reels/source-aligned-bronze.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Six months → sixty seconds — Fluid Forge source-aligned Bronze">
</iframe>

The reel above shows the flow this walkthrough covers: `fluid init --discover postgres://…`, `fluid validate --probe`, `fluid apply`, `fluid runs status`. The steps below start from the contract the repo ships instead of discovering one.

::: tip Where this walkthrough lives
The exact contract, docker-compose, seed SQL, Makefile, and verification script for this walkthrough live in the `forge-cli` repo at [`examples/source-aligned-postgres-duckdb/`](https://github.com/Agenticstiger/forge-cli/tree/main/examples/source-aligned-postgres-duckdb). The contract declares schema `0.7.3`, as the repo ships it; `0.7.5`, the latest stable schema, also validates it. This page was run against `data-product-forge` 0.18.1.
:::

## What you'll build

A single contract that:

1. Reads `public.orders` from a local Postgres
2. Lands the rows as `out/orders.parquet`
3. Runs the `dlp_scan` and `quality_gate` pre-land hooks
4. Persists a run record under `.fluid/runs/<product>/<build>/runs/<run-id>.json`

Total wall time on the included fixture: under 3 seconds.

## Prerequisites

- Docker (for the Postgres container)
- `make` (for the Makefile shortcuts)
- Fluid Forge and DuckDB: `pip install "data-product-forge[local]"` (the `local` extra installs DuckDB 1.5.0 or later)
- The example's `Makefile` runs `$(VENV)/bin/python`, with `VENV` defaulting to `../../.venv` inside a forge-cli checkout. Outside one, run the steps by hand as shown below.

## The contract

```yaml
fluidVersion: "0.7.3"
kind: DataProduct
id: bronze.crm_orders
name: CRM Orders Bronze
description: |
  Source-aligned Bronze data product. Acquires raw orders from a Postgres
  source via DuckDB's postgres_scan and lands them as Parquet for downstream
  Silver/Gold consumption.
domain: sales

metadata:
  # Both vocabularies (medallion + Data Mesh) are first-class in v0.7.3.
  # Bronze and SDP (Source-Aligned Data Product) are equivalent — either
  # alone is sufficient. They're shown here together to demonstrate that
  # tools and humans can read whichever they prefer. The validator
  # rejects Bronze+ADP / Bronze+CDP / Silver+SDP etc. as inconsistent.
  layer: Bronze
  productType: SDP
  owner:
    team: data-platform
    email: data-platform@co.example
  classification: confidential
  experimental: [acquisition]

retention:
  runState: P30D
  runLogs: P90D
  lineage: P365D
  dlq: P180D

builds:
  - id: ingest_orders
    description: Full-refresh copy of public.orders from Postgres.
    pattern: acquisition
    engine: duckdb
    capabilities:
      - full_refresh
      - schema_discovery
    properties:
      source:
        kind: postgres
        connection:
          host: "{{ env.PGHOST }}"
          port: "{{ env.PGPORT }}"
          database: "{{ env.PGDATABASE }}"
          user: "{{ env.PGUSER }}"
          password: "{{ env.PGPASSWORD }}"
        mode: full_refresh
        streams:
          - public.orders
      sink:
        format: parquet
      preLand:
        - dlp_scan
        - quality_gate
      quality:
        gates:
          - rule: not_null
            columns: [id]
            severity: error
        onError: route_to_dlq
      lineage:
        emit: true
    execution:
      trigger:
        type: schedule
        schedule: "0 */4 * * *"
    outputs:
      - orders_raw

exposes:
  - exposeId: orders_raw
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: ./out/orders.parquet
    contract:
      schema: []
      schemaPolicy: discover_and_freeze
```

A few things worth noting:

- **Both `metadata.layer` and `metadata.productType` are set.** Either one alone would also validate. Bronze ↔ SDP is the canonical pairing — see [Product Types](/forge_docs/data-products/product-type.html) for the full mapping.
- **`retention:` is at the top level**, not inside the build. The schema accepts the four horizons, and each value must be an ISO 8601 duration (`P30D`, not `30d`). As of 0.18.1, `fluid retention sweep` does not read this block: see [Retention in 0.18.1](#retention-in-0-18-1) below.
- **`{{ env.PGHOST }}` placeholders** resolve from environment variables at apply time; the contract is safe to commit.
- **`pattern: acquisition` + `engine: duckdb`** triggers the embedded DuckDB runner — no external service needed.

## Run it end-to-end

The `Makefile` shipped with the example wraps the steps:

```bash
cd forge-cli/examples/source-aligned-postgres-duckdb
make all
```

`make all` runs:

```text
make up        # docker compose up: Postgres with seeded public.orders
make run       # fluid validate → fluid apply
make verify    # python verify.py: row-count + schema assertions
```

If you'd rather run the steps by hand:

```bash
# 1. Bring up Postgres (port 5432) with seeded fixture data
docker compose up -d

# Set the env vars the contract reads (the values docker-compose.yml creates)
export PGHOST=localhost PGPORT=5432
export PGDATABASE=fluid_demo PGUSER=fluid PGPASSWORD=fluid_pw

# 2. Validate the contract
fluid validate contract.fluid.yaml

# 3. Apply (acquires from Postgres, writes Parquet)
fluid apply --mode amend-and-build --build-id ingest_orders contract.fluid.yaml --yes

# 4. Verify the output
python verify.py
```

Expected `validate` output:

```text
✅ Valid FLUID contract (schema v0.7.3)
Validation completed in 0.006s
```

`apply` prints the build runner's summary:

```text
🚀 FLUID Build Runner
================================================================================
Builds: 1
================================================================================
...
duckdb.run stream=public.orders sql_chars=449
================================================================================
📈 Overall Summary
================================================================================
Total builds: 1
✅ Executed: 1
❌ Failed: 0
⏭️  Skipped: 0
================================================================================
```

Before the runner starts, `apply` also prints a warning about `{{ env.PGPASSWORD }}`: it refuses to resolve a placeholder whose name looks like a secret into the contract body and leaves it literal there. The run succeeds, because the acquisition runner reads the variable itself when it connects. Two more lines are expected on a laptop run: a notice that `FLUID_PII_TOKENIZATION_KEY` is unset (only relevant if you add a `tokenize_pii` hook), and, with a password shorter than six characters, a note that it is not in the log-redaction registry.

`verify.py` reads `out/orders.parquet` and checks the row count and columns:

```text
OK: 5 rows, columns=['amount', 'customer', 'id', 'placed_at']
```

The seed loads five orders with four columns.

The run record is `.fluid/runs/bronze.crm_orders/ingest_orders/runs/<run-id>.json`:

```json
{
  "facets": {
    "duration_seconds": 0.4000580310821533,
    "engine": "duckdb",
    "landed": {
      "destinations": {
        "public.orders": "out/orders.parquet"
      },
      "mode": "full_refresh",
      "rows_from": "write"
    }
  },
  "finished_at": "2026-10-05T06:23:08Z",
  "records_total": 5,
  "run_id": "0101M45BNXTB2G7K0H",
  "started_at": "2026-10-05T06:23:07Z",
  "state": "succeeded",
  "streams": [
    {
      "duration_seconds": 0.1841881275177002,
      "error": null,
      "name": "public.orders",
      "records": 5,
      "state": "succeeded"
    }
  ]
}
```

::: warning The env vars must be set in the shell that runs `apply`
If `PGHOST` and the others are not exported in that shell, the build fails at connect time and the run record says so (`state: failed`, `records: 0`), for example `Unable to connect to Postgres at "": connection to server on socket "/tmp/.s.PGSQL.5432" failed`. As of 0.18.1, `fluid validate --probe` does not catch this: with the variables unset it still reports the contract valid.
:::

## What just happened

| Stage | What ran | Where it's wired |
|---|---|---|
| Validation | JSON-schema check against the contract's declared schema (`0.7.3`), plus the Bronze/SDP consistency check | `fluid validate` |
| Source read | The runner installs and loads DuckDB's `postgres` extension on first use, then reads the stream with `postgres_scan(...)`. The first run needs network access to DuckDB's extension repository | DuckDB runner, `build_runners/duckdb/` |
| Quality gate | The `not_null` gate on `id` is compiled into the read: the `COPY` selects `... WHERE id IS NOT NULL` | DuckDB runner |
| Pre-land hook | `dlp_scan` classifies the batch before it lands. `quality_gate` in `preLand` is accepted and handled by the gate above, not by a separate hook | `build_runners/hooks/dlp_scan.py` |
| Write | `COPY (...) TO 'out/orders.parquet' (FORMAT 'parquet')` | DuckDB runner |
| Run record | The JSON record shown above | `.fluid/runs/...` |

## Day 2: runs and retention

After a successful run, `fluid runs` reads the records under `.fluid/`:

```bash
fluid runs status bronze.crm_orders --last 5
```

```text
product_id: bronze.crm_orders
build_id: ingest_orders
runs:
  -
    run_id: 0101M45BQFC1NR8P5F
    state: succeeded
    started_at: 2026-10-05T06:23:58Z
    finished_at: 2026-10-05T06:23:58Z
    records_total: 5
    ...
freshness_seconds: 3.45383
error_rate_24h: 0.0
last_state: succeeded
facets:
  total_runs_seen: 2
```

With two runs on record, compare them by run id (the ids are the file names under `.fluid/runs/<product>/<build>/runs/`):

```bash
fluid runs diff bronze.crm_orders \
  --build ingest_orders \
  --run-a <run-id-1> --run-b <run-id-2>
```

```text
state_a: succeeded
state_b: succeeded
records_total_a: 5
records_total_b: 5
records_delta: 0
...
streams:
  -
    name: public.orders
    records_a: 5
    records_b: 5
    delta: 0
```

`fluid runs logs bronze.crm_orders --component build` prints `(no build logs for bronze.crm_orders)` for this build: the run record is the only thing this build writes under `.fluid/`.

### Retention in 0.18.1

```bash
fluid retention sweep
```

```text
deleted_paths: []
bytes_freed: 0
by_category:
  run_state: 0
  run_logs: 0
  lineage: 0
  dlq: 0
```

As of 0.18.1, `fluid retention sweep` does not read the contract's `retention:` block, and it does not read `.fluid/policies/<product>/retention.json`. It sweeps every product under the state root with fixed horizons: run state `P30D`, run logs `P90D`, lineage `P365D` and DLQ `P180D`. A product that declares `runState: P365D` still has its run records swept after 30 days, and a key you leave out gets the fixed value, not "never". The [`fluid retention`](/forge_docs/cli/retention.html) reference describes the command.

See [`fluid runs`](/forge_docs/cli/runs.html) and [`fluid secrets`](/forge_docs/cli/secrets.html) for the rest of the operator commands.

## Where to go from here

The same contract shape works with other acquisition engines and deployment modes; [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) lists them and the contract keys each one reads. For a source other than Postgres, change `source.kind` and `source.connection`.

## See also

- [Product Types — SDP, ADP, CDP](/forge_docs/data-products/product-type.html) — the vocabulary used in this contract
- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — the framework reference
- [`fluid init --discover`](/forge_docs/cli/init.html#discover-—-introspect-a-source-into-a-bronze-contract) — auto-generate this contract by introspecting the source
- [`fluid runs`](/forge_docs/cli/runs.html), [`fluid retention`](/forge_docs/cli/retention.html), [`fluid secrets`](/forge_docs/cli/secrets.html) — day-2 ops
