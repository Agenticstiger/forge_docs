# `fluid spark`

*On forge-cli `main`, not yet in a release ([forge-cli #912](https://github.com/Agenticstiger/forge-cli/pull/912), [forge-cli #919](https://github.com/Agenticstiger/forge-cli/pull/919)).*

Start one run of a Spark build and wait for it to end, or show a build's recent runs. A build is an `engine: spark` build with `parameters.spark` (under `builds[].properties`), described in [Spark to Iceberg on AWS](../advanced/spark-iceberg-aws.md).

`fluid apply` provisions a Spark build and keeps a streaming one running. A scheduled build (a batch build, or a stream with `trigger: {availableNow: true}`) is started by its scheduler instead, and `fluid spark run` is the command the scheduler calls. It runs on EMR Serverless, AWS Glue, EMR on EC2 and EMR on EKS, and needs the `[aws]` extra (`pip install 'data-product-forge[aws]'`): boto3 loads only when a run is read or started.

## Syntax

```bash
fluid spark run CONTRACT --build-id ID [--env ENV] [--json] [--no-wait] [--timeout SECONDS] [--restart]
fluid spark status CONTRACT [--build-id ID] [--env ENV] [--json]
```

## `fluid spark run`

```bash
fluid spark run contract.fluid.yaml --build-id daily_orders
```

It starts one run on the build's runtime, waits for it, and exits 0 only when the run succeeded, so a scheduler task fails when the run does.

| Option | Description |
| --- | --- |
| `CONTRACT` | The contract. The `.env` of the current directory is read as `fluid apply` reads it, for `AWS_REGION` and the settings a project file may carry. |
| `--build-id ID` | Required. The build to run. |
| `--env ENV` | The environment overlay to apply. |
| `--json` | Print one JSON line instead of text, a refusal included. |
| `--no-wait` | Return once the run is started. |
| `--timeout SECONDS` | How long to wait for the run to end before cancelling it. Default 21600 (six hours). |
| `--restart` | A streaming build: start it again although its last run failed. |

What it does:

- **Waits, and cancels on a signal.** Ctrl-C, SIGTERM or SIGHUP cancel the run, so a task a scheduler kills does not leave a job running.
- **Adopts a run that is going.** When a scheduler retries a task whose run is still going, the command waits for that run instead of starting a second one.
- **Reconciles a streaming build** as `fluid apply` does, so `--restart` can start one whose last run failed. See [Starting and reconciling runs](../advanced/spark-iceberg-aws.md#starting-and-reconciling-runs).
- **Waits at most `--timeout`.** A run still going then is cancelled, and the exit code is 1.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The run succeeded. |
| `1` | The run failed or was cancelled, or could not be started or read. |
| `2` | The contract or the operator's policy refuses the build. Nothing was started. |

### The JSON line

With `--json` the command prints exactly one line, with sorted keys. A run:

| Key | Holds |
| --- | --- |
| `build`, `runtime` | The build id and its runtime |
| `action` | `started`, `adopted`, `succeeded`, `failed`, `cancelled` or `unchanged`, among others |
| `where` | The application, job, cluster or virtual cluster |
| `runId`, `state` | The run and its state |
| `message` | Why, when there is something to say. AWS text goes through the secret redactor |
| `error` | `true` when the exit code is 1 |
| `cancelled` | The ids of runs this command cancelled |

When the run could not be cancelled, the message says so: `could not be cancelled and may still be going: cancel it by hand`.

A refusal is one line too, with `"action": "refused"`, `"error": true`, the `event` and a `message`, and exits 2. For a build that is not in the contract:

```json
{"action": "refused", "build": "nope", "error": true, "event": "spark_run_no_build", "message": "no Spark build 'nope'", "runId": null, "runtime": null, "state": null}
```

Neither the JSON nor an error carries a credential: the job config holds the ARN of the mask key, never the key.

## `fluid spark status`

```bash
fluid spark status contract.fluid.yaml
fluid spark status contract.fluid.yaml --build-id ingest-orders --json
```

Shows each Spark build's recent runs, newest first, and whether each used the build's current config (`current config`) or an older one (`older config`). Exit code 0 when every build could be read, and 1 when one could not. `--json` prints one line holding a list, each entry with `build`, `runtime`, `configHash`, `where` and `runs`.

## Scheduling it

An Airflow task runs the command through a `BashOperator`. `fluid generate schedule` writes that DAG for a scheduled Spark build: see [Scheduled Spark builds](../advanced/airflow.md#scheduled-spark-builds).

## Operator settings

`FLUID_SPARK_CONF_ALLOWLIST`, `FLUID_SPARK_WAIT_SECONDS`, `FLUID_SPARK_MAVEN_REPOSITORY` and the others are described in [Spark to Iceberg on AWS](../advanced/spark-iceberg-aws.md#operator-settings). The caller needs the AWS permissions listed under [The caller's permissions](../advanced/spark-iceberg-aws.md#the-caller-s-permissions).

## See also

- [Spark to Iceberg on AWS](../advanced/spark-iceberg-aws.md)
- [`fluid plan`](./plan.md): lists a `spark.reconcile` action for each Spark build.
- [`fluid apply`](./apply.md)
