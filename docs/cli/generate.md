# `fluid generate`

Unified artifact generation from FLUID contracts.

## Syntax

```bash
fluid generate <transformation|speed-transformation|dbt|dbt-tests|schedule|ci|standard|artifacts|iac|vector>
```

## Subcommands

### `fluid generate artifacts`

**Stage 3 of the 11-stage pipeline.** One call writes the catalog and execution artifacts for a contract:

- ODCS (v3.1.0) contract files under `odcs/`
- ODPS-Bitol (v1.0.0) product files under `odps-bitol/`
- OPDS (v4.1, LF/ODPI) product file under `opds/`
- Airflow DAGs under `schedule/`, when the contract has an `orchestration.engine` or a scheduled build
- Policy bindings under `policy/bindings.json` (IAM / GRANT)
- A `MANIFEST.json` (SHA-256 per file and a merkle root) that stage 4 verifies

```bash
fluid generate artifacts runtime/bundle.tgz --out dist/artifacts/                  # the pipeline path
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/                 # local shortcut
fluid generate artifacts contract.fluid.yaml --emit odcs,odps-bitol                # catalog only
fluid generate artifacts runtime/bundle.tgz --env aws \
  --contract-path contracts/orders/contract.fluid.yaml                             # DAGs that run `fluid apply --env aws`
```

Options: `CONTRACT`, `--out`, `--emit`, `--manifest`, `--env`, `--contract-path`. The output tree, the emit keys, the scheduled-build DAGs and the fragment-layout limitation are on the [`generate artifacts`](./generate-artifacts.md) page. Verify the emitted tree with [`fluid validate-artifacts`](./validate-artifacts.md) (stage 4).

### `fluid generate transformation`

Generate transformation artifacts from the contract's builds. The engine is read from `builds[].engine`; `fluid generate transformation --list` prints the engines the CLI has:

```text
  dataflow     patterns: hybrid-reference, embedded-logic
  dataform     patterns: hybrid-reference, embedded-logic, multi-stage
  dbt          patterns: hybrid-reference, embedded-logic, multi-stage
  glue         patterns: hybrid-reference, embedded-logic
  spark        patterns: hybrid-reference, embedded-logic, multi-stage
  sql          patterns: embedded-logic, multi-stage
```

```bash
fluid generate transformation
fluid generate transformation contract.fluid.yaml -o ./dbt_project
fluid generate transformation contract.fluid.yaml -o ./dbt_project --dbt-validate
fluid generate transformation contract.fluid.yaml --all-builds -o ./out
```

Key options:

- `contract` (default: `contract.fluid.yaml` in the current directory)
- `--output`, `-o` — output directory (default: the build's `repository`, else `./<engine>_project`)
- `--build-index` — which build to generate for (default `0`)
- `--all-builds` — generate for every build in the contract
- `--concurrency N` — how many builds `--all-builds` generates in parallel (default `4`)
- `--model PATH` — a forged logical sidecar (`*.model.json`); see below for the automatic case
- `--overwrite`
- `--env`
- `--model-contracts` — emit enforced dbt model contracts on every expose model (`contract: {enforced: true}` plus per-column `data_type` and `constraints` derived from `exposes[].contract.schema[]`), so `dbt build` fails in producer CI when the model's output drifts from the contract. Opt-in; dbt-only (dbt-core ≥ 1.5).
- `--dbt-tests-key {auto,tests,data_tests}` — which YAML key generated dbt data tests attach under. The default `auto` (also `$FLUID_DBT_TESTS_KEY`) detects the dbt binary you would run: Fusion and dbt-core ≥ 1.8 emit `data_tests:`, dbt-core before 1.8 and "no dbt found" emit the legacy `tests:`. Pass an explicit value in CI generators that have no dbt binary. dbt-only.
- `--mesh-hub HUB_PROJECT_NAME` — declare a dbt Mesh hub: emits `dependencies.yml` with `projects: [{name: HUB_PROJECT_NAME}]` (dbt-core ≥ 1.6). dbt-only. See [Mesh hub](#mesh-hub).
- `--dbt-validate` — after generating a dbt project, run `dbt parse` against it. Skipped without a dbt binary, and for other engines.
- `--list`, `--verbose`, `--quiet` (`-q`)

When the contract was produced by `fluid forge data-model`, the generator loads the logical sidecar named by `labels.modelSidecar` and emits deterministic SQL from the forged logical model. For dbt output, zero generated `models/**/*.sql` files is a hard failure rather than a quiet success.

`fluid generate speed-transformation` and `fluid generate dbt` are aliases for this path.

#### What the `sql` engine emits

::: warning Behaviour change in 0.16.0
The `sql` engine used to emit one inert `SELECT` per stage. Each stage of a multi-stage build now runs `CREATE OR REPLACE VIEW`. Regenerate and re-run any scripts you committed from an earlier version.
:::

```bash
fluid generate transformation contract.fluid.yaml -o gen_sql
```

```text
consumes_not_wired: build customer_360_pipeline uses the 'sql' engine, which never reads consumes[], ...

Generated 5 files (sql engine):

  gen_sql/01_stage_1_customer_base.sql
  gen_sql/02_stage_2_purchase_summary.sql
  gen_sql/03_stage_3_engagement_summary.sql
  gen_sql/04_stage_4_rfm_calculation.sql
  gen_sql/05_stage_5_high_value_filter.sql
```

`gen_sql/01_stage_1_customer_base.sql`:

```sql
-- Generated by fluid generate — do not edit manually.
-- Regenerate with: fluid generate
-- Contract: gold.customer.analytics_360_v1
-- Stage: stage_1_customer_base (1/5)
-- Materialises: customer_base  (CREATE OR REPLACE VIEW)

CREATE OR REPLACE VIEW customer_base AS
SELECT
  customer_id,
  ...
```

- **Files** are `NN_<stage>.sql`, numbered by the stage's position in `stages[]`. A runner that executes them in filename order runs the stages in declaration order, so declare stages in dependency order; the generator warns (`sql_stage_order_not_topological`) when a stage precedes one it depends on.
- **The view is named after the stage's declared output**, the first entry of `stages[].outputs`, because a contract's SQL refers to stages by output name (`FROM customer_base`). A stage with no output of its own, or whose output name another stage also claims, gets `-- Not materialised: <reason>` in the header instead, and its SQL is emitted as a bare statement. SQL that already writes to a target of its own (`INSERT`, `CREATE`, `MERGE` and the other statements that name a sink) is also emitted as it is, with a `-- Not materialised:` header.
- **Declared inputs are bound.** `builds[].properties.parameters.inputs` entries (`name`, `path`, `format`) become `00_inputs.sql`, which sorts first:

  ```sql
  -- customers_raw <- data/customers.csv
  CREATE OR REPLACE VIEW customers_raw AS SELECT * FROM read_csv_auto('data/customers.csv', AUTO_DETECT:=true, DELIM:=',');
  ```

  This is the statement `fluid apply` runs for the local provider. Paths resolve relative to the directory the script runs in. The file is written only for a local (`local` / `duckdb`) build platform; for any other platform the generator warns `sql_inputs_not_bound_for_platform` and writes nothing.
- **A single-stage `embedded-logic` build** emits one bare `SELECT` named after the build id (`clean_customers.sql`), with no view around it.

A re-run of `CREATE OR REPLACE VIEW` is not harmless. It drops the grants on the view in Snowflake and Databricks and makes a Snowflake stream over the view stale, and it fails when a table of the same name already exists. Review the generated scripts before pointing them at a shared schema.

#### How dbt models are named

*(since 0.16.0)* A multi-stage build emits one model per stage, and the model file is named after the stage's declared output, not the stage's name:

```bash
fluid generate transformation dbt.fluid.yaml -o gen_dbt
```

```text
Generated 10 files (dbt engine):

  gen_dbt/dbt_project.yml
  gen_dbt/packages.yml
  gen_dbt/profiles.yml
  gen_dbt/models/
    sources.yml
  gen_dbt/models/marts/
    customer_360_master.sql
    customer_base.sql
    engagement_summary.sql
    high_value_customers.sql
    purchase_summary.sql
    schema.yml
```

For the stage named `stage_4_rfm_calculation` with `outputs: [customer_360_master]`, the file is `customer_360_master.sql`.

- The first usable entry of `outputs` names the model. A stage with no output keeps its own name, and a name two stages both claim goes to neither (the generator logs `dbt_stage_model_name_collision`).
- `dependsOn` entries are rewritten to model names, so `ref()` calls resolve.
- The directory still comes from the stage name: a name containing `staging`, `stg_`, `extract` or `raw` goes to `models/staging/`; one containing `intermediate`, `int_` or `prep` goes to `models/intermediate/`; any other goes to `models/marts/`.

A project generated before 0.16.0 has different model and file names, and regenerating renames them. The contract's data tests now attach to models that exist, so a data-quality rule with no dbt equivalent appears as a fail-loud `fluid_*` sentinel test (for example `fluid_valid_values_email`), where before it attached to a model that was not there.

Two warnings cover a generated file that names a model the run did not emit:

| Warning | What happens |
| --- | --- |
| `dbt_schema_yml_model_missing` | A `schema.yml` entry whose model was not emitted is kept, and the warning says its tests and column docs attach to nothing. It is kept so that `fluid verify --reconcile-dbt`, which reconciles the contract's exposes against `schema.yml`, does not start failing with `model_missing_in_dbt`. |
| `semantic_models: dropping ...` | A semantic model or metric whose `ref` target was not emitted is dropped from `semantic_models.yml`. |

#### Engines and `consumes[]`

Only the `dbt` engine turns `consumes[]` into something: it emits `models/sources.yml`. The other engines (`sql`, `spark`, `glue`, `dataform`, `dataflow`) do not read `consumes[]`, and say so once per build, naming the upstreams, with exit code 0:

```text
consumes_not_wired: build customer_360_pipeline uses the 'sql' engine, which never reads consumes[], so nothing it generates is derived from the 3 declared upstream(s): bronze.customer.raw_customers_v1.raw_customer_data, bronze.sales.raw_orders_v1.raw_order_data, bronze.support.raw_interactions_v1.raw_interaction_data. Whether the emitted code happens to reference them depends entirely on what the build's own SQL names. Point the build at them by hand, or use the dbt engine, which emits them as sources.
```

The `customer-360` template triggers it. Wire the upstreams by hand in the build's SQL, or use the `dbt` engine.

For a `dbt` build, an upstream the generator cannot find in the workspace gets a source whose database and schema fall back through environment variables, so `dbt parse` does not fail on a missing variable:

```yaml
database: '{{ env_var(''FLUID_SOURCE_DATABASE'', target.database) }}'
schema: '{{ env_var(''FLUID_SOURCE_SCHEMA'', target.schema) }}'
```

For a Snowflake, BigQuery (`gcp`), Redshift or Athena (`aws`) binding, a platform variable sits between the two: `SNOWFLAKE_DATABASE` / `SNOWFLAKE_STAGE_SCHEMA`, `GCP_PROJECT` / `BIGQUERY_DATASET`, `REDSHIFT_DATABASE` / `REDSHIFT_SCHEMA`, `ATHENA_DATABASE` / `ATHENA_SCHEMA`. The generated project's output above is for a `local` binding, which has none.

#### dbt compatibility

The generator reads `dbt --version` from `$DBT_EXECUTABLE` or `PATH`, and chooses the YAML shapes the detected dbt understands:

| Generated shape | Emitted when dbt-core is | Otherwise |
| --- | --- | --- |
| Generic-test inputs nested under `arguments:` | 1.10.8 or later, or dbt v2 (Fusion) | Flat inputs. |
| Source `freshness` and `loaded_at_field` under `config:` | 1.10.5 or later, or dbt v2 (Fusion) | At the top of the source table. |

Model `access` is written under `config:` whatever version is detected.

If no dbt is detectable, the generator emits the older shapes. dbt v2 rejects those, so a CI job that generates without dbt installed and then runs dbt v2 fails at parse. Install the dbt you will run in the job that runs `generate`, or pass `--dbt-tests-key` explicitly for the tests key. forge-cli's source records the floors above as measured on dbt-core 1.8.10, 1.9.11, 1.10.0, 1.10.5, 1.10.8, 1.12.5 and 2.0.4.

When `fluid apply` runs a dbt build in a container, the fallback when the local dbt cannot run the build's adapter, the container installs `dbt-<adapter><2` and `dbt-core<2` into `python:3.12-slim`. Three variables change that: `DBT_BOOTSTRAP_IMAGE` replaces the base image, `DBT_ADAPTER_PACKAGE` replaces the install (and drops the `dbt-core<2` cap, which is how you opt into v2), and `DBT_DOCKER_IMAGE` runs a prebuilt image that already has dbt.

#### Mesh hub

```bash
fluid generate transformation dbt.fluid.yaml -o gen_mesh --mesh-hub central_hub
```

writes `dependencies.yml`:

```yaml
projects:
- name: central_hub
packages:
- package: dbt-labs/dbt_utils
  version:
  - '>=1.4.0'
  - <1.5.0
```

dbt does not allow `packages.yml` and `dependencies.yml` in one project, so the package pins that `packages.yml` would carry are folded into `dependencies.yml`, and no `packages.yml` is written. `--dbt-validate` runs `dbt deps` before `dbt parse` when either file exists and `dbt_packages/` does not.

#### Errors

Before it writes a file, the generator resolves each generated path and checks it against the output directory. A contract field that becomes a filename, such as `builds[].properties.stages[].name`, passes `fluid validate` with any string, so it can hold a path:

```text
generated_path_outside_output_dir: {'path': '01_../../../../ESCAPED.sql', 'output_dir': 'gen_evil', 'hint': "A generated file path escapes the output directory. This normally means a contract field that becomes a filename (e.g. builds[].properties.stages[].name) contains path separators or '..'."}
```

The command exits 1 and writes nothing. `generated_path_collision` is the same refusal for two keys that resolve to one file (`02_z/../01_a.sql` normalises onto `01_a.sql`), which would otherwise leave one stage's SQL silently replaced. Both checks run before any engine writes a file. Stage names become filenames: keep path separators and `..` out of them.

### `fluid generate dbt-tests`

Read the contract's `exposes[].contract.dq.rules[]` and emit a dbt `schema.yml` so your data-quality rules run as native dbt tests.

```bash
fluid generate dbt-tests
fluid generate dbt-tests contract.fluid.yaml -o dbt/models/schema.yml
fluid generate dbt-tests --env prod
```

Key options:

| Option | Description |
| --- | --- |
| `contract` | Contract path. Defaults to `contract.fluid.yaml` in the current directory. |
| `--out`, `-o` | Output path for the dbt `schema.yml` (default `./schema.yml`). Drop it into your dbt project's `models/<schema>/` directory. |
| `--env` | Environment overlay (`dev` / `test` / `prod`). |
| `--dbt-tests-key {auto,tests,data_tests}` | Which YAML key the tests attach under; same rule as [`generate transformation`](#fluid-generate-transformation). Default `auto`, also `$FLUID_DBT_TESTS_KEY`. |

- **Column-level rules** map to dbt's built-in tests — `not_null`, `unique`, `accepted_values` — with `dbt-utils` placeholders emitted for rules that have no native dbt equivalent.
- **Model-level rules** map to `dbt-utils`: `anomaly_detection` / `drift_detection` rules become `dbt-utils` expressions, and a `freshness` rule becomes `dbt_utils.recency`.
- The generated `dbt-utils`-based tests require the `dbt-utils` package to be installed in your dbt project.
- A generated file starts with `# managed-by: fluid`. Re-running the command regenerates a file that has the header, so edits to it are lost. A file without the header is not overwritten: the command fails with `dbt_tests_refusing_overwrite` and tells you to delete the file or pick another `--out`.

After generating, run `dbt test` in your dbt project to execute the rules.

### `fluid generate schedule`

Generate orchestration artifacts: Airflow DAGs, Dagster pipelines or Prefect flows. The scheduler is read from `orchestration.engine`, or set with `--scheduler`.

```bash
fluid generate schedule contract.fluid.yaml --scheduler airflow -o dags
fluid generate schedule contracts/orders/contract.fluid.yaml --env aws
fluid generate schedule --list
```

Key options:

- `contract`
- `--output`, `-o` — output directory (default `./dags`, `./pipelines` or `./flows`, by scheduler)
- `--scheduler` — `airflow`, `dagster` or `prefect`
- `--overwrite`
- `--env` — environment overlay. For a `fluid apply` DAG it is also the `--env` each scheduled run passes to `fluid apply`.
- `--contract-path PATH` — the contract's path relative to `$FLUID_PROJECT_DIR` on the Airflow worker, for a `fluid apply` DAG. Default: the `contract` argument relative to the current directory.
- `--list`, `--verbose`

Builds that declare `execution.trigger.schedule` (or `cron`) and no explicit `orchestration.tasks` get Airflow DAGs, with Airflow as the default engine. Each DAG runs its build through `fluid apply --mode amend-and-build`:

```bash
fluid generate schedule sched.fluid.yaml --env aws -o dags_out
```

```text
Generated 1 files (airflow scheduler):

  dags_out/customer_360_pipeline_dag.py
```

The DAG's contents, its worker requirements and the environment it passes to fluid are on the [`generate artifacts`](./generate-artifacts.md#scheduled-builds) page. The DAG id carries the env: `<product>__<env>__<build>`.

This is the promoted path for orchestration generation.

### `fluid generate ci`

Generate CI/CD pipeline configuration for Jenkins, GitHub Actions, GitLab CI, Azure DevOps, Bitbucket, CircleCI or Tekton.

```bash
fluid generate ci --system github
fluid generate ci contracts/orders/contract.fluid.yaml --system jenkins --out Jenkinsfile
```

Jenkins example for a product chained behind another and applied in `aws`:

```bash
fluid generate ci contracts/orders/contract.fluid.yaml \
  --system jenkins \
  --fluid-env-default aws \
  --apply-mode-default amend-and-build \
  --default-publish-target fluid-command-center \
  --out Jenkinsfile
```

Jenkins example for an Entropy Data / Data Mesh Manager first run:

```bash
fluid generate ci contract.fluid.yaml \
  --system jenkins \
  --install-mode pypi \
  --default-publish-target datamesh-manager \
  --no-verify-strict-default \
  --publish-stage-default \
  --out Jenkinsfile
```

Options:

| Option | Description |
| --- | --- |
| `contract` | Contract path. Defaults to `contract.fluid.yaml` when omitted. The path as given becomes the pipeline's `CONTRACT` default, so `contracts/orders/contract.fluid.yaml` generates a pipeline that builds that file. |
| `--system` | Target CI system: `jenkins`, `github`, `gitlab`, `azure`, `bitbucket`, `circleci`, or `tekton`. Default `gitlab`. Hyphen/underscore variants (`github-actions`, `azure-devops`, `gitlab-ci`, `circle-ci`, …) are also accepted. |
| `--complexity {basic,standard,advanced,enterprise}` | Pipeline complexity. Default `standard`. `basic` is validate + apply, `standard` adds testing, `advanced` multi-env and approvals, `enterprise` governance and compliance steps. |
| `--out PATH` | Override the primary output path. Multi-file systems still write their supporting files to canonical locations. |
| `--no-generate-artifacts` | Skip the transformation and schedule stages, for reference-only contracts. Also set automatically when a build's `builds[].pattern` is `hybrid-reference`. In Jenkins and Tekton it sets stage 3's default to off. |
| `--install-mode {pypi,dev-source}` | Jenkins and Tekton. `pypi` (default): the install step installs the package spec (Jenkins: `FLUID_PACKAGE_SPEC` into a virtual environment in the workspace). `dev-source` installs from a `/forge-cli-src` bind mount for contributor labs and fails if the mount is missing; on Tekton it also drops the `fluid-package-spec` and pip index parameters from `pipeline.yaml`. |
| `--fluid-package-spec SPEC` | Default of the `FLUID_PACKAGE_SPEC` parameter. Default: the version that generated the file, with the extras the contract's bindings need across its base and every overlay, such as `data-product-forge[local]==0.18.1` or `data-product-forge[aws,local]==0.18.1`. |
| `--fluid-env-default ENV` | Default of `FLUID_ENV`, the overlay the stages pass to `--env`, and the fallback the stages read, so a build with no parameters runs in `ENV`. Letters, digits, `.`, `_` and `-`, starting with a letter. Default `dev`. |
| `--apply-mode-default MODE` | Default of `APPLY_MODE`, the mode stage 6 plans and stage 7 applies: `dry-run`, `create-only`, `amend`, `amend-and-build`, `replace` or `replace-and-build`. Default `dry-run` for Jenkins, `amend` for Tekton. |
| `--default-publish-target TARGET` | Default of `PUBLISH_TARGETS`, and the fallback stage 10 reads when a build has no parameters. Default `datamesh-manager`. Pick the catalog your team publishes to, for example `fluid-command-center`, `horizon`, `datahub` or `collibra`. |
| `--[no-]verify-strict-default` | Jenkins only. Default of `VERIFY_STRICT`. Default `true`. |
| `--[no-]publish-stage-default` | Default of `RUN_STAGE_10_PUBLISH`. Default `false`. |
| `--[no-]publish-include-env` | Jenkins only. Whether stage 10 appends `--env "${FLUID_ENV:-dev}"` to `fluid publish`. Default `true` since 0.16.3. |
| `--[no-]schedule-sync-default` | Default of `RUN_STAGE_11_SCHEDULE_SYNC`. Default `false`. |
| `--scheduler-default {airflow,mwaa,composer,astronomer,prefect,dagster}` | Default of `SCHEDULER`, the scheduler stage 11 syncs to. Default blank, which makes stage 11 a no-op. |
| `--scheduler-destination-default URL` | Default of `SCHEDULER_DESTINATION`: a shared DAG root (`s3://`, `gs://`, `az://`, `ssh://`, `scp://`, `git+ssh://`, `file://` or an absolute path). Stage 11 writes this product into `<root>/<contract id>/` and deletes only there, so several products' pipelines can share one root. |
| `--[no-]diff-last-applied` | Jenkins only. Give stage 5 the plan the last successful build applied (`fluid diff --last-applied`), copied from that build's artifacts, so a schema change the contract makes shows as pending and not as drift. Needs the `copyartifact` plugin. Default off. |
| `--runner-host-override HOST` | The loopback host to use when the pipeline's fluid process runs in a container and the contract says `host: localhost`: `host.docker.internal` (Docker Desktop), the bridge IP (Linux Docker), `host.containers.internal` (Podman) or a Service name (Kubernetes). Written as `FLUID_RUNNER_HOST_OVERRIDE` in the pipeline's environment. |
| `--list-engines` | Print the acquisition and transformation engines the generator recognises, with the pip extras each needs, and exit. |

#### Which systems read which option

As measured on 0.18.1 by generating each system with and without the option and comparing the files:

- **Jenkins and Tekton** render the 11-stage pipeline with parameters. Both read `--fluid-package-spec`, `--fluid-env-default`, `--apply-mode-default`, `--default-publish-target`, `--publish-stage-default`, `--schedule-sync-default`, `--scheduler-default`, `--scheduler-destination-default` and `--no-generate-artifacts`. Both also read `--install-mode` and `--runner-host-override`. Jenkins alone reads `--verify-strict-default`, `--publish-include-env` and `--diff-last-applied` (each left Tekton's files byte-identical when measured on 0.18.1). Tekton with `--complexity basic` renders a three-task pipeline instead; Jenkins rendered the same file for `--complexity basic` and `--complexity enterprise` (the other levels were not compared; measured on 0.18.1).
- **GitLab CI, GitHub Actions, Azure DevOps, Bitbucket and CircleCI** render a single pipeline whose shape follows `--complexity`. The options above that set a parameter default do not change those files, with two exceptions: `--runner-host-override` sets `FLUID_RUNNER_HOST_OVERRIDE` (Jenkins and Tekton set it too), and `--fluid-env-default` sets the fallback of `FLUID_ENV` in some of their commands (not CircleCI's).

#### The generated Jenkinsfile

- **Install.** Stage 0 creates `$WORKSPACE/.fluid-venv` and installs `FLUID_PACKAGE_SPEC` into it, because an agent whose system Python is externally managed (PEP 668) refuses a bare `pip install`. The spec defaults to the version that generated the file, so a Jenkinsfile generated by 0.18.1 installs `data-product-forge[local]==0.18.1` and does not move when a new release ships. Override it per build with the `FLUID_PACKAGE_SPEC` parameter, `FLUID_PIP_INDEX_URL` and `FLUID_PIP_EXTRA_INDEX_URL` (TestPyPI), or `FLUID_ALLOW_PRERELEASE`.
- **Plugins.** `workflow-aggregator` and `git`, plus `copyartifact` with `--diff-last-applied`. The workspace is removed with the core `deleteDir()` step, so the `ws-cleanup` plugin is not needed.
- **The first build.** Jenkins learns a Pipeline's parameters from its first build, so a `buildWithParameters` request to a job that has never run is refused (observed on a Jenkins controller on 4 Oct 2026). Start the job once from the UI with no parameters. The generated file is written for that run: every parameter default is also the fallback each stage reads, so a first build, or the first build after a restart that re-seeds jobs from job-dsl or JCasC, runs what the declarations say. `--fluid-env-default` and `--apply-mode-default` set what that run does.
- **Stage 10.** `fluid publish` receives `--env "${FLUID_ENV:-dev}"` by default, so the catalog gets the contract with the overlay stages 5 to 9 used. Before 0.16.3 `fluid publish` had no `--env`, and the default was off. Pass `--no-publish-include-env` only when the pipeline installs a CLI older than `fluid publish --env`. GitLab CI, GitHub Actions, Azure DevOps and Bitbucket pass `--env "${FLUID_ENV:-dev}"` to `fluid publish` in their default output; the default CircleCI output has no `fluid publish` step.
- **Parameters** include `PUBLISH_TARGETS` (default `datamesh-manager`, or `--default-publish-target`) and `APPLY_MODE` (default `dry-run`, so the first build applies nothing).
- **Regenerate after upgrading.** A committed Jenkinsfile keeps the install, defaults and fallbacks of the version that generated it. Run `fluid generate ci` again and review the diff to pick up changes.

A Command Center holds one record per contract id, and `fluid publish` upserts it, so publishing one contract from two envs leaves the record of whichever published last (measured on 4 Oct 2026, with a contract published from `aws` and from `gcp`). Stage 10 is off by default; `--[no-]publish-stage-default` changes that default per pipeline.

### `fluid generate standard`

Export to data product standards.

```bash
fluid generate standard contract.fluid.yaml --format odps --out ./product.odps.yaml
fluid generate standard --list
```

Key options:

- `contract`
- `--format`, `-f` — **required**. Without it the command prints `Error: --format is required. Use --list to see available formats.` and exits 1. `odps` is the recommended value, not a default.
- `--out`, `-o` — output file. Without it the file is written under `runtime/exports/`. Write a relative path with a directory part (`./product.odps.yaml`): as of 0.18.1, `--out product.odps.yaml` for the `odps` and `odps-bitol` formats fails with `[Errno 2] No such file or directory: ''`.
- `--env`
- `--list`

Supported formats:

| `--format` | What it is | Use it when |
| --- | --- | --- |
| `odps` | **Bitol ODPS v1.0.0** — Open Data Product Standard (center-stage) | Publishing to Entropy Data / Data Mesh Manager. Rich product metadata, lineage, SLA, governance. Preserves FLUID-specific fields under an `x-fluid` namespace. Default file: `runtime/exports/product.odps.yaml`. |
| `odcs` | Open Data Contract Standard (ODCS) v3.1.0 — the Bitol.io standard | Publishing **contract-level** specs (schema, quality, SLA) to Bitol-aligned tooling. Where ODPS describes a whole data product, ODCS focuses on the consumer-facing contract. |
| `odps-v4.1` | LF/ODPI ODPS v4.1 — Open Data Product Specification (opt-in) | ODPI-aligned catalogs that consume the Linux Foundation / Open Data Product Initiative spec. |
| `odps-bitol` | An explicit alias of `odps` | Same output as `odps`, byte for byte, with no warning. Use it to say "Bitol" in a CI log. |
| `opds` | A deprecated alias of `odps-v4.1` | Writes the LF/ODPI v4.1 JSON and prints a deprecation warning. Use `odps-v4.1`. |

### Examples of each format

```bash
fluid generate standard contract.fluid.yaml --format odps        # FLUID -> Bitol ODPS v1.0.0 (center-stage)
fluid generate standard contract.fluid.yaml --format odcs        # FLUID -> ODCS v3.1.0
fluid generate standard contract.fluid.yaml --format odps-v4.1   # FLUID -> LF/ODPI ODPS v4.1 (opt-in)
```

### ODPS environment tuning

The ODPS exporter reads a few environment variables for output shape:

| Env var | Default | Purpose |
| --- | --- | --- |
| `ODPS_INCLUDE_BUILD_INFO` | `true` | Include build information (engine, pattern) |
| `ODPS_INCLUDE_EXECUTION_DETAILS` | `false` | Include execution details (triggers, runtime) |
| `ODPS_TARGET_PLATFORM` | `generic` | Platform-specific tuning (`collibra`, etc.) |
| `ODPS_VALIDATE_OUTPUT` | `true` | Validate the emitted JSON |
| `ODPS_API_VERSION` | `v1.0.0` | Bitol ODPS `apiVersion` to emit. `v1.1.0` opts into the RFC 0029 top-level `type` field (see [`fluid odps-bitol`](./odps-bitol.md)); it stays opt-in until Bitol cuts the v1.1.0 release. |

Formats are deterministic: identical input yields byte-identical output, so the result can be checked into version control.

#### Shortcut — `fluid export-opds` (deprecated alias)

For a one-shot file write of the LF/ODPI ODPS v4.1 JSON:

```bash
fluid export-opds CONTRACT [--env ENV] [--out PATH]
```

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required) |
| `--env ENV` | Apply an environment overlay |
| `--out PATH` | Output file path (default: `runtime/exports/product.odps-v4.1.json`) |

Produces the same output as `fluid generate standard --format odps-v4.1`. The command is a deprecated alias and prints a deprecation warning; prefer `fluid generate standard --format odps-v4.1` in new scripts. (The center-stage `--format odps` emits Bitol ODPS v1.0.0 to `runtime/exports/product.odps.yaml` instead.)

## Examples

```bash
fluid generate transformation
fluid generate transformation contract.fluid.yaml -o ./dbt_project
fluid generate transformation contract.fluid.yaml -o ./dbt_project --dbt-validate
fluid generate schedule contract.fluid.yaml --scheduler airflow -o dags
fluid generate ci --system github
fluid generate standard contract.fluid.yaml --format odps
fluid generate standard contract.fluid.yaml --format odps-v4.1
```

## Compatibility note

[`fluid generate-airflow`](./generate-airflow.md) still works for Airflow generation, but current docs lead with `fluid generate schedule --scheduler airflow`.
