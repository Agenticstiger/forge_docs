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
- ✅ **dbt builds as jobs**: a dbt build whose `execution.runtime.platform` is `databricks` becomes a serverless job that Databricks runs on its own trigger. *(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* `fluid apply --mode amend-and-build` also starts a run now and waits for it (see [Running the job from `fluid apply`](#running-the-job-from-fluid-apply))
- ✅ **Contract rules as dbt tests**: *(since 0.30.0, [forge-cli #871](https://github.com/Agenticstiger/forge-cli/pull/871))* The `dq.rules` of the exposes a dbt job writes run as dbt tests in the job, and a failing rule of severity `critical` or `error` fails the run (see [Contract rules as dbt tests](#contract-rules-as-dbt-tests))
- ✅ **Lakeflow pipelines**: *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* A build with `engine: lakeflow` (schema 0.7.7 preview) becomes a Lakeflow Declarative Pipeline whose expectations are the contract's `dq.rules`, and `fluid apply --mode amend-and-build` runs it and prints each rule's counts (see [Lakeflow pipelines](#lakeflow-pipelines))
- ✅ **Residency**: `binding.location.region` is checked against the contract's `sovereignty` policy and against the workspace's metastore (see [Residency](#residency))
- ✅ **Verify**: `fluid verify` checks the live table's columns, `USE CATALOG` for every reader, the residency, the governance tags, the bound masks and row filter, and that each dbt job exists exactly once
- ✅ **One pinned credential**: the workspace comes from `DATABRICKS_HOST` only, and a run never falls back to a stray profile
- ⚠️ **Live drift**: `fluid diff` has no Databricks inspector yet (see [`fluid diff`](#fluid-diff))
- ✅ **Column masks, row filters, denied columns**: Unity Catalog SQL functions that `fluid apply` binds on the table (see [Column masks and row filters](#column-masks-and-row-filters))
- ✅ **Metric views**: an expose's `semantics` block becomes a Unity Catalog metric view beside its table, which Genie, AI/BI dashboards and SQL read with `MEASURE()` (see [Metric views](#metric-views)) *([forge-cli #865](https://github.com/Agenticstiger/forge-cli/pull/865), since 0.30.0)*
- ✅ **Retention**: `lifecycle.expire` is accepted for a table rebuilt in full on every run, and `fluid verify` checks the table's Delta history against it (see [Retention](#retention))
- ✅ **Landing from a DuckDB acquisition**: the acquisition runner uploads Parquet to a Unity Catalog volume and loads the table with `INSERT OVERWRITE`, applying `policy.privacy.masking` before the data leaves the machine (see [Landing a DuckDB acquisition](#landing-a-duckdb-acquisition))
- ✅ **Described in Unity Catalog**: table and column comments from the contract, the product's identity as table tags, a column's `sensitivity` as a column tag, and Unity Catalog's certification (see [Comments and product tags](#comments-and-product-tags) and [Certification](#certification)) *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))*
- ✅ **Scoped grants**: an `accessPolicy` grant with `resources` is placed only on the tables it names (see [Scoping a grant to an expose](#scoping-a-grant-to-an-expose))
- ✅ **Data quality monitoring**: *(since 0.30.0, [forge-cli #864](https://github.com/Agenticstiger/forge-cli/pull/864))* An expose that states a freshness or completeness SLO turns on Databricks data quality monitoring for its schema, and Catalog Explorer shows the table's Quality indicator (see [Data quality monitoring](#data-quality-monitoring))
- ❌ **Iceberg, `packaging`, and the governance fields that are not mapped**: `fluid validate` refuses them rather than apply something that is not enforced (see [What validate refuses](#what-validate-refuses))

## Prerequisites

| You need | Why |
| --- | --- |
| OpenTofu `1.6.0` or newer on `PATH` | `fluid apply` runs `tofu`. An older one stops the run. |
| A Unity Catalog workspace with an existing catalog | The catalog is read, never created. The identity that applies needs `USE CATALOG` and `CREATE SCHEMA` on it. |
| A SQL warehouse, its id in `DATABRICKS_WAREHOUSE_ID` | Every table statement runs on it, and so do the dbt jobs. Find the id under SQL Warehouses, Connection details. The id is not a secret. |
| A Unity Catalog volume of its own, `/Volumes/<catalog>/<schema>/<volume>` in `DATABRICKS_STAGING_VOLUME` | Only for a DuckDB acquisition that lands in Databricks (see [Landing a DuckDB acquisition](#landing-a-duckdb-acquisition)). |
| `pip install 'data-product-forge[databricks]'` | The extra brings `databricks-sdk`. `fluid verify` needs it, and so does `fluid apply` to bind [column masks and row filters](#column-masks-and-row-filters) and to [land a DuckDB acquisition](#landing-a-duckdb-acquisition). *(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* An apply that [runs a dbt job](#running-the-job-from-fluid-apply) needs it too. *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* So does one that [runs a Lakeflow pipeline](#running-it-from-fluid-apply). |

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
| `qos.freshnessSLO`, `qos.completenessTarget` or another freshness or completeness SLO | *(since 0.30.0, [forge-cli #864](https://github.com/Agenticstiger/forge-cli/pull/864))* A `databricks_data_quality_monitor` on the schema (see [Data quality monitoring](#data-quality-monitoring)). |
| A build with `engine: lakeflow` | *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* A serverless Lakeflow pipeline and its source file, and no table resource: the pipeline creates its table (see [Lakeflow pipelines](#lakeflow-pipelines)). |

Permissions map to table privileges: `read`, `select` and `query` to `SELECT`; `write`, `insert`, `update` and `delete` to `MODIFY`; `admin` and `manage` to `ALL_PRIVILEGES`. `create` has no table privilege and is skipped.

A principal is a user's email, a group's name or a service principal's application id, written bare. A `user:` or `group:` prefix is stripped. A service account or domain principal has no Unity Catalog counterpart, so map it in `binding.principals` or the run is refused.

A grant with `resources` goes only on the tables it names (see [Scoping a grant to an expose](#scoping-a-grant-to-an-expose)).

A grant is authoritative for its principal. If the schema already existed and other teams share it, each principal the contract names keeps `USE_SCHEMA` alone on it. Give a product its own schema.

### Scoping a grant to an expose

*(since 0.27.0, [forge-cli #801](https://github.com/Agenticstiger/forge-cli/pull/801))*

An `accessPolicy` grant may name the exposes it is for in `resources`. Databricks evaluates three shapes, and a grant without `resources` is for every expose:

```yaml
accessPolicy:
  grants:
    - principal: group:data-analysts
      permissions: [read]
      resources:
        - "$.exposes[?(@.exposeId=='orders')]"
```

| `resources` entry | Grant goes on |
| --- | --- |
| `$.exposes[?(@.exposeId=='<id>')]` (either quote, spaces allowed) | The table of that expose. Repeat the entry for several exposes. |
| `$.exposes[*]` or `$.exposes` | Every expose's table. |
| No `resources` | Every expose's table. |

Anything else is refused as `databricks-grant-scope-unmapped`, rather than placed on more tables than the contract names: a path forge-cli cannot evaluate, a blank entry, or an `exposeId` the contract does not have. `fluid verify` checks `USE CATALOG` per table, so a scoped principal is checked only on the tables it was granted. A reader named in `policy.authz.readers` or `writers` is for that expose alone, as before.

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
| A removed label (its tag assignment) | Not refused: it holds no data. The apply prints it. |
| A removed data quality monitor | *(since 0.30.0, [forge-cli #864](https://github.com/Agenticstiger/forge-cli/pull/864))* Not refused: it holds no table data. The apply prints it (see [Data quality monitoring](#data-quality-monitoring)). |
| A missing catalog, missing credentials or an unreachable workspace | Fails at plan, naming the catalog, the variables to set or the host. |

An apply that stops before it applies anything (`--mode dry-run`, a refusal, the data-loss gate, a failed plan) hands back any object it imported with `tofu state rm`. The objects stay as they are, and the next apply adopts them again.

### A schema the contract stops using

*([forge-cli #873](https://github.com/Agenticstiger/forge-cli/pull/873), since 0.30.0)*

When a table moves to another schema or catalog, or a schema's last expose is removed, the saved plan destroys the old schema. It destroys the table too, so the apply needs `--allow-data-loss`, and so does its dry-run. OpenTofu never force-destroys a schema, and Unity Catalog refuses to delete one that holds anything. Two things this product makes there are no OpenTofu resource, so nothing in the plan removes them: its [metric views](#metric-views) and the functions of its [column masks and row filters](#column-masks-and-row-filters). Before 0.30.0 the apply failed at that schema until they were dropped by hand.

Now `fluid apply` clears them, in each schema the saved plan destroys and the contract no longer names:

1. **Before `tofu apply`**, it drops this product's metric views over the tables the plan destroys or that no longer exist, and the mask and row filter functions that no table uses.
2. **`tofu apply`** destroys the tables. When they had masks or a row filter, their functions are still in the schema, so its destroy fails.
3. **Then** it drops those functions, plans again, and applies the destroys that waited (`tofu plan (the destroys that waited): +0 ~0 -<n>`). It does this only when every error was the failed destroy of such a schema, the drops cleared each of those schemas with nothing left in it, and the new plan holds only those destroys. Otherwise the apply's own error stands.

What it drops, and what it leaves:

- **Only the deploy identity's objects go.** A view or function another identity owns, or whose owner cannot be read, is left.
- **A view goes only with this product's `fluid.product_id`**, and only when the table it reads is one the plan destroys or no longer exists.
- **A function goes only under a name forge-cli gives one** (`fluid_rf_<table>_<hash8>`, `fluid_mask_<table>_<column>_<hash8>`), and never while a table or view of the schema still uses it. Unity Catalog binds a mask or a row filter by the function's name, so that table could read through whatever function someone made next under that name.
- **Only schemas this environment's own OpenTofu state holds are looked in.** They come from the saved plan, never from a search of the catalog, so another environment of the product keeps its objects.
- **Anything else the schema holds is named and left**: a table or view the plan keeps, another product's view, an object another identity owns, and a function a kept table uses or forge-cli did not name. The run prints `note: OpenTofu cannot destroy <schema> while it holds <what, and why>. Move or drop them, then re-run fluid apply.`, and the schema's destroy fails until they are moved or dropped. A volume or a model in the schema is neither dropped nor named.
- **A schema that cannot be read has nothing in it dropped.** Without `databricks-sdk`, or when the Databricks client cannot be created, no schema is checked, and the run says so.
- **`--mode dry-run` prints the drops and runs none.** Under `Schemas this apply destroys, and what is in them outside OpenTofu`, it lists what goes before the apply (`before apply: drop metric view <name>: <why>`) and what waits for the tables (`after tofu destroys <table>: drop function <name>`), each with its `DROP` statement, and ends with `dry-run: none of these statements ran.`

### Adopting an existing table

A table that already exists is imported before the first apply, not replaced. Its existing grants are imported with it, so a privilege the contract does not name shows in the plan as an update that removes it.

- **With column mapping** (`delta.columnMapping.mode=name`): adopted.
- **Without it**: refused, with or without `--allow-data-loss`. Setting the property upgrades the table's Delta protocol, which older readers and some external engines cannot read, and unsetting it does not undo that. The message gives the statement its owner runs once every reader can read column mapping:

  ```sql
  ALTER TABLE `main`.`sales`.`orders` SET TBLPROPERTIES ('delta.columnMapping.mode' = 'name')
  ```

  Or leave the table out of the contract, or let a dbt build write it.

## Governance

What a contract says about where its data lives and who may read it, and what forge-cli does with each field on Databricks. Each part below says what is enforced, where, and what `fluid verify` reads back.

| Contract | On Databricks | Verify dimension |
| --- | --- | --- |
| `binding.location.region` with `sovereignty` | Held by the policy at `fluid validate`, `fluid apply` and `generate iac`, and checked against the workspace's metastore at plan time (see [Residency](#residency)) | `residency` |
| `labels`, and the classification, jurisdiction, regulation and residency a contract carries | Unity Catalog tags on the schema and the table (see [Governance tags](#governance-tags)) | `governance_tags` |
| `description`, the product's identity, `sensitivity` and the certification label | Table and column comments, product tags on the table, column tags and `system.certification_status` *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* (see [Comments and product tags](#comments-and-product-tags) and [Certification](#certification)) | `governance_tags` |
| `lifecycle.expire` with `lifecycle.retention` | Accepted for a table rebuilt in full on every run, when the retention covers the table's Delta history (see [Retention](#retention)) | `retention` |
| `policy.authz.columnRestrictions` and `rowFilters` | SQL functions bound on the table as column masks and a row filter, by `fluid apply` only (see [Column masks and row filters](#column-masks-and-row-filters)) | `row_filter_masks` |

### Residency

*(since 0.27.0, [forge-cli #778](https://github.com/Agenticstiger/forge-cli/pull/778))*

A workspace is in one region. A contract's [`sovereignty`](../concepts/sovereignty.md) policy is checked for a Databricks expose as it is for the other clouds, from the region the expose declares in `binding.location.region`:

```yaml
sovereignty:
  jurisdiction: EU
  deniedRegions: [us-west-2]
  enforcementMode: strict

exposes:
  - exposeId: orders
    binding:
      platform: databricks
      format: delta_table
      location:
        database: main
        schema: sales
        table: orders
        region: eu-central-1     # the region of the workspace DATABRICKS_HOST names
```

The rules:

- **A declared region is held to the policy** (`allowedRegions`, `deniedRegions`, `jurisdiction`) like any cloud region.
- **With a `sovereignty` block, no region is a finding.** An error under `enforcementMode: strict`, a warning under `advisory`. Where the data lives cannot be checked without one.
- **The policy holds at apply, not only at validate.** `fluid apply` and `fluid generate iac` refuse a placement the policy forbids with `SovereigntyViolationError`, before any module is written, so before `tofu init`, an import or an adoption.
- **The refusal says why.** *(since 0.28.0, [forge-cli #835](https://github.com/Agenticstiger/forge-cli/pull/835))* `fluid generate iac` used to turn the refusal into `generate_iac_failed` and print only the finding. It now prints the error's panel, with the reason, the fix and the doc link, as `fluid apply` does. Captured with `jurisdiction: EU`, `allowedRegions: [eu-central-1]` and a `binding.location.region` of `us-west-2` (terminal width 100):

  ```text
╭────────────────────────────────── ✗ SovereigntyViolationError ───────────────────────────────────╮
│ Databricks placement refused by the sovereignty policy: orders: Region 'us-west-2' not in        │
│ allowed regions list; orders: Region 'us-west-2' (jurisdiction: US) does not match required      │
│ jurisdiction: EU                                                                                 │
│ why  contract.sovereignty is enforced (strict) and allows eu-central-1; the tables would be      │
│ created in the workspace DATABRICKS_HOST names.                                                  │
│ fix  Set binding.location.region on every databricks expose to the region of the workspace       │
│ DATABRICKS_HOST names, one the policy allows, or change the policy.                              │
│ doc  https://agenticstiger.github.io/forge_docs/concepts/sovereignty.html                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
  ```

  A refusal whose message is too long for the panel's title (one that lists every finding) is printed whole inside the panel, not cut at the border.
- **The spelling is exact.** The region must be a plain lower-case name: lower-case letters, digits and hyphens, starting with a letter, 2 to 63 characters, no spaces (`eu-central-1`, `westeurope`, `europe-west3`). Anything else is refused as `databricks-region-invalid`. It is not lower-cased for you: the policy compares the text as written, so `US-WEST-2` would otherwise pass a `deniedRegions: [us-west-2]` check and still plan against a workspace in us-west-2.
- **One region per contract.** The module applies to one workspace (`DATABRICKS_HOST`). Two Databricks exposes that declare different regions are refused as `databricks-region-conflict`.
- **The declaration is checked against the workspace, at plan time.** With a region declared, the module reads the workspace's metastore (`data.databricks_current_metastore`), and every schema it owns carries a precondition that the metastore's region equals the declared one. `tofu plan` fails, `--mode dry-run` included, before anything is written, when `DATABRICKS_HOST` names a workspace elsewhere. The run stops with `opentofu_plan_failed` and kind `databricks-residency-region`, and prints one line with both regions and the fix (the wording from [forge-cli #801](https://github.com/Agenticstiger/forge-cli/pull/801), since 0.27.0):

  ```text
  the contract declares binding.location.region eu-central-1, but the workspace DATABRICKS_HOST names is in us-west-2. Point DATABRICKS_HOST at a workspace in eu-central-1, or correct binding.location.region.
  ```

  When the plan output does not show the live region, the line says "in a region the plan output does not show". The precondition sits on every schema the module owns, whichever expose declared the region.
- **No region and no `sovereignty` block** gives the module it always did.

`fluid verify` reads the workspace's metastore summary and reports a `residency` dimension: it passes when the region matches the declaration (compared without regard to case), fails with the fix when it does not, and is skipped when the contract declares none. A mismatch raises the result to `CRITICAL`.

::: warning Not proven live
Whether a real metastore reports its region in the spelling a contract declares (GCP's `europe-west3`, for one) is not proven against a live workspace, nor is a workspace with no metastore assigned, where the plan should fail on the data source. If the spelling differs, the plan fails and names both regions.
:::

### Governance tags

*(since 0.27.0, [forge-cli #779](https://github.com/Agenticstiger/forge-cli/pull/779))*

A contract's governance labels reach AWS as tags and Glue parameters and GCP as labels. On Databricks they are Unity Catalog tags, one `databricks_entity_tag_assignment` per tag, built from the same source as the other two clouds (`iac/governance_labels.py`). Before this change the Databricks module never read `labels`, and nothing said so.

The tags a contract carries are its and the expose's `labels`, plus `fluid_classification`, `fluid_jurisdiction`, `fluid_regulation` and `fluid_residency`, from the classification (the expose's `policy.classification`, else `metadata.classification`) and the contract's `sovereignty` block. Keys first pass through the label alphabet the three clouds share (lower-case letters, digits, `_` and `-`, at most 63 characters), so a tag has the same key on each. Values are written as the contract states them; see **Values** below.

| On | Carries |
| --- | --- |
| Each schema the product owns | The contract's own labels and governance values. Two exposes in one schema give the same tags. |
| Each table | The same, plus the expose's labels and classification. |

Two rules shape the keys:

- **A `-` in a key becomes `_`.** A Unity Catalog tag key may not contain `. , - = / :`, and a governance label key is lower-case letters, digits, `_` and `-`. `data-classification` is the tag `data_classification`; `fluid_jurisdiction` stays as it is.
- **Nothing is dropped, nothing is overwritten.** Two labels that become one key (`cost-center` and `cost_center`) are refused as `databricks-tag-collision`. More than the 50 tags a Unity Catalog securable holds is refused as `databricks-tags-too-many`. `fluid validate` reports both. *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* On a table, the product's own tags (see [Comments and product tags](#comments-and-product-tags)) count toward the 50 with the governance labels, and a label that becomes one of their keys is also `databricks-tag-collision`.

**Values.** *([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* A tag value is the contract's text, less the surrounding whitespace Unity Catalog refuses. It keeps case, spaces and punctuation, and `fluid_regulation` joins the frameworks with `, `. A value over 256 characters is refused as `databricks-tag-value-too-long` rather than cut, and `fluid validate` reports it too. Up to 0.29.0 a value went through the label alphabet as well: lower-cased, with each character other than a letter, a digit, `_` or `-` turned into `-`, and cut at 63 characters. GCP labels and AWS tags still do.

These labels and `sovereignty` fields, compiled offline with `fluid generate iac` on each release, give the same keys and these values:

```yaml
labels:
  business-value: "A single unrenewed ground lease can strand a multi-tenant tower"
  cost-center: CC-42
sovereignty:
  jurisdiction: US
  regulatoryFramework: [GDPR, CCPA]
```

| Tag | 0.29.0 | 0.30.0 |
| --- | --- | --- |
| `business_value` | `a-single-unrenewed-ground-lease-can-strand-a-multi-tenant-tower` | `A single unrenewed ground lease can strand a multi-tenant tower` |
| `cost_center` | `cc-42` | `CC-42` |
| `fluid_jurisdiction` | `us` | `US` |
| `fluid_regulation` | `gdpr_ccpa` | `GDPR, CCPA` |

**A deployment made before 0.30.0** gets the new values at its next `fluid apply`, which updates each changed tag in place (`~` in the plan). A tag assignment's address and import id depend on its key alone, and the provider (1.140.0) updates `tag_value` without replacing the assignment. So no table, schema or data is replaced or destroyed, and no `--allow-data-loss` is needed. Until that apply, `fluid verify` reports each old value as a changed tag, `CRITICAL`.

A contract with no labels gets the module it always did. *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* Since 0.28.0 that is no longer so for a table: a contract with no labels still gets the product's own tags on it.

An assignment that already exists is imported before the first apply, best-effort as grants are, so a run after lost state adopts it instead of failing. Removing a label destroys only its assignment. That holds no data, so it does not need `--allow-data-loss`: the apply prints it, as it does a revoked grant.

`fluid verify` reads the table's and its schema's tags into a `governance_tags` dimension. Every tag the contract implies must be there with its value. A missing or changed tag is `CRITICAL`, with `fluid apply` as the fix. A tag someone else set is ignored, and a module that sets no tag and no comment skips the dimension. The tag list is paginated: verify follows every page, and a repeated page token or more than 100 pages is an error, not a pass.

::: warning Tags on a table a dbt build writes
Databricks does not document whether a table keeps its tags across the `CREATE OR REPLACE` a dbt `table` materialization runs, and forge-cli has not proven it. If tags go missing after a build, `fluid apply` sets them again. `fluid verify` is the gate.
:::

*([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* forge-cli ran the change on Databricks Free Edition: a product carrying the 0.29.0 values planned `+0 ~17 -0` and applied, `information_schema.table_tags` then showed the values as the contract states them, and `fluid verify` passed on all 27 tags.

### Comments and product tags

*(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))*

`fluid apply` describes the table in Unity Catalog from the contract, so it looks like a native one.

**Comments.**

- The table's comment is the expose's `description`, else the product's. A product `description` written as an object contributes its `purpose`.
- A column's comment is its `contract.schema[].description`.
- A description with a backslash is refused as `databricks-comment-unsafe`: the provider escapes only quotes when it writes `COMMENT '...'`, and Databricks reads a backslash in a literal as an escape, so a trailing one, or one before a quote, would break the literal. One with `${` is refused as `databricks-comment-unsafe` too, because Spark may replace it with a variable, setting or environment value before the comment is stored.

**Product tags.** Each table carries these tags, built from the contract. A field the contract does not state makes no tag. Only `fluid_domain`, `fluid_layer`, `fluid_product_type` and `fluid_version` are keys AWS Glue and Snowflake already use; `fluid_product_id`, `fluid_product_name`, `fluid_product_version` and `fluid_owner_team` are new.

| Tag | From |
| --- | --- |
| `fluid_product_id` | `id` |
| `fluid_product_name` | `name` |
| `fluid_domain` | `domain` |
| `fluid_layer` | `metadata.layer` |
| `fluid_product_type` | `metadata.productType` |
| `fluid_product_version` | the expose's `version` |
| `fluid_version` | `fluidVersion` |
| `fluid_owner_team` | `metadata.owner.team` |

These count toward Unity Catalog's 50 tags per securable, together with the governance labels, the classification tags and the certification tag. A contract with no labels still carries these. A label that becomes one of these keys is refused as `databricks-tag-collision`, but only for a key the contract states: with no `metadata.productType`, a label `fluid_product_type` is no collision. A tag value longer than 256 characters is refused as `databricks-tag-value-too-long`, rather than cut, since a cut id or name would name another product.

The table's owner is unchanged. The deploy identity keeps owning it, which the masks, the row filter and the fail-safe lock depend on. The owner team is only a tag.

**Column tags.** A column the contract classifies with `sensitivity` carries it as the column tag `fluid_sensitivity`. A table holds at most 1,000 column tags, and more is refused as `databricks-tags-too-many`. A `sensitivity` over 256 characters is refused as `databricks-tag-value-too-long`.

A contract with one classified column and two labels, validated and compiled offline (`fluid generate iac`), gave these table tags, with the column tag on `email`:

```text
cost_center            cc42
fluid_domain           sales
fluid_layer            Gold
fluid_owner_team       data-engineering
fluid_product_id       sales.orders_dbx
fluid_product_name     Orders
fluid_product_version  1.0.0
fluid_version          0.7.5
system.certification_status  certified
```

Read back on a live workspace on 2026-11-04 (comments, product tags, column tags and `certified`, with an admin token). Not tried live: a non-admin identity holding only ASSIGN.

#### Comments on a dbt-written table

On a table a dbt build writes, the comments stay dbt's. Its `CREATE OR REPLACE` sets the table and column comments from the model (with `persist_docs`), so forge-cli sets none there. The product tags, the column tags and the certification are still set. `fluid validate` passes and, when the contract describes the table or a column, warns. Captured:

```text
✅ Valid FLUID contract (schema v0.7.5)
⚠️  1 warning(s)
Validation completed in 0.021s

Validation Warnings:
====================
 1. exposes[0] (orders) is written by dbt, whose CREATE OR REPLACE sets the table and column comments: Unity Catalog shows the dbt model's descriptions (with persist_docs), not the contract's, so fluid apply sets none.
```

`fluid verify` checks no comment on such a table.

### Certification

*(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))*

Unity Catalog marks an asset as certified or deprecated with the system governed tag `system.certification_status`. forge-cli sets it on each Databricks table from the contract:

| Value | When |
| --- | --- |
| `deprecated` | `lifecycle.state` is `deprecated`, on the expose, else on the product. |
| `certified` | The label `certification: certified` is on the expose, else on the product, and the state is not `deprecated`. |

- **A deprecated product is never shown as certified**, whatever its label.
- **The label is not also a plain tag.** It becomes the certification tag and no `certification` tag.
- **Any other value is refused** as `databricks-certification-invalid` (compared in lower case, so `Certified` passes as `certified`), unless the state is `deprecated`, which wins before the label is read. Unity Catalog's tag takes only `certified` and `deprecated`.
- **Scope.** *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* A `labels.certification` on the product certifies every Databricks table of the product. One on an expose certifies only that expose's table.
- **ASSIGN.** This tag is a system governed tag, so the deploy identity needs the ASSIGN permission on it, besides `APPLY TAG` on the table. That comes from Databricks' documentation and the SDK's `EntityTagAssignmentsAPI.create`. It was read back live with an admin token (2026-11-04); a non-admin identity holding only ASSIGN was not tried. The apply engine prints a note after the `tofu plan` summary, indented by two spaces, on a dry run too:

```text
  note: system.certification_status is set on main.sales.orders (certified): a system governed tag, so this identity needs the ASSIGN permission on it, which an account or workspace admin grants, or the tag assignment fails.
```

The text is the plugin's `plan_notices` output for the example contract, captured offline; the engine adds the `note: ` prefix and the indent.

### Column masks and row filters

*(since 0.27.0, [forge-cli #785](https://github.com/Agenticstiger/forge-cli/pull/785))*

`policy.authz.columnRestrictions` and `policy.authz.rowFilters` were refused on Databricks. They are now enforced by Unity Catalog itself: forge-cli creates SQL functions and binds them on the table with `ALTER TABLE ... SET ROW FILTER` and `ALTER COLUMN ... SET MASK`. The engine then rewrites a restricted principal's query, whichever tool sends it. The semantics are the ones GCP and AWS give the same fields, with the differences noted below.

```yaml
exposes:
  - exposeId: orders
    # binding and contract.schema as above, with a `region` column
    policy:
      authz:
        readers:
          - "group:data-analysts"
          - "group:contractors"
        columnRestrictions:
          - principal: group:data-analysts
            columns: [amount]
            access: mask
            mask: last_four        # last_four, first_four or nullify
          - principal: group:contractors
            columns: [amount, ordered_at]
            access: deny
        rowFilters:               # fluidVersion 0.7.6 (preview)
          - principal: group:data-analysts
            where: "region = 'EMEA'"
```

#### Why `fluid apply` binds them, outside OpenTofu

The `databricks/databricks` provider (1.140.0) has no function resource and no mask or filter attribute on `databricks_sql_table` ([terraform-provider-databricks #4550](https://github.com/databricks/terraform-provider-databricks/issues/4550)). So the statements run on the SQL warehouse `DATABRICKS_WAREHOUSE_ID` names, through the SQL Statement Execution API, in two hooks `fluid apply` runs around `tofu apply`:

| Hook | Does |
| --- | --- |
| Before `tofu apply` | Binds the masks and filter on every table that already exists, so a grant the apply adds lands on a protected table. A filter that needs a column the apply adds is held, until the real one can bind, by a deny-all row filter. A failure here stops the run before `tofu apply`. |
| After `tofu apply` | Binds what is still missing, on the tables the apply created (empty at that moment), and drops what the contract no longer restricts. |

- **Only what differs runs.** The live bindings are read from the Tables API first, so a second apply executes no statement. `--mode dry-run` prints the statements and runs none.
- **Removed restrictions are dropped after the apply** (`DROP ROW FILTER`, `DROP MASK`). The apply prints it as an access-widening change. It is not gated by `--allow-data-loss`, since no data is lost. Only a filter or mask whose function carries this module's `fluid_` prefix is ever dropped.
- **A binding made by hand is never replaced silently.** Where the contract asks for a row filter or mask and the table has one whose function lacks the `fluid_` prefix, the run stops before any change, on any table, and names the table, the column and the live function. Remove it, or move its rule into the contract.
- **A failed `tofu apply` still binds.** A table the apply created, its grants and the dbt job that fills it can exist with no mask or filter. A bind-only pass runs before the apply's own error is raised: it binds what exists, closes what it cannot bind, skips a table that was never created and drops nothing. The run still exits with `opentofu_apply_failed`.
- **dbt rebuilds keep them.** Databricks documents that a row filter and masks survive the `CREATE OR REPLACE TABLE` a dbt build runs. This is not proven against a live workspace.
- **The `[databricks]` extra is needed at apply** for such a contract, and the run says so when it is missing: `pip install 'data-product-forge[databricks]'`.

#### `fluid generate iac` refuses such a contract

The module `fluid generate iac` writes holds no mask or filter, and a plain `tofu apply` of it would create the table and grant `SELECT` with none of them, exposing unmasked data to the principals the contract restricts. So it refuses, as `databricks-enforcement-outside-module`, before it writes a module:

- use `fluid apply`, which binds the masks and filters before it grants, and revokes access when it cannot (`--mode dry-run` shows the statements), or
- remove the restrictions from the contract.

`fluid apply`, `fluid plan` and `fluid validate` are unaffected.

#### What the functions are

Each function is created once, as `CREATE FUNCTION IF NOT EXISTS`, under a name that carries a hash of its definition: `fluid_rf_<table>_<hash8>` for the row filter and `fluid_mask_<table>_<column>_<hash8>` for a mask, in the table's schema. Unity Catalog refuses to replace a function a filter or mask uses, so a changed predicate or rule is a new function, bound in place of the old one, and the same contract always names the same function. A superseded function is dropped by `fluid apply` after the apply succeeds ([forge-cli #801](https://github.com/Agenticstiger/forge-cli/pull/801), since 0.27.0), when no table in the schema uses it and the run's identity owns it, and the run prints `dropped superseded function <name>`. Only `fluid_rf_<table>_…`, `fluid_mask_<table>_<column>_…` and deny-all functions of the contract's tables are candidates. A function owned by another identity, or by an owner that cannot be read, is left and printed as `left function <name>: …`. A `DROP` that fails prints `note: superseded function <name> was not dropped: …` and the apply still succeeds. When a schema's tables or functions cannot all be read, nothing in it is dropped. *(since 0.28.0, [forge-cli #835](https://github.com/Agenticstiger/forge-cli/pull/835))* `fluid apply --mode dry-run` now lists those drops and runs nothing. For each `fluid_` mask or row-filter function the clean-up would drop, it prints `would drop superseded function <name> (after the apply, if it succeeds)`, and `would leave function <name>: <why>` where it would leave one. It works out the list against the bindings the apply leaves, so a function bound now to a table the contract manages is listed as droppable when the contract no longer expects it. When a schema cannot be read, the dry run prints `note: orphan functions in <catalog>.<schema> not listed: ...`. This is from the code at v0.28.0 and was not run against a live workspace. *([forge-cli #873](https://github.com/Agenticstiger/forge-cli/pull/873), since 0.30.0)* In a schema the contract stops using, the functions go too, once no table uses them (see [A schema the contract stops using](#a-schema-the-contract-stops-using)).

The hashed name can be computed from the contract, so someone with `CREATE FUNCTION` on the schema could create it first with a body that returns the value unmasked. So after each create, and before any bind, forge-cli reads the function back. Its owner (the identity the run authenticates as), body, parameters and return type must be the expected ones, whitespace aside. A function that is not is never bound, and the run prints what differs.

#### What a restriction means

- **A denied column reads `NULL`.** Unity Catalog has no column-level grant, so `access: deny` becomes a mask that returns `NULL` (cast to the column's type) for the principal. The column stays listed in the table's schema.
- **A mask returns the value masked**: `last_four` is `XXXXX` and the last four characters, `first_four` the first four characters and `XXXXX`, `nullify` is `NULL`. A value of four characters or fewer is its SHA-256 in hex instead, and a `NULL` stays `NULL`, as on AWS. `last_four` and `first_four` need a string column (`string`, `varchar`, `char`); `nullify` takes any.
- **One mask per column**, the Unity Catalog limit, so the function combines every restriction on the column. A rule belongs to the principal that names it, not to the column: one principal may read a column `nullify`ed and another `last_four`ed (GCP and AWS refuse that). The function has one branch per rule, strictest first: deny, `nullify`, `first_four`, `last_four`. A member of several groups gets the strictest that matches, and everyone else reads the value.
- **One row filter per table.** A restricted principal's members read the union of the rows its principals' predicates select. A reader no filter names reads every row.
- **Identities are tested both ways.** Logical principals resolve through `binding.principals`, and every resolved identity is tested as a group and as the current user, `(is_account_group_member('<name>') OR current_user() = '<name>')`, whatever the principal's prefix. A `group:` principal may be mapped to a service principal's application id or a user's email, and a test of the wrong kind would match no one while the grant to that identity still applied. A name that is both a group and a user is restricted either way, which errs closed.

#### Row filter predicates

A predicate is contract text that becomes a function body, so it is never spliced in. It is parsed as one boolean expression (sqlglot, Databricks dialect), checked node by node against an allowlist, and written back from the tree with its columns re-quoted.

| Allowed | |
| --- | --- |
| Operators | comparisons, `AND`, `OR`, `NOT`, `IS [NOT] NULL`, `IN`, `BETWEEN`, `LIKE`, `ILIKE`, `+`, `-`, `*` |
| Values | literals, `CAST`, and the table's columns |
| Functions | `lower`, `upper`, `length`, `trim`, `coalesce`, `abs` |

Anything else is refused as `databricks-row-filter-invalid`: a `;`, a comment, a subquery, a session function such as `current_user()`, a column the table does not have, and a predicate that reads no column.

#### If a bind fails

A mask or filter that cannot be bound must not leave the table readable. After a failed bind, including a failed read of the table, forge-cli closes it in order:

1. **A deny-all row filter** is bound for the restricted identities (a zero-column function, `RETURN NOT <any restricted identity>`, content-hashed and checked like the others). It blocks them whatever grant path gives them the table: a group they are also in, a schema or catalog grant.
2. **If that cannot be bound**, or would replace a row filter this module did not create, `SELECT` (and `ALL PRIVILEGES`) on the table is revoked from every grantee but its owner, listed through the permissions API.
3. **Paths it cannot close are named.** A grant inherited from the schema or the catalog is not one a table-level `REVOKE` reaches. The run lists each with the statement to run.

The lock leaves the table's owner and the identity of the run alone: revoking from the run's own identity would lock it out of the table it has to repair. When the owner is unreadable the message says so. When the contract restricts the owner or the run's identity, the message names that as an open path, with the `ALTER TABLE … OWNER TO` statement to run, since an owner reads its table whatever is revoked ([forge-cli #801](https://github.com/Agenticstiger/forge-cli/pull/801), since 0.27.0).

The message says exactly what was done, and the run exits non-zero (`databricks-enforcement-failed`). Fix the cause and run `fluid apply` again: it binds first, replacing a deny-all filter, and grants again afterwards.

#### A job that writes a table not yet protected

A dbt job that writes a restricted table must not fill it before it is bound. When the table is missing, a binding is missing or differs, a bound function is not the expected one, or the live state cannot be read, the job is created with `pause_status: PAUSED` on its schedule or continuous block, and the apply says so:

```text
job 'fluid sales.orders_dbx transform' is created paused (pause_status PAUSED): it writes main.sales.orders, whose masks and row filter are not bound yet, and a run before that would fill an unprotected table. The next fluid apply, once they are bound, starts its schedule; an explicit run-now works meanwhile.
```

The next `fluid apply`, once the bindings match, unpauses it in place, with no drift from unpausing it by hand. A manual job has no trigger to pause. `fluid validate` and the pure compile never read the workspace.

*(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* Under `--mode amend-and-build`, the run the apply starts (see [Running the job from `fluid apply`](#running-the-job-from-fluid-apply)) comes after the bindings, so it fills a protected table. It leaves the job paused: the next `fluid apply` unpauses the schedule, as above.

#### What masks and filters refuse

Refused rather than dropped, since a table applied without them would be readable without what the contract promises:

| Refusal | Why |
| --- | --- |
| `databricks-column-allow-unmapped`: `access: allow` | An allow list would hide the column from every reader it does not name, the owner and the pipelines included, and Unity Catalog has no column grant to express it. Use `deny` for the principals who must not read it, or `mask`. |
| `databricks-mask-type`: `last_four` or `first_four` on a non-string column | Those rules mask text. Mask a string column, or use `nullify`. |
| `databricks-principal-kind`: a principal with no prefix, or a `domain:` one | There is no Unity Catalog identity to test for. Write `group:<name>`, `user:<email>` or `serviceAccount:<name>` and map it in `binding.principals`. |
| `databricks-row-filter-invalid` | A predicate outside the allowlist above. |
| `databricks-enforcement-outside-module` | `fluid generate iac` (above). |
| `databricks-governance-unmapped`: `policy.privacy.rowLevelPolicy`, `binding.governance` | Not mapped. ABAC policies are not; enforce access with grants and with `columnRestrictions` and `rowFilters`. |
| `databricks-governance-unmapped`: `policy.privacy.masking` on an expose that a DuckDB acquisition does not alone write | Landing-time masking is applied only by the acquisition runner, so an expose written by a dbt build or by no build would hold the unmasked values. Write it with a DuckDB acquisition build (see [Landing a DuckDB acquisition](#landing-a-duckdb-acquisition)), or remove the masking and use `columnRestrictions`. |

`fluid verify` reads the bindings back into a `row_filter_masks` dimension (see [`fluid verify`](#fluid-verify)).

::: warning Not proven live
Proven against the in-process stand-in with a real `tofu` apply, with the function bodies evaluated in DuckDB. Not run against a live workspace: that `CREATE FUNCTION IF NOT EXISTS`, `SET ROW FILTER` (with `ON ()` as well) and `SET MASK` behave as the stand-in models them; that `SET` replaces a binding already on the table (if it does not, a changed predicate or the interim filter fails closed with the old binding in place); that a function's `routine_definition` is its body as written; that `current_user()` is a service principal's application id; and what a warehouse of each type enforces.
:::

### Retention

*(since 0.27.0, [forge-cli #801](https://github.com/Agenticstiger/forge-cli/pull/801))*

Nothing on Databricks deletes rows by age. What can make a retention promise true is the table's shape: a table rebuilt in full on every run holds no row older than the last run, except in its Delta history, the old data files Delta keeps for time travel. `VACUUM` removes those once they are older than the table's retention, and predictive optimization runs `VACUUM` on Unity Catalog managed tables. So `lifecycle.expire: true` is accepted when:

- **Every build that writes the expose rewrites the whole table.** That is a dbt build whose model for the table resolves to `materialized: table` and whose selection includes the model, or a DuckDB acquisition with `properties.source.mode: full_refresh`. forge-cli reads the dbt project to resolve the materialization as dbt does: the model's `config()` call beats its `config:` in a properties YAML, which beats `dbt_project.yml` by the most specific path, and the default is `view`. A value forge-cli cannot read statically (`var()`, a conditional `config()`) is refused, not guessed.
- **`lifecycle.retention` covers the Delta history.** It must be at least the larger of `delta.logRetentionDuration` (30 days by default) and `delta.deletedFileRetentionDuration` (7 days by default), so at least `P30D` unless the dbt model declares shorter values in its `tblproperties`. A year counts as 365 days and a month as 28, so a retention is never read as longer than it is.

forge-cli does not set those table properties, since dbt owns a dbt-written table's definition, and it does not check that the build runs often enough to stay inside the retention. That cadence is yours to keep.

| Refusal | Why |
| --- | --- |
| `databricks-retention-period` | No `lifecycle.retention`, or one that is not an ISO 8601 duration. |
| `databricks-retention-unmapped` | No build writes the expose, a build is neither dbt nor a DuckDB acquisition, or an acquisition sets no `properties.source.mode`: nothing says the table is rebuilt in full. |
| `databricks-retention-incremental` | A dbt model materialized `incremental` or `snapshot`, or an acquisition whose source mode is not `full_refresh`: earlier rows stay, and a Delta history limit cannot expire them. |
| `databricks-retention-not-table` | A dbt model materialized as anything but `table` (dbt's default is `view`). |
| `databricks-retention-dbt-unresolved` | The dbt project is a Git URL, cannot be found, or the model's materialization or `tblproperties` cannot be read. Point `repository` at a local project. |
| `databricks-retention-not-selected` | The build's `properties.model` or `properties.select` does not include the model, or selects it only through graph operators, tags, configs or state that forge-cli cannot evaluate. Select it by name. |
| `databricks-retention-too-short` | `lifecycle.retention` is shorter than the history. The message names the whole day count that covers it. |

`fluid verify` is the gate on the live table, in a `retention` dimension (see [`fluid verify`](#fluid-verify)).

## Data quality monitoring

*(since 0.30.0, [forge-cli #864](https://github.com/Agenticstiger/forge-cli/pull/864))*

An expose that states a freshness or completeness SLO turns on Databricks data quality monitoring (formerly anomaly detection) for the schema the product owns. Databricks then scans the schema's tables on serverless compute, shows each table's result as its Quality indicator in Catalog Explorer, and writes every scan to `system.data_quality_monitoring.table_results` ([Databricks' docs](https://docs.databricks.com/aws/en/data-quality-monitoring/anomaly-detection/)). There is no new contract field: the SLO fields turn it on, and one field turns it off.

### What turns it on

Any one of these on a Databricks expose:

| Field | Turns it on when |
| --- | --- |
| `qos.freshnessSLO` | It is set. |
| `qos.completenessTarget` | It is set, `0` included. |
| `observability.defaultSLIs.freshness` or `observability.defaultSLIs.completeness` | The block is there, and neither it nor `defaultSLIs` says `enabled: false`. A `latency` block does not count. |
| `contract.dq.rules[]` | An entry's `type` is `freshness`, `completeness` or `anomaly_detection`. |

`contract.dq.monitoring.enabled: false` turns it off for that expose, whatever SLOs it states. `enabled: true` on its own turns nothing on.

```yaml
exposes:
  - exposeId: orders
    # binding and contract.schema as in the minimal contract
    qos:
      freshnessSLO: PT6H
      completenessTarget: 0.98
  - exposeId: refunds
    # bound to main.sales.refunds, in the same schema, and states no SLO
```

To keep an expose unwatched, whatever it states:

```yaml
    contract:
      # schema as above
      dq:
        monitoring:
          enabled: false
```

**The SLO values are not thresholds.** Databricks learns each table's bounds from the table's own history. Freshness flags a commit that comes unusually late for that table, and completeness flags fewer rows in the last 24 hours than its history predicts. The monitor takes no threshold: in the pinned provider (`databricks/databricks` 1.140.0), its anomaly detection settings hold only the list of tables it excludes. So `PT6H` and `0.98` choose which tables are watched, and are not the bounds Databricks checks. The apply says so (below). On a watched expose, a `contract.dq.monitoring.window` other than one day (`P1D`, or `PT24H`) is not applied either, and `fluid validate` warns about it. With `window: PT1H` on `orders`:

```text
✅ Valid FLUID contract (schema v0.7.5)
⚠️  1 warning(s)
Validation completed in 0.171s

Validation Warnings:
====================
 1. exposes[0] (orders): contract.dq.monitoring.window PT1H is not applied. Databricks data quality monitoring counts a table's rows over the last 24 hours and judges its freshness against the table's own commit history. Set it to P1D, or remove it.
```

### What `fluid apply` creates

One `databricks_data_quality_monitor` on each schema the product owns, when at least one of the product's tables in it asks:

- **It is on the schema** (`object_type = "schema"`), which it names by the schema's `schema_id`. The product's tables in the schema that do not ask (no SLO, or `enabled: false`) are excluded by name. A table in the schema that the contract does not declare is not excluded, so it is scanned too.
- **It comes after the schema's tables.** Turning it on starts a scan, and Databricks documents that a table the first scan skips can wait up to two weeks for its indicator.
- **No table that asks, no monitor.** A contract that states no such SLO gets the module it always did.

For the two exposes above, the module `fluid generate iac` writes holds this resource:

```json
"databricks_data_quality_monitor": {
  "sales_orders_dbx_main_sales": {
    "anomaly_detection_config": {
      "excluded_table_full_names": [
        "main.sales.refunds"
      ]
    },
    "depends_on": [
      "databricks_sql_table.sales_orders_dbx_main_sales_orders",
      "databricks_sql_table.sales_orders_dbx_main_sales_refunds"
    ],
    "object_id": "${databricks_schema.sales_orders_dbx_main_sales.schema_id}",
    "object_type": "schema"
  }
}
```

The apply engine prints a note after the `tofu plan` summary, on a dry run too:

```text
  note: data quality monitoring is on for schema main.sales (watched: main.sales.orders; excluded: main.sales.refunds). Databricks learns each table's freshness and completeness bounds from its history, not from the contract's SLO values; it scans on serverless compute billed as DATA_QUALITY_MONITORING and shows the result as the table's Quality indicator in Catalog Explorer. system.data_quality_monitoring.table_results holds every scan (account admins only, unless they grant SELECT). contract.dq.monitoring.enabled: false turns it off for an expose.
```

The text is the plugin's `plan_notices` output for the example contract, captured offline; the engine adds the `note: ` prefix and the indent.

### Where the results show

- **Catalog Explorer.** The table's Overview shows its Quality indicator, which Databricks' docs call the health indicator. A newly watched table shows `Training` until Databricks has learned enough of its history, then `Healthy` or `Unhealthy`. An excluded table shows `Excluded`, with the reason `User Configured`. The docs also list `Error` and `Not enabled`. Seeing the indicator takes `SELECT` on the table or `BROWSE` on its catalog.
- **`system.data_quality_monitoring.table_results`.** One row per table and scan. By default only account admins can read it, and they can grant others access.

On a live Free Edition workspace on 2026-11-12, a monitor's first scan took about 8 minutes. After the apply, `table_results` held the watched table as `Training`, with freshness and completeness `Unknown` (`RECENTLY_CREATED`), and no row for the excluded one. A result past `Training` was not reached in that run.

forge-cli turns on no alerts: the pinned provider's anomaly detection settings have none (the resource's `notification_settings` belong to data profiling, a separate feature forge-cli does not use). `fluid verify` does not check the monitor.

### What it costs

The scans run on serverless compute, billed as `DATA_QUALITY_MONITORING`, as often as each table is updated, starting with a first scan when monitoring is turned on. Databricks Free Edition runs it, and the scans use the workspace's serverless compute, so expect them to count toward its daily compute quota. A Free Edition workspace over the quota stops all compute for the rest of the day, so on Free Edition, opt out the products you do not need watched. What the scans cost was not measured: `system.billing.usage` showed no `DATA_QUALITY_MONITORING` row within the live session, and its rows can lag the scans by hours.

### Adopting, removing and refusing

- **An existing monitor is adopted, not created over.** A monitor already on the schema, turned on in Catalog Explorer or through the API, would make a second create fail (`RESOURCE_ALREADY_EXISTS`). So `fluid apply` imports it by `schema,<schema_id>`, once the schema itself is in state, and prints `brownfield:  adopted N pre-existing resource(s) into state`. From then on the contract decides what it excludes: the same apply updates the list in place when it differs. The module `fluid generate iac` writes holds no import for it, since that id is known only from the schema's state.
- **Removing it is not gated.** When no table in the schema asks any more (an opt-out, dropped SLOs, a removed expose), the apply deletes the monitor. Its hidden scan job and what it has learned go with it, never table data, so it needs no `--allow-data-loss`. The apply prints it after the plan summary, with any job or file it removes. (When the plan's output does not name every removal, the gate fails closed: every removal counts, and the line is not printed.) Captured against the in-process stand-in, after `enabled: false` on the only watched expose:

  ```text
    tofu plan: +0 ~0 -1
    1 job(s), workspace file(s), folder(s) or data quality monitor(s) removed (no table data lost; not gated; a job's run history and what a monitor has learned go with them): databricks_data_quality_monitor.dbx_fake_orders_main_sales
  ```

  When the schema goes as well, the monitor is deleted first.
- **A refused monitor fails the apply, after the tables.** Databricks documents that monitoring needs serverless compute in the workspace and `MANAGE` on the schema or its catalog (the schema's owner has it). When Databricks refuses the create, the tables are already in place, since they come first: fix the cause or opt out, and run `fluid apply` again. The run fails with `opentofu_apply_failed`, and the suggestions say what monitoring needs and how to turn it off. Captured against the stand-in, which refused the create with `feature not enabled`:

  ```text
  ❌ opentofu_apply_failed  [ERR_OPENTOFU_APPLY_FAILED]
    error: failed to create data_quality_monitor (databricks_data_quality_monitor.dbx_fake_orders_main_sales)
    resource: databricks_data_quality_monitor.dbx_fake_orders_main_sales
    detail: feature not enabled

  💡 Suggestions:
    • OpenTofu records state as it goes, so resources created before the failure are normally tracked
    • Fix the cause named above, then re-run 'fluid apply' to continue
    • Re-run with --debug to see the raw tofu output
    • Databricks refused the data quality monitor on this schema; the schema's tables are in place (they come first). Monitoring needs a Unity Catalog workspace with serverless compute, and MANAGE on the schema for this identity (its owner has it).
    • Or turn it off for the expose: set contract.dq.monitoring.enabled: false, then re-run fluid apply.
    • To see what exists, run 'tofu state list' in .fluid/iac/databricks/dbx_fake_orders
  ```

::: warning Proven live on one run
Proven against the in-process stand-in with a real `tofu` and provider 1.140.0, and on a live Free Edition workspace on 2026-11-12 (`HONESTLY_TESTED.md`, the 2026-11-12 data quality monitoring row), in a scratch catalog dropped afterwards. Live, a two-table product applied with its monitor and a second plan was empty, and Catalog Explorer showed `Training` on the watched table and `Excluded` on the other. A monitor made through the REST API was adopted. When the excluded table started to ask too, the monitor was updated in place and its exclusion list emptied. Opting out deleted the monitor without the gate. Not tried live: a result past `Training`, the cost, a workspace or identity Databricks refuses (proven against the stand-in only), and alerts.
:::

## Metric views

*([forge-cli #865](https://github.com/Agenticstiger/forge-cli/pull/865), since 0.30.0)*

An expose with a `semantics` block gets a Unity Catalog [metric view](https://docs.databricks.com/aws/en/metric-views/) beside its table, named `<catalog>.<schema>.<table>_semantic_model`. Genie, AI/BI dashboards and SQL then read the contract's measures and metrics as Databricks' own, defined once:

```sql
SELECT region, MEASURE(revenue), MEASURE(revenue_per_order)
FROM main.sales.orders_semantic_model
GROUP BY ALL
```

The view takes its table's name, not `semantics.name`, and stays in the table's schema, which the product owns.

*(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* A table a [Lakeflow pipeline](#lakeflow-pipelines) publishes gets no metric view yet, and `fluid validate` warns when its expose has `semantics` (see [Next to the pipeline's table](#next-to-the-pipeline-s-table)).

The [minimal contract](#a-minimal-contract), with a `region` column and a semantics block:

```yaml
exposes:
  - exposeId: orders
    # binding and policy as above
    contract:
      schema:
        # order_id, amount and ordered_at as above, then:
        - name: region
          type: string
          businessName: Sales region
          labels:
            synonyms: territory; market
    semantics:
      name: orders
      description: Orders, as the shop counts them.
      entities:
        - name: order
          type: primary
          expr: order_id
      dimensions:
        - name: region
          type: categorical
        - name: order_day
          type: time
          expr: ordered_at
          typeParams:
            timeGranularity: day
      measures:
        - name: revenue
          agg: sum
          expr: amount
        - name: order_count
          agg: count_distinct
          expr: order_id
      metrics:
        - name: emea_revenue
          type: simple
          measure: revenue
          filter: "region = 'EMEA'"
        - name: revenue_per_order
          type: ratio
          numerator: revenue
          denominator: order_count
      labels:
        ai-synonyms: sales; bookings
```

`fluid apply` creates the view with this definition, which is what forge-cli writes for the block above:

```yaml
version: 1.1
comment: |-
  Orders, as the shop counts them.

  Synonyms: sales; bookings.
source: main.sales.orders
dimensions:
- name: order_id
  expr: source.order_id
- name: region
  expr: source.region
  display_name: Sales region
  synonyms:
  - territory
  - market
- name: order_day
  expr: DATE_TRUNC('DAY', source.ordered_at)
measures:
- name: revenue
  expr: SUM(source.amount)
- name: order_count
  expr: COUNT(DISTINCT source.order_id)
- name: emea_revenue
  expr: SUM(source.amount) FILTER (WHERE source.region = 'EMEA')
- name: revenue_per_order
  expr: MEASURE(revenue) / NULLIF(MEASURE(order_count), 0)
```

### What maps to what

| In `semantics` | In the metric view |
| --- | --- |
| `entities[]` | A dimension. It takes its key column's name when the key is a column (`order_id` above), and the entity's own name when the key is an expression. An entity whose key is a single name that is no column of the table is left out, with a `fluid validate` warning: an entity is a join key, and a metric view holds no join. |
| `dimensions[]`, categorical | A dimension. |
| `dimensions[]`, time | A dimension at its `typeParams.timeGranularity`. A `DATE` at `day` stays as it is, a coarser grain on a `DATE` becomes `TRUNC(<column>, '<GRAIN>')`, and anything else becomes `DATE_TRUNC('<GRAIN>', <column>)`. |
| `measures[]` | A measure: `SUM`, `AVG`, `COUNT`, `MIN`, `MAX` or `MEDIAN` by its `agg`, `count_distinct` as `COUNT(DISTINCT ...)`, and `percentile` as `PERCENTILE_CONT(<p>) WITHIN GROUP (ORDER BY ...)`, or `PERCENTILE_DISC` with `aggParams.useDiscretePercentile`. `<p>` is `aggParams.percentile`, 0.5 by default. |
| `measures[].nonAdditiveDimension` | A window measure, ordered by that time dimension with `range: current`: `semiadditive: last` for `windowChoice: max`, and `first` for `min`, the default. |
| `metrics[]`, simple | Its measure's aggregate, with the metric's `filter` as `FILTER (WHERE ...)`. Over a non-additive measure, it keeps the measure's window. One with its measure's name and no filter is that measure. |
| `metrics[]`, ratio | `MEASURE(<numerator>) / NULLIF(MEASURE(<denominator>), 0)`, so a zero denominator reads `NULL`. Without `numerator` and `denominator`, the first two `inputMetrics` are used. |
| `description` | The view's comment is `semantics.description`, else the expose's. A dimension's comment is its own description, else its column's. A measure's or a metric's comment is its own description. |
| A column's `businessName` and `labels.synonyms` | The `display_name` and `synonyms` of the dimension over that column. Synonyms are `;`-separated, at most 10. |
| `labels.ai-synonyms`, `labels.ai-instructions` | Added to the view's comment, as `Synonyms: ...` and `Instructions: ...`. |

Every column an expression names, bare or as `<table>.<column>`, is written `source.<column>`. A metric view reads a bare name as one of its own fields or measures before a column (measured on Databricks SQL 2026.45), so a dimension named like a column would otherwise change the measures that read it. A name that is no column stays as written. An entity and a dimension with the same name and the same expression are one field.

Not carried: `aggTimeDimension` and `defaultAggTimeDimension` (MetricFlow's `metric_time`, which a metric view has no counterpart for), `createMetric`, a metric's `owner`, the model's `tags`, and `labels.ai-example-questions`, which the product's Genie space reads as its sample questions.

### Who can read it

- **Exactly the table's readers.** `SELECT` on the view goes to each principal the contract lets read the table. `SELECT` and `ALL PRIVILEGES` are revoked from anyone else, except the view's owner and the deploying identity.
- **Revokes come first.** They run before `tofu apply`, and first again after it, so no failure leaves a removed reader able to read.
- **The table's row filter still applies.** A query through the view was filtered by it, measured on Free Edition with the deploying user's token, not as a reader. Masks through a view were not measured.
- **A view reads its table with its owner's rights.** So when a restricted table's masks or row filter cannot be bound after `tofu apply`, `SELECT` and `ALL PRIVILEGES` on the views over it are revoked before the run fails, from everyone but the view's owner and the deploying identity, its readers included.

### Why `fluid apply` creates it, outside OpenTofu

The `databricks/databricks` provider has no metric view resource ([terraform-provider-databricks #4827](https://github.com/databricks/terraform-provider-databricks/issues/4827)). So the view's statements run on the SQL warehouse `DATABRICKS_WAREHOUSE_ID` names, in the same two hooks around `tofu apply` as the [masks and row filters](#column-masks-and-row-filters):

| Hook | Does |
| --- | --- |
| Before `tofu apply` | Stops the run when an object this module did not create holds a view's name: a table, a view without this product's `fluid.product_id` property, or a view another identity owns. Revokes the readers the contract no longer names. Drops this product's views that the contract no longer declares, in the schemas its tables are in: a view named `*_semantic_model` that carries this product's `fluid.product_id` and that the deploying identity owns. Any other is left, with a `left metric view <name>: ...` line. In a schema the saved plan destroys, it drops this product's views over the tables the plan destroys or that no longer exist (see [A schema the contract stops using](#a-schema-the-contract-stops-using)). |
| After `tofu apply` | `CREATE VIEW ... WITH METRICS LANGUAGE YAML` when the view is missing, or `ALTER VIEW ... AS` when its definition changed. Then the grants. |

- **Only what differs runs.** The view carries `fluid.product_id`, `fluid.expose_id` and a digest of its definition as table properties. When the digest and the stored definition match, nothing runs, so a second apply executes no statement.
- **Never `CREATE OR REPLACE`.** Measured live, a replace drops the view's grants and makes the replacer its owner. `ALTER VIEW ... AS` keeps both.
- **Another environment keeps its own view.** A view is dropped only in the schemas this contract's tables are in, and in those the saved plan destroys, which this environment's own OpenTofu state holds. A staging copy of the product, with the same id in another schema of the catalog, keeps its view: its schema is in neither. The run prints `dropped metric view <name>` for a view dropped in a schema the contract still names, and `done: drop metric view <name>: <why>` in one the plan destroys.
- **`--mode dry-run` prints what would run, and runs none of it.** The `CREATE VIEW`, or the `ALTER VIEW` and the digest it records, is printed under an `after apply:` line. Each revoke and each drop is a `before apply:` line, and each grant an `after apply:` line, naming the principal or the view without the SQL. It says `unchanged` for a definition that would not change and `REFUSED before the apply: <why>` for a name another object holds. Without `databricks-sdk`, or when the client cannot be created, it cannot read the live state: it marks each view `(live state not read)` and lists no drops.
- **`fluid diff` reports it.** The report it writes (`--out`) lists the view as a `databricks_metric_view` action. Its terminal output and `fluid plan` do not show the view.
- **`fluid generate iac` writes no view.** The module holds none, so a module applied by hand creates no metric view.
- **The `[databricks]` extra is needed at apply**, as for masks: `pip install 'data-product-forge[databricks]'`. Without it, a contract that declares a view is refused before `tofu apply`.
- **The product's Genie space lists it.** *([forge-cli #863](https://github.com/Agenticstiger/forge-cli/pull/863), since 0.30.0)* With `extensions.databricksGenie`, the space is converged after the metric views, so the first apply already shows the view beside its table.

### If a statement fails

A statement that fails after `tofu apply` fails the run with `databricks-metric-view-failed` (event `opentofu_access_enforcement_failed`), naming the view and what failed. The tables and grants the apply made stay, and the next apply converges the view. The deploying identity needs `CREATE TABLE` and `USE SCHEMA` on the schema, `SELECT` on the table and `CAN USE` on the warehouse.

### What metric views refuse

`fluid validate` refuses, for a Databricks binding, what metric view YAML cannot express, rather than approximate it. Among others:

- a derived metric (its `expr` names other metrics, which a metric view reads only through `MEASURE()`), a ratio with a `filter`, and a metric type other than `simple` or `ratio`;
- a `nonAdditiveDimension` that is not a time dimension of the model, and an `hour` or `minute` grain on a `DATE`;
- two fields or measures with one name (they share one namespace, case aside), and a dimension, measure or metric named `source`;
- a dimension or measure whose `expr` is a single name that is no column of the table, and a bare name that is no column but names one of the model's dimensions or measures;
- a dimension, measure or metric name that is not a plain identifier, a simple metric over a measure the model does not declare, a ratio over an unknown or circular input, and an invalid `aggParams.percentile`;
- an expression outside the SQL allowlist (a statement keyword, a comment, `;` or `$`), an unclosed quote, and unbalanced parentheses;
- a call that would lend the view owner's rights to its readers: `secret()`, `http_request()`, `ai_*()`, `read_*()`, reflection, identity functions such as `current_user()` and `is_member()`, `IDENTIFIER()`, and a function named with quotes or a qualifier;
- more than 10 distinct synonyms on a field (case aside), and a synonym or display name over 255 characters;
- `$$` or `${` in a description, a synonym, a display name or an `ai-*` label, and `$$`, `${` or a control character in the contract id or an `exposeId`;
- a table named like another table's view (`<table>_semantic_model`).

A derived metric, for example:

```text
 1. exposes[0] (orders) semantics.metrics[2] (revenue_growth) is a derived metric: its expr names other metrics, which a metric view reads only through MEASURE(), and forge-cli does not rewrite the expression, so it is refused rather than approximated. Express it as a ratio of two metrics, or remove it for Databricks.
```

A `semantics` block with nothing to compile, such as labels alone, makes no view, and `fluid validate` warns that it does not.

A misspelt column inside a longer expression or a filter (`amountt * 2`, say) is not caught here. Databricks refuses it when it creates the view, after `tofu apply`, and the run fails (see [If a statement fails](#if-a-statement-fails)).

## dbt builds as jobs

A build with an `engine` of `dbt` or `dbt-databricks` and `execution.runtime.platform: databricks` runs in the workspace, not on the machine that applies. `fluid apply` provisions one serverless job per build with a dbt task. Databricks runs it on the SQL warehouse `DATABRICKS_WAREHOUSE_ID` names, in the catalog and schema of the first Databricks expose the build writes (`builds[].outputs`). The job is named `fluid <product> <build>`.

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

Never uploaded: `profiles.yml`, `target/`, a hidden file or directory, a symbolic link. A path key that names the project root, a hidden directory or a place outside the project is refused. The upload takes at most 1000 files and 20 MiB, and a file may be 2 MiB. The apply uploads the project as it is when the apply runs, as a local dbt run reads it when it runs. A plan's `planDigest` and `bundleDigest` bind the contract, not the project's files. *(since 0.30.0, [forge-cli #871](https://github.com/Agenticstiger/forge-cli/pull/871))* When an expose the build writes states `dq.rules`, the upload also holds a generated test file for each test those rules make (one or several per rule), and they count toward the 1000 files above (the byte limits apply to your own files). Your own files go up unchanged (see [Contract rules as dbt tests](#contract-rules-as-dbt-tests)).

**A Git URL** is cloned by Databricks, and nothing is uploaded. It must be `https://` with no user or password in it, on `github.com`, `gitlab.com`, `bitbucket.org` or Azure DevOps (`dev.azure.com`, or a `*.visualstudio.com` organisation). Name exactly one ref, once: `?branch=`, `?tag=` or `?commit=`. Add `&path=` for a project below the repository root. A private repository needs a Git credential in Databricks. *(since 0.30.0, [forge-cli #871](https://github.com/Agenticstiger/forge-cli/pull/871))* A build that writes an expose with `dq.rules` cannot use a Git URL: forge-cli adds the rules' tests to the project it uploads, and no file can be added to a checkout (see [What the rules refuse](#what-the-rules-refuse)).

```yaml
    repository: https://github.com/acme/orders-dbt?tag=v1.2.0&path=dbt
```

### Triggers, retries, notifications, timeout, run-as

| Contract | Job |
| --- | --- |
| `trigger.type: schedule` (or no type) with `cron` | A Quartz `schedule`, days of the week by name. `trigger.timezone` is an IANA name; the default is `UTC`. |
| `trigger.type: continuous` | Databricks' `continuous` trigger. |
| `trigger.type: manual`, or no trigger | No trigger. Start a run from the job's page or with `databricks jobs run-now`. *(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* Or apply with `--mode amend-and-build`, which starts one and waits for it (see [Running the job from `fluid apply`](#running-the-job-from-fluid-apply)). |
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
- a Git URL that breaks the rules above, and a Git host outside those;
- *(since 0.30.0, [forge-cli #871](https://github.com/Agenticstiger/forge-cli/pull/871))* a contract data-quality rule that no dbt test can run as written, and a Git URL on a build that writes an expose with rules (see [What the rules refuse](#what-the-rules-refuse));
- a dbt build with another adapter (`engine: dbt-snowflake`, for example) and `runtime.platform: databricks`: a Databricks job runs dbt with the dbt-databricks adapter only.

### Applying and removing

`fluid apply` never runs such a build's dbt on the applying machine: the build runs as its job. A dbt build without `runtime.platform: databricks` still runs locally with the dbt-databricks profile. forge-cli's own schedules (`fluid generate schedule`, the Airflow DAG `fluid apply` writes) give a Databricks job build no task: Databricks starts its runs. In 0.29.0, `--mode amend-and-build` provisions the job, then prints its name and how to start a run now.

*(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* `--mode amend-and-build` and `--mode replace-and-build` start a run of the job and wait for it, as the next section says.

Removing a job, an uploaded file or a folder from the contract needs no `--allow-data-loss`, since no table data is lost. The job's run history goes with the job, and the apply says so.

### Running the job from `fluid apply`

*(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))*

Under `--mode amend-and-build` and `--mode replace-and-build`, `fluid apply` starts a run of each such build's job and waits for it to end. The run starts once `tofu apply` has succeeded and the [masks and row filters](#column-masks-and-row-filters) are bound, so it writes tables that are already protected. A run that fails fails the apply.

| `--mode` | The job |
| --- | --- |
| `amend-and-build` | Provisioned, then one run starts now, and the apply waits for it. |
| `replace-and-build` | The same, and that run adds `--full-refresh` to the job's `dbt build`. |
| `amend`, `create-only`, `replace` | Provisioned only. It runs on its trigger. |

`--build-id <id>` starts only that build's job. A continuous job (`trigger.type: continuous`) is never started: Databricks keeps it running, so a run of it never ends. The apply says so and goes on.

- **The job is the one this apply provisioned.** The apply finds it in its own OpenTofu state by the job's `fluid_product` and `fluid_build` tags, never by its name: two environments of one contract in one workspace each own a job of that name. When the state holds no such job, or more than one, no run starts and the build fails.
- **The run changes nothing on the job.** The apply starts the run and, at the time limit or on an interrupt (below), cancels it. It writes nothing else. The job's settings, schedule and pause state stay as they are, so a scheduled job keeps its schedule and a job [created paused](#a-job-that-writes-a-table-not-yet-protected) stays paused. The `--full-refresh` of `replace-and-build` goes with that run only, and the job's own commands keep none.
- **A busy job queues the run.** The run waits in the job's queue, instead of being skipped, when the job is busy (it runs one run at a time, and a scheduled run may be going) or the workspace is at its limit. The start request carries an idempotency token and is retried with the same token, so a retry never starts a second run.

What a run prints, captured live on Databricks Free Edition on 2026-11-12 for a one-model dbt product, with the workspace host and id replaced:

```text
🚀 Build 'summarize' - started run 864120962919474 of Databricks job 'fluid iactest.build.sites_summary summarize' (711974842827325)
   run page: https://<workspace>/?o=<workspace-id>#job/711974842827325/run/864120962919474
   0:00 RUNNING
   0:57 TERMINATED SUCCESS
   task 'dbt': Done. PASS=1 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=1
✅ Build 'summarize' - Databricks run 864120962919474 succeeded in 57s
```

- The run's page comes first. Then each state the run enters gets a line, with the time since the run started, and a `still <state>` line follows each minute while nothing changes.
- A queued run says why. Databricks' own reason is used when it gives one. It usually gives none (seen live), so the line names one of two causes, or none when the job's runs cannot be listed:

  ```text
     0:00 QUEUED - behind run <run id> of this job, which runs one at a time
     0:00 QUEUED - waiting for the workspace's limit on runs or tasks at once (Databricks Free Edition runs at most 5 job tasks at a time)
  ```

- On success, dbt's own `Done. PASS=...` line is printed for each task that has one.
- Every credential value in the environment is masked in what is printed, and terminal escape sequences are removed.

**When the run fails.** A run that ends in anything but `SUCCESS` fails its build, and the apply exits `1`. The apply prints the run's end state and message. For each task that did not succeed, it prints the task's error and up to the last 30 lines of its output, then the run page again. A live run of a model that names a column its source does not have (abridged, with the wrapped error line joined):

```text
   0:00 RUNNING
   1:08 still RUNNING
   1:18 TERMINATED RUN_EXECUTION_ERROR
❌ Build 'summarize' - Databricks run 973093456770242 ended RUN_EXECUTION_ERROR after 1m18s: Task dbt failed with message: Workload failed, see run output for details.
   task 'dbt': Command 'dbt build --select +sites_summary+' … returned non-zero exit status 1.
   dbt output:
     + dbt deps
     …
     19:59:14    Database Error in model sites_summary (models/sites_summary.sql)
       [UNRESOLVED_COLUMN.WITH_SUGGESTION] A column, variable, or function parameter with name `height_meters` cannot be resolved. Did you mean one of the following? [`height_m`, `site_id`, `kind`]. SQLSTATE: 42703; line 19 pos 47
     …
     19:59:14  Done. PASS=0 WARN=0 ERROR=1 SKIP=0 NO-OP=0 REUSED=0 TOTAL=1
   run page: https://<workspace>/?o=<workspace-id>#job/711974842827325/run/973093456770242
```

**How long it waits.** `FLUID_DATABRICKS_RUN_TIMEOUT_SECONDS` caps the wait for each run, in whole seconds. Unset, the cap is an hour, or the job's own limit plus 15 minutes when that is longer, so a contract's `runtime.timeout` is never cut short. The job's own limit is its timeout when it has one (a job forge-cli emits has none), else each task's timeout times its attempts, plus the intervals between them. The build in the example under [dbt builds as jobs](#dbt-builds-as-jobs) (`timeout: 1h`, `maxAttempts: 3`, `initialDelay: 5m`) is waited for up to 3 h 25 min: three attempts of an hour, two 5-minute intervals and the 15 minutes. A task with no timeout leaves the cap at an hour. A value that is not a whole number of seconds above 0, in at most nine digits, is not used: the apply says so, and names the cap it waits for instead.

**Stopping it.** At the cap, the run is cancelled and the build fails, and the message names the variable to raise. Ctrl-C while the run is waited on cancels it too, and so do SIGTERM and SIGHUP (a cancelled CI job, a closed terminal); the apply then stops as Ctrl-C stops it. A signal that is ignored stays ignored, so under `nohup` the apply and the run outlive the terminal. A cancel that fails is said: `could not cancel run <run id>: <why>`.

**A run it cannot read.** A failed read of the run is tried again, and the first failure is said. After five failed reads in a row, the apply stops waiting and the build fails. The run is left as it is, since it may still be going, and its page is printed when an earlier read returned it. Failed reads alone never cancel a run.

**It needs `databricks-sdk`.** The run is started through it. Without the `[databricks]` extra, an apply that would start a run is refused before anything is applied:

```text
❌ apply_databricks_sdk_missing  [ERR_APPLY_DATABRICKS_SDK_MISSING]
  error: a dbt or lakeflow build runs on Databricks, and the build phase starts it through databricks-sdk, which is not installed; nothing was applied
  hint: pip install 'data-product-forge[databricks]', or apply with --mode amend to provision it without starting it
```

`--dry-run` is not refused. It runs `tofu plan`, applies and starts nothing, and names the run it would start:

```text
🔍 [DRY RUN] Build 'summarize' - would start a run of Databricks job 'fluid iactest.build.sites_summary summarize' and wait for it.
```

Under `replace-and-build` the line ends `with dbt build --full-refresh and wait for it.`

**Several products, in lineage order.** Each apply starts its own product's jobs only. To build an estate whose products read each other, provision every product first, in parallel, with `--mode amend`. Then run `--mode amend-and-build` one lineage level at a time, upstream first. For a product that has not changed since, the second apply plans no change (live: `tofu plan: +0 ~0 -0`, about 30 seconds for some 75 resources), except to unpause a job [created paused](#a-job-that-writes-a-table-not-yet-protected). Then it starts the runs and waits for them.

### Contract rules as dbt tests

*(since 0.30.0, [forge-cli #871](https://github.com/Agenticstiger/forge-cli/pull/871))*

The rules in `exposes[].contract.dq.rules` of an expose a Databricks dbt build writes run as dbt tests in that build's job. There is no new contract field and no flag: the rules turn it on. The tests are part of the job's `dbt build`, so they run on every run of the job, whether its trigger, a person or `fluid apply` started it. `dbt build` runs each test right after the model it tests. The dbt task's output, which the job's run page shows, lists every rule's test by name as passed, warned or failed, and `fluid apply --mode amend-and-build` prints that list when the run ends (see [What `fluid apply` prints for each rule](#what-fluid-apply-prints-for-each-rule)).

A rule that no test can run as written is refused, not skipped (see [What the rules refuse](#what-the-rules-refuse)). [`fluid test`](../cli/test.md) checks the same rules on demand against the deployed table.

```yaml
exposes:
  - exposeId: orders
    # binding as in the minimal contract
    contract:
      schema:
        - name: order_id
          type: string
          required: true
        - name: status
          type: string
          validationRules:
            - type: enum
              constraint: "NEW | SHIPPED | CANCELLED"
        - name: amount
          type: decimal(18,2)
          validationRules:
            - type: range
              constraint: ">= 0"
        - name: ordered_at
          type: timestamp
      dq:
        rules:
          - id: order_id_unique
            type: uniqueness
            selector: order_id
            severity: critical
          - id: status_valid
            type: valid_values
            selector: status
            severity: error
          - id: amount_nonnegative
            type: valid_values
            selector: amount
            severity: warn
          - id: orders_fresh
            type: freshness
            selector: ordered_at
            window: PT6H
            severity: warn
```

With the build in [dbt builds as jobs](#dbt-builds-as-jobs), the job's upload gains four files:

```text
tests/fluid_dq/orders/order_id_unique.sql
tests/fluid_dq/orders/status_valid.sql
tests/fluid_dq/orders/amount_nonnegative.sql
tests/fluid_dq/orders/orders_fresh.sql
```

#### Where the tests go

A rule makes one singular dbt test, or several (see `<name>` below). Each test is a `.sql` file in the copy of the project that `fluid apply` uploads, at `<test path>/fluid_dq/<model>/<name>.sql`.

- `<test path>` is the first entry of `test-paths` in `dbt_project.yml`, or `tests` when the key is absent.
- `<model>` is the dbt model that writes the expose: the build's `properties.model` when the build writes one table, otherwise the model named after the expose's table (`binding.location.table`).
- `<name>` is the rule's `id`, lower-cased, with each run of characters other than ASCII letters, digits and `_` turned into one `_`, and any leading or trailing `_` removed. It is the test's name in dbt and in the run's output. If two rules would get the same name, the later one gets `__<expose>` added. A `selector` that lists several columns makes one test per column, named `<name>__<column>` (the column lower-cased and cleaned the same way). A `valid_values` rule whose column makes several declarations (see [What a `valid_values` rule allows](#what-a-valid-values-rule-allows)) makes one test per declaration, named `<name>__<kind>`, where `<kind>` is `accepted_values`, `regex`, `bounds` or `reference`.

A dbt test passes when its query returns no row. Two of the four files above:

```sql
-- Contract rule order_id_unique (uniqueness): written by fluid apply from the contract. Change the contract, not this file.
{{ config(severity="error", enabled=true, tags=["fluid_dq"], meta={'fluid_rule_id': "order_id_unique", 'fluid_expose_id': "orders"}) }}
{{ adapter.dispatch('test_unique', 'dbt')(ref("orders"), "`order_id`") }}
```

```sql
-- Contract rule amount_nonnegative (valid_values): written by fluid apply from the contract. Change the contract, not this file.
{{ config(severity="warn", enabled=true, tags=["fluid_dq"], meta={'fluid_rule_id': "amount_nonnegative", 'fluid_expose_id': "orders"}) }}
select `amount` as failing_value
from {{ ref("orders") }}
where `amount` is not null and not (`amount` >= 0)
```

To read the tests before an apply, run `fluid generate iac`: each file is a `databricks_workspace_file` in `main.tf.json`, with its text in `content_base64`.

- **Your files upload unchanged.** The project's own files go up byte for byte. dbt takes one properties entry per model (a second entry fails the parse), and that entry is yours, so the tests are files of their own and nothing is merged into your YAML. Nothing is written to the project on your machine either: only the uploaded copy holds the tests.
- **Only the job runs them.** A dbt build that runs on your machine, without `runtime.platform: databricks`, runs the project as it is.
- **Change the contract, not the files.** Each file starts with a comment that says so. The next apply uploads the set of tests the contract describes.
- **They count toward the upload limit.** The generated files count toward the 1000 files in [Where the dbt project comes from](#where-the-dbt-project-comes-from).
- **No dbt package is installed.** `dbt deps` installs what your `packages.yml` names and nothing more, and nothing is merged into that file. The tests for `unique`, `not_null`, `accepted_values` and `relationships` call dbt's own test SQL, as a YAML test of that name calls it. The regex, range, freshness, schema and share tests are SQL of forge-cli's own, because a serverless job's `dbt deps` may not reach hub.getdbt.com: Databricks Free Edition limits outbound traffic to trusted domains.
- **Each file carries its severity and a tag.** `config()` sets `severity`, which wins over `dbt_project.yml`, and the tag `fluid_dq`, so `dbt build --select tag:fluid_dq` selects the rules' tests alone.

#### What each rule runs

| Rule `type` | The test |
| --- | --- |
| `uniqueness` | dbt's `unique` on the selected column. A `selector` that lists several columns is refused: it could mean each column or their combination, and `fluid test` reads one column too. |
| `completeness` | dbt's `not_null` on each selected column. A `selector` of `a,b,c` makes three tests. |
| `valid_values` | The values the rule allows, read as `fluid test` reads them (below). |
| `accuracy` | Every non-null value of each selected column meets `<operator> <threshold>`, with `>=` when the rule has no `operator`. The `threshold` is the bound, not a share. |
| `freshness` | The newest value of the one selected date or timestamp column is no older than `window`, an ISO 8601 duration with a fixed length (`PT15M`, `PT2H`, `P1D`; not months or years). `operator: "<"` asks for younger than the window, and the default `<=` allows exactly its age. A table with no row fails. |
| `schema` | Every contract column, or each selected one, exists in the table dbt built, with its declared type as Databricks reports it (`bigint`, `string`, `decimal(18,2)`). Columns the contract does not declare are left alone. |
| `anomaly_detection` | No test. Databricks data quality monitoring runs it (below). |
| `drift_detection` | Refused: it is judged against the table's history. |

A `threshold` other than `1.0` with `>=` or `==` turns `uniqueness`, `completeness` and `valid_values` into share tests (see [Severity and thresholds](#severity-and-thresholds)).

#### Severity and thresholds

`critical` and `error` become dbt severity `error`. `warn` and `info` become `warn`. A failing `error` test fails the dbt task, so the run and `fluid apply` fail, and dbt skips the models below it. A failing `warn` test is reported and the run goes on. The tests run after the model, which has already replaced its table, so a failing rule does not undo the write: the table keeps what the model wrote.

A `threshold` of `1.0` with `>=` or `==`, or no `threshold`, means every row must pass. Any other `threshold` (below `1.0`, or `1.0` with another `operator`) is the share of rows that must pass, computed as `fluid test` computes it:

- the non-null share of the rows for `completeness`;
- the distinct share of the non-null values for `uniqueness`;
- the share of the non-null values that are allowed for `valid_values`.

The test fails when the measured share does not meet `<operator> <threshold>`, with `>=` when the rule has no `operator`. A table with no row to measure passes. A share is a fraction from 0 to 1: write `0.99`, not `99`. `accuracy` reads its `threshold` as a bound instead, and `freshness` and `schema` take none.

#### What a `valid_values` rule allows

A rule has no field for its allowed values, so a `valid_values` test reads them where `fluid test` does (`quality_engine.value_domain`). The values the rule lists come first: its `description` holds `status valid values: NEW, SHIPPED.`, with the values separated by commas and ending at the first full stop. Otherwise the selected column's own declarations decide. Every one of them must hold, and each is a test of its own:

- the first `enum` validationRule, written `A | B` or `A,B`: dbt's `accepted_values`;
- the first `regex` validationRule: forge-cli's regex test. The value, cast to a string, must match the pattern with Spark's `rlike`, which looks for the pattern anywhere in the value. Write `^` and `$` to require the whole value to match;
- the first `range` validationRule, written `>= 0`, `>= 0 and <= 100` or `between 0 and 100`: a bounds test;
- `labels.references: <product id>.<column>`: dbt's `relationships` against the dbt source table the project declares for that product.

A `custom` validationRule declares no allowed values. A rule that lists none, on a column that declares none, is refused. A null never fails these tests: `completeness` is the rule for nulls.

A reference is found through `consumes[]`. List the product there with the `exposeId` of its table, and declare exactly one dbt source table of that name in the project:

```yaml
consumes:
  - productId: crm.customers_v1
    exposeId: customers
```

```yaml
sources:
  - name: crm
    tables:
      - name: customers
```

With `labels.references: crm.customers_v1.id` on `customer_id`, the test checks that every non-null `customer_id` of the model exists in `id` of `source('crm', 'customers')`.

#### `anomaly_detection` and data quality monitoring

No test runs an `anomaly_detection` rule, because an anomaly is judged against the table's history. Databricks data quality monitoring learns those bounds itself (see [Data quality monitoring](#data-quality-monitoring)), and such a rule is one of the things that turn it on. So `fluid validate` accepts the rule and writes no test for it. Monitoring takes no threshold from the contract, so the rule's `threshold` is not applied.

On an expose with `contract.dq.monitoring.enabled: false`, nothing would run the rule, so it is refused. Turn the monitoring back on, check the rule with `fluid test`, or remove it. A rule that monitoring could not read either, one with a bad `severity`, say, is refused like any other rule.

A `freshness` or `completeness` rule also turns monitoring on. That is separate from its dbt test: monitoring learns its own bounds, and the test checks the limit the rule states.

#### What the rules refuse

`fluid validate`, `fluid generate iac` and `fluid apply` refuse a contract whose rules cannot all run, with the fix. `fluid plan` does not run this check: it writes a plan for such a contract, so run `fluid validate` first. `fluid apply` refuses the contract before anything is applied, with or without a saved plan. With a `drift_detection` rule added to the rules above, `fluid validate` says:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
Validation completed in 0.013s

Validation Errors:
==================
 1. builds[0] (transform) expose 'orders': rule 'orders_drift' (drift_detection) has no check of the table as it stands here: an anomaly or a drift is judged against the table's history. Check it with fluid test against the deployed table (it reads an anomaly_detection threshold as a row count), or remove it from this expose.
```

`fluid generate iac` and `fluid apply` stop with `unsupported_binding`, and the code of the refusal is the `kind`:

```text
❌ unsupported_binding  [ERR_UNSUPPORTED_BINDING]
  kind: databricks-job-dq-rule
  error: builds[0] (transform) expose 'orders': rule 'orders_drift' (drift_detection) has no check of the table as it stands here: an anomaly or a drift is judged against the table's history.
  remediation: ['Check it with fluid test against the deployed table (it reads an anomaly_detection threshold as a row count), or remove it from this expose.']
```

**A rule no test can run as written** is `databricks-job-dq-rule`. Each message names the build, the expose and the rule:

| The rule | The fix |
| --- | --- |
| is `drift_detection`, or `anomaly_detection` on an expose that turns monitoring off | Check it with `fluid test` against the deployed table, or remove it. For an anomaly rule, turn the monitoring back on instead. |
| is `valid_values`, lists no values, and its column declares no `enum`, `regex` or `range` validationRule and no `labels.references` | Declare the allowed values on the column. |
| is `valid_values` on a column whose `range` is not one or more bounds (`>=`, `>`, `<=` or `<` and a number, joined by `and`) or `between A and B`, or is one no value meets (`between 100 and 0`) | Write the range in one of those forms, lower bound first. |
| selects no column (only `schema` takes `*`), or a column that `contract.schema` does not declare | Name a column of the expose's schema, or several, comma-separated. |
| is `uniqueness` and selects several columns | Write one uniqueness rule per column. |
| is `freshness` and selects several columns, or one that is not a date or timestamp | Select the one `DATE` or `TIMESTAMP` column the age is measured on. |
| is `freshness` with a `window` that is not a fixed ISO 8601 duration (`P1M`) | Set `window` to a duration such as `PT15M`, `PT2H` or `P1D`. |
| is `freshness` or `schema` and has a `threshold` | Remove it. A freshness rule's limit is its `window`. |
| has a `threshold` that is not a number, or, unless the rule is `accuracy`, is outside 0 to 1 (`99`) | Write the share as a fraction: `0.99`. |
| is `accuracy` with no numeric `threshold` | Set `threshold` to the bound and `operator` to the comparison. |
| has an `operator` outside `>=`, `>`, `<=`, `<`, `==` and `!=` (the schema refuses it first), or is a `freshness` rule with an `operator` other than `<=` or `<` | Use one of the six; a freshness rule takes `<=` or `<`. |
| has a `severity` other than `critical`, `error`, `warn` or `info` | Set one of the four. |
| has `labels.references` that is not `<product id>.<column>`, that names its own product, or that names a product `consumes[]` lists by several exposes | Write the `<product id>.<column>` of another product, and list that product in `consumes[]` once. |
| has an `id`, or allowed values, holding a control character or an unpaired surrogate | Write it in plain text. |

**The build or the project** is refused with these:

| Refusal | Refused when | The fix |
| --- | --- | --- |
| `databricks-job-dq-git-source` | The build's `repository` is a Git URL, and an expose it writes has rules. | Point `repository` at the local dbt project. |
| `databricks-job-dq-model` | The model that writes the expose is not in the project's `model-paths`. | Name the model in `properties.model` (one output per build), or name it after the expose's `binding.location.table`. |
| `databricks-job-dq-not-selected` | The build's selection leaves the model out, so dbt would never run its tests. | Select the model: `properties.select: ['orders']`, or `properties.model`. |
| `databricks-job-dq-reference` | A `labels.references` product is not in `consumes[]`, or the project does not declare exactly one dbt source table named like the consumed expose. | List the product in `consumes[]` with the `exposeId` of its table, and declare that one table as a dbt source. |
| `databricks-job-dq-name` | The project has a singular test with the name of a rule's test. dbt names a test once per project, so the whole job would fail to parse. | Rename the rule's `id`, or the project's test. |
| `databricks-job-dq-path` | The project already holds a file at the path of a generated test. | Move it out of `<test path>/fluid_dq/`, the generated tests' folder. |
| `databricks-job-dq-test-path` | `test-paths` is an empty list, so dbt reads no test file, or its first entry holds an unpaired surrogate. | Leave `test-paths` out (dbt reads `tests/`), or name a directory in plain text. |
| `databricks-job-project-size` | The project and its generated tests are more than 1000 files. | Take files out of the project, or drop rules. The message suggests a Git source, which a build with rules cannot use. |

A selection that forge-cli cannot evaluate (by tag, config or state) is not refused. The run's report then says which tests dbt did not run.

#### What `fluid apply` prints for each rule

Under `--mode amend-and-build` and `--mode replace-and-build`, `fluid apply` waits for the run (see [Running the job from `fluid apply`](#running-the-job-from-fluid-apply)). When the run has ended, it reads the dbt task's output once and, when it can read it, prints one line for each rule's test, in the contract's order, whether the run succeeded or not. On a failed run the lines come after the task's error and before the tail of dbt's output. They come from the contract alone, so a test that dbt never ran is listed too.

```text
     ✗ orders_required_complete__status: FAIL 1 row - completeness status, severity error
     ✓ orders_customer_id_mostly_set: PASS - completeness customer_id (share >= 0.75), severity error
```

A line is a mark, the test's name, what dbt printed for it, the rule's type and column, and the dbt level it maps to, `error` or `warn`. A share rule shows its limit.

| Mark | dbt printed | Meaning |
| --- | --- | --- |
| `✓` | `PASS` | The test found no row. |
| `!` | `WARN 1 row` | A `warn` test found rows. The count is dbt's. |
| `✗` | `FAIL 3 rows`, or `ERROR` | An `error` test found rows, or a test failed to run (a SQL error, say). |
| `-` | `SKIP` | dbt did not run the test (its model failed, say). |
| `?` | `not in the task's output` | dbt printed no result line for the test. |

A summary line above them counts the outcomes, such as `contract rules as dbt tests: 6 pass, 2 warn, 2 fail, 1 not reported`. When none of the tests appears in the output, one line says so instead: `contract rules as dbt tests: none of the 11 reported in the task's output; dbt stopped before running them, or the run page has the rest`. Databricks keeps only the end of a very long output, and the lines then add `(Databricks kept only its end)`. A build run with `--mode amend`, `create-only` or `replace` starts no run, so nothing is printed, and the tests run on the job's trigger.

Captured live on Databricks Free Edition on 2026-11-12, with a bad row seeded into the table, with the workspace host and the ids replaced. Nine rules became eleven tests. The wrapped error line is joined, and dbt's output is abridged:

```text
🚀 Build 'transform' - started run <run-id> of Databricks job 'fluid fluid_iactest.dq_orders_v1 transform' (<job-id>)
   run page: https://<workspace>/?o=<workspace-id>#job/<job-id>/run/<run-id>
   0:00 RUNNING
   1:08 still RUNNING
   1:59 TERMINATED RUN_EXECUTION_ERROR
❌ Build 'transform' - Databricks run <run-id> ended RUN_EXECUTION_ERROR after 1m59s: Task dbt failed with message: Workload failed, see run output for details.
   task 'dbt': Command 'dbt build --select +orders+' else exit 1 fi returned non-zero exit status 1.
   contract rules as dbt tests: 6 pass, 2 warn, 2 fail, 1 not reported
     ✓ orders_order_id_unique: PASS - uniqueness order_id, severity error
     ✓ orders_required_complete__order_id: PASS - completeness order_id, severity error
     ✗ orders_required_complete__status: FAIL 1 row - completeness status, severity error
     ✓ orders_required_complete__loaded_at: PASS - completeness loaded_at, severity error
     ✓ orders_status_valid: PASS - valid_values status, severity error
     ! orders_country_code_valid: WARN 1 row - valid_values country_code, severity warn
     ✗ orders_amount_nonnegative: FAIL 1 row - valid_values amount, severity error
     ! orders_customer_id_ref: WARN 1 row - valid_values customer_id, severity warn
     ✓ orders_customer_id_mostly_set: PASS - completeness customer_id (share >= 0.75), severity error
     ✓ orders_freshness: PASS - freshness loaded_at, severity warn
     ? orders_schema_conformance: not in the task's output - schema, severity error
   dbt last 30 of 60 lines:
     …
     21:35:32  [ERROR]: in test orders_amount_nonnegative (tests/fluid_dq/orders/orders_amount_nonnegative.sql)
     21:35:32    Got 1 result, configured to fail if != 0
     …
     21:35:32  [WARNING]: in test orders_customer_id_ref (tests/fluid_dq/orders/orders_customer_id_ref.sql)
     21:35:32  [WARNING]: Got 1 result, configured to warn if != 0
     …
     21:35:32  Done. PASS=7 WARN=2 ERROR=2 SKIP=0 NO-OP=0 REUSED=0 TOTAL=11
   run page: https://<workspace>/?o=<workspace-id>#job/<job-id>/run/<run-id>
```

The last rule line, `?`, is the schema rule's test. This run came before a fix that made dbt select that test: dbt found eleven tests and ran ten, and `fluid apply` showed the one it never ran. The two `error` rules failed the run, so `fluid apply` exited `1`. The two `warn` rules did not fail it by themselves.

A second run, on clean data, succeeded, and `fluid apply` exited `0`. The model and all eleven tests passed. Abridged:

```text
🚀 Build 'transform' - started run <run-id> of Databricks job 'fluid fluid_iactest.dq_orders_v1 transform' (<job-id>)
   run page: https://<workspace>/?o=<workspace-id>#job/<job-id>/run/<run-id>
   0:00 RUNNING
   0:57 TERMINATED SUCCESS
   task 'dbt': Done. PASS=12 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=12
   contract rules as dbt tests: 11 pass
     ✓ orders_order_id_unique: PASS - uniqueness order_id, severity error
     ✓ orders_required_complete__order_id: PASS - completeness order_id, severity error
     …
     ✓ orders_schema_conformance: PASS - schema, severity error
✅ Build 'transform' - Databricks run <run-id> succeeded in 57s
```

::: warning Proven live on one run
Each test is rendered in a stand-in for dbt's Jinja context, and a real dbt-core with dbt-duckdb parses the upload and lists every rule's test. The tests also ran on a live Free Edition workspace on 2026-11-12 (`HONESTLY_TESTED.md`, the row for contract DQ rules as dbt tests), in a scratch catalog dropped afterwards. The two runs above are that run: nine rules as eleven tests, a bad row that failed the first, and clean data for the second. The plan after the second run was empty (`+0 ~0 -0`). Not run live: a share below `1.0` that fails, a reference share, and a regex or bounds share (only a passing completeness share was). A Git source with rules is refused by design. Not handled: a versioned dbt model, and a `dbt_project.yml` that sets `+where` or `+limit` on tests, which would change these tests too. dbt's result lines are read from the task's output, so lines that Databricks cut from a long output are reported as not in it. The run page was read through the Jobs API, not in a browser.
:::

## Tables a dbt build writes

dbt's `table` materialization rebuilds a table with `CREATE OR REPLACE`. So after the apply creates a table that a dbt build writes (locally or as a job), the module leaves its definition to dbt. It ignores the table's columns, partitions, clustering, properties and comment, and sets no column mapping. Each apply reports the column drift it no longer reconciles, and `fluid verify` is the gate. *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* The comment is left to dbt too, so the contract's descriptions are not written there; `fluid validate` warns and says so (see [Comments on a dbt-written table](#comments-on-a-dbt-written-table)). The tags are still set.

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

## Lakeflow pipelines

*(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))*

A build with `engine: lakeflow` is a [Lakeflow Declarative Pipeline](https://docs.databricks.com/aws/en/ldp/), and the expose's data-quality rules are its [expectations](https://docs.databricks.com/aws/en/ldp/expectations). You write the SELECT. forge-cli writes the pipeline's source around it: a materialized view with the expose's columns, types and comments, and one expectation per rule in `exposes[].contract.dq.rules`. `fluid apply` provisions one serverless pipeline per build, in the expose's own catalog and schema. Lakeflow records each rule's passed and failed records in the pipeline's event log, the source of the pipeline graph's Data quality tab, and `fluid apply --mode amend-and-build` prints them.

### Opting in

The engine is new in the 0.7.7 preview schema, so the contract declares `fluidVersion: "0.7.7"`. The build, from the [worked example](#worked-example-two-products):

```yaml
builds:
  - id: build-capacity
    pattern: embedded-logic
    engine: lakeflow
    outputs: [capacity]
    execution:
      trigger:
        type: manual
      runtime:
        platform: databricks
    properties:
      sql: |
        SELECT s.site_id, CAST(s.tower_height_m * 100 AS DECIMAL(10,2)) AS load_kg,
               CASE WHEN s.tower_height_m > 30 THEN 'A' ELSE 'Z' END AS method,
               current_timestamp() AS _ingested_at
          FROM fluid_iactest_ldp.bronze_sites.sites s
```

- **`pattern: embedded-logic` and `properties.sql`.** The SQL is one query, such as a `SELECT` or a `WITH`, and its result is the table. Read an upstream by its Unity Catalog name, `catalog.schema.table`. A comment before the query and a trailing `;` are fine. A second statement is refused, and so is a string, a backtick name or a `/*` comment left open at the end.
- **`outputs`.** Exactly one expose, bound to a Databricks table (`platform: databricks`, `format: delta_table`). It may be left out when the contract has only that expose.
- **`execution.trigger.type`.** `manual`, or no trigger, makes a triggered pipeline: `fluid apply --mode amend-and-build` starts an update, and so does the pipeline's page. `continuous` keeps the pipeline running. A cron schedule is refused for now. To schedule a triggered pipeline, give a Databricks job a pipeline task.
- **`execution.runtime.platform`.** `databricks`, or leave it out.

A lakeflow build also takes its `id`, `description`, `tags` and `labels`, and in `properties` a `language` (`sql`, the default), `tags` and `labels`. Any other setting, such as retries, notifications, `runtime.timeout`, `runtime.serviceAccount` or a `repository`, is refused, since the pipeline would not honour it.

With `fluidVersion: "0.7.6"`, `fluid validate` refuses the engine:

```text
 1. builds[0].engine: 'lakeflow' (a Databricks Lakeflow Declarative Pipeline) is an engine of the 0.7.7 preview schema: set the contract's fluidVersion to 0.7.7 to use it
```

### What `fluid apply` provisions for it

| Contract | Databricks object |
| --- | --- |
| The build | A serverless `databricks_pipeline` named `fluid <product> <build>`, tagged `fluid_product` and `fluid_build`, that publishes into the expose's catalog and schema. It runs on the `CURRENT` channel, not in development mode. A triggered one does not retry a failed update: `pipelines.numUpdateRetryAttempts` is `0`, where Lakeflow's default is five, since the same rows would fail the same rule. |
| The pipeline's source | A `databricks_workspace_file`, `<table>.sql`, in a folder under the applying identity's home: `.fluid/<product>/<build>/pipeline/`, each id with a digest, so no two products share a folder. |
| `location.schema` | The `databricks_schema`, as for any table, with the contract's tags. |
| `location.table`, `contract.schema` | No table resource. The pipeline creates the table at its first update, as its source defines it. |
| `accessPolicy.grants`, `policy.authz.readers` | `SELECT` and `USE_SCHEMA` on the schema for each reader. The table does not exist yet when they are granted. |

The table's own tags wait for the table too: `fluid apply` sets them after each update it runs that completes (see [Tags on the pipeline's table](#tags-on-the-pipeline-s-table)).

`fluid generate iac` shows the source before an apply. It is the `databricks_workspace_file` in `main.tf.json`, with its text in `content_base64`. For the worked example it reads:

```sql
-- Generated by forge-cli from silver.test.capacity_v1, build build-capacity. Do not edit: change the contract and run fluid apply.

CREATE OR REFRESH PRIVATE MATERIALIZED VIEW `capacity__capacity_key_unique` (
  CONSTRAINT `capacity_key_unique` EXPECT (_fluid_rows = 1) ON VIOLATION FAIL UPDATE
)
COMMENT 'Business key (site_id) must be unique per record.'
AS SELECT `site_id`, count(*) AS _fluid_rows FROM `capacity`
 WHERE `site_id` IS NOT NULL GROUP BY `site_id`;

CREATE OR REFRESH PRIVATE MATERIALIZED VIEW `capacity__capacity_freshness` (
  CONSTRAINT `capacity_freshness` EXPECT (_fluid_newest IS NOT NULL AND _fluid_newest >= current_timestamp() - INTERVAL 93600 SECONDS)
)
AS SELECT max(`_ingested_at`) AS _fluid_newest FROM `capacity`;

CREATE OR REFRESH PRIVATE MATERIALIZED VIEW `capacity__capacity_site_ref` (
  CONSTRAINT `capacity_site_ref` EXPECT (_fluid_found)
)
COMMENT 'Every non-null site_id must exist in Sites.'
AS SELECT c.`site_id` AS _fluid_value, r._fluid_key IS NOT NULL AS _fluid_found
  FROM `capacity` c
  LEFT JOIN (SELECT DISTINCT `site_id` AS _fluid_key FROM `fluid_iactest_ldp`.`bronze_sites`.`sites`) r
    ON c.`site_id` = r._fluid_key
 WHERE c.`site_id` IS NOT NULL;

CREATE OR REFRESH MATERIALIZED VIEW `capacity` (
  `site_id` string NOT NULL COMMENT 'The site\'s id',
  `load_kg` decimal(10,2) NOT NULL,
  `method` string,
  `_ingested_at` timestamp,
  CONSTRAINT `capacity_required_complete` EXPECT (`load_kg` IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT `capacity_method_valid` EXPECT ((`method` IS NULL OR `method` IN ('A', 'B', 'C')))
)
COMMENT 'Each site\'s structural load; it\'s the engineer\'s view.'
TBLPROPERTIES (
  'fluid.product_id' = 'silver.test.capacity_v1',
  'fluid.build_id' = 'build-capacity'
)
AS
SELECT s.site_id, CAST(s.tower_height_m * 100 AS DECIMAL(10,2)) AS load_kg,
       CASE WHEN s.tower_height_m > 30 THEN 'A' ELSE 'Z' END AS method,
       current_timestamp() AS _ingested_at
  FROM fluid_iactest_ldp.bronze_sites.sites s
;
```

- **The check views come first, and the table last.** Your query is the last text in the file, so nothing forge-cli writes can follow it. The order in the file does not order the pipeline: each check view reads the table, so Lakeflow runs it after the table.
- **The columns are the contract's.** Each column has its type, `NOT NULL` where it is `required`, and its `description` as its comment. The expose's `description` is the table's comment. These declared columns are the table's definition. A query whose columns or types do not match them was not tried live.
- **Change the contract, not the file.** Its first line says so. The next apply uploads the source the contract describes.

### Rules as expectations

A rule that one row decides is an expectation on the table, `CONSTRAINT <rule id> EXPECT (...)`. A rule that needs the whole table is checked by a private materialized view in the same pipeline, which is never published to the catalog. The view is named `<table>__<rule id>`, with the id in lower case. Its one expectation carries the rule id as written, so the counts name the rule either way.

| Rule `type` | Where it runs | It passes when |
| --- | --- | --- |
| `completeness` | The table | Each selected column is not null. |
| `valid_values` | The table | Each non-null value meets every declaration the rule reads: it is in the `enum`, matches the `regex` (Spark's `RLIKE`) and is within the `range`. Values the rule lists itself replace the column's declarations, as for the dbt tests (see [What a `valid_values` rule allows](#what-a-valid-values-rule-allows)). |
| `accuracy` | The table | Each non-null value meets `<operator> <threshold>`. |
| `uniqueness` | A check view | Each non-null value of the column appears once. |
| `freshness` | A check view | The newest value is no older than `window`, or younger than it with `operator: "<"`. A table with no row fails. |
| `valid_values` on a column with `labels.references` | A check view | Each non-null value exists in the referenced product's column (see [References to another product](#references-to-another-product)). When the column also declares an `enum`, `regex` or `range`, those run on the table under the same rule id, and the view is `<table>__<rule id>__reference`. |
| `schema` | The column list | The table has the contract's columns and types (above). It adds no expectation. |
| `anomaly_detection`, `drift_detection` | Refused | They are judged against the table's history. |

A null passes the value checks. `completeness` is the rule for nulls.

**Severity** decides what a failing row does:

| `severity` | On the table | On a check view |
| --- | --- | --- |
| `info`, `warn` | `EXPECT`: the row is kept and counted. | Counted. |
| `error` | `ON VIOLATION DROP ROW`: the row is not written, and the drop is counted. | Counted only. A check view has no row of the product to drop. |
| `critical` | `ON VIOLATION FAIL UPDATE`: the update fails, and Databricks rolls back its write to the table. | `ON VIOLATION FAIL UPDATE`, after the table is written: the update fails, and the table keeps what it wrote. |

Only a failed update fails `fluid apply`, so only a `critical` rule can fail it. An `error` rule's dropped rows are counted, and the apply goes on. There is no quarantine table, since the dropped rows would sit in a table outside the contract's access policy.

**Thresholds.** The `threshold` of a `completeness`, `uniqueness` or `valid_values` rule is a share. An `error` or `critical` rule of those types must hold for every row: no `threshold`, or `1.0` with `>=` or `==`. Any other share is refused there, because `DROP ROW` and `FAIL UPDATE` act on every failing row. An `info` or `warn` rule may keep its share: its expectation only counts the failing rows, and nothing compares them with the share. An `accuracy` rule's `threshold` is its bound, as for the dbt tests, so a rule of any severity takes it.

**Rule ids** name the expectations and the check views. Each must be a plain identifier (letters, digits and `_`, not starting with a digit), and unique on its expose regardless of case. A check view's name holds at most 255 characters.

#### References to another product

A `valid_values` rule on a column with `labels.references: <product id>.<column>` checks that each non-null value exists in that product's column. forge-cli finds the product's table through the workspace, as an embedded-SQL build resolves `consumes[]`:

- The product's contract is the one that declares its id, found from the nearest `fluid.workspace.yaml` above the contract and in the roots `FLUID_UPSTREAM_CONTRACTS` lists. Exactly one contract may declare it.
- The table is the expose that `consumes[]` names for the product (`exposeId`). With no `consumes[]` entry, it is the product's one Databricks table that has the column.
- The upstream contract is read without an `--env` overlay, so an overlay that moves its table is not followed.

A reference that does not resolve this way is refused as `databricks-lakeflow-reference-unresolved`, with the reason. Unlike a dbt job, a pipeline needs no `consumes[]` entry and no dbt source to check one.

### Running it from `fluid apply`

| `--mode` | The pipeline |
| --- | --- |
| `amend-and-build` | Provisioned, then one update starts now, and the apply waits for it. |
| `replace-and-build` | The same, and the update is a full refresh. |
| `amend`, `create-only`, `replace` | Provisioned only. Start an update from the pipeline's page. Until the first update, the table does not exist. |

The update starts once `tofu apply` has succeeded. `--build-id <id>` starts only that build's update. The pipeline is the one this apply provisioned: the apply finds it in its own OpenTofu state by its `fluid_product` and `fluid_build` tags, as it finds a dbt job. A continuous pipeline is not started, since Databricks keeps it running. Its table's tags are still set, once the table exists. Until then, the apply says the next apply sets them.

What an update prints, captured live on Databricks Free Edition on 2026-11-13 for the [worked example](#worked-example-two-products), with the workspace host and the ids replaced:

```text
🚀 Build 'build-capacity' - started update <update-id> of Lakeflow pipeline 'fluid silver.test.capacity_v1 build-capacity' (<pipeline-id>)
   pipeline page: https://<workspace>/#joblist/pipelines/<pipeline-id>
   0:00 CREATED
   0:01 WAITING_FOR_RESOURCES
   0:17 INITIALIZING
   0:24 SETTING_UP_TABLES
   0:31 RUNNING
   0:49 COMPLETED
   data quality (the pipeline graph's Data quality tab):
     ✗ capacity_required_complete  error    capacity: passed 3, failed 1 (dropped 1)
     ⚠ capacity_method_valid       warn     capacity: passed 2, failed 2
     ✓ capacity_key_unique         critical capacity__capacity_key_unique: passed 3, failed 0
     ✓ capacity_freshness          warn     capacity__capacity_freshness: passed 1, failed 0
     ✓ capacity_site_ref           warn     capacity__capacity_site_ref: passed 3, failed 0
   tags: 8 on fluid_iactest_ldp.silver_capacity.capacity, 1 on its columns
✅ Build 'build-capacity' - update <update-id> completed in 54s
```

- The pipeline's page comes first. Then each state the update enters gets a line, with the time since it started, and a `still <state>` line follows each minute while nothing changes.
- When the update ends, one line per rule gives its counts from the update's event log. The table's expectations come first, then the check views'. A line is a mark, the rule id, its severity, the dataset (the table, or the rule's check view) and the counts. An `error` rule on the table adds the rows it dropped.
- Then come the tags the apply set, and the time the build took.

| Mark | Meaning |
| --- | --- |
| `✓` | No row failed. |
| `⚠` | Rows failed an `info` or `warn` rule, which only counts them. |
| `✗` | Rows failed an `error` or `critical` rule. |
| `?` | No counts: a `critical` rule that failed (Lakeflow may record nothing for it), or a dataset the update did not refresh. |

In this run, the `error` rule dropped the site that has no height, and the `warn` rule counted the two sites whose `method` is `Z`. The update completed, so the apply exited `0`.

**When the update fails.** An update that ends `FAILED` or `CANCELED` fails its build, and the apply exits `1`. The apply prints the rule counts, then up to three of the update's errors. A failed expectation's error quotes the record that failed it (Databricks' `Input data:` and `Output record:`), a row of the table or of what its query read. That part is cut, because a terminal or a CI log has more readers than the table. The update's event log on the pipeline's page shows it.

Live on 2026-11-12, a duplicate `site_id` seeded into the upstream failed the update. That run came before two changes to this output, so it is shown here as forge-cli 0.30.0 prints it: the record is cut, and the `warn` rule is marked `⚠`. Abridged, with the ids replaced and the wrapped line joined:

```text
   1:00 FAILED
   data quality (the pipeline graph's Data quality tab):
     ✗ capacity_required_complete  error    capacity: passed 4, failed 1 (dropped 1)
     ⚠ capacity_method_valid       warn     capacity: passed 3, failed 2
     ✗ capacity_key_unique         critical capacity__capacity_key_unique: passed 0, failed 1
     ✓ capacity_freshness          warn     capacity__capacity_freshness: passed 1, failed 0
     ✓ capacity_site_ref           warn     capacity__capacity_site_ref: passed 4, failed 0
❌ Build 'build-capacity' - update <update-id> of Lakeflow pipeline 'fluid silver.test.capacity_v1 build-capacity' (<pipeline-id>) ended FAILED.
   Update <update-id> is FAILED since flow fluid_iactest_ldp.silver_capacity.capacity__capacity_key_unique failed an expectation check. - [EXPECTATION_VIOLATION.VERBOSITY_ALL] Flow 'fluid_iactest_ldp.silver_capacity.capacity__capacity_key_unique' failed to meet the expectation. Violated expectations: 'capacity_key_unique'. (the record is not printed here: the update's event log on the pipeline's page shows it)
```

The `critical` uniqueness rule failed the update, and the table kept the duplicate: a check view runs after the table is written. Lakeflow recorded the check's failure but no passed count, so the line reads `passed 0`.

**How long it waits.** `FLUID_DATABRICKS_RUN_TIMEOUT_SECONDS` caps the wait, in whole seconds, as for a dbt job. Unset, the cap is an hour. At the cap, the pipeline is stopped and the build fails. Ctrl-C, SIGTERM and SIGHUP stop it too, also while the start request is in flight. After five failed reads of the update in a row, the apply stops waiting and leaves the update as it is.

**It needs `databricks-sdk`.** Without the `[databricks]` extra, an apply that would start an update, or set a continuous pipeline's tags, is refused before anything is applied, as for a dbt job (see [Running the job from `fluid apply`](#running-the-job-from-fluid-apply)). `--dry-run` is not refused. It names what it would do:

```text
🔍 [DRY RUN] Build 'build-capacity' - would start an update of Lakeflow pipeline 'fluid silver.test.capacity_v1 build-capacity' and wait for it.
```

Under `replace-and-build` it reads `would start an update (full refresh) of`, and for a continuous pipeline `would set the tags of continuous Lakeflow pipeline`.

#### Tags on the pipeline's table

A pipeline's table gets the same tags as a table forge-cli owns: the product's tags, and each column's `sensitivity` (see [Comments and product tags](#comments-and-product-tags)). OpenTofu cannot set them, because the table does not exist when it runs. So `fluid apply` sets them after each update it runs that completes, and on a continuous pipeline's table once it exists. A failed update sets none. Each time it sets them:

- A declared tag is set, and a changed value is replaced.
- A tag the contract no longer declares is removed when the deploying identity set it (the tag's `updated_by`). So a label the contract dropped goes, whatever ran the updates since. A tag a steward set stays, and so does a tag the table inherits.
- When the deploying identity cannot be read, nothing is removed, and the apply says so.
- A tag that cannot be set or removed fails the build. Re-run `fluid apply --mode amend-and-build`.

Tags on a pipeline's table survive later updates and full refreshes (measured on Free Edition). An update started in Databricks, from the pipeline's page or a job, sets no tags. Live, after `site_id` lost its `sensitivity` in the contract, the second apply planned `+0 ~0 -0`, ran an update in 52 s and removed the column's tag. The 8 table tags stayed:

```text
   tags: 8 on fluid_iactest_ldp.silver_capacity.capacity, 0 on its columns
```

### Next to the pipeline's table

The pipeline owns its table. Only the pipeline writes it, and the table's comments are the definition's: a `COMMENT ON` run from outside is reset by the next update. What would compete with the pipeline is refused:

| Refusal | Refused when | The fix |
| --- | --- | --- |
| `databricks-lakeflow-enforcement` | The expose has `policy.authz.columnRestrictions` or `rowFilters`. Lakeflow binds masks and row filters only in the pipeline's definition, which forge-cli does not write yet. | Remove them, or write the expose with a dbt build. |
| `databricks-lakeflow-write-grant` | A principal would get more than read access, `MODIFY` say. | Grant `read`, `select` or `query` only. |
| `databricks-lakeflow-partitions` | The binding declares partitions. | Remove them. |
| `databricks-retention-unmapped` | The expose sets `lifecycle.expire`. | Remove it. |
| `databricks-lakeflow-writers` | Another build writes the expose. Two lakeflow builds that publish one table are `databricks-lakeflow-table-shared`. | Write the expose with one lakeflow build only. |
| `databricks-lakeflow-schema-shared` | Another expose of the contract is in the same schema. Readers get `SELECT` on the schema, so they would read it too. | Give the lakeflow-built expose a schema of its own. |
| `databricks-lakeflow-schema-not-owned` | A reader would get `SELECT` on the schema, and at plan the schema already holds a table or view the contract does not declare. Nothing is applied. | Bind the expose to a schema of its own, or move those tables out of it. |

Some things are set up at or right after `tofu apply`, before the pipeline's first update creates the table. They leave a pipeline's table out for now, and `fluid validate` warns about each one the contract asks for:

- **Unity Catalog primary and foreign keys** ([forge-cli #860](https://github.com/Agenticstiger/forge-cli/pull/860)). A pipeline's table takes them only in its definition, which forge-cli does not write yet.
- **Data quality monitoring** (see [Data quality monitoring](#data-quality-monitoring)). A freshness or completeness SLO on the expose turns on no monitor. The `dq.rules` are the pipeline's expectations, counted on each update. To say so in the contract, set `contract.dq.monitoring.enabled: false`.
- **A metric view** from `semantics` (see [Metric views](#metric-views)).
- **The Genie space** of `extensions.databricksGenie` ([forge-cli #863](https://github.com/Agenticstiger/forge-cli/pull/863)). The space leaves the table out. A product whose tables are all a pipeline's gets no space, and a space an earlier apply made for it is left as it is.

With a `qos.freshnessSLO` on the expose, for example:

```text
✅ Valid FLUID contract (schema v0.7.7)
⚠️  1 warning(s)
Validation Warnings:
====================
 1. exposes[0] (capacity) is published by a Lakeflow pipeline: fluid apply turns on no data quality monitoring for its table, so qos.freshnessSLO is not monitored. Its contract.dq.rules are the pipeline's expectations, counted on each update. Set contract.dq.monitoring.enabled to false to say so in the contract.
```

### What a lakeflow build refuses

`fluid validate`, `fluid generate iac` and `fluid apply` refuse what the pipeline would take and not honour, with the fix. `fluid plan` does not run these checks: it writes a plan for such a contract, so run `fluid validate` first. `fluid apply` refuses before anything is applied. With a cron trigger, `fluid validate` says:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.7)

Validation Errors:
==================
 1. builds[0] (build-capacity) has execution.trigger.type 'schedule'; a lakeflow build is triggered (manual: fluid apply --mode amend-and-build starts an update, and so does the pipeline's page) or continuous. Use trigger type manual or continuous, and schedule a triggered pipeline in Databricks (a job with a pipeline task) until forge-cli does.
```

`fluid generate iac` and `fluid apply` stop with `unsupported_binding`, and the `kind` is the code of the refusal:

```text
❌ unsupported_binding  [ERR_UNSUPPORTED_BINDING]
  kind: databricks-lakeflow-trigger-unsupported
  error: builds[0] (build-capacity) has execution.trigger.type 'schedule'; a lakeflow build is triggered (manual: fluid apply --mode amend-and-build starts an update, and so does the pipeline's page) or continuous.
  remediation: ['Use trigger type manual or continuous, and schedule a triggered pipeline in Databricks (a job with a pipeline task) until forge-cli does.']
```

The refusals of the build and its rules (those of the table are [above](#next-to-the-pipeline-s-table)):

| Refusal | Refused when |
| --- | --- |
| `databricks-lakeflow-pattern` | The build is not `pattern: embedded-logic` with SQL in `properties.sql`. |
| `databricks-lakeflow-query` | `properties.sql` is not one query: a second statement, a `;` inside it, or a string, backtick name or `/*` comment left open. |
| `databricks-lakeflow-trigger-unsupported` | The trigger is not `manual` or `continuous`. |
| `databricks-lakeflow-setting-unsupported` | The build sets anything else (see [Opting in](#opting-in)). |
| `databricks-lakeflow-platform` | `execution.runtime.platform` is not `databricks`. |
| `databricks-lakeflow-outputs` | The build does not write exactly one expose bound to a Databricks table. |
| `databricks-lakeflow-rule-unexpressible` | A rule no expectation can express: `anomaly_detection` (whatever the monitoring says), `drift_detection`, or a rule the rule reader refuses, such as a `valid_values` rule with no allowed values. The dbt tests read rules with the same reader, so the rule checks in [What the rules refuse](#what-the-rules-refuse) apply here too, as this refusal. |
| `databricks-lakeflow-rule-id` | A rule id that is not a plain identifier, two rules of one expose with the same id regardless of case, or a check view name over 255 characters. |
| `databricks-lakeflow-rule-threshold` | An `error` or `critical` rule with a share. |
| `databricks-lakeflow-reference-unresolved` | A `labels.references` product that the workspace does not resolve to one Databricks table with that column. |
| `databricks-lakeflow-rule-column` | A rule checks a column the table does not have, because the column's name was refused. |
| `databricks-lakeflow-range` | A `range` bound that is not a finite number. |
| `databricks-lakeflow-literal-unsafe` | An allowed value or a regex that holds `${`, or a table or column comment that holds a control character or a line break. A Lakeflow source file substitutes `${name}` from the pipeline's settings, so `${` would not stay literal. A comment with `${` is refused for every Databricks table, as `databricks-comment-unsafe`. |

Removing a pipeline from the contract needs `--allow-data-loss`, since deleting a pipeline can delete its table. Its source file and folder go without it.

### `fluid verify` on a pipeline's table

`fluid verify` checks a pipeline's table as it checks any Databricks table (see [`fluid verify`](#fluid-verify)), with these differences:

- **Before the first update,** the table does not exist, which is `CRITICAL`. The fix is the pipeline's: `Its Lakeflow pipeline creates it on its first update: run fluid apply --mode amend-and-build, or start an update from the pipeline's page`.
- **The columns** are checked against the definition, which keeps `required` as `NOT NULL`.
- **The tags and comments** are checked as on a table forge-cli owns. A missing tag's fix is `fluid apply --mode amend-and-build`, since an update run from Databricks sets none.
- **Masks, row filters and retention** are skipped. A pipeline's table cannot declare them.
- **The pipeline itself** is not checked. The jobs check covers dbt builds only.

Live, after the first update, `fluid verify` passed the columns, types, constraints and location, and all 10 tags and 2 comments: 8 table tags, the column's tag and the schema's `data_classification`. Its `USE CATALOG` check failed, as it should: the scratch catalog's owner had not granted it to `account users` (see [`USE CATALOG` is the owner's to grant](#use-catalog-is-the-owner-s-to-grant)).

### Worked example: two products

The live runs used two products in one workspace: a table of sites, and a lakeflow product that reads it and states six rules. The catalog was a scratch one, `fluid_iactest_ldp`, dropped afterwards. Use an existing catalog of yours, as in [A minimal contract](#a-minimal-contract).

```text
fluid.workspace.yaml            # version: 1
sites/contract.fluid.yaml
capacity/contract.fluid.yaml
```

`sites/contract.fluid.yaml` is a plain Databricks table:

```yaml
fluidVersion: "0.7.7"
kind: DataProduct
id: bronze.test.sites_v1
name: Sites
domain: test
metadata:
  layer: Bronze
  owner:
    team: test-team
exposes:
  - exposeId: sites
    kind: table
    binding:
      platform: databricks
      format: delta_table
      location:
        database: fluid_iactest_ldp
        schema: bronze_sites
        table: sites
    contract:
      schema:
        - name: site_id
          type: STRING
          required: true
        - name: tower_height_m
          type: DOUBLE
```

`capacity/contract.fluid.yaml` builds its table with a pipeline:

```yaml
fluidVersion: "0.7.7"
kind: DataProduct
id: silver.test.capacity_v1
name: Capacity
description: The tower's capacity, one row per site.
domain: test
labels:
  data-classification: internal
metadata:
  layer: Silver
  owner:
    team: test-team
consumes:
  - productId: bronze.test.sites_v1
    exposeId: sites
exposes:
  - exposeId: capacity
    kind: table
    version: 1.0.0
    description: Each site's structural load; it's the engineer's view.
    binding:
      platform: databricks
      format: delta_table
      location:
        database: fluid_iactest_ldp
        schema: silver_capacity
        table: capacity
      principals:
        group:analysts: account users
    contract:
      schema:
        - name: site_id
          type: STRING
          required: true
          description: The site's id
          sensitivity: internal
          labels:
            references: bronze.test.sites_v1.site_id
        - name: load_kg
          type: DECIMAL(10,2)
          required: true
        - name: method
          type: STRING
          validationRules:
            - type: enum
              constraint: A,B,C
        - name: _ingested_at
          type: TIMESTAMP
      dq:
        rules:
          - id: capacity_key_unique
            type: uniqueness
            selector: site_id
            threshold: 1.0
            operator: ">="
            severity: critical
            description: Business key (site_id) must be unique per record.
          - id: capacity_required_complete
            type: completeness
            selector: load_kg
            threshold: 1.0
            operator: ">="
            severity: error
          - id: capacity_method_valid
            type: valid_values
            selector: method
            threshold: 1.0
            operator: ">="
            severity: warn
          - id: capacity_freshness
            type: freshness
            selector: _ingested_at
            window: PT26H
            operator: "<="
            severity: warn
          - id: capacity_schema
            type: schema
            selector: "*"
            severity: error
          - id: capacity_site_ref
            type: valid_values
            selector: site_id
            threshold: 1.0
            operator: ">="
            severity: warn
            description: Every non-null site_id must exist in Sites.
accessPolicy:
  grants:
    - principal: group:analysts
      permissions: [read]
      resources: ["$.exposes[?(@.exposeId=='capacity')]"]
builds:
  - id: build-capacity
    pattern: embedded-logic
    engine: lakeflow
    outputs: [capacity]
    execution:
      trigger:
        type: manual
      runtime:
        platform: databricks
    properties:
      sql: |
        SELECT s.site_id, CAST(s.tower_height_m * 100 AS DECIMAL(10,2)) AS load_kg,
               CASE WHEN s.tower_height_m > 30 THEN 'A' ELSE 'Z' END AS method,
               current_timestamp() AS _ingested_at
          FROM fluid_iactest_ldp.bronze_sites.sites s
```

- `binding.principals` maps `group:analysts` to `account users`, a group every workspace has, which stood in for a real one.
- `capacity_site_ref` checks `site_id` against the upstream through `labels.references`, and `consumes[]` names the upstream's expose.
- `capacity_schema` adds no expectation: the column list is the check.

Apply the upstream, load it, then build the product:

```bash
export DATABRICKS_HOST=https://<workspace>.cloud.databricks.com
export DATABRICKS_TOKEN=<token>
export DATABRICKS_WAREHOUSE_ID=<your-warehouse-id>
fluid validate capacity/contract.fluid.yaml
fluid apply sites/contract.fluid.yaml --yes
fluid apply capacity/contract.fluid.yaml --mode amend-and-build --yes
fluid verify capacity/contract.fluid.yaml
```

`DATABRICKS_WAREHOUSE_ID` is needed for a product whose only table is a pipeline's too: `fluid validate` refuses any Databricks contract without it. Between the two applies, the live run loaded four sites into the upstream, two of them bad:

```sql
INSERT INTO fluid_iactest_ldp.bronze_sites.sites VALUES
  ('S1', 40.0), ('S2', 25.0), ('S3', NULL), ('S4', 35.0);
```

`S3` has no height, so its `load_kg` is null and the `error` completeness rule drops it. `S2` is not over 30 m and `S3` has no height, so both get the `method` `Z`, which the `warn` rule counts. The table holds three sites.

The product's apply planned and applied six resources: the schema, its `data_classification` tag, the readers' grant, the pipeline, its source file and its folder. Then it ran the update shown in [Running it from `fluid apply`](#running-it-from-fluid-apply). A second apply with nothing changed planned no change.

::: warning Proven live on two runs
The emitter and the build phase have unit tests against a stubbed Pipelines and tag API, and the module passes `tofu validate` against provider 1.140.0. There is no stand-in workspace tier for pipelines. The worked example ran on a live Free Edition workspace twice (`HONESTLY_TESTED.md`, the Lakeflow rows of 2026-11-12 and 2026-11-13), each time in a scratch catalog dropped afterwards. The update took 44 s on the first run and 54 s on the second, and the event log's counts were what the rules promise. A seeded duplicate failed the update with Lakeflow's `EXPECTATION_VIOLATION` error, and the apply exited `1`. That run also found that Lakeflow retried the failed update by itself, which is why a triggered pipeline now retries nothing. The second run removed a dropped label's tag. Measured too: an outside `COMMENT ON` is reset by the next update, tags survive a refresh and a full refresh, and two pipelines can update at once on Free Edition. Not run live: `replace-and-build`, a continuous pipeline, a table that exists outside its pipeline, a grant to a real group, a steward's tag, a tag list longer than one page, a failing `critical` rule with today's output (one ran live on 2026-11-12, before the record was cut), and a `critical` rule on the table itself. No live run looked at the Data quality tab: the counts above are the event log's.
:::

## Landing a DuckDB acquisition

*(since 0.27.0, [forge-cli #801](https://github.com/Agenticstiger/forge-cli/pull/801))*

A DuckDB acquisition build (`pattern: acquisition`, `engine: duckdb`) whose expose is on Databricks used to write a local file and report success with nothing in Databricks. It now lands the data in the table `fluid apply` created, in three steps:

1. **Mask and stage.** The runner applies `policy.privacy.masking` (hash, tokenize, encrypt or mask columns) and writes Parquet under `.fluid/staging`, so masked values are all that leaves the machine.
2. **Upload.** The file goes through the Files API, in one `PUT` (5 GiB limit), to `<volume>/<product>/<build>/<run id>/<file>.parquet`. The volume is `DATABRICKS_STAGING_VOLUME`, `/Volumes/<catalog>/<schema>/<volume>` with three plain identifiers, read from the environment only: a contract that named a path could aim the upload anywhere the credential reaches. Give staging a volume of its own.
3. **Load.** One statement runs on `DATABRICKS_WAREHOUSE_ID`: `INSERT OVERWRITE c.s.t (cols) SELECT cols FROM read_files('<the staged file>', format => 'parquet')`. It is a full refresh by column name that reads only this run's file, and it keeps the table's definition, grants, tags, row filter and masks. The run fails when the rows loaded differ from the rows in the file.

The staged files are always deleted: after success, after a failure, after a short load and on Ctrl-C (an `INSERT` the warehouse has answered for is cancelled first). A file that cannot be deleted fails the run and is named first. Each load also deletes what earlier runs of the same build left under `<volume>/<product>/<build>/`, but only run-id-named directories holding nothing but Parquet files, all more than an hour old; this runs under the deploy credential, which is why the volume should be its own. The run record carries `facets.databricks_load`: the table, the rows, where the count came from, the staging path, whether the staged files were deleted and how many earlier runs' leftovers were swept.

*(since 0.28.0, [forge-cli #835](https://github.com/Agenticstiger/forge-cli/pull/835))* After a load that finishes, the landing leaves nothing behind:

- **Volume directories.** After the load, it removes the build's directory `<volume>/<product>/<build>/` and then the product's `<volume>/<product>/`, each only once it lists empty. The Files API deletes only an empty directory, so a directory another run or build still uses stays. On Ctrl-C the empty volume directories are not pruned. The volume itself is never removed. A failure here is logged and does not fail the run, since an empty directory holds no data.
- **The local copy.** The masked Parquet file under `.fluid/staging/<build>/` is deleted after the load attempt, whether it succeeded or failed, and the build's directory with it once empty. On a load that completed, `facets.databricks_load.local_staging_deleted` says whether it went. After a failed load there is no facet, and the stream's error says so.
- **When the delete fails.** A local file that cannot be deleted fails the run. The error reads `databricks load: could not delete the local staged copy, which holds the landed data; delete it: <path> (<ExcName>: <reason>)`, after the load's own error if the load failed. The file holds the landed data, so delete it by hand.

From the code and tests at v0.28.0, against the in-process stand-in. The load itself ran live on 2026-11-04; the clean-up above did not.

The runner never creates or alters a table. A missing table fails the run and names `fluid apply`. A build with more than one stream is refused when it runs.

::: warning Proven live on one run
Proven against an in-process stand-in, and on a live Free Edition workspace on 2026-11-04 (`HONESTLY_TESTED.md`, the 2026-11-04 row): 5 rows loaded, the email column hashed, the staged files deleted from the volume, a second run overwrote the table, and the column masks, the row filter and a scoped grant were enforced after the `INSERT OVERWRITE`. That run also showed the empty volume directories and the local masked copy left behind, which the landing now removes; that clean-up was not re-run live. Not recorded as tried live: the Files API's limits.
:::

What is refused, before the table exists where `fluid validate` or `fluid apply` can tell:

| Refusal | Why |
| --- | --- |
| `databricks-landing-unsupported` | An acquisition writing a Databricks expose with a source mode other than `full_refresh`, or a sink format other than `parquet`. A `{{ env.X }}` placeholder there is skipped only by `fluid validate`; at apply one still unresolved is refused. |
| `databricks-masking-invalid` | A `policy.privacy.masking` rule the runner cannot apply, such as `k_anonymity`, an unknown strategy, or `masking` that is not a list. |
| `databricks-governance-unmapped` | `policy.privacy.masking` on an expose that is not written only by DuckDB acquisitions (see [What masks and filters refuse](#what-masks-and-filters-refuse)). |

## What validate refuses

`fluid validate` refuses what would apply with exit 0 and not be enforced:

- a host in the contract, on a binding or a build;
- Iceberg and a `packaging` block;
- the governance fields that are not mapped (`policy.privacy.rowLevelPolicy`, `binding.governance`, and `policy.privacy.masking` on an expose a DuckDB acquisition does not alone write), a `lifecycle.expire` the table's shape cannot keep (see [Retention](#retention)), an acquisition the landing cannot run (see [Landing a DuckDB acquisition](#landing-a-duckdb-acquisition)), an `accessPolicy` grant whose `resources` forge-cli cannot evaluate (see [Scoping a grant to an expose](#scoping-a-grant-to-an-expose)), a column restriction or row filter Unity Catalog cannot express, and a label set that collides or exceeds 50 tags (see [Column masks and row filters](#what-masks-and-filters-refuse) and [Governance tags](#governance-tags));
- a `binding.location.region` that is not a plain lower-case region name, two exposes that declare different regions, and, with a `sovereignty` block, a placement the policy refuses (see [Residency](#residency));
- a `binding.location` key the module would drop (`path` and others). `region` is read: see [Residency](#residency);
- *(since 0.30.0, [forge-cli #871](https://github.com/Agenticstiger/forge-cli/pull/871))* a contract data-quality rule, on an expose a dbt job writes, that no dbt test can run as written (see [What the rules refuse](#what-the-rules-refuse));
- *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* a lakeflow build setting the pipeline would not honour, a rule no expectation can express, and what would compete with the pipeline for its table (see [What a lakeflow build refuses](#what-a-lakeflow-build-refuses) and [Next to the pipeline's table](#next-to-the-pipeline-s-table));
- a description with a backslash or `${`, a label set that becomes one of the product's own tag keys, a tag value over 256 characters, more than 1,000 column tags on a table, and a `certification` label other than `certified` *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* (see [Comments and product tags](#comments-and-product-tags) and [Certification](#certification));
- duplicate partitions;
- a column type Databricks has no mapping for (it would be created as `string`), or would reject;
- a `semantics` block a metric view cannot hold *([forge-cli #865](https://github.com/Agenticstiger/forge-cli/pull/865), since 0.30.0)* (see [What metric views refuse](#what-metric-views-refuse)).

It warns when a `DECIMAL` has no scale, because it would keep no fractional digits. *(since 0.30.0, [forge-cli #864](https://github.com/Agenticstiger/forge-cli/pull/864))* It also warns about a `contract.dq.monitoring.window` other than one day on an expose that turns on data quality monitoring, since the window is not applied (see [Data quality monitoring](#data-quality-monitoring)). *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* It warns when a Lakeflow pipeline's table asks for Unity Catalog keys, data quality monitoring, a metric view or a Genie space, which `fluid apply` does not set up on such a table yet (see [Next to the pipeline's table](#next-to-the-pipeline-s-table)).

## CLI commands

```bash
fluid validate contract.fluid.yaml
fluid generate iac contract.fluid.yaml --out iac
fluid plan contract.fluid.yaml --out plans/plan.json
fluid apply contract.fluid.yaml --yes
fluid verify contract.fluid.yaml
fluid diff contract.fluid.yaml
fluid publish contract.fluid.yaml
fluid doctor --verbose
fluid auth logout databricks <profile>
```

`fluid apply` routes through OpenTofu automatically for `platform: databricks`, as for the other clouds; there is no flag. It verifies `bundleDigest` and `planDigest` before any `tofu apply`.

### `fluid verify`

Install the extra first: `pip install 'data-product-forge[databricks]'`. Verify reads the live Unity Catalog table and checks these:

1. **Columns** against the contract. A missing column or a changed type is `CRITICAL`; an extra column is `INFO`; a nullability mismatch is graded as for the other warehouses.
2. **`USE CATALOG`** for every reader (or `ALL PRIVILEGES`), read from the catalog's effective permissions. A reader without it is `CRITICAL`, and the finding carries the `GRANT` its owner runs. A privilege a group conveys counts ([forge-cli #775](https://github.com/Agenticstiger/forge-cli/pull/775)).
3. **Residency** (`residency`): the workspace's metastore region against `binding.location.region`. Skipped when the contract declares none. See [Residency](#residency).
4. **Governance tags** (`governance_tags`): every tag the contract implies is on the table and its schema, with its value. Skipped when the module sets no tag and no comment, which a table now seldom satisfies, since it carries the product's tags. See [Governance tags](#governance-tags). *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* It also checks the product's tags on the table, the column tags and the comments (the table's and each described column's must equal the contract's, except on a table a dbt build writes), and reads each tag list to its last page.
5. **Column masks and row filter** (`row_filter_masks`): the expected, content-hashed function names against the table's live `row_filter` and each column's `mask`, and each bound function read back for its owner (this verify's identity or the table's owner), body, parameters and return type. A missing or different binding is `CRITICAL`, with `fluid apply` as the fix. Skipped when the contract restricts nothing. See [Column masks and row filters](#column-masks-and-row-filters).
6. **Jobs**: each dbt build that writes the expose has exactly one job of its name. None means `fluid apply` did not run or the job was deleted. Several mean an apply without its state created a duplicate. A job that is `PAUSED` while its table's masks or row filter are not in place also fails, with `fluid apply` as the fix.
7. **Retention** (`retention`, [forge-cli #801](https://github.com/Agenticstiger/forge-cli/pull/801), since 0.27.0): skipped when the contract sets no `lifecycle.expire`. It reads the live table's `delta.logRetentionDuration` and `delta.deletedFileRetentionDuration` (Delta's defaults when unset). `fail`, `CRITICAL`, when the longer of the two exceeds `lifecycle.retention` or one is not an interval; the fix is the `ALTER TABLE … SET TBLPROPERTIES` that sets both, or a longer retention. `warn` when predictive optimization is off for the table (enable it, or schedule `VACUUM`), or when Unity Catalog returned no table properties and Delta's defaults were assumed (check `SHOW TBLPROPERTIES`). See [Retention](#retention).

`USE CATALOG` is checked per table, so a [scoped grant's](#scoping-a-grant-to-an-expose) principal is checked only where it was granted.

A missing table is `CRITICAL` ("run `fluid apply`"). A failure to reach the workspace is reported as a result, not a traceback, and no message carries a token.

*(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* A Lakeflow pipeline's table is checked the same way, with a few differences (see [`fluid verify` on a pipeline's table](#fluid-verify-on-a-pipeline-s-table)).

### `fluid diff`

`fluid diff` initialises OpenTofu with the committed lock and checks the state. Its live comparison has no Databricks inspector, so it reports the expose as not checked (`no live inspector for platform 'databricks'`). Use `fluid verify` for the live table.

### `fluid doctor` and the welcome scan

`fluid doctor --verbose` shows a **Databricks Provider** row in its provider table:

- `⚪ Not configured` when none of `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, `DATABRICKS_CONFIG_PROFILE` and `DATABRICKS_WAREHOUSE_ID` is set;
- `✅ Configured` when the credential resolves (it shows the workspace and auth method) and the warehouse id is set;
- `⚠️ Needs attention` when the credential is refused (with the reason and the fix) or the warehouse id is missing.

The row also says whether `databricks-sdk` is installed, and gives the install command when it is not.

It never opens a connection, never prints a token, and never fails `fluid doctor`. The `fluid forge` welcome scan lists Databricks among the detected clouds when `DATABRICKS_HOST` is set with a token, an OAuth pair or a profile name.

### `fluid publish`

*(since 0.27.0, [forge-cli #780](https://github.com/Agenticstiger/forge-cli/pull/780))*

The Command Center cannot link a Databricks table to its workspace unless it is told which workspace holds it. For a product on `platform: databricks`, `fluid publish` adds `metadata.workspace_host` to the asset it sends to the [Command Center](../concepts/command-center.md#what-fluid-publish-sends), so the Command Center can build a console link.

- **Source**: `DATABRICKS_HOST`, never the contract. A contract cannot name a host (see [Credentials](#credentials)). The value is normalised and checked as the provider checks it: `https://`, or plain `http://` only to a loopback host.
- **Value**: scheme and host only, `https://<host>[:port]`. A path, query or fragment is dropped.
- **Left out, not an error**, when:
  - `DATABRICKS_HOST` is unset, not acceptable (plain `http://` to a host that is not loopback) or malformed;
  - it carries user-info (`https://user:password@host`), which would otherwise travel with the link;
  - the product's platform is not Databricks;
  - the checkout's project config named the Command Center endpoint. The runner's environment is not the checkout's to send, the rule publish already follows for `{{ env.* }}` placeholders and the operator's credential.

The console link itself is built on the Command Center side.

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
- *(since 0.30.0, [forge-cli #871](https://github.com/Agenticstiger/forge-cli/pull/871))* **A failing rule does not stop the write.** The contract rules run as dbt tests after the model has replaced its table. A rule of severity `critical` or `error` fails the run and skips the models below it, and the table keeps what the model wrote. A build run from a Git URL cannot run the rules at all (see [Contract rules as dbt tests](#contract-rules-as-dbt-tests)).
- **The catalog is never created or granted.** Create it and grant `USE CATALOG` yourself.
- **A denied column is still listed.** Unity Catalog has no column-level grant, so a denied column is a mask that reads `NULL` (see [Column masks and row filters](#column-masks-and-row-filters)).
- **Masks and row filters come from `fluid apply` alone.** `fluid generate iac` refuses a contract that has them, and a module applied by hand would have none.
- **Landing-time masking needs a DuckDB acquisition.** `policy.privacy.masking` is applied by the acquisition runner before the data leaves the machine, so an expose written by anything else is refused (see [Landing a DuckDB acquisition](#landing-a-duckdb-acquisition)).
- **Retention is a Delta history limit.** It holds only for a table rebuilt in full. forge-cli does not set the table's retention properties and does not check that the build runs within the retention (see [Retention](#retention)).
- *([forge-cli #873](https://github.com/Agenticstiger/forge-cli/pull/873), since 0.30.0)* **A schema the contract stops using is cleared only of this product's own objects.** `fluid apply` drops the metric views and the mask and row filter functions this product made there, when the deploy identity owns them. Anything else keeps the schema, and its destroy fails until that is moved or dropped (see [A schema the contract stops using](#a-schema-the-contract-stops-using)).
- **Empty folders stay.** The `.fluid/<product>/<build>` folders above `files/` are not managed; only `files/` and below are.
- *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* **A Lakeflow pipeline's table takes no masks, row filters or partitions yet**, and gets no Unity Catalog keys, data quality monitor, metric view or Genie space. forge-cli does not write them into the pipeline's definition, and the rest is set up before the pipeline creates its table (see [Next to the pipeline's table](#next-to-the-pipeline-s-table)).
- *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* **A Lakeflow pipeline gets no schedule from the contract.** A cron trigger is refused. Start updates with `fluid apply --mode amend-and-build`, from the pipeline's page, or with a Databricks job's pipeline task.
- *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* **A failing whole-table check does not stop the write.** A `critical` uniqueness, freshness or reference rule runs in a check view after the table is written, so the failed update leaves the table with its rows (see [Rules as expectations](#rules-as-expectations)).
- *(since 0.30.0, [forge-cli #864](https://github.com/Agenticstiger/forge-cli/pull/864))* **Data quality monitoring takes no threshold and no alert from the contract.** Databricks learns each table's bounds itself, and the pinned provider's anomaly detection settings have no alert setting for forge-cli to fill (see [Data quality monitoring](#data-quality-monitoring)).

## How it is tested

The full matrix is in `HONESTLY_TESTED.md` in forge-cli. In short:

| Tier | What it covers |
| --- | --- |
| Unit | 471 tests across the emitter, jobs, credentials, engine hooks, cron conversion, the dbt runner, verify, doctor and the welcome scan, against a stubbed SDK client. *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* 107 more for Lakeflow pipelines: the generated source and module, every refusal, and the build phase against a stubbed Pipelines and tag API. |
| `tofu validate` | Both job modules (Git and workspace upload) and the dbt-written table's `ignore_changes` list validate against provider 1.140.0's schema. *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* So do a Lakeflow pipeline, its source file and folder, and the schema grant. |
| Stand-in workspace | The real `fluid` CLI, `tofu` and provider 1.140.0 against an in-process stand-in for the Unity Catalog, SQL statement, permissions and jobs APIs: plan, apply, an empty second plan, the data-loss gate, adoption, job and file removal. The stand-in does not check SQL dialect or privilege names. *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* It has no pipelines API, so Lakeflow pipelines skip this tier. |
| Live, Databricks Free Edition | One manual run on 2026-11-01 with the real `fluid` CLI: validate, plan, dry-run and apply, an empty second plan, one job run that succeeded and built the table, `fluid verify` with the real SDK, a model change, and removal of the job and its files. Everything the run created was swept afterwards. *(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* A second manual run on 2026-11-12, in a scratch catalog dropped afterwards, ran the job from `fluid apply`: `amend-and-build` started a run, waited for it and exited 0; a broken model exited 1 with the task's error and dbt's output; `replace-and-build` on a scheduled job ran `--full-refresh`, and the job kept its schedule and its commands; a run queued behind another run of the job; a missing `databricks-sdk` was refused before `tofu`; `--dry-run` and `--mode amend` started no run. *(since 0.30.0, [forge-cli #864](https://github.com/Agenticstiger/forge-cli/pull/864))* Another manual run on 2026-11-12, in a scratch catalog dropped afterwards, turned data quality monitoring on, adopted a monitor made through the API, changed what it excludes and turned it off (see [Data quality monitoring](#data-quality-monitoring)). *(since 0.30.0, [forge-cli #871](https://github.com/Agenticstiger/forge-cli/pull/871))* One more manual run on 2026-11-12, in a scratch catalog dropped afterwards, ran a dbt product's nine contract rules as eleven tests with `amend-and-build`: with a bad row seeded the run failed and `fluid apply` printed each rule's result, and on clean data the run succeeded (see [Contract rules as dbt tests](#contract-rules-as-dbt-tests)). *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* Two more manual runs, on 2026-11-12 and 2026-11-13, each in a scratch catalog dropped afterwards, built a product as a Lakeflow pipeline with `amend-and-build`: each update printed the counts its rules promise, `fluid verify` passed the table's columns and tags, a seeded duplicate failed an update, and a dropped label's tag was removed (see [Lakeflow pipelines](#lakeflow-pipelines)). |
| Emulator (nightly, not gating) | First run on 2026-10-30 passed 1 of 4: creates and the replace gate work, but a second plan is not empty against the emulator. |

*([forge-cli #865](https://github.com/Agenticstiger/forge-cli/pull/865), since 0.30.0)* Metric views: 91 unit tests (the YAML, 39 refusals and 3 near misses that must still compile, and the hooks against the stand-in) and 5 stand-in tests through the real `fluid` CLI and `tofu`, one of them with the Genie space. One manual run on Free Edition on 2026-11-12, in a scratch catalog dropped afterwards, applied the semantics block of an industry-model gold product verbatim (13 dimensions, 3 non-additive measures, 4 filtered metrics) on a table shaped like it. The apply created the view and granted `SELECT` to its 3 readers, `MEASURE()` returned each market at its latest snapshot, and a second apply ran no statement. Not proven live for metric views: Genie and AI/BI dashboards reading the view, and a query sent as one of its readers.

*([forge-cli #873](https://github.com/Agenticstiger/forge-cli/pull/873), since 0.30.0)* A schema the contract stops using: 14 tests of the rules against the stand-in, 24 of the engine with `tofu` stubbed, and 2 through the real `fluid` CLI and `tofu` against the stand-in, in which a table with a metric view, a mask and a row filter moves to another schema, and a schema's last expose is removed. Not proven live: that the provider destroys the table before its schema and Unity Catalog then deletes the schema once its functions are dropped. A live run on 2026-11-03 measured only that Unity Catalog does not delete a schema that holds a function.

Not proven live: a Git source, profile or OAuth auth, a run-as service principal, table adoption, a larger project, and re-adopting a job after lost state. *(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* Nor are the reason line of a queued run and a run queued for the workspace's limit. *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* Nor, for a Lakeflow pipeline, are `replace-and-build`, a continuous pipeline, a table that exists outside its pipeline, a grant to a real group, a steward's tag, a tag list longer than one page, and a failing `critical` rule with today's output (one ran live on 2026-11-12, before the record was cut).
