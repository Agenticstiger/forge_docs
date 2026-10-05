---
title: "Recipe — add a quality rule"
description: "Declare dq.rules on an expose, run them with fluid test, and gate your pipeline on the exit code when a column has nulls, duplicates, out-of-range values or stale data."
---

# Recipe: add a quality rule

**Time:** 5 minutes · **Audience:** anyone with an existing contract and data already landed

**Prerequisite:** the local DuckDB engine, from `pip install "data-product-forge[local]"`. Without it, `fluid apply --mode amend-and-build` fails with `No module named 'duckdb'`.

## Problem

You have a working contract and no check that the data it describes is any good: a null `customer_id`, a duplicated `order_id`, a negative `total`, a table nobody has written to since last month.

## Solution

Declare `dq.rules` on the expose and run `fluid test`. `fluid test` is the gate: it exits non-zero when a rule at `error` or `critical` severity fails. `fluid apply` does not evaluate `dq.rules` (see [Where the rules run](#where-the-rules-run)).

The example below runs as written on the local provider. It lands a CSV into a Parquet file with a DuckDB acquisition build, then tests the landed file.

```text
orders/
├── contract.fluid.yaml
└── data/
    └── orders.csv
```

```csv
order_id,customer_id,total,order_ts,status
o-1001,c-001,49.99,2026-09-01 10:15:00,paid
o-1002,c-002,12.50,2026-09-02 08:30:00,paid
o-1003,,8.30,2026-09-03 17:45:00,refunded
o-1003,c-001,-159.00,2026-09-04 12:00:00,chargeback
```

Row three has no `customer_id`, rows three and four share an `order_id`, row four has a negative `total` and a `status` the rules do not allow, and every timestamp is old.

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: silver.sales.customer_orders
name: Customer orders
metadata:
  layer: Silver
  productType: ADP
  owner:
    team: data-platform
    email: data-platform@example.com
builds:
  - id: load_orders
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
          - customer_orders
      sink:
        format: parquet
    outputs:
      - customer_orders
exposes:
  - exposeId: customer_orders
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: out/customer_orders.parquet
    contract:
      schema:
        - { name: order_id, type: VARCHAR }
        - { name: customer_id, type: VARCHAR }
        - { name: total, type: DOUBLE }
        - { name: order_ts, type: TIMESTAMP }
        - { name: status, type: VARCHAR }
      dq:
        rules:
          # 1. Every row has a customer_id.
          - id: customer_id_complete
            type: completeness
            selector: customer_id
            threshold: 1.0
            operator: ">="
            severity: error

          # 2. order_id is unique.
          - id: order_id_unique
            type: uniqueness
            selector: order_id
            threshold: 1.0
            operator: ">="
            severity: error

          # 3. The newest order_ts is less than an hour old.
          - id: orders_freshness
            type: freshness
            selector: order_ts
            window: PT1H
            severity: warn

          # 4. Every row satisfies total >= 0.
          - id: total_non_negative
            type: accuracy
            selector: total
            threshold: 0
            operator: ">="
            severity: error

          # 5. status is one of the listed values.
          - id: status_known
            type: valid_values
            selector: status
            description: "status valid values: paid, refunded."
            severity: warn
```

Land the data, then test it:

```bash
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --mode amend-and-build --yes
fluid test contract.fluid.yaml
```

`fluid validate` checks the rule syntax only; it does not read data. `--mode amend-and-build` is what runs the acquisition build; the default `amend` mode does not run builds. `fluid test` prints one row per check:

```text
┃ #    ┃ Result ┃ Check                  ┃ Details                             ┃
│ 5    │ ✅     │ Schema fields          │ All fields match                    │
│ 6    │ ✅     │ Row count / SLA        │ OK                                  │
│ 7    │ ❌     │ Quality tests          │ customer_id_complete — completeness │
│      │        │                        │ for 'customer_id' is 75.00%;        │
│      │        │                        │ order_id_unique — uniqueness for    │
│      │        │                        │ 'order_id' is 75.00%;               │
│      │        │                        │ total_non_negative — min value of   │
│      │        │                        │ 'total' is -159.0  (+2 non-gating   │
│      │        │                        │ rule failure(s))                    │
...
❌ 6 passed  |  1 warned  |  1 failed  |  3 error(s)  |  2 warning(s)
Data-quality rules: 0/5 passed
```

The exit code is 1. The two `warn` rules (`orders_freshness`, `status_known`) are the "non-gating" failures: they are counted, not gating. `fluid test --output json` lists every rule with its `expected` and `actual`:

```json
{"severity": "error", "category": "quality", "message": "total_non_negative — min value of 'total' is -159.0", "path": "exposes[0].contract.dq.rules.total_non_negative", "expected": ">= 0", "actual": "-159.0"}
```

## Severity and exit code

| Severity | `fluid test` | With `fluid test --strict` |
|----------|--------------|----------------------------|
| `critical` | Exit 1 | Exit 1 |
| `error` | Exit 1 | Exit 1 |
| `warn` | Reported, exit 0 | Exit 1 |
| `info` | Does not fail the run | Does not fail the run |

Measured on 0.18.1: with only the two `warn` rules failing, `fluid test` exits 0 and `fluid test --strict` exits 1. With `orders_freshness` raised to `critical`, `fluid test` exits 1. With `status_known` lowered to `info` and `orders_freshness` still `warn`, `fluid test` exits 0 and `--strict` exits 1, because the `warn` rule still fails.

## Where the rules run

- **`fluid test` evaluates them.** On a local contract it reads the landed file through DuckDB. The BigQuery and Snowflake validation providers call the same rule engine; the example here ran on local only.
- **`fluid apply` does not.** Applying the data above, with its null, its duplicate and its negative `total`, completes with exit 0. To block a promotion, put `fluid test` in CI after the step that lands the data and before the step that publishes or promotes it, and stop on its exit code.
- **`fluid test --engine soda`** renders the same rules as SodaCL and runs a locally installed `soda scan`. It exits non-zero if a declared rule has no SodaCL equivalent.
- An acquisition build also has its own pre-land `quality.gates`. Those run while the data is landing, before it is written; see [Quality gates](../advanced/source-aligned-acquisition.md#quality-gates).

## Rule types

`type` takes one of eight values in the 0.7.5 schema. The native engine executes six:

| `type` | What it checks | Notes |
|--------|----------------|-------|
| `completeness` | The fraction of rows where `selector` is not null, compared with `threshold` using `operator` | Without `threshold`, the fraction must be 1.0 |
| `uniqueness` | Distinct non-null values of `selector` divided by non-null values, compared the same way | Nulls are not counted |
| `accuracy` | Every non-null value of `selector` satisfies `operator threshold` | `>=` and `>` check the minimum, `<=` and `<` the maximum, `==` and `!=` count violating rows |
| `valid_values` | No non-null value of `selector` falls outside an allowed list | The schema has no key for the list: write it in `description` as `<column> valid values: a, b, c.`. A `valid_values` rule with no list fails instead of passing |
| `freshness` | Age of the newest `selector` value is no more than `window` | `window` is an ISO 8601 duration (`PT1H`, `P2D`) or shorthand (`6h`, `2d`). An unparseable window fails the rule |
| `anomaly_detection` | With `selector: "*"`, the row count compared with `threshold` | This is a row-count bound, not a statistical detector. With a column selector it behaves as `accuracy` |

`schema` and `drift_detection` are accepted by the schema but not executed by the native engine. They are reported as failures at the severity you declared, with the message "this gate is NOT being enforced". `--engine soda` reports them as unmapped too.

A rule the engine cannot evaluate is reported as a failure, not skipped. Measured on 0.18.1:

- **No `selector`.** Every type needs one, `freshness` included. The rule fails with "missing 'selector' (column name)".
- **`valid_values` with no list**, or a `freshness` window that does not parse, fails with a message naming the problem.

`fluid validate` rejects keys the schema does not define. A `dqRule` takes `id`, `type`, `selector`, `threshold`, `operator`, `window`, `severity`, `description`, `tags` and `labels`; a `validValues:` key fails with "Additional properties are not allowed". The failure message of a `valid_values` rule with no list suggests a `validValues` list as an alternative; as of 0.18.1 only the `description` form passes `fluid validate`. Nor is there a `where:` clause. For a rule that applies to a subset of rows, filter in the build's SQL; see [Quality, SLAs and lineage](../concepts/quality-sla-lineage.md).

## Make the clean file pass

Replace `data/orders.csv` with rows that satisfy rules 1 to 4 and run the same two commands. The two `warn` rules still fail while the timestamps are old and `chargeback` is in the data; that is the point of `warn`:

```text
│ 7    │ ⚠️     │ Quality tests          │ orders_freshness — data is 2646099s │
│      │        │                        │ old, max allowed is 3600s; status   │
│      │        │                        │ valid values: paid, refunded. — 1   │
│      │        │                        │ invalid value(s) in 'status'        │
...
✅ 6 passed  |  2 warned  |  0 error(s)  |  2 warning(s)
Data-quality rules: 3/5 passed
```

## See also

- [Concepts: Quality, SLAs and lineage](../concepts/quality-sla-lineage.md): `qos`, lineage, and the rule shapes in context
- [`fluid test`](../cli/test.md): the flags, including `--output json` and `--engine soda`
- [`fluid verify`](../cli/verify.md): checks the deployed target against the contract's schema
