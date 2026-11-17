---
title: Spark to Iceberg on AWS (preview)
description: Declare a Kafka stream, or batch SQL over catalog tables, in the contract; forge-cli compiles the Spark job, provisions its infrastructure with OpenTofu on EMR Serverless, Glue, EMR on EC2 or EMR on EKS, and starts and reconciles its runs.
---

# Spark to Iceberg on AWS (preview)

*On forge-cli `main`, not yet in a release ([forge-cli #902](https://github.com/Agenticstiger/forge-cli/pull/902), [forge-cli #903](https://github.com/Agenticstiger/forge-cli/pull/903), [forge-cli #904](https://github.com/Agenticstiger/forge-cli/pull/904), [forge-cli #912](https://github.com/Agenticstiger/forge-cli/pull/912), [forge-cli #918](https://github.com/Agenticstiger/forge-cli/pull/918), [forge-cli #919](https://github.com/Agenticstiger/forge-cli/pull/919), [forge-cli #924](https://github.com/Agenticstiger/forge-cli/pull/924), [forge-cli #927](https://github.com/Agenticstiger/forge-cli/pull/927), [forge-cli #934](https://github.com/Agenticstiger/forge-cli/pull/934)).*

A build with `engine: spark` and `parameters.spark` lands records in an Iceberg table that the Glue catalog holds:

- The contract says which Kafka topic the job reads, or which SQL it runs over catalog tables, and how the result becomes the rows of the output expose.
- forge-cli compiles that into a `job.json` and checks every output column against it before anything deploys.
- OpenTofu provisions what the job needs: its artifacts, role, logs and, where the contract asks for it, the EMR Serverless application or the Glue job.
- `fluid apply` starts the job and keeps a streaming one running. A scheduler starts a scheduled one with [`fluid spark run`](../cli/spark.md).

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

This contract reads a topic from MSK and hashes one column. Checked on forge-cli `main`: with the operator settings below, `fluid validate` passes with no warning and `fluid generate iac` writes the module.

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
| `clusterId` | EMR on EC2 only: an existing cluster. A transient cluster is refused for now. |
| `virtualClusterId` | EMR on EKS only, and required there: an existing virtual cluster. |
| `glueVersion` | Glue only. Default `5.0`. |
| `releaseLabel` | The EMR release, on the EMR runtimes. Default `emr-7.12.0`. |
| `executionRoleArn` | An existing role the job runs as. See [Roles](#roles-and-who-lists-what). |
| `maskKeySecretArn` | The Secrets Manager ARN of the key `maskAtIngest: hash` uses. A mapping that masks a column needs it. |
| `sparkConf` | Spark settings, limited to sizing and tuning unless the operator lists more. See [Spark settings](#spark-settings). |
| `source` | The Kafka connection. Exactly one of `bootstrapServers` or `mskClusterArn`; `auth` is `msk-iam` (the default with an ARN) or `none` (the default with brokers); `groupIdPrefix`. |

An MSK source needs no broker list: forge looks the brokers up from the cluster ARN when it applies, and fills them into `job.json` (the SASL/IAM list for `msk-iam`, the TLS list for `auth: none`). A plaintext listener is named in `bootstrapServers`.

### Stream settings

*0.7.7 preview.* A `properties.stream` has these fields besides the topic, format and schema of the Flink lane:

| Field | Meaning |
|---|---|
| `trigger` | `{processingTime: <ISO duration>}` for a micro-batch every interval, or `{availableNow: true}` for a run that processes what is there and ends. Unset, forge uses half the expose's `qos.freshnessSLO`, and sets no trigger when the expose has none. |
| `watermark` | `{column, delay}`. The column must be a top-level `timestamp_ltz`: Spark 3.5 does not keep a watermark on `timestamp` (an NTZ type). |
| `checkpoint` | An `s3://` prefix. It defaults to `s3://<bucket>/_checkpoints/<product>/<build>/`, at the bucket root and never under the table, where Iceberg's orphan-file cleanup would delete it. When forge creates the job's role, a declared checkpoint must sit under `s3://<bucket>/_checkpoints/<product>/`; one outside it is refused (`spark-checkpoint-scope`). |
| `startingOffsets` | `earliest` or `latest`, for a stream with no checkpoint yet. |
| `registry` | The schema registry of an `avro-confluent` stream. See [Schema registry](./schema-registry.md). |

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

`fluid generate iac` and `fluid apply` add these to the module for each Spark build (checked on forge-cli `main`):

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

Some keys are refused even when listed, by name or by a prefix such as `spark.sql.*`, because they load code or environment into a job that runs with its role, or move what it writes. The list is the same for `fluid spark run`, `fluid apply` and the infrastructure emit. It holds:

- keys that load code: `spark.jars*`, `spark.files*`, `spark.archives`, `spark.submit.*`, `spark.pyspark.*`, `spark.python.*`, `spark.plugins*`, `spark.extraListeners`, `spark.sql.extensions`, the `extraClassPath`, `extraJavaOptions` and `extraLibraryPath` keys of the driver and executor, `defaultJavaOptions`, `userClassPathFirst`, and the classes that `spark.sql.adaptive.customCostEvaluatorClass` and `spark.sql.streaming.stateStore.providerClass` name;
- keys that set identity, credentials or environment: `spark.hadoop.*`, `spark.executorEnv.*`, `spark.emr-serverless.driverEnv.*` and `executorEnv.*`, `spark.yarn.*`, `spark.kubernetes.*`, `spark.kerberos.*`, `spark.security.*`, `spark.authenticate*`, `spark.ssl.*`, `spark.redaction.*`, `spark.emr-serverless.lakeformation.*`;
- keys that move what the job writes or switch off what the runner relies on: `spark.sql.catalog.*`, `spark.sql.catalogImplementation`, `spark.sql.defaultCatalog`, `spark.sql.warehouse.dir`, `spark.sql.streaming.checkpointLocation`, `spark.sql.queryExecutionListeners`, `spark.sql.streaming.streamingQueryListeners`, `spark.sql.variable.substitute`, `spark.sql.session.timeZone`, `spark.sql.mapKeyDedupPolicy`, `spark.eventLog.*`, `spark.ui.*`, `spark.master`, `spark.app.*`.

A key with a bad name or value gets its own message, and only a valid key that is not listed is told to be exported by the operator.

## Starting and reconciling runs

There is no OpenTofu resource for a job run, so runs are started by forge and not by the module.

`fluid plan` lists one `spark.reconcile` action per Spark build. `planDigest` covers it, and it needs no AWS credentials. The action's payload carries the runtime, mode, target, execution role, the artifact locations and a **config hash**: the sha256 of the job config, the runner's sha256 and the run settings (runtime, target, release, role, `sparkConf`, retries, and on Glue the pinned jars it loads). `fluid apply` compiles the runs again and refuses a bound plan whose Spark actions differ (`apply_spark_artifact_mismatch`). It also needs the `[aws]` extra (`apply_aws_sdk_missing`) and the OpenTofu engine (`apply_spark_needs_opentofu`).

After `tofu apply`, `fluid apply` reconciles each streaming build:

| Found | What apply does |
|---|---|
| A running job with this hash | Nothing. |
| A running job with another hash | Cancels it, waits for it to stop, and starts the new config on the **same checkpoint**, so it resumes where the old one stopped. |
| A new topic or cluster, with a checkpoint an earlier run read | Refuses, before cancelling anything. A checkpoint holds the offsets of one topic on one cluster. To read the new stream, move `properties.stream.checkpoint` to a new prefix: the job then starts from `startingOffsets`. |
| No running job | Starts one, unless the last run with this hash failed. |
| A last run that failed | An error that names the run and its reason. On EMR Serverless a streaming job retries until it fails more than `maxFailedAttemptsPerHour` times in an hour, and then stops, so starting it again would fail the same way. Fix the cause, then run `fluid spark run <contract> --build-id <id> --restart`, or change the build. |
| A second active copy of the current config | Cancels it. |
| A stream moved to `trigger.availableNow` | Cancels its old continuous job. Its scheduler starts it from now on. |

A scheduled build (batch, or a stream with `availableNow`) is reported as `scheduled` and is never reconciled: its scheduler starts it with [`fluid spark run`](../cli/spark.md). A Glue stream also restarts when a pinned jar or `FLUID_SPARK_GLUE_JARS_URL` changes, because the hash covers the jars it loads; a running Glue Avro stream restarts once on the release that added this. Plan and apply need the same `FLUID_SPARK_GLUE_JARS_URL`, because the plan binds the hash, and apply refuses a plan made with another.

Per runtime, the start is:

- **EMR Serverless:** `StartJobRun` with `mode=STREAMING` and a retry policy of `execution.retries.maxAttempts` attempts per hour (default 5, at most 10), or `BATCH`.
- **Glue:** `StartJobRun` on the build's job.
- **EMR on EC2:** `AddJobFlowSteps` on `clusterId`, with `spark-submit --deploy-mode client`, so cancelling the step stops the driver.
- **EMR on EKS:** `StartJobRun` on `virtualClusterId`.

### The caller's permissions

The role that runs `fluid apply` or `fluid spark run`, or the scheduler's execution role (the MWAA role, say), needs these actions. For a build that runs to completion, the managed policy `fluid-<product>-spark-caller` holds them, scoped to the product's own application, job, cluster or virtual cluster:

| Runtime | Actions | Also |
|---|---|---|
| `emr-serverless` | `emr-serverless:StartJobRun`, `GetJobRun`, `ListJobRuns`, `CancelJobRun`, `TagResource`, and `ListApplications` when the contract names no `applicationId` | `iam:PassRole` on the job's role, with `iam:PassedToService` set to `emr-serverless.amazonaws.com` |
| `glue` | `glue:StartJobRun`, `GetJobRun`, `GetJobRuns`, `BatchStopJobRun` | |
| `emr-ec2` | `elasticmapreduce:AddJobFlowSteps`, `ListSteps`, `DescribeStep`, `CancelSteps` | |
| `emr-eks` | `emr-containers:StartJobRun`, `DescribeJobRun`, `ListJobRuns`, `CancelJobRun`, `TagResource` | `iam:PassRole` on the job's role |

Scope `iam:PassRole` to the forge roles, so that a contract cannot pass a stronger one.

## Network and packages

A streaming run resolves its pinned packages when it starts:

| Package | Used for |
|---|---|
| `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1` | Reading Kafka |
| `software.amazon.msk:aws-msk-iam-auth:2.2.0` | MSK IAM authentication |
| `org.apache.spark:spark-avro_2.12:3.5.1` and `za.co.absa:abris_2.12:6.4.0` | Confluent Avro |

Iceberg is on the EMR runtimes already, at `/usr/share/aws/iceberg/lib/iceberg-spark3-runtime.jar`, and Glue gets it from `--datalake-formats iceberg`. **The cluster needs outbound HTTPS** to Maven Central, and to Confluent's repository for Avro: the subnets of the EMR Serverless application and the subnet of the Glue `NETWORK` connection. forge creates no NAT gateway.

*On forge-cli `main`, not yet in a release ([forge-cli #919](https://github.com/Agenticstiger/forge-cli/pull/919)).* An operator without that egress sets `FLUID_SPARK_MAVEN_REPOSITORY` to one https mirror (CodeArtifact or Artifactory, with Maven Central and Confluent's repository behind it). It replaces Confluent's repository in `spark.jars.repositories`. Spark 3.5 still tries Maven Central and spark-packages first, so without egress those attempts fail, which can be slow, and the resolver then falls through to the mirror. The variable is read from the real environment only. A URL with a user or a password, a query, a comma, a link-local or metadata host, or plain http is refused, and the message names the rule and never the URL. A mirror that needs a credential is not supported: use one that the job's role reaches with IAM. A contract's `sparkConf` cannot replace it. Glue resolves no packages, so the mirror does not apply there.

### Avro on Glue

*On forge-cli `main`, not yet in a release ([forge-cli #927](https://github.com/Agenticstiger/forge-cli/pull/927)).* Glue 5.0 ships Spark, the Kafka connector, `kafka-clients`, the MSK IAM library, `spark-avro` and Iceberg, but not ABRiS, and the Confluent registry client it holds is inside a Hudi bundle. So a Glue build that decodes Confluent Avro loads seven jars that forge pins by sha256: ABRiS 6.4.0 for Scala 2.12, `za.co.absa.commons` 1.0.0, and the Confluent 6.2.1 clients ABRiS is built against (`kafka-avro-serializer`, `kafka-schema-serializer`, `kafka-schema-registry-client`, `common-config`, `common-utils`). The Confluent clients are from 2021: the pins protect integrity, not against known CVEs, so re-pin when ABRiS moves. A JSON build, an MSK IAM build and an EMR build add no jars.

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

*On forge-cli `main`, not yet in a release ([forge-cli #918](https://github.com/Agenticstiger/forge-cli/pull/918)).* A contract that sets `registerLocation: true` on the output's binding and has a forge Spark job write the table gets a different registration. Lake Formation's service-linked role has no `s3:PutObject`, and EMR 7.12 writes Iceberg with the credentials Lake Formation vends. So forge registers the location with a role of the product's instead:

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
| `spark_run_no_build`, `spark_status_no_build` | `fluid spark run` or `status` found no such Spark build |

## See also

- [`fluid spark`](../cli/spark.md): start a scheduled run, or show a build's runs.
- [Schema registry](./schema-registry.md): `stream.registry`, produced subjects and the registry operator settings.
- [Managed Flink to Iceberg](./managed-flink-iceberg.md): the `properties.stream` and `properties.mapping` this lane shares.
- [Scheduling Spark builds on Airflow](./airflow.md#scheduled-spark-builds).
- [Environment variables](./environment-variables.md#spark-on-aws-preview): every variable this lane reads.
