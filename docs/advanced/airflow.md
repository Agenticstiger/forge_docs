# Airflow Integration

Generate Apache Airflow DAGs from a contract. `fluid generate schedule` writes one DAG per scheduled build; each run of the DAG executes `fluid apply` for that build on the Airflow worker. The older `fluid generate-airflow` command is deprecated and is described [below](#fluid-generate-airflow-deprecated).

## Quick start

A build becomes a DAG when it declares a cron trigger:

```yaml
builds:
  - id: customer_360_pipeline
    execution:
      trigger:
        type: schedule
        cron: "0 2 * * *"
        timezone: Europe/Dublin
```

Generate the DAG into a directory named after the product id, then check what it wrote:

```bash
fluid generate schedule contract.fluid.yaml -o dags/gold.customer.analytics_360_v1
```

```text
Generated 1 files (airflow scheduler):

  dags/gold.customer.analytics_360_v1/customer_360_pipeline_dag.py

Tip: To regenerate after editing the contract: fluid generate schedule
```

`fluid generate schedule` renders these DAGs when the contract's `orchestration.engine` is `airflow` and the contract declares no explicit `orchestration.tasks`. A contract with no `orchestration.engine` at all but a build with a cron trigger defaults to Airflow. A build with a trigger of another type (`event`, `timetable`, `schedule_and_dataset`) gets no DAG, because a plain cron DAG would silently drop what those types mean. `--env` is the overlay for the generation and the `--env` every scheduled run passes to `fluid apply`; leave it out for a contract with no overlays.

## What the DAG does

The generated file says it in its own docstring (real output, trimmed):

```text
Every run executes this on the Airflow worker, with the constants below
filled in (`--env` is left out when FLUID_ENV_NAME is empty):

    cd "$FLUID_PROJECT_DIR"
    fluid apply "$FLUID_PROJECT_DIR/$CONTRACT_PATH" --env "$FLUID_ENV_NAME" \
        --mode amend-and-build --build-id "$BUILD_ID" --yes

Worker requirements:

- FLUID_PROJECT_DIR names the directory that holds the product checkout,
  the directory CI ran the pipeline from.
- `fluid` is on PATH, or FLUID_BIN names the executable.
- The credentials the apply needs are in the worker environment. Only
  these reach the fluid process:

    PATH HOME USER LOGNAME LANG LANGUAGE LC_ALL LC_CTYPE TZ TMPDIR
    SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE HTTP_PROXY
    HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy GLUE_ROLE_ARN
    S3_STAGING_DIR S3_DATA_DIR GOOG_SERVICE_ACCOUNT_NAME
    TESTCONTAINERS_HOST_OVERRIDE

  every name matching

    FLUID_* AWS_* GOOGLE_* GCP_* GCLOUD_* CLOUDSDK_* AZURE_* ARM_*
    SNOWFLAKE_* DATABRICKS_* PG* POSTGRES_* REDSHIFT_* ATHENA_* VAULT_*
    DBT_* DLT_* DATAHUB_* DMM_* ODCS_* ODPS_* TF_* OPENLINEAGE_* OTEL_*

  the variables the contract reads (CONTRACT_ENV_NAMES), and any names
  listed, space separated, in FLUID_DAG_ENV_PASSTHROUGH. fluid starts with
  nothing else, and never with a variable whose name starts AIRFLOW.
```

In practice:

- Set `FLUID_PROJECT_DIR` on the worker. Without it the task fails with `set FLUID_PROJECT_DIR on the Airflow worker to the directory that holds the product checkout`. The contract path is the path you gave the generator, relative to the working directory, or `--contract-path` when the worker's layout differs.
- Put the credentials the apply needs in the worker environment. The DAG starts `fluid` with an empty environment plus the names above, so a variable that is neither on the list nor named by a `{{ env.NAME }}` or `${NAME}` placeholder in the contract, nor an `env://NAME` `secretRef`, does not arrive. Add one with `FLUID_DAG_ENV_PASSTHROUGH="NAME1 NAME2"`.
- A DAG uses `max_active_runs=1` and `catchup=False`, retries from the build's `execution.retries.maxAttempts` (attempts minus one), and sets a three-hour execution timeout.
- The same product on two clouds needs a directory each (`<product>` with no env, `<product>__<env>` with one), so each [schedule sync](#pushing-dags-to-the-scheduler) mirrors only its own DAGs.

## Pushing DAGs to the scheduler

`fluid generate artifacts` writes the schedule artifacts under `schedule/<product-id>/`, and stage 11 of a [generated Jenkins pipeline](./operating-in-ci.md) hands that directory to `fluid schedule-sync`:

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts
fluid schedule-sync --scheduler airflow --dags-dir dist/artifacts/schedule --destination dest --dry-run
```

```text
[schedule-sync] → /usr/bin/rsync -av --delete -- .../dist/artifacts/schedule/gold.customer.analytics_360_v1/ .../dest/gold.customer.analytics_360_v1/
[schedule-sync] ✔ airflow sync complete (1 subprocess(es))
```

`--dags-dir` must contain one directory per product. With the default `--delete-scope product`, a loose file in `--dags-dir` is refused with `schedule_sync_dags_dir_not_product_scoped` and exit code 2, so one product's sync cannot delete another's DAGs. If you generated with `fluid generate schedule`, write into `-o <dags-dir>/<product-id>/` as in the quick start. `schedule-sync` takes no contract argument: it needs `--scheduler` and `--dags-dir`, plus `--destination` for `airflow` and `mwaa`.

## `fluid generate-airflow` (deprecated)

`fluid generate-airflow` still runs, and prints a warning that points at its replacement:

```bash
fluid generate-airflow contract.yaml -o dag.py --dag-id my_pipeline --schedule "0 * * * *"
```

```text
{"time": "2026-10-05T00:40:54Z", "level": "WARNING", "name": "fluid.cli", "message": "Note: 'generate-airflow' is deprecated. Use 'fluid generate schedule --scheduler airflow' instead."}
DAG written to dag.py
```

It renders one `BashOperator` task per provider action in the plan, and its flags are `-o`, `--dag-id`, `--schedule`, `--env` and `--verbose`. For the quickstart contract the tasks are placeholders:

```python
provision_customer_360_master = BashOperator(
    task_id='provision_customer_360_master',
    bash_command="echo 'Provision customer_360_master on local'",
    dag=dag
)
```

Notes for the DAGs it writes:

- It targets Airflow 2 APIs: the file imports `days_ago` and sets `schedule_interval`.
- Contract values that reach a `bash_command` are stripped of `{` and `}`, because Airflow renders `bash_command` as a Jinja template at run time, and then shell-quoted, so a build `script` arrives as one token, not a shell line.
- Task ids are sanitized, and two actions whose ids differ only in punctuation get `_2`, `_3` suffixes instead of one silently replacing the other.
- A dbt build runs `dbt run --select <script or build id>`; `--models`, which dbt 2 rejects, is not used.

For a walkthrough that builds a pipeline from a contract, see the [Declarative Airflow Walkthrough](../walkthrough/airflow-declarative.md).

## Cloud Composer deployment

Upload a generated DAG to the environment's bucket:

```bash
BUCKET=$(gcloud composer environments describe my-env \
  --location us-central1 \
  --format="get(config.dagGcsPrefix)")

gsutil cp customer_360_pipeline_dag.py $BUCKET/dags/
```

Create the environment with the image version your organisation supports (`gcloud composer environments create my-env --location us-central1 --image-version <composer-image-version>`). The worker also needs `FLUID_PROJECT_DIR`, the `fluid` CLI and the product checkout; see [What the DAG does](#what-the-dag-does).

## Local Airflow testing

Parse the DAG file before deploying it:

```bash
python3 dags/gold.customer.analytics_360_v1/customer_360_pipeline_dag.py
```

If the file imports, Airflow can load it. Running it needs `FLUID_PROJECT_DIR` and the `fluid` CLI on the machine that runs the Airflow worker.

## See also

- [Declarative Airflow Walkthrough](../walkthrough/airflow-declarative.md): a build-by-build tour
- [Operating in CI](./operating-in-ci.md): stage 11 and `schedule-sync` in a pipeline
- [`fluid generate`](../cli/generate.md): the `generate` subcommands
- [GCP walkthrough](../walkthrough/gcp.md): Cloud Composer, end to end
