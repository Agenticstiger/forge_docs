# Databricks Provider

Deploy data products to Databricks Unity Catalog (a schema, a managed Delta table and its grants) and run dbt builds as Databricks jobs, using the same contract format and CLI commands as the other providers.

**Status:** ✅ Added in CLI `0.26.0` ([forge-cli #769](https://github.com/Agenticstiger/forge-cli/pull/769) tables, credentials and verify; [#774](https://github.com/Agenticstiger/forge-cli/pull/774) dbt jobs)
**Tested Services:** Unity Catalog schemas, managed Delta tables, grants, serverless dbt jobs

> **Why it matters**
> Target Databricks with the same contract your other teams run elsewhere. Set `binding.platform: databricks` and `fluid apply` compiles the contract to an OpenTofu module for the `databricks/databricks` provider and runs it.

---

## Overview

- ✅ **Plan & Apply**: a schema, a managed Delta table and one grant per principal, through OpenTofu
- ✅ **Existing catalog**: `location.database` names a catalog that must already exist. forge-cli reads it and never creates, grants on or destroys it
- ✅ **dbt builds as jobs**: a dbt build whose `execution.runtime.platform` is `databricks` becomes a serverless job that Databricks runs on its own trigger
- ✅ **Verify**: `fluid verify` checks the live table's columns, `USE CATALOG` for every reader and that each dbt job exists exactly once
- ✅ **One pinned credential**: the workspace comes from `DATABRICKS_HOST` only, and a run never falls back to a stray profile
- ⚠️ **Live drift**: `fluid diff` has no Databricks inspector yet (see [`fluid diff`](#fluid-diff))
- ❌ **Iceberg, masks, row filters, column restrictions, `packaging`**: `fluid validate` refuses them rather than apply something that is not enforced (see [What validate refuses](#what-validate-refuses))

## Prerequisites

| You need | Why |
| --- | --- |
| OpenTofu `1.6.0` or newer on `PATH` | `fluid apply` runs `tofu`. An older one stops the run. |
| A Unity Catalog workspace with an existing catalog | The catalog is read, never created. The identity that applies needs `USE CATALOG` and `CREATE SCHEMA` on it. |
| A SQL warehouse, its id in `DATABRICKS_WAREHOUSE_ID` | Every table statement runs on it, and so do the dbt jobs. Find the id under SQL Warehouses, Connection details. The id is not a secret. |
| `pip install 'data-product-forge[databricks]'` | The extra brings `databricks-sdk`. Only `fluid verify` needs it. |

## Credentials

The module takes the workspace and the credential from the environment, never from the contract. A contract that names a host (on a binding or a build) is refused, because the credential would be sent to it.

| Variable | Meaning |
| --- | --- |
| `DATABRICKS_HOST` | The workspace URL. Required. It must be `https://`; plain `http://` is accepted only for a loopback host such as `localhost`. |
| `DATABRICKS_TOKEN` | A personal access token. |
| `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET` | An OAuth M2M service principal. |
| `DATABRICKS_AUTH_TYPE` | Chooses the method explicitly (`pat`, `oauth-m2m`, or another the profile names). |
| `DATABRICKS_CONFIG_PROFILE` | Use this one profile of the config file as the credential. Its `host` must equal `DATABRICKS_HOST`. |
| `DATABRICKS_CONFIG_FILE` | The config file, instead of `~/.databrickscfg`. |
| `DATABRICKS_WAREHOUSE_ID` | The SQL warehouse (above). |

The rules:

- With no `DATABRICKS_CONFIG_PROFILE`, the credential is the environment's: a token (`pat`) or the OAuth pair (`oauth-m2m`), or the method `DATABRICKS_AUTH_TYPE` names. The config file is not read.
- With `DATABRICKS_CONFIG_PROFILE`, that profile is the credential and no other profile is read. A laptop's `databricks auth login` profile works this way.
- Two credentials at once are refused before `tofu` starts: a profile plus a token or secret in the environment, or a token plus an OAuth client with no `DATABRICKS_AUTH_TYPE` to choose between them.
- A profile for a different workspace than `DATABRICKS_HOST` is refused. So is a missing `DATABRICKS_HOST` and a plain-HTTP host.
- Before 0.26.0, a run without `DATABRICKS_HOST` went to whatever workspace the `DEFAULT` profile named, with its token.

`fluid apply`, `fluid diff` and `fluid verify` all use this one policy. A Databricks personal access token is masked in logs.

## A minimal contract

One `delta_table` expose, with the location as catalog (`database`), schema and table:

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: sales.orders_dbx
name: Orders
description: Orders on Databricks
domain: sales

metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-engineering@company.example.com

exposes:
  - exposeId: orders
    title: Orders
    version: "1.0.0"
    kind: table
    binding:
      platform: databricks
      format: delta_table
      location:
        database: main        # an existing catalog
        schema: sales         # the product owns this schema
        table: orders         # a managed Delta table
    policy:
      authz:
        readers:
          - "group:data-analysts"
    contract:
      schema:
        - name: order_id
          type: string
          required: true
        - name: amount
          type: decimal(18,2)
        - name: ordered_at
          type: timestamp
```

Check it and emit the module. No credentials are needed for either, only the warehouse id:

```bash
export DATABRICKS_WAREHOUSE_ID=<your-warehouse-id>
fluid validate contract.fluid.yaml
fluid generate iac contract.fluid.yaml --out iac
```

```text
✅ Valid FLUID contract (schema v0.7.5)

Wrote OpenTofu module: iac/main.tf.json  (provider: databricks, 4 resources)
```

The four resources are the schema, the table and two grants for `data-analysts`: `SELECT` on the table and `USE_SCHEMA` on the schema. The catalog is a `databricks_catalog` data source, not a resource. The module pins `databricks/databricks` to `~> 1.140.0`, and `tofu init` checks it against a lock file shipped with forge-cli.

Then deploy:

```bash
export DATABRICKS_HOST=https://<workspace>.cloud.databricks.com
export DATABRICKS_TOKEN=<token>
fluid apply contract.fluid.yaml --yes
fluid verify contract.fluid.yaml
```

## What `fluid apply` provisions

| Contract | Databricks object |
| --- | --- |
| `location.database` | The catalog, read with `data.databricks_catalog`. A missing catalog fails `tofu plan`, `--mode dry-run` included, before anything is created. |
| `location.schema` | A `databricks_schema` the product owns. It is never force-destroyed: removing a schema that still holds tables fails. |
| `location.table`, `contract.schema` | A managed Delta `databricks_sql_table`. `delta.columnMapping.mode=name` is set, since Delta drops and renames columns only under column mapping. |
| `accessPolicy.grants`, `policy.authz.readers` and `writers` | One `databricks_grant` per principal on the table, plus `USE_SCHEMA` on the schema. |
| A dbt build with `runtime.platform: databricks` | A serverless job and the workspace files it needs (see [dbt builds as jobs](#dbt-builds-as-jobs)). |

Permissions map to table privileges: `read`, `select` and `query` to `SELECT`; `write`, `insert`, `update` and `delete` to `MODIFY`; `admin` and `manage` to `ALL_PRIVILEGES`. `create` has no table privilege and is skipped.

A principal is a user's email, a group's name or a service principal's application id, written bare. A `user:` or `group:` prefix is stripped. A service account or domain principal has no Unity Catalog counterpart, so map it in `binding.principals` or the run is refused.

A grant is authoritative for its principal. If the schema already existed and other teams share it, each principal the contract names keeps `USE_SCHEMA` alone on it. Give a product its own schema.

### `USE CATALOG` is the owner's to grant

A reader needs `USE CATALOG` on the catalog as well. The catalog is not the product's, so forge-cli never grants it: a grant is authoritative, and it would revoke that principal's other privileges on the catalog for every product in it. `fluid apply` prints the statement the catalog's owner runs, and `fluid verify` checks it:

```text
data-analysts also need USE CATALOG on catalog main, which forge-cli never grants (the catalog is not the product's). Its owner runs: GRANT USE CATALOG ON CATALOG `main` TO `data-analysts`. fluid verify checks it.
```

### Changes the apply gates

| Change | Result |
| --- | --- |
| A dropped column, a partition change (a replace), a removed table | Refused unless `--allow-data-loss` is given. |
| A column rename | Refused unless `--allow-data-loss`: with the column count unchanged the provider renames by position, so the old values would stay under the new name. |
| A column reorder | Refused, flag or not. No apply can reach it. |
| A column type change | Fails at plan, naming the column. |
| A revoked grant | Not refused. |
| A missing catalog, missing credentials or an unreachable workspace | Fails at plan, naming the catalog, the variables to set or the host. |

An apply that stops before it applies anything (`--mode dry-run`, a refusal, the data-loss gate, a failed plan) hands back any object it imported with `tofu state rm`. The objects stay as they are, and the next apply adopts them again.

### Adopting an existing table

A table that already exists is imported before the first apply, not replaced. Its existing grants are imported with it, so a privilege the contract does not name shows in the plan as an update that removes it.

- **With column mapping** (`delta.columnMapping.mode=name`): adopted.
- **Without it**: refused, with or without `--allow-data-loss`. Setting the property upgrades the table's Delta protocol, which older readers and some external engines cannot read, and unsetting it does not undo that. The message gives the statement its owner runs once every reader can read column mapping:

  ```sql
  ALTER TABLE `main`.`sales`.`orders` SET TBLPROPERTIES ('delta.columnMapping.mode' = 'name')
  ```

  Or leave the table out of the contract, or let a dbt build write it.

## dbt builds as jobs

A build with an `engine` of `dbt` (or `dbt-<adapter>`) and `execution.runtime.platform: databricks` runs in the workspace, not on the machine that applies. `fluid apply` provisions one serverless job per build with a dbt task. Databricks runs it on the SQL warehouse `DATABRICKS_WAREHOUSE_ID` names, in the catalog and schema of the first Databricks expose the build writes (`builds[].outputs`). The job is named `fluid <product> <build>`.

The job runs `dbt deps`, then `dbt build` with the selectors and vars a local run uses. It runs in a serverless environment (version 2) with `dbt-databricks>=1.8.0,<2.0.0`.

```yaml
builds:
  - id: transform
    pattern: hybrid-reference
    engine: dbt
    repository: ./dbt                  # a local project, or an https:// Git URL
    properties:
      model: orders
    execution:
      trigger:
        type: schedule
        cron: "0 6 * * 1-5"
        timezone: Europe/Zurich
      retries:
        maxAttempts: 3
        initialDelay: 5m
      notifications:
        - type: email
          target: data-engineering@company.example.com
          condition: failure
      runtime:
        platform: databricks
        timeout: 1h
    outputs:
      - orders
```

### Where the dbt project comes from

`repository` is one of two things.

**A local project** is uploaded to the workspace as files, under the applying identity's home folder: `.fluid/<product>/<build>/files`, with each id replaced by a digest so no two products share a folder. Only what dbt reads goes up:

- `dbt_project.yml`, `packages.yml`, `dependencies.yml`, `package-lock.yml` and `selectors.yml`;
- the directories the `*-paths` keys of `dbt_project.yml` name (by default `models`, `macros`, `seeds`, `snapshots`, `tests` and `analyses`).

Never uploaded: `profiles.yml`, `target/`, a hidden file or directory, a symbolic link. A path key that names the project root, a hidden directory or a place outside the project is refused. The upload takes at most 1000 files and 20 MiB, and a file may be 2 MiB. The apply uploads the project as it is when the apply runs, as a local dbt run reads it when it runs. A plan's `planDigest` and `bundleDigest` bind the contract, not the project's files.

**A Git URL** is cloned by Databricks, and nothing is uploaded. It must be `https://` with no user or password in it, on `github.com`, `gitlab.com`, `bitbucket.org` or `dev.azure.com`. Name exactly one ref, once: `?branch=`, `?tag=` or `?commit=`. Add `&path=` for a project below the repository root. A private repository needs a Git credential in Databricks.

```yaml
    repository: https://github.com/acme/orders-dbt?tag=v1.2.0&path=dbt
```

### Triggers, retries, notifications, timeout, run-as

| Contract | Job |
| --- | --- |
| `trigger.type: schedule` (or no type) with `cron` | A Quartz `schedule`, days of the week by name. `trigger.timezone` is an IANA name; the default is `UTC`. |
| `trigger.type: continuous` | Databricks' `continuous` trigger. |
| `trigger.type: manual`, or no trigger | No trigger. Start a run from the job's page or with `databricks jobs run-now`. |
| `retries.maxAttempts` | The first run counts, so `3` is two retries. |
| `retries.initialDelay` | The fixed interval between attempts. |
| `notifications` of `type: email` | The job's email notifications, `condition` of `success`, `failure` or `always` (default `failure`). |
| `runtime.timeout` | The task timeout. |
| `runtime.serviceAccount` | `run_as`, for a service principal only (below). |

A job runs as the identity that applies it. A contract can name a service principal's application id in `runtime.serviceAccount`, and the job runs as it only if that id is listed in `FLUID_DATABRICKS_RUN_AS_ALLOWLIST` (comma-separated) where `fluid apply` runs. A contract alone never picks the identity. A user is never accepted.

### What is refused

`fluid validate` and `fluid generate iac` refuse what the job would take and not honour:

- an event or dataset trigger, or a cron and a `schedule` that disagree;
- a backoff that is not fixed, or a `maxDelay`;
- a Slack notification, or an email target that is not an address;
- `runtime.image`, `environment`, `executor`, or `resources.cpu`, `memory`, `disk`;
- a `vars` value holding an `{{ env.* }}` template, which the job settings would store in clear;
- a `serviceAccount` that is not an application id, or is not in the allowlist;
- a Git URL that breaks the rules above, and a Git host outside the four.

### Applying and removing

`fluid apply --mode amend-and-build` leaves such a build to its job. It does not run dbt on the applying machine; it prints the job's name and how to start a run now. A dbt build without `runtime.platform: databricks` still runs locally with the dbt-databricks profile. forge-cli's own schedules (`fluid generate schedule`, the Airflow DAG `fluid apply` writes) give a Databricks job build no task: Databricks starts its runs.

Removing a job, an uploaded file or a folder from the contract needs no `--allow-data-loss`, since no table data is lost. The job's run history goes with the job, and the apply says so.

## Tables a dbt build writes

dbt's `table` materialization rebuilds a table with `CREATE OR REPLACE`. So after the apply creates a table that a dbt build writes (locally or as a job), the module leaves its definition to dbt. It ignores the table's columns, partitions, clustering, properties and comment, and sets no column mapping. Each apply reports the column drift it no longer reconciles, and `fluid verify` is the gate.

::: warning Known limitation in 0.26.0: the rebuild drops NOT NULL
The rebuild drops a contract's `required: true`, so `fluid verify` reports the column as a nullability mismatch. The column stays `NOT NULL` only if the dbt model declares it: an enforced model contract with a `not_null` constraint.

```yaml
models:
  - name: orders
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
        data_type: string
        constraints:
          - type: not_null
```
:::

## What validate refuses

`fluid validate` refuses what would apply with exit 0 and not be enforced:

- a host in the contract, on a binding or a build;
- Iceberg, masks, row filters, column restrictions, a `packaging` block;
- a `binding.location` key the module would drop (`path`, `region` and others);
- duplicate partitions;
- a column type Databricks has no mapping for (it would be created as `string`), or would reject.

It warns when a `DECIMAL` has no scale, because it would keep no fractional digits.

## CLI commands

```bash
fluid validate contract.fluid.yaml
fluid generate iac contract.fluid.yaml --out iac
fluid plan contract.fluid.yaml --out plans/plan.json
fluid apply contract.fluid.yaml --yes
fluid verify contract.fluid.yaml
fluid diff contract.fluid.yaml
fluid doctor --verbose
fluid auth logout databricks <profile>
```

`fluid apply` routes through OpenTofu automatically for `platform: databricks`, as for the other clouds; there is no flag. It verifies `bundleDigest` and `planDigest` before any `tofu apply`.

### `fluid verify`

Install the extra first: `pip install 'data-product-forge[databricks]'`. Verify reads the live Unity Catalog table and checks three things:

1. **Columns** against the contract. A missing column or a changed type is `CRITICAL`; an extra column is `INFO`; a nullability mismatch is graded as for the other warehouses.
2. **`USE CATALOG`** for every reader (or `ALL PRIVILEGES`), read from the catalog's effective permissions. A reader without it is `CRITICAL`, and the finding carries the `GRANT` its owner runs. A privilege a group conveys counts ([forge-cli #775](https://github.com/Agenticstiger/forge-cli/pull/775)).
3. **Jobs**: each dbt build that writes the expose has exactly one job of its name. None means `fluid apply` did not run or the job was deleted. Several mean an apply without its state created a duplicate.

A missing table is `CRITICAL` ("run `fluid apply`"). A failure to reach the workspace is reported as a result, not a traceback, and no message carries a token.

### `fluid diff`

`fluid diff` initialises OpenTofu with the committed lock and checks the state. Its live comparison has no Databricks inspector, so it reports the expose as not checked (`no live inspector for platform 'databricks'`). Use `fluid verify` for the live table.

### `fluid doctor` and the welcome scan

`fluid doctor --verbose` shows a **Databricks Provider** row in its provider table:

- `⚪ Not configured` when none of `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, `DATABRICKS_CONFIG_PROFILE` and `DATABRICKS_WAREHOUSE_ID` is set;
- `✅ Configured` when the credential resolves (it shows the workspace and auth method) and the warehouse id is set;
- `⚠️ Needs attention` when the credential is refused (with the reason and the fix) or the warehouse id is missing.

The row also says whether `databricks-sdk` is installed, and gives the install command when it is not.

It never opens a connection, never prints a token, and never fails `fluid doctor`. The `fluid forge` welcome scan lists Databricks among the detected clouds when `DATABRICKS_HOST` is set with a token, an OAuth pair or a profile name.

### `fluid auth logout databricks`

`~/.databrickscfg` belongs to the Databricks CLI, SDK, dbt and terraform and holds every profile. Logout removes only the profile you name ([forge-cli #772](https://github.com/Agenticstiger/forge-cli/pull/772)):

```bash
fluid auth logout databricks dev
```

```text
Removed profile 'dev' from /path/to/.databrickscfg (kept: DEFAULT). The token or secret it held stays valid until it is revoked in the Databricks workspace.
```

It keeps every other profile, writes the file back owner-only (`0600`) and never deletes it. With no profile named, a file that holds profiles is left alone and the command exits `1`, listing them. `DATABRICKS_CONFIG_PROFILE` is quoted in that hint, never acted on. `DATABRICKS_CONFIG_FILE` moves the file, and `fluid auth login` and `fluid auth status databricks` read it too. An OAuth profile (`auth_type = databricks-cli`) is left to `databricks auth logout --profile=<name> --delete`, which clears its cached tokens. Every logout also removes the host and token `fluid auth login` saved in the OS keyring.

## Limitations

- **No live drift check in `fluid diff`.** Use `fluid verify`.
- **Jobs are not adopted.** A job's import id is a job id, which neither the contract nor `tofu` can look up by name. An apply that lost its state creates a second job. `fluid verify` flags the duplicate; delete the extra one.
- **Shared schemas.** A schema shared between products needs the packaging modes, which are refused for Databricks for now.
- **dbt rebuild drops `NOT NULL`** unless the model declares it (above).
- **The catalog is never created or granted.** Create it and grant `USE CATALOG` yourself.
- **Empty folders stay.** The `.fluid/<product>/<build>` folders above `files/` are not managed; only `files/` and below are.

## How it is tested

The full matrix is in `HONESTLY_TESTED.md` in forge-cli. In short:

| Tier | What it covers |
| --- | --- |
| Unit | 471 tests across the emitter, jobs, credentials, engine hooks, cron conversion, the dbt runner, verify, doctor and the welcome scan, against a stubbed SDK client. |
| `tofu validate` | Both job modules (Git and workspace upload) and the dbt-written table's `ignore_changes` list validate against provider 1.140.0's schema. |
| Stand-in workspace | The real `fluid` CLI, `tofu` and provider 1.140.0 against an in-process stand-in for the Unity Catalog, SQL statement, permissions and jobs APIs: plan, apply, an empty second plan, the data-loss gate, adoption, job and file removal. The stand-in does not check SQL dialect or privilege names. |
| Live, Databricks Free Edition | One manual run on 2026-11-01 with the real `fluid` CLI: validate, plan, dry-run and apply, an empty second plan, one job run that succeeded and built the table, `fluid verify` with the real SDK, a model change, and removal of the job and its files. Everything the run created was swept afterwards. |
| Emulator (nightly, not gating) | First run on 2026-10-30 passed 1 of 4: creates and the replace gate work, but a second plan is not empty against the emulator. |

Not proven live: a Git source, profile or OAuth auth, a run-as service principal, table adoption, a larger project, and re-adopting a job after lost state.
