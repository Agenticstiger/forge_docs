# `fluid generate artifacts`

Stage 3 of the 11-stage pipeline. One call writes the catalog and execution artifacts for a contract, plus a `MANIFEST.json` (SHA-256 per file and a merkle root) that stage 4 verifies.

Added in `0.8.0` as a top-level subcommand of [`fluid generate`](./generate.md).

## Example

From a bundle, the way a pipeline runs it:

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
fluid generate artifacts runtime/bundle.tgz --out dist/artifacts/
fluid validate-artifacts dist/artifacts/ --strict
```

From a contract file, as a local shortcut:

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
```

The command prints where it wrote and the manifest digest:

```text
✅ Artifacts written to dist/artifacts
   MANIFEST digest:
sha256:...
   files: 7
```

The tree for a contract with two exposes, no `orchestration.engine` and no scheduled build:

```text
dist/artifacts/
├── MANIFEST.json                                     # SHA-256 per file + merkle root
├── odcs/product.odcs.<exposeId>.yaml                 # ODCS v3.1.0, one per exposed port
├── odps-bitol/<product-id>.odps.yaml                 # ODPS-Bitol v1.0.0
├── odps-bitol/<product-id>.<exposeId>.odcs.yaml      # one per exposed port, next to the product file
├── opds/<product-id>.opds.json                       # OPDS v4.1 (LF/ODPI)
└── policy/bindings.json                              # compiled IAM / GRANT bindings
```

A contract that gets a schedule artifact adds `schedule/<product-id>[__<env>]/<build-id>_dag.py`, described in [Scheduled builds](#scheduled-builds). *(since 0.33.0, [forge-cli #979](https://github.com/Agenticstiger/forge-cli/pull/979))* A contract with a forge Spark build adds `spark/<build-id>/job.json`, described in [Spark job configs](#spark-job-configs).

## Syntax

```bash
fluid generate artifacts CONTRACT [--out PATH] [--emit KEYS] [--manifest PATH] [--env ENV] [--contract-path PATH]
                         [--allow-scaffold-on-change-request]
```

`CONTRACT` is a bundle (`.tgz`) or a contract YAML file. A bundle comes from [`fluid bundle --format tgz`](./bundle.md): `generate artifacts` extracts it and re-verifies its MANIFEST first. A contract file is the local-dev shortcut; the pipeline path is the bundle.

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Bundle (`.tgz`) or contract YAML file (positional, required). |
| `--out PATH` | Output directory. Default `dist/artifacts/`. |
| `--emit KEYS` | Comma-separated emit keys. Default: `odps-bitol,odcs,opds,schedule,policies`. *(since 0.33.0, [forge-cli #979](https://github.com/Agenticstiger/forge-cli/pull/979))* The default also holds `spark`. See the [emit set](#emit-set). `dbt` is not an emit key; dbt projects come from [`fluid generate transformation`](./generate.md#fluid-generate-transformation). |
| `--manifest PATH` | Where to write `MANIFEST.json`. Default `<out>/MANIFEST.json`. Stage 4 re-verifies it. |
| `--env ENV` | The environment the artifacts are for. A bundle must have been built for it (`fluid bundle --env ENV`); a bundle built for another env is refused, because a bundle is not re-overlaid. A contract file gets the overlay applied, as `fluid bundle --env ENV` would. The value is also the `--env` every scheduled DAG passes to `fluid apply`. Default for the DAGs: `$FLUID_ENV`; if that is unset too, the DAGs carry no `--env`. `--env ''` means no `--env`. |
| `--contract-path PATH` | The contract's path relative to the project directory. Scheduled DAGs append it to `$FLUID_PROJECT_DIR` on the Airflow worker. Default: the input's path relative to the current directory for a contract file, and `contract.fluid.yaml` (with a warning) for a bundle, which records no location. |
| `--allow-scaffold-on-change-request` | *(since 0.37.0)* Run `custom-scaffold` on a change-request build too. See [Custom scaffold](#custom-scaffold). Only this flag overrides the refusal, never a variable or a `.env` file. |

## Emit set

| Key | What it emits | Notes |
| --- | --- | --- |
| `odcs` | ODCS v3.1.0 files under `odcs/`, one per exposed port | Schema vendored from `bitol-io/open-data-contract-standard`. |
| `odps-bitol` | ODPS-Bitol v1.0.0 product file under `odps-bitol/`, with an ODCS file per exposed port beside it | Schema vendored from `bitol-io/open-data-product-standard`. |
| `opds` | OPDS v4.1 (LF/ODPI) product file under `opds/` (`<product-id>.opds.json`) | `odps` is accepted as a deprecated alias of `opds` and warns. |
| `schedule` | Airflow DAG files under `schedule/` | Emitted when `orchestration.engine` is set, or when a build declares a schedule trigger. *(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* A `dataset` or `schedule_and_dataset` trigger counts too. See [Scheduled builds](#scheduled-builds). |
| `spark` | `spark/<build-id>/job.json` for each forge Spark build | *(since 0.33.0, [forge-cli #979](https://github.com/Agenticstiger/forge-cli/pull/979))* The runner config `fluid apply` uploads. A contract without a Spark build writes nothing. See [Spark job configs](#spark-job-configs). |
| `policies` | `policy/bindings.json`, the compiled IAM / GRANT bindings | *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), since 0.20.0)* A crash inside the policy compiler fails the stage with `policy_compiler_crashed` (exit 1). See [`fluid policy compile`](./policy-compile.md#errors). |
| `pyspark-schema` | `pyspark-schema/<port>_schema.py`, one PySpark `StructType` module per output port with columns | *(since 0.37.0)* Not in the default set: name it with `--emit`. The same module [`fluid generate pyspark-schema`](./generate-pyspark-schema.md) writes, byte for byte. See [PySpark schema modules](#pyspark-schema-modules). |
| `custom-scaffold` | `custom-scaffold/`, the files the contract's `extensions.customScaffold` block generates | *(since 0.37.0)* Not in the default set, and never on a change-request build. Needs the `custom-scaffold` extra. See [Custom scaffold](#custom-scaffold). |

`builds[].pattern` (for example `hybrid-reference`) decides how the transformation runs and gates no emit key: a reference-only contract gets the same set as any other.

When `schedule` is requested and the contract has nothing to schedule, the run logs one of these events, drops the key and continues:

| Event | Cause |
| --- | --- |
| `generate_artifacts_skip_schedule_no_engine` | No `orchestration.engine`, and no build with a schedule trigger. *(since 0.34.0, [forge-cli #1018](https://github.com/Agenticstiger/forge-cli/pull/1018))* A Spark stream that declares `execution.retries` counts as a build with a schedule, so it does not log this event. |
| `generate_artifacts_skip_schedule_engine_none` | `orchestration.engine: none`. |
| `generate_artifacts_skip_schedule_unreadable` | The contract file cannot be read at all. |

A contract that is readable but does not load (a malformed overlay for the `--env` given, for example) fails the stage with `generate_artifacts_failed` and `emit_key: schedule` instead of skipping.

## Scheduled builds

A build that declares a cron trigger is run on that schedule by Airflow, through `fluid apply`. Stage 3 writes the DAG; [`fluid schedule-sync`](./schedule-sync.md) (stage 11) delivers it to the scheduler.

```yaml
builds:
  - id: ingest_subscriptions
    execution:
      trigger:
        type: schedule              # or no type at all
        schedule: "0 */4 * * *"     # `cron:` is accepted too; five fields or an Airflow preset
        timezone: Europe/Paris      # default UTC
      retries:
        maxAttempts: 4              # Airflow retries = maxAttempts - 1; default 3, at most 10
```

```bash
fluid generate artifacts contracts/orders/contract.fluid.yaml --out dist/artifacts/ \
  --env aws --contract-path contracts/orders/contract.fluid.yaml
```

```text
dist/artifacts/schedule/<product-id>__aws/ingest_subscriptions_dag.py
```

### When a DAG is generated

The `schedule` key writes DAGs when either holds:

- `orchestration.engine` is set to anything except `none`.
- No `orchestration.engine` is set, and a build declares `execution.trigger.schedule` (or `cron`) with trigger `type: schedule` or no type. *(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* A `dataset` or `schedule_and_dataset` trigger counts too. The engine then defaults to Airflow. The file does nothing until `schedule-sync` delivers it, and stage 11 names the scheduler (`airflow`, `mwaa`, `composer` and `astronomer` run Airflow DAGs), so the default decides the file format only. *(since 0.34.0, [forge-cli #1018](https://github.com/Agenticstiger/forge-cli/pull/1018))* A forge Spark stream that declares `execution.retries` counts as such a build too: it gets a keepalive DAG, and the engine defaults to Airflow.

Each such build gets its own DAG that runs `fluid apply`, unless the contract hand-declares `orchestration.tasks`, which keep their declared operators. *(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* Builds that `builds[].dependencies` link share one DAG, with a task for each build. A build is left out when its own `execution.orchestration.engine` is `none` or not Airflow, or when its trigger is `event`, `manual` or `timetable`, which a DAG on a cron or on datasets cannot express. A `dataset` or `schedule_and_dataset` build gets a DAG: see [Build graphs and dataset triggers](../advanced/airflow.md#build-graphs-and-dataset-triggers). In 0.32.0 and earlier, those two were left out too, and a contract with no `orchestration.engine` whose only trigger was `dataset` logged `generate_artifacts_skip_schedule_no_engine` and wrote no DAG. *(since 0.22.0, [forge-cli #734](https://github.com/Agenticstiger/forge-cli/pull/734))* A `continuous` build, or one that runs outside forge-cli, gets no DAG and no task at all (see [Continuous builds](../concepts/builds-exposes-bindings.md#continuous-builds-trigger-type-continuous)).

### Layout and naming

- File: `schedule/<product-id>[__<env>]/<build-id>_dag.py`. *(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* For builds that `builds[].dependencies` link, `<build-id>` is the build that carries the trigger. One directory per product and env, so a sync to a shared DAG root deletes only that product's files (see the [DAG layout](./schedule-sync.md#dag-layout) on the `schedule-sync` page). The `__<env>` suffix is present when an env is set, from `--env` or `$FLUID_ENV`.
- DAG id: `<product>__<env>__<build>` with an env, `<product>__<build>` without.
- The DAG is hashed into `MANIFEST.json`, and a rerun of stage 3 replaces it.
- Upgrading from 0.16.7 or earlier: those versions wrote `schedule/<product-id>/` with DAG id `<product>__<build>`. The first [`fluid schedule-sync`](./schedule-sync.md) after the upgrade has to retire the old DAG of each env, or the old and the new DAG both run and both apply the same product against the same state.

[`fluid generate schedule`](./generate.md#fluid-generate-schedule) writes the same DAG without the `schedule/<product-id>/` directory, into the directory given to `-o` (default `./dags`).

### What each run executes

On the Airflow worker, one `BashOperator` task named `fluid_apply` runs:

```bash
cd "$FLUID_PROJECT_DIR"
fluid apply "$FLUID_PROJECT_DIR/<contract path>" --env <env> \
    --mode amend-and-build --build-id <build id> --yes
```

That is the apply stage 7 runs, so a cloud target keeps one OpenTofu state whether the run came from CI or from the scheduler, provided the worker has the same `FLUID_STATE_BACKEND`. `--env` is left out when the DAG was generated without an env.

*(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* A DAG for linked builds has one such task for each build, named by the build id, and each runs `fluid apply ... --build-id <build id>`. See [Build graphs and dataset triggers](../advanced/airflow.md#build-graphs-and-dataset-triggers).

The DAG sets `max_active_runs=1` (two applies of one build do not overlap) and `catchup=False` (a paused DAG does not replay missed runs). A fluid exit code of 99 fails the task instead of skipping it. The task uses the `airflow.sdk` DAG and `schedule=` of Airflow 3, with imports that fall back to Airflow 2.6 and later.

Fixed when the DAG is generated: the env, the contract path, the cron, the timezone and the retry count. Read on the worker at run time:

| Variable | Meaning |
| --- | --- |
| `FLUID_PROJECT_DIR` | Required. The directory holding the product checkout, the one CI ran the pipeline from. The run fails when it is unset or the contract is not under it. |
| `FLUID_BIN` | The fluid executable. Default `fluid` on `PATH`. |
| `FLUID_DAG_ENV_PASSTHROUGH` | Extra variable names, space separated, to pass to fluid. |

The schedule is checked at generation time to the grammar Airflow parses it with, so a cron Airflow would refuse fails the run instead of the DAG import. This six-field cron:

```text
generate_schedule_invalid_schedule: {'error': "build 'customer_360_pipeline': trigger schedule '0 2 * * * *' is not a five-field cron expression (minute hour day-of-month month day-of-week) or an Airflow preset such as @daily"}
```

fails `fluid generate schedule` with exit 2, and `fluid generate artifacts` with `generate_artifacts_failed` (exit 1). A six-field cron is refused because Airflow's cron parser reads the sixth field as seconds, while a Quartz cron puts seconds first.

### The environment fluid sees

The DAG file holds ids, the contract path, the env name and the names of the variables the contract reads, and no secret values. fluid starts through `env -i` with:

- `PATH HOME USER LOGNAME LANG LANGUAGE LC_ALL LC_CTYPE TZ TMPDIR`, the CA bundle and proxy variables, and `GLUE_ROLE_ARN S3_STAGING_DIR S3_DATA_DIR GOOG_SERVICE_ACCOUNT_NAME TESTCONTAINERS_HOST_OVERRIDE`.
- Any variable whose name starts with `FLUID_`, `AWS_`, `GOOGLE_`, `GCP_`, `GCLOUD_`, `CLOUDSDK_`, `AZURE_`, `ARM_`, `SNOWFLAKE_`, `DATABRICKS_`, `PG`, `POSTGRES_`, `REDSHIFT_`, `ATHENA_`, `VAULT_`, `BAO_` *(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))*, `DBT_`, `DLT_`, `DATAHUB_`, `DMM_`, `ODCS_`, `ODPS_`, `TF_`, `OPENLINEAGE_` or `OTEL_`.
- The variables the contract names through `{{ env.NAME }}`, `${NAME}` or `secretRef: env://NAME`.
- The names listed in `FLUID_DAG_ENV_PASSTHROUGH`.

A name starting `AIRFLOW` does not pass, even when the contract or `FLUID_DAG_ENV_PASSTHROUGH` names it, so the Airflow worker's own configuration (`AIRFLOW__*`, `AIRFLOW_CONN_*`, the Fernet key) does not reach the apply. `VIRTUAL_ENV` is not passed either: on a worker it names Airflow's environment, and fluid's Python runner would run builds with that interpreter. A dbt project's own `env_var()` calls, or dlt's `SOURCES__*` and `DESTINATION__*` settings, are not on the list: name them in `FLUID_DAG_ENV_PASSTHROUGH`.

## PySpark schema modules

*(since 0.37.0)* `--emit pyspark-schema` puts the modules of [`fluid generate pyspark-schema`](./generate-pyspark-schema.md) in the tree and in the MANIFEST, so a sealed release carries them.

```bash
fluid generate artifacts runtime/bundle.tgz --emit odcs,pyspark-schema --out dist/artifacts/
```

```text
dist/artifacts/pyspark-schema/<port>_schema.py
```

- The key is not in the default set. A contract with a column Spark has no type for would fail stage 3 on every run.
- The modules describe the contract the run's ODCS describes. `--env` overlays it; `$FLUID_ENV`, which the DAGs and Spark job configs follow, does not.
- A file at a module's path that the emitter did not write is left alone and the run is refused. A link at `pyspark-schema/` itself is removed, not written through. A run removes only the modules an earlier run wrote.
- [`fluid validate-artifacts`](./validate-artifacts.md) checks each module against an allowlist of what it may hold (one `StructType`, nothing else). A module changed after stage 3 fails stage 4 even if the MANIFEST was rewritten.
- `fluid ship --require-artifacts pyspark-schema` fails a release run that wrote none.

## Custom scaffold

*(since 0.37.0)* `--emit custom-scaffold` generates the files a contract's `extensions.customScaffold` block declares (CI files, job settings, a README) into `custom-scaffold/`, so they are in the MANIFEST and in a sealed release.

```bash
fluid generate artifacts runtime/bundle.tgz \
  --emit odps-bitol,odcs,opds,schedule,policies,spark,custom-scaffold --out dist/artifacts/
```

### Install the engine

The engine is an optional extra. It is not in the default install:

```bash
pip install 'data-product-forge[custom-scaffold]'
```

It needs `data-product-forge-custom-scaffold` 0.5.0 or newer, below 1. The extra is also part of `[all]`. The engine is imported only when a run names the key and the contract declares the block, so `fluid --help` loads what it did before. Without the engine, or with one older than 0.5.0 or one that does not import, the run fails with an error that names the extra.

### Rules

- The key is never part of the default set. A default run on a contract with the block tells you how to ask for it.
- The engine renders the bundles' templates in this process. Name the key only where you trust the contract's bundles.
- Before the engine runs, its own validator checks the block. Every `entrypoint` bundle is held to `FLUID_PLUGINS_ALLOWLIST` and `FLUID_PLUGINS_BLOCKLIST`, as every other plugin is.
- A relative `path:` bundle is read from the contract's directory: the bundle's recorded source contract, else `--contract-path`.
- The engine writes into a hidden directory beside `custom-scaffold/`. Every file it reports must be a regular file there with the reported SHA-256 and size, under the exact name the directory lists. Nothing unreported and no link may be there. Only then is the directory moved into place, so a refused run leaves no scaffold behind.
- Like every other subdirectory of `--out` that stage 3 owns, `custom-scaffold/` is cleared on every run, whatever `--emit` names. A scaffold an earlier run wrote never outlives a run without the key. A directory that holds `fluid-scaffold.yaml` (a bundle, with `--out` at the contract's directory) is refused rather than cleared.
- An unknown `--emit` key, a scaffold bundle in `custom-scaffold/` and a change-request build refuse the run before anything in `--out` changes. The engine's own refusals come after the clear.
- `fluid ship --require-artifacts custom-scaffold` fails a release run that wrote none.
- `fluid generate ci` installs the extra in the pipeline when the contract declares the block, so a pipeline that names the key in `GENERATE_EMIT` can run it.

### Git bundles and credentials

A git bundle that authenticates keeps the engine's own credential model:

| Setting | Where | Meaning |
| --- | --- | --- |
| `FLUID_CUSTOM_SCAFFOLD_AUTH_HOSTS` | Environment where the command runs | The hosts a credential may go to. A host not listed gets none. |
| `secret_ref` in the contract | Contract | May only name a variable that starts with `FLUID_SCAFFOLD_`. |

The engine's operator settings (`FLUID_CUSTOM_SCAFFOLD_*`) cannot come from a project `.env` file.

### Change-request builds

A generated pipeline shares one `GENERATE_EMIT` between its pull or merge request builds and its default-branch builds, and runs stage 3 on both. Naming `custom-scaffold` for releases would run a change's bundle templates before anyone merged it, often with the job's credentials. So the key never runs on a change-request build.

- `fluid generate artifacts --emit custom-scaffold` refuses such a build with `custom_scaffold_change_request`, before anything in `--out` is removed or written and before the engine is imported. Pass `--allow-scaffold-on-change-request` to run it anyway. No variable or `.env` file stands in for the flag.
- `fluid ship` leaves `custom-scaffold` out of stage 3's `--emit` and `--require-artifacts` on such a build and says so in the stage's notes. Stage 3 is skipped when that was all it had to do. A default-branch build keeps it.
- A run that would seal a release (`--release-dir`) or publish while `--require-artifacts` names `custom-scaffold` is refused (exit 2), so a build marked by mistake never ships without it.

This covers all seven generated CI systems, in both install modes. The build is marked by each system's own variables:

| CI system | Marker |
| --- | --- |
| Jenkins | `CHANGE_ID` (also `ghprbPullId`, `gitlabMergeRequestId`) |
| GitHub Actions | `GITHUB_EVENT_NAME` is `pull_request`, `pull_request_target`, `pull_request_review` or `pull_request_review_comment` |
| GitLab CI | `CI_MERGE_REQUEST_IID` or `CI_MERGE_REQUEST_ID`; `CI_PIPELINE_SOURCE` is `merge_request_event` (also the external pull request variables) |
| Azure Pipelines | `BUILD_REASON` is `PullRequest` (also `SYSTEM_PULLREQUEST_PULLREQUESTID`, `SYSTEM_PULLREQUEST_PULLREQUESTNUMBER`) |
| Bitbucket Pipelines | `BITBUCKET_PR_ID` |
| CircleCI | `CIRCLE_PULL_REQUEST`, `CIRCLE_PR_NUMBER` or `CI_PULL_REQUEST` |
| Tekton | None. The generated Pipeline and Task take a `FLUID_CHANGE_REQUEST` parameter that defaults to `true`. Every run counts as a change request unless a default-branch run passes `false` (the header's `tkn` example shows it). A run that forgets it leaves the scaffold out. |

Any other pipeline may set `FLUID_CHANGE_REQUEST` in the job's environment, never in a project `.env`. Any value but blank, `0`, `false`, `no` or `off` marks the build, and only the variable's name is printed. A marker only ever marks a build: `FLUID_CHANGE_REQUEST=false` never clears a CI system's own.

### Troubleshooting

| Code | Meaning and fix |
| --- | --- |
| `custom_scaffold_change_request` | The build is marked as a change request. Run the key on a default-branch build, or pass `--allow-scaffold-on-change-request` where you trust the change. |
| `custom_scaffold_engine_missing` | The extra is not installed. Run `pip install 'data-product-forge[custom-scaffold]'`. |
| `custom_scaffold_engine_too_old` | The engine is older than 0.5.0. Upgrade the extra. |
| `custom_scaffold_engine_broken` | The engine is installed but does not import. Reinstall the extra. |
| `custom_scaffold_contract_invalid` | The engine's validator refused the `extensions.customScaffold` block. |
| `custom_scaffold_bundle_failed` | A bundle could not be loaded. |
| `custom_scaffold_plan_failed` | The engine could not plan the files. |
| `custom_scaffold_unsafe_path` | A file path would leave the output directory. |
| `custom_scaffold_apply_failed` | The engine failed while writing the files. |
| `custom_scaffold_output_failed` | A reported file is missing, differs from its reported digest or size, or a file-system error stopped the move into place. |
| `custom_scaffold_plugin_blocked` | An `entrypoint` bundle is blocked by `FLUID_PLUGINS_ALLOWLIST` or `FLUID_PLUGINS_BLOCKLIST`. |
| `custom_scaffold_failed` | Any other engine failure. The message is redacted. |

## Spark job configs

*(since 0.33.0, [forge-cli #979](https://github.com/Agenticstiger/forge-cli/pull/979))* A forge [Spark build](../advanced/spark-iceberg-aws.md) (`engine: spark` with `parameters.spark`, in a 0.7.7 contract) runs from a `job.json`: the runner config that forge compiles from the contract. The `spark` emit key writes it for each Spark build to `spark/<build id>/job.json`, so the artifacts `MANIFEST.json` holds the hash of the config that gets deployed. A contract with no Spark build writes nothing under `spark/`.

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
```

On the contract from [Spark to Iceberg on AWS](../advanced/spark-iceberg-aws.md#declaring-the-build), run on forge-cli `main`:

```text
...
generate_artifacts_spark_apply_time_values
✅ Artifacts written to dist/artifacts
   MANIFEST digest:
sha256:...
   files: 6
```

```text
dist/artifacts/
├── MANIFEST.json
├── odcs/product.odcs.orders.yaml
├── odps-bitol/commerce.orders-stream.odps.yaml
├── odps-bitol/commerce.orders-stream.orders.odcs.yaml
├── opds/commerce.orders-stream.opds.json
├── policy/bindings.json
└── spark/ingest-orders/job.json
```

`job.json`, trimmed:

```json
{
  "build": "ingest-orders",
  "checkpoint": "s3://commerce-lake/_checkpoints/commerce.orders-stream/ingest-orders/",
  "configVersion": 1,
  ...
  "mode": "streaming",
  "product": "commerce.orders-stream",
  "sink": {
    "catalog": "fluid",
    "region": "eu-west-1",
    "table": "commerce.orders",
    "type": "glue",
    "warehouse": "s3://commerce-lake/iceberg/commerce/orders/"
  },
  "source": {
    "auth": "msk-iam",
    "bootstrapServers": "${fluid_msk_bootstrap_brokers}",
    ...
    "kind": "kafka",
    ...
    "topic": "commerce.orders",
    ...
  },
  ...
}
```

What the file is, and what it is not:

- **It is the deployed config.** [`fluid generate iac`](./generate-iac.md) writes the same text into the `aws_s3_object` that uploads `_fluid/spark/<product>/<build>/job.json`. On this contract the only difference from that object is the broker list, which OpenTofu fills in. The file is the same whether `generate artifacts` reads the contract file or a bundle made from it. With a contract file, `--env` applies that overlay first; a bundle is already bound to its environment.
- **Two values stay placeholders**, because only `tofu apply` knows them: `<account>` in the warehouse and checkpoint of an output that names no bucket (the account's shared `<account>-fluid-data` bucket), and `${fluid_msk_bootstrap_brokers}` for a source named by its MSK cluster ARN. The run logs `generate_artifacts_spark_apply_time_values` for each build that holds one.
- **What the upload refuses is refused here.** Two builds whose ids differ only in case or in `-` and `_` would write one file, and a config that holds `${` is an unresolved interpolation that the Spark runner refuses. Either stops the stage with `generate_artifacts_failed` and `emit_key: spark`, as does a build the Spark compiler refuses. The first looks like this:

  ```text
  ❌ generate_artifacts_failed  [ERR_GENERATE_ARTIFACTS_FAILED]
    error: Spark builds 'ingest-orders' and 'ingest_orders' would write one job.json (ids that differ only in case or in '-' and '_' name one file); give each its own id
    emit_key: spark
  ```

- **The operator's upload rules are not applied.** The settings that limit contract SQL and the hosts a job may name stay with `fluid apply`; `fluid validate` reports them. A `job.json` written here can still be refused at apply.
- **A rerun clears only files of this shape.** Whatever `--emit` says, a run first removes the `<out>/spark/<dir>/job.json` files already there, and then the directories that leave empty. It removes no other file under `<out>/spark/`.

Stage 4 checks each file: [`fluid validate-artifacts`](./validate-artifacts.md) reads it as a JSON object with an integer `configVersion`, a `build` that names its directory, and `product`, `mode` and `sink`.

## Fragment layouts

A fragment layout is a root contract that composes its exposes and builds from files through `$ref` (see [Contract refs](../concepts/contract-refs.md)). `fluid generate artifacts` loads the composed contract, with or without `--env`, so a split contract gets byte-identical artifacts to the same contract written flat:

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
```

In 0.24.0 and earlier the command read the root as written unless `--env` was given, and failed on a fragment root with `FLUID expose has no usable name`; `generate ci` also judged reference-only builds and engines from the raw root. Both are fixed in 0.25.0 ([forge-cli #760](https://github.com/Agenticstiger/forge-cli/pull/760)).

The generated Jenkins and Tekton pipelines feed stage 3 the bundle:

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
fluid generate artifacts runtime/bundle.tgz --out dist/artifacts/
```

## Examples

### Explicit emit set

```bash
# Catalog only (skip DAGs and bindings)
fluid generate artifacts contract.fluid.yaml --emit odcs,odps-bitol

# Execution only
fluid generate artifacts contract.fluid.yaml --emit schedule,policies

# PySpark schema modules too (since 0.37.0)
fluid generate artifacts contract.fluid.yaml --emit odcs,pyspark-schema
```

## Next step

Run [`fluid validate-artifacts`](./validate-artifacts.md) against the emitted tree to verify MANIFEST integrity and per-format schemas before shipping to catalogs or the scheduler.

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
fluid validate-artifacts dist/artifacts/ --strict
```
