---
title: Fields that need fluidVersion 0.7.6
description: The contract fields that exist only in the 0.7.6 preview schema, the CLI release that introduced each, and validated examples of opting in.
---

# Fields that need `fluidVersion: "0.7.6"`

Some fields exist only in the 0.7.6 preview schema. A contract that declares `fluidVersion: "0.7.5"` and uses one of them fails `fluid validate`. This page lists them and shows how to opt in. The [0.7.6 preview delta](./contract-0.7.6-preview.md) has the full row for each field; this page is the map to it.

## Opt in

Change `fluidVersion` and add the field. This contract keeps its objects for 30 days and then deletes them, and encrypts the bucket with a key the product creates:

```yaml
fluidVersion: "0.7.6"
kind: DataProduct
id: gold.sales.orders_v1
name: Orders
metadata:
  owner:
    team: sales-data
    email: sales-data@northwind.example
exposes:
  - exposeId: orders
    kind: table
    contract:
      schema:
        - name: order_id
          type: string
    lifecycle:
      retention: P30D
      expire: true
    binding:
      platform: aws
      format: parquet
      encryption:
        kms: product
      location:
        bucket: <your-bucket>
        path: orders/
        region: eu-west-1
```

Bucket names are global: write a bucket you own in place of `<your-bucket>`.

```bash
fluid validate contract.fluid.yaml
```

```text
✅ Valid FLUID contract (schema v0.7.6)
```

The same file with `fluidVersion: "0.7.5"` is rejected, once per field the 0.7.5 schema does not know:

```text
❌ Invalid FLUID contract (2 error(s)) (schema v0.7.5)

Validation Errors:
==================
 1. exposes[0].binding: Additional properties are not allowed ('encryption' was
unexpected)
 2. exposes[0].lifecycle: Additional properties are not allowed ('expire' was
unexpected)
```

`expire: true` turns `retention` from a declaration into deletion. Read the `exposes[].lifecycle.expire` row before you set it: it says what the AWS and GCP emitters write, what happens to data that is already older than the period, and which plans `fluid apply` refuses without `--allow-data-loss`.

## What the preview adds

"First in CLI" is the first release whose bundled 0.7.6 schema contains the field, read from the tagged releases of the CLI.

| Field | First in CLI | What it declares |
| --- | --- | --- |
| `packaging`, `exposes[].binding.packaging` | 0.13.0 | Whether the product owns each infrastructure container (`isolated`) or writes into a pre-existing, platform-owned pool (`shared`), as one default for the contract and an override per exposure. See the [`packaging`](./contract-0.7.6-preview.md#packaging) rows. |
| `exposes[].semantics.measures[].aggParams` | 0.13.0 | Parameters for a measure whose `agg` is `percentile`: the percentile, and whether to use the discrete form. |
| `consumers` | 0.13.1 | The dashboards, notebooks, analyses, ML apps and applications built on the product, shaped like dbt exposures. The schema describes the key as reserved and not yet consumed by any code. See the [`consumers`](./contract-0.7.6-preview.md#consumers) rows. |
| `consumes[].upstreamWorkspace`, `consumes[].upstreamDigest` | 0.16.0 | For an upstream that lives in another mesh: the federated workspace that owns it, and the `sha256:` digest this product was composed against. Setting `upstreamWorkspace` requires `upstreamDigest`. |
| `exposes[].binding.governance.lakeFormation.bucketPolicy` | 0.16.3 | Which Lake Formation grantees also get an S3 bucket-policy statement: `cross-account`, `none` or `all-grantees`. |
| `exposes[].binding.encryption.kms` | 0.16.5 | The key that encrypts the data at rest: `product`, `none`, an alias, an AWS key ARN, or a Cloud KMS key name. |
| `exposes[].lifecycle.expire` | 0.16.5 | Whether `retention` deletes data. |
| `exposes[].binding.principals` | 0.17.0 | A map from the contract's logical principals to the identities they are on this binding's cloud. |

The [`consumes`](./contract-0.7.6-preview.md#consumes) and [`exposes`](./contract-0.7.6-preview.md#exposes) sections of the preview delta hold the rows for the fields above, in the order the schema declares them.

### Federated upstreams

`upstreamWorkspace` and `upstreamDigest` travel together. This pair of fields on a `consumes[]` entry validates under 0.7.6:

```yaml
consumes:
  - productId: silver.hr.people_v2
    exposeId: people
    upstreamWorkspace: hr-mesh
    upstreamDigest: sha256:<64 hex characters>
```

Drop the digest and keep the workspace, and validation names the dependency:

```text
 1. consumes[0]: 'upstreamDigest' is a dependency of 'upstreamWorkspace'
```

Under 0.7.5 both keys are rejected as unexpected. The `upstreamDigest` row describes the check `fluid apply` makes against the upstream's live digest. [`fluid apply`](../cli/apply.md) documents the `--no-verify-federation` flag that skips it.

### Mapping principals per cloud

A contract names the principals it grants to and restricts as the business knows them. `binding.principals` says which identity each one is on the cloud the binding targets, so the same base contract deploys to AWS and to GCP with a different overlay each.

On GCP a principal that is not an IAM member is refused at `fluid validate`, with or without a `binding.principals` block. A base contract that grants to a bare `analysts` (`accessPolicy` is a top-level contract key, not a key under an expose):

```yaml
accessPolicy:
  grants:
    - principal: analysts
      permissions: [read]
```

on a `gcp` binding fails:

```text
 1. exposes accessPolicy: principal 'group:analysts' is not a GCP IAM member
(user:, group: or serviceAccount: with an email address, or domain:), and this
binding's binding.principals does not map it, so it can only be a logical name.
...
```

Mapping it in the binding fixes it:

```yaml
binding:
  platform: gcp
  principals:
    analysts: group:analysts@<your-domain>
```

Replace `<your-domain>` with the domain of your own groups; left as written, validate refuses the identity as not a GCP IAM member.

The same refusal applies to a placeholder in a reserved top-level domain (`.example`, `.test`, `.invalid`, `.localhost`), per the `exposes[].binding.principals` row. A value that is not valid for the binding's platform is refused too: an AWS role ARN mapped on a `gcp` binding fails with "is not a GCP IAM member".

## Behaviour that does not wait for the preview

`bucketPolicy` is a 0.7.6 key, but the behaviour it controls is not. When a binding with Lake Formation grants omits it, the AWS emitter in 0.18.1 applies `cross-account`: only grantees in another AWS account get a bucket-policy statement, and same-account grantees get none. Setting the key under 0.7.6 changes that choice; leaving it out does not return the earlier output. The `exposes[].binding.governance.lakeFormation.bucketPolicy` row has the security reasoning.

## Changed rows that a 0.7.5 contract can already use

These rows appear on the preview delta, but the field itself is in the 0.7.5 schema. Only the rows listed here were checked against both schemas.

| Field | What 0.7.6 changes |
| --- | --- |
| `exposes[].policy.authz.columnRestrictions` | The schema description now says what `fluid apply` enforces on each cloud, and the items gain descriptions. The field and its keys are in 0.7.5. |
| `exposes[].policy.privacy.masking` | The field gains a description. |
| `exposes[].policy.privacy.masking[].params` | 0.7.5 accepts any keys. 0.7.6 lists `saltEnv`, `keyEnv`, `keepFirst` and `keepLast`. Those four keys appear as added rows on the delta because 0.7.5 left `params` open, and a 0.7.5 contract that uses them passes schema validation. |
| `exposes[].binding.location.partitionBy` | A longer description covering its use with `lifecycle.expire` on BigQuery. |

A 0.7.5 contract that declares `columnRestrictions` on a `gcp` binding is in the 0.7.5 schema. It validates when the expose has a reader (an `accessPolicy` read grant or `policy.authz.readers`) and fails without one.

## Changed rows that need 0.7.6

- `fluidVersion` gains `0.7.6` in its allowed values, and its description changes.
- `consumes` gains an if/then rule: when an item sets `upstreamWorkspace`, `upstreamDigest` is required. This rule is not in 0.7.5.
- `exposes[].lifecycle` is new, and `exposes[].lifecycle.retention` has a different description. `lifecycle.expire` is rejected under 0.7.5 as an unexpected key.

## Related

- [Contract reference](./README.md): how to read the tables, and the stable and preview split.
- [Schema 0.7.5](./contract-0.7.5.md): the complete stable reference.
- [Release notes 0.13.0](../RELEASE_NOTES_0.13.0.md) and [0.15.0](../RELEASE_NOTES_0.15.0.md): the releases that introduced packaging and federated pinning.
