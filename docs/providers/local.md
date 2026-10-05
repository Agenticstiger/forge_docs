# Local Provider

**Status:** ✅ Production Ready  
**Docs Baseline:** CLI `0.18.1`<br>
**Engine:** DuckDB (1.5.0 or later)

> **Why it matters**
> Build and test a real data product on your laptop, with no cloud account and no credentials, then ship the same contract to a cloud.
> `binding.platform: local` runs the build's SQL on an embedded DuckDB and writes each output to a file. Moving to BigQuery, Snowflake or AWS later means editing that expose's `binding`, not the rest of the contract.

---

## Quick start

### Install

```bash
pip install "data-product-forge[local]"
```

The `local` extra brings DuckDB (`duckdb>=1.5.0`) and pandas. Without it, a build fails with `duckdb not installed. Install it with: pip install duckdb`.

### A minimal contract

Put the contract and its data in one directory:

```text
my-product/
├── contract.fluid.yaml
└── data/
    └── customers.csv      # customer_id,name,amount
```

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: example.local_analytics_v1
name: Local Analytics
domain: example

metadata:
  layer: Bronze
  owner:
    team: data-analytics
    email: team@company.com

builds:
  - id: build_customers
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT customer_id, name, amount
        FROM customers_raw
        WHERE amount >= 100
      parameters:
        inputs:
          - name: customers_raw
            path: data/customers.csv
            format: csv
    outputs:
      - customers

exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: runtime/out/customers.parquet
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
        - name: name
          type: STRING
        - name: amount
          type: INTEGER
```

Run it from the contract's directory:

```bash
cd my-product
fluid apply contract.fluid.yaml --yes
fluid verify contract.fluid.yaml
```

```text
...
✅ Data product deployed successfully
 Actions Applied  3
...
📋 Verifying: customers
   Format: parquet
...
   📊 Rows: 2

   🔍 Dimension 1: Schema Structure
      ✅ PASS - All 3 declared columns present
```

On the local provider a plain `fluid apply` runs the build's SQL; no `--mode amend-and-build` is needed. The result lands at `runtime/out/customers.parquet`. `--provider local` is optional: the provider comes from `binding.platform`.

---

## Inputs: `parameters.inputs`

`builds[].properties.parameters.inputs` declares which file backs which name the SQL reads:

| Key | Meaning |
|---|---|
| `name` | The view name the SQL uses (`customers_raw` above) |
| `path` | The file; a glob such as `data/sales_*.csv` works |
| `format` | `csv`, `parquet` or `json`. Read by a plain `fluid apply`; `--mode amend-and-build` picks the reader from the file extension and ignores it |
| `schema` | Optional column types for the view |

`fluid apply` registers each entry as a DuckDB view before the SQL runs. `fluid generate transformation` writes the same statements to `00_inputs.sql` next to the build's SQL, so the generated script runs on its own:

```sql
-- customers_raw <- data/customers.csv
CREATE OR REPLACE VIEW customers_raw AS SELECT * FROM read_csv_auto('data/customers.csv', AUTO_DETECT:=true, DELIM:=',');
```

Reading a file directly in the SQL (`SELECT * FROM read_csv_auto('data/customers.csv')`) also works, inside the limits below. A declared input is also bound by the script `fluid generate transformation` writes.

### Reading another product

A `consumes[]` entry the SQL names by its `exposeId` is bound to the upstream product's output. A `local` upstream is read at its `location.path`, relative to the upstream contract's directory; the upstream contract is found under the nearest `fluid.workspace.yaml` or in `FLUID_UPSTREAM_CONTRACTS`. A `parameters.inputs` entry with the same `name` wins over that lookup. [`fluid apply`](../cli/apply.md) lists the discovery rules. When a `consumes[]` entry is neither resolved nor declared, apply logs `local_consumes_not_bound`.

---

## Where paths resolve

| Path | Resolved against |
|---|---|
| An expose's `binding.location.path` (the output) | the contract's directory (since 0.16.3) |
| A `parameters.inputs[].path` and a path inside the SQL | the working directory |
| `runtime/out/local_apply_log.jsonl`, `runtime/apply_report.html` | the working directory |

So run `fluid apply` from the contract's directory. From anywhere else the output still lands next to the contract, but the inputs are looked up in the working directory and the build fails, with `Input file not found: data/customers.csv` for a declared input, or a sandbox refusal for a path in the SQL.

::: warning A failed local build can leave a placeholder file
As of 0.18.1, when the build's SQL fails, the provider still writes a 24-byte placeholder (`id,value` / `1,materialized`, not Parquet) at the output path, although the apply exits 1. A later `fluid verify` then reports `No magic bytes found`. Delete the file, or re-run the build, before trusting the output.
:::

A `{{ env.NAME }}` placeholder in an output path resolves the same way in `fluid apply`, `fluid verify` and `fluid diff`, so chained products can share a data directory:

```yaml
binding:
  platform: local
  format: parquet
  location:
    path: "{{ env.DATA_DIR }}/customers.parquet"
```

A relative contract path that climbs out of the working directory (`fluid apply ../other/contract.fluid.yaml`) is refused with `ERR_PATH_TRAVERSAL_DETECTED`.

---

## What build SQL can read (since 0.18.0)

Contract SQL runs in a DuckDB sandbox. It can read and write the contract's directory, the FLUID workspace around it, `./runtime`, the run's scratch directory, the declared inputs and outputs inside those directories, and the directories an operator lists in `FLUID_DUCKDB_ALLOWED_DIRS`. Refused, with the build failing:

| SQL | What you see |
|---|---|
| A path outside the allowed directories, an absolute path elsewhere, `../` escapes | `Permission Error: Cannot access file ... DuckDB refused it: contract SQL may only read and write the locations the contract declares and its own directory (...)` |
| A URL: `read_csv('https://...')` | `File https://... requires the extension httpfs to be loaded` |
| `SET` or `PRAGMA` that changes a setting | `Cannot change configuration option "threads" - the configuration has been locked` |
| Functions DuckDB used to autoload: `read_xlsx`, `sqlite_scan`, `delta_scan`, `iceberg_scan` | not in the catalog |

Move remote data into the contract's directory with an acquisition build first, or declare it. See [DuckDB sandbox](../advanced/duckdb-sandbox.md) and the [0.18.0 release notes](../RELEASE_NOTES_0.18.0.md).

---

## What a run leaves behind

```text
my-product/
├── contract.fluid.yaml
├── data/customers.csv
├── .fluid/run-id.txt
└── runtime/
    ├── apply_report.html          # the execution report
    └── out/
        ├── customers.parquet      # the expose's output
        ├── local_apply_log.jsonl  # one line per action
        └── preview_<n>.csv        # a preview of the build's result
```

`runtime/out/local_apply_log.jsonl` records each action's status, the files it wrote and its row count:

```json
{"i": 0, "status": "ok", "op": "load_data", "table": "customers_raw", "path": "data/customers.csv", "rows": 3, "format": "csv"}
{"i": 1, "status": "ok", "op": "sql", "written": ["runtime/out/preview_1.csv"], "rows": 2, "inputs": [{"table": "customers_raw", "path": "data/customers.csv", "format": "csv", "options": {}}]}
{"i": 2, "status": "ok", "op": "materialize", "dst": ".../runtime/out/customers.parquet", "source_table": "result_build_customers", "format": "parquet"}
```

A resolved `consumes[]` upstream is logged there with its `productId`, `exposeId` and `uri`. Error text in the log, the build output and retry log lines has the value of every credential-named `{{ env.X }}` the build uses redacted.

Each apply runs in a temporary DuckDB session, so no database file outlives the run. The durable result is the file at each expose's `location.path`. Add `runtime/` and `.fluid/` to `.gitignore`.

### Querying the output

```python
import duckdb

duckdb.sql("SELECT * FROM 'runtime/out/customers.parquet' WHERE amount > 100").show()
```

```bash
duckdb -c "SELECT * FROM 'runtime/out/customers.parquet' LIMIT 10"
```

---

## What `fluid verify` checks on a local file

For a local output, `fluid verify` checks column names, the row count, and the shape of masked columns. Data types, constraints and location are not checked. A missing or unreadable file is an error and fails the run.

::: warning Masking on a local embedded-SQL build
As of 0.18.1, an embedded-SQL build that lands a local file does not apply `policy.privacy.masking` and does not refuse it either: the column lands in cleartext and `fluid apply` exits 0. `fluid verify` reports the column as CRITICAL (`masked column(s) did not land treated`), and only `fluid verify --strict` exits 1. Masking is applied by the DuckDB acquisition runner; see [source-aligned acquisition](../advanced/source-aligned-acquisition.md).
:::

---

## Use in CI

```yaml
# .github/workflows/test.yml
- name: Build and check the product
  working-directory: my-product
  run: |
    pip install "data-product-forge[local]"
    fluid validate contract.fluid.yaml
    fluid apply contract.fluid.yaml --yes
    fluid verify contract.fluid.yaml --strict
```

---

## Cloud Migration

To move an expose to a cloud, change its `binding`: the `platform`, and the `format` and `location` that go with it. The rest of the contract stays.

```yaml
exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: gcp                 # was: local
      format: bigquery_table        # was: parquet
      location:                     # was: path
        project: my-project-id
        dataset: analytics
        table: customers
        region: europe-west3
```

Changing only `platform` is not enough. `fluid validate` then warns: `platform=gcp resolves to no GCP resource ... fluid generate iac and fluid apply would emit nothing for this port`. Rows reach BigQuery when the build runs with `--mode amend-and-build`; see [Loading data](./gcp.md#loading-data). The [switch-clouds recipe](../recipes/switch-clouds.md) shows the full diff, and [per-environment overlays](../recipes/per-environment-overlays.md) keep `local` and cloud bindings side by side.

::: warning `--provider` does not retarget a contract *(since 0.15.0)*
`fluid apply contract.yaml --provider gcp` on a `platform: local` contract is rejected before anything is written, on both `fluid apply` and `fluid generate iac`. The flag disambiguates a contract that spans clouds or declares none; retargeting is done by editing `binding`.
:::

---

## Next Steps

- [Local Walkthrough](../walkthrough/local.md): a complete tutorial
- [GCP Provider](./gcp.md): the same contract on BigQuery
- [`fluid apply`](../cli/apply.md): modes and what a build reads
- [DuckDB sandbox](../advanced/duckdb-sandbox.md)
