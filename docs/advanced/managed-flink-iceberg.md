---
title: Managed Flink to Iceberg (preview)
description: Declare a Kafka topic's records and how they become Iceberg rows in the contract; forge-cli writes, checks and deploys the Flink job through the Kubernetes operator.
---

# Managed Flink to Iceberg (preview)

*(since 0.27.0, [forge-cli #784](https://github.com/Agenticstiger/forge-cli/pull/784), which includes [#809](https://github.com/Agenticstiger/forge-cli/pull/809), [#817](https://github.com/Agenticstiger/forge-cli/pull/817) and [#819](https://github.com/Agenticstiger/forge-cli/pull/819))*

forge-cli can compile, deploy and verify an append-only Kafka → Flink → Iceberg stream that the contract declares:
- the contract says what the records on a topic are and how they become the rows of an Iceberg table;
- forge-cli writes the Flink SQL itself and checks every output column against it before anything deploys;
- it then reconciles the job through the [Flink Kubernetes operator](https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-stable/).

The lane is opt-in in two ways:
- the contract declares `fluidVersion: "0.7.7"`, the preview schema;
- the build sets `properties.parameters.flink.management: operator`.

Flink builds that run elsewhere, and the stable `0.7.6` schema, are unchanged.

::: tip Where to start
The [example contracts](https://github.com/Agenticstiger/forge-cli/tree/main/examples/flink-iceberg) cover a nested topic landed as it is, the same topic flattened to one row per item, and the same topic rebuilt into a nested table of its own shape. The example's README runs them end to end in Docker.
:::

## What is supported

| Surface | Preview behaviour |
|---|---|
| Kafka records | `properties.stream`: one topic, the value as `json` or `avro-confluent`, its fields as typed columns, an optional record key (`raw`, `json` or `avro-confluent`) and Kafka metadata as columns. A malformed JSON record fails the job rather than being dropped. |
| Mapping | `properties.mapping`. Output columns are read by name by default. A mapping can lift nested fields, explode one array into rows, look up map entries, build nested outputs field by field, and apply safe conversions. Every output column's type and nullability is checked before deploy. |
| Types | Structs, arrays, string-keyed maps, nested nullability, decimals up to precision 38, timestamps up to microseconds; nesting depth up to 32. |
| Output table | Native Iceberg namespace and table creation, format v2, append-only writes, Parquet by default, identity partitions only ([why](#partitioning)). An existing table whose schema differs from the contract is refused before any write. |
| Storage | An explicit S3 warehouse URI on a REST catalog, S3-compatible FileIO and state endpoints, and optional bearer or OAuth2 catalog auth through named environment variables. Authenticated catalog and token requests need HTTPS. |
| Runtime | A Flink 1.20.1 / Java 17 / Iceberg 1.10.0 image with forge-cli's SQL runner. Operator resources with digest-pinned images, immutable SQL ConfigMaps, and dedicated checkpoint, savepoint and HA prefixes. |
| Lifecycle | `amend`, `amend-and-build`, `create-only`, dry runs, savepoint upgrades and suspension. Replace and reset are refused. |
| Evidence | `fluid verify` reads the operator's reconciled spec, a recent successful checkpoint, the catalog's schema and a recent committed snapshot. These are not per-record delivery receipts. |
| Publication | ODCS export carries the nested types, with each nested column's full FLUID type in a `fluid.recursiveType` custom property, because ODCS has no typed maps. It also records each column's source as `transformSourceObjects` / `transformLogic`, and an explode as `dataGranularityDescription`. |
| Change review | `fluid diff --baseline` classifies changes to the stream and the mapping alongside the expose rules ([below](#schema-changes-and-fluid-diff)). |

A managed contract holds only managed builds and their outputs. One build writes each expose. Build ids and deployment namespace/name pairs may not repeat. No two checkpoint, savepoint or HA locations in the contract may be the same or nest inside each other. Provision Kafka, the catalog, the buckets, the namespace, the service account, the Secrets and the operator separately.

## Declaring the stream

The build says which records it reads in `properties.stream`, and how to reach them in `properties.parameters.flink.source`:

```yaml
fluidVersion: "0.7.7"
kind: DataProduct
id: commerce.nested-events
name: Nested commerce events
metadata:
  owner:
    team: data-platform
builds:
  - id: ingest-orders
    engine: flink
    pattern: embedded-logic
    outputs: [orders]
    execution:
      trigger:
        type: continuous
      runtime:
        platform: kubernetes
    properties:
      language: flink_sql
      stream:                       # what the records are
        kind: kafka
        topic: orders
        format: json                # or avro-confluent
        schema:                     # the record value, as columns
          - name: event_id
            type: string
            required: true
          - name: customer
            type: struct
            fields:
              - name: id
                type: string
              - name: address
                type: struct
                fields:
                  - name: country
                    type: string
          - name: items
            type: array
            element:
              type: struct
              fields:
                - name: sku
                  type: string
                - name: price
                  type: decimal(18,2)
          - name: attributes
            type: map
            key: {type: string, required: true}
            value: {type: string}
          - name: event_time
            type: timestamp_ltz(3)
      parameters:
        flink:
          management: operator
          source:                   # how to reach them
            bootstrapServers: kafka:9092
            groupId: forge-commerce-orders-v1
            startupMode: group-offsets    # or earliest-offset
            eventTime:
              column: event_time
              delaySeconds: 5
          deployment:
            name: commerce-orders
            namespace: data-products
            context: development
            serviceAccount: flink
            image: registry.example.com/forge-flink@sha256:<digest>
            checkpointUri: s3://flink-state/orders/checkpoints
            savepointUri: s3://flink-state/orders/savepoints
            haUri: s3://flink-state/orders/ha
            secretRefs: [flink-storage]
```

- **`stream.schema`** uses the same column shape as an expose's `contract.schema`.
  - Every struct, array and map spells out its children (`fields`, `element`, `key` and `value`).
  - `required` defaults to `false`.
  - Map keys must be required strings.
  - Names must be plain SQL identifiers, and may not differ only by case.
- **`stream.format`** encodes the record value:
  - With `json`, a declared field the record lacks reads as null, and an undeclared field is ignored.
  - With `avro-confluent`, the declared schema is the reader schema, and `parameters.flink.source.schemaRegistryUrl` names the registry. Keep the producers' subject FORWARD or FULL compatible (transitive) with what the contract declares: the contract reads the data, so it lags the producers.
- **`stream.topic`** is one Kafka topic name: no pattern and no list.
- **`eventTime.column`** turns a timestamp of precision 3 or less into Flink's event time, with a watermark `delaySeconds` behind it. Flink takes no finer precision. A watermark is not a late-record policy: nothing is quarantined.
- **`parameters.flink.source`** holds the connection only. A `topic`, `format` or `schema` there is refused, with a pointer to `properties.stream`.

## Record shapes

Without a mapping, each output column is read from the stream column of the same name, nested fields included. A flat topic, and a nested topic landed as it is, need no mapping at all: the expose lists the columns it wants.

The output column's type must be the stream's, or a wider type that holds every value: int to long, float to double, a decimal with more precision at the same scale, a timestamp with finer precision. forge-cli casts those itself, in a struct's fields too, but not inside an array or a map.

`properties.mapping` covers every other shape. An entry in `columns` names an output column, or a field of one, and the path it is read from:

```yaml
mapping:
  explode:                      # one output row per element of items
    path: items
    as: item
  columns:                      # only what does not come by name
    - {name: customer_id, from: customer.id}                 # a nested field, lifted
    - {name: country,     from: customer.address.country}
    - {name: channel,     from: "attributes['channel']"}     # a map entry
    - {name: sku,         from: item.sku}                    # a field of the element
    - {name: price,       from: item.price}
```

| To | Write |
|---|---|
| Lift a nested field to a column | `from: customer.address.country` |
| Read a map entry | `from: "attributes['channel']"`: always nullable, because the key may be missing |
| Explode an array into rows | `explode: {path: items, as: item}`, then `item.sku` for a field of a struct element, or `item` for a scalar element |
| Keep the exploded element nested | an output column named like `as` (`item`), of the element's struct type |
| Build a nested output from fields elsewhere | a dotted name: `{name: order.key, from: order_key}`. The struct `order` is built field by field, and the fields you do not list are read from the same path. |
| Read binary as text | `cast: string`, which decodes the bytes as UTF-8. A widening needs no `cast:`, and every other conversion is refused. |

How the static check decides:
- **Struct fields bind by name.** forge-cli writes every column in the expose's order and builds structs field by field, so a reordered or narrower struct never shifts values into the wrong field.
- **A required output must be fed by a path that cannot be null.** A nullable parent struct, a map lookup and a nullable array element can all be null.
- **A struct built from one nullable source struct is null where that struct is.** Its own required fields stay required where the struct is present. The struct itself may not then be declared required.
- **An explode drops a record whose array is null or empty.** A null element becomes a row whose element fields are null.
- **A path is never SQL.** It is a dotted name with `['literal']` map keys, at most 64 steps; anything else is refused without being echoed.

The job's query reads nothing but the stream. Every identifier and literal in it is written by forge-cli. Errors name the expose column and the path:

```text
Managed Flink: Flink build ingest-orders: properties.mapping.columns[0].from: customer has no field adress
Managed Flink: exposes[0].contract.schema.channel: channel is not a column of properties.stream; map channel in properties.mapping.columns
```

## The record key and Kafka metadata

```yaml
stream:
  # ...topic, format and schema as above
  key:
    format: raw                 # raw (one string or binary column), json or avro-confluent
    schema:
      - {name: order_key, type: string}
    # prefix: key_              # when a key field repeats a value field's name
  metadata:
    - {name: kafka_partition, from: partition}
    - {name: kafka_offset,    from: offset}
    - {name: kafka_timestamp, from: timestamp}
    - {name: kafka_headers,   from: headers}
```

- **Key columns** sit next to the value's.
  - A record with no key reads them as null.
  - With `key.prefix`, a key field can share its name with a value field. A Debezium key repeats the value's `id`, for example. A mapping then names the prefixed column.
- **Metadata columns** have fixed types:

  | `from` | Type |
  |---|---|
  | `topic` | string |
  | `partition` | int |
  | `offset` | long |
  | `timestamp` | timestamp_ltz(3) |
  | `timestamp-type` | string |
  | `headers` | map&lt;string, binary&gt; |
  | `leader-epoch` | int |

  All are never null except `leader-epoch`.
- **Uses for metadata columns:**
  - A metadata column can be the event-time column.
  - `{name: trace_id, from: "kafka_headers['trace-id']", cast: string}` reads one header as text.
  - A struct output built from metadata, such as `kafka: {partition, offset, timestamp}`, keeps the Kafka position in one place.

## Fragments

A stream is a value like any other in the contract, so a team can keep one topic's description in a fragment and `$ref` it from every product that reads the topic. The example's `shapes/` directory does this for two contracts, with a `fluid.workspace.yaml` (`ref_root: .`) that lets both reach the shared fragment. The fragment's value schema is a fragment of its own:

```yaml
properties:
  stream:
    $ref: ../fragments/streams/orders.yaml
```

Check a fragment on its own, from `shapes/`. Name the schema version, because a workspace with no root contract gives none:

```bash
fluid validate --schema-version 0.7.7 --fragment streamSource fragments/streams/orders.yaml
fluid validate --schema-version 0.7.7 --fragment schema fragments/streams/orders.value.yaml
```

A mapping kept in its own file is checked the same way, with `--fragment recordMapping`.

`fluid bundle` resolves the refs, and the bundle compiles to the same job.

## A build's own SQL

A build may set `properties.sql` (one `SELECT` from `source_events`) instead of a mapping:
- forge-cli binds its result to the output columns by name, and Flink's planner checks the types in the pod;
- SQL hints (`/*+ ... */`) and semicolons are refused;
- a mapping and SQL together are refused.

That SQL runs with the job's catalog identity, so it can read any table that identity can read, not only the stream. `fluid apply` therefore refuses it unless the operator lists it:

```bash
export FLUID_FLINK_CONTRACT_SQL_ALLOWLIST="commerce.nested-events/ingest-orders@sha256:<digest>"
```

The refusal prints the pinned entry for the SQL it found. All three forms are accepted:
- **Pinned (recommended):** `<product>/<build>@sha256:<digest of the SQL>` approves that SQL and nothing it is later edited into.
- **Build:** `<product>/<build>` approves whatever SQL that build runs.
- **Product:** `<product>` approves every build of the product.

`fluid validate` warns about every build that brings its own SQL.

## Operator settings

A contract names everything about where its job lands: the kube context and namespace, the image, the service account and the Secrets mounted into it. The applier's kubeconfig would grant whatever those name. So `fluid apply` (`--dry-run` included), `fluid diff` and `fluid verify` refuse a deployment until the operator lists its targets. An unset list allows nothing:

```bash
export FLUID_FLINK_KUBE_CONTEXT_ALLOWLIST=development
export FLUID_FLINK_NAMESPACE_ALLOWLIST=data-products
export FLUID_FLINK_IMAGE_ALLOWLIST=registry.example.com/forge-flink   # repository, without :tag and @sha256:
export FLUID_FLINK_SERVICE_ACCOUNT_ALLOWLIST=data-products/flink
export FLUID_FLINK_SECRET_ALLOWLIST=data-products/flink-storage
export FLUID_ACQUISITION_DEPLOYMENT_HOST_ALLOWLIST=catalog.example.com,svc.cluster.local
```

- **Images:**
  - An image entry is an exact repository, or a prefix ending in `/` (`registry.example.com/`).
  - A prefix without the slash is not a prefix: `ghcr.io/acme` does not admit `ghcr.io/acmeevil`.
  - Kubernetes pulls by digest, so the tag never decides what runs.
- **Service accounts and Secrets:** an entry is `name` (in any listed namespace) or `namespace/name`.
- **Hosts the job contacts:**
  - These are the catalog, an OAuth2 token endpoint and any `s3.endpoint` in `catalogProperties`. *(since 0.27.0, [forge-cli #784](https://github.com/Agenticstiger/forge-cli/pull/784))* `fluid apply` also checks each Kafka broker in `source.bootstrapServers` and `source.schemaRegistryUrl`, by the same rule, before a kubectl call.
  - A hostname needs an entry in `FLUID_ACQUISITION_DEPLOYMENT_HOST_ALLOWLIST` whatever it resolves to, because the job resolves it itself, after fluid has checked it. List a parent domain such as `svc.cluster.local` to cover a cluster's services.
  - An IP address needs an entry only when it is public. A link-local address is always refused.
  - There is no topic allowlist: within an allowed broker the contract picks the topic, and the broker's ACLs bound that.
- **Catalog credentials:**
  - A `catalogAuth` variable needs `NAME@host` in `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST` for each host that receives it, before fluid reads it: `LAKEKEEPER_TOKEN@catalog.example.com` for a bearer token.
  - The host must match exactly; a parent domain does not cover it. A bare `NAME` allows every host.
  - An OAuth2 credential needs two entries: one for the token endpoint, which must be `https://`, and one for the catalog, which receives the token minted from it.
  - `fluid verify` sends the token from your machine, where a loopback host (`localhost`, `127.0.0.0/8`, `::1`) is your own machine and needs neither entry. `db.localhost` is not loopback.
  - `fluid apply` sends the token from the pod, where `localhost` is the pod itself or a sidecar injected into it, so there a loopback host needs its `NAME@host` entry too.
- **Catalog text:** no other catalog property may start with `env:` or contain `${` or a control character, because Iceberg would resolve it from the job's environment. Only `catalogAuth` references a variable.
- **Which command checks what:**
  - `fluid apply` (a dry run included), `fluid diff` and `fluid verify` check the deployment targets.
  - `fluid apply` also checks the catalog, the token endpoint, the `s3.endpoint`, the Kafka brokers in `source.bootstrapServers`, the `source.schemaRegistryUrl` and the contract's own SQL, and pairs the `catalogAuth` variable with each host that receives it, loopback included.
  - `fluid verify` also checks the catalog and the token endpoint, because it sends the credential from its own environment; a loopback host needs no pairing there.

All of these are read from the operator's environment, a shell or a CI variable. A project's `.env` cannot set them: see [What a project's `.env` may set](./project-dotenv-trust.md). Checkpoint, savepoint, HA and warehouse locations are not on these lists; scope them with the permissions of the credentials in the allowed Secrets.

## Workflow

```bash
fluid validate contract.fluid.yaml
fluid generate flink contract.fluid.yaml --out runtime/flink
fluid diff contract.fluid.yaml --exit-on-drift --out runtime/drift.json
fluid plan contract.fluid.yaml --mode amend --out runtime/plan.json
fluid apply runtime/plan.json --mode amend --yes
fluid verify contract.fluid.yaml --strict --out runtime/delivery.json
```

- **Offline steps:** `generate flink`, `plan` and `apply --mode dry-run` never contact the cluster, the catalog or the registry.
- **In the pod:** when the job starts, its runner creates the namespace and table if they are missing, then compares the table with the contract and has Flink's planner check the query. Only then does it submit the job.
- **Image:** replace the example's all-zero image digest and development endpoints before deploying. The image must contain forge-cli's SQL runner and the pinned connectors; a plain Flink image is not enough. Use the same `--mode` for plan and apply. Bundle and plan digests are bound before any Kubernetes write.
- **`diff`** compares the live deployment with the last-applied specification.
  - An intentional change in the next plan is pending, not drift. New deployments are pending too.
  - A missing baseline or an unreadable cluster is an error, never a clean result.
  - It covers the operator spec. `verify` covers the table's schema and commits.
- **`apply`** reports running or suspended, not delivered.
- **`verify`** also checks a checkpoint through the Kubernetes service proxy, and loads the catalog's schema and snapshot independently.
  - It waits up to 120 seconds for fresh evidence (`--streaming-timeout`; `0` checks once).
  - An idle stream may outlast `maxSnapshotAgeSeconds`, so set that budget from the product's delivery expectations.

## Partitioning

`icebergConfig.partitionSpec` may use identity partitions only (`transform: identity`). Iceberg's transforms (year, month, day, hour, bucket, truncate) are hidden partitioning, which Flink SQL cannot declare: Iceberg's Flink DDL partitions by plain columns, and `PARTITIONED BY (days(col))` does not parse. `fluid validate` refuses those transforms. To use one, create the table with that partition spec before the job runs, and leave it out of the contract. The job's `CREATE TABLE IF NOT EXISTS` then leaves the table alone. The runner compares only the columns, so the table's columns, their order and their nullability must match the contract exactly. The live lane does not cover a table created this way.

## Schema changes and fluid diff

The output table is created with `CREATE TABLE IF NOT EXISTS`. Before every start, the runner compares the existing table's schema with the contract, recursively, and refuses a mismatch. Nothing is migrated automatically: an added column, a rename, a change of requiredness or a type change needs an explicit Iceberg migration and review. The check does not lock the table against concurrent DDL.

`fluid diff --baseline <old contract>` reads `properties.stream` as a reader schema:

| Change | Severity |
|---|---|
| Another topic, value format, key format or metadata source | breaking |
| A field the job newly requires, or one that becomes required | breaking |
| A narrowed or changed field type | breaking (a widening is non-breaking) |
| A field the job stops reading | non-breaking (an output still reading it fails `fluid validate`) |
| An explode added, removed or moved | breaking: it changes how many rows a record becomes |
| An output read from another path or with another conversion | non-breaking, for review |
| A build that starts running its own SQL, or changes it, including a new or renamed build | breaking |
| A build that declares or drops its stream | info |

The expose rules still apply to the output table.

## Credentials and operations

- **Required deployment fields:** `name`, `namespace`, `context`, `image`, `serviceAccount`, `checkpointUri`, `savepointUri` and `haUri`.
- **kubectl:** it uses `deployment.context` explicitly, with bounded timeouts, ownership checks, and server-side apply that never takes over a conflict.
- **Permissions:**
  - The CLI needs read and write on the FlinkDeployment and ConfigMap resources, and read on the service proxy.
  - The Flink service account needs the usual Kubernetes HA permissions.
- **`deployment.secretRefs`** injects existing Kubernetes Secrets through `envFrom`. Configure object-store credentials or workload identity outside the contract. Never put credential values in SQL, URIs or generated resources.
- **`catalogAuth`:**
  - `{type: oauth2, credentialEnv: ICEBERG_CREDENTIAL, oauth2ServerUri: https://identity.example/token, scope: catalog}` reads `client_id:client_secret` from the variable.
  - `{type: bearer, tokenEnv: ICEBERG_TOKEN}` reads a token.
  - The job resolves the variable in its pod. `fluid verify` resolves it in its own environment. Neither copies a credential to the other.
- **Suspension:** `deployment.state: suspended` suspends the job, and `running` resumes it through the operator. A failed savepoint is never replaced with a fresh start.
- **`--validate-only`:** the runner's `--validate-only` mode still runs the setup DDL, and may create a namespace or table. It is not side-effect free.

## What this does not certify

The `Flink Iceberg preview` workflow runs on every relevant pull request:
- strict mypy checks;
- a 90% coverage floor on the streaming modules.

Its manual `run_live` input runs the generated jobs in Docker, through Kafka (Redpanda), Flink, an Iceberg REST catalog and an S3 mock. It needs no cloud account or Kubernetes cluster. That run:
- **checks nested values and recovery:**
  - compares every value of 200 records with five levels of nested structs, arrays and maps, nulls, empty containers, exact decimals and timestamps;
  - restarts the task manager in the middle of the run;
  - refuses an existing table whose nested schema no longer matches.
- **checks both record shapes:** a flattened product and a nested reshape run from one shared stream fragment, fed records with a key and a header. PyIceberg reads both back, and they are compared with what was produced.
- **plans the generated queries:** the examples' queries, and the mappings hardest on Flink's validator, are EXPLAINed in the runtime image's own Flink.

This is not Kubernetes lifecycle or production HA certification. The operator's apply, readiness, ownership and drift paths are unit-tested. A real install, upgrade, savepoint and resume, job-manager loss and Kubernetes failure injection are still open gates. The Docker fixture's local checkpoints do not prove durable S3 HA.

Not implemented:
- **Changes and ordering:** CDC, upsert and delete streams (the Debezium formats); late-record routing or quarantine; automatic Iceberg schema or partition evolution.
- **Formats:** protobuf; a raw value payload.
- **Mapping:** keeping records whose array is empty; exploding a map, or more than one array in a build; filtering events by type.
- **Kafka and the registry:** registry version pinning and compatibility checks; Kafka SASL/TLS settings.
- **Outputs and storage:** nested policy and quality enforcement; more than one output per build; non-S3 storage; catalogs that name the warehouse instead of giving its URI.

Root governance and access policies, and output or nested quality and policy rules, are refused rather than advertised as enforced.

## See also

- [Source-aligned acquisition](./source-aligned-acquisition.md): batch and CDC ingestion through the acquisition engines.
- [Environment variables](./environment-variables.md#managed-flink-preview): every variable this lane reads.
- [What a project's `.env` may set](./project-dotenv-trust.md): why the operator settings cannot come from a project file.
