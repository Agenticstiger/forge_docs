# Airflow Integration

Generate Apache Airflow DAGs from a contract. `fluid generate schedule` writes one DAG per scheduled build; each run of the DAG executes `fluid apply` for that build on the Airflow worker. *(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* Builds that `builds[].dependencies` link run in one DAG, one task for each build, and a build can run on a dataset trigger: see [Build graphs and dataset triggers](#build-graphs-and-dataset-triggers). The older `fluid generate-airflow` command is deprecated and is described [below](#fluid-generate-airflow-deprecated).

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

`fluid generate schedule` renders these DAGs when the contract's `orchestration.engine` is `airflow` and the contract declares no explicit `orchestration.tasks`. A contract with no `orchestration.engine` at all but a build with a cron trigger defaults to Airflow.

*(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* A build with a `dataset` or `schedule_and_dataset` trigger gets a DAG too, and a contract with no `orchestration.engine` and such a build defaults to Airflow. Builds that `builds[].dependencies` link run in one DAG. [Build graphs and dataset triggers](#build-graphs-and-dataset-triggers) covers both. A build with a trigger of type `event`, `manual` or `timetable` still gets no DAG, because a DAG on a cron or on datasets would silently drop what those types mean. In 0.32.0 and earlier, `dataset` and `schedule_and_dataset` were left out too, and a contract with no `orchestration.engine` whose only trigger was `dataset` stopped with `No scheduler engine specified`. *(since 0.22.0, [forge-cli #734](https://github.com/Agenticstiger/forge-cli/pull/734))* A `continuous` build gets no DAG either: its platform keeps it running (see [Continuous builds](../concepts/builds-exposes-bindings.md#continuous-builds-trigger-type-continuous)). `--env` is the overlay for the generation and the `--env` every scheduled run passes to `fluid apply`; leave it out for a contract with no overlays.

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
    SNOWFLAKE_* DATABRICKS_* PG* POSTGRES_* REDSHIFT_* ATHENA_* VAULT_* BAO_*
    DBT_* DLT_* DATAHUB_* DMM_* ODCS_* ODPS_* TF_* OPENLINEAGE_* OTEL_*

  the variables the contract reads (CONTRACT_ENV_NAMES), and any names
  listed, space separated, in FLUID_DAG_ENV_PASSTHROUGH. fluid starts with
  nothing else, and never with a variable whose name starts AIRFLOW.
```

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* `BAO_*` joins `VAULT_*` among the prefixes, so the OpenBao address, token, namespace and CA variables reach a `vault://` reference's lookup. A 0.30.1 DAG passes only `VAULT_*`.

In practice:

- Set `FLUID_PROJECT_DIR` on the worker. Without it the task fails with `set FLUID_PROJECT_DIR on the Airflow worker to the directory that holds the product checkout`. The contract path is the path you gave the generator, relative to the working directory, or `--contract-path` when the worker's layout differs.
- Put the credentials the apply needs in the worker environment. The DAG starts `fluid` with an empty environment plus the names above, so a variable that is neither on the list nor named by a `{{ env.NAME }}` or `${NAME}` placeholder in the contract, nor an `env://NAME` `secretRef`, does not arrive. Add one with `FLUID_DAG_ENV_PASSTHROUGH="NAME1 NAME2"`.
- A DAG uses `max_active_runs=1` and `catchup=False`, retries from the build's `execution.retries.maxAttempts` (attempts minus one), and sets a three-hour execution timeout.
- *(since 0.34.0, [forge-cli #1009](https://github.com/Agenticstiger/forge-cli/pull/1009))* The task's `fluid apply` runs a dbt or Python build once, whichever of these its `trigger.type` is: `schedule`, `dataset`, `schedule_and_dataset`, `event`, `dependency` or `timetable`. The apply runs the build once. What decides when is the DAG for `schedule`, `dataset` and `schedule_and_dataset`, the DAG of the builds it depends on for `dependency`, and another scheduler or an event for `event` and `timetable`, which get no DAG. In 0.33.0 only `schedule` ran: a dbt or Python build of any other of these types failed with `Unknown trigger type` and exit code `1`, so the task of a `dataset` or `schedule_and_dataset` build, which this page generates a DAG for, failed. A `manual` build keeps its `iterations`, `continuous` is refused, and a `trigger.type` that is none of the names the schema knows fails with `Unknown trigger type` and the list `manual, dataset, dependency, event, schedule, schedule_and_dataset, timetable`. On 0.33.0 a `schedule_and_dataset` build printed this, and in 0.34.0 it runs once:

  ```text
     Trigger: schedule_and_dataset
     Command: dbt build
     ❌ Unknown trigger type: schedule_and_dataset
     Supported types: manual, schedule
  ```

  ```text
     Trigger: schedule_and_dataset (manual apply override)
     Command: dbt build
     Iterations: 1
  ```
- The same product on two clouds needs a directory each (`<product>` with no env, `<product>__<env>` with one), so each [schedule sync](#pushing-dags-to-the-scheduler) mirrors only its own DAGs.

## Build graphs and dataset triggers

*(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* This whole section describes it. Builds that `builds[].dependencies` link run in one DAG, one `fluid apply --build-id` task per build, each after the builds it names. A build with a `dataset` or `schedule_and_dataset` trigger gets a DAG that runs when the datasets it names are updated. A task declares, as `outlets`, the assets of the exposes its build writes (see [Outlets](#outlets) for the exposes that name none), so one product's DAG can start another's.

### Example: ingest, transform, publish, then a second product

`sales.orders_daily` has three builds. Only `ingest` has a trigger. The other two name the build they run after:

```yaml
id: sales.orders_daily
builds:
  - id: ingest
    engine: duckdb
    execution:
      trigger:
        type: schedule
        cron: "0 2 * * *"
        timezone: Europe/Dublin
    outputs: [orders_raw]
  - id: transform
    engine: duckdb
    dependencies:
      - buildId: ingest
        condition: success
    outputs: [orders_clean]
  - id: publish
    engine: duckdb
    dependencies:
      - buildId: transform
        condition: success
    outputs: [orders_daily]
exposes:
  - exposeId: orders_daily
    binding:
      platform: aws
      format: parquet
      location:
        bucket: acme-lake
        path: gold/orders_daily/
        region: eu-west-1
  # orders_raw and orders_clean are S3 exposes in the same bucket
```

```bash
fluid generate schedule contract.fluid.yaml -o dags/sales.orders_daily
```

```text
Generated 1 files (airflow scheduler):

  dags/sales.orders_daily/ingest_dag.py
...
```

One file, named after `ingest`, the build that carries the trigger. Its DAG, trimmed:

```python
with DAG(
    dag_id='sales.orders_daily__ingest',
    description='fluid apply sales.orders_daily --build-id each of ingest, transform, publish',
    schedule=SCHEDULE,
    ...
) as dag:
    tasks = {}
    tasks['ingest'] = BashOperator(
        task_id='ingest',
        ...
        env={
            "FLUID_DAG_CONTRACT": CONTRACT_PATH,
            "FLUID_DAG_ENV": FLUID_ENV_NAME,
            "FLUID_DAG_BUILD_ID": 'ingest',
            "FLUID_DAG_CONTRACT_ENV": CONTRACT_ENV_NAMES,
        },
        ...
        outlets=[
            Asset('s3://acme-lake/raw/orders'),
        ],
    )
    tasks['transform'] = BashOperator(
        task_id='transform',
        ...
        trigger_rule='all_success',
        outlets=[
            Asset('s3://acme-lake/silver/orders_clean'),
        ],
    )
    tasks['publish'] = BashOperator(
        task_id='publish',
        ...
        trigger_rule='all_success',
        outlets=[
            Asset('s3://acme-lake/gold/orders_daily'),
        ],
    )

    tasks['ingest'] >> tasks['transform']
    tasks['transform'] >> tasks['publish']
```

A second product, `finance.revenue_daily`, runs when the `orders_daily` table is updated. Another product's expose is named by its asset URI, the one the DAG above declares in `outlets`:

```yaml
id: finance.revenue_daily
builds:
  - id: revenue
    engine: duckdb
    execution:
      trigger:
        type: dataset
        datasets:
          - s3://acme-lake/gold/orders_daily
    outputs: [revenue_daily]
```

```bash
fluid generate schedule contract.fluid.yaml -o dags/finance.revenue_daily
```

Its DAG, trimmed:

```python
DATASETS = [
    's3://acme-lake/gold/orders_daily',
]
...
with DAG(
    dag_id='finance.revenue_daily__revenue',
    description='fluid apply finance.revenue_daily --build-id revenue',
    schedule=[Asset(uri) for uri in DATASETS],
    ...
```

When the `publish` task succeeds, Airflow marks `s3://acme-lake/gold/orders_daily` as updated and starts the `revenue` DAG. The full contracts pass `fluid validate`, and the output above came from forge-cli `main`. With 0.32.0, the first contract writes only `ingest_dag.py`, a one-task DAG with no `outlets` (`transform` and `publish` have no trigger of their own, so they get no DAG), and the second stops with `No scheduler engine specified`.

### How linked builds share a DAG

- **One DAG per linked group.** Builds that depend on each other, in either direction, run in one DAG. A build that nothing links and that carries a trigger keeps its own DAG.
- **One trigger per DAG.** The DAG runs on the one trigger its builds declare, whichever build declares it. A build with no trigger of its own (or `trigger.type: dependency`) runs in the DAG of the builds it depends on. Builds of one group may repeat the same trigger.
- **Names.** The DAG id is `<product id>__<build id>`, or `<product id>__<env>__<build id>` with `--env`, and the file is `<build id>_dag.py`. Both are named after the build that carries the trigger (the first of them in `builds[]` when several builds of the group repeat it), and `BUILD_ID` in the file holds that build. In the file name, a character of the build id other than a letter, digit or `_` becomes `_`.
- **Task ids.** Each task's `task_id` is its build id, and its `FLUID_DAG_BUILD_ID` is the same value, so the task runs `fluid apply --build-id <build id>`. A DAG with one task keeps the task id `fluid_apply`.
- **Per task.** A task takes its `retries` from its own build's `execution.retries.maxAttempts`, and has its own execution timeout: three hours, plus the run's wait for a Spark build.

A dependency's `condition` becomes the task's Airflow trigger rule. A dependency with no condition is `success`.

| `condition` | Trigger rule | The task starts |
| --- | --- | --- |
| `success` | `all_success` | once the builds it names succeeded |
| `completion` | `all_done` | once they finished, whatever their outcome |
| `always` | `always` | at once, without waiting for them |

A dependency on a build that `fluid apply` keeps running, such as a Spark stream, is not waited for, and the DAG's own documentation says so:

```text
A build here depends on these, but no DAG runs them, so no task waits
for them: stream-raw (a Spark stream that fluid apply keeps running).
```

A contract whose only builds are such streams gets `No build needs a DAG` from `fluid generate schedule`, not `No scheduler engine specified`, and no file is written. *(since 0.34.0, [forge-cli #1018](https://github.com/Agenticstiger/forge-cli/pull/1018))* A stream that declares `execution.retries` is the exception on Airflow: it gets a keepalive DAG, and a contract of such streams writes a file. See [Keeping a stream running](#keeping-a-stream-running).

### Dataset triggers

| `trigger.type` | The DAG runs |
| --- | --- |
| `schedule` | on `trigger.cron` (or `trigger.schedule`) |
| `dataset` | when the datasets in `trigger.datasets` are updated |
| `schedule_and_dataset` | on its cron, and when those datasets are updated |

`trigger.datasets` lists the datasets. `datasetsOperator` is `all` (the default: every dataset has been updated since the DAG's last run) or `any` (one of them). `dataset` takes no cron. `schedule_and_dataset` needs one that recurs, so `@once` is refused. A dataset is one of:

- **An asset URI**, as a string. It is checked as Airflow checks it and written in the form Airflow stores: a lower-case scheme and no trailing slash after a path (a bare `s3://bucket` keeps its slash). A URI with user info, a query, a fragment, a space or a `{{ ... }}` or `${...}` placeholder is refused.
- **`{productId, exposeId}`** of an expose of this contract. The generator turns it into that expose's asset URI (see [Outlets](#outlets)). The `productId` must be this contract's id. For another product's expose, write the URI.

An `any` trigger on a cron renders like this (trimmed):

```python
schedule=asset_or_time_schedule(
    CronTriggerTimetable(SCHEDULE, timezone=TIMEZONE),
    AssetAny(*(Asset(uri) for uri in DATASETS)),
),
```

The files load on Airflow 2.6 and later, and on Airflow 3. On Airflow 2, a `datasetsOperator: any` or `schedule_and_dataset` trigger needs 2.9 or later. The generator does not render `event`, `manual` or `timetable` triggers: a build with one gets no DAG.

### Outlets

Each task declares the exposes its build writes as `outlets`, so Airflow starts a DAG scheduled on one of them when the task succeeds, in this product's DAGs or another's. A build writes the exposes in its `outputs`. A build with no `outputs` counts as writing every expose that no build lists.

An expose is named by the URI that Airflow's own providers use for the same storage, built from its `binding`:

| `binding.platform` | Asset URI |
| --- | --- |
| `aws` with `location.bucket` | `s3://<bucket>/<path>` (with no `path`, `<database>/<table>` under the bucket) |
| `gcp` with `location.project`, `dataset` and `table` | `bigquery://<project>/<dataset>/<table>` |
| `gcp` with `location.bucket` | `gs://<bucket>/<path>` |
| `snowflake` | `snowflake://<account>/<database>/<schema>/<table>` |
| `databricks` with `location.host` | `databricks://<host>/<database>/<schema>/<table>` |
| `postgres`, `pgvector` | `postgres://<host>:<port>/<database>/<schema>/<table>` (port 5432 when none is given) |
| `kafka`, `confluent` | `kafka://<first bootstrap server>/<topic>` |
| `local` with an absolute `location.path` | `file://` and the path: `/data/out/x.parquet` gives `file:///data/out/x.parquet` |

An expose gets no outlet when its URI cannot be fixed at generation: a relative `local` path (the project directory is somewhere else on each worker), a value filled in on the worker (`{{ env.X }}`, `${X}`), a missing location field, or a platform not in the table. The task is generated without it.

A one-build DAG you generated before gains the `Asset` import and an `outlets=` list when its build writes an expose that has an asset URI, and nothing else. When none of them has one, the file does not change. A DAG that gains them:

```python
try:  # Airflow 3
    from airflow.sdk import Asset
except ImportError:  # Airflow 2.x
    from airflow.datasets import Dataset as Asset
...
        outlets=[
            Asset('s3://lake/iceberg/curated/events_daily'),
        ],
```

### Errors that stop generation

Each of these stops `fluid generate schedule` with `generate_schedule_invalid_schedule` and exit code 2, and the message says what to change:

- a cycle in `builds[].dependencies`;
- a dependency on the build itself, or on no build;
- two different triggers in one linked group;
- two conditions among one build's dependencies, because Airflow gives a task one trigger rule;
- a dependency on a build that another engine runs (its `execution.orchestration.engine` names another engine, or `none`);
- a DAG that its own output would trigger, or two or more DAGs that trigger each other through their outputs;
- a dataset Airflow would refuse, or a `{productId, exposeId}` that names another product or an expose the contract does not declare.

Two messages (trimmed):

```text
generate_schedule_invalid_schedule: {'error': "builds[].dependencies form a cycle: 'ingest' -> 'transform' -> 'publish' -> 'ingest' (each runs after the one before it), so none of them could ever start. Remove one of these dependencies"}
```

```text
generate_schedule_invalid_schedule: {'error': "builds 'ingest' and 'publish' are linked by builds[].dependencies, so they run in one DAG, but their triggers differ (schedule '0 2 * * *' (Europe/Dublin) vs schedule '0 5 * * *' (UTC)). One DAG runs on one trigger: keep it on one build and remove the other's, or drop the dependency and give 'publish' a dataset trigger on what 'ingest' writes"}
```

Both came from forge-cli `main`, the first with `publish` made a dependency of `ingest`, the second with a second cron on `publish`.

### Regenerating

With `--overwrite`, `fluid generate schedule` also removes the DAG files an earlier run wrote into the output directory for the same product and env that the contract no longer makes. A build that now runs as a task of another build's DAG would otherwise run twice. Regenerating over the three one-build DAGs that 0.32.0 wrote when each build had a cron trigger of its own prints (from forge-cli `main`):

```text
Removed dags/sales.orders_daily/publish_dag.py: an earlier run wrote it for this product and env, and the contract no longer makes that DAG.
Removed dags/sales.orders_daily/transform_dag.py: an earlier run wrote it for this product and env, and the contract no longer makes that DAG.
```

Only a `.py` file that opens with the generated DAG's docstring and sets the same `PRODUCT_ID` and `FLUID_ENV_NAME` is removed.

`fluid validate` warns about an Airflow task's `buildStepRef` under `orchestration`: it names a `transformations[]` step, and no generated DAG runs one. To run a build after another, list it in `builds[].dependencies`.

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

*(since 0.37.0)* Add `--airflow-url` and the push waits until Airflow (2 or 3) has parsed every pushed file, and fails the stage on an import error. See [Waiting for Airflow to parse the files](../cli/schedule-sync.md#waiting-for-airflow-to-parse-the-files-since-0-37-0).

## Alerts

The DAGs forge generates can alert on a failure, a retry, a success and a missed SLA, through Airflow's own notifiers. The contract declares the routes in a top-level `alerts` block (contract 0.7.7 preview). *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

```yaml
fluidVersion: "0.7.7"
alerts:
  sla: PT2H                # an ISO duration, at most P30D; a route on sla_miss needs it
  routes:
    - name: oncall-email
      kind: email
      connection: smtp_default
      to: [data-oncall@example.org]
      events: [failure, retry]
    - name: team-slack
      kind: slack
      connection: slack_data_alerts
      events: [failure, success]
    - name: opsgenie
      kind: webhook
      format: opsgenie
      connection: opsgenie_alerts
      events: [failure, sla_miss, success]
```

Run [`fluid generate schedule`](../cli/generate.md) or [`fluid generate artifacts`](../cli/generate-artifacts.md) as usual. The DAG files carry the alerts. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

### Routes

- A route has a `name` (letters, digits, `_` and `-`, at most 64, unique in the contract) and a `kind`. `connection` is the id of the Airflow connection that holds the address, URL or key. It is required for `webhook` and for a plugin kind that asks for one. `email`, `slack` and `pagerduty` use `smtp_default`, `slack_default` and `pagerduty_events_default` when it is left out. A key a route does not read is refused. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `events` is a list of distinct events and picks what the route sends: `failure` (the default: a task failed for good), `retry` (a task failed and will retry), `success` (the run succeeded) and `sla_miss`. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `alerts.sla` is the SLA: an ISO 8601 duration from `PT1S` to `P30D`, in weeks, days, hours, minutes and seconds (`PT4H`, `P1DT6H`), never months or years. A route that names `sla_miss` without it is refused. An `alerts.sla` that no route uses for `sla_miss` is a warning. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `severity` is `critical`, `error`, `warning` or `info`. Without it a `failure` alerts as `critical` and a `retry` or `sla_miss` as `warning`; a `success` is always `info`. Each service gets it in its own terms (PagerDuty's severity, Zenduty's `alert_type`, Opsgenie's `priority` from P1 to P5). `options` passes settings to a plugin kind, and the built-in kinds refuse it. `to` and `from` belong to `email` routes and `format` to `webhook` routes. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `alerts.defaults: false` leaves out the routes an organisation's pack adds to every product (see [Extending alerts](#extending-alerts)). A contract replaces such a route by giving a route the same `name`. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- A product may have at most 20 routes, its own and the pack's defaults together. More is refused at `fluid validate` and when the DAG is rendered, not cut to 20. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

### Kinds and their connections

- `email` uses Airflow's `SmtpNotifier`. `to` is required: a list of one to 50 addresses. Set `from` if the connection's default sender is not what you want. The connection is an SMTP connection. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `slack` uses `SlackWebhookNotifier`. The connection is a Slack incoming-webhook connection: it holds the webhook, and so fixes the channel. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `webhook` uses `HttpNotifier` and needs the Airflow `http` provider 5.5.0 or newer. `format` picks the body. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
  - `generic` (the default) sends forge's own JSON. The connection's host is the whole URL. A header the service wants, such as a key, goes in the connection's extra, which Airflow sends as request headers. If the URL itself holds a key, put it in the connection's password too: Airflow's secrets masker does not hide a host, and a failed delivery can quote the URL. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
  - `zenduty` sends a Generic Integration event. Set the integration URL as the HTTP connection's host. `success` sends `alert_type: resolved`. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
  - `opsgenie` sends an Alert API request. Set the alerts URL as the host, and put `{"Authorization": "GenieKey <key>"}` in the connection's extra, which Airflow sends as headers. `success` closes the alert by its alias. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `pagerduty` uses `PagerdutyNotifier`. The connection holds the routing key. It is its own kind because Events API v2 puts the routing key in the request body, and a generic webhook would have written it into the DAG. `success` resolves the incident. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `success` resolves the incident in Zenduty, Opsgenie and PagerDuty. One dedup key is used per DAG. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- A plugin adds more kinds (see [Extending alerts](#extending-alerts)). *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

Install the provider each kind needs on the Airflow side. The floors are `smtp` 1.2.0, `slack` 8.1.0, `pagerduty` 3.3.0 and `http` 5.5.0. For an `sla_miss` alert on Airflow 3.1 and newer, which runs the notifier in the triggerer, the floors are `smtp` 2.3.0, `slack` 9.2.0, `pagerduty` 5.1.0 and `http` 5.5.0. The DAG's documentation lists what its routes need. An import error from a missing provider shows up in the [parse check](#pushing-dags-to-the-scheduler) of `fluid schedule-sync`. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

### What each Airflow version does

- `failure`, `retry` and `success` work on Airflow 2 and 3. A `failure` or `retry` alert names the task and carries the run id, the try number and the log URL, from Airflow's own context. A `success` alert carries the run id. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `sla_miss` on Airflow 2.7 and newer sets every task's `sla`, measured from the end of the run's data interval, and the DAG's `sla_miss_callback`. Airflow 2.6 gets no SLA wiring, because its notifiers cannot take the callback's arguments. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- `sla_miss` on Airflow 3.1 and newer, which has no SLAs, adds a `DeadlineAlert` per route that fires `alerts.sla` after the run was queued. Its callback runs the notifier in the triggerer. Airflow's deadline API is experimental, so the DAG builds it inside a `try`: if a later Airflow changes it, the DAG loses its deadline alerts and still imports. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- Airflow 3.0 has neither SLAs nor deadlines, so a missed SLA alerts no one there. The DAG's documentation says so. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- A plugin kind whose notifier has no `async_notify` cannot run in the triggerer, so its `sla_miss` route alerts on Airflow 2 only. `fluid validate` warns about it. The built-in kinds all have it. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

### No secret in a contract or a DAG

A route never holds a secret. The secret stays in the Airflow connection, which your secrets backend can serve. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

- `connection` takes only the characters of an Airflow connection id. A URL, an address with a password, or a key-shaped value (a long hex string, a UUID, a random token) is refused at `fluid validate` and when the DAG is rendered. The value is not shown in the message. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- Every string a route gives holds no `{` or `}` (Airflow renders notifier fields as templates), no URL, and nothing the redactor masks. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- A plugin route's option named like a secret (`api_key`, `password`, `routingKey`) is refused whatever its value. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- Both redaction layers mask Zenduty and PagerDuty integration URLs, Opsgenie `GenieKey` values and `routing_key` / `integration_key`, in case one reaches a log. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

### Extending alerts

- An organisation's pack adds default routes to every product through the `fluid_build.alert_defaults` entry point group. A contract replaces one by its `name`, or leaves them all out with `alerts.defaults: false`. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- A package adds a route kind through the `fluid_build.alert_notifiers` entry point group. The kind is a subclass of `fluid_build.alerts.AlertNotifier`, or any object with its attributes, so a pack needs no forge import. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- A kind is read by name and loaded only when a route names it. `FLUID_PLUGINS_ALLOWLIST` and `FLUID_PLUGINS_BLOCKLIST` apply before the import. A built-in kind name is reserved, and two distributions of one name are both refused. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- A kind that is missing or fails refuses the route (the message names only the exception type). It never drops the route silently. An installed pack the allow or block policy leaves out is named. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- [`fluid plugins`](../cli/plugins.md) lists both groups without importing them. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

### Checks and limits

- `fluid validate` runs `contract_alerts`, and in its plugin phase `contract_alert_plugins`, so a contract that passes renders. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- A contract without routes renders the same DAG as before. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*
- The acquisition DAGs that [`fluid schedule-sync`](../cli/schedule-sync.md) writes carry no alerts, and the run warns about it. *On forge-cli `main`, not yet in a release ([forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056)).*

## MWAA on AWS

*([forge-cli #715](https://github.com/Agenticstiger/forge-cli/pull/715), since 0.20.0)* `fluid apply` does not create an Amazon MWAA environment. Create the environment yourself, in your own VPC, or use one you already run, and push the DAGs to the S3 folder it reads. Schedule the builds with `builds[].execution.trigger`, and leave `orchestration.schedule` out:

```yaml
orchestration:
  engine: airflow
builds:
  - id: load_orders
    execution:
      trigger:
        type: schedule
        cron: "0 6 * * *"
```

```bash
fluid generate schedule contract.fluid.yaml -o dags/sales_orders_daily
fluid schedule-sync --scheduler mwaa --dags-dir dags --destination s3://acme-airflow-dags/dags/ --dry-run
```

```text
[schedule-sync] scheduler=mwaa dags-dir=.../dags env=dev delete-scope=product dry-run=True
[schedule-sync] → /usr/local/bin/aws s3 sync .../dags/sales_orders_daily/ s3://acme-airflow-dags/dags/sales_orders_daily/ --delete
[schedule-sync] ✔ mwaa sync complete (1 subprocess(es))
```

Drop `--dry-run` to push. `--destination` is the S3 folder the environment reads its DAGs from, in its source bucket. Each scheduled run executes `fluid apply` on the MWAA worker, which needs what [What the DAG does](#what-the-dag-does) lists.

An `aws` contract that keeps `orchestration.schedule` with `orchestration.engine: airflow` asks `fluid apply` for the environment itself, and is refused with `unsupported_binding`, kind `mwaa-environment-not-emitted`, before anything is applied; see [Scheduling on AWS](../providers/aws.md#scheduling-on-aws). Before this change the apply reported success and no environment existed. The refusal's own next step names `fluid generate schedule --scheduler airflow --output dags/<contract id>` and `fluid schedule-sync --scheduler mwaa --dags-dir dags`, the product-scoped layout above, so the two commands run as printed.

## `fluid generate-airflow` (deprecated)

*(since 0.31.0, [forge-cli #923](https://github.com/Agenticstiger/forge-cli/pull/923))* `fluid generate-airflow` is an alias of `fluid generate schedule --scheduler airflow`, and one renderer writes both. What changed is on [its page](../cli/generate-airflow.md#what-it-writes). The notes below describe 0.30.1 and earlier.

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

## Scheduled Spark builds

*(since 0.31.0, [forge-cli #950](https://github.com/Agenticstiger/forge-cli/pull/950))* A build of `engine: spark` (its `parameters.spark` lives under `builds[].properties`) whose run ends on its own, a batch job or a stream with `trigger.availableNow`, gets the standard `fluid apply` DAG, like every scheduled build. Its one task, `fluid_apply`, runs:

```text
fluid apply <contract> --mode amend-and-build --build-id <id> --yes
```

The build phase of that apply starts one run on EMR Serverless, Glue, EMR on EC2 or EMR on EKS, waits for it, and fails unless the run succeeded, so the task fails when the run does. Ctrl-C, SIGTERM or SIGHUP cancel the run. The task goes through the same hardened `env -i` script as every `fluid apply` DAG.

- **Timeouts.** `execution.runtime.timeout`, an ISO-8601 duration such as `PT2H`, is how long the run may take; six hours when unset. The task's timeout is the three hours every apply DAG gets plus that wait. A value that is not a duration of at least one second is refused before `tofu apply` changes anything (`apply_spark_invalid`).
- **Retries** come from `execution.retries.maxAttempts`, as for every scheduled build.
- **A streaming build gets no DAG**, unless its `properties.stream.trigger` is `availableNow: true`. A stream runs continuously, and `fluid apply` keeps it running. *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* A scheduler task can keep a stream running between applies: it runs `fluid apply <contract> --mode reconcile --build-id <stream> --yes` every few minutes, and starts the stream again when it died, within its restart budget. See [Reconcile mode](../cli/apply.md#reconcile-mode). *(since 0.34.0, [forge-cli #1018](https://github.com/Agenticstiger/forge-cli/pull/1018))* `fluid generate schedule` writes that task, as a keepalive DAG, for a stream that declares `execution.retries`: see [Keeping a stream running](#keeping-a-stream-running). A build is a stream when `parameters.spark.mode` says so, or when it declares `properties.stream` and sets no mode. *(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* A build that depends on a stream does not wait for it; see [Build graphs and dataset triggers](#build-graphs-and-dataset-triggers).
- **The worker runs the whole apply**, `tofu` included, so it needs the apply's permissions and the state backend, as for any scheduled build, plus `fluid` with boto3 (`data-product-forge[aws]` in MWAA's `requirements.txt`). The scheduler policy forge emits for a Spark product covers the run only. The operator settings (`FLUID_SPARK_*`) and the run's AWS actions are the ones [Spark to Iceberg on AWS](./spark-iceberg-aws.md#the-caller-s-permissions) lists.
- A build that is not Spark gets the standard DAG, as before. A contract of dbt and Spark builds gets a DAG for each scheduled build. *(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))* Builds that `builds[].dependencies` link share one DAG instead (see [Build graphs and dataset triggers](#build-graphs-and-dataset-triggers)).

### Keeping a stream running

*(since 0.34.0, [forge-cli #1018](https://github.com/Agenticstiger/forge-cli/pull/1018))* A forge Spark stream that declares `execution.retries` gets a small DAG of its own, a keepalive. Its one task runs [`fluid apply --mode reconcile`](../cli/apply.md#reconcile-mode) every few minutes, so a stream that a Spot interruption or a failed driver stopped starts again on its checkpoint, within the restart budget that `execution.retries` sets.

- **Who gets one.** A Spark stream (a build with `properties.stream`) that is not `trigger.availableNow` and not `trigger.type: continuous`, and declares `execution.retries` as an object such as `{maxAttempts: 5}`, on Airflow, the default engine. It is opt-in: a stream without `execution.retries` gets no DAG, although `--mode reconcile` would restart it too (5 restarts per rolling hour when unset). A contract whose only builds are such streams gets this DAG, and no longer `No build needs a DAG`. Prefect, Dagster and [`fluid scaffold-composer`](../cli/scaffold-composer.md) write nothing for a stream, and their messages point at the Airflow keepalive (`--scheduler airflow`, or `fluid generate schedule`). A batch that depends on the stream does not wait for it: the stream is in no build graph. With no `orchestration.engine` in the contract, such a stream makes Airflow the default, as a build with a cron trigger does, and `fluid generate artifacts` (stage 3 of a pipeline) writes its DAG under `schedule/`.
- **What the DAG is.** A file `<build>_dag.py`, with the `-` of the build id as `_`. Its DAG id is `<product>[__<env>]__<build>`, and its one task is `fluid_keepalive`. The task runs, with the same `env -i` script and environment allowlist as every `fluid apply` task:

  ```text
  cd "$FLUID_PROJECT_DIR"
  fluid apply "$FLUID_PROJECT_DIR/$CONTRACT_PATH" --env "$FLUID_ENV_NAME" --mode reconcile --build-id "$BUILD_ID" --yes
  ```

  `--env` is left out when `FLUID_ENV_NAME` is empty.
- **Schedule and limits.** It runs every 5 minutes, `*/5 * * * *`, or on the build's `execution.orchestration.airflow.dagConfig.schedule`, which is validated like any DAG's cron. `@once` is refused, because a keepalive has to recur. It runs one run at a time (`max_active_runs=1`), with no catch-up, no Airflow retries and a 30-minute task timeout. The build's `execution.retries` is the restart budget (`maxAttempts` restarts per rolling hour, 5 when unset, at most 10), and `--mode reconcile` applies it. Each wait inside a run is bounded by [`FLUID_SPARK_WAIT_SECONDS`](./environment-variables.md#spark-on-aws-preview), 900 seconds by default.
- **No outlets.** A stream updates its tables all the time, and an asset event every 5 minutes would start every DAG scheduled on them. A dataset trigger on an expose that only the stream writes is refused, as before.
- **What a run does.** A healthy stream is a no-op. A stream that died starts again on its checkpoint. A run succeeds (exit `0`) when the stream is unchanged, restarted and still running, left stopped because it was cancelled on purpose, or there is nothing to reconcile. It fails (exit `1`, which Airflow's alerting picks up) when the stream drifted from the contract, nothing is deployed, the job config the last apply deployed cannot be read, the restarts are spent, EMR Serverless's or EMR on EKS's own retries are spent, the EMR on EC2 cluster ended, the restarted run ends at once, or an AWS call fails (a missing permission, say). Where forge restarts (EMR on EC2, Glue and a local build), a spent budget is not final: once the oldest restart is an hour old, the next run restarts the stream, and the runs before it fail.
- **Stopping it.** A stream cancelled on purpose stays stopped: `--mode reconcile` leaves a cancelled run alone. `fluid apply` starts it again.
- **The worker.** It needs the settings and the forge release that the CI apply has: the `FLUID_SPARK_*` operator settings (a missing allowlist refuses the build, and a setting that changes the compiled config reads as drift), and the role of the product's `fluid-<product>-spark-caller` policy, which lets it read the stream's job config and runner, and, on EMR on EC2, read the cluster and the step role. See [The caller's permissions](./spark-iceberg-aws.md#the-caller-s-permissions).

For a stream with `execution.retries` and no other build, on Airflow:

```text
Generated 1 files (airflow scheduler):

  dags/ingest_orders_dag.py

Tip: To regenerate after editing the contract: fluid generate schedule
```

The DAG's docstring says what a run does:

```text
Every run reconciles one always-on stream on the Airflow worker, with the
constants below filled in (`--env` is left out when FLUID_ENV_NAME is empty):

    cd "$FLUID_PROJECT_DIR"
    fluid apply "$FLUID_PROJECT_DIR/$CONTRACT_PATH" --env "$FLUID_ENV_NAME" \
        --mode reconcile --build-id "$BUILD_ID" --yes

It runs no tofu apply. When the stream died (a Spot interruption, a failed
driver), it starts again on its checkpoint, within the restart budget the
build's execution.retries sets, so the task itself never retries. The run
fails when the stream cannot be kept running: it drifted from the contract,
nothing is deployed, the job config the last apply deployed cannot be read,
its cluster ended, or the restarts are spent. It can also fail when this
worker's FLUID_SPARK_* settings or forge release differ from the CI apply's.
A run cancelled on purpose stays stopped until fluid apply starts it. It
runs on SCHEDULE, one run at a time, with no catch-up. The build's
execution.orchestration.airflow.dagConfig.schedule sets SCHEDULE.
```

With `--scheduler prefect` or `--scheduler dagster`, the same contract writes nothing:

```text
No build needs a DAG: every build runs outside forge-cli (a Flink job, for example), as a stream that fluid apply keeps running, or continuously (trigger.type: continuous), so there is nothing to schedule. No files written.
A stream that declares execution.retries gets a keepalive DAG on Airflow: fluid generate schedule --scheduler airflow.
```

`fluid scaffold-composer`, which writes a Cloud Composer DAG, writes nothing for it either:

```text
Every build runs outside forge-cli (a Flink job, for example), as a stream that
fluid apply keeps running, or continuously (trigger.type: continuous), so there
is nothing to schedule. No DAG written.
A stream that declares execution.retries gets a keepalive DAG from fluid
generate schedule, which restarts it when it stops.
```

`@once` as the schedule is refused:

```text
generate_schedule_invalid_schedule: {'error': "'ingest-orders': execution.orchestration.airflow.dagConfig.schedule: a keepalive DAG reconciles the stream on a recurring cron, and @once is not one"}
```

These outputs are from the real `fluid generate schedule` and `fluid scaffold-composer` on `main`, on the example stream with `execution: {retries: {maxAttempts: 5}}` added; the DAG file's constants are `SCHEDULE = '*/5 * * * *'`, `RETRIES = 0` and a task timeout of 1800 seconds. No Airflow ran here: forge-cli's own tests load the DAG in a real Airflow 2 and Airflow 3 when one is named.

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

If the file imports, Airflow can load it. *(since 0.37.0)* Every DAG forge generates is also loaded by a real Airflow 2 and a real Airflow 3 in a gated test. Running it needs `FLUID_PROJECT_DIR` and the `fluid` CLI on the machine that runs the Airflow worker.

## See also

- [Declarative Airflow Walkthrough](../walkthrough/airflow-declarative.md): a build-by-build tour
- [Operating in CI](./operating-in-ci.md): stage 11 and `schedule-sync` in a pipeline
- [`fluid generate`](../cli/generate.md): the `generate` subcommands
- [GCP walkthrough](../walkthrough/gcp.md): Cloud Composer, end to end
