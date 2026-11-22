---
title: Importing existing pipelines
description: Propose FLUID data products from PySpark jobs and Airflow DAGs that already run, with a conventions file that describes your layout, a report of what could not be read, and importer plugins for other tools.
---

# Importing existing pipelines

*(since 0.37.0)* `fluid import pyspark` and `fluid import airflow` read the code of pipelines that already run and propose FLUID contracts for them. They read files and nothing else. Nothing is imported, no job runs, Airflow is never loaded, and no network call is made unless you ask for one with `--registry`.

This page is the guide. The [`fluid import`](../cli/import.md) page has the command syntax and every flag.

## The short path

```bash
fluid import pyspark ./jobs --dags ./dags --dry-run
```

`--dry-run` prints each proposed product, its writer, its outputs and its upstream reads, then the report, and writes nothing. Read the report, fill in the conventions file, and run again until the report says what you expect. Then run without `--dry-run`:

```bash
fluid import pyspark ./jobs --dags ./dags --conventions conventions.yaml
fluid validate contract.*.fluid.yaml
```

Output from a real dry run on 0.37.0, on two small files: a job that reads `raw.orders` and writes `curated.orders`, and a DAG with one `SparkSubmitOperator` whose `application` is `/opt/jobs/orders_job.py`:

```text
  Proposal (1 product(s)):
    curated.orders  (owner data-engineering) → contract.curated.orders.fluid.yaml [new]
        build orders_job: jobs/orders_job.py
        exposes: orders (table)
        consumes: raw.orders.orders

  Mapped 1:1 (4):
    • write curated.orders (jobs/orders_job.py:5) → exposes[orders] of curated.orders
    • DAG orders_daily task build_orders (SparkSubmitOperator) → builds[orders_job].execution.orchestration of curated.orders
    • read raw.orders (jobs/orders_job.py:4) → consumes[raw.orders] (no producer in the scanned code)
    • job jobs/orders_job.py → builds[orders_job] of curated.orders

  Used defaults (2):
    • curated.orders: exposes[orders] has an empty schema (the code does not state the columns)
    • curated.orders: binding platform and format default to other: name the catalog or path prefix under `catalogs` or `paths` in the conventions, or set them by hand

  Unsupported (must be re-authored, 2):
    ⚠ DAG orders_daily task build_orders submits /opt/jobs/orders_job.py: joined to a job file by file name only
    ⚠ curated.orders (curated.orders) is read by no scanned job and no declared consumer: retire it, or name its consumer under `external_consumers` in the conventions

  Notes:
    • read 1 Python file(s) under jobs: 1 do Spark reads or writes (jobs), 0 do not
    • read 1 DAG file(s) under dags: 1 DAG(s), 1 task(s), 1 submit a script
    • 1 submitted script(s) joined to a job file (1 by name); 0 not joined
    • 1 upstream table(s) or topic(s) are read but written by no scanned job; consumes[] names them under the id the id rule gives: raw.orders (raw.orders)

Dry run: nothing was written. 1 file(s) would be written.
```

The proposal is a starting point. The code cannot state some things, such as column lists or a Snowflake warehouse. The report lists them under **Used defaults**, and the contract is still written.

## What is read

Files are parsed with Python's `ast` module. Names are folded where the code makes that possible: constants, f-strings, `+` on strings, `os.environ[...]` from the conventions file, and the other cases below. A name that does not fold is reported with the reason. It is never guessed.

### In a PySpark job

| Read | What is taken |
|---|---|
| `spark.table(...)`, `read.table`, `read.load`, `read.parquet`, `csv`, `json`, `orc`, `text` | A read of a table or a path |
| `write.saveAsTable`, `insertInto`, `save`, `parquet`, `csv`, `json`, `orc`, `text` | A write of a table or a path |
| `writeTo(t)` with `append`, `create`, `replace`, `createOrReplace`, `overwrite`, `overwritePartitions` | A write of a table |
| `readStream` and `writeStream` with `start`, `toTable`, `foreachBatch` | A stream read and a stream write |
| `checkpointLocation` as an option, a `start` keyword or a session conf | The stream's checkpoint |
| `trigger` with `processingTime`, `once`, `availableNow`, `continuous`; `queryName`; `outputMode` | The stream's trigger and name |
| Kafka `subscribe`, `subscribePattern`, `assign` (source) and `topic` (sink), plus the bootstrap servers | A topic read or written |
| `spark.sql(...)`: `INSERT`, `CTAS`, `MERGE`, `UPDATE`, `DELETE` targets and the tables a statement reads | Reads and writes. CTE names and temporary views are left out. An f-string field that does not fold becomes a hole, and the rest of the statement is still read. |
| Functions named under `helpers` in the conventions | A read or write you describe |

A stream's writer or reader may be held in a variable that later assignments only add to (`w = w.trigger(...)` in each branch of an `if`). The importer follows it. The sink is the same on every run. The trigger is every one that can apply (`availableNow | processingTime=1 minute`). The product is `continuous` when any alternative keeps running. Only a trigger or an option that does not name the sink may be added: not the format, path, topic, table or checkpoint. A trigger set where the writer is used (`w.trigger(availableNow=True).toTable(...)`) replaces the alternatives the branches set.

The body is read by structured control flow: `if`/`else` join, a loop may run zero or many times, and `try`/`except`/`finally`, `with` and `match` are followed. `return` and `raise` end a path. A `break` or `continue` runs the `finally` bodies it leaves. At most 20 alternatives are kept for one use, and past that the variable is not followed.

Lists and strings built with `name += ...` are read after the last addition. This works at the top level of a body, and inside a top-level `for` over a dict (`items`, `keys`, `values`) or a list that folds (at most 500 items and 5,000 steps).

A path that folds only at its beginning (`f"{LANDING}/orders/dt={run_date}/"`) is the table that the first matching `paths` rule gives: its prefix plus the first path segment. The segment must be complete in the part that folds. The report says so.

An Airflow Variable is read from the conventions file:

| Written in code | Read as |
|---|---|
| `Variable.get("x")`, with `default_var=` (Airflow 2), `default=` (Airflow 3) or a positional default | What `airflow_variables` holds for `x` in the chosen environment |
| `{{ var.value.x }}` or `{{ var.value["x"] }}` in an operator's script, arguments or `bash_command` | The same value, filled in |

A Variable the file does not name stays unresolved. Its default is not assumed. `deserialize_json` and `var.json` are not read.

### In an Airflow DAG file

| Read | What is taken |
|---|---|
| `DAG(...)`, `with DAG(...)`, `@dag` | The DAG id, `schedule`, `schedule_interval` or `timetable`, `catchup`, tags, and the `owner` in `default_args` |
| Tasks | Each task, its operator and its dependencies: `>>`, `<<`, `set_downstream`, `set_upstream`, `chain`, `cross_downstream` |
| `SparkSubmitOperator`, `EmrAddStepsOperator`, `EmrCreateJobFlowOperator`, `EmrContainerOperator`, `EmrServerlessStartJobOperator`, `GlueJobOperator`, `DatabricksSubmitRunOperator` | The script the task submits |
| `spark-submit` inside a `BashOperator` | The script the command submits |
| Project operator classes named under `operators` | Treated as the kind you give |

With `--dags`, or through `script_roots` for `fluid import airflow`, each task is joined to the script it submits. The DAG's schedule, tags, owner, tasks and dependencies then land on the build under `execution.orchestration`.

A script that runs jobs by name (`driver.py --job-list silver_orders`) is described under `drivers` in the conventions. The task is then joined to every job file the list names.

#### Spark work behind a Python task

A `PythonOperator` (any operator with `python_callable`) and a TaskFlow `@task` are followed into the function they run. Nothing is imported or run.

| Behaviour | Detail |
|---|---|
| A helper of the project's own library, named under `submit_helpers` | Its script, config file and arguments are read from the task's `op_kwargs` (by name) and `op_args` (by position). Both are templated, so `{{ var.value.x }}` in them is filled from `airflow_variables`. Reading goes through `functools.partial` and a `lambda`. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |
| A function of the DAG files, or of another file of the scan | Read without an entry. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |
| What a followed body can submit | `add_job_flow_steps` and `run_job_flow` steps (boto3, and the EMR hook's positional form), the EMR hook's `create_job_flow` overrides, `start_job_run` or `submit_job` with a `jobDriver` (EMR on EKS `sparkSubmitJobDriver`, EMR Serverless `sparkSubmit`), `subprocess.run`, `call`, `check_call`, `check_output`, `Popen`, `getoutput`, `getstatusoutput`, `os.system`, `os.popen`, and a written-out argument list that starts with `spark-submit` (or a shell running one). *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |
| Parameters | A parameter holds what the task passes. `**kwargs` holds the rest, which is not all known because Airflow adds the context. A parameter the body binds again is not read. Defaults are read for calls inside a followed body, not for the task's own function. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |
| Depth | A function that calls another is followed three calls deep, never into itself. A function whose code is outside the scan is never read. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |
| What the contract records | A Python task's params gain `python_callable` (as written) and `config` (when it resolved). *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |

Settings a DAG imports from the module next to it by its full package name (`teamx.dags.nightly.settings`, with the DAGs folder on Airflow's path) are found when the import runs through the file's own directory (or a parent inside the scan) and goes on to a file there, or when it starts with the names of the scanned directory and the directories above it. A name of more than 24 parts is not looked for. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* A name that starts with a standard library, `airflow` or `pyspark` name is never taken for the project's. When only the importing file's own package makes a name resolve, a note under **Notes** says which file it was read as (`` `<name>` is read as <file>, the module of that name in the file's own package (check that it is not another library's) ``), up to 20 lines. A relative import in a DAG file (`from .settings import SCRIPT`) resolves the same way whatever the working directory you run from. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))*

The folder reads `dict(...)` (keywords, one mapping, `**spreads`) and `d.get(key[, default])`. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* A dict key written before a `**spread` that does not fold is not taken as known, because the spread can replace it when the code runs. What it names is reported as not read. A key written after the spread (`{**unknown, "table": "a"}`) is still read. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))*

### What is not read

| Not read | What you see |
|---|---|
| SQL operators inside DAGs, and Airflow datasets or assets | Not in the proposal |
| Job parameters bound from DAG arguments through `argparse` | The job's names that depend on them are reported as not constant |
| JDBC reads and writes | A note. No JDBC product is proposed. |
| Delta merge APIs | Not read |
| Columns from `StructType` literals | The expose has an empty schema, and the report says so |
| dag-factory YAML DAGs | Not read |
| DAGs built in loops or functions, and mapped tasks | Reported |
| `chain(*list)` | Reported |
| A DataFrame that comes out of a function call or a parameter | Not followed. Reads that no single write owns are listed on the product. |
| A Variable read as JSON | Not read |

## The proposal rules

| Rule | Behaviour |
|---|---|
| One product per output | One product per output table or topic. `--split-by` changes the boundary (see [the flags](../cli/import.md#importing-pyspark-jobs-and-airflow-dags)). |
| One writer | A table written by two jobs is proposed once. The first writer by path wins and the report names both. |
| One owner | The task's `owner`, else the DAG's `default_args` owner, translated through `owners`. With several owners the first is used and the report says so. With none, `owner.team` is `imported` and the report says so. |
| Reads become `consumes[]` | A read that no scanned job writes is named with the id rule and listed in the report. |
| Builds are records | Each build has pattern `hybrid-reference`, engine `spark` and `properties.model: script`. forge does not run it. |
| Trigger | `manual`, or `continuous` for a long-running stream. Never `schedule`. |
| DAG facts | Under `execution.orchestration` with `mode: manual` and `generateOnChange: false`. |
| DAG ids | `dagId` and `taskId` take only lower case letters, digits, `_`, `.` and `-`. In 0.37.0 a DAG or task id with a capital is not recorded, and the report says so. *(since 0.38.0, [forge-cli #1058](https://github.com/Agenticstiger/forge-cli/pull/1058))* A DAG or task id with a capital (`Nightly_Orders`) is recorded as the importer's identifier of it (`nightly_orders`), with a number after it when that is taken: among the import's DAG ids, and a task's among its DAG's task ids, in file order. An id that fits is never changed. A task's dependencies, and the products `--split-by dag` and `--split-by task` make, use the recorded ids. The running DAG keeps its own id. **Used defaults** lists each id recorded under another one with the Airflow id it stands for: up to 20 lines, then a count. Only an id that is not a constant is still left out, and the report says so. |

The trigger is never `schedule` because [`fluid generate schedule`](../cli/generate.md) would then render a second DAG for a pipeline that already has one.

Each task entry carries both `type: custom` and `operator`. The schema holds any task that lacks either to a `contract_path` requirement, and these tasks have no contract path.

**What a product lists in `consumes[]`.** When the statement that writes an output names everything it reads (tables or paths, with no temporary view and no hole), the product lists those reads. The same holds for the reads a DataFrame expression is made of, followed through names assigned once. A read written inside the write's own expression feeds only that write. Where the code does not say, the product lists every read that no single write owns. What feeds a write that the `ignore` rules drop (a staging table) feeds the products that read it. A staging path is found by its scheme family (`s3a` and `s3n` are `s3`, `gcs` is `gs`, `file:///x` is `/x`), bucket and directories, so a read of the same path in another spelling, with a glob, or of a partition below it, takes what fed the write.

**Ids.** Product, expose and build ids are unique in one run: a second `orders` is `orders_2`. Two jobs with one file name are two products (`a-main`, `b-main`). Files at the top of the scanned directory are named after it. A name with no ASCII letter or digit gets a short digest. An id is at most 120 characters. A path that differs only in case is another path.

**Unread products.** An output that no scanned job reads and no `external_consumers` entry names is flagged in the report. The contract is still proposed. A product that another product of the same job reads is not flagged.

## The conventions file

`--conventions FILE` gives the importer your layout as data. Every key is optional. Keep the ones that describe your project.

```yaml
version: 1
script_roots:
  "s3://code-bucket/jobs/": jobs
paths:
  - prefix: "s3://lake/curated/"
    database: curated
    platform: aws
    format: iceberg
environment: prod
environments:
  prod: {TABLE_PREFIX: ""}
  dev: {TABLE_PREFIX: dev_}
defaults: {database: retail, domain: retail, platform: aws}
owners:
  data-eng: {team: data-engineering}
```

The file is read strictly:

- No code in it runs.
- A key that is not listed below is refused, and the refusal names the key and the line.
- A key given twice, anywhere in the file, is refused. (The YAML merge key `<<` may repeat.)
- A text value with a control or invisible character is refused.
- The file is at most 256 KB, with at most 500 entries in one mapping or list. A text value is at most 500 characters and a regular expression at most 200.
- A refusal message is at most 400 characters. The key is cut, and the reason stays.
- `platform` and `format` values are checked against the bundled schema's enums. `defaults.platform` is checked against the runtime platforms of `execution.runtime.platform`.

### Keys

| Key | Holds | Notes |
|---|---|---|
| `version` | `1` | The only version this CLI reads |
| `script_roots` | Deployed script prefix mapped to a directory in your checkout | Joins a task's submitted script to a file. The longest prefix wins. |
| `paths` | A list of `prefix`, `database`, `table`, `platform`, `format`, `catalog` | What a data path prefix holds. Without `table`, the table is the first segment after the prefix. |
| `helpers` | A function name mapped to `{reads\|writes: table\|path\|topic, arg: <position or keyword>, format: ...}` | Project functions that wrap Spark reads and writes. A helper that is called but not named produces a note. |
| `operators` | An operator class mapped to a kind | Project operators that submit Spark work. The kind is one of `spark_submit`, `emr_add_steps`, `emr_create_job_flow`, `emr_containers`, `emr_serverless`, `glue_job`, `databricks_submit`, `bash`. |
| `submit_helpers` | A function name mapped to where its script, arguments and config are | Python functions that submit Spark work. See [below](#submit-helpers). *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |
| `drivers` | A list of `script`, `argument`, `job_lists`, `jobs` | A script that runs jobs by name. See [below](#drivers). |
| `session_names` | A list of names | Names whose `.sql()` and `.table()` are Spark's. |
| `config_modules` | A list of `module` and `path` | Constants kept outside the scanned directory (`project_config.settings`). |
| `environment` | One name | The environment the lookups use. It chooses among the names under `environments` and `airflow_variables` together. A name under neither is refused with `is not named under environments or airflow_variables`. |
| `environments` | An environment name mapped to variables | What `os.environ[...]` holds in each environment. See [environments](#environments). |
| `airflow_variables` | An environment name mapped to Airflow Variables | What `Variable.get("x")` and `{{ var.value.x }}` hold. Read like `environments`. |
| `defaults` | `database`, `domain`, `platform` | Used when the code gives none |
| `catalogs` | A catalog alias mapped to `platform`, `format`, `catalog` | The first part of a three-part table name. |
| `layers` | A database mapped to `Bronze`, `Silver` or `Gold` | Sets `metadata.layer` |
| `owners` | An owner label mapped to `team`, `email`, `slack`, `oncall` | Name at least a team or an email. The label is what the DAG or task calls the owner. |
| `external_consumers` | A list of names | Outputs that something outside the scanned code reads. See [below](#external-consumers). |
| `ignore` | `tables`, `paths` (regular expressions), `files` (globs relative to the scanned directory) | Dropped from the proposal. A pattern sees at most 256 characters of a name. |
| `products` | `{id: "<template>"}` | The id rule. Only `{catalog}`, `{database}` and `{table}` may be used. |

A table in a Spark catalog (`glue_catalog.raw.orders`) gets `binding.location.catalog` only when its kind is known. The kind is known when the alias is one FLUID knows, when a `catalogs` rule maps it, or when the scanned code sets `spark.sql.catalog.<alias>.type` or a `catalog-impl` (Glue, REST, Hive, Nessie, Hadoop) in `builder.config`, `conf.set`, a dict or a `--conf`. Otherwise the binding has no catalog and the report says to set it. An alias is not a kind, and `fluid validate` refuses it.

### Where a path may point

A path in the file (`script_roots` values, `config_modules[].path`, `drivers` directories) is relative to the file. Once it is resolved (a link counts for where it points), it must be inside one of these:

- the folder that holds the conventions file;
- the directory to scan (`<jobs-dir>` for pyspark, `<dags-dir>` for airflow);
- for `fluid import pyspark`, the `--dags` directory.

*(since 0.37.0, [forge-cli #1034](https://github.com/Agenticstiger/forge-cli/pull/1034))* Everything else is refused: `..` out of all of them, an absolute path elsewhere, a link that points out, and a sibling whose name only starts like a named one. The file can therefore live in a folder beside the repositories:

```bash
fluid import pyspark ../repos --dags ../repos/dags --conventions config/conventions.yaml
```

A refusal reads `<path> leaves the directory of the conventions file and the directories named on the command line: keep what the scan reads inside one of them`.

`fluid import airflow` names only the DAGs directory. A `script_roots` entry that points at a repository beside the DAGs repository is therefore refused there. Use `fluid import pyspark <jobs-dir> --dags <dags-dir>`, or put the conventions file in a folder above both.

Since 0.38.0, a path that is allowed but names nothing is one line in the report. The line gives the path as written and as resolved, the tasks it leaves unjoined, and, when the path names something from a folder above a directory named on the command line, that folder ("put the conventions file there"). The refusal for a path that leaves every allowed directory also says how to bring it in. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))*

### Environments

`environments` and `airflow_variables` map an environment name to variables. A value is text and may be empty.

| Value | Meaning |
|---|---|
| `PREFIX: ""` | The variable has this value. `os.environ["PREFIX"]` folds to the empty text. |
| A variable the file does not name | Unresolved, and reported (`the environment variable PREFIX`). |
| `PREFIX:` with nothing, `~`, `null`, a list, a mapping | Refused with `expected text: write "" for an empty value, put anything YAML would read as a number, a yes/no or a date in quotes, or leave the variable out`. Before 0.37.0 a null silently became the text `None`. |
| `1.10`, `007`, `yes`, an unquoted date | Refused until quoted. YAML would turn them into another value. A value is the text it is written as, kept exactly (not trimmed), at most 500 characters. |

A value whose name says it is a credential (`db_password`, `API_TOKEN`, the names Airflow hides in its own logs) is not substituted. The code's reference stays as written, and the report lists the names.

The example from the table-prefix case:

```yaml
environment: prod
environments:
  prod: {TABLE_PREFIX: ""}
  dev: {TABLE_PREFIX: dev_}
```

With `TABLE_PREFIX = os.environ["TABLE_PREFIX"]` in a job and `f"curated.{TABLE_PREFIX}orders"` as the target, the table is `curated.orders` with `environment: prod` and `curated.dev_orders` with `environment: dev`. A dry run with `dev` proposes `curated.dev_orders`.

### Drivers

A task that submits `driver.py --job-list silver_orders` runs whatever the list names. Describe the driver, and the task is joined to every job file the list names.

```yaml
drivers:
  - script: driver.py
    argument: --job-list
    job_lists: {dir: libs/job_lists, file: "{value}.yaml", key: jobs}
    jobs: {dir: libs/jobs, file: "{job}.py"}
```

| Field | Holds |
|---|---|
| `script` | The submitted script's file name, or its trailing path segments (`pkg/driver.py`). No `..`. |
| `argument` | A flag (`--job-list`) or a 0-based position. |
| `job_lists.dir`, `job_lists.file` | The directory of the lists, and a list's file name with `{value}` where the argument's value goes. |
| `job_lists.key` | Where the names are in the list file. Without it, the file is the list. |
| `jobs.dir`, `jobs.file` | The directory of the job files, and a job file's name with `{job}` for a name. |

Names and values must be plain file names (no `/`, no `..`). Directories follow [the path rule](#where-a-path-may-point), and a link that points out is refused. The list is bounded safe YAML and is never run. A list file is at most 16 KB and 500 names, and all the lists of one import are at most 128 KB. A list that would pass the total is refused before it is read. A key given twice in a list file is refused.

### External consumers

`external_consumers` lists outputs that something outside the scanned code reads (a dashboard, another team's job). An entry is `db.table`, `catalog.db.table`, a topic, a path, or the product id, in any case. A trailing `/` is ignored. The key is `external_consumers`. The name `consumers` is not used, because a contract has a reserved `consumers` block.

```yaml
external_consumers: [gold.revenue_daily, orders-topic]
```

Declaring a consumer clears the report's "retire it" line for that output on the next import.

### Submit helpers

*(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* `submit_helpers` describes a Python function of your own library that submits Spark work. Name it by the function name, or the end of its dotted path (`run_spark_step` matches `tasks.emr.run_spark_step`). The longest entry that matches wins.

```yaml
submit_helpers:
  run_spark_step:
    script: script_path
    args: step_args
    config: additional_params.config_path
    kind: emr_add_steps
```

| Field | Holds |
|---|---|
| `script` | Required. Where the script is among the function's arguments. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |
| `args` | Where the script's arguments are: one place, never a text with braces. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |
| `config` | Where the script's config file is. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |
| `kind` | What it submits to: one of the `operators` kinds above except `bash` (for example `emr_add_steps`). The default is `spark_submit`. The EMR and Glue kinds give the AWS runtime platform, and `databricks_submit` gives Databricks. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |

A place is a keyword (`script_path`), a position (`0`), or a key path into one argument (`additional_params.script_path`). `script` and `config` may be a text with places in braces (`"s3://{bucket}/{key}"`). Text without braces is taken as a place, so a fixed script cannot be written here. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))*

## `--split-by task`

`--split-by task` makes one product per DAG task. The product holds the outputs of every job the task runs, a driver's job list included, and its id is `<domain>.<dag>.<task>`. A job that no task runs is one product of its own. See [`fluid import`](../cli/import.md#importing-pyspark-jobs-and-airflow-dags) for every boundary.

## The report

The report has the same four sections as every importer: Mapped 1:1, Used defaults, Unsupported (must be re-authored) and Notes. These lines are the ones to act on:

| Line | What to do |
|---|---|
| `... is read by no scanned job and no declared consumer: retire it, or name its consumer` | Add the consumer to `external_consumers`, or retire the output. One line per product up to 20, then a count. |
| `... joined to a job file by file name only` | The task's script was matched by its file name. Map the deployed prefix under `script_roots` to be exact. |
| A task submitted a script that was not joined | Map its prefix under `script_roots`, or run pyspark with `--dags`. |
| `several job files match it equally` | Two job files share the name. Map a prefix under `script_roots`. |
| `... is not a constant` | A table, path or topic name did not fold. The line gives the reason. Name a `helpers` entry, an environment, or an `airflow_variables` entry. |
| A note about a helper function | Name the helper under `helpers`. |
| `the trigger of this stream is picked by a branch of the code (...)` | The stream has more than one possible trigger. Check the trigger in the contract. |
| `reads or writes a path that is not a constant past <root>: it is taken as that table` | A path only folds at its beginning. Check the table. |
| `N job file(s) run through a driver` | Tasks joined through `drivers`. |
| `the job list X names N job(s) with no job file...` | A name in a list has no file in `jobs.dir`. |
| `the environment variable PREFIX`, or a Variable name | A value the conventions can give. Add it under `environments` or `airflow_variables`. |
| A conventions value is not used because its name looks like a credential | The code's reference stays as written. |
| A list of reads cut per product (`each lists at most K`) | Past 40,000 listed reads in all, each product lists at most K of its reads, from 500 down to 5. Below 5 the import is refused with a `--split-by job` hint. |
| A product's `fluid validate` findings | What the contract rules find that no code can give (columns, a Databricks schema, a Snowflake warehouse). Up to 30 products with findings left over are named. |
| `DAG ... is recorded as dagId '...'` or `task ... is recorded as taskId '...'`, and `N more Airflow id(s) are recorded under a FLUID id` | *(since 0.38.0, [forge-cli #1058](https://github.com/Agenticstiger/forge-cli/pull/1058))* An Airflow id with a capital was recorded under a lower-case id (a line under **Used defaults**, ending in `The running DAG keeps its own id`). Nothing to fix: the line says which Airflow id each recorded id stands for. |
| `N Python task(s) run a function that is not read here: ...`, and a line per value a script waits for | *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* The note (under **Notes**) counts the functions that Python tasks run and that are not read (top 10 by tasks) and says to name the submitting ones under `submit_helpers`. A function of the standard library, Airflow or PySpark is named as one that `submit_helpers` does not take: call it from a function of the DAG files, and what that function runs is read. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* **Used defaults** gets one line per value a submitted script or config file waits for that the conventions can give, with up to 3 tasks named: a constant of a module outside the scan (`config_modules`), an environment variable (`environments`), an Airflow Variable (`airflow_variables`). A credential-looking name is not listed. At most 20 lines, and the rest are counted. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* |

Each proposal is checked against the schema before anything is written. A schema error stops the import, with `the proposal ... is not a valid contract`. That points at a conventions value the schema refuses, or at a bug to report. Tasks the schema refuses are dropped from the DAG record, and the report says so.

## Limits

The reading is bounded. A refusal names the way out: a smaller directory, or `ignore.files`.

| Limit | Value |
|---|---|
| A source file | Not read over 300 KB or with more than 50,000 `{` characters (counted in the encoding Python reads it in). A generated file: ignore it. |
| One import's source | At most 64 MB in all (jobs, DAG files and every script root together). At most 200,000 syntax-tree nodes parsed at once. At most 2 MB for re-reading dropped modules. |
| Files scanned | At most 5,000 files, 50,000 directory entries and 12 levels |
| Reads and writes | A scan keeps at most 200,000. A job keeps 5,000 reads, 5,000 writes and 200 notes. |
| Tasks | A job records at most 1,000 of its tasks. A command keeps its first 20 submits. A task lists at most 100 arguments. |
| SQL | At most 1,500,000 characters parsed in one import (a statement once per file) |
| A name | A table or path name is at most 512 characters. A folded string is at most 4,096. A longer `bash_command` is listed as not read, with none of its text. |
| One proposal | At most 50,000 outputs and 10,000 products. At most 200,000 reads listed in `consumes[]` between products. At most 1,000,000 reads and 1,000,000 task links gone through. At most 16,000,000 characters of DAG tasks. |
| Per product | Each lists at most 500 reads and 500 tasks. The report counts the rest. At most 20 streams are described. |
| One DAG | At most 10,000 dependencies |
| An argument or a command | An argument over 4,096 characters or a command over 20,000 is shown only as its size (`<an argument of N characters, too long to show>`). |
| Conventions paths | `script_roots`, `config_modules` and `drivers` paths stay inside [the directories above](#where-a-path-may-point) |
| DAG file calls | *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))* The DAG files of one scan follow at most 500,000 calls and lists of the bodies between them, plus 250 for each Python task followed, and 200,000 for one file. |

Limits that follow from how the code is read:

- A job that reads its own output and writes another product counts as a reader of that output, so the unread flag is not raised.
- Reads that only feed a write whose target is unresolved or JDBC are on no product.
- A list returned unchanged by a helper (`def f(x): return x`), or taken as a mutable default (`def f(x=A)`) and then changed in place through the other name, is not seen as an alias of the first. The folder can then show the shorter list.
- `.exists()` and `.scalar()` called on a name that is not a DataFrame make the write loose: it lists every read that no single write owns.
- A def whose name the file also assigns once is the function only between the def and the end of that assignment, which includes its value: `extract = PythonOperator(..., python_callable=extract)` follows `extract`. A use of the name after the assignment, or inside a function or lambda that runs later, is not followed. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))*
- A written-out `spark-submit` list is taken as run. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))*
- The own-package anchor can take a same-named directory of another top-level package for the file's own. *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055))*

## Credential masking

Command lines and argument lists in a DAG are copied into the contract so you can see what runs. The importer masks credentials in them word by word. A word ends at a shell operator, and the operator and the quoting stay. The lines, comments and quoting of the command are kept.

**Masked:**

| Form | Example shape |
|---|---|
| `NAME=value` where the name looks like a credential | `PGPASSWORD=...` |
| Credential flags and their values | `--password`, `--passwd`, `--pw`, `--token`, `--access-key`, `-p`, `-w` (not before a path or a port, and not for `mkdir -p`, `ssh -p` and the like), `bcp -P`, `docker login -p` |
| Users with a secret | `-u user:secret`, `--user`, `-uUSER:PASS`, `mysql -pSECRET` |
| Spark and Hadoop secrets | `--conf spark.hadoop.fs.s3a.secret.key=...` |
| Headers and cookies in a quoted word | `-H "X-Api-Key: ..."` |
| JSON values with a credential key | A long one is masked whole |
| A URL's secret parts | The password in a URL (an AWS secret with a slash included), and `sig=`, `key=`, `code=` in a URL |
| An Oracle login | `sqlplus user/password@service`, and a bare `scott/pw@ORCL` after an Oracle client, `userid=`, `-u` or `--dsn`. A login as a plain word or an option's value (`scott/tiger@db:1521/ORCL`, `scott/tiger@//db/ORCL`) is masked too. |
| Nested shells | `bash -c "..."`, to five levels |
| Clients behind a wrapper | `sudo -u app mysql -pX`, `timeout 10 mysql`, `xargs docker login`, `docker run img mysql` |
| A value set with `set` | `aws configure set aws_secret_access_key X` |

The user information of a data path or a host, and a `key=value` path segment with a credential's key, never reach an id, a file name or a binding.

**An argument or a command too long to read** (over 4,096 and 20,000 characters) is shown only as its size, so a cut cannot show part of a credential. Characters that hide a credential from a rule (a zero-width one) are removed before the rules read the text. An apostrophe in a comment or a here-document does not pair with a quote lines below it, and a script in a quoted word is read line by line. A new line between commands in a `bash_command` is recorded as `;`.

**Left as written, on purpose:**

- A Jinja field (`{{ var.value.x }}`) is a reference, not a secret.
- A name that ends in `file`, `path`, `id`, `url` and the like holds a reference.
- A flag's state, a small number, or a path is not a secret.
- An image digest, a time or a dotted path is not taken for a login.

Review the contract before you commit it. Masking works on the shape of the text, so a secret in an unusual shape can be left as written.

## Importer plugins

A package can add `fluid import <tool>` through the `fluid_build.importers` entry-point group. Your package does not import forge.

```toml
[project.entry-points."fluid_build.importers"]
my-tool = "my_package.forge_importer:MyImporter"
```

The entry point names an object: a class (built with no arguments), an instance, or a function that returns one.

| Member | Required | Contract |
|---|---|---|
| `import_to_contract(source, *, options)` | One of these two | Returns `(contract, report)` |
| `import_to_contracts(source, *, options)` | One of these two | Returns `([contract, ...], report)` for a tool that splits a source into products |
| `can_import(source)` | No | Returns whether the source is one this importer reads |
| `guards_overwrite = True` | No | The command refuses to replace a file that differs from what the plugin writes, unless `--force` |

The report is any object with four lists: `mapped_one_to_one`, `required_defaults`, `unsupported` and `notes`. It can also be `None`. `options` holds:

| Key | Holds |
|---|---|
| `split_by` | `project` unless the user chose a boundary |
| `conventions` | The `--conventions` value, as a string. Never opened for the plugin. |
| `dags` | The `--dags` value, as a string. Never opened for the plugin. |

How a plugin is loaded:

- It is read by name from entry-point metadata and loaded only when its tool is asked for by name. No other command runs plugin code, and `fluid --help` stays cold.
- `FLUID_PLUGINS_ALLOWLIST` and `FLUID_PLUGINS_BLOCKLIST` apply to the entry-point name before anything is imported. See [`fluid plugins`](../cli/plugins.md#operator-governance).
- A built-in name cannot be taken: a plugin adds a source and never replaces one. A plugin that claims one is skipped without being imported.
- Two distributions that ship one name are both refused.
- A plugin that fails to import or to build is skipped, and only the exception type is logged.
- `fluid plugins` lists the group under the role `importer`.

## See also

- [`fluid import`](../cli/import.md): flags, output files and errors.
- [`fluid plugins`](../cli/plugins.md): the plugin roles and the allow/block policy.
- [Airflow integration](./airflow.md): the DAGs forge generates from a contract.
