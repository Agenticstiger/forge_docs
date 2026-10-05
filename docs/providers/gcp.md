# GCP Provider

**Status:** ✅ Production Ready  
**Docs Baseline:** CLI `0.18.1`<br>
**Services:** BigQuery, Cloud Storage, Pub/Sub, IAM, Data Catalog policy tags, Cloud KMS

> **Why it matters**
> Ship the same contract to BigQuery without a GCP-specific rewrite.
> Set `binding.platform: gcp` and `fluid apply` compiles the contract to an OpenTofu module for the `hashicorp/google` provider, runs it, and lands the build's rows in the table it created.

A GCP binding goes through three stages, each driven by the contract:

1. **Provision.** `fluid apply` emits an OpenTofu module (`fluid generate iac` writes the same module for review) and runs `tofu`. These come from that module: datasets, tables, buckets, grants, policy tags, keys and partition expiry.
2. **Land.** In `--mode amend-and-build`, a build whose output is a BigQuery table stages its result as Parquet and loads it with one BigQuery load job.
3. **Check.** `fluid verify` reads the live table and compares it with the contract: schema, location, row count, masking, and the governance the module emitted.

---

## Quick start

### Prerequisites

```bash
# The CLI with the BigQuery client. Add `local` when builds run SQL on DuckDB
# and land the result in BigQuery (see "Loading data").
pip install "data-product-forge[gcp,local]"

# OpenTofu 1.6 or later on PATH: `fluid apply` delegates to it.
tofu version

# Application Default Credentials, read by both OpenTofu and fluid's own BigQuery client.
gcloud auth application-default login

gcloud services enable bigquery.googleapis.com
# Only when the contract uses them:
gcloud services enable storage.googleapis.com      # Cloud Storage bindings
gcloud services enable datacatalog.googleapis.com  # column restrictions (policy tags)
gcloud services enable cloudkms.googleapis.com     # binding.encryption.kms (0.7.6)
```

### A minimal contract

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: analytics.customers_v1
name: Customer Analytics
domain: analytics

metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-engineering@company.example.com

accessPolicy:
  grants:
    - principal: "group:data-analysts@company.example.com"
      permissions: [read, select]

exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: analytics
        table: customers
        region: europe-west3      # set it: an omitted region means BigQuery's US multi-region
    contract:
      schema:
        - name: id
          type: INTEGER
          required: true
        - name: email
          type: STRING
```

Review the module, then apply it:

```bash
fluid validate contract.fluid.yaml
fluid generate iac contract.fluid.yaml --out infra
fluid apply contract.fluid.yaml --yes
```

`fluid generate iac` prints what it wrote:

```text
Wrote OpenTofu module: infra/main.tf.json  (provider: gcp, 3 resources)

Review and apply with OpenTofu:
  tofu -chdir=infra init
  tofu -chdir=infra plan
```

The three resources are the dataset (`location: europe-west3`, `project: my-project-id`), the table with its schema (`INTEGER` becomes `INT64`), and one `google_bigquery_dataset_iam_member` granting `roles/bigquery.dataViewer` to the group. `--provider gcp` is optional: the provider is read from `binding.platform`.

::: tip A starter contract
`fluid init <name> --quickstart --provider gcp` writes a GCP starter from the bundled `fluid.starter-gcp` blueprint, offline. As of 0.18.1 it declares `fluidVersion: 0.7.4`, a placeholder `project: your-gcp-project` and no region; set both before you apply.
:::

---

## Authentication

fluid's BigQuery and Data Catalog clients and OpenTofu's `hashicorp/google` provider authenticate with Application Default Credentials. ADC sources such as `gcloud auth application-default login`, a service-account key file, an attached service account or workload identity federation work, with no key handling in fluid:

| Where you run | What ADC finds |
|---|---|
| A laptop | `gcloud auth application-default login` |
| A GCE VM, GKE pod or Cloud Build step | the attached service account |
| Another cloud or CI system | a Workload Identity Federation `external_account` file named by `GOOGLE_APPLICATION_CREDENTIALS` |

### Keyless from AWS (Workload Identity Federation)

A pipeline that runs on AWS (an EC2 agent or an ECS task with an IAM role) can deploy to GCP without a service-account key. Create a workload identity pool with an AWS provider, let the AWS role impersonate a deploy service account, then write the credential configuration:

```bash
gcloud iam workload-identity-pools create-cred-config \
  projects/<project-number>/locations/global/workloadIdentityPools/<pool>/providers/<provider> \
  --service-account=<deploy-sa>@<project>.iam.gserviceaccount.com \
  --aws --enable-imdsv2 \
  --output-file=gcp-wif.json

export GOOGLE_APPLICATION_CREDENTIALS="$PWD/gcp-wif.json"
fluid apply contract.fluid.yaml --env gcp --yes
```

The file holds no secret: it tells the Google auth library to exchange the instance's AWS credentials for a short-lived GCP token. To scope the pool to one AWS role, map `attribute.aws_role` from `assertion.arn.extract('assumed-role/{role}/')` in the pool provider and grant `roles/iam.workloadIdentityUser` on the deploy service account to that attribute.

---

## Where the resources go

### Project and region are binding fields

`binding.location.project` and `binding.location.region` decide where each expose is provisioned, whatever project `gcloud` is set to. The project is written onto the dataset, the table, their IAM members, the key ring and the taxonomy, and the build's load job runs in it. Two exposes can target two projects from one contract.

| Field | When it is omitted |
|---|---|
| `location.project` | `tofu` uses the provider's project (`GOOGLE_PROJECT`, `GOOGLE_CLOUD_PROJECT`, `GCLOUD_PROJECT`, `CLOUDSDK_CORE_PROJECT`). The build's load job reads the same variables. |
| `location.region` | The dataset is created in BigQuery's `US` multi-region. With a `sovereignty` block the contract is refused instead (below). |

::: warning Before 0.16.2
`binding.location.project` was ignored by the GCP module, so resources went to the ambient project. If you applied a contract that names a project with an earlier release, check where its datasets live before the next apply.
:::

### Sovereignty fails closed

With a [`sovereignty`](../concepts/sovereignty.md) block, a GCP binding that names no region is refused, because the platform would choose where the data lives. `fluid validate` reports it:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
...
 1. ❌  Binding declares no region, so where its data lives cannot be checked
against the sovereignty policy (the platform would choose)
   💡 Set binding.location.region to one of: europe-west3
```

`fluid generate iac` and `fluid apply` refuse the same binding (`ERR_GENERATE_IAC_FAILED`, "GCP placement refused by the sovereignty policy"). BigQuery's `EU` and `US` multi-regions count as the EU and US jurisdictions.

### One project per environment

Keep the base contract cloud-neutral and put the project in an overlay, or in an environment variable:

```yaml
binding:
  platform: gcp
  format: bigquery_table
  location:
    project: "{{ env.FLUID_GCP_PROJECT }}"
    dataset: analytics
    table: customers
    region: europe-west3
```

`fluid apply`, `fluid plan`, `fluid verify` and, since 0.18.1, `fluid diff`'s live check resolve the placeholder before they touch BigQuery. On 0.18.0, `fluid diff` read the unresolved value and refused the binding as "not a valid id", so a generated pipeline's `--exit-on-drift` stage failed on every run. As of 0.18.1, `fluid generate iac` writes an unset variable into the module verbatim (`"project": "{{ env.FLUID_GCP_PROJECT }}"`) and exits 0, so set it before you generate. See [per-environment overlays](../recipes/per-environment-overlays.md).

### State

`fluid apply` keeps OpenTofu state locally unless you name a backend. `--state-backend gcs://<bucket>/<prefix>` (or `FLUID_STATE_BACKEND`) puts it in Cloud Storage. With no key named, the default key includes the provider, `fluid/<id>/gcp/terraform.tfstate`, so a contract applied to AWS and GCP through overlays keeps two states. An earlier per-contract default is migrated with `tofu init -migrate-state`; a state at that key that belongs to another provider is left in place and logged.

---

## What `fluid apply` creates

| Contract | Emitted resource |
|---|---|
| An expose that resolves to a BigQuery table | `google_bigquery_dataset` + `google_bigquery_table` with the contract schema |
| An expose that resolves to a BigQuery view | `google_bigquery_dataset` + `google_bigquery_table` with `view.query` from `location.query` |
| An expose that resolves to Cloud Storage | `google_storage_bucket` |
| An expose that resolves to Pub/Sub | `google_pubsub_topic` |
| An Iceberg expose | the warehouse bucket (see [Iceberg](#iceberg-on-bigquery-via-dbt-since-0-14-0)) |
| `binding.labels` | resource labels, next to `managed_by: fluid` and `fluid_contract: <id>` |
| `accessPolicy.grants` | `google_bigquery_dataset_iam_member` / `google_storage_bucket_iam_member` ([Access grants](#access-grants-accesspolicy)) |
| `policy.authz.columnRestrictions` | Data Catalog taxonomy, policy tags and reader grants ([Column restrictions](#column-restrictions-policy-tags)) |
| `exposes[].lifecycle.expire` *(0.7.6)* | DAY partitions with `expiration_ms` ([Retention](#retention-0-7-6)) |
| `binding.encryption.kms` *(0.7.6)* | Cloud KMS key ring and key, used by the dataset and table ([Encryption](#encryption-at-rest-cmek-0-7-6)) |

### Column types

Contract types are written as BigQuery types:

| Contract type | BigQuery type |
|---|---|
| `string`, `text`, `varchar`, `char`, `uuid` | `STRING` |
| `integer`, `int`, `bigint`, `smallint` | `INT64` |
| `float`, `double`, `double precision` | `FLOAT64` |
| `numeric`, `decimal(p,s)` | `NUMERIC` |
| `boolean` | `BOOL` |
| `timestamp`, `timestamptz`, `timestamp with time zone` | `TIMESTAMP` |
| `datetime` | `DATETIME` |
| `date`, `time`, `json`, `bytes` (`blob`) | `DATE`, `TIME`, `JSON`, `BYTES` |

A bare `array` is written as `ARRAY`, which is not a BigQuery column type; declare a typed column or a JSON column instead. `fluid verify` treats BigQuery's legacy names (`INTEGER`, `FLOAT`, `BOOLEAN`, `RECORD`) as equal to `INT64`, `FLOAT64`, `BOOL` and `STRUCT`; see [`fluid verify`](../cli/verify.md#bigquery).

### Not emitted

These are not produced by the 0.18.1 GCP module. A contract key for them is either absent from the schema or accepted and ignored:

- BigQuery row-level security (`CREATE ROW ACCESS POLICY`) and dynamic data masking (data policies).
- VPC Service Controls.
- Partitioning, clustering, table expiration, materialized or authorized views from `binding.properties` (`partitioning`, `clustering`, `materialized`, `authorized`). `binding.properties` passes validation and the module ignores these keys. Partitioning comes only from [retention](#retention-0-7-6).
- Service accounts, routines, external tables and Cloud Run services.

---

## Configuration

### Provider Settings

The GCP provider needs no contract-level provider block. It is selected from each expose's `binding.platform`, so `--provider gcp` is optional for `plan`, `apply`, and `verify`. What you configure per output is the `binding`: the `format`, the `location` coordinates and, on 0.7.6, `encryption` and `principals`.

BI Engine reservations, query cost limits (`max_bytes_billed`) and networking have no contract field. Manage them with `gcloud` or your platform's own configuration.

### How a GCP expose resolves to a target (since 0.15.0)

`binding.format` refines the target; it is no longer the whole answer. Since
`0.15.0` one resolver decides what a GCP expose is provisioned as, and
`fluid generate iac`, `fluid apply`, `fluid validate` and `fluid verify` all route
through it, so the stages cannot disagree about what an expose *is*:

| Step | What is read | Outcome |
|------|--------------|---------|
| 1 | An explicit GCP `binding.format` | `bigquery_table` / `bigquery_view` → BigQuery, `gcs_bucket` → Cloud Storage, `pubsub_topic` → Pub/Sub, an Iceberg format with a derivable bucket → the Iceberg warehouse bucket |
| 2 | Otherwise, the shape of `binding.location` on a GCP-platform binding | a `dataset` key → BigQuery, `bucket` → Cloud Storage, `topic` → Pub/Sub |
| 3 | Neither matched | the expose resolves to no GCP resource, and `fluid validate` reports it |

Step 2 is what stops a `platform: gcp` expose whose `format` is absent, or is the
schema-valid `gcs_file`, from emitting nothing. The platform token goes through the
same alias table the provider detector uses, so `google`, `gcs` and `bigquery` are
read as GCP for both questions: "which plugin runs?" and "which exposures are
mine?".

Formats that name no `hashicorp/google` resource by design stay silent rather than
being reported as a no-op: `http_api`, `grpc_api`, `kafka_topic`, and stores on
another platform (`snowflake_table`, `s3_file`, `athena_table`, `redshift_table`,
`postgres_table` and friends). Iceberg exposes are left to the
[Iceberg prerequisite checks](../cli/validate.md#iceberg-prerequisite-checks-since-0-14-0),
which name the specific missing input instead of reporting the same cause twice.

::: warning Before `0.15.0`
The emitter dispatched on `binding.format` alone, so a schema-valid expose such as
`platform: gcp`, `format: gcs_file`, `location.bucket: acme-raw` validated clean and
emitted **nothing**. As of `0.15.0` that expose emits its bucket, and a GCP expose that
still resolves to nothing is reported at validate time: an **error** when a format
names a container while `binding.location` omits the key that container needs, a
**warning** otherwise. A resource-free module is a hard `generate_iac_empty_module`
failure unless you pass `--allow-empty`.
:::

`fluid verify` asks the same resolver. A BigQuery table or view goes to the BigQuery
verifier and is addressed by the name the emitter used (an expose with no
`location.table` is named for its `exposeId`). A GCS bucket, Pub/Sub topic or Iceberg
warehouse reports `unsupported`, which means "not checked" rather than "check failed".

---

### Iceberg on BigQuery via dbt (since 0.14.0)

An Iceberg expose on a GCP binding (`binding.format: iceberg`) makes
`fluid generate transformation` emit dbt's `catalogs.yml` with
`catalog_type: biglake_metastore`, and `fluid apply` provisions the one
prerequisite dbt names and refuses to create: the GCS warehouse bucket. The
BigLake metastore itself needs no setup; it is built into BigQuery.

```yaml
exposes:
  - exposeId: events
    kind: table
    binding:
      platform: gcp
      format: iceberg              # or iceberg_table
      location:
        project: my-project-id
        dataset: analytics
        table: events
        bucket: my-lake            # or a full URI: warehouse: gs://my-lake/products/events
        path: products/events      # this product's prefix of a shared warehouse root
    contract:
      schema:
        - name: id
          type: INTEGER
          required: true
```

- **One bucket, both halves.** The IaC bucket name is derived from the same
  warehouse URI the dbt emitter writes into `external_volume`, so the bucket dbt
  loads into is the bucket `fluid apply` creates.
- **Shared warehouse roots are destroy-safe.** When the binding declares a
  `location.path` (the product owns only a prefix of a shared warehouse root), the
  bucket's `force_destroy` is dropped, so one product's destroy cannot take another
  product's data with it.

Retention, keys and column restrictions are refused on an Iceberg binding: they apply only to a BigQuery table.

---

## Loading data

Rows reach BigQuery through a build run in `--mode amend-and-build` (a plain `fluid apply` provisions only). Two kinds of build load a BigQuery table, and both use the same load.

### SQL on DuckDB, landed in BigQuery

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: sales.orders_daily
name: Orders Daily
domain: sales
metadata:
  layer: Silver
  owner:
    team: sales-data
    email: sales-data@company.example.com
builds:
  - id: orders_daily
    pattern: embedded-logic
    engine: duckdb
    properties:
      sql: |
        SELECT CAST(ordered_at AS DATE) AS order_date,
               COUNT(*)                 AS orders,
               SUM(amount)              AS revenue
        FROM orders
        GROUP BY 1
      parameters:
        inputs:
          - name: orders
            path: data/orders.csv
            format: csv
    outputs:
      - orders_daily
exposes:
  - exposeId: orders_daily
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: sales
        table: orders_daily
        region: europe-west3
    contract:
      schema:
        - name: order_date
          type: DATE
          required: true
        - name: orders
          type: INTEGER
        - name: revenue
          type: NUMERIC
```

```bash
fluid apply contract.fluid.yaml --mode amend-and-build --yes
```

The SQL runs on the local DuckDB engine, inside the [DuckDB sandbox](../advanced/duckdb-sandbox.md). The result is written as Parquet under `.fluid/staging/<build>/` and one load job moves it into the table `tofu` created: `WRITE_TRUNCATE`, `CREATE_NEVER`, with the table's own schema. A `TIMESTAMP` column holding DuckDB's zone-less timestamp is loaded as UTC. A failed load, a missing table or a short load fails the build, and the run is recorded under `.fluid/runs/` so `fluid verify` holds the table to the rows it landed. Add `.fluid/` to `.gitignore`.

The SQL can also read an upstream product's BigQuery table. Name it in `consumes[]` and refer to it by its `exposeId`; the upstream contract is found under the nearest `fluid.workspace.yaml` or in `FLUID_UPSTREAM_CONTRACTS`, and read with the same `--env` overlay as this run. The table is read through the BigQuery API into a staged Parquet file, which the view reads. [`fluid apply`](../cli/apply.md) documents the discovery rules.

Refused before the SQL runs (`EmbeddedSqlLandingError`):

- a landing on GCS, `gs://`, Azure, Snowflake or Databricks;
- a second expose in `outputs` bound to a cloud store or warehouse (this path lands only the first);
- a landing that is one of the build's own inputs;
- an expose with `policy.privacy.masking` (`MaskingNotAppliedError`): this path does not apply masking, so a masked gold table must be built another way.

With a `sovereignty` block, every BigQuery table the build reads or loads must name a region inside the policy (`EmbeddedSqlSovereigntyError`).

### Acquisition into BigQuery

A source-aligned acquisition build on the DuckDB engine lands one stream in a BigQuery table through the same load:

```yaml
builds:
  - id: ingest_orders
    pattern: acquisition
    engine: duckdb
    properties:
      source:
        kind: postgres
        connection:
          host: "{{ env.PGHOST }}"
          port: "{{ env.PGPORT }}"
          database: "{{ env.PGDATABASE }}"
          user: "{{ env.PGUSER }}"
          password: "{{ env.PGPASSWORD }}"
        mode: full_refresh          # WRITE_TRUNCATE; incremental_append is WRITE_APPEND
        streams:
          - public.orders
      sink:
        format: parquet
    outputs:
      - orders_raw
exposes:
  - exposeId: orders_raw
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: crm_bronze
        table: orders
        region: europe-west3
    contract:
      schema:
        - name: id
          type: INTEGER
          required: true
        - name: status
          type: STRING
```

Refused before any work runs: more than one stream, a sink format other than `parquet`, a source mode other than `full_refresh` or `incremental_append`, and an install without the `gcp` extra (`loading into BigQuery needs the gcp extra: pip install 'data-product-forge[gcp]'`). Masking in `policy.privacy.masking` is applied before the file is staged. See [source-aligned acquisition](../advanced/source-aligned-acquisition.md#masking-at-landing). A downstream product that reads this table through `consumes[]` is shown in [the same chain on S3 and BigQuery](../recipes/consumes-contract-to-contract.md#the-same-chain-on-s3-and-bigquery).

### Load location and emulators

A load job runs where the table is. A binding with no region gives the job no location, so BigQuery runs it in the table's location instead of a guessed `US`. Pinning `location.region` remains the recommendation.

With `BIGQUERY_EMULATOR_HOST` set, loads, reads and `fluid verify` go to that host with anonymous credentials, so no real token is sent to the emulator. A load job that reports no row count is checked by counting the table afterwards.

---

## Security & Governance

### Access grants (`accessPolicy`)

```yaml
accessPolicy:
  grants:
    - principal: "group:data-analysts@company.example.com"
      permissions: [read, select]
    - principal: "serviceAccount:etl@my-project-id.iam.gserviceaccount.com"
      permissions: [write, insert]
```

Each grant becomes one non-authoritative `google_bigquery_dataset_iam_member` per role and member, on every dataset the contract creates:

```text
google_bigquery_dataset_iam_member  ..._roles_bigquery_dataViewer_group_data_analysts_company_example_com_4451af44f1
    member: group:data-analysts@company.example.com   role: roles/bigquery.dataViewer
google_bigquery_dataset_iam_member  ..._roles_bigquery_dataEditor_serviceAccount_etl_my_project_id_iam_gserviceaccount_com_ef975625fb
    member: serviceAccount:etl@my-project-id.iam.gserviceaccount.com   role: roles/bigquery.dataEditor
```

| Permission | BigQuery dataset role | Cloud Storage bucket role |
|---|---|---|
| `read`, `select`, `query` | `roles/bigquery.dataViewer` | `roles/storage.objectViewer` (`read`) |
| `write`, `insert`, `update`, `delete` | `roles/bigquery.dataEditor` | `roles/storage.objectCreator` (`write`), `roles/storage.objectAdmin` (`delete`) |
| `admin`, `owner` | `roles/bigquery.dataOwner` | `roles/storage.admin` |

A principal is `<type>:<identity>` (`user:`, `group:`, `serviceAccount:`, `domain:`), and the member resource name carries a hash of role and member, so `data.eng`, `data-eng` and `data_eng` keep one grant each.

Because the grants are members, not the dataset's whole access list:

- BigQuery's default entries (the project's owners, writers and readers) stay on the dataset. Keep basic project roles away from projects that hold restricted data; [policy tags](#column-restrictions-policy-tags) still protect restricted columns.
- A grant made outside the contract is not removed by the next apply.
- `fluid verify` does not check dataset grants yet.

To grant a consumer in another project, name its identity:

```yaml
accessPolicy:
  grants:
    - principal: "serviceAccount:consumer@other-project.iam.gserviceaccount.com"
      permissions: [read, select, query]
```

#### Placeholder principals are refused

On GCP, a principal in a reserved top-level domain (`.example`, `.test`, `.invalid`, `.localhost`) or one that is not an IAM member at all (`group:data-platform` with no domain, a bare `analysts`, `role:analyst`) is refused by `fluid validate`, `fluid generate iac` and `fluid apply`:

```text
 1. exposes accessPolicy: principal 'group:data-analysts@company.example'
resolves to 'group:data-analysts@company.example', a placeholder: .example is a
reserved top-level domain (RFC 2606), so no real identity has it, and BigQuery
refuses an access entry for an identity that does not exist. ...
```

Map such a logical principal to a real identity in [`binding.principals`](#logical-principals-binding-principals-0-7-6), or to `[]` when it has no identity on GCP.

#### First apply after upgrading from 0.16.x or earlier

Before 0.17.0 the grants were the dataset's authoritative `access` list. The first `fluid apply` on a dataset whose state still holds that list sets `access`, for that one apply, to the list minus the entries no member resource covers, which revokes them; the apply prints the dataset and the revoked entries. Entries added to the dataset by hand since the last apply are removed too, as the old module removed them. Special groups, views and routines are kept. `fluid diff` shows the same change, so run it first to preview the revocation. A dataset whose every entry would be revoked is refused, naming the entries to revoke by hand. Later applies leave `access` alone.

Revoking a grant deletes no data, so it applies without `--allow-data-loss`; the [OpenTofu data-loss gate](../cli/apply.md#opentofu-data-loss-gate) lists what that flag does cover. The role table is also in [`fluid generate iac`](../cli/generate-iac.md#access-grants-on-gcp-0-17-0). For the AWS side of the same fields, see [`accessPolicy` on AWS](./aws.md#accesspolicy-on-aws).

#### `metadata.policies` is deprecated

The legacy `metadata.policies` mapping still emits, so existing out-of-tree
contracts keep working, but it has never been schema-valid and fails
`fluid validate`. Migrate to `accessPolicy`. Both surfaces are read, so a contract
mid-migration does not drop half its grants; duplicate grants collapse. See
[Release Notes `0.13.0`](../RELEASE_NOTES_0.13.0.md#accesspolicy-is-now-the-iac-access-grant-surface).

### Shared vs. isolated containers

By default the product **owns** the BigQuery dataset and GCS bucket it creates. A
[`packaging` block](../cli/generate-iac.md#packaging-modes) (`fluidVersion: "0.7.6"`)
can declare them `shared` instead: a pre-existing, platform-owned pool the product
writes into but cannot destroy. A shared dataset and bucket become OpenTofu data
sources, the grants become per-table `google_bigquery_table_iam_member` resources,
and a shared bucket's IAM members gain an object-prefix CEL condition.

### Column restrictions (policy tags)

```yaml
exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: analytics
        table: customers
        region: europe-west3
    policy:
      authz:
        columnRestrictions:
          - principal: "group:interns@company.example.com"
            columns: [email]
            access: deny
    contract:
      schema:
        - name: id
          type: INTEGER
        - name: email
          type: STRING
          sensitivity: pii
```

With the `accessPolicy` above, `fluid apply` emits, for any `fluidVersion`:

| Resource | What it holds |
|---|---|
| `google_data_catalog_taxonomy` | one per product and dataset, `activated_policy_types: [FINE_GRAINED_ACCESS_CONTROL]`, in the binding's region |
| `google_data_catalog_policy_tag` | one per set of restricted columns that share their readers, attached through the table schema's `policyTags` |
| `google_data_catalog_policy_tag_iam_member` | `roles/datacatalog.categoryFineGrainedReader` for each allowed reader (here `group:data-analysts@company.example.com`) |

Semantics:

- `deny`: the principal may not read the columns. `allow`: only the principals an `allow` names may read them. A deny beats an allow.
- A restriction never grants access. The readers are the `accessPolicy` read grantees and the expose's `policy.authz.readers`; an allowed principal that is not a reader is logged, not added.
- An expose with a restriction and no reader is refused (`column-restriction-no-readers`): the tag would lock the columns for everyone.
- The restriction's `tags` and `labels` go into the policy tag's description.

A denied principal gets an error on the restricted columns, and `SELECT * EXCEPT (email)` still works for it. Measured against real BigQuery on 4 Oct 2026, the refusal reads:

```text
User has neither fine-grained reader nor masked get permission to get data protected by policy tag "<taxonomy> : <tag>" on column <project>.<dataset>.<table>.<column>.
```

`fluid policy-apply` is a different path, and in 0.18.1 it changes nothing on GCP: it reports the compiled bindings and returns `applied: 0`. Both the dataset IAM and the policy tags that enforce column restrictions are provisioned by `fluid apply`. See [`fluid policy apply`](../cli/policy-apply.md#what-each-provider-does).

### Data Masking

Two kinds of masking exist, and only one is applied on GCP:

- **Masking at landing (applied).** A DuckDB acquisition build applies `policy.privacy.masking` while it writes the staged Parquet file, so BigQuery receives treated values. Since 0.17.0, `fluid verify` fails (CRITICAL) a masked BigQuery column whose values lack the strategy's shape.
- **BigQuery dynamic data masking (not emitted).** No BigQuery data policy is created, so a reader with table access sees the stored value. Use [column restrictions](#column-restrictions-policy-tags) to keep a column from a principal. The AWS side is [masking at landing](./aws.md#masking-at-landing); what the platform enforces overall is on [Governance](../advanced/governance.md#what-the-platform-enforces).

```yaml
policy:
  privacy:
    masking:
      - column: email
        strategy: mask             # keeps keepFirst (default 0) and keepLast (default 4) characters
        params:
          keepFirst: 1
          keepLast: 4
      - column: credit_card
        strategy: hash             # salted SHA-256; salt from $FLUID_PII_HASH_SECRET (16 bytes or more)
```

| Strategy | Output | Params | Secret |
|---|---|---|---|
| `hash` | 64 lowercase hex characters (SHA-256 of salt and value) | `saltEnv` | `FLUID_PII_HASH_SECRET` by default, 16 bytes or more |
| `mask` | `*` except the first `keepFirst` and last `keepLast` characters | `keepFirst`, `keepLast` | none |
| `tokenize` | 32 lowercase hex characters (HMAC-SHA256) | `keyEnv` | `FLUID_PII_TOKENIZATION_KEY` by default, 32 bytes or more |
| `encrypt` | `aesgcm:v1:` and base64url (AES-GCM, reversible with the key) | `keyEnv` | `FLUID_PII_ENCRYPTION_SECRET_KEY` by default |

A treated column lands as a string. `k_anonymity` is refused at landing, as are unknown params (`algorithm` among them), a literal salt or key in `params`, an unset secret, and a masked column declared with a non-string type. An embedded-SQL build refuses a masked expose. The params are typed in `fluidVersion: "0.7.6"` and accepted untyped on 0.7.5.

### Retention (0.7.6)

```yaml
fluidVersion: "0.7.6"
...
exposes:
  - exposeId: candidates
    kind: table
    lifecycle:
      retention: P90D
      expire: true
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: northwind-demo
        dataset: telco_gold
        table: churn_candidates
        region: europe-west3
        partitionBy: [scored_at]      # optional: one DATE, TIMESTAMP or DATETIME column
```

The table gets `time_partitioning: {type: DAY, field: scored_at, expiration_ms: 7776000000}`, so each daily partition is deleted 90 days after its date. Without `partitionBy` it is partitioned by ingestion time and a row lives at least `retention` after it landed. With `partitionBy`, retention counts from the column's date: a backfill of rows older than `retention` lands in expired partitions and is deleted at once (`fluid apply` logs `bigquery_retention_event_time`). Retention does not set a table-level expiration.

BigQuery cannot partition an existing table. The first apply that adds `expire: true` to a live table plans the table's replacement, which `fluid apply` refuses without `--allow-data-loss`; the next build lands the data again. Changing `retention` later is an in-place update. `partitionBy` must be a list; a scalar fails validation.

### Encryption at rest (CMEK, 0.7.6)

```yaml
binding:
  platform: gcp
  format: bigquery_table
  location: { project: northwind-demo, dataset: telco_gold, table: churn_candidates, region: europe-west3 }
  encryption:
    kms: product
```

| `kms` value | Result |
|---|---|
| `product` | `google_kms_key_ring` `fluid-<id>-<dataset>` and `google_kms_crypto_key` `bigquery` (`rotation_period: 7776000s`, 90 days) in the dataset's location; `roles/cloudkms.cryptoKeyEncrypterDecrypter` for the BigQuery service agent; the key as the dataset default and the table's `encryption_configuration` |
| `projects/<p>/locations/<l>/keyRings/<r>/cryptoKeys/<k>` | that existing key |
| `none` | Google-managed keys |

An AWS key (`alias/...`, an ARN) is refused on GCP. Tables of one dataset that declare different keys are refused (`encryption-kms-mixed-dataset`). Adding a key to a live table plans its replacement and needs `--allow-data-loss`. A key ring cannot be deleted on GCP: `tofu destroy` schedules the key's versions for destruction and the next apply adopts the same names.

### Logical principals (`binding.principals`, 0.7.6)

The base contract names principals as the business knows them; each environment's overlay maps them to real identities on that cloud:

```yaml
# overlays/gcp.yaml
exposes:
  - binding:
      platform: gcp
      principals:
        group:data-platform@northwind.example: group:data-platform@northwind.example.com
        group:analysts@northwind.example: group:analysts@northwind.example.com
```

A value is one identity, a list, or `[]` (no identity on this cloud, nothing granted). With `binding.principals` present, every principal the expose names must be mapped (`principal-unmapped`). The same mapping drives dataset grants and policy-tag readers.

### Prerequisites for governed resources

| Feature | API | Role for the identity running `fluid apply` |
|---|---|---|
| Dataset grants | BigQuery | `bigquery.datasets.update` on the datasets |
| Column restrictions | `datacatalog.googleapis.com` | `roles/datacatalog.categoryAdmin` |
| `encryption.kms: product` | `cloudkms.googleapis.com` | `roles/cloudkms.admin` |

`fluid verify`'s policy-tag check needs `datacatalog.taxonomies.get` and `datacatalog.taxonomies.getIamPolicy`; its row-count query needs `roles/bigquery.jobUser`.

---

## What `fluid verify` checks on BigQuery

```bash
fluid verify contract.fluid.yaml --env gcp --strict
```

| Check | Fails as |
|---|---|
| The table exists | error |
| Columns and types match the contract | CRITICAL (missing column or changed type) |
| The dataset's location matches `location.region` | CRITICAL |
| Row count equals the last recorded load (`full_refresh`) | CRITICAL |
| The table is not empty | CRITICAL |
| Masked columns hold treated values | CRITICAL |
| Partition type, field and expiry; no table expiration *(retention)* | CRITICAL |
| The table's and the owned dataset's `kmsKeyName` *(encryption)* | CRITICAL |
| Each restricted column carries a tag whose fine-grained readers are exactly the derived set | CRITICAL |

The table is addressed as the load addresses it, with `{{ env.* }}` resolved. A GCS bucket, Pub/Sub topic or Iceberg warehouse reports `unsupported`. See [`fluid verify`](../cli/verify.md).

::: tip Proven against real BigQuery
forge-cli's own tests prove the governed module against `tofu validate` and an in-process BigQuery stand-in. On 4 Oct 2026, products applied in a demo lab from shared base contracts through `--env gcp` overlays passed `fluid verify` against live BigQuery, including retention, Cloud KMS encryption and policy tags, and per-persona impersonation showed a denied column refused by its policy tag.
:::

---

## Troubleshooting

### "Access Denied" during apply

The identity running `fluid apply` needs permission to create and update datasets, tables and dataset IAM in the target project. Grant it `roles/bigquery.dataOwner` and `roles/bigquery.jobUser` on that project, not `roles/bigquery.admin`, which carries project-wide BigQuery administration that an apply does not need. Add the roles in [Prerequisites for governed resources](#prerequisites-for-governed-resources) for the features the contract uses: `roles/datacatalog.categoryAdmin` for column restrictions and `roles/cloudkms.admin` for `encryption.kms: product`.

### A placeholder grant is refused

See [Placeholder principals are refused](#placeholder-principals-are-refused): map the principal in `binding.principals`.

### The dataset landed in `US`

The binding names no region. Set `location.region`; a dataset's location cannot be changed in place.

---

## Next Steps

- [GCP Walkthrough](../walkthrough/gcp.md): a hands-on deployment
- [`fluid apply`](../cli/apply.md): modes, embedded-SQL reads and landings
- [`fluid generate iac`](../cli/generate-iac.md): the emitted module and packaging modes
- [Governance & policy](../concepts/governance-policy.md)
- [DuckDB sandbox](../advanced/duckdb-sandbox.md): what build SQL may read
