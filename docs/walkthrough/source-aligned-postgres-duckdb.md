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

The 60-second reel above runs the exact flow this walkthrough documents: `fluid init --discover postgres://…` → `fluid validate --probe` → `fluid apply` → `fluid runs status`.

::: tip Where this walkthrough lives
The exact contract, docker-compose, seed SQL, Makefile, and verification script for this walkthrough live in the `forge-cli` repo at [`examples/source-aligned-postgres-duckdb/`](https://github.com/Agenticstiger/forge-cli/tree/main/examples/source-aligned-postgres-duckdb). Schema 0.7.3 is delivered on the `feat/source-aligned-acquisition` branch — install from that branch (or wait for the next release) to follow along.
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
- Fluid Forge installed from the `feat/source-aligned-acquisition` branch (schema 0.7.3 not yet on PyPI)

## The contract

```yaml
fluidVersion: "0.7.3"
kind: DataProduct
id: bronze.crm_orders
name: CRM Orders Bronze
description: |
  Source-aligned Bronze data product. Acquires raw orders from a Postgres
  source via DuckDB's postgres_scan and lands them as Parquet.
domain: sales

metadata:
  layer: Bronze
  productType: SDP        # Bronze ↔ SDP — both shown for clarity
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
- **`retention:` is at the top level**, not inside the build. It governs how long Forge keeps run records, logs, lineage events, and DLQ entries — sweep with [`fluid retention sweep`](/forge_docs/cli/retention.html).
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

# Set the env vars the contract reads
export PGHOST=localhost PGPORT=5432
export PGDATABASE=acme PGUSER=acme PGPASSWORD=acme

# 2. Validate the contract
fluid validate contract.fluid.yaml

# 3. Apply (acquires from Postgres, writes Parquet)
fluid apply --build ingest_orders contract.fluid.yaml

# 4. Verify the output
python verify.py
```

Expected `validate` output:

```text
Validating 1 product in workspace 'CRM Orders Bronze'...
  ✅ bronze.crm_orders     no errors

Result: 1 passed, 0 failed
```

Expected `apply` output:

```text
▸ Materializing bronze.crm_orders → ingest_orders ...
  ▸ acquired schema   public.orders (5 columns, 8 rows)
  ▸ ran preLand hooks dlp_scan ✓ · quality_gate ✓
  ▸ wrote Parquet     ./out/orders.parquet (1 file, 1.2 KB)
  ▸ persisted run     .fluid/runs/bronze.crm_orders/ingest_orders/runs/2026-04-30T...json
  ✓ 1 build applied · 0 errors
```

## What just happened

| Stage | What ran | Where it's wired |
|---|---|---|
| Validation | JSON-schema check against fluid-schema-0.7.3.json + Bronze↔SDP consistency | `fluid validate` |
| Plan | The `acquisition` pattern compiles to one `runner: duckdb` action | Internal — DuckDB runner picks this up |
| Lock | Single-flight lock acquired on `(bronze.crm_orders, ingest_orders, default)` | `_state.FileStateStore` |
| Source read | DuckDB loads the `postgres` extension and runs `SELECT * FROM postgres_scan(...)` | DuckDB runner under `build_runners/duckdb/` |
| Pre-land hooks | `dlp_scan` then `quality_gate` run on the in-memory result before write | `build_runners/hooks/{dlp_scan,quality_gate}.py` |
| Write | `COPY (...) TO 'out/orders.parquet' (FORMAT 'parquet')` | DuckDB runner |
| Run record | Structured JSON written under `.fluid/runs/...` | `_state.FileStateStore` |
| Lineage | OpenLineage `RunEvent` emitted (`null` emitter by default — local dev) | `_lineage.py` |

## Day-2 — what to do after first apply

The acquisition layer is fully integrated with the day-2 ops commands. Once you have a successful run:

```bash
# Recent runs for this product
fluid runs status bronze.crm_orders --last 5

# Full logs from the most recent run
fluid runs logs bronze.crm_orders --component build

# Compare two runs (schema + row-count delta)
fluid runs diff bronze.crm_orders \
  --build ingest_orders \
  --run-a <run-id-1> --run-b <run-id-2>

# Sweep retention horizons
fluid retention sweep
```

See [`fluid runs`](/forge_docs/cli/runs.html), [`fluid retention`](/forge_docs/cli/retention.html), and [`fluid secrets`](/forge_docs/cli/secrets.html) for the full operator reference.

## Why this matters

This is the smallest possible source-aligned data product. With the same shape:

- Swap `engine: duckdb` for `engine: dlt` to use a Python-native dlt source — no contract changes besides the engine block
- Swap `engine: duckdb` for `engine: airbyte` and add an `imageSignature.cosign` block to require Cosign-verified Airbyte connector images
- Swap `engine: duckdb` for `engine: debezium` for CDC instead of full-refresh (changes the `mode:` to one of `initial`/`schema_only`/`never`/`when_needed`/`always`)
- Move `deployment.mode: embedded` to `deployment.mode: managed` with `platform: kubernetes` to have Forge generate Helm + ExternalSecret + NetworkPolicy for the engine

The contract stays portable across all six engines — see [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) for the full engine matrix and deployment mode options.

## See also

- [Product Types — SDP, ADP, CDP](/forge_docs/data-products/product-type.html) — the vocabulary used in this contract
- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — the framework reference
- [`fluid init --discover`](/forge_docs/cli/init.html#discover) — auto-generate this contract by introspecting the source
- [`fluid runs`](/forge_docs/cli/runs.html), [`fluid retention`](/forge_docs/cli/retention.html), [`fluid secrets`](/forge_docs/cli/secrets.html) — day-2 ops
