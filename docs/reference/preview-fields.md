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

*([forge-cli #712](https://github.com/Agenticstiger/forge-cli/pull/712), since 0.20.0)* `builds[].properties.sink.catalogAuth` is a 0.7.6 field too. It has no row above and none in the preview delta: that delta is generated from the 0.7.6 schema bundled in the CLI release this site is pinned to, and the field was added to the schema after it. It names the environment variable that authenticates a streaming sink to an Iceberg REST catalog; see [Authenticate a sink to a REST catalog](../advanced/source-aligned-acquisition.md#authenticate-a-sink-to-a-rest-catalog).

*(since 0.21.0, [forge-cli #731](https://github.com/Agenticstiger/forge-cli/pull/731))* `builds[].engine: flink` is a 0.7.6 value too, for a job that runs on the Flink Kubernetes Operator, AWS Managed Service for Apache Flink, or another Flink platform. forge-cli validates and plans it but ships no runner; see [Flink jobs](../concepts/builds-exposes-bindings.md#flink-jobs-engine-flink).

*(since 0.21.0, [forge-cli #732](https://github.com/Agenticstiger/forge-cli/pull/732))* In a contract that names 0.7.6, an overlay patches `builds`, `exposes` and `consumes` by identity instead of by position; see [How an overlay merges](../concepts/environments-and-overlays.md#how-an-overlay-merges).

*(since 0.22.0, [forge-cli #734](https://github.com/Agenticstiger/forge-cli/pull/734))* `builds[].execution.trigger.type: continuous` is a 0.7.6 value too, for a job its platform keeps running: no scheduler starts it, and it takes no other trigger; see [Continuous builds](../concepts/builds-exposes-bindings.md#continuous-builds-trigger-type-continuous).

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

## Seven more fields, in the next release after `0.22.0`

::: tip Not in a released CLI yet
[forge-cli #753](https://github.com/Agenticstiger/forge-cli/pull/753) adds seven optional
fields to the 0.7.6 preview schema, for things a contract could not previously say. All seven
require `fluidVersion: "0.7.6"`, all are additive, and a contract that sets none of them
validates and exports byte for byte as before. The names are taken from Bitol ODCS v3.1.0 and
the released ODPS v1.1.0 rather than invented, so import and export are a pass-through instead
of a translation.

The release is a minor bump from `0.22.0` and its number is not settled yet, so this page names
the release rather than the number. The generated [0.7.6 preview delta](./contract-0.7.6-preview.md)
does not list these rows: it is rendered from the schema bundled in the CLI release this site is
pinned to, and will carry them once that pin moves.
:::

| Field | What it declares | What it changes on export |
| --- | --- | --- |
| `metadata.team` | The team as a roster — `{name, members[]}`, each member `{username, name, role, email}` — where `metadata.owner` holds one team name and one mailbox and no role at all | Fills the ODCS and ODPS team block, which came out empty before. See [the `email` caveat](#the-email-caveat) |
| `description` (root) | Either a string, as today, or `{purpose, usage, limitations}` — the shape both Bitol standards define | An export could only ever carry `description.purpose`; `usage` and `limitations` had no home a contract could declare, so every export left them empty |
| `consumes[].contractId` | The upstream contract's own id, for an upstream that has one — a product not built with FLUID, registered in a catalog under an id FLUID did not derive | The canonical-port builder already preferred an explicit id; with `consumes[]` closed there was no way to supply one, so the derived id was exported as if the upstream answered to it |
| `exposes[].contract.id` | An explicit, stable contract id for one output port | Used verbatim as the ODCS `id` and the ODPS output port `contractId`. See [pinning a contract id](#pinning-a-contract-id) |
| `binding.location.host` | Host or endpoint; for a Kafka binding, the bootstrap servers | The ODCS server mapper already read `host` and fell back to `account`, while the schema accepted only `account` — so the only valid way to set bootstrap servers was a field named for something else. With neither set, the exported server is the placeholder `${KAFKA_BOOTSTRAP_SERVERS}` |
| `exposes[].binding.serialization` | `{value, key}`, each one of `json`, `avro`, `protobuf`, `xml`, `avro-confluent`, `json-confluent` | The only thing that moves a Kafka server's ODCS `format` off `kafka_topic`. See [declaring the wire format](#declaring-the-wire-format) |
| `quality` on a column | Column-level data quality rules, in ODCS's own shape | Written straight into `schema[].properties[].quality[]` of the exported ODCS contract. See [column quality rules](#column-quality-rules) |

`binding.location.host` is usually set per environment in an overlay rather than in the base
contract, since the brokers differ by environment and the rest of the binding does not.

### The `email` caveat

`metadata.team.members[].email` is **not** exported as a Bitol `TeamMember` field, because
there is no such field to export it as. All three vendored schemas — ODCS v3.1.0, ODPS v1.0.0
and ODPS v1.1.0 — define `TeamMember` with `additionalProperties: false` and none of them has
an `email` property. Writing one would produce a document that fails the standard's own schema.

So the roster's `email` is carried in that member's `fluidEmail` custom property instead. It is
not dropped, and it is not smuggled into a field that means something else.

`username` is the only member field Bitol requires, and the only one this schema requires. The
other three, `name`, `role` and `email`, are optional. `role` is free-form, because Bitol does
not constrain it — `owner`, `steward`, `data engineer`.

### Pinning a contract id

Without `exposes[].contract.id` a port's contract id is derived as `<product id>.<exposeId>`,
so renaming the product or the expose silently changes the contract id and breaks every
consumer reference to it. A catalog that requires an id format of its own — a URN, a UUID —
cannot be served at all.

The field has **no pattern**, only a minimum length of 1. That is deliberate: a catalog's id
format is the catalog's business, so the schema does not have an opinion about what a URN or a
UUID should look like.

Each expose needs its own. Two exposes that resolve to one contract id — whether both pin it,
or one pins what the other derives — fail `fluid validate` and every export path, and the
message names both exposes and the shared id. That export used to succeed and write one
per-port ODCS document for two output ports, so one port's schema was lost; see
[Read this first if you consume the exported artifacts](../upgrading.md#read-this-first-if-you-consume-the-exported-artifacts).

### Declaring the wire format

A Kafka binding declares `format: kafka_topic`, which tells a consumer nothing about whether
the values on the topic are Avro or JSON — the one thing it has to know to read the topic at
all. `binding.serialization.value` says so, and `key` says the same for a topic whose keys are
not opaque bytes.

The first four values are the message formats ODCS v3.1.0 documents for its own Kafka server
`format`. The two `-confluent` values name those same wire formats carried through a Confluent
schema registry, spelled as Apache Flink spells them; on export they collapse onto the plain
wire format, because that is what the ODCS field means. The registry is not forgotten: the
whole `binding.serialization` block rides along verbatim in the `fluidExtras` custom property.

A contract that does not declare it exports exactly as it does today.

### Column quality rules

The ODCS exporter has always replayed a column's `quality` key verbatim and always read it back
on import — but `$defs.column` is `additionalProperties: false` and did not define it. So a
column written the way the exporter supports was **refused by `fluid validate`**: the only way
to get a hand-written column rule into a published contract was to write an invalid contract.

Two things are worth knowing before you set it.

- **It replaces the derived rules for that column** rather than adding to them. That is what
  makes an imported ODCS column round-trip byte for byte. A column without it exports exactly
  as it does today, with the rules forge derives from `required`, the primary-key tag and
  `validationRules`.
- **Put the rules on the column, not in a pass-through bucket.** The ODPS importer merges a
  resolved port's `contract` block into its output-port stub and discards the sub-import's root
  `extensions`, so rules parked in that bucket were dropped outright by a
  FLUID → ODPS → FLUID cycle.

The authority for an item's contents is ODCS v3.1.0 `$defs.DataQuality`, which the schema
deliberately does not re-declare — a copy would drift from the vendored schema, and
`fluid odcs validate` already checks a document against it. The keys the
schema does name:

| Key | Applies to | Notes |
| --- | --- | --- |
| `id` | every type | Stable identifier, unique within the column's rules; the charset is ODCS `$defs.StableId`. Rules forge derives itself are named `<column>-<metric>`. Optional in ODCS, but a DQ engine that labels results by rule id rejects a contract whose rules have none, so give every rule one |
| `type` | — | `text` (prose), `library` (a predefined ODCS metric), `sql` (a query whose result is compared) or `custom` (a named engine's own check) |
| `metric` | `library` | One of `nullValues`, `missingValues`, `invalidValues`, `duplicateValues`, `rowCount` — the five ODCS v3.1.0 defines. A name outside the list is not a library rule |
| `arguments` | `library` | Extra arguments for the metric: `pattern` or `validValues` for `invalidValues`, as DataHub's ODCS ingestion reads them |
| `query` | `sql` | The query whose result the comparison operator is applied to |
| `engine`, `implementation` | `custom` | The engine that runs the check (`soda`, `great-expectations`, `dbt`) and the check as that engine expresses it |
| `dimension` | every type | One of `accuracy`, `completeness`, `conformity`, `consistency`, `coverage`, `timeliness`, `uniqueness` |
| `description`, `severity`, `unit` | every type | ODCS types `severity` as a free string and documents `info` / `warning` / `error` by example. `unit` is usually `rows` (the default) or `percent` |

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
