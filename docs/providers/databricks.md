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
- ✅ **dbt builds as jobs**: a dbt build whose `execution.runtime.platform` is `databricks` becomes a serverless job that Databricks runs on its own trigger. *On forge-cli's feat/databricks-build-run-now branch ([forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861)), not yet on `main` or in a release.* `fluid apply --mode amend-and-build` also starts a run now and waits for it (see [Running the job from `fluid apply`](#running-the-job-from-fluid-apply))
- ✅ **Residency**: `binding.location.region` is checked against the contract's `sovereignty` policy and against the workspace's metastore (see [Residency](#residency))
- ✅ **Verify**: `fluid verify` checks the live table's columns, `USE CATALOG` for every reader, the residency, the governance tags, the bound masks and row filter, and that each dbt job exists exactly once
- ✅ **One pinned credential**: the workspace comes from `DATABRICKS_HOST` only, and a run never falls back to a stray profile
- ⚠️ **Live drift**: `fluid diff` has no Databricks inspector yet (see [`fluid diff`](#fluid-diff))
- ✅ **Column masks, row filters, denied columns**: Unity Catalog SQL functions that `fluid apply` binds on the table (see [Column masks and row filters](#column-masks-and-row-filters))
- ✅ **Retention**: `lifecycle.expire` is accepted for a table rebuilt in full on every run, and `fluid verify` checks the table's Delta history against it (see [Retention](#retention))
- ✅ **Landing from a DuckDB acquisition**: the acquisition runner uploads Parquet to a Unity Catalog volume and loads the table with `INSERT OVERWRITE`, applying `policy.privacy.masking` before the data leaves the machine (see [Landing a DuckDB acquisition](#landing-a-duckdb-acquisition))
- ✅ **Described in Unity Catalog**: table and column comments from the contract, the product's identity as table tags, a column's `sensitivity` as a column tag, and Unity Catalog's certification (see [Comments and product tags](#comments-and-product-tags) and [Certification](#certification)) *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))*
- ✅ **Scoped grants**: an `accessPolicy` grant with `resources` is placed only on the tables it names (see [Scoping a grant to an expose](#scoping-a-grant-to-an-expose))
- ❌ **Iceberg, `packaging`, and the governance fields that are not mapped**: `fluid validate` refuses them rather than apply something that is not enforced (see [What validate refuses](#what-validate-refuses))

## Prerequisites

| You need | Why |
| --- | --- |
| OpenTofu `1.6.0` or newer on `PATH` | `fluid apply` runs `tofu`. An older one stops the run. |
| A Unity Catalog workspace with an existing catalog | The catalog is read, never created. The identity that applies needs `USE CATALOG` and `CREATE SCHEMA` on it. |
| A SQL warehouse, its id in `DATABRICKS_WAREHOUSE_ID` | Every table statement runs on it, and so do the dbt jobs. Find the id under SQL Warehouses, Connection details. The id is not a secret. |
| A Unity Catalog volume of its own, `/Volumes/<catalog>/<schema>/<volume>` in `DATABRICKS_STAGING_VOLUME` | Only for a DuckDB acquisition that lands in Databricks (see [Landing a DuckDB acquisition](#landing-a-duckdb-acquisition)). |
| `pip install 'data-product-forge[databricks]'` | The extra brings `databricks-sdk`. `fluid verify` needs it, and so does `fluid apply` to bind [column masks and row filters](#column-masks-and-row-filters) and to [land a DuckDB acquisition](#landing-a-duckdb-acquisition). *On forge-cli's feat/databricks-build-run-now branch ([forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861)), not yet on `main` or in a release.* An apply that [runs a dbt job](#running-the-job-from-fluid-apply) needs it too. |

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

The tags a contract carries are its and the expose's `labels`, plus `fluid_classification`, `fluid_jurisdiction`, `fluid_regulation` and `fluid_residency`, from the classification (the expose's `policy.classification`, else `metadata.classification`) and the contract's `sovereignty` block. Keys and values first pass through the label alphabet the three clouds share (lower-case letters, digits, `_` and `-`, at most 63 characters), so a tag carries the same text on each.

| On | Carries |
| --- | --- |
| Each schema the product owns | The contract's own labels and governance values. Two exposes in one schema give the same tags. |
| Each table | The same, plus the expose's labels and classification. |

Two rules shape the keys:

- **A `-` in a key becomes `_`.** A Unity Catalog tag key may not contain `. , - = / :`, and a governance label key is lower-case letters, digits, `_` and `-`. `data-classification` is the tag `data_classification`; `fluid_jurisdiction` stays as it is. The value is not changed further.
- **Nothing is dropped, nothing is overwritten.** Two labels that become one key (`cost-center` and `cost_center`) are refused as `databricks-tag-collision`. More than the 50 tags a Unity Catalog securable holds is refused as `databricks-tags-too-many`. `fluid validate` reports both. *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* On a table, the product's own tags (see [Comments and product tags](#comments-and-product-tags)) count toward the 50 with the governance labels, and a label that becomes one of their keys is also `databricks-tag-collision`.

A contract with no labels gets the module it always did. *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* Since 0.28.0 that is no longer so for a table: a contract with no labels still gets the product's own tags on it.

An assignment that already exists is imported before the first apply, best-effort as grants are, so a run after lost state adopts it instead of failing. Removing a label destroys only its assignment. That holds no data, so it does not need `--allow-data-loss`: the apply prints it, as it does a revoked grant.

`fluid verify` reads the table's and its schema's tags into a `governance_tags` dimension. Every tag the contract implies must be there with its value. A missing or changed tag is `CRITICAL`, with `fluid apply` as the fix. A tag someone else set is ignored, and a module that sets no tag and no comment skips the dimension. The tag list is paginated: verify follows every page, and a repeated page token or more than 100 pages is an error, not a pass.

::: warning Tags on a table a dbt build writes
Databricks does not document whether a table keeps its tags across the `CREATE OR REPLACE` a dbt `table` materialization runs, and forge-cli has not proven it. If tags go missing after a build, `fluid apply` sets them again. `fluid verify` is the gate.
:::

Not run against a live workspace.

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

Each function is created once, as `CREATE FUNCTION IF NOT EXISTS`, under a name that carries a hash of its definition: `fluid_rf_<table>_<hash8>` for the row filter and `fluid_mask_<table>_<column>_<hash8>` for a mask, in the table's schema. Unity Catalog refuses to replace a function a filter or mask uses, so a changed predicate or rule is a new function, bound in place of the old one, and the same contract always names the same function. A superseded function is dropped by `fluid apply` after the apply succeeds ([forge-cli #801](https://github.com/Agenticstiger/forge-cli/pull/801), since 0.27.0), when no table in the schema uses it and the run's identity owns it, and the run prints `dropped superseded function <name>`. Only `fluid_rf_<table>_…`, `fluid_mask_<table>_<column>_…` and deny-all functions of the contract's tables are candidates. A function owned by another identity, or by an owner that cannot be read, is left and printed as `left function <name>: …`. A `DROP` that fails prints `note: superseded function <name> was not dropped: …` and the apply still succeeds. When a schema's tables or functions cannot all be read, nothing in it is dropped. *(since 0.28.0, [forge-cli #835](https://github.com/Agenticstiger/forge-cli/pull/835))* `fluid apply --mode dry-run` now lists those drops and runs nothing. For each `fluid_` mask or row-filter function the clean-up would drop, it prints `would drop superseded function <name> (after the apply, if it succeeds)`, and `would leave function <name>: <why>` where it would leave one. It works out the list against the bindings the apply leaves, so a function bound now to a table the contract manages is listed as droppable when the contract no longer expects it. When a schema cannot be read, the dry run prints `note: orphan functions in <catalog>.<schema> not listed: ...`. This is from the code at v0.28.0 and was not run against a live workspace.

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

*On forge-cli's feat/databricks-build-run-now branch ([forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861)), not yet on `main` or in a release.* Under `--mode amend-and-build`, the run the apply starts (see [Running the job from `fluid apply`](#running-the-job-from-fluid-apply)) comes after the bindings, so it fills a protected table. It leaves the job paused: the next `fluid apply` unpauses the schedule, as above.

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

Never uploaded: `profiles.yml`, `target/`, a hidden file or directory, a symbolic link. A path key that names the project root, a hidden directory or a place outside the project is refused. The upload takes at most 1000 files and 20 MiB, and a file may be 2 MiB. The apply uploads the project as it is when the apply runs, as a local dbt run reads it when it runs. A plan's `planDigest` and `bundleDigest` bind the contract, not the project's files.

**A Git URL** is cloned by Databricks, and nothing is uploaded. It must be `https://` with no user or password in it, on `github.com`, `gitlab.com`, `bitbucket.org` or Azure DevOps (`dev.azure.com`, or a `*.visualstudio.com` organisation). Name exactly one ref, once: `?branch=`, `?tag=` or `?commit=`. Add `&path=` for a project below the repository root. A private repository needs a Git credential in Databricks.

```yaml
    repository: https://github.com/acme/orders-dbt?tag=v1.2.0&path=dbt
```

### Triggers, retries, notifications, timeout, run-as

| Contract | Job |
| --- | --- |
| `trigger.type: schedule` (or no type) with `cron` | A Quartz `schedule`, days of the week by name. `trigger.timezone` is an IANA name; the default is `UTC`. |
| `trigger.type: continuous` | Databricks' `continuous` trigger. |
| `trigger.type: manual`, or no trigger | No trigger. Start a run from the job's page or with `databricks jobs run-now`. *On forge-cli's feat/databricks-build-run-now branch ([forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861)), not yet on `main` or in a release.* Or apply with `--mode amend-and-build`, which starts one and waits for it (see [Running the job from `fluid apply`](#running-the-job-from-fluid-apply)). |
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
- a dbt build with another adapter (`engine: dbt-snowflake`, for example) and `runtime.platform: databricks`: a Databricks job runs dbt with the dbt-databricks adapter only.

### Applying and removing

`fluid apply` never runs such a build's dbt on the applying machine: the build runs as its job. A dbt build without `runtime.platform: databricks` still runs locally with the dbt-databricks profile. forge-cli's own schedules (`fluid generate schedule`, the Airflow DAG `fluid apply` writes) give a Databricks job build no task: Databricks starts its runs. In 0.29.0, `--mode amend-and-build` provisions the job, then prints its name and how to start a run now.

*On forge-cli's feat/databricks-build-run-now branch ([forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861)), not yet on `main` or in a release.* `--mode amend-and-build` and `--mode replace-and-build` start a run of the job and wait for it, as the next section says.

Removing a job, an uploaded file or a folder from the contract needs no `--allow-data-loss`, since no table data is lost. The job's run history goes with the job, and the apply says so.

### Running the job from `fluid apply`

*On forge-cli's feat/databricks-build-run-now branch ([forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861)), not yet on `main` or in a release.*

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
  error: a dbt build runs on Databricks, and the build phase starts its job through databricks-sdk, which is not installed; nothing was applied
  hint: pip install 'data-product-forge[databricks]', or apply with --mode amend to provision the job without starting it
```

`--dry-run` is not refused. It runs `tofu plan`, applies and starts nothing, and names the run it would start:

```text
🔍 [DRY RUN] Build 'summarize' - would start a run of Databricks job 'fluid iactest.build.sites_summary summarize' and wait for it.
```

Under `replace-and-build` the line ends `with dbt build --full-refresh and wait for it.`

**Several products, in lineage order.** Each apply starts its own product's jobs only. To build an estate whose products read each other, provision every product first, in parallel, with `--mode amend`. Then run `--mode amend-and-build` one lineage level at a time, upstream first. For a product that has not changed since, the second apply plans no change (live: `tofu plan: +0 ~0 -0`, about 30 seconds for some 75 resources), except to unpause a job [created paused](#a-job-that-writes-a-table-not-yet-protected). Then it starts the runs and waits for them.

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
- a description with a backslash or `${`, a label set that becomes one of the product's own tag keys, a tag value over 256 characters, more than 1,000 column tags on a table, and a `certification` label other than `certified` *(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* (see [Comments and product tags](#comments-and-product-tags) and [Certification](#certification));
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
- **The catalog is never created or granted.** Create it and grant `USE CATALOG` yourself.
- **A denied column is still listed.** Unity Catalog has no column-level grant, so a denied column is a mask that reads `NULL` (see [Column masks and row filters](#column-masks-and-row-filters)).
- **Masks and row filters come from `fluid apply` alone.** `fluid generate iac` refuses a contract that has them, and a module applied by hand would have none.
- **Landing-time masking needs a DuckDB acquisition.** `policy.privacy.masking` is applied by the acquisition runner before the data leaves the machine, so an expose written by anything else is refused (see [Landing a DuckDB acquisition](#landing-a-duckdb-acquisition)).
- **Retention is a Delta history limit.** It holds only for a table rebuilt in full. forge-cli does not set the table's retention properties and does not check that the build runs within the retention (see [Retention](#retention)).
- **Empty folders stay.** The `.fluid/<product>/<build>` folders above `files/` are not managed; only `files/` and below are.

## How it is tested

The full matrix is in `HONESTLY_TESTED.md` in forge-cli. In short:

| Tier | What it covers |
| --- | --- |
| Unit | 471 tests across the emitter, jobs, credentials, engine hooks, cron conversion, the dbt runner, verify, doctor and the welcome scan, against a stubbed SDK client. |
| `tofu validate` | Both job modules (Git and workspace upload) and the dbt-written table's `ignore_changes` list validate against provider 1.140.0's schema. |
| Stand-in workspace | The real `fluid` CLI, `tofu` and provider 1.140.0 against an in-process stand-in for the Unity Catalog, SQL statement, permissions and jobs APIs: plan, apply, an empty second plan, the data-loss gate, adoption, job and file removal. The stand-in does not check SQL dialect or privilege names. |
| Live, Databricks Free Edition | One manual run on 2026-11-01 with the real `fluid` CLI: validate, plan, dry-run and apply, an empty second plan, one job run that succeeded and built the table, `fluid verify` with the real SDK, a model change, and removal of the job and its files. Everything the run created was swept afterwards. *On forge-cli's feat/databricks-build-run-now branch ([forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861)), not yet on `main` or in a release.* A second manual run on 2026-11-12, in a scratch catalog dropped afterwards, ran the job from `fluid apply`: `amend-and-build` started a run, waited for it and exited 0; a broken model exited 1 with the task's error and dbt's output; `replace-and-build` on a scheduled job ran `--full-refresh`, and the job kept its schedule and its commands; a run queued behind another run of the job; a missing `databricks-sdk` was refused before `tofu`; `--dry-run` and `--mode amend` started no run. |
| Emulator (nightly, not gating) | First run on 2026-10-30 passed 1 of 4: creates and the replace gate work, but a second plan is not empty against the emulator. |

Not proven live: a Git source, profile or OAuth auth, a run-as service principal, table adoption, a larger project, and re-adopting a job after lost state. *On forge-cli's feat/databricks-build-run-now branch ([forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861)), not yet on `main` or in a release.* Nor are the reason line of a queued run and a run queued for the workspace's limit.
