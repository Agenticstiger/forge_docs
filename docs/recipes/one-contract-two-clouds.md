---
title: One contract, two clouds
description: Deploy one data product contract to AWS and to GCP with --env overlays, governed the same on both. Runnable locally up to the cloud apply.
---

# One contract, two clouds

**Time:** 15 min to run locally · **Needs:** CLI 0.18.1 with the `local`,
`aws` and `gcp` extras, `jq` · OpenTofu and cloud credentials only for the apply

You want the same data product on AWS (S3, Glue, Lake Formation) and on GCP
(BigQuery), with the same schema, retention, encryption and column
restrictions on both, and no second copy of the contract to keep in sync.

The pattern: a base contract that binds to `local`, and one overlay per cloud
that patches only `exposes[].binding`. You pick the cloud with `--env aws` or
`--env gcp`. Every command below up to the apply runs offline.

```bash
pip install "data-product-forge[local,aws,gcp]"
```

## 1. Lay out the workspace

```text
acme-analytics/
├── fluid.workspace.yaml
└── customer-events/
    ├── contract.fluid.yaml
    ├── data/events.csv
    └── overlays/
        ├── aws.yaml
        └── gcp.yaml
```

```yaml
# fluid.workspace.yaml
workspace:
  name: acme-analytics
expected-environments:
  customer-events: [aws, gcp]
```

`expected-environments` turns a missing overlay into an error: without it,
`--env gcp` with no `overlays/gcp.yaml` would warn and run the local base as if
it were GCP. See [Workspaces](../concepts/workspaces.md#expected-environments).

```csv
# customer-events/data/events.csv
event_id,customer_id,event_type,revenue_eur
e1,c1,purchase,19.90
e2,c2,view,0
e3,c1,purchase,5.00
```

## 2. Write the base contract

The base holds everything the clouds share, including the governance. It names
principals logically (`group:analysts@acme.example`); each overlay says who
that is on its cloud.

```yaml
# customer-events/contract.fluid.yaml
fluidVersion: "0.7.6"            # lifecycle.expire, encryption and principals are 0.7.6 (preview)
kind: DataProduct
id: analytics.customer_events_v1
name: Customer Events
description: Customer interaction events, one row per event.
domain: Customer
metadata:
  layer: Silver
  productType: ADP
  owner:
    team: customer-platform
    email: customer-platform@acme.example

accessPolicy:
  grants:
    - principal: group:analysts@acme.example
      permissions: [read]
    - principal: group:stewards@acme.example
      permissions: [read]

builds:
  - id: load_events
    pattern: embedded-logic
    engine: sql
    properties:
      sql: >-
        SELECT event_id, customer_id, event_type, revenue_eur
        FROM read_csv('data/events.csv')
    outputs: [customer_events]

exposes:
  - exposeId: customer_events
    kind: table
    lifecycle:
      retention: P30D
      expire: true                 # delete data older than 30 days
    policy:
      authz:
        columnRestrictions:
          - principal: group:analysts@acme.example
            columns: [customer_id]
            access: deny
    binding:
      platform: local
      format: parquet
      location:
        path: output/customer_events.parquet
    contract:
      schema:
        - name: event_id
          type: string
          required: true
        - name: customer_id
          type: string
          required: true
        - name: event_type
          type: string
        - name: revenue_eur
          type: double
```

## 3. Write one overlay per cloud

```yaml
# customer-events/overlays/aws.yaml
exposes:
  - binding:
      platform: aws
      format: parquet
      location:
        bucket: <your-lake-bucket>
        path: silver/customer_events/     # bucket-relative prefix
        database: customer_analytics      # Glue database
        table: customer_events            # Glue table
        region: eu-central-1
      encryption:
        kms: product
      governance:
        lakeFormation:
          grants:                         # who reads, on AWS
            - principal: arn:aws:iam::123456789012:role/analyst
              permissions: [SELECT]
            - principal: arn:aws:iam::123456789012:role/steward
              permissions: [SELECT]
      principals:
        group:analysts@acme.example: arn:aws:iam::123456789012:role/analyst
        group:stewards@acme.example: arn:aws:iam::123456789012:role/steward
```

```yaml
# customer-events/overlays/gcp.yaml
exposes:
  - binding:
      platform: gcp
      format: bigquery_table
      location:
        project: acme-analytics-prod
        dataset: customer_analytics
        table: customer_events
        region: europe-west3
      encryption:
        kms: product
      principals:
        group:analysts@acme.example: group:analysts@<your-domain>
        group:stewards@acme.example: group:data-stewards@<your-domain>
```

Replace `<your-lake-bucket>` with an S3 bucket name you own (bucket names are
global), and `<your-domain>` with the domain of your Google Workspace or Cloud
Identity groups. Left as written, `--env gcp` fails validation, by design: the
identity `group:analysts@<your-domain>` is "not a GCP IAM member", so the
placeholder cannot reach a real access list.

On AWS the column restriction narrows the Lake Formation grants, so the aws
overlay must carry them; without them the restriction is refused
(`column-restriction-unenforceable`). On GCP, the readers come from
`accessPolicy.grants`.

## 4. Run it locally

The base contract builds and verifies on your machine, with no cloud:

```console
$ cd customer-events
$ fluid apply contract.fluid.yaml --mode amend-and-build --yes
...
🔷 Build 'load_events' (embedded-SQL / local DuckDB)
   ✅ Completed in 1.31s — 1 action(s) executed
...
$ fluid verify contract.fluid.yaml
...
   📊 Rows: 3
   🔍 Dimension 1: Schema Structure
      ✅ PASS - All 4 declared columns present
...
```

The local binding does not apply the retention, the key or the column
restriction; those are cloud resources.

## 5. Validate each cloud

These outputs were captured with `<your-domain>` set to `example.com`. Validate
refuses only the reserved top-level domains (`.example`, `.test`, `.invalid`,
`.localhost`), so `example.com` passes; no real group has it.

```console
$ fluid validate contract.fluid.yaml --env aws
overlay_applied
✅ Valid FLUID contract (schema v0.7.6)
Validation completed in 0.002s

$ fluid validate contract.fluid.yaml --env gcp
overlay_applied
✅ Valid FLUID contract (schema v0.7.6)
Validation completed in 0.002s
```

Validate runs the same governance derivation apply uses. Leave the
`principals:` block out of `overlays/gcp.yaml` and the GCP validation fails,
because `acme.example` is a reserved domain no real group has:

```console
$ fluid validate contract.fluid.yaml --env gcp
overlay_applied
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.6)
...
 1. exposes accessPolicy: principal 'group:analysts@acme.example' resolves to 'group:analysts@acme.example', a placeholder: .example is a reserved top-level domain (RFC 2606), so no real identity has it, and BigQuery refuses an access entry for an identity that does not exist. Map the logical principal in this environment's binding.principals to the real group or service account it stands for, ...
```

## 6. See what differs between the clouds

Only the binding differs. Strip it from the resolved contract of each
environment and the rest is identical:

```console
$ for env in aws gcp; do
>   fluid bundle contract.fluid.yaml --env "$env" --format json | jq -S 'del(.exposes[].binding)' | shasum
> done
overlay_applied
46dee60aaaf06d9a312839edf9496b870b8890f5  -
overlay_applied
46dee60aaaf06d9a312839edf9496b870b8890f5  -
```

What each cloud gets is different, and you can read it before anything is
deployed. `fluid generate iac` writes the OpenTofu module `fluid apply` would
apply:

```console
$ fluid generate iac contract.fluid.yaml --env aws --out iac-aws
...
Wrote OpenTofu module: iac-aws/main.tf.json  (provider: aws, 10 resources)
$ fluid generate iac contract.fluid.yaml --env gcp --out iac-gcp
...
Wrote OpenTofu module: iac-gcp/main.tf.json  (provider: gcp, 11 resources)
```

| Contract field | `iac-aws/main.tf.json` | `iac-gcp/main.tf.json` |
|---|---|---|
| the table | `aws_s3_bucket`, `aws_glue_catalog_database`, `aws_glue_catalog_table` | `google_bigquery_dataset`, `google_bigquery_table` |
| `lifecycle {retention: P30D, expire: true}` | `aws_s3_bucket_lifecycle_configuration`: expire after 30 days under `silver/customer_events/` | `time_partitioning {type: DAY, expiration_ms: 2592000000}` on the table |
| `encryption.kms: product` | `aws_kms_key`, `aws_kms_alias` `alias/fluid/analytics_customer_events_v1/<your-lake-bucket>`, `aws_s3_bucket_server_side_encryption_configuration` | `google_kms_key_ring`, `google_kms_crypto_key` `bigquery`, `google_kms_crypto_key_iam_member` |
| `columnRestrictions` (analysts denied `customer_id`) | the analyst's `aws_lakeformation_permissions` with `excluded_column_names: [customer_id]`; the steward's on the whole table | `google_data_catalog_taxonomy`, a `google_data_catalog_policy_tag` on `customer_id`, `categoryFineGrainedReader` for `group:data-stewards@<your-domain>` only |
| `accessPolicy.grants` | not emitted (the Lake Formation grants above) | two `google_bigquery_dataset_iam_member` (`roles/bigquery.dataViewer`) for the mapped groups |

The AWS module also holds a second lifecycle rule, for `.fluid/athena-results/`
where `fluid verify` writes Athena query results, and an `aws_s3_bucket_policy`
with its `aws_iam_policy_document`. The policy's `count` is 1 only when a Lake
Formation grantee's account differs from the account running OpenTofu. The
grantees here use account `123456789012`, so whether the policy is created
depends on your account. GCP adds a `terraform_data` that forces the table's
replacement when its partitioning changes. The full mapping is in
[Governance parity](../concepts/governance-parity.md).

## 7. Plan and apply each cloud

```bash
fluid plan  contract.fluid.yaml --env aws --out runtime/plan-aws.json
fluid plan  contract.fluid.yaml --env gcp --out runtime/plan-gcp.json
```

Each `plan.json` records its environment (`contract_metadata.env`), so
`fluid apply runtime/plan-aws.json` applies the AWS overlay without `--env`.

The apply needs OpenTofu and credentials for that cloud. Keep state in a
bucket, keyed per contract and provider:

```bash
export FLUID_STATE_BACKEND=s3://<your-state-bucket>
fluid apply contract.fluid.yaml --env aws --mode amend-and-build --yes

export FLUID_STATE_BACKEND=gcs://<your-state-bucket>
fluid apply contract.fluid.yaml --env gcp --mode amend-and-build --yes
```

Each apply prints the state it uses. Captured with `--dry-run` and no
credentials (the init then failed, after this line was printed). The bucket name
`acme-tfstate` is illustrative; bucket names are global, so use one you own:

```console
$ FLUID_STATE_BACKEND=gcs://acme-tfstate fluid apply contract.fluid.yaml --env gcp --dry-run
...
OpenTofu engine — provider: gcp
  module:      .fluid/iac/gcp/analytics_customer_events_v1/main.tf.json
  state:       remote: gcs://acme-tfstate/fluid/analytics.customer_events_v1/gcp (from FLUID_STATE_BACKEND)
...
```

The two clouds keep two states (`fluid/<id>/aws/terraform.tfstate` and
`fluid/<id>/gcp`), so one cloud's apply does not read the other cloud's
resources as orphans. If you applied this contract to one cloud before 0.17.0, the first
apply moves its state to the per-provider key and leaves the old object in
place; see [OpenTofu state](../concepts/state.md).

## 8. Verify each cloud

```bash
fluid verify contract.fluid.yaml --env aws --strict
fluid verify contract.fluid.yaml --env gcp --strict
fluid diff   contract.fluid.yaml --env gcp --exit-on-drift
```

On each cloud, `fluid verify` reads the live platform: the schema, the row
count against the build's run records, the retention rule or partition
expiry, the key, and the column restrictions (Lake Formation permissions on
AWS, the policy tag and its fine-grained readers on GCP). It does not check the
dataset grants. On GCP the column check needs `datacatalog.taxonomies.get` and
`datacatalog.taxonomies.getIamPolicy`; on AWS the Lake Formation check must run
as a Lake Formation administrator.

## Things to know

- **Publishing to the Command Center is last writer wins.** The Command Center
  keeps one product per contract id, so `fluid publish --env aws` and then
  `--env gcp` leaves the product showing the GCP platform and location. Publish
  from one environment. In a Jenkinsfile from `fluid generate ci`, the publish
  stage's parameter (`RUN_STAGE_10_PUBLISH`) defaults to off;
  `--publish-stage-default` turns that default on, so leave it off for the
  second cloud.
- **The environment is not part of the state key.** A second GCP environment
  (say `gcp-staging`) with the same `FLUID_STATE_BACKEND` would share the
  `gcp` state. Give it its own bucket.
- **Do not put `$ref` in an overlay.** As of 0.18.1 such an overlay is silently
  ignored by validate and plan. See
  [Environments and overlays](../concepts/environments-and-overlays.md#how-an-overlay-merges).
- **Snowflake and local bindings ignore these governance fields.** A
  `snowflake` overlay validates and emits no retention, key, restriction or
  grant resources.
- **Chained products follow the overlay.** A downstream product's build loads
  its upstream with the same `--env`, so an `--env gcp` build reads the
  upstream's BigQuery table. See
  [Workspaces](../concepts/workspaces.md#how-a-build-finds-the-products-it-consumes).
- **Generated pipelines run one environment each.** `fluid generate ci
  --fluid-env-default gcp` sets the `FLUID_ENV` every stage passes to `--env`.

## Optional: deploy to GCP from AWS without a key file

When the pipeline runs on AWS (for example a Jenkins agent on EC2), it can
deploy to GCP without a service-account key, through GCP Workload Identity
Federation: a workload identity pool with an AWS provider that maps
`attribute.aws_role` from `assertion.arn.extract('assumed-role/{role}/')`, and
a deploy service account that one AWS role may impersonate. The credential file
the pipeline points `GOOGLE_APPLICATION_CREDENTIALS` at is generated with
`gcloud iam workload-identity-pools create-cred-config` and its `--aws` and
`--enable-imdsv2` flags; it holds no secret. forge-cli reads it through
Application Default Credentials like any other. Setup is in Google's guide,
[Configure Workload Identity Federation with AWS](https://cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds).

::: danger Restrict the provider and the binding to one AWS role
Set both of the following. With neither, any role in the AWS account can
impersonate the deploy service account, and that service account holds the KMS
and Data Catalog administration roles listed under
[Prerequisites](../concepts/governance-parity.md#prerequisites).

1. Give the AWS provider an attribute condition that admits only the pipeline's
   role. With the mapping above:

   ```text
   attribute.aws_role == "<jenkins-deploy-role>"
   ```

   Pass it as `--attribute-condition` when you create the provider. A condition
   on the full ARN works too, for example
   `assertion.arn.startsWith("arn:aws:sts::<ACCOUNT_ID>:assumed-role/<jenkins-deploy-role>/")`.
2. Grant `roles/iam.workloadIdentityUser` on the deploy service account to that
   role's principal set only, never to the whole pool:

   ```text
   principalSet://iam.googleapis.com/projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/<POOL>/attribute.aws_role/<jenkins-deploy-role>
   ```

   A binding to `.../workloadIdentityPools/<POOL>/*` admits every identity the
   pool accepts.
:::

## See also

- [Environments and overlays](../concepts/environments-and-overlays.md)
- [Governance parity](../concepts/governance-parity.md)
- [OpenTofu state](../concepts/state.md)
- [Switch clouds by editing only `binding`](./switch-clouds.md) — move a
  contract to another cloud instead of running it on two.
- [Per-environment overlays](./per-environment-overlays.md)
