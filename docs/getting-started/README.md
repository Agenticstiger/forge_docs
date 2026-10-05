---
title: Getting Started
description: Install the CLI, scaffold a data product, and validate, plan, apply, verify and test it on your laptop with DuckDB. Run end to end on CLI 0.18.1.
---

# Getting Started

Build a data product on your laptop: install the CLI, scaffold a contract, then validate, plan, apply, verify and test it on DuckDB. No cloud account and no credentials.

This page was run end to end on CLI `0.18.1`, in an empty directory, with a fresh virtual environment. Every command is followed by the output it printed, trimmed with `...` and with absolute paths shortened.

**Time:** about 10 minutes · **Needs:** Python 3.10 or newer, `pip`

## What you build

One data product, `analytics.my-first-product`. It reads a CSV of orders, totals them per customer, writes the result to a CSV file, and declares a data-quality rule that `fluid test` checks.

## Install the CLI

```bash
pip install "data-product-forge[local]"
fluid version
```

```text
╭───────────────────────────────────── 📦 Version Information ─────────────────────────────────────╮
│ FLUID CLI                                                                                        │
│ Version: 0.18.1                                                                                  │
│ API: v1                                                                                          │
│                                                                                                  │
│ Supported Specifications:                                                                        │
│ • FLUID 0.7.1, 0.7.2, 0.7.3, 0.7.4, 0.7.5, 0.7.6 (preview)                                       │
│ • Default: 0.7.5                                                                                 │
│ • Latest (stable): 0.7.5                                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
...
```

The package is `data-product-forge` and the command is `fluid`. The older `fluid-forge` package stopped at `0.7.9`; do not install it.

The `local` extra installs DuckDB (`duckdb>=1.5.0`), pandas and numpy, which the local engine runs on. Without it a local build fails with `duckdb not installed. Install it with: pip install duckdb`. Add an extra for each place you deploy to:

| Extra | For | Installs |
| --- | --- | --- |
| `local` | Builds on your machine (DuckDB) | `duckdb`, `pandas`, `numpy` |
| `gcp` | BigQuery | Google Cloud client libraries, `dbt-bigquery` |
| `aws` | S3, Glue, Athena | `boto3` |
| `snowflake` | Snowflake | `snowflake-connector-python`, `dbt-snowflake` |

```bash
pip install "data-product-forge[local,gcp]"           # several extras at once
pip install "data-product-forge[local]==0.18.1"       # an exact version, for CI
```

A cloud `fluid apply` runs OpenTofu, so it also needs `tofu` 1.6.0 or newer on your `PATH`, or `fluid apply --ensure-opentofu`, which downloads a pinned build from the OpenTofu release and checks it against that release's `SHA256SUMS` (integrity, not a signature). For production CI, install OpenTofu with a cosign- or gpg-verified install instead, and keep `tofu` on the runner image. The local path in this tutorial does not use OpenTofu.

Coming from an older release? [Upgrading](../upgrading.md) has a checklist for each version you cross.

## Step 1: Scaffold a product

```bash
mkdir fluid-quickstart && cd fluid-quickstart
fluid init my-first-product --blueprint fluid.starter
```

```text
Scaffolded team memory at .../fluid-quickstart/.fluid/team-memory.yaml
Created fluid.workspace.yaml — workspace my-first-product

╭───────────────────────────────────────── Blueprint Mode ─────────────────────────────────────────╮
│ 📦 Creating from blueprint: Starter Data Product                                                 │
│                                                                                                  │
│ Minimal Bronze data product (embedded SQL → local CSV) — the quickest way to a valid, runnable   │
│ contract.                                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

✅ Created my-first-product/contract.fluid.yaml from blueprint fluid.starter
...
```

`fluid init` writes into two directories. The one you ran it in becomes the [workspace](../concepts/workspaces.md) root; `my-first-product/` is the product:

```text
fluid-quickstart/
├── fluid.workspace.yaml
├── .gitignore
├── .fluid/
│   ├── init-receipt.json
│   └── team-memory.yaml
└── my-first-product/
    ├── contract.fluid.yaml
    └── .fluid/
        └── forge-receipt.json
```

Commit these files except the two receipts. The generated `.gitignore` already leaves out the receipts, `runtime/` (where local builds write) and per-engineer files under `.fluid/`. [`fluid init`](../cli/init.md#what-fluid-init-writes) describes each file.

::: warning Why this page does not start from `fluid init --quickstart`
`fluid init my-project --quickstart` scaffolds the `customer-360` example, which validates and plans. As of 0.18.1 the local engine does not run its five-stage SQL build: `fluid apply` prints "Data product deployed successfully" and writes a 24-byte placeholder (`id,value` / `1,materialized`) to each output, and `fluid verify` then exits 1. The `fluid.starter` blueprint used here lands real rows. [Local walkthrough](../walkthrough/local.md#what-the-local-engine-does-on-0-18-1) lists the local engine's other limits.
:::

## Step 2: Read the contract

```bash
cd my-first-product
cat contract.fluid.yaml
```

```yaml
# FLUID Data Product Contract
# Docs: https://agenticstiger.github.io/forge_docs/concepts/contract.html
fluidVersion: 0.7.4
kind: DataProduct
id: analytics.my-first-product
name: my-first-product
description: my-first-product — generated from the fluid.starter blueprint.
domain: analytics
metadata:
  layer: Bronze
  owner:
    team: data-platform
    email: data-platform@example.com
  provenance:
    ...
builds:
- id: my-first-product_build
  pattern: embedded-logic
  engine: sql
  properties:
    sql: "SELECT\n  'Hello from the my-first-product data product' AS message,\n \
      \ CURRENT_TIMESTAMP AS created_at\n"
exposes:
- exposeId: my-first-product_output
  kind: table
  binding:
    platform: local
    format: csv
    location:
      path: runtime/out/my-first-product.csv
  contract:
    schema:
    - name: message
      type: string
    - name: created_at
      type: timestamp
```

Three blocks do the work:

- **`builds[]`** says how the data is produced: here, one SQL statement that DuckDB runs.
- **`exposes[]`** says what the product offers: one table, with a typed schema.
- **`binding`**, inside the expose, says where it lands: a CSV file on this machine. It is the block that changes when the product moves to another platform: `platform`, `format` and `location` together ([Builds, exposes, bindings](../concepts/builds-exposes-bindings.md#moving-a-product-to-another-platform)).

`fluidVersion` is the version of the contract schema the file is written against. The blueprint writes `0.7.4`; `0.7.5` is the latest stable schema, and the CLI accepts both. See [Understand the version numbers](#understand-the-version-numbers).

## Step 3: Validate and plan

```bash
fluid validate contract.fluid.yaml
```

```text
✅ Valid FLUID contract (schema v0.7.4)
Validation completed in 0.001s
```

```bash
fluid plan contract.fluid.yaml
```

```text
============================================================
FLUID Execution Plan
============================================================
Contract: my-first-product
Version: 0.7.4
Total Actions: 2
============================================================

1. provision_my-first-product_output (provisionDataset)
2. schedule_my-first-product_build (scheduleTask)

✅ Plan saved to:
.../my-first-product/plan.json
```

`validate` checks the file against the schema. `plan` lists what an apply would do and writes it to `plan.json`; it changes nothing else.

## Step 4: Apply

```bash
fluid apply contract.fluid.yaml --yes --mode amend-and-build
```

```text
================================================================================
🚀 FLUID Build Runner
================================================================================
...
🔷 Build 'my-first-product_build' (embedded-SQL / local DuckDB)
   ✅ Completed in 0.03s — 1 action(s) executed
   📁 .../my-first-product/runtime/out/my-first-product.csv
...
Total builds: 1
✅ Executed: 1
❌ Failed: 0
```

`--mode amend-and-build` creates the output and runs every build in `builds[]`. As of 0.18.1, on the local provider, leave the mode off and the apply still prints "Data product deployed successfully", but it writes the placeholder `id,value` / `1,materialized` to `runtime/out/my-first-product.csv` and puts the SQL result in `runtime/out/preview_0.csv`. The modes are listed in [`fluid apply`](../cli/apply.md).

Look at what landed:

```bash
cat runtime/out/my-first-product.csv
```

```text
message,created_at
Hello from the my-first-product data product,2026-10-05 10:35:49.479853+02
```

## Step 5: Verify

```bash
fluid verify contract.fluid.yaml --strict
```

```text
📋 Verifying: my-first-product_output
   Format: csv
   ...
   📊 Rows: 1

   🔍 Dimension 1: Schema Structure
      ✅ PASS - All 2 declared columns present

   ⚪ Data types, constraints, location: not checked for local files (column names, row count and
masked-value shapes only)
...
✅ Match: 1
⚠️  Mismatch: 0
❌ Error: 0
```

`verify` reads what was deployed and compares it with the contract. For a local file it checks column names and the row count; on a cloud target it also checks types and, where the provider supports it, the governance the contract declares ([`fluid verify`](../cli/verify.md)). With `--strict` it exits 1 when a declared column is missing or the file has columns the contract does not declare; without `--strict` it reports the drift and exits 0. Use `--strict` in CI.

## Step 6: Make it read your data

Create `data/orders.csv` next to the contract:

```csv
order_id,customer_id,amount
1,C001,120.00
2,C002,35.50
3,C001,80.25
4,C003,210.00
5,C002,14.75
```

In `contract.fluid.yaml`, replace everything from `builds:` to the end of the file with:

```yaml
builds:
- id: my-first-product_build
  pattern: embedded-logic
  engine: sql
  properties:
    sql: |
      SELECT
        customer_id,
        COUNT(*) AS orders,
        ROUND(SUM(amount), 2) AS revenue
      FROM read_csv_auto('data/orders.csv')
      GROUP BY customer_id
      ORDER BY customer_id
exposes:
- exposeId: my-first-product_output
  kind: table
  binding:
    platform: local
    format: csv
    location:
      path: runtime/out/my-first-product.csv
  contract:
    schema:
    - name: customer_id
      type: string
    - name: orders
      type: integer
    - name: revenue
      type: decimal
    dq:
      rules:
      - id: customer_id_present
        type: completeness
        selector: customer_id
        severity: error
        description: Every row names a customer.
```

Run the commands from the directory that holds the contract: as of 0.18.1 the path in `read_csv_auto(...)` resolves against your working directory. Contract SQL runs in a sandbox that reads only the contract's directory, its workspace and a few declared locations, so keep source files inside the project ([DuckDB sandbox](../advanced/duckdb-sandbox.md)).

Apply again and look at the result:

```bash
fluid apply contract.fluid.yaml --yes --mode amend-and-build
cat runtime/out/my-first-product.csv
```

```text
customer_id,orders,revenue
C001,2,200.25
C002,2,50.25
C003,1,210.0
```

`fluid verify contract.fluid.yaml --strict` now reports `📊 Rows: 3` and `✅ PASS - All 3 declared columns present`.

## Step 7: Test the data-quality rule

```bash
fluid test contract.fluid.yaml --no-cache
```

```text
┏━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ #    ┃ Result ┃ Check                  ┃ Details                     ┃
┡━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1    │ ✅     │ Schema syntax          │ Valid                       │
│ 2    │ ✅     │ Provider connection    │ OK                          │
│ 3    │ ✅     │ Binding configuration  │ OK                          │
│ 4    │ ✅     │ Resource exists        │ 1 exposed resource(s) found │
│ 5    │ ✅     │ Schema fields          │ All fields match            │
│ 6    │ ✅     │ Row count / SLA        │ OK                          │
│ 7    │ ✅     │ Quality tests          │ 1 rule(s) passed            │
│ 8    │ ⚠️     │ Metadata / governance  │ 1 info/warning(s)           │
└──────┴────────┴────────────────────────┴─────────────────────────────┘

✅ 7 passed  |  1 warned  |  0 error(s)  |  0 warning(s)  |  0.07s
Data-quality rules: 1/1 passed
```

Row 7 ran the `dq.rules` you declared against the output. The warning in row 8 is informational: the contract has no `metadata.tags`.

::: warning Why `--no-cache`
As of 0.18.1 `fluid test` caches the columns it reads for an hour in `~/.fluid/cache`, keyed by the binding's location as written. For a local file that is the relative path, so a second product, or a second run of this tutorial, with the same `path` reads the cached columns of the first. Without `--no-cache`, Step 7 reported `Field 'customer_id' is missing from actual schema` after Step 6 changed the columns.
:::

Now break the data on purpose. Add a row with no customer, apply, and test again:

```bash
echo "6,,9.99" >> data/orders.csv
fluid apply contract.fluid.yaml --yes --mode amend-and-build
fluid test contract.fluid.yaml --no-cache
```

```text
│ 7    │ ❌     │ Quality tests          │ Every row names a customer. — completeness for          │
│      │        │                        │ 'customer_id' is 75.00%                                 │
...
❌ 6 passed  |  1 warned  |  1 failed  |  1 error(s)  |  0 warning(s)  |  0.07s
Data-quality rules: 0/1 passed
```

The apply succeeded and wrote the bad row: `fluid apply` does not evaluate `dq.rules`. `fluid test` does, and it exited 1 because the rule's severity is `error`. Put `fluid test` after the apply in CI and a failing rule stops the pipeline. Remove the last line of `data/orders.csv` to go back to a passing product.

## Understand the version numbers

Two numbers, two meanings:

- `fluid version` reports the CLI release you installed: `0.18.1`.
- `fluidVersion` inside a contract selects the [contract schema](../reference/README.md) it is written against. `0.7.5` is the latest stable schema and the default for a contract that does not say. `0.7.6` is a preview you opt into by writing `fluidVersion: "0.7.6"`; [Fields that need 0.7.6](../reference/preview-fields.md) lists what it adds.

Each scaffolder writes its own version: `--quickstart` and directory templates write `0.7.5`, the `fluid.starter` blueprint `0.7.4`, and `--discover`, `fluid product-new` and `fluid import` `0.7.3`. The table is in [Which `fluidVersion` each path writes](../cli/init.md#which-fluidversion-each-path-writes). An older version keeps validating; to move a contract up, change the line and run `fluid validate`. The schema itself is published as the [FLUID specification](https://open-data-protocol.github.io/fluid/).

## The AI-assisted path: `fluid forge`

`fluid init` scaffolds from a fixed template or blueprint. `fluid forge` looks at the files in your directory and drafts a contract with the LLM provider you configure with `fluid ai setup`:

```bash
fluid forge
fluid forge --domain finance
```

A contract it drafts with two or more builds or exposes, or with a `sovereignty` or `accessPolicy` block, can come out as a root file plus a `fragments/` directory; `validate`, `plan` and `apply` resolve the fragments for you ([Contract fragments](../concepts/fragments.md)). See [AI forge and data-model journeys](../walkthrough/ai-forge-data-model.md).

## Where next

The rest of the docs follow one product from here to production. Read in this order, or jump to what you need:

| Next | Page |
| --- | --- |
| Chain two local products, and see the local engine's limits | [Local walkthrough](../walkthrough/local.md) |
| Understand the contract | [What is a contract](../concepts/contract.md), then [Builds, exposes, bindings](../concepts/builds-exposes-bindings.md) |
| Split a large contract into files | [Contract fragments](../concepts/fragments.md) |
| Run one contract in dev, staging and prod, or on two clouds | [Environments and overlays](../concepts/environments-and-overlays.md), [One contract, two clouds](../recipes/one-contract-two-clouds.md) |
| Deploy to a cloud | [BigQuery](../walkthrough/gcp.md), [Snowflake quickstart](./snowflake.md), [AWS provider](../providers/aws.md), [Switch clouds](../recipes/switch-clouds.md) |
| Govern it | [Governance & policy](../concepts/governance-policy.md), [Governance parity](../concepts/governance-parity.md), [Sovereignty](../concepts/sovereignty.md), [Agent policy](../concepts/agent-policy.md) |
| Ship it through CI | [The 11-stage pipeline](../walkthrough/11-stage-pipeline.md), [Declarative Airflow](../walkthrough/airflow-declarative.md), [Command Center](../concepts/command-center.md) |
| Change it once it is live | [Change a live data product](../recipes/evolve-a-live-product.md), [Upgrading](../upgrading.md) |

The full list of tutorials, with what each one needs, is on the [tutorials page](../walkthrough/README.md).

## Troubleshooting

### `fluid: command not found`

The virtual environment that holds the CLI is not on your `PATH`. Activate it, or run the module directly:

```bash
python -m fluid_build.cli --help
```

### A local build fails with `duckdb not installed`

Install the `local` extra: `pip install "data-product-forge[local]"`.

### Check the installation

```bash
fluid doctor
```

`fluid doctor` prints a summary of its checks, the readiness of the configured LLM provider for `fluid forge`, and where Forge keeps its memory store.

---

## Need help?

- **Questions or ideas?** [Start a GitHub Discussion](https://github.com/Agenticstiger/forge-cli/discussions)
- **Bug or unexpected behavior?** [Open an issue](https://github.com/Agenticstiger/forge-cli/issues) with what you ran and what you saw
- **Want to contribute?** See [the contributing guide](../contributing.md)
