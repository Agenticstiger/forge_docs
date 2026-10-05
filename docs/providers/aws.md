# AWS Provider

Deploy data products to Amazon Web Services (S3, Glue, Athena, Lake Formation) with the same contract and CLI commands you use for the other providers.

**Docs Baseline:** CLI `0.18.1`<br>
**`fluid apply` creates:** S3 buckets, Glue databases and tables, Lake Formation registrations and grants, KMS keys, S3 lifecycle rules<br>
**`fluid verify` reads:** Glue, Athena, S3, KMS, Lake Formation

> **Why it matters**
> Set `binding.platform: aws` with a `format` and a `location`, and `fluid apply` emits an OpenTofu module for S3, Glue and Lake Formation. Athena queries the Glue table it creates.

<CliCast
  src="/forge_docs/demos/aws-quickstart.svg"
  title="AWS quickstart — S3 + Glue + Athena"
  caption="Same Customer 360 contract as the local quickstart, with its binding edited for aws. S3 bucket provisioned, Glue catalog created, Athena able to query it, from one fluid apply."
  width="920"
  insight="One contract, S3 + Glue + Athena, no console clicks in the recording. | The S3 bucket, Glue database, and Glue table are provisioned by fluid apply from the contract. | The same contract retargets to GCP or Snowflake by editing only its binding."
/>

::: warning Which schema version
Examples on this page use `fluidVersion: "0.7.5"`, the stable schema. The fields marked **0.7.6** (`binding.encryption`, `exposes[].lifecycle.expire`, `lakeFormation.bucketPolicy`, `binding.principals`) exist only in the preview schema, so a contract that uses them declares `fluidVersion: "0.7.6"`. Under `0.7.5`, `fluid validate` rejects each of them with `Additional properties are not allowed`.

Orchestration guidance prefers `fluid generate schedule --scheduler airflow` over the older `fluid generate-airflow`.
:::

---

## Overview

The AWS provider turns a FLUID contract into cloud resources:

- **Plan and apply** — S3 buckets, Glue databases and Glue tables. No Athena workgroup is created: Athena queries run in a workgroup you already have, and `fluid verify` uses `primary` unless you pass `--athena-workgroup`.
- **Lake Formation governance** — location registration, principal grants, column-limited grants, LF-tags (TBAC), row filters and the bucket policy that goes with the grants. See [Lake Formation](#lake-formation).
- **Column restrictions** — `policy.authz.columnRestrictions` becomes each Lake Formation grant's excluded columns. See [Column restrictions](#column-restrictions).
- **Encryption and retention** *(0.7.6)* — a KMS key per bucket and an S3 lifecycle rule. See [Encryption at rest and retention](#encryption-at-rest-and-retention).
- **Masking at landing** — the DuckDB runner treats `policy.privacy.masking` columns before they reach S3. See [Masking at landing](#masking-at-landing).
- **Verification** — `fluid verify` reads Glue, runs an Athena `COUNT(*)` and checks the governance above on the live account. See [Verify on AWS](#verify-on-aws).
- **Sovereignty validation** — region allow and deny lists are enforced before deployment. See [Data Sovereignty](#data-sovereignty).
- **IAM policy compilation** — `fluid policy-compile` writes IAM bindings from `accessPolicy`, as advisory output only. See [accessPolicy on AWS](#accesspolicy-on-aws).

## Working example: Bitcoin price tracker

This contract passes `fluid validate --strict` on CLI `0.18.1`. Its read access is Lake Formation grants on the binding, and one of the two grantees has two columns restricted from it.

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: crypto.market_data.bitcoin_prices_aws_v1
name: Bitcoin Price Tracker (AWS Athena)
description: >
  Bitcoin price data on S3, cataloged in Glue and queried through Athena.
domain: Market Data

metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-eng@company.example.com

# The binding's region must be one of these. With enforcementMode: strict,
# a region written as an {{ env.* }} placeholder fails `fluid validate`.
sovereignty:
  jurisdiction: "EU"
  dataResidency: true
  allowedRegions:
    - eu-central-1
    - eu-west-1
  enforcementMode: strict

exposes:
  - exposeId: bitcoin_prices_table
    title: Bitcoin Price Feed
    version: "1.0.0"
    kind: table

    binding:
      platform: aws
      format: parquet
      location:
        database: crypto_data
        table: bitcoin_prices
        bucket: "{{ env.S3_BUCKET }}"
        path: data/bitcoin/prices/
        region: eu-west-1

      # On AWS, who may read the table is declared here, as Lake Formation
      # grants. accessPolicy is not written to AWS.
      governance:
        lakeFormation:
          registerLocation: true
          grants:
            - principal: "arn:aws:iam::{{ env.AWS_ACCOUNT_ID }}:role/data-analyst"
              permissions: [SELECT]
            - principal: "arn:aws:iam::{{ env.AWS_ACCOUNT_ID }}:role/intern"
              permissions: [SELECT]

    policy:
      classification: Internal
      authn: iam
      authz:
        readers:
          - "arn:aws:iam::{{ env.AWS_ACCOUNT_ID }}:role/data-analyst"
          - "arn:aws:iam::{{ env.AWS_ACCOUNT_ID }}:role/intern"
        columnRestrictions:
          - principal: "arn:aws:iam::{{ env.AWS_ACCOUNT_ID }}:role/intern"
            columns: [market_cap_usd, volume_24h_usd]
            access: deny

    contract:
      schema:
        - name: price_timestamp
          type: timestamp
          required: true
          description: UTC timestamp when the price was recorded
        - name: price_usd
          type: decimal(18,2)
          required: true
          description: Bitcoin price in USD
        - name: market_cap_usd
          type: decimal(20,2)
          required: false
          description: Total market capitalization in USD
          sensitivity: internal
        - name: volume_24h_usd
          type: decimal(20,2)
          required: false
          description: 24-hour trading volume in USD
          sensitivity: internal

# A placeholder for your own ingest code in ./runtime. This page does not
# ship that script.
builds:
  - id: bitcoin_price_ingestion
    description: Fetch Bitcoin prices from the CoinGecko API
    pattern: hybrid-reference
    engine: python
    repository: ./runtime
    properties:
      model: ingest
    execution:
      trigger:
        type: manual
      runtime:
        image: python:3.11-slim
        dependencies: [boto3, requests, pyarrow]
        env: [AWS_REGION, S3_BUCKET]
    outputs:
      - bitcoin_prices_table
```

Set the two placeholders, validate, and review the module `fluid apply` would run:

```bash
export S3_BUCKET=my-fluid-data-bucket AWS_ACCOUNT_ID=123456789012

fluid validate contract.fluid.yaml --strict
fluid generate iac contract.fluid.yaml --provider aws --out ./review
```

```text
✅ Valid FLUID contract (schema v0.7.5)
...
Wrote OpenTofu module: ./review/main.tf.json  (provider: aws, 7 resources)
```

`fluid validate` keeps `{{ env.* }}` placeholders literal. `fluid generate iac` and `fluid apply` resolve them before they write the module, A variable that is unset is not an error: the placeholder is written into the module as literal text, so set both before you generate or apply.

### Infrastructure created

The seven resources the example above produces:

| Resource | Comes from | Details |
|----------|------------|---------|
| `aws_s3_bucket` | `location.bucket` | Created with `force_destroy = true`, so destroying it deletes the objects in it. |
| `aws_glue_catalog_database` | `location.database` | The Data Catalog database. |
| `aws_glue_catalog_table` | `location.table`, `contract.schema` | An external table over `s3://<bucket>/<path>`. A `parquet` table declares the Parquet input and output formats and `ParquetHiveSerDe`, which is what lets Athena read it. |
| `aws_lakeformation_resource` | `registerLocation: true` | Registers `arn:aws:s3:::<bucket>/<path>` with the Lake Formation service-linked role. |
| `aws_lakeformation_permissions` (two) | `grants[]` | One resource per grant. The `intern` grant is `table_with_columns` with the two restricted columns excluded. |
| `aws_s3_bucket_policy` | `grants[]` with an `arn:` principal | Plan-time `count`: zero unless a grantee is in another AWS account. See [Bucket policy](#bucket-policy). |

Declaring more fields adds resources: the [Lake Formation](#lake-formation) fields add `aws_lakeformation_data_lake_settings`, `aws_lakeformation_lf_tag`, `aws_lakeformation_resource_lf_tags` and `aws_lakeformation_data_cells_filter`, and the [0.7.6 fields](#encryption-at-rest-and-retention) add `aws_kms_key`, `aws_kms_alias`, `aws_s3_bucket_server_side_encryption_configuration` and `aws_s3_bucket_lifecycle_configuration`.

The module also looks up the caller's account (`data.aws_caller_identity`) whenever a Lake Formation, KMS or `{account}-fluid-data` bucket reference needs it.

::: tip Athena can read the table
Since `0.16.2`, a `parquet` Glue table carries `MapredParquetInputFormat`, `MapredParquetOutputFormat` and `ParquetHiveSerDe`. Before that, the table had no storage classes and Athena queries on it failed with `HIVE_UNSUPPORTED_FORMAT`. A table created by `0.16.1` or earlier declares them after a re-apply with a current CLI. Iceberg and the other formats are emitted without these classes.
:::

After the build lands data under the table's prefix, query it in Athena:

```sql
SELECT price_timestamp, price_usd
FROM crypto_data.bitcoin_prices
ORDER BY price_timestamp DESC
LIMIT 5;
```

The Glue table exists, empty, as soon as `fluid apply` finishes; it has rows once a build has written objects under `data/bitcoin/prices/`.

### Shared vs. isolated containers

::: tip New in `0.13.0` (`0.7.6` preview, opt-in)
By default this product **owns** the S3 bucket and Glue database it creates. A
[`packaging` block](../cli/generate-iac.md#packaging-modes) can instead declare them `shared` — a
pre-existing, platform-owned pool that the product writes into but **cannot destroy**. A shared
bucket becomes `data.aws_s3_bucket` with no `force_destroy`; a shared Glue database is addressed by
literal name; Lake Formation `registerLocation` scopes to `location.path` and registers nothing when
a pooled bucket has no prefix. Contracts with no `packaging` block emit exactly as before.
:::

### Key schema patterns

The binding schema uses three fields to identify platform resources:

| Field | Purpose | AWS Values |
|-------|---------|-----------|
| `binding.platform` | Cloud provider | `aws` |
| `binding.format` | Storage format | `parquet`, `csv`, `json`, `avro`, `orc`, `delta` and `iceberg` get a Glue table |
| `binding.location` | Resource coordinates | `bucket`, `path`, `region`, `database`, `table` |

GCP uses `platform: gcp` with `format: bigquery_table`, and Snowflake `platform: snowflake` with `format: snowflake_table`. Retargeting a contract changes `platform`, `format` and `location` together; see [Switch clouds](../recipes/switch-clouds.md).

## Region

How `--env` picks the overlay that carries the region is in [Environments and overlays](../concepts/environments-and-overlays.md).

Name a real region code in the binding:

```yaml
location:
  region: eu-west-1
```

When every AWS binding in the contract names the same region code, the emitted module pins it on the provider, and it wins over `AWS_REGION` in your shell:

```json
"provider": { "aws": { "region": "eu-west-1" } }
```

That is also what keeps the sovereignty check and the placement of the resources in agreement. What the module does not pin:

| Binding region | Provider region |
|----------------|-----------------|
| One region code across all AWS bindings | That region |
| Two or more region codes | The environment's (`AWS_REGION`), with the warning `aws_bindings_span_regions regions=eu-west-1,us-east-1: the provider region comes from the environment` |
| A jurisdiction (`EU`), a Google region, or a placeholder that is still unresolved when the module is written | The environment's |

`fluid generate iac` and `fluid apply` resolve a placeholder such as `{{ env.AWS_REGION }}` first, so it is pinned when it resolves to a region code. `fluid validate` and `fluid plan` keep it literal. Under `enforcementMode: strict` (the schema default) a literal placeholder fails `fluid validate` with two errors, a region outside `allowedRegions` and a region that does not match the jurisdiction; under `advisory` the same findings are warnings, and `--strict` turns warnings into exit 1. Put the real region in the binding, in an overlay per environment if the environments differ ([per-environment overlays](../recipes/per-environment-overlays.md)).

### Moving a contract between regions

Before planning, `fluid apply` reads the regions its existing state records. If they differ from the pinned region, it stops. This is what a contract first applied from a shell in another region meets: without the guard, `tofu` would plan the resources as new in the pinned region, plan no destroy, and leave the originals unmanaged. `fluid diff` runs the same check. The guard is described in [`fluid apply`](../cli/apply.md#region-move-guard).

```text
CLI command error
❌ opentofu_region_moved  [ERR_OPENTOFU_REGION_MOVED]
  error: state holds this contract's resources in us-east-1, but its bindings
name eu-west-1. Applying would create them again in eu-west-1 and leave the
originals unmanaged
  state: .fluid/iac/aws/crypto_market_data_bitcoin_prices_aws_v1

💡 Suggestions:
  • If the resources should stay where they are, set the binding's
location.region to the region the error names
  • If they should move, empty and remove them there first (tofu destroy in the
state directory the error names, with AWS_REGION set to the old region), then
apply again
```

To keep the resources, set `location.region` to the region the error names (`us-east-1` here). To move them, run `tofu destroy` in the state directory the error prints, with `AWS_REGION` set to the old region, then apply again. The bucket this product owns is created with `force_destroy`, so that destroy deletes its objects.

That output comes from the real apply path with the state read replaced by one that records `us-east-1`; it was not produced against an AWS account.

## State

[OpenTofu state](../concepts/state.md) covers the keys, backends and the commands that read state; [One contract, two clouds](../recipes/one-contract-two-clouds.md) deploys one contract to both clouds.

`fluid apply` keeps OpenTofu state per provider, so one contract deployed to AWS and to GCP through two `--env` overlays has two states and neither plan reads the other cloud's resources as orphans.

- **Local state** (the default) is in `.fluid/iac/aws/<id>/` under the workspace directory (`--workspace-dir`, default the current directory), where `<id>` is the contract id with `.` and `-` written as `_`. The apply prints the module's path and a `state:` line.
- **Remote state** takes `--state-backend s3://<bucket>/<key>` or the `FLUID_STATE_BACKEND` variable. A key you write is used as written. A bucket with no key gets `fluid/<contract id>/aws/terraform.tfstate` when the spec comes from `FLUID_STATE_BACKEND` or the contract has a `packaging` block.
- **A bucket-only `--state-backend` on a contract with no `packaging` block** gets the shared key `fluid/terraform.tfstate`, which every such contract on that bucket uses. Name a key, or use `FLUID_STATE_BACKEND`, so two products do not share a state.

State that a release before the per-provider key wrote at `fluid/<contract id>/terraform.tfstate` is moved to the new key by the first apply, with OpenTofu's own `init -migrate-state`. When the old key holds another provider's state (a gcp apply that finds the aws state there), the apply leaves it and logs that the old key holds the other provider's state. A key that names no provider and holds another cloud's resources is refused with `state_shared_with_another_provider`.

## CLI commands

The CLI reads the provider from the contract's `binding.platform`; no `--provider` flag is needed.

`--provider` disambiguates a contract that spans clouds or declares none; it is not
a retargeting switch, and *since 0.15.0* a `--provider` that contradicts every cloud
the contract declares is rejected before anything is written, on both
`fluid generate iac` and `fluid apply`. Retarget by editing `binding` — see the
[switch-clouds recipe](../recipes/switch-clouds.md).

The aliases the provider detector accepts — `platform: s3`, `glue`, `athena`,
`redshift` as well as `aws` — are now also what the AWS emitter filters `exposes[]`
with *(since 0.15.0)*. They used to disagree: one of those aliases auto-detected as
AWS and was then skipped by every AWS filter, so a correctly detected provider
emitted an empty module.

```bash
# Validate against the bundled schema; --strict also fails on warnings
fluid validate contract.fluid.yaml --strict

# Review the module apply would run
fluid generate iac contract.fluid.yaml --provider aws --out ./review

# Generate execution plan
fluid plan contract.fluid.yaml --env dev --out plans/plan-dev.json

# Drift gate: compare the deployed Glue table with the contract
fluid diff contract.fluid.yaml --env dev --exit-on-drift

# Deploy S3 bucket, Glue DB and table, Lake Formation resources
fluid apply contract.fluid.yaml --env dev --yes

# Run the build
fluid apply contract.fluid.yaml --mode amend-and-build

# Check the deployment: Glue columns, Athena row count, governance
fluid verify contract.fluid.yaml --env dev --strict

# Compile advisory IAM bindings from accessPolicy
fluid policy-compile contract.fluid.yaml --env dev --out runtime/policy/bindings.json

# Generate Airflow DAG
fluid generate-airflow contract.fluid.yaml --output airflow-dags/bitcoin_aws.py

# Export standards
fluid odps export contract.fluid.yaml --out standards/product.odps.json --format json
fluid odcs export contract.fluid.yaml --output standards/product.odcs.yaml
```

`fluid diff` reads the Glue table in the region `fluid apply` uses and compares its columns and types with the contract. Since `0.18.1` its live check resolves `{{ env.* }}` placeholders in the binding before it reads the target.

`fluid diff` and `fluid verify` read AWS through boto3; install it with `pip install 'data-product-forge[aws]'`. Builds that land data with DuckDB need the `local` extra (`duckdb>=1.5.0`).

## Where a build lands data

A `pattern: acquisition` build with `engine: duckdb` that reads one stream (`source.streams` lists one stream or none) writes to the destination of the expose its `outputs` list names. The first rule that matches decides. For a file format the build writes a file under the prefix; a table-format sink keeps the URI unchanged:

| The expose's binding | The build writes |
|----------------------|------------------|
| A BigQuery table | A staging file, then a load job (see the [GCP provider](./gcp.md)) |
| `platform: aws`, `location.bucket` and `location.path` | `s3://<bucket>/<path>/<location.table>.<ext>`, or `<stream>.<ext>` when `location.table` is not set |
| `location.path` alone | The path, relative to the contract directory (an absolute path must lie inside the [sandbox's allowed directories](../advanced/duckdb-sandbox.md)) |
| No `location.path` | `out/<stream>.<ext>` under the contract directory |

The path is bucket-relative and always treated as a prefix, with or without a trailing slash, and it is the same prefix the Glue table's `location` uses, so the data and the catalog agree. A `path` that is already a full `s3://` URI is used as written. The extension follows `sink.format` (`parquet`, `csv`, or `ndjson` for `json`), and the credentials come from the ambient AWS credential chain, signed for the binding's `location.region`.

These rules apply to a build that reads one stream (`source.streams` lists one stream or none). A build with several streams writes each to `out/<stream>.<ext>`.

The bucket value has to resolve when the build runs. A `{{ env.S3_BUCKET }}` that is unset leaves the acquisition runner with no bucket to compose a URI from, and it writes `location.path` under the contract directory instead of failing. An embedded-SQL build refuses an unset bucket variable.

An embedded-SQL build (`engine: sql`) lands its result the same way when the first expose is an S3 binding: in `s3://<bucket>/<path>/<location.table or exposeId>.<ext>`, inside the Glue table's location. It writes `parquet`, `csv` or `json`, and refuses another format on an S3 binding.

Contract SQL on the DuckDB engine can read and write only the contract's own directory and the locations the contract declares. For S3 that means the declared `s3://` locations: an `s3://` URL in SQL that the contract does not declare is refused, and `http(s)://`, `gs://` and Azure URLs cannot be read from contract SQL at all. Land remote data with an acquisition build first. The rules are in [DuckDB sandbox for contract SQL](../advanced/duckdb-sandbox.md); `$ref` composition is confined the same way, see [Contract references](../concepts/contract-refs.md).

For acquisition build properties, see [Source-aligned acquisition](../advanced/source-aligned-acquisition.md); the same landing rules are in [where the build lands data](../advanced/source-aligned-acquisition.md#where-the-build-lands-data).

## Credentials setup

### Jenkins CI (recommended)

Create a Jenkins **Secret File** credential containing your AWS env vars:

```bash
# File contents (plain key=value, no 'export' prefix)
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=eu-central-1
AWS_ACCOUNT_ID=123456789012
S3_BUCKET=my-fluid-data-bucket
```

The [Universal Pipeline](../walkthrough/universal-pipeline.md) auto-detects this format and sources it into the pipeline's stages. No provider-specific credential logic.

### Local development

```bash
# Option 1: AWS CLI profile
aws configure --profile fluid-dev

# Option 2: .env file (same format as Jenkins)
cat > .env << 'EOF'
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=eu-central-1
AWS_ACCOUNT_ID=123456789012
S3_BUCKET=my-fluid-data-bucket
EOF

# Source and run
set -a; . .env; set +a
fluid apply contract.fluid.yaml --env dev --yes
```

### Local testing against emulators (LocalStack / moto / MinIO)

::: tip Available in `0.11.0`; extended to builds in `0.16.5`
When a **custom AWS endpoint** is set, the AWS IaC emitter adds an emulator-compatible
`provider "aws"` block so `fluid apply` (and `fluid generate iac`) run against
[LocalStack](https://www.localstack.cloud/) or moto instead of real AWS. Since `0.16.5` the same
variables point DuckDB's S3 access at the emulator, so builds read and write it too.
:::

Set the standard AWS SDK endpoint override — global or per-service:

```bash
export AWS_ENDPOINT_URL=http://localhost:4566        # global (LocalStack default port)
# …or per-service:
export AWS_ENDPOINT_URL_S3=http://localhost:4566
export AWS_ENDPOINT_URL_GLUE=http://localhost:4566

# LocalStack accepts any non-empty test credentials
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_REGION=us-east-1

fluid generate iac contract.fluid.yaml --provider aws --out ./review
tofu -chdir=./review init && tofu -chdir=./review apply
```

When `AWS_ENDPOINT_URL*` is set, the emitted module includes:

| Provider setting | Why emulators need it |
|---|---|
| `s3_use_path_style = true` | Emulators serve buckets as `host/bucket`, not `bucket.host` virtual-host style. |
| `skip_credentials_validation` / `skip_requesting_account_id` | No real STS to call. |
| `skip_metadata_api_check` | No EC2 instance-metadata endpoint. |
| `skip_region_validation` | Emulators accept any region string. |

On **real AWS** (no `AWS_ENDPOINT_URL*` set) the provider block holds only the region, and only when the [bindings pin one](#region). The provider reads credentials from the standard credential chain.

For DuckDB builds:

- `AWS_ENDPOINT_URL_S3` is used first, then `AWS_ENDPOINT_URL`. A value that is not an `http(s)://` URL naming a host, or that carries a user name or password, is ignored with a warning, and the build then reaches AWS itself.
- The store is addressed path-style unless its host ends in `.amazonaws.com`.
- `AWS_IGNORE_CONFIGURED_ENDPOINT_URLS=true` turns the override off.
- With an override set, a DuckDB `CREATE SECRET` that fails (for example because the `aws` extension cannot load) fails the run with `ObjectStoreEndpointError`. Without that, the build would read and write real AWS while the infrastructure was in the emulator. Make the DuckDB `httpfs` and `aws` extensions loadable, or unset the variable.

## Governance on AWS

[Governance parity](../concepts/governance-parity.md) sets these fields beside their GCP equivalents.

| Contract field | What `fluid apply` writes on AWS | What `fluid verify` checks | Schema |
|----------------|----------------------------------|----------------------------|--------|
| `binding.governance.lakeFormation.grants` | `aws_lakeformation_permissions`, one per grant | Not checked on their own; see the column-restrictions check | `0.7.5` |
| `exposes[].policy.authz.columnRestrictions` | Excluded columns on each read grant | No principal reaches a restricted column through Lake Formation | `0.7.5` |
| `binding.governance.lakeFormation.rowFilter` | `aws_lakeformation_data_cells_filter` | Not checked | `0.7.5` |
| `binding.governance.lakeFormation.bucketPolicy` | Which grantees get an S3 bucket-policy statement | Not checked | `0.7.6` |
| `exposes[].lifecycle {retention, expire: true}` | An S3 lifecycle rule on the binding's prefix | The enabled rule and its days | `0.7.6` |
| `binding.encryption.kms` | SSE-KMS as the bucket default, and the key for `product` | The key is `Enabled`, and the objects use it | `0.7.6` |
| `binding.principals` | Maps logical principals to IAM ARNs | Used by the checks above | `0.7.6` |
| `policy.privacy.masking` | Nothing: the DuckDB runner treats the values at landing | Landed values have the strategy's shape | `0.7.5` |
| `accessPolicy.grants` | Nothing | Not checked | `0.7.5` |
| `policy.privacy.rowLevelPolicy` | Nothing | Not checked | `0.7.5` |

Forge emits no platform-native dynamic data masking on AWS. `policy.privacy.rowLevelPolicy` is a declaration the AWS emitter does not read; use `lakeFormation.rowFilter` for row-level filtering.

A policy the binding cannot apply is refused rather than dropped: `fluid validate`, `fluid generate iac` and `fluid apply` refuse a column restriction on an aws binding that has no Lake Formation grants or no Glue table.

### Lake Formation

On AWS, access and row- and column-level governance are implemented through **Lake Formation**, declared under `binding.governance.lakeFormation` (with account-level admins and tag definitions under the top-level `governance.lakeFormation` block). On the OpenTofu apply path Forge emits:

| Contract field | AWS resource emitted |
|----------------|----------------------|
| `governance.lakeFormation.admins` | `aws_lakeformation_data_lake_settings` |
| `governance.lakeFormation.tagDefinitions` | `aws_lakeformation_lf_tag` |
| `binding.governance.lakeFormation.registerLocation` | `aws_lakeformation_resource` |
| `binding.governance.lakeFormation.grants` | `aws_lakeformation_permissions` (column-limited grants use `table_with_columns`) |
| `binding.governance.lakeFormation.bucketPolicy` | Controls the `aws_s3_bucket_policy` written beside the grants *(0.7.6)* |
| `binding.governance.lakeFormation.tags` | `aws_lakeformation_resource_lf_tags` (TBAC) |
| `binding.governance.lakeFormation.rowFilter` | `aws_lakeformation_data_cells_filter` (row filter and optional column projection) |

The grants are on the Glue table, or on the database when the binding names no `location.table`. A grant's `principal` is an IAM principal ARN.

```yaml
exposes:
  - exposeId: bitcoin_prices_table
    binding:
      platform: aws
      format: parquet
      governance:
        lakeFormation:
          registerLocation: true
          grants:
            - principal: "arn:aws:iam::123456789012:role/data-analyst"
              permissions: [SELECT]
              columns: [price_timestamp, price_usd]   # column-limited grant
          rowFilter:
            name: recent_only
            rowExpression: "price_usd > 0"
```

`rowFilter` takes a `name` and a `rowExpression`, both required. `expression` is not a field and fails validation. Optional `columnNames`, `excludedColumnNames` or `allColumns` set which columns the filter shows; with none of them every column is visible.

::: warning The row filter is not granted to anyone
As of 0.18.1, Forge writes the data cells filter and no grant on it: `grants[]` entries are grants on the table, and a table-level `SELECT` reads every row. A principal reads through the filter only after a grant on the filter that you make outside the contract.
:::

::: warning `governance.lakeFormation.admins` is authoritative
Lake Formation's `PutDataLakeSettings` replaces the account's admin list with the one Forge sends. Any admin you do not list is removed on apply, **including the role or user that runs the apply**, and the Lake Formation grants and registrations that need an admin can then fail.

The resource also clears the settings the contract does not set: the account's default permissions for new databases and tables (the `IAMAllowedPrincipals` defaults), trusted resource owners and parameters. Destroying it empties the admin list.

List every principal that must stay an admin, the CI apply role included.
:::

#### Column-limited grants

A grant limits columns in one of two ways. Both emit `SELECT` only.

```yaml
grants:
  # An allow-list: the principal reads these columns.
  - principal: "arn:aws:iam::123456789012:role/data-analyst"
    permissions: [SELECT]
    columns: [price_timestamp, price_usd]

  # An exclusion list: the principal reads every column except these.
  - principal: "arn:aws:iam::123456789012:role/intern"
    permissions: [SELECT]
    excludedColumns: [market_cap_usd]
```

`columns` becomes `table_with_columns.column_names`. `excludedColumns` becomes `wildcard = true` with `excluded_column_names`; without the wildcard the provider's `tofu plan` fails, which was the module Forge wrote before `0.16.6`.

The emitter refuses these, with the error kind `lakeformation-grant-columns`:

| What the grant does | Why it is refused |
|---------------------|-------------------|
| Names both `columns` and `excludedColumns` | Lake Formation takes a column list or a wildcard, not both. |
| Names a column the expose's `contract.schema` does not declare | A misspelt `excludedColumns` entry would leave the real column readable. |
| Excludes every column | The grant would give nothing to read. |
| Limits columns on a binding with no `location.table` | The grant would be on the database and the limit would be dropped. |
| Asks for `ALTER`, `DROP`, `DELETE`, `INSERT` or `ALL` beside a column limit, or has no `SELECT` | Lake Formation takes only `SELECT` on a column-limited grant and refuses the others beside a partial `SELECT`. `DESCRIBE` is dropped, because Lake Formation implies it with the `SELECT`. |
| Gives the principal a second grant on the table beside a column-limited grant | Lake Formation refuses `DESCRIBE`, `ALTER`, `DROP`, `DELETE` and `INSERT` to a principal holding a partial `SELECT`, and a table-level `SELECT` would read the withheld columns. |
| Puts `SELECT` in `permissionsWithGrantOption` beside `excludedColumns` | Lake Formation takes the grant option on a column-limited `SELECT` only with an allow-list. |
| Puts `DESCRIBE` in `permissionsWithGrantOption` beside a column limit | Lake Formation will not grant `DESCRIBE` to a principal holding a partial `SELECT`, so no grant can carry its grant option. |

These refusals come from `fluid generate iac` and `fluid apply`. As of 0.18.1, `fluid validate` does not run them, so a contract with a misspelt `excludedColumns` entry passes `fluid validate --strict` and fails when the module is emitted:

```text
CLI command error
❌ unsupported_binding  [ERR_UNSUPPORTED_BINDING]
  kind: lakeformation-grant-columns
  error: governance.lakeFormation.grants[1] names the columns ['market_cap'],
which the expose's contract.schema does not declare, so the Glue table has no
such column. A misspelt excludedColumns entry would leave the real column
readable.
```

Review with `tofu plan`, not only `tofu validate`. `tofu validate` accepts an `excluded_column_names` block that `tofu plan` rejects, because the table name is not known until plan time.

#### Column restrictions

`policy.authz.columnRestrictions` is the cloud-neutral way to say who may not read which columns. On AWS each Lake Formation `SELECT` or `ALL` grant excludes the restricted columns its principal may not read. The example at the top of the page produces, for the `intern` grant:

```json
"table_with_columns": [
  {
    "excluded_column_names": ["market_cap_usd", "volume_24h_usd"],
    "wildcard": true
  }
]
```

and a plain table grant for `data-analyst`. The rules:

- `deny` hides the columns from the principal. `allow` makes the columns readable only by the principals an `allow` names. A deny beats an allow.
- A restriction never grants access. The readers are the principals with a Lake Formation `SELECT` or `ALL` grant on the binding. An allowed principal with no read grant is logged, not added.
- A restriction needs Lake Formation grants. On an aws binding with none, `fluid validate`, `fluid generate iac` and `fluid apply` refuse it, because nothing would enforce it:

  ```text
   1. exposes.policy.authz.columnRestrictions restricts columns, but this aws
  binding declares no governance.lakeFormation.grants, the only column-level
  control the AWS emitter writes. Nothing would enforce the restriction. Add
  governance.lakeFormation to the aws overlay's binding: registerLocation: true
  and a grant for each reader; forge-cli then writes the restricted columns into
  each grant's excluded columns.
  ```

  The same error kind, `column-restriction-unenforceable`, covers a binding whose format has no Glue table. As of 0.18.1, `fluid plan` writes a plan for a contract whose aws binding has no Lake Formation grants without an error; the refusal comes at validate, generate and apply.
- A grant that already carries `excludedColumns` must agree with the restrictions, or the emit is refused with `column-restriction-conflict`. A grant's hand-written `columns` must not include a restricted column the principal may not read. Either way, remove the hand-written list and let the restrictions write it.
- A restriction on a column the schema does not declare is refused, and so is one that leaves a read grant with no column to read (`lakeformation-grant-columns`).
- A restriction's principal must be an IAM principal ARN. A logical principal such as `role:intern` fails validation unless [`binding.principals`](#logical-principals-and-binding-principals) maps it:

  ```text
  exposes.policy.authz.columnRestrictions: principal 'role:intern' resolves to
  'role:intern', which is not an IAM principal ARN
  (arn:aws:iam::<account>:role/<name> or :user/<name>). Map it in
  binding.principals to the IAM role or user ARN it stands for.
  ```

A table that still grants `IAM_ALLOWED_PRINCIPALS`, which Lake Formation's default settings give new tables, lets any IAM principal with S3 access read every column whatever the grants say. `fluid verify` holds `IAM_ALLOWED_PRINCIPALS` to every restricted column and fails when it can read one; see [Verify on AWS](#verify-on-aws).

#### Logical principals and `binding.principals`

*0.7.6.* The base contract can name principals as the business knows them, and each environment's binding maps them to the IAM identities they are on that cloud:

```yaml
fluidVersion: "0.7.6"
exposes:
  - exposeId: bitcoin_prices_table
    binding:
      platform: aws
      principals:
        group:analysts@example.com: "arn:aws:iam::123456789012:role/data-analyst"
        group:interns@example.com: "arn:aws:iam::123456789012:role/intern"
    policy:
      authz:
        columnRestrictions:
          - principal: group:interns@example.com
            columns: [market_cap_usd, volume_24h_usd]
            access: deny
```

A value is one ARN, a list of them, or `[]` for no identity on this cloud. With `binding.principals` present, every principal the contract names in `accessPolicy.grants` and `columnRestrictions` for the expose must be mapped; an unmapped one is refused. `lakeFormation.grants[].principal` stays an ARN.

#### Bucket policy

*0.7.6.* A grant with an `arn:` principal can also get a statement in an `aws_s3_bucket_policy` (`s3:ListBucket` and `s3:GetBucketLocation` on the bucket, `s3:GetObject` under `location.path`). That statement lets the principal read the objects straight from S3, which skips Lake Formation's column filters, row filters and revocations. `bucketPolicy` chooses who gets one:

```yaml
governance:
  lakeFormation:
    registerLocation: true
    bucketPolicy: none
```

| `bucketPolicy` | Statements for |
|----------------|----------------|
| `cross-account` (the default) | Only grantees whose ARN names an AWS account other than the one running the apply. Decided at plan time against the caller's identity. Same-account grantees get no statement; on a registered location they read through Lake Formation. |
| `none` | No bucket policy. Use it when the location is registered and every reader goes through a Lake Formation integrated engine. |
| `all-grantees` | Every `arn:` grantee, same-account ones included. Reopens the direct S3 read path. |

The emitted bucket policy is **authoritative**: it replaces every other statement on the bucket. When no grantee is left in `cross-account` mode, the resource gets a plan-time `count` of zero, so the bucket's own policy is untouched. Two exposes with grants on one bucket must use the same `bucketPolicy` value, and their statements are merged into the bucket's one policy.

`bucketPolicy` exists only in schema `0.7.6`. A `0.7.5` contract gets the `cross-account` behaviour and cannot opt back.

::: warning Upgrading from before 0.16.3
Grants used to put every grantee, same-account ones included, into the bucket policy. The default is now `cross-account`, so a same-account principal that read the objects directly from S3 (not through Athena or another Lake Formation engine) loses that access on the next apply. Set `bucketPolicy: all-grantees` under `fluidVersion: "0.7.6"` to restore the old policy.
:::

### Masking at landing

`policy.privacy.masking` is applied by the DuckDB acquisition runner, inside the `COPY` and after the quality gates, so the S3 object and the dead-letter queue hold treated values, not cleartext. It is not applied by other engines (a `python` build, for example), and no AWS resource is emitted for it.

```yaml
exposes:
  - exposeId: subscribers
    policy:
      privacy:
        masking:
          - column: msisdn
            strategy: hash
    contract:
      schema:
        - name: msisdn
          type: string
```

| Strategy | What lands | Secret, from the environment |
|----------|------------|------------------------------|
| `hash` | 64 lowercase hex characters: SHA-256 of salt and value | `params.saltEnv` names the variable; default `FLUID_PII_HASH_SECRET`, at least 16 bytes |
| `mask` | The value with every character but the first `keepFirst` (default 0) and last `keepLast` (default 4) replaced by `*` | None |
| `tokenize` | 32 lowercase hex characters: HMAC-SHA256 of the value | `params.keyEnv`; default `FLUID_PII_TOKENIZATION_KEY`, at least 32 bytes |
| `encrypt` | `aesgcm:v1:` and the base64url ciphertext (AES-GCM) | `params.keyEnv`; default `FLUID_PII_ENCRYPTION_SECRET_KEY`, the base64 of 16, 24 or 32 bytes |

The build is refused, before any rows move, for `k_anonymity` (a property of a whole table, not of one value), for parameters the strategy does not take, for a literal `salt` or `key` in `params`, for an unset or too-short secret, and for a column whose declared type is not a string, because a treated column always lands as a string. Set the secret in the environment that runs the build, never in the contract. Quality gates run on the source values, before the rewrite.

`fluid verify` fails (CRITICAL) a masked column whose landed values lack the strategy's shape, so a table that declares masking but holds cleartext in that column, loaded by a `python` build or by hand, fails the check. See [Verify on AWS](#verify-on-aws). For the strategies in full, see [masking at landing](../advanced/source-aligned-acquisition.md#masking-at-landing) and [tag PII](../recipes/tag-pii.md). What the platform enforces across clouds is on [Governance](../advanced/governance.md#what-the-platform-enforces).

### Encryption at rest and retention

*0.7.6.* Both fields need `fluidVersion: "0.7.6"` and apply to a bucket this product owns.

```yaml
fluidVersion: "0.7.6"
exposes:
  - exposeId: bitcoin_prices_table
    lifecycle:
      retention: P90D
      expire: true
    binding:
      platform: aws
      format: parquet
      location:
        database: crypto_data
        table: bitcoin_prices
        bucket: "{{ env.S3_BUCKET }}"
        path: data/bitcoin/prices/
        region: eu-west-1
      encryption:
        kms: product
```

Added to the example's module: `aws_kms_key`, `aws_kms_alias`, `aws_s3_bucket_server_side_encryption_configuration` and `aws_s3_bucket_lifecycle_configuration`.

**Encryption.** `binding.encryption.kms` takes:

| Value | Result |
|-------|--------|
| `product` (the default when the block is present) | A customer managed key for each bucket this product owns, with rotation on, the alias `alias/fluid/<contract id>/<bucket>` and a seven-day deletion window, as the bucket's default SSE-KMS with an S3 Bucket Key. |
| `alias/<name>`, or a key or alias ARN | An existing key. It is looked up at plan time, so the applying identity needs `kms:DescribeKey` on it, and the plan fails unless the key is `Enabled` and a symmetric encryption key. With `registerLocation` it must be customer managed: `alias/aws/s3` is refused. |
| `none` | Nothing is emitted; S3 uses its default SSE-S3. |

The key policy of a `product` key lets the account's IAM policies decide who uses it. When the binding has `governance.lakeFormation`, it also lets the Lake Formation service-linked role use the key, so a principal querying through Athena with credentials Lake Formation vends needs no KMS permission of its own. A grantee that the bucket policy lets read objects directly gets `kms:Decrypt`, through S3 only. The identity that writes the data needs `kms:GenerateDataKey` and `kms:Decrypt` from IAM. A key on a shared (pool) bucket is the pool owner's: `product` is refused there, and a named key is only checked.

::: warning Dropping `encryption` keeps the data under a key that is deleted
Removing the block, or naming another key, removes the product key while the bucket keeps the objects encrypted with it. They become unreadable when the seven-day deletion window ends, unless you rewrite them or cancel the deletion (`kms:CancelKeyDeletion`). `fluid apply` refuses that plan without `--allow-data-loss`.
:::

**Retention.** `lifecycle.retention` is an ISO-8601 duration. It stays a declaration until `expire: true` turns it into a rule:

- One rule per expose in the bucket's lifecycle configuration, filtered to the binding's prefix (`location.path`, else `<database>/<table>/`). A binding with neither is refused, so no rule expires a whole bucket.
- It expires current objects `retention` after they are written. Years count as 365 days and months as 30; a part of a day rounds up to a whole one.
- It removes a noncurrent version one day after it stops being current and aborts an incomplete multipart upload after seven days, or after the retention period if that is shorter.
- A rule for `fluid verify`'s own result prefix, `.fluid/athena-results/`, is added at the shortest retention declared on the bucket.
- Two exposes whose prefixes contain each other, with different schedules, are refused (`retention-overlap`).

The lifecycle configuration is **authoritative for the whole bucket**: S3 keeps one, so rules Forge did not write are replaced. Forge therefore writes it only on a bucket the product owns. On a shared pool bucket nothing is written, the pool's owner holds the rule, and `fluid verify` checks it. An existing bucket's rules and default encryption are imported with the bucket, so the plan shows them changing in place.

Removing `expire`, or the key, removes a resource that holds policy. `fluid apply` refuses that plan without `--allow-data-loss`; removing a Lake Formation grant is a revocation and is not gated.

`exposes[].lifecycle.retention` is separate from the top-level `retention:` block that sweeps run state and logs; see [`fluid retention`](../cli/retention.md).

### accessPolicy on AWS

`accessPolicy.grants` is the cloud-neutral statement of who may read. It is a top-level block of the contract, not a field of an expose; under `exposes[]` it is a schema error. The AWS emitter does not write it: on AWS, access is the binding's `governance.lakeFormation.grants`. A contract with `accessPolicy.grants` and an aws binding that has no Lake Formation grants gets a validate warning, and `--strict` turns it into exit 1:

```text
⚠️  1 warning(s)

Validation Warnings:
====================
 1. accessPolicy.grants are not enforced on aws binding(s) bitcoin_prices_table:
the AWS emitter does not write accessPolicy, and these bindings declare no
governance.lakeFormation.grants, the AWS form of who may read the table. Add
them to the aws overlay's binding (column restrictions then narrow them).
```

A pipeline that runs `fluid validate --strict` fails on it; stage 2 of the [11-stage pipeline](../walkthrough/11-stage-pipeline.md) does. Without `--strict` it is a warning. Add `lakeFormation` grants to the aws binding, for example in the aws overlay of a contract that also targets GCP (see [per-environment overlays](../recipes/per-environment-overlays.md)). The warning is raised only when no grant exists; a binding with Lake Formation grants does not trigger it.

`fluid policy-compile` still reads `accessPolicy.grants` and writes IAM bindings, which you can use as a starting point for IAM policies. Nothing applies them:

```bash
fluid policy-compile contract.fluid.yaml --out runtime/policy/bindings.json
```

```json
{
  "bindings": [
    {
      "provider": "aws",
      "resource_type": "s3.bucket",
      "resource_id": "{{ env.S3_BUCKET }}",
      "bucket": "{{ env.S3_BUCKET }}",
      "region": "eu-west-1",
      "principal": "role:data-analyst",
      "actions": ["s3:GetObject", "s3:ListBucket"]
    },
    {
      "provider": "aws",
      "resource_type": "glue.table",
      "resource_id": "crypto_data.bitcoin_prices",
      "database": "crypto_data",
      "table": "bitcoin_prices",
      "region": "eu-west-1",
      "principal": "role:data-analyst",
      "actions": [
        "glue:GetTable",
        "glue:GetDatabase",
        "athena:StartQueryExecution",
        "athena:GetQueryResults"
      ]
    },
    ...
  ],
  "warnings": []
}
```

Each principal gets one entry for the bucket and one for the Glue table. The permissions map to two action sets: any of `write`, `insert`, `update` or `delete` selects the write set (`s3:PutObject`, `s3:DeleteObject`, `s3:GetObject`, `s3:ListBucket`, and `glue:CreateTable`, `glue:UpdateTable`, `glue:DeleteTable`); every other permission selects the read set shown above. Placeholders in the bucket stay literal, and the principals are written as the contract names them.

`fluid policy-apply` enforces nothing on AWS. As of 0.18.1 the aws provider has no standalone policy applier, and the command exits 0:

```console
$ fluid policy-apply runtime/policy/bindings.json --mode enforce
...
⚠️  No policy bindings were enforced — the 'aws' provider has no standalone
policy applier. For cloud providers, IAM/GRANT, masking and row-access policies
are emitted and applied during `fluid apply` (stage 7), so `fluid policy-apply`
is a no-op for this provider.
```

### Data Sovereignty

The `sovereignty` block enforces region restrictions **before** any infrastructure is deployed:

```yaml
sovereignty:
  jurisdiction: "EU"
  dataResidency: true        # a boolean — "must this data stay in the jurisdiction?"
  allowedRegions: [eu-central-1, eu-west-1]
  deniedRegions: [us-east-1, us-west-2]
  crossBorderTransfer: false
  regulatoryFramework: [GDPR]
  enforcementMode: advisory  # or strict (blocks deployment)
```

#### Which key holds what (since 0.15.0)

| Key | Type | What AWS does with it |
|-----|------|-----------------------|
| `allowedRegions` | list of regions | The residency allow-list. A binding region outside it is refused *(since 0.15.0 — this is the key the list is read from)* |
| `deniedRegions` | list of regions | Refused outright, and deny beats allow *(since 0.15.0 — it was never consulted before)* |
| `dataResidency` | boolean | "Must this data stay inside the declared jurisdiction?" It is **not** a region list, and it does not gate `allowedRegions` |
| `jurisdiction` | e.g. `EU`, `UK`, `US` | Checked against the jurisdiction the binding region resolves to |
| `enforcementMode` | `strict` / `advisory` / `audit` | Decides the severity a violation carries — see [Sovereignty enforcement modes](../advanced/governance.md#sovereignty-enforcement-modes-since-0-15-0) |

::: warning Newly blocking in `0.15.0`
The AWS util read the region allow-list *out of* `dataResidency`, which every
bundled schema from `0.7.1` to `0.7.6` types as a **boolean**. So
`dataResidency: true` — the schema default — raised `TypeError: argument of type 'bool' is not a container or
iterable`, while `dataResidency: false` skipped the check in silence. The strict
setting was the one that broke and the permissive one was the one that worked,
which is exactly backwards for a governance control.

**An AWS contract binding outside its own `allowedRegions` now exits 1, where the
module was previously written to disk with exit 0.** A contract declaring
`allowedRegions: [eu-west-1]` and binding to `eu-south-1` is the measured case.
`allowedRegions` is enforced whatever `dataResidency` says, deliberately: gating it
on the boolean would make the AWS provider quietly more permissive than the
`fluid validate` stage before it, and an omitted key reads as falsy in Python, so
"unspecified" would have meant "opt out" for the field whose schema default is the
strict setting.

Two non-schema shapes that exist in the wild — a list under `dataResidency`, and
the dict `fluid import` used to emit — are still read as a fallback **only when
`allowedRegions` is absent**, with a warning naming the right key. They are never
merged into a present `allowedRegions`: every region an invalid key could
contribute is by construction one the valid allow-list deliberately excluded.
:::

`fluid generate iac` also stopped writing a module after the provider refused the
contract *(since 0.15.0)*. The native planner ran inside a best-effort
`except Exception` that logged at DEBUG and returned no actions, and that check is
the only place AWS enforces jurisdiction and residency — so a contract bound outside
its declared jurisdiction logged the violation and then emitted `main.tf.json`
anyway, exit 0. An EU-jurisdiction contract bound to `us-east-1` now exits 1 and
writes no module. The provider's handler also caught only the jurisdiction error and
not its residency sibling, so every residency refusal skipped the
`sovereignty_violation` audit event — the one refusal an operator most needs in the
log was the one missing from it.

#### Sovereignty tags

`fluid:data_jurisdiction`, `fluid:data_residency` and `fluid:allowed_regions` are
attached to the emitted resources. Get them wrong and detective controls downstream
go with them — an AWS Config rule or a tag-based SCP keys on exactly these tags. The
same `dataResidency` confusion reached them: joining the boolean raised, and joining
the dict shape emitted its **keys**, so one tag read
`fluid:allowed_regions = "allowedRegions"`. Fixed in `0.15.0`; `fluid:data_residency`
now reads `enforced` or `regions-pinned`, and an omitted `dataResidency` tags as the
schema says it behaves (`default: true`).

#### Region → jurisdiction *(since 0.15.0)*

AWS regions now resolve through botocore's shipped `endpoints.json` — the partitions
it lists, GovCloud and the EU Sovereign Cloud (`eusc-de-east-1`) included — instead
of a hand-kept table, so a new AWS region arrives by upgrading `boto3` rather than by
waiting for a FLUID release. **Verdicts change on contracts nobody edited:**
`eu-west-2` (London) resolves to `UK` rather than `EU`, and `ap-southeast-1`
(Singapore) and `ap-northeast-2` (Seoul) resolve to `SG` and `KR` rather than a
pass-anything `Global`. An EU-pinned contract bound to any of the three passed
`0.14.1` silently and now fails; a `UK`-pinned contract bound to `eu-west-2` stops
being a false positive. The AWS provider had kept a second table that disagreed with
the canonical engine and now delegates to the one table — full detail in
[Sovereignty enforcement modes](../advanced/governance.md#sovereignty-enforcement-modes-since-0-15-0),
under "The region → jurisdiction table is derived".

## Verify on AWS

The checks, the Athena flags, the result-location order and the IAM list are in [`fluid verify`](../cli/verify.md#s3-and-glue-athena). `fluid verify` checks a binding with `platform: aws`, a `format` Athena can read through a Hive SerDe (`parquet`, as of 0.18.1), and `location.database`, `location.table` and `location.bucket`. It runs in the binding's region and checks the live account against the contract. Another binding is reported as having no verifier, which never fails the run.

```bash
fluid verify contract.fluid.yaml --env dev --strict --out runtime/verify-report.json
```

| Check | How | When it fails |
|-------|-----|---------------|
| The table exists | `glue:GetTable` | Error, exit 1. In a reference-only contract (a build with `pattern: reference`, `hybrid-reference` or `external-reference`) it is INFO. |
| Columns match | Glue columns and partition keys against `contract.schema` | A missing column or a changed type is CRITICAL; an extra column is INFO. |
| The table reads the binding's prefix | Glue `StorageDescriptor.Location` against `s3://<bucket>/<path>` | CRITICAL |
| Athena can read it | `SELECT COUNT(*)`, polled until it finishes or times out | A failed, cancelled or timed-out query is an error, exit 1. |
| It holds what the build landed | The count against the run records of the acquisition build that writes the expose | CRITICAL, by the rule below. |
| It is not empty | The same count | CRITICAL. INFO in a reference-only contract that has no run of its own to compare with. |
| Masked columns landed treated | For `policy.privacy.masking`: counts of values that lack the strategy's shape; no value leaves the query | One such value is CRITICAL. |
| Retention | For `lifecycle {retention, expire: true}`: `s3:GetLifecycleConfiguration`, the earliest `Expiration.Days` of the enabled rules covering the prefix, against `retention` | No such rule, another number of days, or a rule that expires some objects sooner: CRITICAL. |
| Encryption | For `binding.encryption`: `kms:DescribeKey` must answer `Enabled`, then `s3:HeadObject` on up to 1000 objects under the prefix | A key that is not `Enabled`, or an object that is not `aws:kms` with that key: CRITICAL. No object yet: INFO. |
| Column restrictions | For `columnRestrictions`: `lakeformation:ListPermissions` on tables. No `SELECT` of a read grantee, of a denied principal or of `IAM_ALLOWED_PRINCIPALS` reaches a column it may not read, including grants made outside the contract | CRITICAL. |

CRITICAL fails `--strict`. INFO fails only with `--fail-on-warning`. An error fails the command with or without `--strict`.

The column-restrictions check lists the permissions the caller can see, so **it must run as a Lake Formation administrator**. When the contract's own grants are missing from the listing, it reports an error, not a pass, because a partial listing cannot be trusted.

**Which run the count is held to.** A build writes a run record under `.fluid/runs/<contract id>/<build id>/runs/<run id>.json` in the contract directory. A CI pipeline that runs verify in a separate stage must carry that directory over. Verify takes the newest run that landed in this table and compares by the mode that run recorded:

| Recorded mode | Rule |
|---------------|------|
| `full_refresh` | The count equals that run's row count. |
| `incremental_append` | The count is at least the sum of the runs back to and including the last `full_refresh`. |
| Anything else | Reported, never gated: a merge, dedup, CDC or streaming load can update or delete rows. Only an empty table fails. |

**Options.**

| Flag | Env var | Default |
|------|---------|---------|
| `--athena-output-location S3_URI` | `FLUID_ATHENA_OUTPUT_LOCATION` | The workgroup's location, else `s3://<binding bucket>/.fluid/athena-results/` |
| `--athena-workgroup NAME` | `FLUID_ATHENA_WORKGROUP` | `primary` |
| `--athena-timeout SECONDS` | `FLUID_ATHENA_TIMEOUT_SECONDS` | `300` |

The flag wins over the variable. A workgroup that enforces its own output location always wins, and a location inside the table's own prefix is refused. Each run leaves Athena's small result objects at the location used; the lifecycle rule `fluid apply` writes for the default prefix expires them when retention is declared, and otherwise you expire them with a rule of your own.

**IAM the verifying identity needs:**

- `glue:GetTable` and `glue:GetDatabase`, plus `glue:GetPartitions` for a partitioned table.
- `athena:GetWorkGroup` (optional), `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults` and `athena:StopQueryExecution`.
- `s3:GetObject` on the table's prefix, and read and write on the results prefix.
- `s3:ListBucket`, `s3:GetBucketLocation` and `s3:ListBucketMultipartUploads` on the bucket.
- With a registered location: `lakeformation:GetDataAccess` and a Lake Formation `SELECT` grant on the table.
- With declared retention: `s3:GetLifecycleConfiguration`. With a declared key: `kms:DescribeKey`, and `kms:GenerateDataKey` and `kms:Decrypt` on it for the result file.
- For the column check: `lakeformation:ListPermissions`, as a Lake Formation administrator.

## Upgrading an existing AWS contract

The release notes for [`0.16.0`](../RELEASE_NOTES_0.16.0.md) and [`0.17.0`](../RELEASE_NOTES_0.17.0.md) and the [upgrade guide](../upgrading.md) have the full lists.

- **`0.16.2`:** a Parquet Glue table gets Athena's storage classes on re-apply. The module pins the binding's region, and `fluid apply` refuses a move between regions; see [Region](#region).
- **`0.16.3`:** the default `bucketPolicy` no longer gives same-account grantees a direct S3 read; see [Bucket policy](#bucket-policy). `governance.lakeFormation.admins` was always authoritative, and the bundled schemas now say so.
- **`0.16.5`:** DuckDB builds treat masked columns at landing, and `fluid verify` fails a cleartext one. `AWS_ENDPOINT_URL[_S3]` reaches DuckDB.
- **`0.17.0`:** a column restriction on an aws binding with no Lake Formation grants is refused, and `accessPolicy.grants` on an aws binding with no Lake Formation grants warns; see [Column restrictions](#column-restrictions) and [accessPolicy on AWS](#accesspolicy-on-aws).
- **`0.18.0`:** contract SQL runs in a DuckDB sandbox and `$ref` stays inside the contract's directory tree; see [Where a build lands data](#where-a-build-lands-data).

## How far this has been exercised

The forge-cli release notes record how each part was checked. The `parquet` SerDe fix was measured against a real AWS account, as was landing a build's rows in S3 through the Glue table (`0.16.0`). The region pin and the region-move guard were exercised against an emulator. The `0.16.5` retention, encryption, masking and endpoint changes ran against moto and DuckDB writing to a moto S3 server; moto enforces neither key policies nor Lake Formation.

The column-restriction grants and `fluid verify`'s Lake Formation check were tested against moto's stored grants. A grant of the shape `0.17.0` emits (excluded columns beside `wildcard`) was applied and enforced on a real account from `0.16.6`, written by hand in the overlay. What is not proven is the Lake Formation half against a real account as `0.17.0` derives it from `columnRestrictions`. Confirm that behaviour on your own account with `fluid verify` before you rely on it. The GCP half was measured against real Google Cloud on 4 October 2026; see [Governance parity](../concepts/governance-parity.md#what-has-been-proven).

## CI/CD pipeline

The AWS example uses the same Jenkinsfile as GCP and Snowflake, the [Universal Pipeline](../walkthrough/universal-pipeline.md). The stages that touch AWS:

| Stage | Command | What happens on AWS |
|-------|---------|---------------------|
| 2 Validate | `fluid validate --strict` | Contract checked against the bundled schema; an aws binding with `accessPolicy` and no Lake Formation grants is a warning, so `--strict` fails |
| 3 Generate artifacts | `fluid generate artifacts` | Writes `policy/bindings.json`, which is advisory on AWS |
| 5 Drift gate | `fluid diff --env aws --exit-on-drift` | Compares the deployed Glue table's columns with the contract |
| 6 Plan | `fluid plan` | Execution plan generated |
| 7 Apply | `fluid apply` | S3 bucket, Glue database and table, Lake Formation, KMS and lifecycle resources; with `--mode amend-and-build`, the build then runs and writes its output to S3 |
| 8 Policy apply | `fluid policy-apply` | No-op on AWS; exits 0 |
| 9 Verify | `fluid verify --env aws --strict` | Glue columns, Athena count, masking, retention, encryption, column restrictions |
| Orchestration | `fluid generate-airflow` | Production DAG generated |

See the [11-stage pipeline](../walkthrough/11-stage-pipeline.md) for what each stage does.

## See also

- [Universal Pipeline](../walkthrough/universal-pipeline.md) — The Jenkinsfile the providers share
- [Snowflake Provider](./snowflake.md) — Snowflake Data Cloud integration
- [GCP Provider](./gcp.md) — Google Cloud Platform integration
- [Governance parity](../concepts/governance-parity.md) — one contract, AWS and GCP
- [One contract, two clouds](../recipes/one-contract-two-clouds.md) — deploy the same product to both
- [`fluid verify`](../cli/verify.md) and [`fluid apply`](../cli/apply.md) — Command reference
- [DuckDB sandbox for contract SQL](../advanced/duckdb-sandbox.md) — What a build's SQL can read
- [CLI Reference](../cli/README.md) — Full command documentation
