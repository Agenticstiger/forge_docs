---
title: Schema registry (preview)
description: Check a consumed Kafka topic against its schema registry at plan and apply, register the topics a product produces through OpenTofu on the Glue Schema Registry or Confluent, and seed a consumer contract from a subject.
---

# Schema registry (preview)

*(since 0.31.0, [forge-cli #913](https://github.com/Agenticstiger/forge-cli/pull/913), [forge-cli #932](https://github.com/Agenticstiger/forge-cli/pull/932), [forge-cli #938](https://github.com/Agenticstiger/forge-cli/pull/938), [forge-cli #939](https://github.com/Agenticstiger/forge-cli/pull/939))*

A Kafka topic's records have a schema, and a registry holds it. The contract can name that registry in two places, and forge-cli does one thing for each:

| The contract names it in | The topic is | forge-cli |
|---|---|---|
| `properties.stream.registry` of a build | **Consumed** | Checks the subject against the build's `stream.schema` at `fluid plan` and `fluid apply` |
| `binding.properties.registry` of a Kafka expose | **Produced** | Registers the subject through OpenTofu |

Two registries are supported: the **AWS Glue Schema Registry** and a **Confluent** registry. The fields are `0.7.7` preview fields, so a contract that uses them declares `fluidVersion: "0.7.7"`. See the [0.7.7 preview reference](../reference/contract-0.7.7-preview.md).

## The registry reference

Both places take the same object, `$defs/schemaRegistry`:

| Field | Meaning |
|---|---|
| `kind` | `glue` or `confluent`. |
| `url` | Confluent only: the registry's REST endpoint, `http://` or `https://`. No user, password, query or fragment. A credential goes only over https. |
| `registryName` | Glue only: the registry's name. |
| `subject` | The subject. On Glue, the schema name. It defaults to `<topic>-value`. |
| `version` | `latest` or an integer from 1. |
| `compatibility` | Produced subjects: the compatibility mode. Glue allows `NONE`, `DISABLED`, `BACKWARD`, `BACKWARD_ALL`, `FORWARD`, `FORWARD_ALL`, `FULL` and `FULL_ALL`. Confluent allows `NONE`, `BACKWARD`, `BACKWARD_TRANSITIVE`, `FORWARD`, `FORWARD_TRANSITIVE`, `FULL` and `FULL_TRANSITIVE`. |
| `auth` | Confluent: `{secretRef: <reference>}`, the credential for a consumed subject. |
| `rules` | Confluent, produced subjects: see [Data-contract rules](#data-contract-rules). |

The Kafka Connect runner's `schema_registry` block and the managed Flink lane's `schemaRegistryUrl` stay valid. They resolve to the same registry reference, and the runner and the compiler still read their own blocks, so nothing about them changes.

## A consumed topic is checked at plan

```yaml
builds:
  - id: enrich-orders
    engine: spark
    properties:
      stream:
        kind: kafka
        topic: commerce.orders
        format: avro-confluent
        registry:
          kind: glue
          registryName: commerce
        schema:
          - name: order_id
            type: string
            required: true
          - name: amount
            type: decimal(18,2)
```

`fluid validate` stays offline: it checks the shape of the reference and the egress rules. `fluid plan` reads the subject:

- **Confluent.** It pins the version (`GET /subjects/{subject}/versions/{version}`), then asks the registry whether the Avro or JSON Schema derived from `stream.schema` is compatible with it (`POST /compatibility/subjects/{subject}/versions/{n}?verbose=true`). The derived schema is named after the producer's record, because Avro resolution matches records by name. An incompatible answer fails the plan and quotes the registry's messages.
- **Glue.** The Glue Schema Registry has no dry-run API, so forge reads the schema version (`GetSchemaVersion`, the latest or `N`) and compares it with `stream.schema` by its own rules.
- **Both** are also compared by the stream rules of [`fluid diff`](../cli/diff.md), so a subject in `NONE` mode is still checked.

Each subject version checked is printed, and `plan.json` records it under `schemaRegistry.checked`, which `planDigest` covers: an approved plan names the versions it was checked against. A contract that names no registry gets no new key. A failed check stops the plan with `plan_schema_registry_failed`, and no plan is written.

A subject whose registry needs a credential (`auth`) is not read at plan. Plan never fetches a contract secret. It says the subject is `verified-at-apply`, and `fluid apply` checks it before any `tofu apply`, with the same comparison, the credential sent as Basic auth over https. A failure there is `apply_schema_registry_failed`. A dry-run apply reads no registry.

This example has no `parameters.spark`, so a Glue registry is accepted. On a forge Spark build (`parameters.spark`) only `kind: confluent` is accepted, and `kind: glue` is refused at `fluid validate`: "the forge Spark runner reads the Confluent Schema Registry (kind: confluent); the Glue Schema Registry is not supported yet". The Spark runner also takes only `env://` and `aws-sm://` secret references for `auth`.

On a non-Kafka binding, `binding.properties.registry` is a validate warning. The managed Flink lane's legacy `schemaRegistryUrl` is not checked at plan.

## A produced topic is registered through OpenTofu

A Kafka topic the product produces is an expose with `format: kafka_topic` that declares its registry in `binding.properties.registry`, and its schema is the expose's `contract.schema`. Something has to register the subject, so `fluid validate` refuses a contract where nothing can: a Glue subject needs an expose bound to `platform: aws` in the same contract, and a Confluent subject needs the topic itself bound as `platform: confluent` with `format: kafka_topic`. A topic bound as `platform: kafka` can take a Glue subject, not a Confluent one. This contract validates, and `fluid generate iac --provider aws` writes the module (checked on 0.31.0):

```yaml
fluidVersion: "0.7.7"
kind: DataProduct
id: commerce.orders-enriched
name: Orders enriched
domain: commerce
metadata:
  layer: Silver
  owner:
    team: commerce-data
packaging:
  mode: isolated
  pool: commerce-platform
  containers:
    cluster: shared
    schemaRegistry: shared
exposes:
  - exposeId: orders_lake
    kind: table
    binding:
      platform: aws
      format: parquet
      location:
        bucket: commerce-lake
        path: orders/
        region: eu-west-1
    contract:
      schema:
        - {name: order_id, type: string}
  - exposeId: orders_enriched
    kind: stream
    binding:
      platform: kafka
      format: kafka_topic
      location:
        topic: commerce.orders-enriched
        host: b-1.msk.example:9098
      serialization:
        value: avro
      properties:
        registry:
          kind: glue
          registryName: commerce
          compatibility: FULL_ALL
    policy:
      classification: Confidential
    contract:
      schema:
        - {name: order_id, type: string, required: true}
        - {name: email, type: string, sensitivity: pii}
        - {name: amount, type: "decimal(18,2)"}
```

`fluid generate iac --provider aws` writes an `aws_glue_schema` named `commerce.orders-enriched-value`, with `data_format = "AVRO"` and the compatibility from the contract (`BACKWARD_ALL` by default). Checked on 0.31.0: the schema definition is canonical JSON, with sorted keys and no whitespace, so the module and the plan digest are stable, and a re-plan after the apply shows no changes.

| | AWS Glue Schema Registry | Confluent |
|---|---|---|
| Resources | `aws_glue_schema` | `confluent_subject_config` and `confluent_schema` |
| Default compatibility | `BACKWARD_ALL` | `BACKWARD_TRANSITIVE` |
| The registry | A registry that exists, read with `data.aws_glue_registry`. With `packaging.containers.schemaRegistry: isolated` the product creates it (`aws_glue_registry`) | The one the provider's own settings name (below). Neither the endpoint nor a credential is in the module or the state |
| Classification and PII | Not written to the schema | The subject's `metadata` carries the expose's classification (`policy.classification`, else the contract's) and, on an Avro subject, a `PII` tag on each personal-data column |
| Credential | IAM, through the AWS SDK. No secret | The operator's `SCHEMA_REGISTRY_API_KEY` and `SCHEMA_REGISTRY_API_SECRET` |

A changed column list becomes a new schema version. Under `BACKWARD_ALL`, Glue refuses a version that breaks compatibility.

### Confluent: the operator's registry

OpenTofu registers a produced Confluent subject in the registry the `confluentinc/confluent` provider is configured with, from the operator's environment:

| Variable | What it is |
|---|---|
| `SCHEMA_REGISTRY_REST_ENDPOINT` | The registry's endpoint. It must be the contract's `url`: plan and apply refuse another, because the schema would land somewhere the contract never named. Unset, it is a `fluid plan` warning and a `fluid apply` error. |
| `SCHEMA_REGISTRY_ID` | The registry's id (Confluent Cloud). |
| `SCHEMA_REGISTRY_API_KEY`, `SCHEMA_REGISTRY_API_SECRET` | The credential, sent to the contract's `url`. |

`SCHEMA_REGISTRY_REST_ENDPOINT` and `SCHEMA_REGISTRY_ID` cannot be set from a project `.env`: a project file that could set them would send the operator's registry key to a host of its choosing.

The provider validates a new schema with a compatibility request that has no version in its path. Karapace 4.1 and Redpanda 24.2 answer it with 404, so the provider cannot create a schema there. Produced Confluent subjects therefore target Confluent Platform 7 or later, and Confluent Cloud.

### Protobuf

A Kafka expose with `binding.serialization.value: protobuf` registers a `PROTOBUF` subject (`aws_glue_schema.data_format` on Glue, `confluent_schema.format` on Confluent). Before, it was refused. Consumed streams keep `json` and `avro-confluent`: no Flink or Spark compiler reads Protobuf yet, and `fluid import schema-registry` refuses a Protobuf subject.

**Every column declares its field number**, in `protobuf: {field: N}` (a `0.7.7` column property). Nested struct fields need one too. A field number names the field on the wire, so it never changes once data is written. It is from 1 to 536870911, outside the range 19000 to 19999 that Protobuf reserves, and unique within its message.

```yaml
contract:
  schema:
    - name: order_id
      type: string
      required: true
      protobuf: {field: 1}
    - name: placed_at
      type: timestamp_ltz
      required: true
      protobuf: {field: 2}
    - name: address
      type: struct
      protobuf: {field: 3}
      fields:
        - {name: city, type: string, required: true, protobuf: {field: 1}}
    - name: labels
      type: map
      protobuf: {field: 4}
      key: {type: string, required: true}
      value: {type: string}
```

forge writes canonical, deterministic proto3:

- A struct is a nested message, an array a `repeated` field, a map a `map<string, V>`. An array or map of arrays or maps is refused.
- A nullable scalar, or a nullable well-known type, is `optional`. A required one has no label.
- Only the imports a schema uses are written, sorted. Type names are absolute (they start with a dot), so a topic named `google` cannot shadow them.

| FLUID type | Protobuf |
|---|---|
| `date` | `.google.type.Date` |
| `timestamp`, `timestamp_ltz` | `.google.protobuf.Timestamp` |
| `decimal` | `.confluent.type.Decimal` on Confluent, which has it built in, so no schema reference is needed |

**A `decimal` column in a Glue Protobuf subject is refused at `fluid validate`.** The Glue Schema Registry resolves neither `confluent/type/decimal.proto` nor `google/type/decimal.proto`. Use Avro or JSON Schema for that subject, or keep the value as a string.

`fluid validate` also refuses two columns whose proto3 JSON names collide, and a column named like a map's implicit `<Field>Entry` type. A struct's nested message steps aside to `<Name>_<number>` when a name clashes. On Confluent, a Protobuf subject carries the classification property but not the PII field tags, which stay Avro-only. Avro and JSON Schema subjects are unchanged.

On Glue, a new version that retypes a field (`int32` to `string`, say) is refused by the registry under `BACKWARD_ALL`, and one that adds a field is accepted.

### Data-contract rules

A produced **Confluent** subject whose registry block sets `rules: true` registers the expose's row checks as Confluent data-contract rules. Confluent's serializers then enforce them on every record the producer writes. They need Confluent Platform Enterprise 7.4 or later with the rule-set extension, or Confluent Cloud with the Stream Governance Advanced package.

```yaml
exposes:
  - exposeId: orders_topic
    kind: stream
    binding:
      platform: confluent
      format: kafka_topic
      location:
        topic: commerce.orders
      serialization:
        value: avro
      properties:
        registry:
          kind: confluent
          url: https://schema-registry.example.com
          rules: true
    contract:
      schema:
        - {name: order_id, type: string, required: true}
        - {name: quantity, type: int, required: true}
        - {name: status, type: string}
      invariants:
        - id: positive_quantity
          check: "quantity > 0"
        - id: shipped_has_amount
          when: "status = 'shipped'"
          check: "quantity >= 1"
```

Each such invariant becomes one `domain_rules` entry of the schema's `ruleset`: a CEL `CONDITION` in mode `WRITE`, with `on_failure: ERROR`. The two above are written as:

```text
positive_quantity   (message.quantity > 0)
shipped_has_amount  (!((type(message.status) != null_type) && (message.status == "shipped")) || (message.quantity >= 1))
```

A `when` becomes `!when || check`. **What becomes a rule:** a [`contract.invariants[]`](../concepts/data-rules.md#invariants) entry with a `check`, no violation band, and `severity: error`. The rest is reported as not enforced by the registry, as a warning at validate and plan:

```text
exposes[0].binding.properties.registry: invariant 'warn_only' is not enforced by the registry: its severity is warning; only error checks become rules
exposes[0].binding.properties.registry: invariant 'capped' is not enforced by the registry: it allows violating rows (mustBeLessOrEqualTo)
```

Derived columns, aggregates, dependencies, banded checks and warning or info checks are all in that group.

**A check with no exact CEL form is refused** at validate and plan (`schema-registry-rules` from the emitter too), because a rule that is wrong would reject good records or let bad ones through:

```text
 1. exposes[0].binding.properties.registry: invariant 'amount_scale' has no exact CEL form for a Confluent rule: column amount is a decimal: Avro carries it as bytes, which a CEL rule cannot compare exactly
```

The refused forms are: decimal, date and timestamp columns; non-integer literals and mixing int with double; arithmetic on doubles, and division; `ROUND` and the date functions; names reached through a relationship; and a `;` in the text, which Confluent would read as a guard.

The CEL is true exactly when FLUID SQL/1's own evaluator says true, because FLUID SQL/1 is two-valued: a comparison with NULL is false. No rule it writes errors on a row of the declared types. One case diverges: a valid row whose intermediate integer result overflows a 64-bit integer is refused by the rule, which is fail-safe.

`rules` is for Avro subjects only in this preview. On a JSON Schema subject, a consumed subject or a Glue registry it is refused.

## Operator settings

A Confluent registry is a host the contract names, so it goes through the same rules as the other hosts a contract names (see [Network safety](./network-safety.md)). These variables are read from the operator's environment, and a project `.env` cannot set them:

| Variable | Entry |
|---|---|
| `FLUID_ACQUISITION_DEPLOYMENT_HOST_ALLOWLIST` | The registry's host, with no port. A loopback host needs none. |
| `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST` | `NAME@host` for each credential the registry receives: `SCHEMA_REGISTRY_API_SECRET@schema-registry.example.com` for a produced subject, or the variable the contract's `auth.secretRef` names (`SCHEMA_REGISTRY_AUTH@schema-registry.example.com`, for `env://SCHEMA_REGISTRY_AUTH`). A bare `NAME` allows every host. |

A missing entry is a **warning** at `fluid validate` and an **error** at plan and apply. A credential sent over http, and a link-local host, are errors at every stage. A loopback registry needs no entry. The Glue Schema Registry authenticates with IAM and needs none.

Seen at `fluid validate` for a produced Confluent subject with neither entry:

```text
 1. exposes[0].binding.properties.registry.url: host 'schema-registry.example.com' receives the registry credential and is not in FLUID_ACQUISITION_DEPLOYMENT_HOST_ALLOWLIST; the operator lists it there (no port)
 2. exposes[0].binding.properties.registry: SCHEMA_REGISTRY_API_SECRET may not be sent to 'schema-registry.example.com'; the operator grants it with SCHEMA_REGISTRY_API_SECRET@schema-registry.example.com in FLUID_ACQUISITION_SECRET_REF_ALLOWLIST
```

The plan-time read of a consumed Confluent subject sends no credential, and judges the address each request is pinned to.

## Seed a consumer contract from a subject

[`fluid import schema-registry`](../cli/import.md#importing-a-schema-registry-subject) reads one subject and writes a `0.7.7` contract whose build has `properties.stream` (topic, format, schema, registry) from it.

## Errors

| Event or kind | Meaning |
|---|---|
| `plan_schema_registry_failed` | A consumed subject is incompatible, unreadable, refused by the egress rules, or its reference is malformed. No plan is written. The error lists every finding. |
| `apply_schema_registry_failed` | The same, for a subject checked at apply: one whose registry needs a credential, or a produced subject. |
| `schema-registry-rules` | A produced subject's `rules: true` has a check with no exact CEL form, or sits on a subject that cannot take rules |

## See also

- [`fluid import schema-registry`](../cli/import.md#importing-a-schema-registry-subject)
- [Spark to Iceberg on AWS](./spark-iceberg-aws.md) and [Managed Flink to Iceberg](./managed-flink-iceberg.md): the builds that read a consumed topic.
- [Rules about valid data](../concepts/data-rules.md): the invariants that `rules: true` turns into registry rules.
- [Network safety](./network-safety.md): the host and secret rules.
