# `fluid test`

Check a contract against the resources it declares: the binding, the schema, the row count, and the `dq.rules` on each expose. Optionally publish the results.

## Syntax

```bash
fluid test CONTRACT [--env ENV] [--no-data] [--strict] [--output {text,json,junit}] [--output-file PATH]
```

## Example

Against the local provider, with an expose bound to `./out/orders.parquet` and two rules (`id_required`, a completeness rule at severity `error`, and `amount_not_negative`, an accuracy rule at severity `warn`):

```bash
fluid test contract.fluid.yaml
```

```text
╭───────────────────────────────── fluid test ─────────────────────────────────╮
│ ✅ Data Contract Test: bronze.shop.orders_v1                                 │
│ Version 0.0.0  |  Provider: local (DuckDB)                                   │
│ Duration: 0.23s  |  2026-10-05 03:19:59                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
┏━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ #    ┃ Result ┃ Check                  ┃ Details                             ┃
┡━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1    │ ✅     │ Schema syntax          │ Valid                               │
│ 2    │ ✅     │ Provider connection    │ OK                                  │
│ 3    │ ✅     │ Binding configuration  │ OK                                  │
│ 4    │ ✅     │ Resource exists        │ 1 exposed resource(s) found         │
│ 5    │ ⚠️     │ Schema fields          │ 1 warning(s)                        │
│ 6    │ ✅     │ Row count / SLA        │ OK                                  │
│ 7    │ ⚠️     │ Quality tests          │ amount_not_negative — min value of  │
│      │        │                        │ 'amount' is -45.25                  │
│ 8    │ ⚠️     │ Metadata / governance  │ 1 info/warning(s)                   │
└──────┴────────┴────────────────────────┴─────────────────────────────────────┘

✅ 5 passed  |  3 warned  |  0 error(s)  |  2 warning(s)  |  0.23s
Data-quality rules: 1/2 passed
```

The exit code is `0`: the one failing rule has severity `warn`. Change that rule's severity to `error` and the same run exits `1`. [Add quality rules](./tasks/add-quality-rules.md) walks through how each severity and rule type behaves.

The local provider reads the data with DuckDB. If the `duckdb` package is missing (`pip install 'data-product-forge[local]'` installs it), check 3 fails with `duckdb package is required for local validation`.

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay. |
| `--provider` | Override the provider (`gcp`, `snowflake`, `aws`, `local`). Like every provider name, it must be registered in your install. |
| `--project`, `--region` | Override the project / account ID or region from the contract. |
| `--server` | Provider connection string or identifier, such as a Snowflake account locator. |
| `--strict` | Exit `1` on any warning. In the example above `--strict` exits `1`. |
| `--no-data` | Skip live data validation: structure-only checks. Checks 4 to 7 print `not checked (--no-data)`. |
| `--output` | `text` (default), `json`, or `junit`. |
| `--output-file` | Write the report to a file instead of stdout. |
| `--no-cache` | Read the resource schema live instead of from the cache. |
| `--cache-ttl SECONDS` | Schema cache lifetime. Default `3600`. |
| `--cache-clear` | Clear the schema cache before running. |
| `--check-drift` | Compare against historical results. |
| `--publish URL` | Publish the results to a Data Mesh Manager / Entropy Data test-results endpoint, for example `https://api.entropy-data.com/api/test-results`. |
| `--engine` | Quality engine: `native` (default) runs forge's built-in checks; `soda` runs the same rules through Soda. |
| `--datasource` | Soda data source to run against. Required with `--engine soda`. |
| `--soda-config` | Path to Soda `configuration.yml`. Defaults to Soda's auto-discovery. |

## The schema cache

`fluid test` reuses a cached copy of the resource's schema for up to `--cache-ttl` seconds (3600 by default). As of 0.18.1, a column you drop from the data can stay in the cache. In a measured run, a product was rebuilt without its `order_date` column, and `fluid test` reported no problem until `--cache-clear` (or `--no-cache`) made it read the file again and fail with `Field 'order_date' is missing from actual schema`. After you change the data or the contract's schema, run `fluid test ... --no-cache`.

## Quality rules the native engine runs

The native engine evaluates each expose's `contract.dq.rules[]` against the data:

| Rule `type` | What it computes |
| --- | --- |
| `completeness` | Share of non-null values in the `selector` column, compared with `threshold` using `operator`. |
| `uniqueness` | Share of distinct values in the column. |
| `accuracy` | Compares the column's values with `threshold` using `operator`. |
| `valid_values` (alias `validity`) | Every value must be in the allowed list. The schema has no field for the list; write it in the rule's `description`, as `status valid values: paid, refunded.` A rule with no list checks nothing and says so. |
| `freshness` | Age of the newest timestamp in the `selector` column, compared with `window`. |
| `anomaly_detection` | Row-count check: `selector: '*'` means `COUNT(*)`, compared with `threshold`. |

`schema` and `drift_detection` are valid in the contract and are not implemented. The engine reports them as failures at the rule's own severity, with the message `this gate is NOT being enforced`, so a gate nobody runs cannot read as green. `--engine soda` does not map them either.

A rule's severity decides the result: `info` failures are recorded and count as passed, `warn` shows as a warning and exits `0`, and `error` and `critical` fail the run with exit `1`.

## Soda quality engine

`--engine soda` runs the contract's quality rules through [Soda](https://www.soda.io/) instead of the built-in checker:

```bash
fluid test contract.fluid.yaml --engine soda --datasource warehouse
fluid test contract.fluid.yaml --engine soda --datasource warehouse --output junit --output-file results.xml
```

- Forge renders the contract's quality rules to **SodaCL**, then shells out to the `soda` binary.
- The binary is resolved from `$SODA_EXECUTABLE`, then `PATH` — if neither resolves, the command fails with an install hint instead of a stack trace.
- `--datasource` names the Soda data source and is required in this mode. Without it the command exits with `--datasource is required when --engine soda is set`.
- `--output junit` writes JUnit XML that drops straight into a CI test report. A failing rule becomes a `<failure>` with `type="DataQualityFailure[warn]"` (or the rule's own severity), and the `expected` and `actual` values in its body.
- Soda's `stderr` is secret-redacted before it is printed or embedded in a JUnit failure body.

## Notes

- Use `test` when you want live-resource checks and `dq.rules` evaluated.
- Use [`fluid verify`](./verify.md) when you only need contract-to-deployed-state verification. Against the local provider, `verify` checks that the declared columns exist and, for an acquisition build, that the run landed rows; it did not evaluate `dq.rules` in a measured run where `fluid test` failed one at `error`.
