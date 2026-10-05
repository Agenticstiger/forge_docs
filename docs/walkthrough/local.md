# Walkthrough: Local Development

**Time:** 15 minutes | **Difficulty:** Beginner | **Prerequisites:** Python 3.10+, pip

> **Why it matters**
> Build, check and chain data products on your laptop with no cloud account and no credentials.
> The contract you write here runs on DuckDB; the same kind of file is what a cloud run reads, with the binding swapped in an overlay (see [Next steps](#next-steps)).

This walkthrough was run end to end on CLI `0.18.1`. Every command below is followed by the output it printed, with absolute paths shortened to `...`.

## What you build

Two data products in one workspace, both reading and writing files on your machine:

| Product | Reads | Writes |
| --- | --- | --- |
| `entertainment.genre_preferences_v1` | two CSV files | `output/genre_preferences.csv` |
| `entertainment.engagement_v1` | the first product's output, through `consumes` | `output/engagement.csv` |

You will write a contract, then run `validate`, `plan`, `apply`, `verify`, `test` and `diff` against it, and read the limits of the local engine that 0.18.1 enforces or does not enforce.

::: tip Why this page does not use the quickstart template
`fluid init --quickstart` and `fluid demo` scaffold the `customer-360` template, whose build is a five-stage SQL pipeline. As of 0.18.1 the local provider does not run those stages. `fluid apply contract.fluid.yaml --yes` prints "Data product deployed successfully" and writes a 24-byte file containing `id,value` and `1,materialized` to each output. With `--mode amend-and-build` it writes a one-row `demo_col` table to `output/customer_360.parquet` and nothing to `output/high_value_customers.parquet`. `fluid demo` also logs `'ApplyArgs' object has no attribute 'config_override'` when it tries to run the pipeline for you, and exits 0. `fluid validate` passes on the template. Use the contract below to see data land.
:::

---

## Step 1: Install

```bash
pip install "data-product-forge[local]"
fluid version
```

The `local` extra installs DuckDB (`duckdb>=1.5.0`) and pandas. The bare package does not, and a local build then fails:

```text
   ❌ Failed: 1 action(s) failed
      duckdb not installed. Install it with: pip install duckdb
```

`fluid version` on the installed CLI:

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
```

The panels below it list the features and the providers (`local`, `gcp`, `aws`, `snowflake`) the install carries.

## Step 2: Create the project and the data

```bash
mkdir -p netflix-local/genre-preferences/data
cd netflix-local/genre-preferences
```

Create `data/customers.csv`:

```csv
customer_id,email,name,country,signup_date,subscription_tier,age,gender
CUST001,alice.wonder@example.com,Alice Wonderland,US,2023-01-15,Premium,28,F
CUST002,bob.builder@example.com,Bob Builder,UK,2023-02-20,Standard,35,M
CUST003,charlie.brown@example.com,Charlie Brown,CA,2023-03-10,Premium,42,M
CUST004,diana.prince@example.com,Diana Prince,US,2023-04-05,Basic,31,F
CUST005,eve.jackson@example.com,Eve Jackson,AU,2023-05-12,Standard,27,F
```

Create `data/viewing_history.csv`:

```csv
view_id,customer_id,content_id,content_title,content_type,genre,watch_date,watch_duration_minutes,completion_percent,rating
VIEW001,CUST001,CONT101,Stranger Things S4,Series,Sci-Fi,2024-01-10,65,85,5
VIEW002,CUST001,CONT102,The Crown S6,Series,Drama,2024-01-11,58,95,4
VIEW003,CUST001,CONT103,Glass Onion,Movie,Mystery,2024-01-12,139,100,5
VIEW004,CUST002,CONT104,Wednesday S1,Series,Comedy,2024-01-10,45,75,4
VIEW005,CUST002,CONT101,Stranger Things S4,Series,Sci-Fi,2024-01-11,65,90,5
VIEW006,CUST002,CONT105,The Witcher S3,Series,Fantasy,2024-01-13,52,80,3
VIEW007,CUST003,CONT106,Breaking Bad,Series,Thriller,2024-01-09,58,100,5
VIEW008,CUST003,CONT107,Extraction 2,Movie,Action,2024-01-10,111,100,4
VIEW009,CUST003,CONT108,The Gray Man,Movie,Action,2024-01-14,122,95,4
VIEW010,CUST004,CONT102,The Crown S6,Series,Drama,2024-01-11,58,100,5
VIEW011,CUST004,CONT109,Bridgerton S3,Series,Romance,2024-01-12,61,88,5
VIEW012,CUST004,CONT110,Emily in Paris S4,Series,Comedy,2024-01-13,33,55,3
VIEW013,CUST005,CONT103,Glass Onion,Movie,Mystery,2024-01-10,139,100,5
VIEW014,CUST005,CONT111,Love is Blind S5,Series,Reality,2024-01-11,48,90,4
VIEW015,CUST005,CONT112,Squid Game S2,Series,Thriller,2024-01-15,60,100,5
```

## Step 3: Write the contract

Create `contract.fluid.yaml` in `netflix-local/genre-preferences/`:

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: entertainment.genre_preferences_v1
name: Genre Preferences
description: Which genres each Netflix customer watches, built from two CSV files.
domain: Entertainment
tags:
  - streaming
  - customer-analytics

metadata:
  layer: Gold
  tags:
    - streaming
  owner:
    team: customer-analytics
    email: analytics@example.com

builds:
  - id: build_genre_preferences
    description: Count views, minutes, completion and rating per customer and genre
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          c.customer_id,
          c.name AS customer_name,
          v.genre,
          COUNT(*) AS total_views,
          SUM(v.watch_duration_minutes) AS total_minutes,
          ROUND(AVG(v.completion_percent), 2) AS avg_completion,
          ROUND(AVG(v.rating), 2) AS avg_rating
        FROM read_csv_auto('data/customers.csv') c
        JOIN read_csv_auto('data/viewing_history.csv') v
          ON c.customer_id = v.customer_id
        GROUP BY c.customer_id, c.name, v.genre
        ORDER BY c.customer_id, total_views DESC, v.genre
    outputs:
      - genre_preferences

exposes:
  - exposeId: genre_preferences
    kind: table
    title: Genre preferences by customer
    version: 1.0.0
    binding:
      platform: local
      format: csv
      location:
        path: output/genre_preferences.csv
    contract:
      schema:
        - {name: customer_id, type: STRING}
        - {name: customer_name, type: STRING}
        - {name: genre, type: STRING}
        - {name: total_views, type: INTEGER}
        - {name: total_minutes, type: INTEGER}
        - {name: avg_completion, type: FLOAT}
        - {name: avg_rating, type: FLOAT}
      dq:
        rules:
          - id: customer_id_present
            type: completeness
            selector: customer_id
            severity: error
            description: Every row names a customer.
          - id: views_not_negative
            type: accuracy
            selector: total_views
            threshold: 0
            operator: '>='
            severity: error
            description: View counts cannot be negative.
```

Read it in four parts:

- **`builds[]`** holds the transformation. `pattern: embedded-logic` with `engine: sql` runs the SQL in `properties.sql` on DuckDB. As of 0.18.1 the relative paths in `read_csv_auto(...)` resolve against the directory you run the command from, while a relative `location.path` such as `output/genre_preferences.csv` lands beside the contract. Run every command on this page from the directory that holds the contract and the two agree. Run `fluid apply genre-preferences/contract.fluid.yaml ...` from the directory above and the build fails with `No files found that match the pattern "data/customers.csv"`.
- **`outputs`** on the build names the expose it produces.
- **`exposes[]`** declares the product's output: a CSV at `output/genre_preferences.csv`, with a typed schema.
- **`contract.dq.rules[]`** are data-quality rules that `fluid test` runs against the output. Each rule needs an `id`, a `type`, a `selector` and a `severity`.

The contract declares `fluidVersion: "0.7.5"`, the latest stable schema. See [Contract](../concepts/contract.md) for the fields and [Builds, exposes and bindings](../concepts/builds-exposes-bindings.md) for how the three sections connect.

## Step 4: Validate

```bash
fluid validate contract.fluid.yaml
```

```text
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.005s
```

## Step 5: Plan

```bash
fluid plan contract.fluid.yaml
```

```text
============================================================
FLUID Execution Plan
============================================================
Contract: Genre Preferences
Version: 0.7.5
Total Actions: 2
============================================================

1. provision_genre_preferences (provisionDataset)
2. schedule_build_genre_preferences (scheduleTask)
```

The plan names one dataset to provision and one build to schedule. `plan` writes `plan.json` in the directory you ran it from and changes nothing else.

## Step 6: Apply

```bash
fluid apply contract.fluid.yaml --yes --mode amend-and-build
```

```text
Loading contract: .../genre-preferences/contract.fluid.yaml

================================================================================
🚀 FLUID Build Runner
================================================================================
Contract: .../genre-preferences/contract.fluid.yaml
Builds: 1
================================================================================

────────────────────────────────────────────────────────────
🔷 Build 'build_genre_preferences' (embedded-SQL / local DuckDB)
   ✅ Completed in 0.13s — 1 action(s) executed
   📁 .../genre-preferences/output/genre_preferences.csv

================================================================================
📈 Overall Summary
================================================================================
Total builds: 1
✅ Executed: 1
❌ Failed: 0
⏭️  Skipped: 0
================================================================================
```

`--mode amend-and-build` runs every build in `builds[]`. Without a `*-and-build` mode the local provider takes a simpler path with different rules; see [What the local engine does on 0.18.1](#what-the-local-engine-does-on-0-18-1). The modes are listed in [`fluid apply`](../cli/apply.md).

## Step 7: Read the result

```bash
cat output/genre_preferences.csv
```

```text
customer_id,customer_name,genre,total_views,total_minutes,avg_completion,avg_rating
CUST001,Alice Wonderland,Drama,1,58,95.0,4.0
CUST001,Alice Wonderland,Mystery,1,139,100.0,5.0
CUST001,Alice Wonderland,Sci-Fi,1,65,85.0,5.0
CUST002,Bob Builder,Comedy,1,45,75.0,4.0
CUST002,Bob Builder,Fantasy,1,52,80.0,3.0
CUST002,Bob Builder,Sci-Fi,1,65,90.0,5.0
CUST003,Charlie Brown,Action,2,233,97.5,4.0
CUST003,Charlie Brown,Thriller,1,58,100.0,5.0
CUST004,Diana Prince,Comedy,1,33,55.0,3.0
CUST004,Diana Prince,Drama,1,58,100.0,5.0
CUST004,Diana Prince,Romance,1,61,88.0,5.0
CUST005,Eve Jackson,Mystery,1,139,100.0,5.0
CUST005,Eve Jackson,Reality,1,48,90.0,4.0
CUST005,Eve Jackson,Thriller,1,60,100.0,5.0
```

Fourteen rows: five customers, one row per genre each of them watched, ordered by the `ORDER BY` in the SQL.

## Step 8: Verify, test and diff

Three commands compare what is on disk with what the contract says. They answer different questions.

### `fluid verify`: does the output have the declared columns?

```bash
fluid verify contract.fluid.yaml
```

```text
📋 Verifying: genre_preferences
   Format: csv
   Target: .../genre-preferences/output/genre_preferences.csv

   🟢 Severity: SUCCESS (Impact: NONE)
   📁 File: .../genre-preferences/output/genre_preferences.csv (csv)
   📊 Rows: 14

   🔍 Dimension 1: Schema Structure
      ✅ PASS - All 7 declared columns present

   ⚪ Data types, constraints, location: not checked for local files (column names, row count and masked-value shapes only)

   💡 Remediation: NONE
      All checks passed

================================================================================
📊 Verification Summary
================================================================================
Total verified: 1
✅ Match: 1
⚠️  Mismatch: 0
❌ Error: 0
================================================================================
```

For a local CSV or Parquet output `verify` checks the column names against the declared schema, plus a row count. It does not check data types, constraints or location for local files, and says so. Any mismatch in the column names is critical, whether the file has fewer columns or more. With one extra column, `verify` prints `Severity: CRITICAL` and `Not declared in the contract: extra`, exits 1 under `--strict`, and exits 0 without it.

### `fluid test`: do the data-quality rules pass?

```bash
fluid test contract.fluid.yaml
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
│ 7    │ ✅     │ Quality tests          │ 2 rule(s) passed            │
│ 8    │ ✅     │ Metadata / governance  │ Complete                    │
└──────┴────────┴────────────────────────┴─────────────────────────────┘

✅ 8 passed  |  0 error(s)  |  0 warning(s)  |  0.18s
Data-quality rules: 2/2 passed
```

Row 7 ran the two rules from `contract.dq.rules[]` against the CSV.

### `fluid diff`: has the output drifted from the contract?

```bash
fluid diff contract.fluid.yaml --exit-on-drift
```

```text
Live drift check: 1 expose(s)
  genre_preferences [local] match  .../genre-preferences/output/genre_preferences.csv
State drift check: not run (the contract runs on the local engine, which keeps no OpenTofu state). Drift comes from the live checks alone.
```

Without `--state`, `diff` reads each expose's live target and compares its columns with the contract. A local target that does not exist yet reports `absent (to be created)`, which is not drift. The local engine keeps no OpenTofu state, so there is no state check. How `--exit-on-drift` exits, and what the other statuses mean, is in [Stage 5 of the 11-stage pipeline](./11-stage-pipeline.md#stage-5-diff-drift-gate).

---

## Step 9: Chain a second product

A product can read another product's output through `consumes`. Add a workspace marker at the root of the project, then a second contract in its own directory:

```bash
cd ..
cat > fluid.workspace.yaml << 'EOF'
schema_version: 1
kind: WorkspaceConfig
workspace:
  name: netflix-local
  provider: local
EOF
mkdir engagement
```

The layout is now:

```text
netflix-local/
├── fluid.workspace.yaml
├── genre-preferences/
│   ├── contract.fluid.yaml
│   ├── data/
│   └── output/genre_preferences.csv
└── engagement/
    └── contract.fluid.yaml
```

Create `engagement/contract.fluid.yaml`:

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: entertainment.engagement_v1
name: Customer Engagement
description: Total views and watch hours per customer, built from the genre preferences product.
domain: Entertainment
tags:
  - streaming
  - customer-analytics

metadata:
  layer: Gold
  tags:
    - streaming
  owner:
    team: customer-analytics
    email: analytics@example.com

consumes:
  - productId: entertainment.genre_preferences_v1
    exposeId: genre_preferences
    purpose: Per-customer genre counts

builds:
  - id: build_engagement
    description: Roll the genre rows up to one row per customer
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          customer_id,
          customer_name,
          SUM(total_views) AS total_views,
          COUNT(*) AS genres_watched,
          ROUND(SUM(total_minutes) / 60.0, 2) AS total_hours
        FROM genre_preferences
        GROUP BY customer_id, customer_name
        ORDER BY total_hours DESC, customer_id
    outputs:
      - engagement

exposes:
  - exposeId: engagement
    kind: table
    title: Customer engagement
    version: 1.0.0
    binding:
      platform: local
      format: csv
      location:
        path: output/engagement.csv
    contract:
      schema:
        - {name: customer_id, type: STRING}
        - {name: customer_name, type: STRING}
        - {name: total_views, type: INTEGER}
        - {name: genres_watched, type: INTEGER}
        - {name: total_hours, type: FLOAT}
```

The `consumes` entry is a logical address: a `productId` and an `exposeId`. When the build runs, the engine looks for the contract that declares that `id` in files named `contract.fluid.yaml` or `contract.fluid.json`, up to four directories below the one holding `fluid.workspace.yaml`. It works out where that product's expose lands and gives the SQL a view named after the `exposeId`. That is why the SQL reads `FROM genre_preferences` with no path.

```bash
cd engagement
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --yes --mode amend-and-build
```

```text
────────────────────────────────────────────────────────────
🔷 Build 'build_engagement' (embedded-SQL / local DuckDB)
   ⬅ consumes entertainment.genre_preferences_v1/genre_preferences as view "genre_preferences": 
.../genre-preferences/output/genre_preferences.csv
     (no run record or lineage event on this path: the resolved inputs are listed here and in runtime/out/local_apply_log.jsonl)
   ✅ Completed in 0.03s — 1 action(s) executed
   📁 .../engagement/output/engagement.csv
```

```bash
cat output/engagement.csv
```

```text
customer_id,customer_name,total_views,genres_watched,total_hours
CUST003,Charlie Brown,3,2,4.85
CUST001,Alice Wonderland,3,3,4.37
CUST005,Eve Jackson,3,3,4.12
CUST002,Bob Builder,3,3,2.7
CUST004,Diana Prince,3,3,2.53
```

The upstream product has to have run first, because the engine reads the file the upstream wrote. If it has not, the build fails with `Input file not found` and tells you to build the upstream first, with the same `--env`. If the engine cannot find an upstream contract at all, it lists the directories it searched and tells you to check the `productId`, keep the contract under the workspace root, add its repository to `FLUID_UPSTREAM_CONTRACTS`, or bind the input by hand under `builds[].properties.parameters.inputs`. If two contracts under the workspace root declare the same `id`, for example because you copied a contract into a sibling directory to try something, the build refuses with `ConsumesResolutionError` and names the files. Give each contract its own `id` or delete the copy.

---

## What the local engine does on 0.18.1

These behaviours were measured on 0.18.1. They are the edges you meet when you move past one build and one output.

### Contract SQL runs in a sandbox

Since 0.18.0, DuckDB can read only the contract's own directory, its workspace, `./runtime`, a scratch directory and the locations the contract declares. Pointing `read_csv_auto` at `/etc/hosts` fails:

```text
   ❌ Failed: 1 action(s) failed
      Permission Error: Cannot access file "/etc/hosts" - file system operations are disabled by configuration DuckDB refused it: contract SQL may only read and write the locations the contract declares and its own directory (...). Declare the file as an input under the contract's directory or workspace, or move it there (the operator can allow another directory with FLUID_DUCKDB_ALLOWED_DIRS).
```

A URL fails too: DuckDB reports that the file needs the `httpfs` extension. Keep source files under the contract's directory or workspace. The rules and the environment variable are in [DuckDB sandbox](../advanced/duckdb-sandbox.md).

### One build writes one expose: the first

On the `amend-and-build` path an embedded-SQL build writes only the first expose in `exposes[]`, whatever its `outputs` names. A second build that names a different expose does not write it; it overwrites the first expose's file. This contract has two builds and two exposes:

```text
────────────────────────────────────────────────────────────
🔷 Build 'build_genre_preferences' (embedded-SQL / local DuckDB)
   ✅ Completed in 0.38s — 1 action(s) executed
   📁 .../twobuilds/output/genre_preferences.csv

────────────────────────────────────────────────────────────
🔷 Build 'build_views_per_customer' (embedded-SQL / local DuckDB)
   ⚠️  expose views_per_customer is named in the build's outputs, but this path writes only the first expose (genre_preferences); views_per_customer is not written by this build
embedded_sql_plan_warning expose views_per_customer is named in the build's outputs, but this path writes only the first expose (genre_preferences); views_per_customer is not written by this build
   ✅ Completed in 0.11s — 1 action(s) executed
   📁 .../twobuilds/output/genre_preferences.csv
```

Both builds report success and name `genre_preferences.csv`. `output/` holds one file, and it contains the second build's result:

```text
customer_id,total_views
CUST001,3
CUST002,3
```

Give each embedded-SQL build its own product, as in Step 9, until your build writes the expose you declared.

### Masking is refused, or ignored

`policy.privacy.masking` on an expose that an embedded-SQL build lands is refused on the `amend-and-build` path, because the query result would otherwise land in cleartext:

```text
────────────────────────────────────────────────────────────
🔷 Build 'build_genre_preferences' (embedded-SQL / local DuckDB)
   ❌ expose 'genre_preferences' declares policy.privacy.masking, which the embedded-SQL landing path does not apply yet
      why: This build writes the query result as the SQL returns it, so customer_name would land in cleartext.
      fix: Land this expose through an engine that enforces its masking, or write the masking into properties.sql and declare the columns as they then land.
embedded_sql_io_refused build_id=build_genre_preferences code=MaskingNotAppliedError
```

Without a `*-and-build` mode, the same contract applies and writes the column in cleartext, with no warning:

```text
customer_id,customer_name,genre,total_views,total_minutes,avg_completion,avg_rating
CUST001,Alice Wonderland,Drama,1,58,95.0,4.0
CUST001,Alice Wonderland,Mystery,1,139,100.0,5.0
```

The local provider's simple path never reads `policy.privacy.masking`. To treat a column, write the treatment into `properties.sql` and declare the column as it lands. Masking at landing, with `strategy`, `saltEnv`, `keyEnv`, `keepFirst` and `keepLast`, is applied only by the DuckDB acquisition runner; see [Source-aligned: Postgres to DuckDB](./source-aligned-postgres-duckdb.md).

### The default mode takes a simpler path

`fluid apply contract.fluid.yaml --yes` without a `*-and-build` mode uses the local provider's own planner: it runs the SQL of the first build, writes the first expose, and logs `Using simple execution mode (local provider)`. When it has no SQL to run it writes the placeholder file `id,value` / `1,materialized` and still reports success. As of 0.18.1 that includes a contract whose build `id` equals an `exposeId`: the planner logs `Dependency cycle detected` and writes the placeholder. If an output file holds `id,value` and `1,materialized`, you got the placeholder.

---

## Next steps

- **Run it on a schedule.** Add `execution.trigger` to the build and generate an Airflow DAG: [Declarative Airflow](./airflow-declarative.md).
- **Run it in CI.** Generate a pipeline and walk its gates: [The 11-stage pipeline](./11-stage-pipeline.md).
- **Target a cloud.** A cloud run reads the same contract with the binding patched by an overlay, run with `--env`: [Switch clouds](../recipes/switch-clouds.md) and [Per-environment overlays](../recipes/per-environment-overlays.md).
- **Mask at landing.** [Source-aligned: Postgres to DuckDB](./source-aligned-postgres-duckdb.md).
- **Look at the local provider's reference.** [Local provider](../providers/local.md).
