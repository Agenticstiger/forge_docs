# Jenkins CI/CD for FLUID Data Products

Run a data product through validation, planning, apply, verification and publication on Jenkins, with a pipeline the CLI writes for you instead of one you maintain by hand. Each stage is a `fluid` command, so a failed gate stops the build at the stage that found the problem.

This page covers the Jenkins side: generating the Jenkinsfile, setting up the controller and agent, credentials, running the job and what to do when a build fails. What each of the eleven stages checks, with the output each prints, is in [The 11-stage pipeline](./11-stage-pipeline.md). Details below come from the Jenkinsfile that CLI `0.18.1` generates.

## Generate the Jenkinsfile

From the directory that holds `contract.fluid.yaml`:

```bash
fluid generate ci contract.fluid.yaml --system jenkins --out Jenkinsfile
```

```text
[install-mode: pypi] Jenkinsfile written -> Jenkinsfile
  |- Jenkins installs FLUID_PACKAGE_SPEC into $WORKSPACE/.fluid-venv (stage 0)
  |  Override at build time via these Jenkins parameters:
  |    FLUID_PACKAGE_SPEC        = 'data-product-forge==X.Y.Z'  (another version)
  |    FLUID_PIP_INDEX_URL       = 'https://test.pypi.org/simple/'  (TestPyPI)
  |    FLUID_PIP_EXTRA_INDEX_URL = 'https://pypi.org/simple/'   (fallback)
  |    FLUID_ALLOW_PRERELEASE    = true  (pip --pre, alpha/rc releases)
  |- FLUID_PACKAGE_SPEC default: data-product-forge[local]==0.18.1
  |- Jenkins plugins required: workflow-aggregator, git
```

::: warning Do not pair a test or private index with PyPI
pip picks the highest version of a package across every index it is given. With `FLUID_PIP_INDEX_URL` set to TestPyPI and `FLUID_PIP_EXTRA_INDEX_URL` set to PyPI, as the output above suggests, whichever index holds the higher version wins, for `data-product-forge` and for each of its dependencies. Anyone can register a name on TestPyPI, so a pilot build can install a package you did not choose. Run TestPyPI pilots only on an agent that holds no deploy credentials. For private packages, set `FLUID_PIP_INDEX_URL` to one mirror that proxies PyPI and leave `FLUID_PIP_EXTRA_INDEX_URL` empty.
:::

Commit the `Jenkinsfile` beside the contract. The file is generated once and then belongs to you: after you upgrade the CLI, regenerate it and review the diff to pick up changes. The `CONTRACT` parameter defaults to the path you generated from, and `FLUID_PACKAGE_SPEC` to the CLI version that generated the file with the extras the contract and its overlays need. A contract that has an `overlays/gcp.yaml` binding to BigQuery generates `data-product-forge[gcp,local]==0.18.1`; `--fluid-package-spec` overrides it.

## Set up Jenkins

| Where | What it needs |
| --- | --- |
| Controller | the plugins `workflow-aggregator` (Pipeline) and `git`; `copyartifact` only if you generate with `--diff-last-applied` |
| Agent | `python3` with the `venv` module, and `rsync` when the stage-11 destination is a `file://` or `ssh://` path |
| Workspace cleanup | nothing: the Jenkinsfile removes the workspace with the core `deleteDir()` step, so the `ws-cleanup` plugin is not needed |

Stage 0 creates a virtual environment at `$WORKSPACE/.fluid-venv` and installs `FLUID_PACKAGE_SPEC` into it, because agents that follow PEP 668 refuse a bare `pip install`. Every later stage runs the `fluid` from that environment. A private package index goes in the `FLUID_PIP_INDEX_URL` parameter, as one mirror that also proxies PyPI. Leave `FLUID_PIP_EXTRA_INDEX_URL` empty, for the reason in the warning under [Generate the Jenkinsfile](#generate-the-jenkinsfile). `FLUID_ALLOW_PRERELEASE` adds `pip --pre`.

## Create the job

1. In Jenkins choose **New Item**, then **Pipeline** (or **Multibranch Pipeline**).
2. Under **Pipeline**, set **Definition** to **Pipeline script from SCM**, choose **Git**, enter the repository URL and set **Script Path** to `Jenkinsfile`.
3. Save, then run **Build Now** once.

Run that first build with the defaults. Jenkins learns a Pipeline's parameters from a run, so the first build runs with none set; the generated Jenkinsfile gives every parameter a default and every stage reads the same default as its fallback, so the first build is the dry run the defaults describe. Until a job has run once, Jenkins refuses `buildWithParameters` for it (observed on 4 to 5 October 2026 against a controller running a generated pipeline); after that, **Build with Parameters** lists them.

## Give the pipeline credentials

`fluid` reads provider credentials from the environment of the build. The generated Jenkinsfile starts with a comment listing the variables each target reads:

| Target | Variables |
| --- | --- |
| Snowflake | `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE` |
| GCP | `GOOGLE_APPLICATION_CREDENTIALS`, or Workload Identity through OIDC |
| AWS | `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, or an OIDC role |
| Azure | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` |
| Data Mesh Manager | `DMM_API_URL`, `DMM_API_KEY`, only for `fluid publish` |
| Command Center | `FLUID_CC_ENDPOINT`, `FLUID_API_KEY` (sent as `X-API-Key`) and `FLUID_CC_ORG_ID`, for `--target fluid-command-center`; `FLUID_CC_ORG_ID` is optional when the key belongs to exactly one organization |

Surface them to the build with Jenkins credentials. The agent's environment is the other route, and it carries the warning at the end of this section.

**Jenkins credentials (recommended).** Create credentials under **Manage Jenkins**, **Credentials**, then bind them in the Jenkinsfile's `environment {}` block. Jenkins masks a bound value in the console log. `withCredentials([...])` around the steps that need a secret does the same for a narrower scope:

```groovy
environment {
    GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-sa-key')
    FLUID_API_KEY = credentials('command-center-api-key')
}
```

For `GOOGLE_APPLICATION_CREDENTIALS` the credential is a Secret file, which Jenkins exposes as the path of a temporary file. Do not write a key into the Jenkinsfile or into a job parameter. A binding in the pipeline-level `environment {}` is visible to every stage, stage 0's `pip install` included. To keep it out of that stage, bind it in the `environment {}` of the stages that talk to the target, or use `withCredentials`.

Prefer short-lived credentials to stored keys where the cloud offers them: Workload Identity Federation for GCP and an OIDC role for AWS (the generated Jenkinsfile's header comment lists both as alternatives), in place of a service-account key file or an `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` pair that does not expire.

**Agent environment.** Set the variables on the agent: a Docker Compose `environment:`, a Kubernetes agent template, or Jenkins Global Node Properties. `sh` steps inherit them and the Jenkinsfile needs no change.

::: danger Do not put secrets in Global or Node Properties
Jenkins stores Global and Node Properties as plain text in its XML configuration (`config.xml` on the controller), does not mask them in build logs, and gives them to every job that runs on that scope. Never use them for `AWS_SECRET_ACCESS_KEY`, `SNOWFLAKE_PASSWORD` or `FLUID_API_KEY`. If the agent's environment is the route you take, give these pipelines a dedicated agent label (`agent { label '<fluid-agents>' }` in place of the generated `agent any`) and inject the values into that agent from a Kubernetes Secret (`secretKeyRef` in the agent template), not as inline `value:` entries.
:::

Since 0.17.0, a pipeline configured to publish to the Command Center also reports each `fluid apply` run there, with the same credentials; see [Stage 7](./11-stage-pipeline.md#stage-7-apply).

## Run it

The stage toggles are `RUN_STAGE_1_BUNDLE` to `RUN_STAGE_11_SCHEDULE_SYNC`, and `APPLY_MODE` decides what stages 6 to 11 do. Common runs:

| You want | Set |
| --- | --- |
| Review what would change, change nothing | the defaults: `APPLY_MODE=dry-run` |
| Deploy to `dev` and run the builds | `APPLY_MODE=amend-and-build`; `APPLY_BUILD_ID` names the build to run, blank runs every build |
| Deploy additive changes only | `APPLY_MODE=amend` |
| Promote to another environment | `FLUID_ENV=prod`; stage 1 bundles the contract with `overlays/prod.yaml` and every later stage checks it is working on that bundle |
| Replace a table | `APPLY_MODE=replace` or `replace-and-build`; it also needs `ALLOW_DATA_LOSS` unless the environment is `dev` and the target is provably empty |
| Smoke test without publishing | clear `RUN_STAGE_10_PUBLISH` and `RUN_STAGE_11_SCHEDULE_SYNC` |
| Fail on warnings | `VALIDATE_STRICT` (stage 2) and `VERIFY_STRICT` (stage 9), both on by default |

Parameter values reach the shell as environment variables, and the Jenkinsfile builds each command with `set --` so each value stays one argument. A value such as `APPLY_BUILD_ID="x --allow-data-loss"` cannot add a flag.

### One job per environment

`FLUID_ENV` is the overlay the stages pass to `--env`. Generate one pipeline per environment, or one pipeline you run with different `FLUID_ENV` values:

```bash
fluid generate ci contract.fluid.yaml --system jenkins --fluid-env-default prod --out Jenkinsfile.prod
```

The overlay is a file beside the contract, `overlays/<env>.yaml`, that patches the binding. See [Per-environment overlays](../recipes/per-environment-overlays.md), [One contract, two clouds](../recipes/one-contract-two-clouds.md) and [Switch clouds](../recipes/switch-clouds.md). A product applied from two clouds keeps two [OpenTofu states](../concepts/state.md). If two jobs for different clouds both publish the same product, the Command Center keeps whichever published last; see [Stage 10](./11-stage-pipeline.md#stage-10-publish).

### Require approval before apply

The generated Jenkinsfile does not pause for approval. To add a gate, put a Jenkins `input` step before stage 7 and keep the edit in your repository, since regenerating the file removes it:

```groovy
stage('Approve apply') {
    when { expression { params.APPLY_MODE != 'dry-run' && params.FLUID_ENV == 'prod' } }
    steps {
        input message: "Apply ${params.APPLY_MODE} to ${params.FLUID_ENV}?", submitter: 'release-managers'
    }
}
```

Stage 7 only applies a plan whose digests match the bundle, so what the approver reviewed in `runtime/plan.html` is what runs.

## What the build keeps

Each stage archives its output with `archiveArtifacts`, so a failed build leaves the evidence:

| Stage | Archived |
| --- | --- |
| 1 | `runtime/bundle.tgz`, fingerprinted |
| 2 | `runtime/validate-report.json` |
| 3 | `dist/artifacts/**/*` |
| 4 | `runtime/validate-artifacts-report.json` |
| 5 | `runtime/diff-report.json` |
| 6 | `runtime/plan.json`, `runtime/plan.html` |
| 7 | `runtime/apply-report.html`, and the run records under `.fluid/runs/` that a `*-and-build` mode writes |
| 8 | `runtime/policy-apply-report.json` |
| 9 | `runtime/verify-report.json` |
| 10 | `runtime/publish-report.json` |
| 11 | `runtime/schedule-sync-report.json` |

The workspace is deleted at the end of every build, so nothing carries over except the archived files. Stages read the bundle from the same build's workspace.

## Troubleshooting

These messages are the ones the generated Jenkinsfile prints.

**`stage 0: the CLI first on PATH is ..., not the one in $FLUID_VENV: the PATH entry of environment {} did not apply`**
Something replaced `PATH` after the `environment {}` block, so the stages would run a different `fluid` from the one stage 0 installed. Remove the override, or put `$WORKSPACE/.fluid-venv/bin` first in it.

**`stage N reads runtime/bundle.tgz, which stage 1 writes: run stage 1 in the same build`**
`RUN_STAGE_1_BUNDLE` was cleared. Stages 2, 3, 5, 6, 7 and 9 read the bundle, and the workspace does not persist between builds, so stage 1 has to run in the same build.

**`FLUID_ENV must be a plain environment name`**
`FLUID_ENV` may contain letters, digits, `.`, `_` and `-`, and may not start with `.` or `-`. Stage 0 exits 2 otherwise.

**`APPLY_BUILD_ID is not passed on: APPLY_MODE amend runs no build`**
This is a notice, not an error. Only `amend-and-build` and `replace-and-build` run builds, and only they take `--build-id`.

**Stage 5 fails on a pipeline that was green before an upgrade.**
Since 0.16.3 the drift gate compares live targets. See [Stage 5](./11-stage-pipeline.md#stage-5-diff-drift-gate) for the statuses and what counts as drift.

**Stages 9 to 11 print `stage 7 ran as a dry run ... skipped`.**
`APPLY_MODE` is `dry-run`, the default. Nothing was applied, so there is nothing to verify, publish or schedule. Stage 8 does not skip: after a dry run it prints that the bindings are checked, not enforced, and runs `policy-apply` with `--mode check`.

## Hand-written pipelines

A hand-written Jenkinsfile that calls `fluid` directly is the other way to do this: [Universal pipeline](./universal-pipeline.md) shows one that carries no provider-specific logic. The generated pipeline adds the bundle chain, the digest checks between stages and the first-build defaults.

## Related

- [The 11-stage pipeline](./11-stage-pipeline.md)
- [Operating in CI](../advanced/operating-in-ci.md)
- [`fluid generate ci`](../cli/generate.md)
- [Declarative Airflow](./airflow-declarative.md)
