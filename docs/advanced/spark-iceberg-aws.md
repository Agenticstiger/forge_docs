---
title: Spark to Iceberg on AWS (preview)
description: Declare a Kafka stream, or batch SQL over catalog tables, in the contract; forge-cli compiles the Spark job, provisions its infrastructure with OpenTofu on EMR Serverless, Glue, EMR on EC2 or EMR on EKS, and starts and reconciles its runs.
---

# Spark to Iceberg on AWS (preview)

*(since 0.31.0, [forge-cli #902](https://github.com/Agenticstiger/forge-cli/pull/902), [forge-cli #903](https://github.com/Agenticstiger/forge-cli/pull/903), [forge-cli #904](https://github.com/Agenticstiger/forge-cli/pull/904), [forge-cli #912](https://github.com/Agenticstiger/forge-cli/pull/912), [forge-cli #918](https://github.com/Agenticstiger/forge-cli/pull/918), [forge-cli #919](https://github.com/Agenticstiger/forge-cli/pull/919), [forge-cli #924](https://github.com/Agenticstiger/forge-cli/pull/924), [forge-cli #927](https://github.com/Agenticstiger/forge-cli/pull/927), [forge-cli #934](https://github.com/Agenticstiger/forge-cli/pull/934), [forge-cli #950](https://github.com/Agenticstiger/forge-cli/pull/950))*

A build with `engine: spark` and `parameters.spark` (under `builds[].properties`) lands records in an Iceberg table that the Glue catalog holds:

- The contract says which Kafka topic the job reads, or which SQL it runs over catalog tables, and how the result becomes the rows of the output expose.
- forge-cli compiles that into a `job.json` and checks every output column against it before anything deploys.
- OpenTofu provisions what the job needs: its artifacts, role, logs and, where the contract asks for it, the EMR Serverless application or the Glue job.
- `fluid apply` starts the job and keeps a streaming one running. A scheduled one runs through `fluid apply <contract> --mode amend-and-build --build-id <id>`, the path every scheduled build takes: see [Scheduled Spark builds](./airflow.md#scheduled-spark-builds).

The lane is opt-in: the contract declares `fluidVersion: "0.7.7"`, the preview schema, and the build sets `parameters.spark`. It reads the same `properties.stream` and `properties.mapping` as the [managed Flink lane](./managed-flink-iceberg.md), compiled to Spark SQL. Everything else is unchanged.

## What is supported

| Surface | Preview behaviour |
|---|---|
| Runtimes | EMR Serverless, AWS Glue (Glue 5.0, Spark 3.5), EMR on EC2 and EMR on EKS. One runner file runs unchanged on all four. |
| Modes | `streaming`: a Kafka topic, appended to the table. `batch`: SQL over catalog tables, which overwrites the partitions it writes. |
| Records | `properties.stream`: one topic, the value as `json` or `avro-confluent`, as on the Flink lane. |
| Mapping | `properties.mapping`, as on the Flink lane, plus `maskAtIngest: hash` on a column. |
| Output | One Iceberg expose in the Glue catalog, at the warehouse path forge derives from the binding. |

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
| `runtime` | Required: `emr-serverless`, `emr-ec2`, `emr-eks` or `glue`. |
| `mode` | `streaming` or `batch`. It defaults to `streaming` when the build declares `properties.stream`, and to `batch` otherwise. |
| `applicationId` | EMR Serverless only: an existing application. |
| `clusterId` | EMR on EC2 only: an existing cluster. A transient cluster is refused for now. A cluster that runs on Spot needs the layout in [Running EMR on EC2 on Spot](#running-emr-on-ec2-on-spot). |
| `virtualClusterId` | EMR on EKS only, and required there: an existing virtual cluster. |
| `glueVersion` | Glue only. Default `5.0`. |
| `releaseLabel` | The EMR release, on the EMR runtimes. Default `emr-7.12.0`. *On forge-cli `main`, not yet in a release ([forge-cli #984](https://github.com/Agenticstiger/forge-cli/pull/984)).* Each runtime takes its own form, and the default on EMR on EKS is `emr-7.12.0-latest`: see [Release labels](#release-labels). |
| `executionRoleArn` | An existing role the job runs as. See [Roles](#roles-and-who-lists-what). |
| `maskKeySecretArn` | The Secrets Manager ARN of the key `maskAtIngest: hash` uses. A mapping that masks a column needs it. |
| `sparkConf` | Spark settings, limited to sizing and tuning unless the operator lists more. See [Spark settings](#spark-settings). |
| `source` | The Kafka connection. Exactly one of `bootstrapServers` or `mskClusterArn`; `auth` is `msk-iam` (the default with an ARN) or `none` (the default with brokers); `groupIdPrefix`. |

An MSK source needs no broker list: forge looks the brokers up from the cluster ARN when it applies, and fills them into `job.json` (the SASL/IAM list for `msk-iam`, the TLS list for `auth: none`). A plaintext listener is named in `bootstrapServers`.

### Release labels

*On forge-cli `main`, not yet in a release ([forge-cli #984](https://github.com/Agenticstiger/forge-cli/pull/984)).* Each EMR runtime takes its own form of `releaseLabel`:

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
| `registry` | The schema registry of an `avro-confluent` stream. On a forge Spark build only `kind: confluent` is accepted: `kind: glue` is refused. Its `auth` takes `env://` or `aws-sm://` references only. See [Schema registry](./schema-registry.md). |

### Batch builds

A `batch` build runs `properties.sql` over catalog tables and never reads a topic. A batch read of a topic sees only what Kafka still retains, so overwriting the table with it would drop every older row. To land a topic on a schedule, use a `streaming` build with `trigger: {availableNow: true}`: it keeps its position in its checkpoint, and the scheduled run is the micro-batch.

A build declares `properties.mapping` or `properties.sql`, not both, and exactly one Iceberg output.

## What the mapping does on Spark

The mapping is the one the Flink lane takes, so the same `properties.mapping` compiles to Spark 3.5 SQL. What differs, for the contract author:

- **Arrays** that become rows flatten with `LATERAL VIEW inline` for struct elements and `LATERAL VIEW explode` for scalars. Flink uses `CROSS JOIN UNNEST` for both.
- **Built structs** use `named_struct`, with the same null rule as Flink: a built struct is null when its parent is.
- **Types** use Spark's names: `timestamp_ltz` is `TIMESTAMP` and `timestamp` is `TIMESTAMP_NTZ`.
- **Structs are read by field name.** Spark casts structs by position, so an Avro writer schema with a different field order would otherwise swap values.
- **A required field that arrives null fails the job.** Flink fails a `NOT NULL` column the same way. On Spark the job stops with `fluid: required field <name> is null in a Kafka record`.
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
| A caller policy | For a build that runs to completion (batch, or a stream with `availableNow`): the managed policy `fluid-<product>-spark-caller`, for the platform to attach to the scheduler's role. |

Per runtime:

| Runtime | What forge creates | Trust of the job's role |
|---|---|---|
| `emr-serverless` | With `applicationId`, nothing: the application is the domain's and the contract only names it. Without it, `packaging.containers.emrApplication: isolated` creates one for the product, which stops after 15 idle minutes, is capped at 16 vCPU and 64 GB, and sits in the MSK cluster's subnets and security groups. With neither, the contract is refused (`spark-emr-application-shared`). | The EMR Serverless service, for this account and this application. |
| `glue` | An `aws_glue_job` (`gluestreaming` or `glueetl`), Glue 5.0 by default, with `--datalake-formats iceberg`, the runner as its script, `--config` pointing at `job.json`, continuous logs to its group, and a `NETWORK` connection in one of the MSK cluster's subnets. | `glue.amazonaws.com`, for this build's own Glue job. |
| `emr-eks` | Nothing: the virtual cluster is existing. | The IRSA statement that `aws emr-containers update-role-trust-policy` writes. The virtual cluster and its EKS cluster are read at plan time. |
| `emr-ec2` | No role: a step runs as the cluster's instance profile, so forge emits the job's policy as a managed `aws_iam_policy` for the cluster's owner to attach. | None. |

### What the job's role may do in S3

*On forge-cli `main`, not yet in a release ([forge-cli #983](https://github.com/Agenticstiger/forge-cli/pull/983)).* The role forge creates for a Spark build, and the policy it emits for an EMR on EC2 cluster's owner to attach, get S3 access to these prefixes of the output's bucket:

| Prefix | Access |
|---|---|
| The output's `binding.location.path` | Read, write and delete |
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

## Operator settings

| Variable | What it lists or sets |
|---|---|
| `FLUID_SPARK_TARGET_ALLOWLIST` | The existing runtimes a contract may name, as `<runtime>:<id>` (`emr-serverless:<applicationId>`, `emr-ec2:<clusterId>`, `emr-eks:<virtualClusterId>`), and the MSK clusters it may read, as `msk:<cluster ARN>`, matched exactly. The job's role trusts the runtime and the caller policy may start, cancel and add steps there, so naming another team's cluster would reach it. An isolated application of the product needs no entry. |
| `FLUID_SPARK_EXECUTION_ROLE_ALLOWLIST` | The roles a contract's `executionRoleArn` may name: an exact role ARN, or an ARN prefix ending in `/` (a role path). |
| `FLUID_SPARK_CONF_ALLOWLIST` | `sparkConf` keys beyond the tuning ones: a key, or a prefix ending in `*`. See [Spark settings](#spark-settings). |
| `FLUID_SPARK_CONTRACT_SQL_ALLOWLIST` | The builds whose own `properties.sql` the job may run. An entry is `<product>`, `<product>/<build>` or `<product>/<build>@sha256:<digest of the reviewed SQL>`, the last being the one to use. A contract's own SQL runs inside the job with its role, so it can read any table that role can read. A build with a `properties.mapping` needs no entry, because forge compiles a query that reads only the stream. |
| `FLUID_SPARK_WAIT_SECONDS` | How long a reconcile waits for a cancelled run to stop, and for a started one to leave its pending states. Default 900. |
| `FLUID_SPARK_MAVEN_REPOSITORY` | One https Maven mirror. See [Network](#network-and-packages). |
| `FLUID_SPARK_GLUE_JARS_URL` | `s3://<bucket>/<prefix>/`: where the platform keeps the pinned jars a Glue Avro build loads. See [Avro on Glue](#avro-on-glue). |

A stream that reads a registry with a credential also needs the settings of the [Schema registry](./schema-registry.md#operator-settings) page.

### Spark settings

A contract's `sparkConf` may set sizing and tuning settings only: executor and driver memory, cores and instances, `spark.sql.shuffle.partitions`, `spark.default.parallelism`, adaptive execution (`spark.sql.adaptive.*`), dynamic allocation (`spark.dynamicAllocation.*`) and a few others. Any other key needs the operator to list it in `FLUID_SPARK_CONF_ALLOWLIST`.

Some keys are refused even when listed, by name or by a prefix such as `spark.sql.*`, because they load code or environment into a job that runs with its role, or move what it writes. The list is the same for `fluid apply` and the infrastructure emit. It holds:

- keys that load code: `spark.jars*`, `spark.files*`, `spark.archives`, `spark.submit.*`, `spark.pyspark.*`, `spark.python.*`, `spark.plugins*`, `spark.extraListeners`, `spark.sql.extensions`, the `extraClassPath`, `extraJavaOptions` and `extraLibraryPath` keys of the driver and executor, `defaultJavaOptions`, `userClassPathFirst`, and the classes that `spark.sql.adaptive.customCostEvaluatorClass` and `spark.sql.streaming.stateStore.providerClass` name;
- keys that set identity, credentials or environment: `spark.hadoop.*`, `spark.executorEnv.*`, `spark.emr-serverless.driverEnv.*` and `executorEnv.*`, `spark.yarn.*`, `spark.kubernetes.*`, `spark.kerberos.*`, `spark.security.*`, `spark.authenticate*`, `spark.ssl.*`, `spark.redaction.*`, `spark.emr-serverless.lakeformation.*`;
- keys that move what the job writes or switch off what the runner relies on: `spark.sql.catalog.*`, `spark.sql.catalogImplementation`, `spark.sql.defaultCatalog`, `spark.sql.warehouse.dir`, `spark.sql.streaming.checkpointLocation`, `spark.sql.queryExecutionListeners`, `spark.sql.streaming.streamingQueryListeners`, `spark.sql.variable.substitute`, `spark.sql.session.timeZone`, `spark.sql.mapKeyDedupPolicy`, `spark.eventLog.*`, `spark.ui.*`, `spark.master`, `spark.app.*`.

A key with a bad name or value gets its own message, and only a valid key that is not listed is told to be exported by the operator.

## Starting and reconciling runs

There is no OpenTofu resource for a job run, so runs are started by forge and not by the module.

`fluid plan` lists one `spark.reconcile` action per Spark build. `planDigest` covers it, and it needs no AWS credentials. The action's payload carries the runtime, mode, target, execution role, the artifact locations and a **config hash**: the sha256 of the job config, the runner's sha256 and the run settings (runtime, target, release, role, `sparkConf`, retries, and on Glue the pinned jars it loads). `fluid apply` compiles the runs again and refuses a bound plan whose Spark actions differ (`apply_spark_artifact_mismatch`). A non-dry-run apply of a streaming build also needs the `[aws]` extra (`apply_aws_sdk_missing`). Apply needs the OpenTofu engine (`apply_spark_needs_opentofu`).

After `tofu apply`, `fluid apply` reconciles each streaming build:

| Found | What apply does |
|---|---|
| A running job with this hash | Nothing. |
| A running job with another hash | Cancels it, waits for it to stop, and starts the new config on the **same checkpoint**, so it resumes where the old one stopped. |
| A new topic or cluster, with a checkpoint an earlier run read | Refuses, before cancelling anything. A checkpoint holds the offsets of one topic on one cluster. To read the new stream, move `properties.stream.checkpoint` to a new prefix: the job then starts from `startingOffsets`. |
| No running job | Starts one, unless the last run with this hash failed. |
| A last run that failed | An error that names the run and its reason. On EMR Serverless a streaming job retries until it fails more than `maxFailedAttemptsPerHour` times in an hour, and then stops, so starting it again would fail the same way. Fix the cause, then change the build: `fluid apply` starts it with the new config. |
| A second active copy of the current config | Cancels it. |
| A stream moved to `trigger.availableNow` | Cancels its old continuous job. Its scheduler starts it from now on. |

A scheduled build (batch, or a stream with `availableNow`) is reported as `scheduled` and is never reconciled: its scheduler starts it through `fluid apply --mode amend-and-build` (see [Scheduled Spark builds](./airflow.md#scheduled-spark-builds)). A Glue stream also restarts when a pinned jar or `FLUID_SPARK_GLUE_JARS_URL` changes, because the hash covers the jars it loads; a running Glue Avro stream restarts once on the release that added this. Plan and apply need the same `FLUID_SPARK_GLUE_JARS_URL`, because the plan binds the hash, and apply refuses a plan made with another.

Per runtime, the start is:

- **EMR Serverless:** `StartJobRun` with `mode=STREAMING` and a retry policy of `execution.retries.maxAttempts` attempts per hour (default 5, at most 10), or `BATCH`.
- **Glue:** `StartJobRun` on the build's job.
- **EMR on EC2:** `AddJobFlowSteps` on `clusterId`, with `spark-submit --deploy-mode client`, so cancelling the step stops the driver.
- **EMR on EKS:** `StartJobRun` on `virtualClusterId`.

### The caller's permissions

The role that runs `fluid apply`, or the scheduler's execution role (the MWAA role, say) that runs `fluid apply --mode amend-and-build` for a scheduled build, needs these actions. A scheduler's worker runs the whole apply, `tofu` included, so it also needs the apply's own permissions and the state backend, as for any scheduled build: the caller policy below covers the run only. For a build that runs to completion, the managed policy `fluid-<product>-spark-caller` holds them, scoped to the product's own application, job, cluster or virtual cluster:

| Runtime | Actions | Also |
|---|---|---|
| `emr-serverless` | `emr-serverless:StartJobRun`, `GetJobRun`, `ListJobRuns`, `CancelJobRun`, `TagResource`, and `ListApplications` when the contract names no `applicationId` | `iam:PassRole` on the job's role, with `iam:PassedToService` set to `emr-serverless.amazonaws.com` |
| `glue` | `glue:StartJobRun`, `GetJobRun`, `GetJobRuns`, `BatchStopJobRun` | |
| `emr-ec2` | `elasticmapreduce:AddJobFlowSteps`, `ListSteps`, `DescribeStep`, `CancelSteps` | |
| `emr-eks` | `emr-containers:StartJobRun`, `DescribeJobRun`, `ListJobRuns`, `CancelJobRun`, `TagResource` | `iam:PassRole` on the job's role, with `iam:PassedToService` set to `emr-containers.amazonaws.com` |

Scope `iam:PassRole` to the forge roles, so that a contract cannot pass a stronger one.

## Running EMR on EC2 on Spot

A stream on EMR on EC2 runs as one step of a cluster you already run (`clusterId`). forge creates no cluster, so the layout below is a checklist for the cluster's owner. Only the `sparkConf` values in items 4 and 6 go in the contract. Its aim is that a Spot interruption costs time and not records.

What forge does with the cluster decides what the layout must protect:

- **The driver is the step's own process.** forge starts the stream with `spark-submit --deploy-mode client`, so that cancelling the step stops the job. AWS's Spark step guide says client mode launches the driver on the cluster's primary instance.
- **The checkpoint is in S3, not on the cluster.** It defaults to `s3://<bucket>/_checkpoints/<product>/<build>/`, so losing nodes loses no offsets.
- **A step that ends `FAILED` or `INTERRUPTED` counts as failed, and `fluid apply` does not start it again with the same config.** It names the run and its state and starts nothing, because the same config would fail the same way (see [Starting and reconciling runs](#starting-and-reconciling-runs)). To bring the stream back, change the build. After a lost cluster, launch a replacement with forge's policy attached to its instance-profile role, and set `clusterId` to it, with its `emr-ec2:<clusterId>` entry in `FLUID_SPARK_TARGET_ALLOWLIST`: the target is part of the config hash, so `fluid apply` starts the stream on the same checkpoint.

The checklist:

1. **On-Demand primary and core nodes.** The driver runs on the primary node, and the cluster ends when the primary is lost. AWS advises Spot for the primary only where sudden termination is acceptable, and for core nodes only where losing part of the HDFS data is tolerable. Task nodes hold no HDFS data, so Spot belongs there.
2. **Spot task fleets, with `price-capacity-optimized` allocation and diverse instance types.** Use instance fleets, and set the task fleet's Spot `AllocationStrategy` to `price-capacity-optimized`: AWS recommends it, and it is the default from EMR 6.10.0. List several instance types: when EC2 reclaims a Spot instance, EMR tries to replace it with any type on the list. Offer subnets in several Availability Zones too. EMR picks the zone it judges best for the fleet when it creates the cluster, and the cluster's instances then run in that one zone.
3. **YARN application masters pinned to On-Demand (EMR 7.2.0 and later).** In the cluster's `yarn-site` classification, set `yarn.node-labels.enabled` to `true` and `yarn.node-labels.am.default-node-label-expression` to `ON_DEMAND`. AWS warns that an application master on a Spot node can mean "immediate shutdown of the entire YARN application". Set it when you create the cluster: EMR does not add node labels when you reconfigure a running one. AWS describes this setting for clusters that use managed scaling, and its blog post shows instance groups. The example below uses instance fleets and no managed scaling, so check on the running cluster that YARN lists an `ON_DEMAND` node label. Settings that start with `spark.yarn.` are refused in `sparkConf` even when the operator lists them, so this belongs to the cluster and not to the contract.
4. **A minimum On-Demand executor baseline for streams.** Size the On-Demand capacity (the core nodes, and any On-Demand part of a task fleet) for the executors the stream needs to keep committing batches when every Spot node is gone, and tell Spark that number in `sparkConf`: `spark.dynamicAllocation.minExecutors` with dynamic allocation, or `spark.executor.instances` without it. Both are allowed without an operator entry, and both fix a count, not where the executors run. When Spot nodes are reclaimed, YARN can place a replacement executor only on the nodes that remain. Where YARN puts executors while Spot nodes exist depends on the cluster's node labels, so look at where they ran in the interruption test (item 6).
5. **Kafka retention at least as long as the longest downtime you tolerate.** A restarted stream resumes from the offsets in its checkpoint, so the topic must still hold them. Count the whole outage: detecting the loss, replacing the cluster, starting the step, and catching up. Set the topic's `retention.ms` (Kafka's default is 7 days) to at least that, and leave `retention.bytes` unset (`-1`) or size it for the same window, because a topic discards a segment at whichever limit it reaches first. forge's runner leaves Spark's Kafka option `failOnDataLoss` at its default, `true`, so a stream whose checkpointed offsets have aged out fails and does not skip records.
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
- **The apply role needs `iam:PassRole`** on the registration role, because `lakeformation:RegisterResource` passes it.
- **Moving a registered location from the service-linked role to the new role re-registers it.** While that runs, Lake Formation vends no credentials for the location, so jobs that are running on it may fail for that short window.

In the account's `<account>-fluid-data` fallback bucket, and in a `shared` packaging pool's bucket, a forge role writes only the product's own `<product>/` prefix.

## Errors

| Event or kind | Meaning |
|---|---|
| `spark-emr-application-shared` | An EMR Serverless build with no `applicationId` and no `emrApplication: isolated` |
| `spark-checkpoint-scope` | A declared checkpoint outside `s3://<bucket>/_checkpoints/<product>/`, while forge creates the role |
| `spark-glue-jars-unset`, `spark-glue-jars-url` | A Glue Avro build, and `FLUID_SPARK_GLUE_JARS_URL` is unset or malformed |
| `apply_spark_artifact_mismatch` | The bound plan lists other Spark runs than apply compiles |
| `apply_aws_sdk_missing` | boto3 is not installed: `pip install 'data-product-forge[aws]'` |
| `apply_spark_needs_opentofu` | The contract's apply engine is not OpenTofu |
| `apply_spark_invalid` | A Spark build the runner would refuse (a contract before the 0.7.7 managed lane, or an `execution.runtime.timeout` that is not an ISO-8601 duration of at least one second), refused before `tofu apply` changes anything |

## See also

- [Scheduled Spark builds](./airflow.md#scheduled-spark-builds): the `fluid apply` DAG that runs a scheduled build.
- [Schema registry](./schema-registry.md): `stream.registry`, produced subjects and the registry operator settings.
- [Managed Flink to Iceberg](./managed-flink-iceberg.md): the `properties.stream` and `properties.mapping` this lane shares.
- [Scheduling Spark builds on Airflow](./airflow.md#scheduled-spark-builds).
- [Environment variables](./environment-variables.md#spark-on-aws-preview): every variable this lane reads.
