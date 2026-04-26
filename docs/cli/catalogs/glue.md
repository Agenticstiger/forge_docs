# AWS Glue Data Catalog

Source-side catalog adapter for **AWS Glue Data Catalog**. Reads
tables, databases, partitions, and column-level classifiers, plus
Lake Formation tags when present.

> **Recommended for:** AWS-native teams using Glue as the metadata
> store for S3 / Athena / Redshift Spectrum / EMR. Glue's metadata
> is the single source of truth for any AWS analytics stack.

## Install

```bash
pip install "data-product-forge[aws]"
```

Adds `boto3`. (Note: many users already have `boto3` installed for
unrelated reasons — the dep is harmless if duplicated.)

## Privileges to grant

The adapter is **read-only on metadata**. AWS IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetTable",
        "glue:GetTables",
        "glue:GetPartitions",
        "glue:GetTableVersions"
      ],
      "Resource": "*"
    }
  ]
}
```

The pre-built AWS managed policy `AWSGlueConsoleReadOnlyAccess` is a
superset of the above — fine for trial / quickstart, more than the
minimum needed.

For Lake Formation tag reads (optional):

```json
{
  "Effect": "Allow",
  "Action": [
    "lakeformation:GetResourceLFTags",
    "lakeformation:ListLFTags",
    "lakeformation:GetLFTag"
  ],
  "Resource": "*"
}
```

If LF tag privileges are missing, the adapter soft-fails on tag
reads (forge still works).

## Authentication methods

| Method | When to use | Setup |
|---|---|---|
| **`instance_profile`** ★ | EC2 / ECS / Lambda / GitHub-Actions-on-AWS | Inherits the role attached to the compute. No setup. |
| `iam_key` | Local dev, CI without OIDC | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` env vars. |
| `iam_role_arn` | Cross-account access | Assume the target role; adapter handles `sts:AssumeRole`. |
| `aws_profile` | Multi-account local dev | Named profile from `~/.aws/credentials`. |
| `sso` | Federated SSO | `aws sso login` then run `fluid forge`. |

★ `instance_profile` is the recommended path for any compute
running in AWS. Local dev should prefer `aws_profile` or `sso` over
long-lived `iam_key`.

## Setup

```bash
fluid ai setup --source glue --name glue-prod
# ? Catalog: glue
# ? Region: us-east-1
# ? Auth method:
#   ★ instance_profile (recommended on AWS)
#     iam_key
#     iam_role_arn
#     aws_profile
#     sso
# ? AWS profile: default            (only for aws_profile)
# ? Default database: my_db
# ✓ Saved to ~/.fluid/sources.yaml
```

Or env vars:

```bash
export AWS_REGION=us-east-1
export AWS_PROFILE=my-profile     # for aws_profile auth
# OR
export AWS_ACCESS_KEY_ID=...      # for iam_key auth
export AWS_SECRET_ACCESS_KEY=...
```

## End-to-end demo

```bash
fluid ai setup --source glue --name glue-prod

fluid forge data-model from-source \
  --source glue \
  --credential-id glue-prod \
  --database my_db \
  --tables orders customers \
  --technique dimensional \
  -o orders.fluid.yaml

fluid generate transformation orders.fluid.yaml -o ./dbt_orders --dbt-validate
```

`--database` is required for Glue (Glue tables are
database-scoped, not catalog-flat). `--tables` is optional — when
omitted, every table in the database is forged into one model.

## What lands where

| Glue source | Forge output |
|---|---|
| Table `Description` | `OSIDataset.fields[].expression.description` |
| Column `Comment` | `OSIDataset.fields[].expression.description` |
| Table `Owner` | `metadata.owner.team` (excluded if it looks like a system role) |
| Table `Parameters.domain` | `metadata.domain` + industry hint |
| Table `UpdateTime` | `metadata.lineage.upstream[].timestamp` (when known) |
| Lake Formation tags | `agentPolicy.sensitiveData[]` (PII / PHI / PCI from LF tag values) |
| `PartitionKeys` | dbt `partition_by` config |

## Pagination is honored

Glue's `GetTables` API caps at ~100 tables per page. The adapter
walks the `NextToken` to exhaustion — large catalogs return every
table, not just the first page.

## Empty by design: no Glue lineage today

Glue itself has no native table lineage (AWS Data Lineage is a
separate service launched 2024). The adapter's `get_lineage()`
returns empty for now; lineage will land in v1.6+ via a separate
AWS Data Lineage adapter that reuses the Glue auth.

## Common errors

### `CatalogConfigError: boto3 missing`
Run `pip install "data-product-forge[aws]"`.

### `CatalogPermissionError: User not authorized to perform glue:GetTables`
Suggestion list contains the IAM policy block above. Attach the
managed `AWSGlueConsoleReadOnlyAccess` policy for a quick fix.

### `CatalogConnectionError: EntityNotFoundException: Database my_db not found`
Verify the database exists in the configured region — Glue
databases are region-scoped. A `us-east-1` database is invisible
from a `us-west-2` client unless the region is set correctly.

### `CatalogConfigError: database is required for Glue`
Glue tables are database-scoped. Pass `--database my_db` (no
default scope concept like Snowflake's database+schema).

## See also

- [Catalog index](README.md)
- [AWS provider page](../../providers/aws.md)
