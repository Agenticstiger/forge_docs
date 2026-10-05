# Declarative Airflow DAG Generation

Generate Airflow DAGs from a data product contract instead of writing them. FLUID produces two kinds of DAG, and they do different jobs:

- A **scheduled-build DAG** runs `fluid apply` for one build on a cron schedule. You declare the schedule on the build, and the DAG is what Airflow runs. This is the DAG that stage 3 of the [11-stage pipeline](./11-stage-pipeline.md) writes and stage 11 delivers.
- A **provider-action DAG** is made from a contract's `exposes[]` and `builds[]` (or its `orchestration.tasks`) with `fluid generate schedule` or `fluid generate-airflow`. Its tasks are shell or log steps.

This page generates both with CLI `0.18.1` and shows what each file contains, so you can decide which one fits. Output is real; absolute paths are shortened to `...`.

## Scheduled builds: a DAG that runs `fluid apply`

### Declare the schedule on the build

Take the product from the [local walkthrough](./local.md) and add an `execution` block to its build:

```yaml
builds:
  - id: build_genre_preferences
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        ...
    execution:
      trigger:
        type: schedule
        schedule: "0 2 * * *"
        timezone: Europe/Paris
      retries:
        maxAttempts: 3
    outputs:
      - genre_preferences
```

| Field | Meaning |
| --- | --- |
| `trigger.type` | `schedule`, or leave it out |
| `trigger.schedule` | an Airflow preset (`@once`, `@hourly`, `@daily`, `@weekly`, `@monthly`, `@yearly`, `@annually`, `@midnight`) or a five-field cron; `cron:` is accepted as a synonym |
| `trigger.timezone` | the schedule's time zone; default `UTC` |
| `retries.maxAttempts` | Airflow retries are `maxAttempts - 1`; with no `retries` block the DAG uses 3 retries, and 10 is the maximum |

The schedule is checked against the grammar Airflow parses it with (croniter), so a schedule Airflow would refuse fails when you generate, not when Airflow imports the DAG. A six-field cron is refused, because croniter reads the sixth field as seconds while Quartz puts seconds first:

```text
{"time": "2026-10-05T06:21:28Z", "level": "ERROR", "name": "fluid.cli", "message": "generate_schedule_invalid_schedule: {'error': \"build 'build_genre_preferences': trigger schedule '0 0 2 * * *' is not a five-field cron expression (minute hour day-of-month month day-of-week) or an Airflow preset such as @daily\"}"}
```

`fluid generate schedule` exits 2. `fluid generate artifacts` (stage 3) exits 1 on the same contract.

### Generate the DAG

```bash
fluid generate schedule contract.fluid.yaml --scheduler airflow --env dev \
  --contract-path genre-preferences/contract.fluid.yaml -o dags/
```

```text
overlay_base_env: --env 'dev' has no overlay for .../contract.fluid.yaml; using the base contract (dev is the base by convention)

Generated 1 files (airflow scheduler):

  dags/build_genre_preferences_dag.py

Tip: To regenerate after editing the contract: fluid generate schedule
```

`--env` names the overlay every scheduled run passes to `fluid apply`; it defaults to `$FLUID_ENV`. `--contract-path` is where the contract sits relative to `$FLUID_PROJECT_DIR` on the Airflow worker; it defaults to the path you gave on the command line, relative to the current directory. `dev` has no overlay here, which the first line says, and the DAG still carries `dev`.

In the pipeline, stage 3 writes the same DAG with `fluid generate artifacts`, into one directory per product and environment: `dist/artifacts/schedule/<product id>__<env>/<build id>_dag.py`.

### Read the DAG

```python
PRODUCT_ID = 'entertainment.genre_preferences_v1'
BUILD_ID = 'build_genre_preferences'
CONTRACT_PATH = 'genre-preferences/contract.fluid.yaml'
FLUID_ENV_NAME = 'dev'
CONTRACT_ENV_NAMES = ''
SCHEDULE = '0 2 * * *'
TIMEZONE = 'Europe/Paris'
RETRIES = 2
```

```python
with DAG(
    dag_id='entertainment.genre_preferences_v1__dev__build_genre_preferences',
    description='fluid apply entertainment.genre_preferences_v1 --build-id build_genre_preferences',
    schedule=SCHEDULE,
    start_date=pendulum.datetime(2026, 1, 1, tz=TIMEZONE),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "fluid",
        "retries": RETRIES,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(hours=3),
    },
    tags=["fluid", PRODUCT_ID[:100]],
    doc_md=__doc__,
) as dag:
    BashOperator(
        task_id="fluid_apply",
        bash_command=BASH_COMMAND,
        env={
            "FLUID_DAG_CONTRACT": CONTRACT_PATH,
            "FLUID_DAG_ENV": FLUID_ENV_NAME,
            "FLUID_DAG_BUILD_ID": BUILD_ID,
            "FLUID_DAG_CONTRACT_ENV": CONTRACT_ENV_NAMES,
        },
        append_env=True,
        skip_on_exit_code=None,
    )
```

The DAG has one task, a `BashOperator` that runs, on the worker:

```bash
cd "$FLUID_PROJECT_DIR"
fluid apply "$FLUID_PROJECT_DIR/$CONTRACT_PATH" --env "$FLUID_ENV_NAME" \
    --mode amend-and-build --build-id "$BUILD_ID" --yes
```

This is the same apply that stage 7 runs, so a cloud target uses the same OpenTofu state as CI when the worker has the same state-backend settings (`FLUID_STATE_BACKEND`). `--env` is left out when `FLUID_ENV_NAME` is empty.

The DAG is written for Airflow 3 (`airflow.sdk.DAG`, `BashOperator` from `apache-airflow-providers-standard`) with guarded imports that fall back to `airflow.DAG` and `airflow.operators.bash` on Airflow 2.6 and later. It sets `catchup=False` and `max_active_runs=1`, so two applies of one build never overlap, a three-hour execution timeout, and `skip_on_exit_code=None`, so a `fluid` exit code of 99 fails the task instead of skipping it.

### What the Airflow worker needs

| On the worker | Meaning |
| --- | --- |
| `FLUID_PROJECT_DIR` | required: the directory that holds the product checkout, the one CI ran the pipeline from. The run fails if it is unset or the contract is not under it |
| `fluid` on `PATH`, or `FLUID_BIN` | the executable to run |
| the credentials the apply needs | in the worker's environment; nothing secret is written into the DAG file |
| `FLUID_DAG_ENV_PASSTHROUGH` | extra variable names, space separated, to pass on to `fluid` |

`fluid` is started through `env -i`, with only the variables the DAG's docstring lists: `PATH`, `HOME`, the locale and proxy variables, each name matching `FLUID_*`, `AWS_*`, `GOOGLE_*`, `GCP_*`, `SNOWFLAKE_*` and the other provider prefixes it names, the variables the contract reads through `{{ env.NAME }}`, `${NAME}` or `secretRef: env://NAME`, and the names in `FLUID_DAG_ENV_PASSTHROUGH`. A name starting `AIRFLOW` never passes, so the worker's own configuration, connections and Fernet key never reach the apply. A dbt project's own `env_var()` calls and dlt's `SOURCES__*` settings are not known to `fluid`: name them in `FLUID_DAG_ENV_PASSTHROUGH`.

### Which builds get a DAG

Stage 3 (`fluid generate artifacts`) writes schedule artifacts when the contract sets `orchestration.engine` to anything but `none`, or when it sets no engine and a build declares `execution.trigger.schedule` (or `cron`) with `type: schedule` or no type. Airflow renders the second case.

Within that, a build gets the `fluid apply` DAG unless its own `execution.orchestration.engine` is `none` or not Airflow, or its trigger is `event`, `dataset`, `schedule_and_dataset` or `timetable`, which a cron DAG cannot express. A contract that hand-declares `orchestration.tasks` keeps those operators instead.

### The DAG id and the environment

The DAG id is `<product id>__<env>__<build id>`:

```text
dag_id='entertainment.genre_preferences_v1__dev__build_genre_preferences',
```

With no environment (`--env ""` and no `$FLUID_ENV`) it is `<product id>__<build id>`. Because the environment is in the id, you do not need to pass your own `--dag-id` to tell `dev` and `prod` apart: generate each with its own `--env`.

Airflow keys run history on the DAG id, so a DAG that gains an environment starts a new history. DAGs from forge-cli 0.16.7 and earlier were rendered into `<product id>/` with the id `<product id>__<build id>`. `fluid schedule-sync` retires those when the destination is a local path or `git+ssh` and the scheduler is `airflow`; elsewhere it prints a note telling you to delete them once, because Airflow would otherwise run both. [Stage 11](./11-stage-pipeline.md#stage-11-schedule-sync) shows the report.

### Deliver it

```bash
fluid schedule-sync --scheduler airflow --dags-dir dist/artifacts/schedule/ \
  --destination /opt/airflow/dags/ --env dev
```

`--env` on `schedule-sync` is a tag for the log and the report; the overlay was fixed when the DAG was generated. `--delete-scope product` (the default) mirrors each top-level directory of `--dags-dir` into the same-named directory of the destination and deletes only there; `destination` mirrors onto the whole destination; `none` copies without deleting. See [`fluid schedule-sync`](../cli/schedule-sync.md).

---

## Provider-action DAGs

A contract with no schedule trigger can still produce a DAG from its builds and exposes, with `fluid generate-airflow` or `fluid generate schedule`. This section generates one from a Bitcoin price tracker contract on BigQuery with a Python ingest and two dbt models.

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: crypto.bitcoin_prices_gcp
name: bitcoin-prices-gcp

# Metadata drives DAG configuration
metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-eng@example.com

tags:
  - crypto
  - bitcoin

# Builds define the workflow
builds:
  - id: ingest_bitcoin_prices
    description: Fetch Bitcoin prices from CoinGecko API
    pattern: hybrid-reference
    engine: python
    repository: ./runtime
    properties:
      model: ingest_bitcoin_prices

    execution:
      trigger:
        type: manual
      runtime:
        resources:
          memory: "512Mi"
        timeout: "PT5M"
      retries:
        maxAttempts: 3
        backoffStrategy: exponential

    outputs:
      - bitcoin_prices_table

  - id: calculate_daily_summary
    description: Calculate daily price statistics
    pattern: hybrid-reference
    engine: dbt
    repository: ./dbt
    properties:
      model: daily_price_summary
    outputs:
      - daily_price_summary

  - id: calculate_price_trends
    description: Calculate moving averages
    pattern: hybrid-reference
    engine: dbt
    repository: ./dbt
    properties:
      model: price_trends
    outputs:
      - price_trends

# Exposes define datasets and bindings
exposes:
  - exposeId: bitcoin_prices_table
    kind: table
    title: Bitcoin Prices Table
    description: "Real-time Bitcoin prices from CoinGecko API"

    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: crypto_data
        table: bitcoin_prices
        region: us-central1

    contract:
      schema:
        - name: price_timestamp
          type: TIMESTAMP
          required: true
        - name: price_usd
          type: FLOAT64
          required: true
        - name: price_eur
          type: FLOAT64
          required: true
        - name: price_gbp
          type: FLOAT64
          required: true
        - name: market_cap_usd
          type: FLOAT64
          required: true
        - name: volume_24h_usd
          type: FLOAT64
          required: true
        - name: price_change_24h_percent
          type: FLOAT64
          required: false
        - name: ingestion_timestamp
          type: TIMESTAMP
          required: true
```

It validates against schema `0.7.5`. The parts that matter here are the three `builds[]` (one Python, two dbt, each with `outputs`) and the BigQuery `binding` on `bitcoin_prices_table`.

### `fluid generate-airflow`

```bash
fluid generate-airflow contract.fluid.yaml -o dags/bitcoin_tracker.py \
  --dag-id bitcoin_tracker --schedule "0 * * * *"
```

As of 0.18.1 the command logs `Note: 'generate-airflow' is deprecated. Use 'fluid generate schedule --scheduler airflow' instead.` and still writes the file:

```python
# DAG definition
dag = DAG(
    dag_id='bitcoin_tracker',
    description='FLUID data product: bitcoin-prices-gcp',
    schedule_interval='0 * * * *',
    start_date=days_ago(1),
    catchup=False,
    tags=["fluid", "data-product", 'dataproduct', 'unknown'],
    default_args=default_args
)


# Provision dataset: bitcoin_prices_table
provision_bitcoin_prices_table = BashOperator(
    task_id='provision_bitcoin_prices_table',
    bash_command='bq mk --project_id=my-project-id --dataset crypto_data || true',
    dag=dag
)


# Schedule task: ingest_bitcoin_prices
schedule_ingest_bitcoin_prices = BashOperator(
    task_id='schedule_ingest_bitcoin_prices',
    bash_command="echo 'Run ingest_bitcoin_prices'",
    dag=dag
)


# Schedule task: calculate_daily_summary
schedule_calculate_daily_summary = BashOperator(
    task_id='schedule_calculate_daily_summary',
    bash_command='dbt run --select calculate_daily_summary',
    dag=dag
)


# Schedule task: calculate_price_trends
schedule_calculate_price_trends = BashOperator(
    task_id='schedule_calculate_price_trends',
    bash_command='dbt run --select calculate_price_trends',
    dag=dag
)

# Task dependencies
# No dependencies specified
```

What this file does and does not do:

- Contract values that land in `bash_command` are shell-quoted, and task ids are sanitised and de-duplicated.
- A dbt build becomes `dbt run --select <build id>`. The Python build became `echo 'Run ingest_bitcoin_prices'`: the script is not run.
- The BigQuery expose becomes a `bq mk` task. Its `|| true` means a failure to create the dataset does not fail the task.
- Dependencies are not inferred from `outputs`: this contract produced `# No dependencies specified`, so the three tasks run in parallel. Declare ordering with `orchestration.tasks` and `dependsOn` if you need it.
- It imports Airflow 2 modules (`airflow.operators.bash`, `airflow.utils.dates.days_ago`).
- `--dag-id`, `--schedule` and `--env` override the DAG id, the schedule and the overlay. Without `--schedule` the schedule comes from `orchestration.schedule`, else `@daily`.

### `fluid generate schedule`

```bash
fluid generate schedule contract.fluid.yaml --scheduler airflow -o dags/
```

On the same contract, which has `trigger: type: manual` and no `orchestration` block, this writes a differently shaped file with one task per build and a schedule of `0 2 * * *`:

```python
# Task definitions
ingest_bitcoin_prices = PythonOperator(
    task_id='ingest_bitcoin_prices',
    python_callable=lambda: logger.info(
        'Action: ' + 'generic.python.run' + ', Params: ' + '{"model": "ingest_bitcoin_prices"}'
    ),
    dag=dag,
)

calculate_daily_summary = PythonOperator(
    task_id='calculate_daily_summary',
    python_callable=lambda: logger.info(
        'Action: ' + 'generic.dbt.run' + ', Params: ' + '{"model": "daily_price_summary"}'
    ),
    dag=dag,
)

calculate_price_trends = PythonOperator(
    task_id='calculate_price_trends',
    python_callable=lambda: logger.info(
        'Action: ' + 'generic.dbt.run' + ', Params: ' + '{"model": "price_trends"}'
    ),
    dag=dag,
)

# Task dependencies
ingest_bitcoin_prices >> calculate_daily_summary
calculate_daily_summary >> calculate_price_trends
```

The tasks only log `Action: generic.dbt.run, Params: ...`. They run nothing. For a build that must run, put a schedule trigger on it and use the scheduled-build DAG above.

---

## Choose a DAG

| You want | Use |
| --- | --- |
| Airflow to run a build on a schedule, through the same apply CI uses | a `schedule` trigger on the build, then stage 3 or `fluid generate schedule` |
| One DAG per environment | the same, with `--env <name>` for each |
| DAGs delivered by CI | stage 11: [`fluid schedule-sync`](../cli/schedule-sync.md) |
| A DAG skeleton from `orchestration.tasks` for AWS, GCP or Snowflake provider actions | [`fluid export`](./export-orchestration.md) |

Edit the contract, not the DAG: the file says so in its docstring, and the next generation replaces it.

## Related

- [The 11-stage pipeline](./11-stage-pipeline.md): stages 3 and 11 in context
- [Airflow integration](../advanced/airflow.md)
- [`fluid generate`](../cli/generate.md) and [`fluid schedule-sync`](../cli/schedule-sync.md)
- [Local walkthrough](./local.md): the product this page adds a schedule to
