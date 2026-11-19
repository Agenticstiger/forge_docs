---
title: Spark to Iceberg on AWS (preview)
description: Declare a Kafka stream, or batch SQL over catalog tables, in the contract; forge-cli compiles the Spark job, provisions its infrastructure with OpenTofu on EMR Serverless, Glue, EMR on EC2 or EMR on EKS, and starts and reconciles its runs.
---

# Spark to Iceberg on AWS (preview)

*(since 0.31.0, [forge-cli #902](https://github.com/Agenticstiger/forge-cli/pull/902), [forge-cli #903](https://github.com/Agenticstiger/forge-cli/pull/903), [forge-cli #904](https://github.com/Agenticstiger/forge-cli/pull/904), [forge-cli #912](https://github.com/Agenticstiger/forge-cli/pull/912), [forge-cli #918](https://github.com/Agenticstiger/forge-cli/pull/918), [forge-cli #919](https://github.com/Agenticstiger/forge-cli/pull/919), [forge-cli #924](https://github.com/Agenticstiger/forge-cli/pull/924), [forge-cli #927](https://github.com/Agenticstiger/forge-cli/pull/927), [forge-cli #934](https://github.com/Agenticstiger/forge-cli/pull/934), [forge-cli #950](https://github.com/Agenticstiger/forge-cli/pull/950))*

A build with `engine: spark` and `parameters.spark` (under `builds[].properties`) lands records in an Iceberg table that the Glue catalog holds (*(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* With `runtime: local`, in an Iceberg REST catalog: see [Running a build on this machine](#running-a-build-on-this-machine)):

- The contract says which Kafka topic the job reads, or which SQL it runs over catalog tables, and how the result becomes the rows of the output expose.
- forge-cli compiles that into a `job.json` and checks every output column against it before anything deploys.
- OpenTofu provisions what the job needs: its artifacts, role, logs and, where the contract asks for it, the EMR Serverless application or the Glue job.
- `fluid apply` starts the job and keeps a streaming one running. A scheduled one runs through `fluid apply <contract> --mode amend-and-build --build-id <id>`, the path every scheduled build takes: see [Scheduled Spark builds](./airflow.md#scheduled-spark-builds).

The lane is opt-in: the contract declares `fluidVersion: "0.7.7"`, the preview schema, and the build sets `parameters.spark`. It reads the same `properties.stream` and `properties.mapping` as the [managed Flink lane](./managed-flink-iceberg.md), compiled to Spark SQL. Everything else is unchanged.

## What is supported

| Surface | Preview behaviour |
|---|---|
| Runtimes | EMR Serverless, AWS Glue (Glue 5.0, Spark 3.5), EMR on EC2 and EMR on EKS. One runner file runs unchanged on all four. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* A fifth, `local`, is `spark-submit` on the machine `fluid apply` runs on, and the same runner file serves it: see [Running a build on this machine](#running-a-build-on-this-machine). |
| Modes | `streaming`: a Kafka topic, appended to the table. `batch`: SQL over catalog tables, which overwrites the partitions it writes. |
| Records | `properties.stream`: one topic, the value as `json` or `avro-confluent`, as on the Flink lane. |
| Mapping | `properties.mapping`, as on the Flink lane, plus `maskAtIngest: hash` on a column. |
| Output | One Iceberg expose in the Glue catalog, at the warehouse path forge derives from the binding. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* With `runtime: local`, one table in an Iceberg REST catalog on `platform: local`. |

## Declaring the build

This contract reads a topic from MSK and hashes one column. Checked on 0.31.0: with the operator settings below, `fluid validate` passes with no warning and `fluid generate iac` writes the module.

```yaml
fluidVersion: "0.7.7"
kind: DataProduct
id: commerce.orders-stream
name: Orders stream (Kafka to Iceberg on AWS)
metadata:
  layer: Bronze
  owner:
    team: commerce-data
builds:
  - id: ingest-orders
    engine: spark
    pattern: embedded-logic
    outputs: [orders]
    properties:
      stream:
        kind: kafka
        topic: commerce.orders
        format: avro-confluent
        registry:
          kind: confluent
          url: https://schema-registry.example.internal
          subject: commerce.orders-value
          version: latest
          auth:
            secretRef: env://SCHEMA_REGISTRY_AUTH
        trigger:
          processingTime: PT1M
        watermark:
          column: event_time
          delay: PT10M
        startingOffsets: earliest
        schema:
          - name: order_id
            type: string
            required: true
          - name: customer_email
            type: string
          - name: amount
            type: decimal(18,2)
          - name: event_time
            type: timestamp_ltz
      mapping:
        columns:
          - name: customer_email_hash
            from: customer_email
            maskAtIngest: hash
      parameters:
        spark:
          runtime: emr-serverless
          mode: streaming
          applicationId: 00fexampleapp0001
          maskKeySecretArn: arn:aws:secretsmanager:eu-west-1:000000000001:secret:orders-mask-key-AbCdEf
          source:
            mskClusterArn: arn:aws:kafka:eu-west-1:000000000001:cluster/commerce-events/0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d-1
            auth: msk-iam
            groupIdPrefix: fluid-commerce-orders
          sparkConf:
            spark.sql.shuffle.partitions: "8"
exposes:
  - exposeId: orders
    kind: table
    binding:
      platform: aws
      format: iceberg
      location:
        database: commerce
        table: orders
        bucket: commerce-lake
        path: iceberg/commerce/orders/
        region: eu-west-1
    contract:
      schema:
        - name: order_id
          type: string
          required: true
        - name: customer_email_hash
          type: string
        - name: amount
          type: decimal(18,2)
        - name: event_time
          type: timestamp_ltz
```

Bucket names are global: write a bucket you own in place of `commerce-lake`.

### `parameters.spark`

| Field | Meaning |
|---|---|
| `runtime` | Required: `emr-serverless`, `emr-ec2`, `emr-eks`, `glue` or `local`. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* `local` runs `spark-submit` on the machine `fluid apply` runs on, and ignores `applicationId`, `clusterId`, `virtualClusterId`, `releaseLabel`, `glueVersion` and `executionRoleArn`: see [Running a build on this machine](#running-a-build-on-this-machine). |
| `mode` | `streaming` or `batch`. It defaults to `streaming` when the build declares `properties.stream`, and to `batch` otherwise. |
| `applicationId` | EMR Serverless only: an existing application. |
| `clusterId` | EMR on EC2 only: an existing cluster. A transient cluster is refused for now. A cluster that runs on Spot needs the layout in [Running EMR on EC2 on Spot](#running-emr-on-ec2-on-spot). |
| `virtualClusterId` | EMR on EKS only, and required there: an existing virtual cluster. |
| `glueVersion` | Glue only. Default `5.0`. |
| `releaseLabel` | The EMR release, on the EMR runtimes. Default `emr-7.12.0`. *(since 0.33.0, [forge-cli #984](https://github.com/Agenticstiger/forge-cli/pull/984))* Each runtime takes its own form, and the default on EMR on EKS is `emr-7.12.0-latest`: see [Release labels](#release-labels). |
| `executionRoleArn` | An existing role the job runs as. See [Roles](#roles-and-who-lists-what). |
| `maskKeySecretArn` | The Secrets Manager ARN of the key `maskAtIngest: hash` uses. A mapping that masks a column needs it. |
| `sparkConf` | Spark settings, limited to sizing and tuning unless the operator lists more. See [Spark settings](#spark-settings). |
| `source` | The Kafka connection. Exactly one of `bootstrapServers` or `mskClusterArn`; `auth` is `msk-iam` (the default with an ARN) or `none` (the default with brokers); `groupIdPrefix`. |

An MSK source needs no broker list: forge looks the brokers up from the cluster ARN when it applies, and fills them into `job.json` (the SASL/IAM list for `msk-iam`, the TLS list for `auth: none`). A plaintext listener is named in `bootstrapServers`.

### Release labels

*(since 0.33.0, [forge-cli #984](https://github.com/Agenticstiger/forge-cli/pull/984))* Each EMR runtime takes its own form of `releaseLabel`:

| Runtime | Form | Default | What forge does with it |
|---|---|---|---|
| `emr-serverless` | `emr-X.Y.Z` | `emr-7.12.0` | Sets the release of the isolated application it creates. An existing `applicationId` has its own release, so there the label only goes into the config hash. |
| `emr-ec2` | `emr-X.Y.Z` | `emr-7.12.0` | Sends it nowhere: the cluster has its own release. It goes into the config hash. |
| `emr-eks` | `emr-X.Y.Z-latest` or `emr-X.Y.Z-YYYYMMDD` | `emr-7.12.0-latest` | Sends it as the release of each job run it starts. |

On EMR on EKS the label names an image of a release. AWS's release page lists `emr-X.Y.Z-latest` and `emr-X.Y.Z-YYYYMMDD`, the second for a dated image. forge also accepts a variant between the release and the suffix, such as `emr-7.12.0-java11-latest`, and checks only that it is lower-case letters and digits, in one or more segments separated by hyphens. A Glue build takes `glueVersion`, and `fluid validate` refuses a `releaseLabel` on it. The label is part of the config hash, so changing it on a running stream restarts the stream.

`fluid validate` refuses a form the runtime does not take. An `emr-eks` build with `releaseLabel: emr-7.12.0` (run on forge-cli `main`):

```text
❌ Invalid FLUID contract (2 error(s)) (schema v0.7.7)
...
 1. builds[0].properties.parameters.spark.releaseLabel: 'emr-7.12.0' does not match '^emr-[0-9]+\\.[0-9]+\\.[0-9]+(-[a-z0-9]+)*-(latest|[0-9]{8})(?![\\s\\S])'
 2. Spark build ingest-orders: parameters.spark.releaseLabel: runtime emr-eks takes emr-X.Y.Z-latest or emr-X.Y.Z-YYYYMMDD (e.g. emr-7.12.0-latest)
```

An `emr-serverless` or `emr-ec2` build with `releaseLabel: emr-7.12.0-latest` gets two lines of the same shape: the first shows the plain pattern, `^emr-[0-9]+\\.[0-9]+\\.[0-9]+(?![\\s\\S])`, and the second says `runtime emr-serverless takes emr-X.Y.Z (e.g. emr-7.12.0)`, with `emr-ec2` for an `emr-ec2` build. In 0.32.0 and earlier every EMR runtime took only the plain form: an `emr-eks` build with `emr-7.12.0` passed `fluid validate`, and `emr-7.12.0-latest` was refused with `expected emr-[0-9]+\.[0-9]+\.[0-9]+`.

An `emr-eks` build with no `releaseLabel` gets a new config hash, because its default moved from `emr-7.12.0` to `emr-7.12.0-latest`: plan it again. The config hash of an `emr-serverless` or an `emr-ec2` build does not change.

### Stream settings

*0.7.7 preview.* A `properties.stream` has these fields besides the topic, format and schema of the Flink lane:

| Field | Meaning |
|---|---|
| `trigger` | `{processingTime: <ISO duration>}` for a micro-batch every interval, or `{availableNow: true}` for a run that processes what is there and ends. Unset, forge uses half the expose's `qos.freshnessSLO`, and sets no trigger when the expose has none. |
| `watermark` | `{column, delay}`. The column must be a top-level `timestamp_ltz`: Spark 3.5 does not keep a watermark on `timestamp` (an NTZ type). |
| `checkpoint` | An `s3://` prefix. It defaults to `s3://<bucket>/_checkpoints/<product>/<build>/`, at the bucket root and never under the table, where Iceberg's orphan-file cleanup would delete it. When forge creates the job's role, a declared checkpoint must sit under `s3://<bucket>/_checkpoints/<product>/`; one outside it is refused (`spark-checkpoint-scope`). |
| `startingOffsets` | `earliest` or `latest`, for a stream with no checkpoint yet. |
| `maxOffsetsPerTrigger` | *(since 0.34.0, [forge-cli #1015](https://github.com/Agenticstiger/forge-cli/pull/1015))* The most Kafka records one micro-batch reads: a whole number from 1 to 9223372036854775807, split across the topic's partitions by their backlog. Unset, a batch reads everything that is waiting. A Spark stream only: managed Flink refuses the key. See [Bounding a batch](#bounding-a-batch). |
| `registry` | The schema registry of an `avro-confluent` stream. On a forge Spark build only `kind: confluent` is accepted: `kind: glue` is refused. Its `auth` takes `env://` or `aws-sm://` references only. See [Schema registry](./schema-registry.md). |
| `deadLetter` | *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* Where a record the stream cannot land goes, instead of failing the stream: a table beside the output (`sink: table`, the default) or a Kafka topic (`sink: topic`), with `maxRecordsBeforeAbort` (default 10000) and `alertOn: [schema_violation]`. An Avro stream is refused. See [Dead letters](#dead-letters). |

### Bounding a batch

*(since 0.34.0, [forge-cli #1015](https://github.com/Agenticstiger/forge-cli/pull/1015))* A stream that has been stopped, or that starts from `earliest`, finds a backlog, and without a limit its first batch reads all of it. `properties.stream.maxOffsetsPerTrigger` is the most records one micro-batch reads. forge passes it to Spark's Kafka source, which splits it across the topic's partitions by their backlog, so the stream catches up in batches of bounded size and memory. It holds for a `trigger.availableNow` run as well: the run ends once the backlog is read, in as many batches as the limit needs.

```yaml
properties:
  stream:
    startingOffsets: earliest
    maxOffsetsPerTrigger: 5000
```

The value is a whole number from 1 to 9223372036854775807, the largest that Spark reads as a long. `fluid validate` refuses anything else: `0`, a negative number, `true`, a string such as `"5"`, a number with a fraction and a number above the maximum. `5.0` is refused too, by the Spark check alone. For `0` it prints the schema's error and the Spark check's:

```text
❌ Invalid FLUID contract (2 error(s)) (schema v0.7.7)
Validation completed in 0.008s

Validation Errors:
==================
 1. builds[0].properties.stream.maxOffsetsPerTrigger: 0 is less than the minimum of 1
 2. Spark: Spark build ingest-orders: properties.stream.maxOffsetsPerTrigger: expected a whole number, at least 1
```

Unset, the `source` block of `job.json` has no `maxOffsetsPerTrigger` key and the Kafka source has no limit. Set to 5000, the runner gives the source these options, with its `kafka.*` connection options left out. `failOnDataLoss` is in them with or without the limit: see [the Spot checklist](#running-emr-on-ec2-on-spot).

```text
{"subscribe": "commerce.orders", "startingOffsets": "earliest", "includeHeaders": "false", "failOnDataLoss": "true", "maxOffsetsPerTrigger": "5000", "groupIdPrefix": "fluid-commerce-orders"}
```

Setting, changing or removing the limit changes the job config, and with it the config hash, so a running stream restarts once on its next apply, on its checkpoint (see [Starting and reconciling runs](#starting-and-reconciling-runs)). A forge-cli without this change refuses the key: 0.32.0 prints `builds[0].properties.stream: Additional properties are not allowed ('maxOffsetsPerTrigger' was unexpected)`. Managed Flink refuses it as well, with `Managed Flink: Flink build ingest-orders: properties.stream: unsupported field(s) ['maxOffsetsPerTrigger']`.

The outputs are from forge-cli's `fluid validate` and the Spark runner's own option function on a contract of this page's shape (a JSON stream from MSK to an Iceberg table on EMR Serverless) with the key added, and, for 0.32.0, from the pinned CLI. No Kafka source was run: the split across partitions is what forge-cli's schema says Spark does.

### Dead letters

*(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* A Spark stream can send the records it cannot land to a dead-letter table or a Kafka topic, and keep running until a limit you set. A record whose value or key is not the declared JSON, or that lacks a required field, no longer fails the stream by itself: the stream stops only past `maxRecordsBeforeAbort` (see [When the stream stops](#when-the-stream-stops)). Without `properties.stream.deadLetter`, or with `enabled: false`, the first such record fails the stream.

#### What a dead letter is

The job decodes the value, and a key declared as `json`, in Spark's permissive mode, and keeps the text of a record it cannot decode in a field named `fluid_corrupt_record`. A stream that declares a field of that name is refused. Each record gets the first reason that applies, checked in this order: the value's decoding, the key's decoding, then the required fields in the order of the output's source query.

| Reason | When |
|---|---|
| `the value is not JSON of the declared fields and types` | The value does not decode as the declared fields and types. |
| `the key is not JSON of the declared fields and types` | The same for a key declared as `json`. |
| `required field <name> is null` | A field declared `required: true` is null. `<name>` is the field's dotted path, such as `customer.email`; `[]` stands for an array element or a map value, as in `items[].sku`; the name of a key field starts with `key `. A field inside a struct counts only when the struct is there. |

A reason is fixed text built from field names. It holds no value from the record. A record without a reason goes to the output as it did before, through the output's own query, which reads only those records. An Avro stream's dead letters are refused for now: the decoder's permissive mode would also turn a schema registry outage into dead letters.

#### Settings

The contract in [Declaring the build](#declaring-the-build) reads Avro, so a `deadLetter` block in it is refused. With `format: json` and no `registry`, the same build takes this block under `properties.stream`:

```yaml
        deadLetter:
          sink: table
          maxRecordsBeforeAbort: 1000
          alertOn: [schema_violation]
```

| Field | Meaning |
|---|---|
| `enabled` | `true` by default. `false` turns the dead letters off, and a record that cannot land fails the stream. An overlay can set it per environment. |
| `sink` | `table` (the default) or `topic`. An empty block, `deadLetter: {}`, is a table sink with the defaults. |
| `table` | A table sink only. The table's name in the output's database: a letter or an underscore first, then letters, digits and underscores, at most 255 characters. It defaults to `<output table>__dead_letter`. The output's own table name is refused. |
| `topic` | A topic sink only, and required there. The topic's name, on the cluster the stream reads: 1 to 249 characters of letters, digits, `.`, `_` and `-`, and not `.` or `..`. The topic must exist: the job writes to it and creates nothing. The stream's own topic is refused. |
| `maxRecordsBeforeAbort` | A whole number from 0. Default `10000`. The stream stops once it has sent more dead letters than this since the job started: see [When the stream stops](#when-the-stream-stops). |
| `alertOn` | A list of distinct values. `schema_violation` is the one value: the job logs a `dead_letter_alert` line for each micro-batch that sends any dead letter. Default none. |

Any other field is refused, as is a `topic` sink with no `topic` or with a `table`, and a `topic` on a table sink. The page's contract with `format: json`, no `registry` and this block passes `fluid validate` with no warning, with the operator settings of [Roles and who lists what](#roles-and-who-lists-what). The compiled settings are in `job.json`, which `fluid generate artifacts --emit spark` writes. `raw` is `false` here because the contract masks a column: see [Masked builds](#masked-builds). The dead letters' checkpoint is inside the stream's.

```bash
jq '{deadLetter, check: .sql.check, value: .source.value}' artifacts/spark/ingest-orders/job.json
```

```text
{
  "deadLetter": {
    "alertOn": [
      "schema_violation"
    ],
    "checkpoint": "s3://commerce-lake/_checkpoints/commerce.orders-stream/ingest-orders/dead-letter/",
    "maxRecordsBeforeAbort": 1000,
    "raw": false,
    "sink": "table",
    "table": "commerce.orders__dead_letter"
  },
  "check": "SELECT *,\n  CASE\n    WHEN `value`.`fluid_corrupt_record` IS NOT NULL THEN 'the value is not JSON of the declared fields and types'\n    WHEN `value`.`order_id` IS NULL THEN 'required field order_id is null'\n  END AS `fluid_error`\nFROM `kafka_records_decoded`",
  "value": {
    "corruptRecord": "fluid_corrupt_record",
    "format": "json",
    "schema": "`order_id` STRING, `customer_email` STRING, `amount` DECIMAL(18,2), `event_time` TIMESTAMP, `fluid_corrupt_record` STRING"
  }
}
```

0.32.0 refuses the block, run on the contract with this block (`orders.fluid.yaml`):

```bash
fluid validate orders.fluid.yaml
```

```text
❌ Invalid FLUID contract (2 error(s)) (schema v0.7.7)
Validation completed in 0.013s

Validation Errors:
==================
 1. builds[0].properties.stream: Additional properties are not allowed ('deadLetter' was unexpected)
 2. Spark: Spark build ingest-orders: properties.stream: unsupported field(s) ['deadLetter']
```

The `deadLetter` block is part of the config hash, so adding, changing or removing it restarts a running stream on its checkpoint, as any other change does: see [Starting and reconciling runs](#starting-and-reconciling-runs). A stream with `enabled: false` compiles to the job config it had without the block.

#### The table

A table sink writes an Iceberg v2 table in the output's database, with these columns:

| Column | Type | Holds |
|---|---|---|
| `error` | string | The reason. |
| `raw_value` | binary | The record's value as it was read. Null for a build that masks fields. |
| `raw_key` | binary | The record's key as it was read. Null for a build that masks fields. |
| `kafka_topic` | string | The record's topic. |
| `kafka_partition` | int | Its partition. |
| `kafka_offset` | bigint | Its offset. |
| `kafka_timestamp` | timestamp | Its Kafka timestamp. |
| `dead_lettered_at` | timestamp | `current_timestamp()` when the dead-letter query ran. |

The table is not partitioned. Its location is beside the output's, not inside it: the output's parent prefix and the table's name, so `iceberg/commerce/orders/` has `iceberg/commerce/orders__dead_letter/` beside it. Inside the output's location, an Iceberg orphan-file cleanup of the output would delete the files of the dead-letter table.

#### The topic

A topic sink sends each dead letter to a topic on the cluster the stream reads, with the stream's own connection settings. The record's value is `raw_value`. In 0.33.0 its key is `raw_key`, the record's own key, and it carries these headers, each value as text:

| Header | Value |
|---|---|
| `__connect.errors.topic` | The record's topic. |
| `__connect.errors.partition` | Its partition. |
| `__connect.errors.offset` | Its offset. |
| `__connect.errors.connector.name` | `<product>/<build>`. |
| `__connect.errors.stage` | `VALUE_CONVERTER` when the reason starts with `the value`, `KEY_CONVERTER` when it starts with `the key`, and `TRANSFORMATION` otherwise. |
| `__connect.errors.exception.message` | The reason. |

*(since 0.34.0, [forge-cli #1015](https://github.com/Agenticstiger/forge-cli/pull/1015))* The key is where the record came from, `<topic>-<partition>@<offset>`, as in `commerce.orders-2@41874`, and the record's own key moves to one more header, which holds the bytes it was read as and not text:

| Header | Value |
|---|---|
| `fluid.dead-letter.raw-key` | The record's own key. Null for a record that had no key, and for a build that masks fields. |

The record's Kafka timestamp and `dead_lettered_at` are not sent. A topic receives each batch at least once. In 0.34.0, a batch that is sent again after a failure carries the same keys, so a consumer drops repeats by key, and on a topic with `cleanup.policy=compact` a record sent twice is kept once when Kafka compacts the log. A record with a null value is a delete marker on a compacted topic ([Kafka's log compaction](https://kafka.apache.org/documentation/#compaction)). The dead letters of a [masked build](#masked-builds) have no value, and neither has the dead letter of a source record that had none, so send those to a topic that deletes by retention.

#### How the records land

- **The output keeps its own query.** It reads the records that have no reason and writes them with Iceberg's streaming sink, as without dead letters.
- **The dead letters are a second query.** It reads the topic through a source of its own, with the stream's trigger, and has its own checkpoint, `dead-letter/` inside the stream's checkpoint prefix. The job's role already reads and writes that prefix: see [What the job's role may do in S3](#what-the-job-s-role-may-do-in-s3).
- **A table gets each batch once.** The job appends a batch with the dead-letter query's id and the batch id in the snapshot's summary. A batch the job replays after a failure finds its own snapshot and is not appended again. The query id is kept in the checkpoint, so a new checkpoint is a new id. The check reads the table's retained snapshots, so when `expire_snapshots` removes the snapshot of a batch between its failure and its replay, the replay appends the batch again. Iceberg's own streaming sink has the same limit: it looks for the last batch its query committed in the table's retained snapshots (read in the source of Iceberg 1.10.0, `SparkWrite`).
- **Dead letters added to a stream that exists start where the output resumes.** The new query has no checkpoint, so it starts at the end of the output's last committed batch, or where the output's source started when no batch is committed. A partition the topic gained since is read from its start. A record that had stopped the stream is therefore a dead letter once the block is added: the output refuses it and the dead letters take it. When the output has no checkpoint either, the job waits for the output's source to write its starting offsets. If the output's query ends, or 300 seconds pass, before it writes them, the dead letters start from `startingOffsets` and the job logs `dead_letters_start_unknown`. A dead-letter checkpoint that exists is resumed as it is.

#### When the stream stops

The job counts the dead letters it sends. After it has landed a batch, it fails when the count is more than `maxRecordsBeforeAbort`, so the batch that crossed the limit is in the table or the topic before the stream stops. With `0`, the first dead letter stops the stream, after it has landed. The count belongs to the job: it starts at 0 each time the job starts. The job fails with this message, raised as `DeadLetterAbort`, where the numbers are the job's:

```text
1001 records went to the dead letters since the stream started, past maxRecordsBeforeAbort 1000; the stream is stopped
```

With `alertOn: [schema_violation]`, the job writes a line like this one to its standard output for each batch that sends dead letters:

```text
{"forge_spark_runner": "dead_letter_alert", "reason": "schema_violation", "records": 600}
```

`fluid apply` treats the stopped job as a failed run, like any other (on EMR Serverless, after the retries that [the reconcile table](#starting-and-reconciling-runs) describes). With the same config hash it does not start the job again. It names the run and its state, and the message says: `It is not started again with the same config, which would fail the same way: fix the cause and change the build, and fluid apply starts the new config`. A change to the build is a change to the config hash, and a new `maxRecordsBeforeAbort` is one: `fluid plan` writes a new `configHash` for it in the plan's `spark.reconcile` action. The next `fluid apply` then starts the job on the same checkpoint. *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* On EMR on EC2, Glue and a local build, a job that stopped at the limit is a stream that died, and `fluid apply` and `--mode reconcile` start it again on its checkpoint within the [restart budget](#the-restart-budget). The count belongs to the job, so it starts at 0 again in each restart, and the budget bounds the restarts.

#### Masked builds

A build that masks a column at ingest (`maskAtIngest`, see [`maskAtIngest: hash`](#maskatingest-hash)) keeps no raw bytes, because they would hold the masked fields in clear. Its dead letters store the reason, the record's topic, partition, offset and timestamp, and `dead_lettered_at`, and `raw_value` and `raw_key` are null. A topic sink reads the same two columns, so the value it sends is null and, in 0.33.0, its key is null too, and the headers carry the rest. *(since 0.34.0, [forge-cli #1015](https://github.com/Agenticstiger/forge-cli/pull/1015))* The key of every dead letter is `<topic>-<partition>@<offset>`, a masked build's included, and the header `fluid.dead-letter.raw-key` is null. The topic, partition and offset find the record in Kafka while the topic still retains it.

#### What is refused

`fluid validate` refuses the first group:

| Case | Message |
|---|---|
| An Avro `value` or `key` | `properties.stream.deadLetter: an Avro stream's dead letters are not supported yet: the decoder's permissive mode would also turn a schema registry outage into dead letters` |
| `topic` equal to the stream's own | `properties.stream.deadLetter.topic: the stream's own topic; the stream would read its dead letters again` |
| `table` equal to the output's table | `properties.stream.deadLetter.table: the dead letters need a table of their own` |
| A `topic` sink that names a `table` | `properties.stream.deadLetter: a topic sink names its topic, and no table` |
| A declared field named `fluid_corrupt_record` | `properties.stream.deadLetter: the stream declares a field named fluid_corrupt_record, which the runner keeps a record's undecoded text in; rename it` |
| The [managed Flink lane](./managed-flink-iceberg.md) | `properties.stream: unsupported field(s) ['deadLetter']` |

The messages are printed after `Spark build <id>: `, or `Flink build <id>: ` for the Flink lane. A `sink` that is not `table` or `topic`, an `alertOn` value other than `schema_violation`, a negative `maxRecordsBeforeAbort` and an unknown field fail the schema check, which names the field. An Avro stream, as `fluid validate` prints it with the registry's own two warnings silenced by its two operator variables:

```bash
FLUID_ACQUISITION_DEPLOYMENT_HOST_ALLOWLIST=schema-registry.example.internal FLUID_ACQUISITION_SECRET_REF_ALLOWLIST=SCHEMA_REGISTRY_AUTH@schema-registry.example.internal fluid validate orders-avro.fluid.yaml
```

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.7)
Validation completed in 0.035s

Validation Errors:
==================
 1. Spark: Spark build ingest-orders: properties.stream.deadLetter: an Avro stream's dead letters are not supported yet: the decoder's permissive mode would also turn a schema registry outage into dead letters
```

`fluid validate` passes the next group, and `fluid generate iac` refuses it, with the error kind `spark-dead-letters-table-unsupported` (`ERR_UNSUPPORTED_BINDING`). It concerns a table sink only, because the table needs a place and a rule of its own:

| Case | What the message says |
|---|---|
| The output's location is its bucket's root | `the output's location is its bucket's root, and a table of the dead letters' own would sit inside it` |
| `registerLocation: true` on a location forge registers with Lake Formation | `forge registers the output's location with Lake Formation (registerLocation), and the dead letters' location would need a registration of its own, which forge does not emit yet` |
| The expose's `lifecycle` has `expire: true` | `the output's lifecycle expires its objects, and the rule would not reach the dead letters' table, which holds the records' raw bytes` |

Each carries the remediation `Send the dead letters to a topic (deadLetter.sink: topic), whose retention is the topic's.` In forge-cli's tests, an output with no `bucket` (the account's shared bucket, which forge does not register) keeps its table. For the bucket root:

```bash
fluid generate iac bucket-root.fluid.yaml --out iac-x 2>/dev/null
```

```text
❌ unsupported_binding  [ERR_UNSUPPORTED_BINDING]
  kind: spark-dead-letters-table-unsupported
  error: Spark build ingest-orders: properties.stream.deadLetter writes a table of its own beside the output, and the output's location is its bucket's root, and a table of the dead letters' own would sit inside it.
  remediation: ["Send the dead letters to a topic (deadLetter.sink: topic), whose retention is the topic's."]
```

`fluid validate` passes two builds that name one dead-letter table, and `fluid generate iac` and `fluid apply` refuse them with `spark-address-conflict`: `properties.stream.deadLetter.table commerce.orders__dead_letter is another Spark build's dead-letter table.` Give each build's dead letters a table of its own.

#### What OpenTofu emits for dead letters

For a table sink on AWS, `fluid generate iac` emits an `aws_glue_catalog_table` for the dead-letter table, an Iceberg v2 table in the output's Glue database, at the location beside the output's:

```bash
jq '.resource.aws_glue_catalog_table | to_entries[] | select(.key | endswith("__dead_letter")) | .value | {name, location: .storage_descriptor.location, open_table_format_input}' iac/main.tf.json
```

```text
{
  "name": "orders__dead_letter",
  "location": "s3://commerce-lake/iceberg/commerce/orders__dead_letter/",
  "open_table_format_input": {
    "iceberg_input": {
      "metadata_operation": "CREATE",
      "version": "2"
    }
  }
}
```

The job's role gets what writing it takes. These statements are from the contract above, run on forge-cli `main`:

- **S3.** The table's prefix gets the same permissions as the output's prefix: see [What the job's role may do in S3](#what-the-job-s-role-may-do-in-s3). The `ReadWrite0` statement lists the output's prefix, the table's prefix and the checkpoint.
- **Glue.** The `GlueTable` statement lists the dead-letter table beside the output's.

```bash
jq '.data.aws_iam_policy_document | to_entries[] | select(.key | endswith("_access")) | .value.statement[] | select(.sid | IN("ReadWrite0", "GlueTable"))' iac/main.tf.json
```

```text
{
  "actions": [
    "s3:AbortMultipartUpload",
    "s3:DeleteObject",
    "s3:GetObject",
    "s3:PutObject"
  ],
  "effect": "Allow",
  "resources": [
    "arn:aws:s3:::commerce-lake/iceberg/commerce/orders/*",
    "arn:aws:s3:::commerce-lake/iceberg/commerce/orders__dead_letter/*",
    "arn:aws:s3:::commerce-lake/_checkpoints/commerce.orders-stream/ingest-orders/*"
  ],
  "sid": "ReadWrite0"
}
{
  "actions": [
    "glue:GetDatabase",
    "glue:GetTable",
    "glue:UpdateTable"
  ],
  "effect": "Allow",
  "resources": [
    "arn:aws:glue:eu-west-1:${data.aws_caller_identity.fluid_lf_caller.account_id}:catalog",
    "arn:aws:glue:eu-west-1:${data.aws_caller_identity.fluid_lf_caller.account_id}:database/commerce",
    "arn:aws:glue:eu-west-1:${data.aws_caller_identity.fluid_lf_caller.account_id}:table/commerce/orders",
    "arn:aws:glue:eu-west-1:${data.aws_caller_identity.fluid_lf_caller.account_id}:table/commerce/orders__dead_letter"
  ],
  "sid": "GlueTable"
}
```

When `binding.governance.lakeFormation` governs the output, the role also gets Lake Formation permissions on the dead-letter table: `ALTER`, `DESCRIBE`, `INSERT` and `SELECT`, and not `DELETE`, which [Lake Formation writes](#lake-formation-writes) grants for a batch overwrite. *(since 0.34.0, [forge-cli #1010](https://github.com/Agenticstiger/forge-cli/pull/1010))* An output with no `governance.lakeFormation` block gets the same grant where the account's Lake Formation settings govern new tables: see [A job's grant on its own table](#a-job-s-grant-on-its-own-table). On `emr-ec2` forge emits the policy for the cluster's owner to attach and no role, so it emits no Lake Formation permission there. From `fluid generate iac` on the contract with `governance: {lakeFormation: {grants: []}}`:

```bash
jq '.resource.aws_lakeformation_permissions | with_entries(select(.key | contains("dead_letters")))' iac-governed/main.tf.json
```

```text
{
  "commerce_orders_stream_lf_spark_dead_letters_ingest_orders": {
    "permissions": [
      "ALTER",
      "DESCRIBE",
      "INSERT",
      "SELECT"
    ],
    "principal": "${aws_iam_role.commerce_orders_stream_ingest_orders_spark.arn}",
    "table": [
      {
        "database_name": "${aws_glue_catalog_table.commerce_orders_stream_commerce_orders__dead_letter.database_name}",
        "name": "${aws_glue_catalog_table.commerce_orders_stream_commerce_orders__dead_letter.name}"
      }
    ]
  }
}
```

A topic sink emits no table. On MSK with `auth: msk-iam`, the role gets two statements beside its read of the source topic: `kafka-cluster:DescribeTopic` and `kafka-cluster:WriteData` on the dead-letter topic, and `kafka-cluster:WriteDataIdempotently` on the cluster. A Kafka producer is idempotent by default, and MSK authorizes that on the cluster and not on a topic. With `auth: none` forge emits neither statement, and the operator still lists the write.

```bash
jq '.data.aws_iam_policy_document | to_entries[] | select(.key | endswith("_access")) | .value.statement[] | select(.sid | IN("MskDeadLetterTopic", "MskIdempotentWrite"))' iac-topic/main.tf.json
```

```text
{
  "actions": [
    "kafka-cluster:DescribeTopic",
    "kafka-cluster:WriteData"
  ],
  "effect": "Allow",
  "resources": [
    "arn:aws:kafka:eu-west-1:000000000001:topic/commerce-events/0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d-1/commerce.orders.dlq"
  ],
  "sid": "MskDeadLetterTopic"
}
{
  "actions": [
    "kafka-cluster:WriteDataIdempotently"
  ],
  "effect": "Allow",
  "resources": [
    "arn:aws:kafka:eu-west-1:000000000001:cluster/commerce-events/0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d-1"
  ],
  "sid": "MskIdempotentWrite"
}
```

#### Listing the topic

A topic sink writes to the topic the contract names, on the cluster it reads, so forge writes it only once the operator lists it in `FLUID_SPARK_TARGET_ALLOWLIST`, in the real environment (see [Roles and who lists what](#roles-and-who-lists-what)). The entry is matched exactly:

| The cluster is named by | Entry |
|---|---|
| `mskClusterArn` | `msk-write:<cluster ARN>/<topic>` |
| `bootstrapServers` | `kafka-write:<host:port>/<topic>`, one for each broker the list names |

Listing one broker does not list the cluster, because any of them may take the write. The entry is needed on every runtime, `local` included, and for a broker at a private address too. The read of the cluster keeps its own entry, `msk:<cluster ARN>`. An unset list allows none. Without the entry, `fluid validate` warns:

```bash
fluid validate orders-topic.fluid.yaml
```

```text
✅ Valid FLUID contract (schema v0.7.7)
⚠️  1 warning(s)
Validation completed in 0.024s

Validation Warnings:
====================
 1. Spark build ingest-orders: properties.stream.deadLetter.topic commerce.orders.dlq is not in FLUID_SPARK_TARGET_ALLOWLIST (as msk-write:arn:aws:kafka:eu-west-1:000000000001:cluster/commerce-events/0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d-1/commerce.orders.dlq); the job would write it; the IaC is refused at generate and apply until the operator lists it
```

`fluid generate iac` and `fluid apply` refuse the build. The refusal of `fluid apply` comes before `tofu apply` and prints the whole `export` line, your current list with the entry added:

```bash
fluid apply orders-topic.fluid.yaml --dry-run --yes 2>&1 | tail -n +2
```

```text
CLI command error
❌ apply_spark_refused  [ERR_APPLY_SPARK_REFUSED]
  error: Spark build 'ingest-orders' writes dead letters to a topic the operator has not listed. properties.stream.deadLetter.topic commerce.orders.dlq is not in FLUID_SPARK_TARGET_ALLOWLIST (as msk-write:arn:aws:kafka:eu-west-1:000000000001:cluster/commerce-events/0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d-1/commerce.orders.dlq). The job writes the topic its contract names, on the cluster it reads, so a contract could write into another team's topic there. A write needs its entry on every runtime, a broker at a private address included; an unset list allows none.
  hint: If this topic is the product's, have the operator list it in the OPERATOR environment (not a project .env): export FLUID_SPARK_TARGET_ALLOWLIST="emr-serverless:00fexampleapp0001,msk:arn:aws:kafka:eu-west-1:000000000001:cluster/commerce-events/0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d-1,msk-write:arn:aws:kafka:eu-west-1:000000000001:cluster/commerce-events/0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d-1/commerce.orders.dlq"
```

#### On this machine

The dead-letter table also exists for `runtime: local`, where the job creates it (Iceberg v2, the same columns) in a namespace the operator lists: see [Running a build on this machine](#running-a-build-on-this-machine).

### Batch builds

A `batch` build runs `properties.sql` over catalog tables and never reads a topic. A batch read of a topic sees only what Kafka still retains, so overwriting the table with it would drop every older row. To land a topic on a schedule, use a `streaming` build with `trigger: {availableNow: true}`: it keeps its position in its checkpoint, and the scheduled run is the micro-batch.

A build declares `properties.mapping` or `properties.sql`, not both, and exactly one Iceberg output.

## What the mapping does on Spark

The mapping is the one the Flink lane takes, so the same `properties.mapping` compiles to Spark 3.5 SQL. What differs, for the contract author:

- **Arrays** that become rows flatten with `LATERAL VIEW inline` for struct elements and `LATERAL VIEW explode` for scalars. Flink uses `CROSS JOIN UNNEST` for both.
- **Built structs** use `named_struct`, with the same null rule as Flink: a built struct is null when its parent is.
- **Types** use Spark's names: `timestamp_ltz` is `TIMESTAMP` and `timestamp` is `TIMESTAMP_NTZ`.
- **Structs are read by field name.** Spark casts structs by position, so an Avro writer schema with a different field order would otherwise swap values.
- **A required field that arrives null fails the job.** Flink fails a `NOT NULL` column the same way. On Spark the job stops with `fluid: required field <name> is null in a Kafka record`. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* With [`deadLetter`](#dead-letters), the record goes to the dead letters and the job keeps running, until more than `maxRecordsBeforeAbort` have gone there.
- **Kafka metadata** (`topic`, `partition`, `offset`, `timestamp`, `timestamp-type`, `headers`) maps to the Spark Kafka source's columns. `leader-epoch` is refused, because Spark does not read it.
- **Literals** for map keys and struct field names are refused if they hold `'`, `\`, a control character or `${`, because `spark.sql()` substitutes `${env:...}`.

### `maskAtIngest: hash`

A mapped column can set `maskAtIngest: hash`. The column is the HMAC-SHA256 of its source, keyed by the secret `parameters.spark.maskKeySecretArn` names, in lowercase hex. A null source stays null. Because the key is a secret, a low-entropy value such as an email or an integer id cannot be recovered by hashing a list of guesses, as it can from a plain SHA-256.

- It is Spark only. The Flink lane refuses it by name.
- The source is a string, binary, int or long (identifier-like values, whose text form does not depend on a session setting). The target is a string column. It cannot also set `cast`.
- `job.json` holds only the key's ARN, never the key. The job's role gets `secretsmanager:GetSecretValue` on that secret, and `kms:Decrypt` for the key it is encrypted with. Masking without `maskKeySecretArn` is refused.
- The same key gives the same hash, so a column hashed with it still joins to another column hashed with it. Rotating the key changes every hash.

## What forge provisions

`fluid generate iac` and `fluid apply` add these to the module for each Spark build (checked on 0.31.0):

| Resource | Details |
|---|---|
| Artifacts | `aws_s3_object` in the output's bucket. `job.json` at `_fluid/spark/<product>/<build>/job.json`, and the runner at `_fluid/spark/<product>/<build>/runner/<16 hex digits of its sha256>/forge_spark_runner.py`. A new runner is a new key. |
| Logs | A CloudWatch log group `/aws/fluid/spark/<product>/<build>`, encrypted with a per-product KMS key that only CloudWatch Logs may use, for this product's groups. |
| The job's role | Unless the contract names one. Least privilege: S3 read and write on the data and checkpoint prefixes, read on the artifacts, the Glue calls on the output, KMS through S3 and Secrets Manager only, MSK IAM on the cluster, topic and consumer group, `lakeformation:GetDataAccess`, the mask key and a registry secret, and its log group. |
| A dead-letter table | *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* For a stream with `deadLetter` and `sink: table`: an Iceberg v2 `aws_glue_catalog_table` beside the output's table, with its S3 prefix, Glue table and, when Lake Formation governs the output, Lake Formation permissions added to the job's role. *(since 0.34.0, [forge-cli #1010](https://github.com/Agenticstiger/forge-cli/pull/1010))* Without a `governance.lakeFormation` block, those permissions are added where the account's Lake Formation settings govern new tables: see [A job's grant on its own table](#a-job-s-grant-on-its-own-table). A `sink: topic` emits no table: on MSK with IAM the job's role gets the permissions to write the topic. See [What OpenTofu emits for dead letters](#what-opentofu-emits-for-dead-letters). |
| A caller policy | For a build that runs to completion (batch, or a stream with `availableNow`): the managed policy `fluid-<product>-spark-caller`, for the platform to attach to the scheduler's role. *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* A stream that runs continuously gets it too, so that a keepalive can run `fluid apply --mode reconcile` from the scheduler's role. |

Per runtime:

| Runtime | What forge creates | Trust of the job's role |
|---|---|---|
| `emr-serverless` | With `applicationId`, nothing: the application is the domain's and the contract only names it. Without it, `packaging.containers.emrApplication: isolated` creates one for the product, which stops after 15 idle minutes, is capped at 16 vCPU and 64 GB, and sits in the MSK cluster's subnets and security groups. With neither, the contract is refused (`spark-emr-application-shared`). | The EMR Serverless service, for this account and this application. |
| `glue` | An `aws_glue_job` (`gluestreaming` or `glueetl`), Glue 5.0 by default, with `--datalake-formats iceberg`, the runner as its script, `--config` pointing at `job.json`, continuous logs to its group, and a `NETWORK` connection in one of the MSK cluster's subnets. | `glue.amazonaws.com`, for this build's own Glue job. |
| `emr-eks` | Nothing: the virtual cluster is existing. | The IRSA statement that `aws emr-containers update-role-trust-policy` writes. The virtual cluster and its EKS cluster are read at plan time. |
| `emr-ec2` | No role: a step runs as the cluster's instance profile, so forge emits the job's policy as a managed `aws_iam_policy` for the cluster's owner to attach. *(since 0.33.0, [forge-cli #1005](https://github.com/Agenticstiger/forge-cli/pull/1005))* `fluid apply` starts no step until it is attached: see [An EMR on EC2 step starts once its policy is attached](#an-emr-on-ec2-step-starts-once-its-policy-is-attached). | None. |

### What the job's role may do in S3

*(since 0.33.0, [forge-cli #983](https://github.com/Agenticstiger/forge-cli/pull/983))* The role forge creates for a Spark build, and the policy it emits for an EMR on EC2 cluster's owner to attach, get S3 access to these prefixes of the output's bucket:

| Prefix | Access |
|---|---|
| The output's `binding.location.path` | Read, write and delete |
| *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* The dead-letter table's location, for a stream with `deadLetter` and `sink: table`: the output's parent prefix and the table's name, such as `iceberg/commerce/orders__dead_letter/` | Read, write and delete |
| The checkpoint: `_checkpoints/<product>/<build>/`, or the one the contract declares under `_checkpoints/<product>/` | Read, write and delete |
| On Glue, `tmp/` under the build's artifacts prefix | Read, write and delete |
| The build's artifacts, `_fluid/spark/<product>/<build>/` | Read |

For each prefix the role holds three kinds of permission:

- **The objects under it.** `s3:GetObject` on `<prefix>/*`, and for a prefix that is written also `s3:PutObject`, `s3:DeleteObject` and `s3:AbortMultipartUpload`.
- **A listing of the directory.** `s3:ListBucket` on the bucket, limited by an `s3:prefix` condition to the directory's exact name (the prefix without its trailing slash) and to `<prefix>/*`. The exact name matches that directory alone: a sibling such as `<build>-x` does not match.
- **A read of the directory's own key.** `s3:GetObject` on `<prefix>` with no trailing slash. That key holds no data.

It also has `s3:GetBucketLocation` on the bucket.

The exact-name listing and the read of the directory's own key are what Hadoop's file system asks for first. To look up a directory it reads the directory's own key, then `<dir>/`, then lists it, and Spark does this on its checkpoint. Without the directory's own key and its exact-name listing, S3 refuses the first call with a 403 and a stream fails on its own checkpoint. With 0.32.0 and earlier, whose role has `<prefix>/*` and the listing under it only, a stream's job failed within minutes of starting for that reason.

The statements from `fluid generate iac` on the contract above, run on forge-cli `main`. These two are the ones that differ from 0.32.0, where the `s3:prefix` condition lists the three `<prefix>/*` values only and there is no `Directory` statement:

```json
{
  "actions": ["s3:ListBucket"],
  "condition": [
    {
      "test": "StringLike",
      "values": [
        "iceberg/commerce/orders",
        "_checkpoints/commerce.orders-stream/ingest-orders",
        "_fluid/spark/commerce.orders-stream/ingest-orders",
        "iceberg/commerce/orders/*",
        "_checkpoints/commerce.orders-stream/ingest-orders/*",
        "_fluid/spark/commerce.orders-stream/ingest-orders/*"
      ],
      "variable": "s3:prefix"
    }
  ],
  "effect": "Allow",
  "resources": ["arn:aws:s3:::commerce-lake"],
  "sid": "List2"
}
{
  "actions": ["s3:GetObject"],
  "effect": "Allow",
  "resources": [
    "arn:aws:s3:::commerce-lake/iceberg/commerce/orders",
    "arn:aws:s3:::commerce-lake/_checkpoints/commerce.orders-stream/ingest-orders",
    "arn:aws:s3:::commerce-lake/_fluid/spark/commerce.orders-stream/ingest-orders"
  ],
  "sid": "Directory4"
}
```

A role you name with `executionRoleArn` is yours: forge adds nothing to it. If a stream on such a role fails with that 403, give the role the same two permissions for the checkpoint directory.

### Roles and who lists what

A contract that names `executionRoleArn`, `applicationId`, `clusterId`, `virtualClusterId` or an MSK cluster reaches things forge did not create. A named role is reference-only: forge creates no role, and the job runs as the one named, with everything it can do. A batch build must name one, except on `emr-ec2`, because its SQL reads tables forge cannot grant to a role it derives. So the operator lists each such name, in the real environment (a shell or CI variable): a project `.env` is ignored for every `*_ALLOWLIST` setting. An unset list allows nothing.

Without the entries, `fluid validate` warns, and `fluid generate iac` and `fluid apply` refuse. Without the settings, `fluid validate` passes the contract above with four warnings. The first two are these (the other two are about the registry credential: see [Schema registry](./schema-registry.md#operator-settings)):

```text
 1. Spark build ingest-orders: parameters.spark.applicationId 00fexampleapp0001 is not in FLUID_SPARK_TARGET_ALLOWLIST (as emr-serverless:00fexampleapp0001); the IaC is refused at generate and apply until the operator lists it
 2. Spark build ingest-orders: parameters.spark.source.mskClusterArn arn:aws:kafka:eu-west-1:000000000001:cluster/commerce-events/0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d-1 is not in FLUID_SPARK_TARGET_ALLOWLIST (as msk:arn:aws:kafka:eu-west-1:000000000001:cluster/commerce-events/0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d-1); the IaC is refused at generate and apply until the operator lists it
```

## Running a build on this machine

*(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* A build with `parameters.spark.runtime: local` runs forge's Spark runner and its compiled `job.json` with `spark-submit` on the machine `fluid apply` runs on: a laptop or a lab host. When `spark-submit` is not on `PATH`, the error says to install Spark 3.5, or to use an EMR 7.x image. Nothing is provisioned. There is no OpenTofu step, no role and no AWS account, and the job runs with the credentials of the machine. It runs on Linux or macOS: forge tracks a local run with `fcntl.flock`, and refuses the build where that is missing.

A local build needs three things:

- **A `spark-submit`**: the one the operator names, or `spark-submit` on `PATH` (see [Operator settings for a local run](#operator-settings-for-a-local-run)).
- **An Iceberg REST catalog** for the output. The output's binding is on `platform: local`, with `location.catalog` set to `lakekeeper`, `rest` or `polaris`. A binding on `platform: aws`, or a Glue catalog, is refused (see below). The operator declares the catalog's connection in a Spark properties file, under the catalog name `fluid`. The contract carries no connection or credential: a `uri` or `warehouse` that its binding names is only compared with the file's.
- **For a stream, brokers by name and an S3 store for the checkpoint.** `source.bootstrapServers` replaces `source.mskClusterArn`, which a local run refuses because nothing looks up the brokers of an MSK cluster for it. The checkpoint defaults to `s3://<bucket>/_checkpoints/<product>/<build>/`, in the output's `location.bucket`. An output with no bucket needs a declared `properties.stream.checkpoint`, and a declared one must sit under `_checkpoints/<product>/` (in the output's bucket, when it names one). The store's credentials are the operator's, in the properties file.

A batch build's `properties.sql` reads tables of the same `fluid` catalog.

### Switching a contract written for AWS

`runtime: local` ignores the keys of the AWS runtimes: `applicationId`, `clusterId`, `virtualClusterId`, `releaseLabel`, `glueVersion` and `executionRoleArn`. Each still has to have the form its runtime takes. A contract written for AWS can therefore keep them. The switch is one line on the build, in an [overlay](../concepts/environments-and-overlays.md) that `--env local` picks, plus the output's binding, which has to be on `platform: local`:

```yaml
# overlays/local.yaml
builds:
  - id: ingest-orders
    properties:
      parameters:
        spark:
          runtime: local
exposes:
  - exposeId: orders
    binding:
      platform: local
      location:
        catalog: lakekeeper
```

Run on the page's example with a JSON stream and no registry, a `bootstrapServers` source with `auth: none` in place of the MSK cluster, and no `maskAtIngest` or `maskKeySecretArn` (the column is `customer_email`), and with the namespace entry below and the broker's host listed, `fluid validate` passes this overlay with no warning. It raises no `FLUID_SPARK_TARGET_ALLOWLIST` warning for the ignored `applicationId`:

```bash
FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST=fluid/commerce fluid validate contract.fluid.yaml --env local
```

```text
overlay_applied
✅ Valid FLUID contract (schema v0.7.7)
Validation completed in 0.020s
```

With only the `runtime` line in the overlay, the output is still on AWS, and `fluid validate` refuses it (the error lines of its output):

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.7)
...
 1. Spark: Spark build ingest-orders: runtime local writes a table in an Iceberg REST catalog on platform local (binding.platform: local, location.catalog lakekeeper, rest or polaris); a Glue table runs on an AWS runtime
```

A contract whose Spark builds run on AWS and here cannot be applied as one: the native engine that applies a local build runs no AWS Spark build, and `fluid apply` refuses with `apply_spark_needs_opentofu`. Keep the AWS builds and the local builds in separate contracts, or apply each environment's overlay on its own. Each environment keeps its own runs: an apply of AWS builds never stops the local runs of this machine.

### Where the files and the run state go

`fluid apply` writes the job config and the runner when it starts a run, in the layout OpenTofu uploads on AWS:

| File | Where, under the root |
|---|---|
| The job config | `_fluid/spark/<product>/<build>/job.json` |
| The runner | `_fluid/spark/<product>/<build>/runner/<16 hex digits of its sha256>/forge_spark_runner.py` |

The root is `FLUID_SPARK_LOCAL_ROOT`: an `s3://<bucket>[/<prefix>]`, or an absolute directory. Without it the root is `.fluid/spark-artifacts` beside the contract. An `s3://` root is written through the AWS SDK, so it needs the `[aws]` extra (`pip install 'data-product-forge[aws]'`) and reaches SeaweedFS or MinIO through the SDK's own `AWS_ENDPOINT_URL_S3`. `spark-submit` reads the job config from the root. It runs the runner from an `s3://` root, and for a directory root from the copy that forge places in the run's own directory: see [Safety rules](#safety-rules). The root is read when the run starts: `fluid plan` holds `${fluid_spark_local_root}` in its place, so a plan made on one machine matches the apply on another.

Run state lives beside the contract, under `.fluid/<product>/runtime/spark/<build>/runs/<run id>/`. A run id is a UTC timestamp and eight hex digits. The directory holds `run.json` (the run's record and its `spark-submit` argv), `status.json`, `driver.log`, a `lock` file, with a directory root the runner that `spark-submit` runs (`forge_spark_runner.py`), and, after a stop, a `cancel` mark. A run is active while one of its processes holds the lock. When a new run starts, forge removes the ended runs beyond the newest ten of the build. `.fluid` must be a directory of the project's own: a link in it that leads out is refused.

A detached supervisor starts `spark-submit` in a session of its own and records how it ended, so a terminal's Ctrl-C does not reach a stream. The call is in client mode, so the driver is the run's own process and stopping the run stops the job. This is the argv of that stream (the run id, the operator's paths and the project path shortened):

```text
$OPS/spark-submit
--name
fluid-commerce.orders-stream-ingest-orders-744ba50a
--deploy-mode
client
--properties-file
$OPS/spark.properties
--conf
spark.jars=/usr/share/aws/iceberg/lib/iceberg-spark3-runtime.jar
--conf
spark.jars.packages=org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1
--conf
spark.redaction.regex=(?i)secret|password|token|access[.]?key|credential
--conf
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
--conf
spark.sql.shuffle.partitions=16
<project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs/<run-id>/forge_spark_runner.py
--config
<project>/.fluid/spark-artifacts/_fluid/spark/commerce.orders-stream/ingest-orders/job.json
--fluid-config-hash
9413e2b0daefdcdc0af443f6847abaf0aa9dc4a453092639fe8880f76f198483
--fluid-source
3801464d85c37480
--fluid-checkpoint
1a04314328989295
```

*(since 0.34.0, [forge-cli #1014](https://github.com/Agenticstiger/forge-cli/pull/1014))* The argv of a run ends with two more lines, `--fluid-job-sha256` and the digest of the job config that forge wrote under the root, and the runner refuses any other config before it reads anything: see [A run starts only on the config this apply compiled](#a-run-starts-only-on-the-config-this-apply-compiled). These are the two lines in a run of the same stream on `main`:

```text
--fluid-job-sha256
273573946cb2003dc5cb3d54ecb3223eada561317cd2ed8df658b9c6fc11e22f
```

forge puts the properties file's path on the command line, and copies none of its values there, except the two lists it merges, below. forge passes the settings of the run beside the file's: the contract's allowed `sparkConf` ([Spark settings](#spark-settings)), the Iceberg extension and the Kafka connector package. For `spark.jars.packages` and `spark.sql.extensions`, which `spark-submit` would otherwise replace as a whole, forge passes the union of the file's value and its own, the file's entries first. A package that both name is passed once, in the file's version. The file's own `spark.jars` and `spark.jars.repositories` replace forge's, so on a Spark that is not an EMR image the file names the Iceberg runtime jar there. Without its own `spark.jars`, forge points `spark.jars` at the path an EMR image keeps it, `/usr/share/aws/iceberg/lib/iceberg-spark3-runtime.jar`.

### Operator settings for a local run

*(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* The operator sets these in the real environment of the shell or job that runs `fluid apply`. A contract names none of them. `fluid doctor --env` lists these four, with their current value and default; see [`fluid doctor --env`](../cli/doctor.md#env-the-runtime-switches).

| Variable | What it sets |
|---|---|
| `FLUID_SPARK_SUBMIT_EXECUTABLE` | The `spark-submit` a local run starts: an absolute path to an executable file, or a name on `PATH`. Default: `spark-submit` on `PATH`. |
| `FLUID_SPARK_SUBMIT_PROPERTIES_FILE` | An absolute path to a Spark properties file, passed to every local run as `--properties-file`: the catalog (`spark.sql.catalog.fluid`, with its `uri` and `warehouse`), the S3 store, their credentials and the master. forge reads it with the rules of Java's `Properties`, as `spark-submit` does. A `uri` or `warehouse` that the output's binding names has to equal the one the file sets (a trailing `/` aside), or the runner refuses before it writes. Default: none. |
| `FLUID_SPARK_LOCAL_ROOT` | Where the runs read their job config and runner: `s3://<bucket>[/<prefix>]` (a prefix of letters, digits and `. _ = / -`) or an absolute directory. Default: `.fluid/spark-artifacts` beside the contract. |
| `FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST` | The namespaces a local run may create and write tables in, as `<warehouse>/<namespace>`, comma-separated. An unset list allows none. See [The table the job creates](#the-table-the-job-creates). |

`fluid apply` checks the first three, and that this system has `fcntl.flock`, before it applies anything. A build it cannot start ends the apply with `apply_spark_local_unavailable` and exit code `1`, and the error ends `nothing was applied`. A dry run checks none of them. For a missing `spark-submit`:

```bash
FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST=fluid/commerce FLUID_SPARK_SUBMIT_EXECUTABLE=/nonexistent/spark-submit fluid apply contract.fluid.yaml --env local --yes 2>&1 | tail -3
```

```text
❌ apply_spark_local_unavailable  [ERR_APPLY_SPARK_LOCAL_UNAVAILABLE]
  error: Spark build(s) ingest-orders run on this machine (runtime local), and FLUID_SPARK_SUBMIT_EXECUTABLE names /nonexistent/spark-submit, which is not an executable file; nothing was applied
  hint: Set the operator's FLUID_SPARK_SUBMIT_EXECUTABLE, FLUID_SPARK_SUBMIT_PROPERTIES_FILE and FLUID_SPARK_LOCAL_ROOT in the real environment (a project .env cannot set them).
```

A properties file that is not a file and an `s3://` root that breaks the form end the same way, each with its own message.

A local run also reads settings that other parts of this page define:

| Variable | What it does for a local run |
|---|---|
| `FLUID_SPARK_CONF_ALLOWLIST` | The `sparkConf` keys beyond the tuning ones, as on AWS. A key that is refused even when listed is refused for a local build too: with `FLUID_SPARK_CONF_ALLOWLIST=spark.*`, `fluid apply` still refuses `spark.jars` with `apply_spark_refused`. See [Spark settings](#spark-settings). |
| `FLUID_SPARK_CONTRACT_SQL_ALLOWLIST` | The builds whose own `properties.sql` the job may run. A batch build with `properties.sql` warns in `fluid validate` until the operator lists it. See [Contract SQL and `fluid validate`](#contract-sql-and-fluid-validate). |
| `FLUID_SPARK_MAVEN_REPOSITORY` | The Maven mirror, which sets `spark.jars.repositories` of a local stream as it does on AWS, unless the properties file sets its own. |
| `FLUID_SPARK_WAIT_SECONDS` | How long a reconcile waits for a cancelled local run to stop, and for a started one to leave its pending state. Default 900. |
| `FLUID_ACQUISITION_DEPLOYMENT_HOST_ALLOWLIST` | The Kafka broker's host, as for other Spark streams that name brokers. `fluid validate` warns while it is missing. See [Environment variables](./environment-variables.md). |

The AWS SDK's own settings reach an `s3://` root: `AWS_ENDPOINT_URL_S3` or `AWS_ENDPOINT_URL` (forge then asks for path-style requests), `AWS_REGION` or `AWS_DEFAULT_REGION` (`us-east-1` when neither is set), and the SDK's credential chain.

### The table the job creates

Nothing creates the output's table before a local job runs, as OpenTofu creates the Glue table on AWS. The job creates it on its first write. It runs `CREATE NAMESPACE IF NOT EXISTS` for the output's database and `CREATE TABLE IF NOT EXISTS` for the table, in the catalog `fluid`: an Iceberg v2 table with the contract's columns (`NOT NULL` for a `required` one), not partitioned. The statements are in the `sink.create` list of `job.json`, which `fluid generate artifacts --emit spark` writes. Apart from `sink`, that `job.json` equals the AWS one for the same contract, whose sink names a Glue catalog and its warehouse.

A table that exists is written as it is, so a contract could name another team's table and append to it. The operator's list stops that. An entry is `<warehouse>/<namespace>`:

- `<warehouse>` is the binding's `location.warehouse`, or `fluid` when the binding names none.
- The namespace is the output's database. An entry matches whole levels: `fluid/commerce` lists `commerce`, and `fluid/comm` does not.
- An unset list allows no namespace.
- The check covers every table the build creates, a stream's dead-letter table among them: see [Dead letters](#dead-letters).

`fluid validate` warns while the list lacks the entry, and `--strict` turns the warning into exit 1:

```bash
FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST=fluid/comm fluid validate contract.fluid.yaml --env local --strict; echo "exit $?"
```

```text
overlay_applied
✅ Valid FLUID contract (schema v0.7.7)
⚠️  1 warning(s)
Validation completed in 0.021s

Validation Warnings:
====================
 1. Build ingest-orders: not in FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST: fluid/commerce; the local run is refused until the operator lists it

❌ Validation failed: warnings treated as errors (--strict)
exit 1
```

`fluid apply` refuses the build, even with `--dry-run`, and prints the `export` line to use. `fluid plan` and `fluid generate artifacts` do not refuse:

```bash
fluid apply contract.fluid.yaml --env local --dry-run --yes 2>&1 | tail -3
```

```text
❌ apply_spark_refused  [ERR_APPLY_SPARK_REFUSED]
  error: Spark build 'ingest-orders' writes a namespace the operator has not listed. A local run writes commerce.orders in namespace commerce of fluid, which FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST does not list (as fluid/commerce). It creates its tables IF NOT EXISTS, so a table that exists, another team's included, would be adopted and appended to. An unset list allows none.
  hint: If this namespace is the product's, have the operator list it in the OPERATOR environment (not a project .env): export FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST="fluid/commerce"
```

### What `fluid apply` does

A local stream follows the `spark.reconcile` action of [Starting and reconciling runs](#starting-and-reconciling-runs), on this machine. The line of each outcome names the run and where its state is. The reconcile has no AWS client: the local run store plays that part.

| Found | What apply does |
|---|---|
| A running stream with this config hash | Nothing: `unchanged run <run id> RUNNING` |
| A running stream with another hash | Stops it, and starts the new config on the **same checkpoint**: `restarted run <run id> RUNNING` |
| No running stream | Starts one: `started run <run id> RUNNING` |
| A stream stopped from outside forge: the machine shut down or restarted, or a kill | Starts the same config again, as it does for a job run cancelled by hand on AWS. |
| A stream that failed with this config | An error that names the run and its log, and no new start. Change the build, and apply starts the new config. |
| A stream of a build that the contract no longer declares | Stops it: `stopped run <run id> CANCELLED`. A build moved to an AWS runtime keeps its local runs, because an apply of AWS builds never stops them. |

*(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* The rows about a stream stopped from outside forge and a stream that failed change. A stream that failed, one whose supervisor got a signal from outside forge (a shutdown of the machine, say), and one whose processes ended without recording how (`ended LOST`) are a death: `fluid apply` and `--mode reconcile` start it again on its checkpoint within the [restart budget](#the-restart-budget), and count each restart. A spent budget is the error. Only a run that was cancelled through forge is left stopped, and only by `--mode reconcile`.

A stop sends SIGTERM to the run's process group, and SIGKILL after a grace period of 60 seconds. forge waits for the run to end for as long as `FLUID_SPARK_WAIT_SECONDS` says. A new topic or cluster on a checkpoint that an earlier run read is refused before anything is stopped, as on AWS.

A run whose processes ended without recording how, because the machine restarted or something killed them with SIGKILL, did not fail. The next apply starts the same config again and says that the run stopped without recording its end (forge-cli's tests).

These runs used a stand-in `spark-submit`, a script that sleeps, because no Spark is installed where they were produced: they show what forge records and prints, and nothing of Spark's own behaviour. The first three rows, from the stream above (the `Spark ` line of each apply, from `grep "^Spark "`; the second apply changed `spark.sql.shuffle.partitions` from `8` to `16`):

```text
Spark ingest-orders (local): started run 20261119T060815Z-406dcde5 RUNNING on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders)
Spark ingest-orders (local): unchanged run 20261119T060815Z-406dcde5 RUNNING on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders)
Spark ingest-orders (local): restarted run 20261119T060817Z-24b5a23b RUNNING on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders)
```

A failed stream says why and how to start it again. The operator's `spark-submit` and properties file are not in the config hash, so when the cause was this machine's, the message gives the second way: remove the run's directory, and `fluid apply` starts the stream again:

```text
Spark ingest-orders (local): failed run 20261119T060909Z-89c3a970 FAILED on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders). run 20261119T060909Z-89c3a970 ended FAILED (exit 1): log <project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs/20261119T060909Z-89c3a970/driver.log: the stream failed. It is not started again with the same config, which would fail the same way: fix the cause and change the build, and fluid apply starts the new config; when the cause was this machine's (spark-submit, its properties file), remove <project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs/20261119T060909Z-89c3a970 and fluid apply starts it again
```

The two lines of that message, `the stream failed` and the exit code, come from a stand-in `spark-submit` that exits 1; the path is shortened to `<project>`.

*(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* A failed stream is started again on its checkpoint, within the [restart budget](#the-restart-budget), and a message like the one above is the error for a spent budget. It ends with the same second way: `when the cause was this machine's (spark-submit, its properties file), remove <project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs (the build's run history here) and fluid apply starts it again`. The run directory it names is the whole history, which is what the budget is counted from.

**A dry run.** `fluid apply --dry-run` starts and stops nothing and creates no run directory. It prints `would be reconciled to config <first 12 hex digits of the hash>` for a stream, and `would stop <run id>` for a run the contract no longer runs here:

```bash
FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST=fluid/commerce fluid apply contract.fluid.yaml --env local --dry-run --yes 2>&1 | grep -E "^(Spark |spark_reconcile)"
```

```text
Spark ingest-orders (local): would be reconciled to config 423168902cd2
```

**A batch or `availableNow` build** is reported as `scheduled` by a plain `fluid apply`, and runs under its scheduler's command, `fluid apply <contract> --mode amend-and-build --build-id <id>`: see [Scheduled Spark builds](./airflow.md#scheduled-spark-builds). The command starts one run and waits for it to end, up to `execution.runtime.timeout` (21600 seconds when the build sets none). Ctrl-C, SIGTERM or SIGHUP while it waits cancels the run. The line says `succeeded run <run id> SUCCEEDED`, and a run that fails prints `failed run <run id> FAILED` with the log's last lines, and `fluid apply` exits with code `1`:

```text
   Spark daily-curated: started run 20261119T060914Z-b8d947d4 on this machine (.fluid/platform.events/runtime/spark/daily-curated)
   Spark daily-curated (local): succeeded run 20261119T060914Z-b8d947d4 SUCCEEDED on this machine (.fluid/platform.events/runtime/spark/daily-curated)
```

A dry run of that command prints `would start one run and wait up to 21600 s for it to end`.

### The config hash on a local run

The [config hash](#starting-and-reconciling-runs) of a local build is the sha256 of the job config, the runner's sha256 and the run settings, as on AWS. A local build has no target, role, release or retry policy, so those parts are empty. The operator's `spark-submit`, properties file and root are not in it: changing one restarts nothing.

The runner's sha256 is in the hash on every runtime, and the runner of 0.33.0 differs from the one of 0.32.0. So each Spark stream that runs on AWS restarts once on its next `fluid apply`, on its checkpoint. A scheduled build is not restarted.

### An `s3://` root on a Spark that is not an EMR image

`spark-submit` and the runner read an `s3://` root through Hadoop. On a Spark that is not an EMR image, the properties file maps the `s3` scheme to S3A (`spark.hadoop.fs.s3.impl`, with its endpoint) and puts `hadoop-aws` on `spark.driver.extraClassPath`. The class path is needed because `spark-submit` downloads the runner before it loads `--packages`. A directory root needs none of this.

### Safety rules

- **`spark-submit` is the operator's, not the project's.** `FLUID_SPARK_SUBMIT_EXECUTABLE` is one program: an absolute path to an executable file, or a name that `PATH` resolves to an absolute path. A relative path is refused, and so is a `spark-submit` inside the project, links followed, because the project would then choose the program forge starts:

  ```bash
  FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST=fluid/commerce FLUID_SPARK_SUBMIT_EXECUTABLE=$PWD/bin/spark-submit fluid apply contract.fluid.yaml --env local --yes 2>&1 | tail -3
  ```

  ```text
  ❌ apply_spark_local_unavailable  [ERR_APPLY_SPARK_LOCAL_UNAVAILABLE]
    error: Spark build(s) ingest-orders run on this machine (runtime local), and the spark-submit to run (<project>/bin/spark-submit) is inside the project (<project>), which would choose the program forge starts; set FLUID_SPARK_SUBMIT_EXECUTABLE to a spark-submit outside it; nothing was applied
    hint: Set the operator's FLUID_SPARK_SUBMIT_EXECUTABLE, FLUID_SPARK_SUBMIT_PROPERTIES_FILE and FLUID_SPARK_LOCAL_ROOT in the real environment (a project .env cannot set them).
  ```

- **The call is a list, not a shell line.** forge starts `spark-submit` and its supervisor without a shell. The properties file's path is on the command line and its values are not, apart from the two merged lists.
- **The run's files are owner-only.** The run's directory is mode `700`, and `run.json`, `status.json`, `driver.log` and the `lock` are `600` as `stat` shows after a run on macOS. The runner's copy in the run's directory keeps the default `644`, and is readable only through that directory. The supervisor sets its umask to `077`, and forge writes the job config and runner of a directory root as `600`.
- **Credentials are redacted.** forge passes `spark.redaction.regex` with the value `(?i)secret|password|token|access[.]?key|credential`, unless the properties file sets its own. The value adds `credential`, the last word of an Iceberg REST catalog's `spark.sql.catalog.<name>.credential` key, for Spark versions whose own pattern lacks it.
- **The run's environment is cleaned.** `spark-submit` is a bash script. A run keeps only the environment names that a shell could set: `[A-Za-z_][A-Za-z0-9_]*`. It drops names that bash reads as exported functions (`BASH_FUNC_*`), and the settings that make bash run code or trace itself as it starts: `BASH_ENV`, `ENV`, `SHELLOPTS`, `BASHOPTS`, `PS4` and `BASH_XTRACEFD`.
- **The runner runs from a directory of the run's own.** For a directory root forge copies the runner into the run's own directory and checks its sha256 against the one the run was compiled with. For an `s3://` root `spark-submit` downloads the runner into a directory of its own. Every run's driver also gets `PYTHONSAFEPATH`, which Python 3.11 and later honour, so a file such as `json.py` in the project cannot take the place of a module the runner imports.
- **Links under `.fluid` are refused.** A link in the run state's path, or under the default root, that leads out of the project's `.fluid` directory stops the run before it writes.

## Operator settings

| Variable | What it lists or sets |
|---|---|
| `FLUID_SPARK_TARGET_ALLOWLIST` | The existing runtimes a contract may name, as `<runtime>:<id>` (`emr-serverless:<applicationId>`, `emr-ec2:<clusterId>`, `emr-eks:<virtualClusterId>`), and the MSK clusters it may read, as `msk:<cluster ARN>`, matched exactly. The job's role trusts the runtime and the caller policy may start, cancel and add steps there, so naming another team's cluster would reach it. An isolated application of the product needs no entry. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* It also lists the topic a stream's dead letters go to, as `msk-write:<cluster ARN>/<topic>`, or as `kafka-write:<host:port>/<topic>` for each broker a `bootstrapServers` cluster lists, on every runtime: see [Listing the topic](#listing-the-topic). |
| `FLUID_SPARK_EXECUTION_ROLE_ALLOWLIST` | The roles a contract's `executionRoleArn` may name: an exact role ARN, or an ARN prefix ending in `/` (a role path). |
| `FLUID_SPARK_CONF_ALLOWLIST` | `sparkConf` keys beyond the tuning ones: a key, or a prefix ending in `*`. See [Spark settings](#spark-settings). |
| `FLUID_SPARK_CONTRACT_SQL_ALLOWLIST` | The builds whose own `properties.sql` the job may run. An entry is `<product>`, `<product>/<build>` or `<product>/<build>@sha256:<digest of the reviewed SQL>`, the last being the one to use. A contract's own SQL runs inside the job with its role, so it can read any table that role can read. A build with a `properties.mapping` needs no entry, because forge compiles a query that reads only the stream. |
| `FLUID_SPARK_WAIT_SECONDS` | How long a reconcile waits for a cancelled run to stop, and for a started one to leave its pending states. Default 900. |
| `FLUID_SPARK_MAVEN_REPOSITORY` | One https Maven mirror. See [Network](#network-and-packages). |
| `FLUID_SPARK_GLUE_JARS_URL` | `s3://<bucket>/<prefix>/`: where the platform keeps the pinned jars a Glue Avro build loads. See [Avro on Glue](#avro-on-glue). |

A stream that reads a registry with a credential also needs the settings of the [Schema registry](./schema-registry.md#operator-settings) page. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* A build with `runtime: local` needs those of [Operator settings for a local run](#operator-settings-for-a-local-run).

### Contract SQL and `fluid validate`

*(since 0.33.0, [forge-cli #990](https://github.com/Agenticstiger/forge-cli/pull/990))* `fluid validate` asks `FLUID_SPARK_CONTRACT_SQL_ALLOWLIST` the question `fluid apply` asks, under the same environment, and warns about a build's own `properties.sql` only while apply would refuse it. A bundle is validated the same way. For a batch build with `properties.sql`, `fluid validate --strict` gives:

| The list holds | Warning | `--strict`, when nothing else warns |
|---|---|---|
| Nothing, or an entry for another build or product | Yes: the operator lists the product in this variable | Exit 1 |
| `<product>/<build>@sha256:<digest>` for other SQL | Yes, and it adds that the entry listed for the build approves other SQL (it changed after review) | Exit 1 |
| `<product>`, `<product>/<build>`, or `<product>/<build>@sha256:<digest>` for this SQL | No | Exit 0 |

The warning for an entry that pins other SQL, from forge-cli `main`:

```text
✅ Valid FLUID contract (schema v0.7.7)
⚠️  1 warning(s)
...
 1. Build load-orders: properties.sql is run only if the operator lists commerce.orders-batch in FLUID_SPARK_CONTRACT_SQL_ALLOWLIST, and the entry listed for it approves other SQL (it changed after review); properties.mapping is checked against the output before deploy and reads nothing but the stream
❌ Validation failed: warnings treated as errors (--strict)
```

The digest is the sha256 of the SQL with its leading and trailing whitespace stripped. When `fluid apply` refuses a build it prints the whole `export` line: your current list with the build's pinned entry added. Set the variable in the environment of the job that runs `fluid validate` as well as the one that runs apply: it is read from the real environment, so a validate job without it keeps the warning, and a pipeline whose stage 2 runs `fluid validate --strict` fails on it.

In 0.32.0 and earlier the warning was printed for every build with `properties.sql`, whatever the list held, so `fluid validate --strict` failed such a build even after the operator listed it. The managed Flink lane follows the same rule with `FLUID_FLINK_CONTRACT_SQL_ALLOWLIST`: see [A build's own SQL](./managed-flink-iceberg.md#a-build-s-own-sql).

### Spark settings

A contract's `sparkConf` may set sizing and tuning settings only: executor and driver memory, cores and instances, `spark.sql.shuffle.partitions`, `spark.default.parallelism`, adaptive execution (`spark.sql.adaptive.*`), dynamic allocation (`spark.dynamicAllocation.*`) and a few others. Any other key needs the operator to list it in `FLUID_SPARK_CONF_ALLOWLIST`.

Some keys are refused even when listed, by name or by a prefix such as `spark.sql.*`, because they load code or environment into a job that runs with its role, or move what it writes. The list is the same for `fluid apply` and the infrastructure emit. It holds:

- keys that load code: `spark.jars*`, `spark.files*`, `spark.archives`, `spark.submit.*`, `spark.pyspark.*`, `spark.python.*`, `spark.plugins*`, `spark.extraListeners`, `spark.sql.extensions`, the `extraClassPath`, `extraJavaOptions` and `extraLibraryPath` keys of the driver and executor, `defaultJavaOptions`, `userClassPathFirst`, and the classes that `spark.sql.adaptive.customCostEvaluatorClass` and `spark.sql.streaming.stateStore.providerClass` name;
- keys that set identity, credentials or environment: `spark.hadoop.*`, `spark.executorEnv.*`, `spark.emr-serverless.driverEnv.*` and `executorEnv.*`, `spark.yarn.*`, `spark.kubernetes.*`, `spark.kerberos.*`, `spark.security.*`, `spark.authenticate*`, `spark.ssl.*`, `spark.redaction.*`, `spark.emr-serverless.lakeformation.*`;
- keys that move what the job writes or switch off what the runner relies on: `spark.sql.catalog.*`, `spark.sql.catalogImplementation`, `spark.sql.defaultCatalog`, `spark.sql.warehouse.dir`, `spark.sql.streaming.checkpointLocation`, `spark.sql.queryExecutionListeners`, `spark.sql.streaming.streamingQueryListeners`, `spark.sql.variable.substitute`, `spark.sql.session.timeZone`, `spark.sql.mapKeyDedupPolicy`, `spark.eventLog.*`, `spark.ui.*`, `spark.master`, `spark.app.*`.

A key with a bad name or value gets its own message, and only a valid key that is not listed is told to be exported by the operator.

## Starting and reconciling runs

There is no OpenTofu resource for a job run, so runs are started by forge and not by the module.

`fluid plan` lists one `spark.reconcile` action per Spark build. `planDigest` covers it, and it needs no AWS credentials. *(since 0.33.0, [forge-cli #994](https://github.com/Agenticstiger/forge-cli/pull/994))* For an `emr-ec2` build, `fluid plan` and a non-dry-run `fluid apply` also read the cluster, when they can, to warn about Spot: see [What plan and apply check on the cluster](#what-plan-and-apply-check-on-the-cluster). The action's payload carries the runtime, mode, target, execution role, the artifact locations and a **config hash**: the sha256 of the job config, the runner's sha256 and the run settings (runtime, target, release, role, `sparkConf`, retries, and on Glue the pinned jars it loads). `fluid apply` compiles the runs again and refuses a bound plan whose Spark actions differ (`apply_spark_artifact_mismatch`). A non-dry-run apply of a streaming build on an AWS runtime also needs the `[aws]` extra (`apply_aws_sdk_missing`). Apply needs the OpenTofu engine (`apply_spark_needs_opentofu`) for a build on an AWS runtime. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* A build with `runtime: local` runs on any engine: see [Running a build on this machine](#running-a-build-on-this-machine).

After `tofu apply`, `fluid apply` reconciles each streaming build:

| Found | What apply does |
|---|---|
| A running job with this hash | Nothing. |
| A running job with another hash | Cancels it, waits for it to stop, and starts the new config on the **same checkpoint**, so it resumes where the old one stopped. |
| A new topic or cluster, with a checkpoint an earlier run read | Refuses, before cancelling anything. A checkpoint holds the offsets of one topic on one cluster. To read the new stream, move `properties.stream.checkpoint` to a new prefix: the job then starts from `startingOffsets`. |
| No running job | Starts one, unless the last run with this hash failed. *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* Unless it failed where the service's own retries are spent (EMR Serverless and EMR on EKS) or the [restart budget](#the-restart-budget) is spent: see the next row. |
| A last run that failed | An error that names the run and its reason. On EMR Serverless a streaming job retries until it fails more than `maxFailedAttemptsPerHour` times in an hour, and then stops, so starting it again would fail the same way. Fix the cause, then change the build: `fluid apply` starts it with the new config. *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* On EMR on EC2, Glue and a local build the stream is started again on its checkpoint within the [restart budget](#the-restart-budget), and the error is for a spent budget. EMR Serverless and EMR on EKS keep the error, as their own retries come first. |
| A second active copy of the current config | Cancels it. |
| A stream moved to `trigger.availableNow` | Cancels its old continuous job. Its scheduler starts it from now on. |

A scheduled build (batch, or a stream with `availableNow`) is reported as `scheduled` and is never reconciled: its scheduler starts it through `fluid apply --mode amend-and-build` (see [Scheduled Spark builds](./airflow.md#scheduled-spark-builds)). A Glue stream also restarts when a pinned jar or `FLUID_SPARK_GLUE_JARS_URL` changes, because the hash covers the jars it loads; a running Glue Avro stream restarts once on the release that added this. Plan and apply need the same `FLUID_SPARK_GLUE_JARS_URL`, because the plan binds the hash, and apply refuses a plan made with another.

Per runtime, the start is:

- **EMR Serverless:** `StartJobRun` with `mode=STREAMING` and a retry policy of `execution.retries.maxAttempts` attempts per hour (default 5, at most 10), or `BATCH`.
- **Glue:** `StartJobRun` on the build's job.
- **EMR on EC2:** `AddJobFlowSteps` on `clusterId`, with `spark-submit --deploy-mode client`, so cancelling the step stops the driver.
- **EMR on EKS:** `StartJobRun` on `virtualClusterId`.
- **Local:** *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* `spark-submit --deploy-mode client` on this machine, under a detached supervisor: see [Running a build on this machine](#running-a-build-on-this-machine).

### The restart budget

*(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* A stream that died is started again on its checkpoint, within a budget of restarts per rolling hour. A plain `fluid apply` follows the rule, and so does [`fluid apply --mode reconcile`](../cli/apply.md#reconcile-mode), which a keepalive runs. In 0.33.0 a stream whose last run ended `FAILED` was an error until the build changed, and `--mode reconcile` did not exist.

- **The budget** is `execution.retries.maxAttempts` restarts per rolling hour: 5 when it is unset, and at most 10, the numbers that EMR Serverless applies to its own streaming retries.
- **A death** is a run that ended `FAILED` or `INTERRUPTED` (an EMR step that died with its node), was lost with its machine, node or cluster, or was stopped by a signal from outside forge (a local run that was killed, or whose machine shut down), and a stream that stopped by itself. A local run whose supervisor got a signal from outside forge, a shutdown of the machine say, reads as failed now, and counts as a death: 0.33.0 read it as cancelled and started it again. A job killed on its own (`FAILED (exit -9)`) was failed in 0.33.0 too.
- **A cancel is not a death.** A run that was cancelled through the runtime (`aws emr cancel-steps`, `CancelJobRun`, `BatchStopJobRun`, or forge's own cancel of a local run) was stopped on purpose. `--mode reconcile` leaves it stopped, and a plain `fluid apply` starts it again, as the operator who applies asks, without counting a restart. To stop a stream on purpose, cancel its run: `--mode reconcile` leaves it stopped, and a plain `fluid apply` starts it again. A step that a terminating cluster cancelled while it was pending is not an operator's stop: the reconcile reports the ended cluster.
- **Who restarts.** forge restarts a stream on EMR on EC2, on Glue, whose job forge emits with `MaxRetries` 0, and on a local build: none of them has a service that retries. EMR Serverless and EMR on EKS retry a failed run themselves, from `execution.retries`. A run that ended `FAILED` there has spent those retries, and forge starts nothing on top of them; a stream there that stopped without failing restarts within the budget.
- **The count.** Each restart carries `--fluid-restart-of <run id>` in the runner's arguments, where the EMR console shows it in the step's arguments, and the budget is counted from the runtime's own run history (the `ListSteps` of EMR on EC2 reaches back an hour). forge keeps no state. A restart that was cancelled afterwards does not count.
- **A spent budget** starts nothing and is an error. It names the budget, the restarts and when the next one is allowed, and it is not final: once fewer restarts than the budget are under an hour old, the next apply or reconcile restarts the stream. To start it sooner, fix the cause and change the build, and `fluid apply` starts the new config.
- **`execution.retries` is no longer part of the config hash on EMR on EC2 and Glue**, and a local build has none: none of them takes a retry setting, so a new budget restarts nothing. A stream there that already declares `execution.retries` restarts once on its next apply.
- **Two at once.** When two reconciles start the same dead stream at once, say a keepalive tick and a CI apply, the older run is kept and the younger cancels its own start. Of two copies of one config, the older is kept, where 0.33.0 kept the newer.

On EMR on EC2, a stream whose last step died is started again with `--fluid-restart-of` naming it. This is the end of the new step's arguments, and the line `fluid apply` prints:

```text
--fluid-checkpoint 1a04314328989295 --fluid-job-sha256 5316fc870295d2ff984b6d407947d73ec4d316fdab2f0f48b3f34ba483d1d9dd --fluid-restart-of s-1
```

```text
Spark ingest-orders (emr-ec2): restarted run s-2 RUNNING on EMR cluster j-1ABCDEF. run s-1 ended FAILED: Driver exited with code 1; started again on the same checkpoint (restart 1 of 5 allowed per rolling hour)
```

With five restarts of the last hour already, it starts nothing, exits `1`, and says when the next restart is allowed:

```text
Spark ingest-orders (emr-ec2): failed run s-r4 FAILED on EMR cluster j-1ABCDEF. run s-r4 ended FAILED: Driver exited with code 1. Not started again: its budget of 5 restarts per rolling hour (execution.retries.maxAttempts, 5 when unset) is spent: s-r0 at 2026-11-19T07:06:11Z, s-r1 at 2026-11-19T07:14:11Z, s-r2 at 2026-11-19T07:22:11Z, s-r3 at 2026-11-19T07:30:11Z, s-r4 at 2026-11-19T07:38:11Z. It can restart from 2026-11-19T08:06:11Z, when fewer than 5 of them are under an hour old; to start it sooner, fix the cause and change the build, and fluid apply starts the new config. Earlier: run s-r3 ended FAILED: Driver exited with code 1; run s-r2 ended FAILED: Driver exited with code 1; run s-r1 ended FAILED: Driver exited with code 1
```

A cluster that ended takes no new step, so the stream cannot start there again. The error names the cluster's state and reason:

```text
Spark ingest-orders (emr-ec2): failed. EMR cluster j-1ABCDEF is TERMINATED_WITH_ERRORS (INTERNAL_ERROR: The master instance was lost) and takes no new step, so the stream cannot start there again. Point parameters.spark.clusterId at a running cluster and run fluid apply: the stream resumes from its checkpoint
```

On EMR Serverless a stream gets a retry policy of `execution.retries.maxAttempts` attempts per hour (5 when unset), so a run that ended `FAILED` has spent them. This is what `fluid apply` says then, for the default of 5:

```text
run jr-1 ended FAILED: Job failed: OutOfMemoryError. EMR Serverless retries a failed stream (retryPolicy.maxFailedAttemptsPerHour) from execution.retries (5), and it stopped retrying: forge does not start it again on top of the service's own retries, which would fail the same way; fix the cause and change the build, and fluid apply starts the new config
```

On EMR on EKS the service retries only as often as `execution.retries` says. A build that sets none is not retried, and the error says so:

```text
run jr-1 ended FAILED: Job failed: OutOfMemoryError. EMR on EKS retries a failed driver (retryPolicyConfiguration.maxAttempts) only as often as execution.retries says, and this build sets none, so it was not retried: forge does not start a failed run there again. Set execution.retries, or fix the cause and change the build, and fluid apply starts the new config
```

On a local build the same rules hold on this machine. When the cause was the machine's, say `spark-submit` or its properties file, the budget error names the run directory to remove: removing `.fluid/<product>/runtime/spark/<build>/runs` resets the build's history, and with it the budget. This is a plain `fluid apply` on a stream whose job fails at once, on 0.33.0's code and on `main` (the paths are shortened to `<project>`):

```text
Spark ingest-orders (local): failed run 20261119T075156Z-3449d58d FAILED on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders). run 20261119T075156Z-3449d58d ended FAILED (exit 1): log <project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs/20261119T075156Z-3449d58d/driver.log: the stream failed. It is not started again with the same config, which would fail the same way: fix the cause and change the build, and fluid apply starts the new config; when the cause was this machine's (spark-submit, its properties file), remove <project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs/20261119T075156Z-3449d58d and fluid apply starts it again
```

```text
Spark ingest-orders (local): restarted run 20261119T075203Z-c2b31396 FAILED on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders). run 20261119T075200Z-104292e4 ended FAILED (exit 1): log <project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs/20261119T075200Z-104292e4/driver.log: the stream failed; started again on the same checkpoint (restart 1 of 5 allowed per rolling hour); run 20261119T075203Z-c2b31396 ended FAILED (exit 1): log <project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs/20261119T075203Z-c2b31396/driver.log: the stream failed
```

The second run ended at once as well, so that apply exits `1`: a restart is not a recovery, and the next apply restarts it again until the budget is spent.

The outputs are from forge-cli's reconcile step. The EMR on EC2 ones are the code `fluid apply` runs after `tofu apply`, with AWS answered by botocore's test stubs: no cluster was touched. The EMR Serverless and EMR on EKS ones are the texts of the same code for a run that ended `FAILED`. The local ones are the real `fluid apply` with a stand-in `spark-submit`.

### An EMR on EC2 step starts once its policy is attached

*(since 0.33.0, [forge-cli #1005](https://github.com/Agenticstiger/forge-cli/pull/1005))*

A step on an `emr-ec2` cluster runs as the role of the cluster's instance profile, which the cluster's owner holds. Forge does not change that role: it belongs to the cluster's owner. `fluid apply` creates the build's least-privilege policy (the managed `aws_iam_policy` in [What forge provisions](#what-forge-provisions)), and the owner attaches it. On 0.32.0 the first `fluid apply` started the stream before anyone could attach the policy, so, unless the role already held the job's permissions, the step failed at once. In 0.33.0 a stream that failed is not started again with the same config. *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* It is started again on its checkpoint, within the [restart budget](#the-restart-budget).

Before it starts a step, `fluid apply` now reads the cluster's instance profile and the policies attached to the role in it, and starts nothing until the build's policy is among them. The refusal is the build's error and `fluid apply` ends with exit code `1`. The infrastructure is applied by then, so the policy exists, and the line gives the command that attaches it:

```text
Spark ingest-orders (emr-ec2): failed. not started: policy fluid-commerce.orders-stream-ingest-orders-744ba50a-spark is not attached to EMR_EC2_DefaultRole, the role its steps run as on j-1ABCDEF. Attach it, then apply again: aws iam attach-role-policy --role-name EMR_EC2_DefaultRole --policy-arn arn:aws:iam::123456789012:policy/fluid-commerce.orders-stream-ingest-orders-744ba50a-spark
```

The line is printed unbroken, and a narrow terminal wraps it at spaces: join the wrapped lines before you run the command. Attach the policy and run `fluid apply` again. Nothing was started, so that apply starts the stream. With the policy on the role, the same run prints `Spark ingest-orders (emr-ec2): started run s-1 RUNNING on EMR cluster j-1ABCDEF`.

- **What it reads.** `elasticmapreduce:DescribeCluster` for the cluster's instance profile, `iam:GetInstanceProfile` for the roles in it, and `iam:ListAttachedRolePolicies` for each role. The policy counts as attached when its name is among the policies attached to any role of the profile. The command names the first role, and `<the instance-profile role>` when the profile holds none.
- **When it does not run.** When forge cannot read them, for whatever reason, the step starts as it did before. A build that names its own `executionRoleArn` has no forge policy and is not checked, unless that role is named exactly like the forge policy. A dry run reads nothing.
- **Scheduled builds.** A scheduler's start, `fluid apply --mode amend-and-build`, goes through the same check: it prints the same line under the build, the build counts as failed, and `fluid apply` exits with code `1`. The scheduler's next run starts the build once the policy is attached.

The output above is from forge-cli's reconcile step, the code `fluid apply` runs after `tofu apply`, with AWS answered by botocore's test stubs: the real cluster, instance profile and role calls were not made.

### A run starts only on the config this apply compiled

*(since 0.34.0, [forge-cli #1014](https://github.com/Agenticstiger/forge-cli/pull/1014))* A run's job config is an object in S3, which the runtime reads when the run starts and again each time it starts the job again after a failure. Until this change nothing checked what the object held: a config that another `fluid apply` had put there since this one compiled its runs would run under the config hash of this apply's runs, and a later `fluid apply` would take the hash for the config. Now a run starts only on the config that `fluid apply` compiled, in two steps.

1. **`fluid apply` reads the job config and the runner back from S3 before it starts a run, and starts nothing unless both are the ones it compiled.** This is for the runs on AWS: EMR Serverless, Glue, EMR on EC2 and EMR on EKS. The job config counts when its [digest](#the-digest) is the compiled config's. The runner counts when it is, byte for byte, the runner that this forge-cli ships. On EMR on EC2 the [check that the policy is attached](#an-emr-on-ec2-step-starts-once-its-policy-is-attached) comes first. A mismatch is the build's error, and `fluid apply` ends with exit code `1`. Nothing new was started. A running job of another config, which `fluid apply` cancels before it starts the new one, is already cancelled by then, so the stream stays stopped until the next `fluid apply`:

   ```text
   Spark ingest-orders (emr-ec2): failed. Spark build ingest-orders: s3://commerce-lake/_fluid/spark/commerce.orders-stream/ingest-orders/job.json or its runner is not the one this apply compiled (another apply has changed it since); nothing was started. Run fluid apply again: it uploads them and starts the run on them
   ```

   An object that cannot be read, or is larger than 4 MiB, refuses the start in the same way. forge reads the config first and then the runner, and the message names the object it could not read: `s3://commerce-lake/_fluid/spark/commerce.orders-stream/ingest-orders/job.json cannot be read to check it before the run starts (AccessDenied); nothing was started`, or `... is larger than any artifact forge writes; nothing was started`. The word in parentheses is the code that AWS answered with, or the name of the error when AWS did not answer. A scheduler's start, `fluid apply --mode amend-and-build`, goes through the same check and fails in the same way.

2. **The run carries the digest, and the runner refuses any other config before it reads anything.** Every runtime, local included, starts the runner with `--fluid-job-sha256 <digest>` after the arguments that identify the run. These are the runner's arguments in the EMR on EC2 step of the example above:

   ```text
   --config s3://commerce-lake/_fluid/spark/commerce.orders-stream/ingest-orders/job.json --fluid-config-hash 4db36743c76cdbdd980138a0689119de161e565181a9546b0c3ca01a76ad0f49 --fluid-source 8de3ab14e359cfad --fluid-checkpoint 1a04314328989295 --fluid-job-sha256 5316fc870295d2ff984b6d407947d73ec4d316fdab2f0f48b3f34ba483d1d9dd
   ```

   The runner computes the digest of the config it reads, and when that is not the run's, it fails with `JobConfigError` before it reads a record. A runtime that starts the job again after a failure reads the config again, and the runner checks it again:

   ```text
   JobConfigError: the job config at s3://commerce-lake/_fluid/spark/commerce.orders-stream/ingest-orders/job.json is not the one fluid apply started this run on (its digest is 5316fc870295d2ff984b6d407947d73ec4d316fdab2f0f48b3f34ba483d1d9dd; the run's is 0000000000000000000000000000000000000000000000000000000000000000); nothing was read. Run fluid apply again: it starts a run on the config it uploads
   ```

   A run that someone starts by hand, without `--fluid-job-sha256`, is not checked.

#### The digest

The digest is the sha256 of the config's JSON in one canonical form: keys sorted, no spaces, strings in Unicode NFC (OpenTofu writes them so). Two things are not part of it as they are written. For a source that names an `mskClusterArn`, the broker list is left out, because OpenTofu fills it in at apply and MSK can change it, and a change would otherwise stop a stream's retries. The account number that OpenTofu fills into a config is the one that `fluid apply` fills into the compiled config before it compares. Every other field counts, a different `groupIdPrefix` included.

#### What the check does not cover

The check guards against another apply changing the config or the runner. Write access to the artifact bucket stays the boundary: someone who can write there can replace the runner after the read. The identity that runs `fluid apply` needs `s3:GetObject` on the two objects, and `kms:Decrypt` where the bucket encrypts them with a KMS key. The scheduler's policy `fluid-<product>-spark-caller` already holds `s3:GetObject` on both, but not `kms:Decrypt`: add that for the scheduler's role where the bucket encrypts them with a KMS key.

The runner changed, so each running Spark stream restarts once on its next apply, on its checkpoint.

The outputs are from forge-cli's reconcile step, the code `fluid apply` runs after `tofu apply`, with AWS answered by botocore's test stubs (the reads of S3 included), and from forge's runner, run as a script with a stand-in for Spark. No cluster, bucket or Spark job was involved.

### The caller's permissions

The role that runs `fluid apply`, or the scheduler's execution role (the MWAA role, say) that runs `fluid apply --mode amend-and-build` for a scheduled build, needs these actions. A scheduler's worker runs the whole apply, `tofu` included, so it also needs the apply's own permissions and the state backend, as for any scheduled build: the caller policy below covers the run only. For a build that runs to completion, the managed policy `fluid-<product>-spark-caller` holds them, scoped to the product's own application, job, cluster or virtual cluster:

| Runtime | Actions | Also |
|---|---|---|
| `emr-serverless` | `emr-serverless:StartJobRun`, `GetJobRun`, `ListJobRuns`, `CancelJobRun`, `TagResource`, and `ListApplications` when the contract names no `applicationId` | `iam:PassRole` on the job's role, with `iam:PassedToService` set to `emr-serverless.amazonaws.com` |
| `glue` | `glue:StartJobRun`, `GetJobRun`, `GetJobRuns`, `BatchStopJobRun` | |
| `emr-ec2` | `elasticmapreduce:AddJobFlowSteps`, `ListSteps`, `DescribeStep`, `CancelSteps` | *(since 0.33.0, [forge-cli #994](https://github.com/Agenticstiger/forge-cli/pull/994))* Also `DescribeCluster`, `ListInstanceGroups` and `ListInstanceFleets`, read-only, for the Spot check at plan and apply; the generated `fluid-<product>-spark-caller` policy includes them. Without them the check prints nothing. *(since 0.33.0, [forge-cli #1005](https://github.com/Agenticstiger/forge-cli/pull/1005))* A start also reads the cluster's role, to check that the build's policy is attached to it: `DescribeCluster`, and `iam:GetInstanceProfile` and `iam:ListAttachedRolePolicies` on `arn:aws:iam::<account>:instance-profile/*` and `arn:aws:iam::<account>:role/*`. The generated `fluid-<product>-spark-caller` policy holds `DescribeCluster` in its `Run` statement, scoped to the cluster, and the two IAM reads in a `StepRole` statement. Without them the step starts as before. |
| `emr-eks` | `emr-containers:StartJobRun`, `DescribeJobRun`, `ListJobRuns`, `CancelJobRun`, `TagResource` | `iam:PassRole` on the job's role, with `iam:PassedToService` set to `emr-containers.amazonaws.com` |

Scope `iam:PassRole` to the forge roles, so that a contract cannot pass a stronger one.

*(since 0.34.0, [forge-cli #1014](https://github.com/Agenticstiger/forge-cli/pull/1014))* A start on AWS also reads the build's job config and runner from S3, so the role needs `s3:GetObject` on both objects: see [A run starts only on the config this apply compiled](#a-run-starts-only-on-the-config-this-apply-compiled). The generated `fluid-<product>-spark-caller` policy holds it in an `Artifacts` statement, and holds no `kms:Decrypt`.

*(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* The policy also covers the product's always-on streams: it lets a role start, watch and stop their runs and read their job config and runner, so that a keepalive can run [`fluid apply --mode reconcile`](../cli/apply.md#reconcile-mode) from the scheduler's role (the MWAA role, say). It has one statement for each runtime, named `Run<Runtime>`, that lists the runtime's actions once for every target of the product's builds on it, one `PassRole<Runtime>` statement for each runtime that passes a role (EMR Serverless and EMR on EKS), and one `Artifacts` statement. Two more appear where they apply: `StepRoleEmrEc2`, the two IAM reads of an EMR on EC2 start, and `FindApplication`, `emr-serverless:ListApplications` on `*`, for an EMR Serverless build that names no `applicationId`. A managed policy holds at most 6,144 characters, and a statement for each build reached that limit at about six builds. Each build's target, role and artifacts are still named in them. A bucket that encrypts the artifacts with a KMS key also needs `kms:Decrypt` on its key for the scheduler's role, which forge does not grant. `--mode reconcile` reads the uploaded job config on every run, so a role that lacks `s3:GetObject` on it fails while the stream is healthy.

### When a build leaves the contract

*(since 0.34.0, [forge-cli #1008](https://github.com/Agenticstiger/forge-cli/pull/1008))* When a plan deletes the resources of a Spark build on AWS, because the build left the contract or the product went, `fluid apply` stops the build's runs before `tofu apply` destroys the role, the artifacts and the log group that they run with. Before this change the apply had no step for this. forge-cli's changelog says that it destroyed those and left the stream going, a writer that nothing reconciles any more, and that a destroy of a whole product failed part way, because EMR Serverless deletes only an application that is stopped or created and IAM deletes no policy that is still attached.

*(since 0.34.0, [forge-cli #1007](https://github.com/Agenticstiger/forge-cli/pull/1007))* Removing a build needs no `--allow-data-loss`, unless the build has a dead-letter table. What a Spark build runs with holds no data, so the [data-loss gate](../cli/apply.md#opentofu-data-loss-gate) does not count it: the runner and the job config in the artifact bucket, the copies of the jars that a Glue build loads, the build's log group, its role and the role's policies (for an EMR on EC2 build, its job policy), the Glue job and its connection, the product's own EMR Serverless application, the scheduler policy `fluid-<product>-spark-caller`, the key that encrypts the product's Spark log groups, and the role that a registered Lake Formation location is written through. [What forge provisions](#what-forge-provisions), [Avro on Glue](#avro-on-glue) and [Lake Formation writes](#lake-formation-writes) say which of them a build gets. forge-cli's changelog says that the gate counted all of them as data, so dropping a build from a contract was refused unless the apply was allowed to destroy data, and that allowance let a real data loss in the same plan through.

`fluid plan --tofu`, `fluid apply --dry-run` and `fluid apply` list them as removed and not gated. For the example contract's build on EMR on EC2, the line reads:

```text
  5 resource(s) a removed build ran with (its artifacts, role, log group and job; no table data lost; not gated; its logs go with them): aws_s3_object.commerce_orders_stream_ingest_orders_spark_runner, aws_s3_object.commerce_orders_stream_ingest_orders_spark_config, aws_cloudwatch_log_group.commerce_orders_stream_ingest_orders_spark, aws_iam_policy.commerce_orders_stream_ingest_orders_spark, aws_kms_key.commerce_orders_stream_spark_logs
```

What holds data still counts: an output table, a bucket, and a bucket's own key (its address ends in `_kms`). So does the dead-letter table of a stream with `sink: table`: the build adds it, and it goes when the build goes, so removing that build needs the flag. `fluid apply` refuses a plan that removes any of them unless it is given the flag, its `--dry-run` included, and `fluid plan --tofu` warns that it will. The refusal counts those alone. With the output table in the same plan, the five resources of the build are not part of the count:

```text
  error: plan destroys 1 resource(s); `tofu` does not snapshot data — re-run with --allow-data-loss to proceed
```

As for every plan, when the plan's per-resource events do not account for all the removals in its summary (an older `tofu`, a truncated stream), the gate counts every removal and the flag is needed.

After the gate, `fluid apply` reads the plan's deletes, and before `tofu apply` it does these:

1. **It refuses when a policy it would destroy is still attached.** forge emits two IAM managed policies that someone else attaches: an EMR on EC2 build's job policy, which the cluster's owner attaches to the cluster's instance-profile role, and the product's scheduler policy `fluid-<product>-spark-caller`, which the platform attaches to the scheduler's role. The apply ends with the error `opentofu_destroy_preparation_failed` and the kind `spark-policy-attached`. Nothing is stopped or destroyed. The error names where the policy is attached and the commands that detach it. Its text and remediation read:

   ```text
   IAM policy fluid-commerce.orders-stream-ingest-orders-744ba50a-spark (an EMR on EC2 build's job policy, which the cluster's owner attaches to its instance-profile role) is attached to role EMR_EC2_DefaultRole. The plan destroys it, and IAM deletes no attached policy (DeleteConflict), so the apply would stop part way through the destroys. Nothing was stopped or destroyed.
   Detach it, then run fluid apply again:
   aws iam detach-role-policy --role-name EMR_EC2_DefaultRole --policy-arn arn:aws:iam::000000000005:policy/fluid-commerce.orders-stream-ingest-orders-744ba50a-spark
   ```

2. **It stops the runs of each build that goes.** A build's runs are looked for where the tags of its log group say they are (see [the tags](#the-tags-that-say-where-a-build-runs)), or, for an EMR on EC2 build, of its job policy. A Glue job that goes has its runs stopped too, even when the build stays: a build moved off Glue keeps its log group. Every active run that the runtime's list returns is cancelled, and one that is already cancelling is only waited for. The apply waits for each to end. EMR Serverless, EMR on EC2 and EMR on EKS runs are found by the build's run name, and a Glue job's runs by the job. Glue lists the 25 most recent runs of a job, and EMR on EKS one page of them, so stop an older run yourself. The builds are taken in the plan's order.

   ```text
     Spark ingest-orders (emr-ec2): stopped on EMR cluster j-1ABCDEF. cancelled s-1 before the apply destroys what it runs with
   ```

3. **It empties and stops the product's own EMR Serverless application, when that goes.** Every active run in it is cancelled, whichever build started it, and then the application is stopped and waited for, unless it is already stopped or created. *(since 0.34.0, [forge-cli #1017](https://github.com/Agenticstiger/forge-cli/pull/1017))* An application that is still `CREATING` or `STARTING` is waited for until it settles first: one that has been created is deleted as it is, and one that has started is stopped. One still moving after the wait refuses the apply. An application that the contract only names is not one the plan deletes, so it is left as it is.

   ```text
     EMR Serverless application fluid-commerce.orders-stream-spark (00fabc123def): cancelled jr1 before the apply destroys what it runs with; stopped the application.
   ```

A build that moves from an EMR on EC2 cluster to another runtime keeps its log group, whose tags then name the new runtime. Its job policy goes, and carries the old cluster, so the steps on the old cluster are cancelled as well. A build that moves from EMR Serverless or EMR on EKS to another runtime keeps its log group too, and the apply does not look for its old runs then: stop them yourself.

A run that is still going after the wait, an application that has not stopped after it, or an AWS error on a run or on the application, refuses the apply before anything is destroyed, with the error `opentofu_destroy_preparation_failed` and the kind `spark-destroy-runs-going`. An AWS answer that the target no longer exists is not an error: nothing runs there. The wait is [`FLUID_SPARK_WAIT_SECONDS`](./environment-variables.md#spark-on-aws-preview) for each run and for the application's stop, 900 seconds by default. Run `fluid apply` again once the runs have ended, or stop them yourself. The text and remediation of the error read:

```text
Spark ingest-orders (emr-ec2): run s-1 was cancelled but is still CANCEL_PENDING after 3 s (FLUID_SPARK_WAIT_SECONDS). The plan destroys what these runs run with, so nothing was destroyed.
Run fluid apply again once the runs have stopped, or stop them yourself.
The identity running fluid apply needs the runtime's list and cancel actions (as for starting runs), iam:ListEntitiesForPolicy for a policy it destroys, and emr-serverless:GetApplication and emr-serverless:StopApplication for the product's own EMR Serverless application.
```

With `--dry-run`, the apply reads the policies and the runs, changes nothing, and says what it would do. A policy that is still attached refuses a dry run too, with the same error and exit code 1. An AWS error while it reads the runs is then a note and not a refusal:

```text
  Spark ingest-orders (emr-ec2): planned on EMR cluster j-1ABCDEF. would cancel s-1
```

#### The tags that say where a build runs

The log group of every Spark build, and an EMR on EC2 build's job policy, carry three tags: `fluid_runtime`, `fluid_run_target` (`applicationId=<id>`, `glueJobName=<name>`, `clusterId=<id>` or `virtualClusterId=<id>`) and `fluid_run_region`. A destroy reads them from the state, because the build is no longer in the contract. The first `fluid apply` after the upgrade adds them to the existing resources in place. A build that a forge without them deployed, and that goes in that same apply, has none, and the apply cannot tell from them where its runs are. It prints a note, and stops no run of that build, unless the plan also deletes the build's Glue job or the product's own EMR Serverless application: the runs of a Glue job, and every run in that application, are stopped without the tags.

```text
  note: Spark build ingest-orders goes, but nothing it is destroyed with says where it runs (an apply by an earlier forge): stop its run fluid-commerce.orders-stream-ingest-orders-744ba50a yourself if one is going.
```

#### What the identity needs

Besides the list, get and cancel actions of the runtime that the removed build ran on, which can be a runtime the contract no longer names (see [The caller's permissions](#the-caller-s-permissions)), the identity that runs `fluid apply` needs `iam:ListEntitiesForPolicy`, to tell whether a policy is attached, and, for the product's own EMR Serverless application, `emr-serverless:ListJobRuns`, `GetJobRun` and `CancelJobRun` as well as `emr-serverless:GetApplication` and `emr-serverless:StopApplication`.

The outputs above, but the two of the data-loss gate, come from forge-cli's destroy step, the code `fluid apply` calls with the plan's deletes before `tofu apply`, with AWS answered by botocore's test stubs and the plan's deletes built as forge-cli's own tests build them: no AWS account, cluster or application was touched, and the printed account number is a placeholder. The two outputs of the data-loss gate come from forge-cli's plan review, the code that `fluid plan --tofu` and `fluid apply` run on the plan's deletes after `tofu plan`. The deletes given to it are the resources that the example contract's build adds to the module, which a plan deletes when the build is removed, and, for the second output, the contract's output table: no `tofu`, state or AWS call was involved.

## Running EMR on EC2 on Spot

A stream on EMR on EC2 runs as one step of a cluster you already run (`clusterId`). forge creates no cluster, so the layout below is a checklist for the cluster's owner. Only the `sparkConf` values in items 4 and 6 go in the contract. Its aim is that a Spot interruption costs time and not records.

What forge does with the cluster decides what the layout must protect:

- **The driver is the step's own process.** forge starts the stream with `spark-submit --deploy-mode client`, so that cancelling the step stops the job. AWS's Spark step guide says client mode launches the driver on the cluster's primary instance.
- **The checkpoint is in S3, not on the cluster.** It defaults to `s3://<bucket>/_checkpoints/<product>/<build>/`, so losing nodes loses no offsets.
- **A step that ends `FAILED` or `INTERRUPTED` counts as failed, and `fluid apply` does not start it again with the same config.** It names the run and its state and starts nothing, because the same config would fail the same way (see [Starting and reconciling runs](#starting-and-reconciling-runs)). To bring the stream back, change the build. *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* `fluid apply` and `--mode reconcile` start such a step again on the stream's checkpoint, within the [restart budget](#the-restart-budget): an `INTERRUPTED` step, which died with its node, is a restart like any other, and the error is for a spent budget. After a lost cluster, launch a replacement with forge's policy attached to its instance-profile role, and set `clusterId` to it, with its `emr-ec2:<clusterId>` entry in `FLUID_SPARK_TARGET_ALLOWLIST`: the target is part of the config hash, so `fluid apply` starts the stream on the same checkpoint.

The checklist:

1. **On-Demand primary and core nodes.** The driver runs on the primary node, and the cluster ends when the primary is lost. AWS advises Spot for the primary only where sudden termination is acceptable, and for core nodes only where losing part of the HDFS data is tolerable. Task nodes hold no HDFS data, so Spot belongs there.
2. **Spot task fleets, with `price-capacity-optimized` allocation and diverse instance types.** Use instance fleets, and set the task fleet's Spot `AllocationStrategy` to `price-capacity-optimized`: AWS recommends it, and it is the default from EMR 6.10.0. List several instance types: when EC2 reclaims a Spot instance, EMR tries to replace it with any type on the list. Offer subnets in several Availability Zones too. EMR picks the zone it judges best for the fleet when it creates the cluster, and the cluster's instances then run in that one zone.
3. **YARN application masters pinned to On-Demand (EMR 7.2.0 and later).** In the cluster's `yarn-site` classification, set `yarn.node-labels.enabled` to `true` and `yarn.node-labels.am.default-node-label-expression` to `ON_DEMAND`. AWS warns that an application master on a Spot node can mean "immediate shutdown of the entire YARN application". Set it when you create the cluster: EMR does not add node labels when you reconfigure a running one. AWS describes this setting for clusters that use managed scaling, and its blog post shows instance groups. The example below uses instance fleets and no managed scaling, so check on the running cluster that YARN lists an `ON_DEMAND` node label. Settings that start with `spark.yarn.` are refused in `sparkConf` even when the operator lists them, so this belongs to the cluster and not to the contract.
4. **A minimum On-Demand executor baseline for streams.** Size the On-Demand capacity (the core nodes, and any On-Demand part of a task fleet) for the executors the stream needs to keep committing batches when every Spot node is gone, and tell Spark that number in `sparkConf`: `spark.dynamicAllocation.minExecutors` with dynamic allocation, or `spark.executor.instances` without it. Both are allowed without an operator entry, and both fix a count, not where the executors run. When Spot nodes are reclaimed, YARN can place a replacement executor only on the nodes that remain. Where YARN puts executors while Spot nodes exist depends on the cluster's node labels, so look at where they ran in the interruption test (item 6).
5. **Kafka retention at least as long as the longest downtime you tolerate.** A restarted stream resumes from the offsets in its checkpoint, so the topic must still hold them. Count the whole outage: detecting the loss, replacing the cluster, starting the step, and catching up. Set the topic's `retention.ms` (Kafka's default is 7 days) to at least that, and leave `retention.bytes` unset (`-1`) or size it for the same window, because a topic discards a segment at whichever limit it reaches first. forge's runner leaves Spark's Kafka option `failOnDataLoss` at its default, `true`, so a stream whose checkpointed offsets have aged out fails and does not skip records. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* The same holds for a batch that a restart replays into a [dead-letter table](#how-the-records-land) or into the output through Iceberg's streaming sink: each is appended only once while the snapshot that records the batch is still in the table, so run `expire_snapshots` with a retention longer than the longest downtime you tolerate. *(since 0.34.0, [forge-cli #1015](https://github.com/Agenticstiger/forge-cli/pull/1015))* The runner sets `failOnDataLoss` to `true` on every Kafka source, so it no longer depends on Spark's default. Offsets that the topic no longer holds, because retention passed them while the stream was stopped or because the topic was recreated, fail the stream with a Spark error whose message contains `Some data may have been lost because they are not available in Kafka any more`.
6. **Spark decommissioning only after a measured interruption test.** Leave Spark's own decommissioning off until a test shows that it helps.
   - **What is already there.** EC2 sends a Spot interruption notice two minutes before it reclaims an instance, on a best-effort basis. EMR on EC2 has its own decommissioning for Spark, built on YARN's. Spark schedules no new tasks on a node that YARN is decommissioning, and lets the running tasks finish (`spark.blacklist.decommissioning.enabled`, `true` by default). `spark.decommissioning.timeout.threshold` (20 seconds by default, EMR 5.11.0 and later) is for Spot: a Spot instance decommissions within 20 seconds whatever the YARN decommissioning timeout is, and a node that will decommission within the threshold is deny-listed and cleaned up without waiting.
   - **What is separate.** Spark's own `spark.decommission.enabled` (`false` by default since Spark 3.1.0) and its `spark.storage.decommission.*` settings. A contract may set them only when the operator lists them in `FLUID_SPARK_CONF_ALLOWLIST`.
   - **The test.** Interrupt the Spot task instances on purpose while the stream runs, with AWS Fault Injection Service: its action `aws:ec2:send-spot-instance-interruptions` sends the notice to the Spot instances an experiment targets, and `durationBeforeInterruption` sets the wait before the interruption, from 2 to 15 minutes. Run it with decommissioning off, then on.
   - **What to record**, for the same load each time: the executors lost, the tasks and stages retried, the longest batch, whether the query kept running, how far behind Kafka it fell and how long it took to catch up, and whether the table holds the rows of a run with no interruption. Keep the setting only if the numbers improve.

Once per account, before the first cluster that uses Spot: a Spot request made through the API or the CLI needs the service-linked role `AWSServiceRoleForEC2Spot` to exist, and EC2 creates it itself only on a first Spot request from the console. Create it with `aws iam create-service-linked-role --aws-service-name spot.amazonaws.com`.

A cluster that follows items 1 to 3, as the parameters of the EMR `RunJobFlow` call (checked against the EMR API model in botocore, not run against an account). The instance types, sizes and counts are examples:

```json
{
  "ReleaseLabel": "emr-7.12.0",
  "Instances": {
    "KeepJobFlowAliveWhenNoSteps": true,
    "Ec2SubnetIds": ["subnet-0aaa1111", "subnet-0bbb2222", "subnet-0ccc3333"],
    "InstanceFleets": [
      {
        "Name": "primary",
        "InstanceFleetType": "MASTER",
        "TargetOnDemandCapacity": 1,
        "InstanceTypeConfigs": [{"InstanceType": "m5.xlarge"}]
      },
      {
        "Name": "core",
        "InstanceFleetType": "CORE",
        "TargetOnDemandCapacity": 4,
        "InstanceTypeConfigs": [{"InstanceType": "r5.2xlarge"}]
      },
      {
        "Name": "task-spot",
        "InstanceFleetType": "TASK",
        "TargetSpotCapacity": 8,
        "InstanceTypeConfigs": [
          {"InstanceType": "r5.2xlarge"},
          {"InstanceType": "r5a.2xlarge"},
          {"InstanceType": "r5d.2xlarge"},
          {"InstanceType": "r5n.2xlarge"},
          {"InstanceType": "r6i.2xlarge"},
          {"InstanceType": "r6a.2xlarge"}
        ],
        "LaunchSpecifications": {
          "SpotSpecification": {
            "AllocationStrategy": "price-capacity-optimized",
            "TimeoutDurationMinutes": 30,
            "TimeoutAction": "TERMINATE_CLUSTER"
          }
        }
      }
    ]
  },
  "Configurations": [
    {
      "Classification": "yarn-site",
      "Properties": {
        "yarn.node-labels.enabled": "true",
        "yarn.node-labels.am.default-node-label-expression": "ON_DEMAND"
      }
    }
  ]
}
```

`TimeoutDurationMinutes` and `TimeoutAction` are required with a Spot specification. They apply while the cluster is created: `TERMINATE_CLUSTER` fails the launch when EMR cannot provision the Spot capacity in time, and `SWITCH_TO_ON_DEMAND` buys the rest On-Demand instead. The call also needs `Name`, `Applications` (Spark), `JobFlowRole` and `ServiceRole`, left out here.

### What plan and apply check on the cluster

*(since 0.33.0, [forge-cli #994](https://github.com/Agenticstiger/forge-cli/pull/994))* For the `clusterId` of each `emr-ec2` build, `fluid plan` and `fluid apply` read the cluster once, however many builds run on it (`DescribeCluster`, then `ListInstanceGroups`, or `ListInstanceFleets` for an instance-fleet cluster), and warn when it breaks item 1 or 3 of the checklist. A warning never refuses the plan or the apply, and none is in `plan.json`. There are three:

| Finding | When |
|---|---|
| The primary node runs on Spot | A Spot instance group or fleet holds the primary node. The build's driver runs there, so an interruption ends the cluster and the build's run. |
| Core nodes run on Spot | A Spot instance group or fleet holds the core nodes: an interruption takes their HDFS blocks and the YARN containers they run. |
| An application master can land on Spot | Core or task nodes run on Spot, and the cluster's `yarn-site` does not keep application masters on On-Demand nodes: `yarn.node-labels.enabled` is `true` and `yarn.node-labels.am.default-node-label-expression` is `ON_DEMAND` (counted from EMR 7.0, when EMR starts labelling nodes by market; the fix names it from 7.2, where managed scaling places masters by it), or `CORE` while the core nodes are all On-Demand. EMR 5.19 to 5.x start with `CORE`, and 6.x and 7.x with no label. |

Each warning names its fix. On a cluster whose task nodes run on Spot and whose `yarn-site` sets no label, `fluid plan` prints (from forge-cli `main`, run against a stand-in for the EMR API):

```text
⚠️  EMR cluster j-2AXXXXXXGAPLF (Spark build ingest-orders): YARN can place the build's application master on a Spot node (yarn.node-labels.enabled is unset). A master has to live as long as its job, so a Spot interruption of that node interrupts the job.
    Fix: set yarn-site yarn.node-labels.enabled=true and yarn.node-labels.am.default-node-label-expression=ON_DEMAND, when the cluster is created or by reconfiguring its primary instance group.
spark_cluster_posture
```

- **The fix also offers reconfiguring a running cluster.** AWS says EMR does not add node labels that way (item 3 above), so after a reconfiguration check that YARN lists an `ON_DEMAND` node label.
- **The fix names `ON_DEMAND` from EMR 7.2 and `CORE` before**, the latter with On-Demand core nodes. For a cluster of fleets it says "primary fleet" for "primary instance group".
- **Which `yarn-site`.** The cluster's, overridden by the applied configuration of the primary instance group, or for a fleet cluster by the primary fleet's instance types when they agree. When they do not agree, the check says nothing about application masters.
- **A cluster it cannot read prints nothing.** That covers a missing `[aws]` extra (boto3), no credentials, a call AWS refuses, an endpoint that does not answer, and a cluster that is ending or ended. `fluid plan` and `fluid apply` carry on as before, and `fluid apply --dry-run` reads nothing. Each call waits at most 3 seconds to connect and 10 seconds to answer, in two attempts.
- **Permissions.** The three read actions in [The caller's permissions](#the-caller-s-permissions).

## Network and packages

A streaming run resolves its pinned packages when it starts:

| Package | Used for |
|---|---|
| `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1` | Reading Kafka |
| `software.amazon.msk:aws-msk-iam-auth:2.2.0` | MSK IAM authentication |
| `org.apache.spark:spark-avro_2.12:3.5.1` and `za.co.absa:abris_2.12:6.4.0` | Confluent Avro |

Iceberg is on the EMR runtimes already, at `/usr/share/aws/iceberg/lib/iceberg-spark3-runtime.jar`, and Glue gets it from `--datalake-formats iceberg`. **The cluster needs outbound HTTPS** to Maven Central, and to Confluent's repository for Avro: the subnets of the EMR Serverless application and the subnet of the Glue `NETWORK` connection. forge creates no NAT gateway.

*(since 0.31.0, [forge-cli #919](https://github.com/Agenticstiger/forge-cli/pull/919))* An operator without that egress sets `FLUID_SPARK_MAVEN_REPOSITORY` to one https mirror (CodeArtifact or Artifactory, with Maven Central and Confluent's repository behind it). It replaces Confluent's repository in `spark.jars.repositories`. Spark 3.5 still tries Maven Central and spark-packages first, so without egress those attempts fail, which can be slow, and the resolver then falls through to the mirror. The variable is read from the real environment only. A URL with a user or a password, a query, a comma, a link-local or metadata host, or plain http is refused, and the message names the rule and never the URL. A mirror that needs a credential is not supported: use one that the job's role reaches with IAM. A contract's `sparkConf` cannot replace it. Glue resolves no packages, so the mirror does not apply there.

### Avro on Glue

*(since 0.31.0, [forge-cli #927](https://github.com/Agenticstiger/forge-cli/pull/927))* Glue 5.0 ships Spark, the Kafka connector, `kafka-clients`, the MSK IAM library, `spark-avro` and Iceberg, but not ABRiS, and the Confluent registry client it holds is inside a Hudi bundle. So a Glue build that decodes Confluent Avro loads seven jars that forge pins by sha256: ABRiS 6.4.0 for Scala 2.12, `za.co.absa.commons` 1.0.0, and the Confluent 6.2.1 clients ABRiS is built against (`kafka-avro-serializer`, `kafka-schema-serializer`, `kafka-schema-registry-client`, `common-config`, `common-utils`). The Confluent clients are from 2021: the pins protect integrity, not against known CVEs, so re-pin when ABRiS moves. A JSON build, an MSK IAM build and an EMR build add no jars.

The operator keeps the jars in an S3 prefix and tells forge where:

```bash
export FLUID_SPARK_GLUE_JARS_URL=s3://<platform-bucket>/spark-jars/
```

To fill the prefix:

1. Download each jar from Maven Central or packages.confluent.io, and check its sha256 against the pin that `aws_glue_jars.AVRO_JARS` lists.
2. Upload it as a single part with `aws s3 cp <jar> s3://<platform-bucket>/spark-jars/<file> --checksum-algorithm SHA256`. A recent AWS CLI defaults to CRC64NVME, which leaves no SHA-256 for the check, and a multipart upload has a composite checksum.
3. Keep the prefix write-once: only the platform's principal may `s3:PutObject` there, with S3 Object Lock or a bucket policy that refuses overwrites.

The setting is protected: a project `.env` cannot set it, and the contract never names a jar. What forge does with it:

- `tofu plan` reads each jar with its checksum and refuses one whose SHA-256 is not the pin: a swapped jar, a multipart upload, or one with no SHA-256 checksum fails the plan with a message that names the pin.
- Apply copies exactly the verified bytes into the build's own prefix, `_fluid/spark/<product>/<build>/jars/<16 hex digits>/<file>`. S3 refuses the copy if the source's ETag is not the one the plan verified.
- The Glue job loads only those copies, with `--extra-jars`, and `--user-jars-first true` for an Avro build, because Glue's Hudi bundle carries its own copy of the registry client classes.
- The job's role reads its own artifact prefix and nothing on the platform's. Only the applier needs `s3:GetObject`, and `kms:Decrypt` where the prefix is encrypted, on the platform prefix.
- A jar swapped in the platform's prefix after an apply therefore never reaches a run, and a changed source ETag is refused by the next plan before it is copied again. A new pin is a new key, and restarts a running stream.

`fluid validate` warns when an Avro Glue build has no prefix or a malformed one. `fluid generate iac` and `fluid apply` refuse with `spark-glue-jars-unset` or `spark-glue-jars-url`. The other fix is to run the build on EMR Serverless, which resolves its jars from Maven.

## Lake Formation writes

*(since 0.31.0, [forge-cli #918](https://github.com/Agenticstiger/forge-cli/pull/918))* A contract that sets `registerLocation: true` on the output's binding and has a forge Spark job write the table gets a different registration. Lake Formation's service-linked role has no `s3:PutObject`, and EMR 7.12 writes Iceberg with the credentials Lake Formation vends. So forge registers the location with a role of the product's instead:

- The role trusts `lakeformation.amazonaws.com`, reads and writes the registered prefix, and has KMS through S3. `aws_lakeformation_resource` gets `use_service_linked_role = false`.
- Each writer's role is granted `ALTER`, `DESCRIBE`, `INSERT` and `SELECT` on the table, and `DELETE` for a batch overwrite. It is not granted `DATA_LOCATION_ACCESS`, because the table exists.
- A registered location that a Spark job writes must be one named, resolved prefix: no bucket root and no unresolved template. It gets one role per location.
- Without a Spark writer, the registration is unchanged.
- **A dead-letter table.** *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* When `binding.governance.lakeFormation` governs the output, a stream's dead-letter table gets the writer's role `ALTER`, `DESCRIBE`, `INSERT` and `SELECT`, without `DELETE`. A dead-letter table beside a location forge registers is refused: see [What is refused](#what-is-refused). Without a block, see [A job's grant on its own table](#a-job-s-grant-on-its-own-table).
- **The apply role needs `iam:PassRole`** on the registration role, because `lakeformation:RegisterResource` passes it.
- **Moving a registered location from the service-linked role to the new role re-registers it.** While that runs, Lake Formation vends no credentials for the location, so jobs that are running on it may fail for that short window.

In the account's `<account>-fluid-data` fallback bucket, and in a `shared` packaging pool's bucket, a forge role writes only the product's own `<product>/` prefix.

### A job's grant on its own table

*(since 0.34.0, [forge-cli #1010](https://github.com/Agenticstiger/forge-cli/pull/1010))* Up to 0.33.0 forge granted a job's role Lake Formation access to its table only for an output whose binding declares a non-empty `governance.lakeFormation` block. In an account that removed the `IAM_ALLOWED_PRINCIPALS` default for new tables, as Lake Formation advises, a stream with no such block could not see its own table. forge now emits the grant for such an output as well, when the output is a Glue table: `ALTER`, `DESCRIBE`, `INSERT` and `SELECT` on the output's table, with `DELETE` for a batch job, and `ALTER`, `DESCRIBE`, `INSERT` and `SELECT` on the dead-letter table of a stream beside it. The module is the same text in every account. The plan decides whether each grant exists: the module reads the account's Lake Formation settings, and the grant has a `count` of 1 when none of the settings' default permissions for new tables names `IAM_ALLOWED_PRINCIPALS`, and 0 when one does. An account that keeps that default creates nothing new. This is what `fluid generate iac` emits for the example contract on EMR Serverless:

```json
{
  "data": {
    "aws_lakeformation_data_lake_settings": {
      "commerce_orders_stream_lf_settings": {}
    }
  },
  "resource": {
    "aws_lakeformation_permissions": {
      "commerce_orders_stream_lf_spark_writer_order_lines_0": {
        "count": "${length([for d in data.aws_lakeformation_data_lake_settings.commerce_orders_stream_lf_settings.create_table_default_permissions : d if d.principal == \"IAM_ALLOWED_PRINCIPALS\"]) == 0 ? 1 : 0}",
        "principal": "${aws_iam_role.commerce_orders_stream_ingest_orders_spark.arn}",
        "permissions": ["ALTER", "DESCRIBE", "INSERT", "SELECT"],
        "table": [
          {
            "database_name": "${aws_glue_catalog_table.commerce_orders_stream_commerce_order_lines.database_name}",
            "name": "${aws_glue_catalog_table.commerce_orders_stream_commerce_order_lines.name}"
          }
        ]
      }
    }
  }
}
```

An output with a non-empty `governance.lakeFormation` block keeps its grants as they are, and no settings are read for it. An EMR on EC2 job runs as the cluster's own role, which forge does not know, so it gets no grant and no settings are read.

*(since 0.34.0, [forge-cli #1010](https://github.com/Agenticstiger/forge-cli/pull/1010))* The identity that runs `fluid plan` and `fluid apply` needs `lakeformation:GetDataLakeSettings`, for a Spark build on any runtime but EMR on EC2 whose output is a Glue table with no `governance.lakeFormation` block. The grant goes to the job's role whether forge creates it or the contract names it.

## Errors

| Event or kind | Meaning |
|---|---|
| `spark-emr-application-shared` | An EMR Serverless build with no `applicationId` and no `emrApplication: isolated` |
| `spark-checkpoint-scope` | A declared checkpoint outside `s3://<bucket>/_checkpoints/<product>/`, while forge creates the role |
| `spark-glue-jars-unset`, `spark-glue-jars-url` | A Glue Avro build, and `FLUID_SPARK_GLUE_JARS_URL` is unset or malformed |
| `spark-policy-attached` | *(since 0.34.0, [forge-cli #1008](https://github.com/Agenticstiger/forge-cli/pull/1008))* The plan destroys an IAM policy that is still attached: an EMR on EC2 build's job policy or the product's scheduler policy. The error is `opentofu_destroy_preparation_failed`. See [When a build leaves the contract](#when-a-build-leaves-the-contract). |
| `spark-destroy-runs-going` | *(since 0.34.0, [forge-cli #1008](https://github.com/Agenticstiger/forge-cli/pull/1008))* A run of a build that goes, or the product's own application, is still going after `FLUID_SPARK_WAIT_SECONDS`, or AWS refused to list, cancel or stop it. The error is `opentofu_destroy_preparation_failed`. See [When a build leaves the contract](#when-a-build-leaves-the-contract). |
| `spark-dead-letters-table-unsupported` | *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* A `deadLetter` table sink beside an output at its bucket's root, beside a location forge registers with Lake Formation, or beside an output whose lifecycle expires its objects. See [What is refused](#what-is-refused). |
| `apply_spark_refused` | `fluid apply` refuses a Spark build before `tofu apply` changes anything when an operator's list does not allow what the build names: an MSK cluster that `FLUID_SPARK_TARGET_ALLOWLIST` does not list, a host, a secret reference, or a `sparkConf` key. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* It also refuses a `deadLetter` topic that `FLUID_SPARK_TARGET_ALLOWLIST` does not list (see [Listing the topic](#listing-the-topic)), and, for a local build, a namespace that `FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST` does not list (see [The table the job creates](#the-table-the-job-creates)). |
| `apply_spark_artifact_mismatch` | The bound plan lists other Spark runs than apply compiles |
| `apply_aws_sdk_missing` | boto3 is not installed: `pip install 'data-product-forge[aws]'` |
| `apply_spark_needs_opentofu` | The contract's apply engine is not OpenTofu, and it has a Spark build on an AWS runtime. *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* A build with `runtime: local` is not refused. |
| `apply_spark_invalid` | A Spark build the runner would refuse (a contract before the 0.7.7 managed lane, or an `execution.runtime.timeout` that is not an ISO-8601 duration of at least one second), refused before `tofu apply` changes anything |
| `apply_spark_local_unavailable` | *(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))* A build with `runtime: local` whose `spark-submit`, properties file or artifact root this machine cannot use, refused before anything is applied. See [Operator settings for a local run](#operator-settings-for-a-local-run) |

## See also

- [Scheduled Spark builds](./airflow.md#scheduled-spark-builds): the `fluid apply` DAG that runs a scheduled build.
- [Schema registry](./schema-registry.md): `stream.registry`, produced subjects and the registry operator settings.
- [Managed Flink to Iceberg](./managed-flink-iceberg.md): the `properties.stream` and `properties.mapping` this lane shares.
- [Scheduling Spark builds on Airflow](./airflow.md#scheduled-spark-builds).
- [Environment variables](./environment-variables.md#spark-on-aws-preview): every variable this lane reads.
