---
title: Governance parity
description: How retention, encryption at rest, column restrictions and access grants declared once in a contract are enforced on AWS and on GCP, what fluid verify checks, and what has been proven against the real clouds.
---

# Governance parity: one contract, AWS and GCP

A contract declares its governance once, in fields that name no cloud. Each
environment's overlay patches only `exposes[].binding`: the platform, the
location, and which real identities the contract's logical principals are on
that cloud. `fluid apply` emits that cloud's own resources, and `fluid verify`
checks the live platform against the same derivation apply emitted from.

This page is the reference. The how-to is
[One contract, two clouds](../recipes/one-contract-two-clouds.md).

## Which fields need the preview schema

| Field | Schema |
|---|---|
| `exposes[].lifecycle.expire` | 0.7.6 (preview) |
| `exposes[].binding.encryption.kms` | 0.7.6 (preview) |
| `exposes[].binding.principals` | 0.7.6 (preview) |
| `exposes[].policy.authz.columnRestrictions` | 0.7.5 (stable) |
| `accessPolicy.grants[]` | 0.7.5 (stable) |

0.7.5 is the stable schema and the default. A contract opts into the preview
with `fluidVersion: "0.7.6"`. Under 0.7.5 the preview fields fail validation:

```console
$ fluid validate contract.fluid.yaml          # fluidVersion: "0.7.5"
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
...
 1. exposes[0].lifecycle: Additional properties are not allowed ('expire' was unexpected)
```

## The parity table

| Policy (contract field) | AWS: what `fluid apply` emits | GCP: what `fluid apply` emits | What `fluid verify` checks |
|---|---|---|---|
| **Retention**: `exposes[].lifecycle {retention, expire: true}` | One rule per expose in the bucket's `aws_s3_bucket_lifecycle_configuration`, filtered to the binding's prefix, expiring objects `retention` after they are written. | Daily partitions that expire `retention` after their day ends (`time_partitioning {type: DAY, expiration_ms}`), by ingestion time, or on `binding.location.partitionBy` when it names a date or timestamp column. Never a table expiration. | AWS: an enabled rule covering the prefix expires after exactly the period, and none expires sooner. GCP: partition type, field and `expirationMs`, and no table `expirationTime`. |
| **Encryption at rest**: `binding.encryption.kms` | `product`: a KMS key per bucket (`aws_kms_key`, rotation on, alias `alias/fluid/<id>/<bucket>`) as the bucket's default SSE-KMS. `alias/...` or an ARN: that key. `none`: SSE-S3. | `product`: a key ring and key per dataset (`google_kms_key_ring` `fluid-<id>-<dataset>`, `google_kms_crypto_key` `bigquery`, 90-day rotation), granted to the BigQuery service agent, used as the dataset's and the table's key. `projects/.../cryptoKeys/...`: that key. `none`: Google-managed keys. | AWS: the key is `Enabled`, and the objects under the prefix are SSE-KMS with it. GCP: `kmsKeyName` of the table, and of the dataset when the product owns it. |
| **Column restrictions**: `exposes[].policy.authz.columnRestrictions` | Each Lake Formation `SELECT` grant excludes the columns its principal may not read (`aws_lakeformation_permissions` `table_with_columns.excluded_column_names`). | A Data Catalog taxonomy with fine-grained access control, a policy tag per set of restricted columns, attached in the table schema, and `roles/datacatalog.categoryFineGrainedReader` for exactly the allowed readers. | AWS: no `SELECT` of a denied principal, a read grantee or `IAM_ALLOWED_PRINCIPALS` reaches a column it may not read, including grants made outside the contract. GCP: every restricted column carries a tag, the tag's readers are exactly the derived set, and the taxonomy enforces fine-grained access control. |
| **Access grants**: `accessPolicy.grants[]` | Not emitted. On AWS, who reads is the binding's `governance.lakeFormation.grants`. | One `google_bigquery_dataset_iam_member` per role and member, with the logical principal mapped to its GCP identity. | Not checked on either cloud. |

`fluid verify` also checks, on both clouds, the row count against the build's
run records and that columns declared in `policy.privacy.masking` did not land
in cleartext. A mismatch is critical (`fluid verify --strict` fails); a check
that could not run is an error.

### Refused, not dropped, on AWS and GCP

On an `aws` or `gcp` binding, a policy the binding cannot apply is refused at
`fluid validate`, `fluid plan` and `fluid apply`:

- retention, a key or a column restriction on a GCP binding that is not a
  BigQuery table (GCS, Pub/Sub, Iceberg storage);
- a column restriction on an AWS binding with no Lake Formation grants
  (`column-restriction-unenforceable`) or on a non-Glue format;
- a column restriction on GCP with no reader (`column-restriction-no-readers`);
- an AWS key reference on GCP, and a Cloud KMS key name on AWS;
- tables of one BigQuery dataset declaring different keys
  (`encryption-kms-mixed-dataset`).

An `aws` binding whose contract carries `accessPolicy.grants` but no
`governance.lakeFormation.grants` gets a validate warning: "accessPolicy.grants
are not enforced on aws binding(s) ...".

::: warning Other platforms apply none of these fields
As of 0.18.1 the refusals above cover `aws` and `gcp` bindings only. On a
`snowflake` or `local` binding, `lifecycle.expire`, `encryption.kms`,
`columnRestrictions` and `accessPolicy.grants` are neither emitted nor refused.
Measured: the contract from the recipe with a `snowflake` overlay validated
cleanly, and `fluid generate iac --env snowflake` wrote three resources
(`snowflake_database`, `snowflake_schema`, `snowflake_table`) and nothing for
the retention, the restriction or the grants. See
[Snowflake](../providers/snowflake.md) for what the Snowflake provider manages.
:::

## Logical principals and `binding.principals`

The base contract names principals as the business knows them. Each overlay
maps them, in the binding, to the identities they are on that cloud:

```yaml
# contract.fluid.yaml (base)
accessPolicy:
  grants:
    - principal: group:analysts@acme.example
      permissions: [read]
exposes:
  - exposeId: customer_events
    policy:
      authz:
        columnRestrictions:
          - principal: group:analysts@acme.example
            columns: [customer_id]
            access: deny
```

```yaml
# overlays/gcp.yaml
exposes:
  - binding:
      platform: gcp
      principals:
        group:analysts@acme.example: group:analysts@<your-domain>
```

```yaml
# overlays/aws.yaml
exposes:
  - binding:
      platform: aws
      principals:
        group:analysts@acme.example: arn:aws:iam::123456789012:role/analyst
```

- Replace `<your-domain>` with the domain of your own groups before
  `--env gcp` validates: left as written, validate refuses the identity as not
  a GCP IAM member, so a placeholder cannot reach an access list.
- A value is one identity, a list, or `[]` for "no identity on this cloud"
  (nothing is granted to it there). On `gcp` an identity is an IAM member
  (`user:`, `group:`, `serviceAccount:`, `domain:`); on `aws` an IAM principal
  ARN.
- With `binding.principals` present, every principal the contract names for
  the expose must be mapped. An unmapped one is refused at validate:

  ```text
  exposes accessPolicy names principal 'group:stewards@acme.example', and this gcp binding's
  binding.principals does not map it to an identity. forge-cli never emits a logical principal
  as written once a binding maps principals. ...
  ```

- Without the block, principals are used as written, except that on GCP a
  placeholder is refused, at every `fluidVersion`: a principal in a reserved
  top-level domain (`.example`, `.test`, `.invalid`, `.localhost`), or one that
  is not an IAM member at all (no domain, an unknown prefix such as `role:`, an
  unfilled `<<YOUR_PROJECT_HERE>>`). BigQuery refuses an access entry for an
  identity that does not exist.
- On AWS, an unmapped column-restriction principal must already be an IAM ARN.

::: warning A stable (0.7.5) contract cannot follow the placeholder error's advice
The placeholder error says "Map the logical principal in this environment's
binding.principals". `binding.principals` exists only in schema 0.7.6. A 0.7.5
contract that adds it fails with "Additional properties are not allowed
('encryption', 'principals' were unexpected)". On 0.7.5, write real IAM members
in the contract, or move the contract to `fluidVersion: "0.7.6"`.
:::

## Column restrictions

- `deny`: the principal may not read the columns. `allow`: only the principals
  an `allow` names may read them. A deny beats an allow.
- A restriction never grants access. The readers are the expose's readers: on
  GCP the `accessPolicy` read grantees and `policy.authz.readers`; on AWS the
  Lake Formation `SELECT` grantees.
- On GCP a denied principal gets an access error on the restricted columns;
  `SELECT * EXCEPT (<restricted columns>)` still works for it. BigQuery dynamic
  data masking is not emitted.
- On AWS, a grant's hand-written `excludedColumns` keeps working; next to a
  restriction on the same expose the two must agree
  (`column-restriction-conflict`).

`policy.privacy.masking` is a different mechanism, applied by a DuckDB
acquisition build (`pattern: acquisition`, `engine: duckdb`). It hashes, masks,
tokenizes or encrypts the declared columns inside the landing `COPY`, so the
file, S3 object or BigQuery load file is already treated, and `fluid verify`
fails a masked column that landed in cleartext. An `embedded-logic` / SQL build
does not apply masking: as of 0.18.1 it refuses an expose that declares
`policy.privacy.masking` (`Executed: 0, Failed: 1`, with the message "declares
policy.privacy.masking, which the embedded-SQL landing path does not apply
yet"). For that build, write the masking into `properties.sql`.

## Retention counts from the partition's date

On GCP, `lifecycle.expire` expires a partition `retention` after its date. By
ingestion time that is the day the row was loaded. Only when
`binding.location.partitionBy` names a date or timestamp column does it count
from the row's own date. With `partitionBy`, a backfill of rows older than the
retention period lands in partitions that are already expired and BigQuery
deletes them at once.

`lifecycle.retention` and `expire` govern the exposed data. The top-level
`retention:` block and `fluid retention` are a different mechanism, for run
artifacts: see [fluid retention](../cli/retention.md).

## Changes a live table cannot take in place

On AWS, S3 holds one lifecycle configuration per bucket, and `fluid apply`
writes it as the whole configuration: rules on the bucket that `fluid apply` did
not write are replaced, so a bucket with hand-made lifecycle rules loses them.
For a shared (`packaging`) bucket nothing is written, and the pool's owner must
hold the retention rule.

BigQuery cannot partition an existing table, and a table whose key changes is
replaced. The first apply that adds `expire: true`, or a key, to a table that
exists plans the table's replacement, and `fluid apply` refuses it without
`--allow-data-loss`. The next build lands the data again. Removing `expire`
later is refused the same way. Removing an access grant, a policy tag or a Lake
Formation permission is a revocation, not data loss, and is not gated.

GCP dataset grants are non-authoritative member resources since 0.17.0: a grant
made outside the contract is no longer removed by the next apply. The first
apply on a dataset whose state still holds the older authoritative `access`
list revokes, once, the entries no member resource covers, and prints them.

## Prerequisites

- GCP: the Cloud KMS API and the Data Catalog API enabled on the project. The
  identity running `fluid apply` needs `roles/cloudkms.admin`,
  `roles/datacatalog.categoryAdmin` and `bigquery.datasets.update`, beyond
  BigQuery. A key ring and a key cannot be deleted on GCP: `tofu destroy`
  schedules the key's versions for destruction and the next apply adopts the
  same names.
- GCP verify: the column check calls the Data Catalog API with Application
  Default Credentials and needs `datacatalog.taxonomies.get` and
  `datacatalog.taxonomies.getIamPolicy`.
- AWS verify: the Lake Formation check lists the permissions the caller can
  see, so it must run as a Lake Formation administrator. When the contract's
  own grants are not in the listing, it reports an error rather than a pass.

::: warning Those two roles are broad
- `roles/cloudkms.admin` includes `setIamPolicy` on keys, so the identity can
  grant itself decrypt on any key it can administer, and it can destroy key
  versions, which leaves the data encrypted with them unreadable.
- `roles/datacatalog.categoryAdmin` can set the IAM policy of a policy tag, so
  it can grant fine-grained reader on every policy tag it can administer.

The product's key ring is named `fluid-<id>-<dataset>` (shortened to 63
characters with a hash suffix when longer) and is created in the project of the
binding's `location`.
Limit the grants with an IAM condition on the resource name, matching key rings
that start with `fluid-`, or give the product its own project so the roles reach
only that project's keys and tags. Try the narrowed grant on a scratch project
before you rely on it.
:::

## What has been proven

- **Measured against real Google Cloud**, 4 October 2026, on 0.18.0. In a demo
  lab, two lineage chains of eleven products were applied with
  `fluid apply --env gcp` from generated Jenkins pipelines, as a deploy service
  account reached by Workload Identity Federation:
  - Each apply created its dataset, key ring and key, its table with daily
    partitions that expire after the retention, its dataset IAM members, and a
    policy tag on each restricted column.
  - Every `fluid verify` passed its retention, encryption and
    `columnRestrictions` dimensions against the live platform.
  - Consumers read their upstreams bound to BigQuery from BigQuery.
  - Querying as each principal: a denied principal's query of a restricted
    column is refused by that column's tag, a reader the restriction leaves
    reads it, and a principal with no dataset grant is refused the table.
    BigQuery's refusal reads:

    ```text
    User has neither fine-grained reader nor masked get permission to get data protected by policy tag "<taxonomy> : <tag>" on column <project>.<dataset>.<table>.<column>.
    ```

- **Checked against moto, not a real account.** A real `tofu plan` accepts the
  Lake Formation grants with excluded columns, and `fluid verify`'s Lake
  Formation check runs against moto's stored grants. moto enforces neither Lake
  Formation permissions nor key policies, so those tests do not show a denied
  principal's Athena query being refused.
- **Not proven:** the Lake Formation half against a real account as 0.17.0
  derives it from `columnRestrictions`. The grant shape it emits (excluded
  columns beside `wildcard`) was applied and enforced on a real account from
  0.16.6, written by hand in the overlay.
- **Not checked by `fluid verify` on either cloud:** dataset and table access
  grants.

## See also

- [Environments and overlays](./environments-and-overlays.md)
- [OpenTofu state](./state.md)
- [Governance & policy](./governance-policy.md), [Sovereignty](./sovereignty.md)
- [`fluid verify`](../cli/verify.md)
- [AWS](../providers/aws.md), [GCP](../providers/gcp.md)
