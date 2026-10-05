---
title: Write a contract that consumes another contract
description: "Chain data products with consumes[]: a downstream embedded-SQL build reads each upstream expose as a view, locally, on S3 or on BigQuery."
---

# Consume one contract from another

**Time:** 10 minutes · **Skill:** familiarity with the contract YAML shape

A Silver or Gold data product builds on upstream products rather than raw sources. The downstream contract names each upstream in `consumes[]`, and an embedded-SQL build on the DuckDB engine reads it by the name of the exposed table. Your SQL never repeats the upstream's path, and the same SQL reads the upstream's local file, S3 prefix or BigQuery table depending on `--env`.

This recipe builds a chain on CLI 0.18.1: two Bronze products and one Silver product that joins them. The commands and outputs up to the end of [How a consumes entry is read](#how-a-consumes-entry-is-read) are from a local run.

**Prerequisite:** the local DuckDB engine, from `pip install "data-product-forge[local]"`. Without it, `fluid apply --mode amend-and-build` fails with `No module named 'duckdb'`.

## The workspace

```text
northwind/
├── fluid.workspace.yaml
├── bronze/
│   ├── crm_orders/
│   │   ├── contract.fluid.yaml
│   │   └── data/orders.csv
│   └── crm_customers/
│       ├── contract.fluid.yaml
│       └── data/customers.csv
└── silver/
    └── orders_enriched/
        └── contract.fluid.yaml
```

`fluid init` writes `fluid.workspace.yaml` at the project root. Its location is what the build uses to find upstreams, and an empty file works. The upstream contracts must be named `contract.fluid.yaml` (or `.json`): a file with another name, such as `bronze.crm_orders.fluid.yaml`, is not found.

```yaml
# fluid.workspace.yaml
schema_version: 1
kind: WorkspaceConfig
workspace:
  name: northwind
  provider: local
```

### Upstream: `bronze/crm_orders/contract.fluid.yaml`

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: bronze.crm_orders
name: CRM orders
metadata:
  layer: Bronze
  productType: SDP
  owner:
    team: data-platform
    email: data-platform@example.com
builds:
  - id: ingest_orders
    pattern: acquisition
    engine: duckdb
    properties:
      source:
        kind: filesystem
        mode: full_refresh
        connection:
          uri: data/orders.csv
        reader:
          format: csv
        streams:
          - orders
      sink:
        format: parquet
    outputs:
      - orders
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
        - { name: order_id, type: BIGINT }
        - { name: customer_id, type: VARCHAR }
        - { name: amount_cents, type: BIGINT }
        - { name: created_at, type: TIMESTAMP }
```

```csv
order_id,customer_id,amount_cents,created_at
1001,c-001,4999,2026-09-01 10:15:00
1002,c-002,1250,2026-09-02 08:30:00
1003,c-001,830,2026-09-03 17:45:00
1004,c-003,15900,2026-09-04 12:00:00
```

`bronze/crm_customers/contract.fluid.yaml` has the same shape: `id: bronze.crm_customers`, a stream `customers` read from `data/customers.csv`, an expose `customers` landing at `out/customers.parquet`, and the schema `customer_id VARCHAR`, `region VARCHAR`, `segment VARCHAR`.

```csv
customer_id,region,segment
c-001,EMEA,enterprise
c-002,AMER,smb
c-003,EMEA,smb
```

### Downstream: `silver/orders_enriched/contract.fluid.yaml`

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: silver.orders_enriched
name: Orders enriched
metadata:
  layer: Silver
  productType: ADP
  owner:
    team: data-platform
    email: data-platform@example.com
consumes:
  - productId: bronze.crm_orders
    exposeId: orders
  - productId: bronze.crm_customers
    exposeId: customers
builds:
  - id: enrich
    pattern: embedded-logic
    engine: duckdb
    properties:
      sql: |
        SELECT o.order_id,
               o.amount_cents,
               c.region,
               c.segment
        FROM orders o
        LEFT JOIN customers c USING (customer_id)
    outputs:
      - orders_enriched
exposes:
  - exposeId: orders_enriched
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: out/orders_enriched.parquet
    contract:
      schema:
        - { name: order_id, type: BIGINT }
        - { name: amount_cents, type: BIGINT }
        - { name: region, type: VARCHAR }
        - { name: segment, type: VARCHAR }
```

A `consumes[]` entry is `productId` and `exposeId` (plus the optional fields in [Fields on a consumes entry](#fields-on-a-consumes-entry)). The SQL names the upstream tables `orders` and `customers`: the `exposeId`s. There is no `{{ alias }}` templating and no `alias:` key.

## Run the chain

Run each command from the contract's own directory: the Bronze contracts read `data/*.csv` relative to the working directory. Land the upstreams first, then the downstream:

```bash
cd bronze/crm_orders    && fluid apply contract.fluid.yaml --mode amend-and-build --yes
cd ../crm_customers     && fluid apply contract.fluid.yaml --mode amend-and-build --yes
cd ../../silver/orders_enriched && fluid apply contract.fluid.yaml --mode amend-and-build --yes
```

`--mode amend-and-build` is what runs the builds; the default `amend` mode does not. The downstream apply prints what it resolved:

```text
🔷 Build 'enrich' (embedded-SQL / local DuckDB)
   ⬅ consumes bronze.crm_orders/orders as view "orders":
<workspace>/bronze/crm_orders/out/orders.parquet
   ⬅ consumes bronze.crm_customers/customers as view "customers":
<workspace>/bronze/crm_customers/out/customers.parquet
     (no run record or lineage event on this path: the resolved inputs are
listed here and in runtime/out/local_apply_log.jsonl)
   ✅ Completed in 0.08s — 1 action(s) executed
   📁 <workspace>/silver/orders_enriched/out/orders_enriched.parquet
```

The Parquet file holds these rows, in no guaranteed order (the SQL has no `ORDER BY`):

```text
(1001, 4999, 'EMEA', 'enterprise')
(1002, 1250, 'AMER', 'smb')
(1003, 830, 'EMEA', 'enterprise')
(1004, 15900, 'EMEA', 'smb')
```

```bash
fluid verify contract.fluid.yaml     # from silver/orders_enriched: columns and row count of the landed file
```

### If the upstream has not landed

Run the downstream first and the build stops before it writes anything:

```text
   ❌ Failed: 1 action(s) failed
      Input file not found: <workspace>/bronze/crm_orders/out/orders.parquet
      (if a consumes input above does not exist, its upstream has not landed
there yet: build bronze.crm_customers, bronze.crm_orders first, with the same
--env)
```

`consumes[]` does not order the applies. You apply the upstreams first, in your own pipeline or in the order of your CI jobs.

## How a consumes entry is read

On the DuckDB engine (`local`, `duckdb` or unset `execution.runtime.platform`), each `consumes[]` entry that the SQL reads becomes a view named by its `exposeId`.

- **Which contract.** The one declaring `id: <productId>` under the nearest directory above the downstream contract that holds `fluid.workspace.yaml`, plus every root in `FLUID_UPSTREAM_CONTRACTS`. The search goes four directories deep for `contract.fluid.yaml` or `contract.fluid.json` and skips VCS, virtualenv and output directories such as `dist/`, `runtime/` and `.fluid/`. An id declared by two files fails the build and names both.
- **Which entries.** An entry is read when the SQL names a relation equal to its `exposeId`, compared case-insensitively and as DuckDB's parser reads the query; a CTE of that name does not count. An entry the SQL does not read is lineage only: it is listed in the build output and not resolved.
- **Which binding.** The upstream is loaded with the same `--env` overlay as this run, so `--env aws` reads the upstream's `aws` binding. Overlays patch `exposes[].binding` only; the SQL is the same on every target.
- **Which relation.** A local binding reads its `location.path`, relative to the upstream contract's directory. An S3 binding with `location.bucket` and `location.path` reads `s3://<bucket>/<path>/*.<ext>`. A BigQuery table binding is read through the BigQuery API (see [The same chain on S3 and BigQuery](#the-same-chain-on-s3-and-bigquery)).
- **Explicit inputs win.** A `builds[].properties.parameters.inputs` entry whose `name` equals the `exposeId` binds that view by hand, and the `consumes[]` entry is not resolved at all. This is how you bind a federated upstream, or one this engine cannot read.

The sandbox that confines the SQL, and the directories the resolved upstreams add to it, are in [DuckDB sandbox for contract SQL](../advanced/duckdb-sandbox.md).

### What fails, and where

An entry the SQL reads that cannot be resolved fails the build before any SQL runs. Each failure below is a real message from 0.18.1.

| Situation | What you see |
|-----------|--------------|
| `productId` matches no contract in the workspace (here a typo, `bronze.crm_custmers`) | `consumes bronze.crm_custmers/customers: no contract in the workspace declares id 'bronze.crm_custmers'`, then `Looked in <workspace> (the workspace root), four directories deep, in files named contract.fluid.yaml or contract.fluid.json` |
| No `fluid.workspace.yaml` in the contract's directory or above, and `FLUID_UPSTREAM_CONTRACTS` unset | `Looked in nowhere: no fluid.workspace.yaml in <dir> or any directory above it, and FLUID_UPSTREAM_CONTRACTS is not set` |
| The entry names the contract's own id | `the contract consumes its own id`: it would read the file this build is about to overwrite |
| The entry is not read by the SQL | Not a failure. `lineage only, the SQL reads no relation named 'tickets', so it is not resolved`, and a `local_consumes_not_bound` warning |

Each of the first three also tells you the way out: check the `productId`, keep the upstream under the directory holding `fluid.workspace.yaml`, add its repository to `FLUID_UPSTREAM_CONTRACTS`, or bind the name by hand with `parameters.inputs`.

`fluid validate` and `fluid plan` do not resolve `consumes[]`. The contract above with `bronze.crm_custmers` in it passes both, and fails only at `fluid apply --mode amend-and-build`. What `fluid validate` also applies is the composition rule: a contract with `metadata.productType: SDP` (or `layer: Bronze`) that declares `consumes[]` is rejected when the consumed `productId` is one validate can find in the workspace, with `composition rule: SDP ... does not accept upstream products`. A `productId` it cannot find is not reported (it appears only with `-v`). See [Product Types](../data-products/product-type.md#composition-rules).

### Fields on a consumes entry

`productId` and `exposeId` are required. The schema also accepts `versionConstraint`, `qosExpectations`, `requiredPolicies`, `purpose`, `tags` and `labels`, and rejects other keys, including `product`, `expose` and `alias`. Under the 0.7.6 preview, `upstreamWorkspace` and `upstreamDigest` are added (see [Pin a federated upstream](#pin-a-federated-upstream)).

An entry names a logical address only. Whether anything is generated from it depends on the engine:

- **dbt** (`engine: dbt`): `fluid generate transformation` emits the entries as `models/sources.yml`.
- **sql, spark, glue, dataform, dataflow and other engines**: `fluid generate transformation` logs a `consumes_not_wired` warning, because those generators never read `consumes[]`. Point the build at the upstream yourself.
- **Embedded-SQL on DuckDB**: read at apply time, as above.

## The same chain on S3 and BigQuery

Add one overlay per environment beside each contract, as in [Per-environment overlays](./per-environment-overlays.md), and run the downstream with `--env`. The upstream's overlay supplies its binding, and the downstream's own overlay supplies where the result lands. The SQL does not change.

What the build reads and where it lands depends on the downstream's first expose binding. This section follows the 0.18.1 source and forge-cli's apply reference; the local chain above is the part run end to end here.

**Reads.**

- **Local:** the upstream's `location.path`, relative to the upstream's directory.
- **S3:** `s3://<bucket>/<path>/*.<ext>`, the prefix the DuckDB acquisition runner writes into.
- **BigQuery:** a GCP `bigquery_table` upstream is read through the BigQuery API into a staging Parquet file under the build's `.fluid/staging/<build>/inputs/`; the view reads that file and the file is removed after the build. A `TIMESTAMP` reads as a DuckDB `TIMESTAMP` holding the UTC wall clock, the same value the local and S3 targets read.
- **Any other platform** (another warehouse, a stream, a GCS or Azure prefix): `UnreadableBindingError`, naming the platform.
- A `{{ env.X }}` in the upstream binding with `X` unset is an error, not an empty string.

**Lands.** The result is written to the downstream's first expose.

| First expose binding | What happens |
|----------------------|--------------|
| `local` | Written as a local file |
| `aws`, with `location.bucket` and `location.path`, format parquet, csv or json | Written to `s3://<bucket>/<path>/<table or exposeId>.<ext>`, inside the Glue table's location, so `fluid verify --env aws` counts it |
| `gcp` with `bigquery_table` | Written as Parquet under `.fluid/staging/<build>/`, then one load job moves it into the table with `WRITE_TRUNCATE` and `CREATE_NEVER`, using the table's own schema. A failed or short load fails the build. The load is recorded as a run, so `fluid verify` holds the table's row count to the rows landed |

Refused before any SQL runs, as `EmbeddedSqlLandingError`:

- A `gs://` or other non-S3 URI, a GCS bucket, or an Azure, Snowflake or Databricks binding as the landing.
- A landing that resolves to one of the build's own inputs: a BigQuery table the build reads, or an S3 object inside a prefix it reads. The load replaces the table, so it would overwrite another product's rows.
- A further expose in the build's `outputs` bound to a cloud store or warehouse: this path lands only the first expose.

**Masking is not applied on this path.** An expose with `policy.privacy.masking` is refused with `MaskingNotAppliedError`:

```text
   ❌ expose 'orders_enriched' declares policy.privacy.masking, which the
embedded-SQL landing path does not apply yet
      why: This build writes the query result as the SQL returns it, so region
would land in cleartext.
      fix: Land this expose through an engine that enforces its masking, or
write the masking into properties.sql and declare the columns as they then land.
```

This covers BigQuery landings too. The DuckDB acquisition runner is the engine that applies masking; see [Tag PII in your schema](./tag-pii.md).

**Sovereignty.** When the contract declares `sovereignty` and the build reads or loads a BigQuery table, `fluid validate` holds the locations the build actually uses to it (`EmbeddedSqlSovereigntyError`). Every BigQuery binding must name its region, because without one the load is placed in `US`. The landing must be outside `deniedRegions`, inside `allowedRegions` and in the declared `jurisdiction`. See [Sovereignty](../concepts/sovereignty.md).

**Credentials.** BigQuery reads and loads use Application Default Credentials: gcloud ADC, an attached service account, or a Workload Identity Federation `external_account` file in `GOOGLE_APPLICATION_CREDENTIALS`. With `BIGQUERY_EMULATOR_HOST` set they go to that emulator with anonymous credentials. S3 access uses the ambient AWS credential chain and the binding's region; `AWS_ENDPOINT_URL_S3` or `AWS_ENDPOINT_URL` point it at an S3-compatible store.

On 4 October 2026, Silver and Gold products were built this way against real BigQuery with `--env gcp` overlays, each reading its upstreams from BigQuery.

## Pin a federated upstream

When the upstream lives in another team's workspace, you cannot walk to it. Set `fluidVersion: "0.7.6"`: that schema is a preview (0.7.5 is the latest stable) and it adds two keys to a `consumes[]` entry:

- `upstreamWorkspace`: the `id` of a workspace declared in `federation/upstreams.yaml`.
- `upstreamDigest`: `sha256:<64 hex>`, the digest of the upstream contract this product was composed against. `upstreamWorkspace` requires it.

Under `fluidVersion: "0.7.5"` both keys are rejected: `consumes[0]: Additional properties are not allowed ('upstreamDigest', 'upstreamWorkspace' were unexpected)`. Under 0.7.6, `upstreamWorkspace` without `upstreamDigest` fails with `'upstreamDigest' is a dependency of 'upstreamWorkspace'`.

Declare the workspaces in `federation/upstreams.yaml`, relative to the directory you run `fluid apply` from:

```yaml
workspaces:
  - id: telco-billing
    kind: git_registry            # git_registry | catalog | http_registry
    endpoint: https://git.telco-billing.example/mesh.git
    auth:
      mode: github_token          # github_token | basic | oidc | none
      secret_ref: GITHUB_TOKEN
    product_path_template: "{product_id}/contract.fluid.yaml"
```

Compute the digest from a copy of the upstream contract:

```bash
fluid contract digest bronze/crm_customers/contract.fluid.yaml
```

```text
sha256:1a030aedfaab1eb340a772c1b433ba150ceab87fb13311ab1e0cd5af6834c963
```

`fluid contract digest --json` prints `{"digest": ..., "path": ...}`. The digest is over the parsed, canonical contract, not its bytes, so reformatting the upstream does not change it. Then pin it:

```yaml
fluidVersion: "0.7.6"
consumes:
  - productId: telco.invoices
    exposeId: invoices
    upstreamWorkspace: telco-billing
    upstreamDigest: sha256:1a030aedfaab1eb340a772c1b433ba150ceab87fb13311ab1e0cd5af6834c963
```

`fluid apply` fetches each federated upstream's live digest, caches it in `.fluid/federation/<workspace>.digest-cache.json`, and compares. The cache has no expiry. Measured on 0.18.1 with the workspace above, unreachable:

```text
apply_consumes_drift: 1 federated consumes[] entry could not be confirmed in sync (1 unreachable). Applying anyway.
  consumes[0] telco-billing/telco.invoices [unreachable]: Could not reach federated upstream 'telco-billing' to verify the pin (FederationFetchError). The pinned digest was NOT checked -- this is not a statement that the upstream is unchanged.
```

- **The gate warns; it does not abort.** `apply_consumes_drift` is logged at warning level and the apply continues, whether the upstream drifted, was unreachable, or has no pin. Check for it in your pipeline's log if a pin matters to you. `--no-verify-federation` skips the check and logs that it was skipped.
- **As of 0.18.1 the gate does not run for build modes.** The same contract applied with `--mode amend-and-build` printed no federation line at all, because that mode hands off to the build runner before the gate. `--mode amend`, the default, runs it.
- **The embedded-SQL build does not read federated upstreams for you.** It looks a `productId` up in the workspace and the `FLUID_UPSTREAM_CONTRACTS` roots. If the SQL reads a federated entry's `exposeId`, bind that name by hand with `parameters.inputs`; an entry the SQL does not read is lineage only, as in the apply above.
- `FLUID_FEDERATION_HOST_ALLOWLIST` (comma-separated host suffixes) permits a federation endpoint on a private address; without it, an endpoint that resolves to a private, loopback or metadata address is refused. `FLUID_FEDERATION_TIMEOUT_SECONDS` bounds each fetch (default 30).
- **Digests of `git_registry` upstreams changed in 0.15.0.** A pin made on 0.14.1 reads as drift: recompute it with `fluid contract digest` and clear `.fluid/federation/`.

## Scaffold a downstream contract

`fluid forge --from-product` pre-fills `consumes[]` from existing products:

```bash
fluid forge --from-product bronze.crm_orders --from-product bronze.crm_customers
```

The command is AI-assisted and the output is a draft: run `fluid validate` on it, and check the SQL reads each upstream by its `exposeId`. See [`fluid forge`](../cli/forge.md#from-product-—-composition).

## See also

- [Composing a contract with `$ref`](../concepts/contract-refs.md): splitting one contract across files, the other kind of reference
- [DuckDB sandbox for contract SQL](../advanced/duckdb-sandbox.md): what the build's SQL may read, and `FLUID_DUCKDB_ALLOWED_DIRS`
- [Per-environment overlays](./per-environment-overlays.md): the `--env` mechanism the upstream binding follows
- [Product Types](../data-products/product-type.md#composition-rules): what can consume what
- [Consume a data product](../data-products/consume.md): the three ways to consume a published product
- [Builds, Exposes, Bindings](../concepts/builds-exposes-bindings.md): the contract surface
- [`fluid apply`](../cli/apply.md): build modes and the safety flags
- [Environment variables](../advanced/environment-variables.md): `FLUID_UPSTREAM_CONTRACTS`
