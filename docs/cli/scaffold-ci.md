# `fluid scaffold-ci`

Generate a single-file CI pipeline for GitLab, GitHub Actions, or Jenkins that wires together the FLUID validate / generate / plan / test / apply / publish steps.

For the 11-stage pipeline (bundle, artifacts, drift check, policy apply, verify, schedule sync), use [`fluid generate ci`](./generate.md#fluid-generate-ci) instead. `scaffold-ci` writes the short form.

## Syntax

```bash
fluid scaffold-ci CONTRACT [--system {gitlab,github,jenkins}] [--out PATH]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required). |
| `--system` | CI system to target — `gitlab` (default), `github`, or `jenkins`. |
| `--out` | Output path for the generated pipeline file (default `.gitlab-ci.yml`). |

## Examples

```bash
fluid scaffold-ci contract.fluid.yaml
fluid scaffold-ci contract.fluid.yaml --system github --out .github/workflows/fluid.yml
fluid scaffold-ci contract.fluid.yaml --system jenkins --out Jenkinsfile
```

## What the pipeline runs

The generated file installs `data-product-forge` from PyPI (`pip install --quiet data-product-forge`, unpinned) and runs `fluid` commands, in this order:

| Stage | Command |
| --- | --- |
| validate | `fluid validate $CONTRACT` |
| generate | `fluid generate speed-transformation` and `fluid generate schedule`, which discover `contract.fluid.yaml` in the working directory. The dbt project and the DAGs are kept as artifacts. |
| plan | `fluid --provider $PROVIDER plan $CONTRACT --out runtime/plan.json` |
| test | `fluid contract-tests $CONTRACT` |
| apply | When `BUILD_ID` is set: `fluid apply $CONTRACT --mode amend-and-build --build-id $BUILD_ID --yes`. Otherwise `fluid apply runtime/plan.json --yes`. |
| deploy | On `main` with `AIRFLOW_DAGS_DEST` set: `rsync` the `dags/` directory to it. |
| publish | On `main` with `DMM_API_URL` set: `fluid publish $CONTRACT --catalog $CATALOG`. |

The settings are `CONTRACT` (the path you passed), `PROVIDER` (default `default`), `BUILD_ID` (default empty; set it to a `builds[].id` to run that build), `CATALOG` (default `datamesh-manager`), `AIRFLOW_DAGS_DEST` and `DMM_API_URL`. GitLab reads them as CI/CD variables, GitHub Actions as `env`, repository `vars` and `secrets`, Jenkins from the `environment` block.

::: warning Set `PROVIDER` before the first run
`fluid` checks the global `--provider` value against the providers it has registered (`aws`, `datamesh_manager`, `gcp`, `local`, `redshift`, `snowflake`). As of 0.18.1 the generated default `PROVIDER=default` is not one of them, so the plan stage fails:

```text
⚠️ Unknown provider 'default' — installed providers: aws, datamesh_manager, gcp, local, redshift, snowflake (see `fluid providers`)
```

and exits 2. Set `PROVIDER` to the provider your contract targets (`local`, for example, runs the plan against DuckDB).
:::

## Notes

- The `apply` stage is gated: `manual` in GitLab, `workflow_dispatch` in GitHub Actions, and an `input` step on the `main` branch in Jenkins.
- The publish job uses `--catalog`, which `fluid publish` marks deprecated in favour of `--target`. Edit the job to `--target $CATALOG` for new pipelines.
- The default `--out` value is `.gitlab-ci.yml` regardless of `--system`; pass `--out` explicitly when targeting GitHub or Jenkins.
- The Jenkins file cleans the workspace with `cleanWs()`, which needs the Workspace Cleanup plugin. [`fluid generate ci --system jenkins`](./generate.md#the-generated-jenkinsfile) uses the core `deleteDir()` step instead.
- For producing the FLUID artifacts the pipeline drives, see [`fluid generate`](./generate.md), [`fluid plan`](./plan.md), and [`fluid apply`](./apply.md).
