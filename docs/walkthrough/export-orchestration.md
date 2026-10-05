# Generating Orchestration Code from Contracts

**Docs baseline:** CLI `0.18.1`

`fluid export` reads the tasks you declare under `orchestration` in a contract and writes orchestration code for Airflow, Dagster or Prefect. This page exports the same kind of contract for AWS, GCP and Snowflake, shows what comes out, and lists what the generated code does not do. Everything here was run on 0.18.1; paths are shortened to `...`.

::: tip Running a build on a schedule is a different job
To run a contract's own build on a cron schedule, declare the schedule on the build and let FLUID generate a DAG that runs `fluid apply`: see [Declarative Airflow](./airflow-declarative.md). `fluid export` is for contracts that describe cloud steps as `orchestration.tasks`, and what it writes is a skeleton you review and extend.
:::

## 1. Write the contract

The exporters read two keys under `orchestration`: `schedule` and `tasks`. The schema also requires `engine` (`airflow`, `dagster`, `prefect`, `kubeflow`, `custom` or `none`), and the contract needs at least one expose. This one declares three AWS steps:

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: aws.sales_analytics_v1
name: Sales Analytics
domain: Sales
metadata:
  layer: Gold
  owner:
    team: sales-data
    email: sales-data@example.com
exposes:
  - exposeId: transactions
    kind: table
    binding:
      platform: aws
      format: parquet
      location:
        bucket: sales-analytics-data
        path: transactions/
        region: us-east-1
    contract:
      schema:
        - {name: transaction_id, type: STRING}
        - {name: amount, type: DECIMAL}
orchestration:
  engine: dagster
  schedule: "0 */6 * * *"
  tasks:
    - taskId: create_bucket
      type: provider_action
      action: aws.s3.ensure_bucket
      params:
        bucket: sales-analytics-data
    - taskId: create_database
      type: provider_action
      action: aws.glue.ensure_database
      dependsOn: [create_bucket]
      params:
        database: sales
    - taskId: refresh_summary
      type: provider_action
      action: aws.athena.execute_query
      dependsOn: [create_database]
      params:
        database: sales
        query: SELECT count(*) FROM transactions
```

A task is `taskId`, `type: provider_action`, an `action`, `params`, and `dependsOn` for ordering. Only `provider_action` tasks become code. Write the action as `<provider>.<service>.<operation>`, for example `aws.s3.ensure_bucket`. With two parts (`s3.ensure_bucket`) the AWS Dagster exporter produces an op that logs the action and does nothing else, because it takes the service from the second part.

## 2. Export

```bash
fluid --project 123456789012 --region us-east-1 export aws-sales.fluid.yaml --engine dagster -o pipelines/
```

```text
{"event": "provider_initialized", "provider": "aws", "account_id": "123456789012", "region": "us-east-1"}
{"event": "export_started", "contract_id": "aws.sales_analytics_v1", "engine": "dagster", "output_dir": "pipelines"}
{"event": "export_completed", "contract_id": "aws.sales_analytics_v1", "engine": "dagster", "output_file": "pipelines/aws.sales_analytics_v1_pipeline.py", "code_lines": 180}
```

- `--engine` is `airflow` (the default), `mwaa`, `dagster` or `prefect`. `-o` is the output directory.
- The AWS exporter takes the account and region from the global `--project` and `--region`, not from the binding. Without them it reads `AWS_ACCOUNT_ID`, then asks STS who you are with your credentials, and uses `FLUID_REGION` or `europe-west3` as the region. In 0.18.1 that default is written into the generated file even for an AWS contract.
- The contract has no provider field, so `--provider` defaults to `aws`. Pass `--provider gcp` or `--provider snowflake` for those contracts. Without it, a GCP contract exported with the AWS provider writes a DAG of Amazon operators and exits 0.

## 3. AWS and Dagster

The generated file declares one resource per AWS service and one op per task, ordered so each op comes after the ops it depends on:

```python
# Task Ops

@op(
    required_resource_keys={"aws_s3_resource"},
)
def create_bucket(context):
    """Execute aws.s3.ensure_bucket."""
    logger.info('Executing: aws.s3.ensure_bucket')
    params = json.loads('{"bucket": "sales-analytics-data"}')

    # Execute provider action
    s3_client = context.resources.aws_s3_resource
    bucket = params.get("bucket")
    if bucket:
        s3_client.create_bucket(Bucket=bucket)
        logger.info(f"Created S3 bucket: {bucket}")

    return {"status": "success", "task_id": 'create_bucket'}

@op(
    ins={"dep_create_bucket": In(Nothing)},
    required_resource_keys={"aws_glue_resource"},
)
def create_database(context):
    """Execute aws.glue.ensure_database."""
    logger.info('Executing: aws.glue.ensure_database')
    params = json.loads('{"database": "sales"}')

    # Execute provider action
    glue_client = context.resources.aws_glue_resource
    database = params.get("database")
    if database:
        try:
            glue_client.create_database(DatabaseInput={'Name': database})
            logger.info(f"Created Glue database: {database}")
        except glue_client.exceptions.AlreadyExistsException:
            logger.info(f"Database already exists: {database}")

    return {"status": "success", "task_id": 'create_database'}

# ... the refresh_summary op follows the same pattern, with ins={"dep_create_database": In(Nothing)}
```

```python
@job(
    resource_defs={
        "aws_s3_resource": aws_s3_resource,
        "aws_glue_resource": aws_glue_resource,
        "aws_athena_resource": aws_athena_resource,
        "aws_lambda_resource": aws_lambda_resource,
    },
    description='Sales Analytics',
)
def aws_sales_analytics_v1_job():
    """Sales Analytics workflow."""
    create_bucket_result = create_bucket()
    create_database_result = create_database(dep_create_bucket=create_bucket_result)
    refresh_summary_result = refresh_summary(dep_create_database=create_database_result)
```

- A dependency is `ins={"dep_<task>": In(Nothing)}` on the op and a keyword argument at the call site.
- Task ids that collide after being made into Python names get `_2`, `_3` suffixes, and contract values reach the file through string-literal escaping.
- Ops for `aws.s3.*`, `aws.glue.*`, `aws.athena.*` and `aws.lambda.*` actions call boto3 with the task's `params`. Any other action logs `Action: ...` and `Params: ...` and returns success. Read the ops before you schedule them. The Glue op creates the database and treats an existing one as success.

The file ends with a `ScheduleDefinition` from the contract's `schedule` and a `@repository`.

## 4. GCP and Airflow

```yaml
orchestration:
  engine: airflow
  schedule: "@daily"
  tasks:
    - taskId: create_dataset
      type: provider_action
      action: gcp.bigquery.create_dataset
      params:
        dataset_id: analytics
        location: US
    - taskId: create_table
      type: provider_action
      action: gcp.bigquery.create_table
      dependsOn: [create_dataset]
      params:
        dataset_id: analytics
        table_id: customers
        schema:
          - {name: customer_id, type: INTEGER}
          - {name: name, type: STRING}
    - taskId: load_data
      type: provider_action
      action: gcp.bigquery.query
      dependsOn: [create_table]
      params:
        query: INSERT INTO analytics.customers SELECT * FROM raw.customer_data WHERE date = CURRENT_DATE()
```

```bash
fluid --project my-project-id --region us-central1 export gcp-analytics.fluid.yaml --provider gcp --engine airflow -o dags/
```

```python
# Task definitions
create_dataset = BigQueryCreateEmptyDatasetOperator(
    task_id='create_dataset',
    dataset_id='analytics',
    project_id='my-project-id',
    location='US',
    dag=dag,
)

create_table = BigQueryCreateEmptyTableOperator(
    task_id='create_table',
    dataset_id='analytics',
    table_id='customers',
    project_id='my-project-id',
    schema_fields=[{'name': 'customer_id', 'type': 'INTEGER'}, {'name': 'name', 'type': 'STRING'}],
    dag=dag,
)

load_data = BigQueryInsertJobOperator(
    task_id='load_data',
    configuration={'query': {'query': 'INSERT INTO analytics.customers SELECT * FROM raw.customer_data WHERE date = CURRENT_DATE()', 'useLegacySql': False}},
    project_id='my-project-id',
    location='us-central1',
    dag=dag,
)

# Task dependencies
create_dataset >> create_table
create_table >> load_data
```

The GCP exporter reads `dataset_id` and `table_id` from `params` (not `dataset` and `table`); a missing key falls back to `unknown_dataset` or `unknown_table`. It maps `gcp.bigquery.create_dataset`, `create_table` and `query`, plus the Cloud Storage, Pub/Sub and Dataflow services; other actions become `PythonOperator` tasks. The imports are the `apache-airflow-providers-google` operators.

## 5. Snowflake and Prefect

```bash
fluid export sf-inventory.fluid.yaml --provider snowflake --engine prefect -o flows/
```

```python
# Prefect Tasks
@task(retries=3, retry_delay_seconds=30, timeout_seconds=1800)
def create_schema():
    """Execute Snowflake query"""
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('CREATE SCHEMA IF NOT EXISTS INVENTORY')
        results = cursor.fetchall()
        logger.info(f"Query executed: {{len(results)}} rows")
        return len(results)
    finally:
        cursor.close()
        conn.close()

```

```python
# Flow definition
@flow(
    name='snowflake_inventory_analytics_v1',
    description='Inventory Analytics',
    retries=1,
    retry_delay_seconds=60,
)
def snowflake_inventory_analytics_v1_flow():
    """Inventory Analytics flow on Snowflake."""
    create_schema_result = create_schema()
    create_table_result = create_table()
    load_data_result = load_data()

    logger.info("Flow completed successfully")
    return True
```

The Snowflake exporter generates a real task only for `query` and `run_query` actions, reading `params.query` (or `sql`). It takes credentials from the Prefect `Secret` blocks `snowflake-user` and `snowflake-password`.

## What the exports do not do (0.18.1)

- **Dependencies.** The Snowflake Prefect flow calls the tasks in the order the contract lists them and does not use `dependsOn`: the flow body above has no `wait_for`. The AWS exports for all three engines and the GCP Airflow export wire dependencies.
- **Prefect deployment block.** The `if __name__ == "__main__":` block of the AWS and Snowflake Prefect flows calls `cprint`, and the Snowflake one also `success`; the files import neither, so running the file raises `NameError` after `deployment.apply()`.
- **Schedule presets in the AWS Prefect exporter.** It does not know the `@`-prefixed presets, so `@hourly` becomes `0 2 * * *`. Write a cron expression.
- **Airflow tasks it cannot map.** The AWS Airflow export defines `_execute_provider_action`, which raises: provider-action tasks are retired in favour of provisioning with `fluid apply`.
- **Parameter names.** Each provider reads its own `params` keys, as sections 3 to 5 show; the GCP exporter falls back to `unknown_dataset` and `unknown_table` instead of failing.

## Schedules

The AWS exporter wrote these schedules for the same contract on 0.18.1:

| `orchestration.schedule` | Airflow | Dagster | Prefect |
| --- | --- | --- | --- |
| `@hourly` | `@hourly` | `0 * * * *` | `0 2 * * *` |
| `@daily` | `@daily` | `0 0 * * *` | `0 2 * * *` |
| `@weekly` | `@weekly` | `0 0 * * 0` | `0 2 * * *` |
| `0 6 * * 1` | `0 6 * * 1` | `0 6 * * 1` | `0 6 * * 1` |

## Validation

The export stops on a contract it cannot export, with exit 1:

```text
{"time": "2026-10-05T01:17:56Z", "level": "ERROR", "name": "fluid.cli", "message": "\u274c missing_orchestration: {'message': 'Contract missing orchestration section - cannot export DAG', 'hint': 'Add orchestration.tasks to your contract'}"}
```

```text
{"time": "2026-10-05T01:17:58Z", "level": "ERROR", "name": "fluid.cli", "message": "\u274c Error exporting orchestration code: Circular dependencies detected in tasks: task_a, task_b"}
```

## Keep the files current

Generate in CI and check the result compiles. `fluid export` takes one contract per call.

```bash
fluid export contracts/sales.fluid.yaml --engine airflow -o dags/
python -m py_compile dags/*.py
```

With `--verbose`, `fluid export` prints the packages the generated code needs: `apache-airflow-providers-amazon` for Airflow on AWS, `dagster` and `dagster-aws` for Dagster, `prefect` and `prefect-aws` for Prefect. An `ImportError` for an `airflow.providers` module means the matching provider package is not installed on the Airflow image; the GCP DAG needs `apache-airflow-providers-google`.

## Related

- [Declarative Airflow](./airflow-declarative.md): DAGs that run `fluid apply` on a schedule
- [`fluid export`](../cli/export.md)
- [GCP walkthrough](./gcp.md) and [Jenkins CI/CD](./jenkins-cicd.md)
