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

A contract that gets a schedule artifact adds `schedule/<product-id>[__<env>]/<build-id>_dag.py`, described in [Scheduled builds](#scheduled-builds).

## Syntax

```bash
fluid generate artifacts CONTRACT [--out PATH] [--emit KEYS] [--manifest PATH] [--env ENV] [--contract-path PATH]
```

`CONTRACT` is a bundle (`.tgz`) or a contract YAML file. A bundle comes from [`fluid bundle --format tgz`](./bundle.md): `generate artifacts` extracts it and re-verifies its MANIFEST first. A contract file is the local-dev shortcut; the pipeline path is the bundle.

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Bundle (`.tgz`) or contract YAML file (positional, required). |
| `--out PATH` | Output directory. Default `dist/artifacts/`. |
| `--emit KEYS` | Comma-separated emit keys. Default: `odps-bitol,odcs,opds,schedule,policies`. See the [emit set](#emit-set). `dbt` is not an emit key; dbt projects come from [`fluid generate transformation`](./generate.md#fluid-generate-transformation). |
| `--manifest PATH` | Where to write `MANIFEST.json`. Default `<out>/MANIFEST.json`. Stage 4 re-verifies it. |
| `--env ENV` | The environment the artifacts are for. A bundle must have been built for it (`fluid bundle --env ENV`); a bundle built for another env is refused, because a bundle is not re-overlaid. A contract file gets the overlay applied, as `fluid bundle --env ENV` would. The value is also the `--env` every scheduled DAG passes to `fluid apply`. Default for the DAGs: `$FLUID_ENV`; if that is unset too, the DAGs carry no `--env`. `--env ''` means no `--env`. |
| `--contract-path PATH` | The contract's path relative to the project directory. Scheduled DAGs append it to `$FLUID_PROJECT_DIR` on the Airflow worker. Default: the input's path relative to the current directory for a contract file, and `contract.fluid.yaml` (with a warning) for a bundle, which records no location. |

## Emit set

| Key | What it emits | Notes |
| --- | --- | --- |
| `odcs` | ODCS v3.1.0 files under `odcs/`, one per exposed port | Schema vendored from `bitol-io/open-data-contract-standard`. |
| `odps-bitol` | ODPS-Bitol v1.0.0 product file under `odps-bitol/`, with an ODCS file per exposed port beside it | Schema vendored from `bitol-io/open-data-product-standard`. |
| `opds` | OPDS v4.1 (LF/ODPI) product file under `opds/` (`<product-id>.opds.json`) | `odps` is accepted as a deprecated alias of `opds` and warns. |
| `schedule` | Airflow DAG files under `schedule/` | Emitted when `orchestration.engine` is set, or when a build declares a schedule trigger. See [Scheduled builds](#scheduled-builds). |
| `policies` | `policy/bindings.json`, the compiled IAM / GRANT bindings | |

`builds[].pattern` (for example `hybrid-reference`) decides how the transformation runs and gates no emit key: a reference-only contract gets the same set as any other.

When `schedule` is requested and the contract has nothing to schedule, the run logs one of these events, drops the key and continues:

| Event | Cause |
| --- | --- |
| `generate_artifacts_skip_schedule_no_engine` | No `orchestration.engine`, and no build with a schedule trigger. |
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
- No `orchestration.engine` is set, and a build declares `execution.trigger.schedule` (or `cron`) with trigger `type: schedule` or no type. The engine then defaults to Airflow. The file does nothing until `schedule-sync` delivers it, and stage 11 names the scheduler (`airflow`, `mwaa`, `composer` and `astronomer` run Airflow DAGs), so the default decides the file format only.

Each such build gets its own DAG that runs `fluid apply`, unless the contract hand-declares `orchestration.tasks`, which keep their declared operators. A build is left out when its own `execution.orchestration.engine` is `none` or not Airflow, or when its trigger is `event`, `dataset`, `schedule_and_dataset` or `timetable`, which a plain cron DAG cannot express.

### Layout and naming

- File: `schedule/<product-id>[__<env>]/<build-id>_dag.py`. One directory per product and env, so a sync to a shared DAG root deletes only that product's files. The `__<env>` suffix is present when an env is set, from `--env` or `$FLUID_ENV`.
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
- Any variable whose name starts with `FLUID_`, `AWS_`, `GOOGLE_`, `GCP_`, `GCLOUD_`, `CLOUDSDK_`, `AZURE_`, `ARM_`, `SNOWFLAKE_`, `DATABRICKS_`, `PG`, `POSTGRES_`, `REDSHIFT_`, `ATHENA_`, `VAULT_`, `DBT_`, `DLT_`, `DATAHUB_`, `DMM_`, `ODCS_`, `ODPS_`, `TF_`, `OPENLINEAGE_` or `OTEL_`.
- The variables the contract names through `{{ env.NAME }}`, `${NAME}` or `secretRef: env://NAME`.
- The names listed in `FLUID_DAG_ENV_PASSTHROUGH`.

A name starting `AIRFLOW` does not pass, even when the contract or `FLUID_DAG_ENV_PASSTHROUGH` names it, so the Airflow worker's own configuration (`AIRFLOW__*`, `AIRFLOW_CONN_*`, the Fernet key) does not reach the apply. `VIRTUAL_ENV` is not passed either: on a worker it names Airflow's environment, and fluid's Python runner would run builds with that interpreter. A dbt project's own `env_var()` calls, or dlt's `SOURCES__*` and `DESTINATION__*` settings, are not on the list: name them in `FLUID_DAG_ENV_PASSTHROUGH`.

## Fragment layouts

A fragment layout is a root contract that composes its exposes and builds from files through `$ref` (see [Contract refs](../concepts/contract-refs.md)). As of 0.18.1, `fluid generate artifacts` reads a contract file as written and does not resolve `$ref`, so the default emit set fails on a fragment root:

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
```

```text
❌ Provider error: FLUID expose has no usable name — Bitol ODPS v1.0.0
OutputPort requires a stable port name. Set expose.exposeId, expose.id, or
expose.name.
```

The exit code is 1, and an empty `odps-bitol/` directory is left in `--out`. The same product in flat form succeeds. Either of these works:

```bash
# the stage-1 bundle, which carries the resolved contract
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
fluid generate artifacts runtime/bundle.tgz --out dist/artifacts/

# or --env, which loads the contract with its overlay and its $refs resolved
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/ --env dev
```

The generated Jenkins and Tekton pipelines feed stage 3 the bundle. In the same check on 0.18.1, `fluid generate transformation`, `generate schedule`, `generate standard`, `generate dbt-tests`, `generate ci` and `generate iac` loaded the fragment root; `generate artifacts` was the one that did not.

## Examples

### Explicit emit set

```bash
# Catalog only (skip DAGs and bindings)
fluid generate artifacts contract.fluid.yaml --emit odcs,odps-bitol

# Execution only
fluid generate artifacts contract.fluid.yaml --emit schedule,policies
```

## Next step

Run [`fluid validate-artifacts`](./validate-artifacts.md) against the emitted tree to verify MANIFEST integrity and per-format schemas before shipping to catalogs or the scheduler.

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
fluid validate-artifacts dist/artifacts/ --strict
```
