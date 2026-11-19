# Operating in CI

Runbook for running fluid pipelines unattended on Jenkins, GitHub Actions, GitLab CI or any other runner. The commands and file contents below were generated or run with CLI 0.18.1 from the `fluid init --quickstart` contract.

::: tip Companion page
When a stage fails, [Production troubleshooting](./production-troubleshooting.md) has the symptom, diagnosis and fix for each error the stages raise.
:::

## Generate a pipeline

```bash
fluid generate ci contract.fluid.yaml --system jenkins --out Jenkinsfile
```

```text
[install-mode: pypi] Jenkinsfile written -> Jenkinsfile
  |- Jenkins installs FLUID_PACKAGE_SPEC into $WORKSPACE/.fluid-venv (stage 0)
  ...
  |- FLUID_PACKAGE_SPEC default: data-product-forge[local]==0.33.0
  |- Jenkins plugins required: workflow-aggregator, git
```

The other systems:

```bash
fluid generate ci                          # GitLab CI (default)
fluid generate ci --system github          # GitHub Actions
fluid generate ci --system azure           # Azure DevOps
fluid generate ci --system bitbucket       # Bitbucket Pipelines
fluid generate ci --system circleci        # CircleCI
fluid generate ci --system tekton          # Tekton (writes tekton/*.yaml)
```

The templates are not the same pipeline. The Jenkins template runs the stages described next (a stage 0 bootstrap, then stages 1-11), and the Tekton template generates the same eleven stages as tasks in `tekton/tasks.yaml`, with `APPLY_MODE` defaulting to `amend` where Jenkins defaults to `dry-run`. The tables below are Jenkins's. Generated with the default `standard` complexity, the GitHub Actions workflow runs `fluid doctor`, `fluid validate`, `fluid generate speed-transformation` and `fluid generate schedule`, a plan with `--check-sovereignty`, tests, and per-environment `fluid apply`, `fluid policy-apply`, `fluid verify` and `fluid contract-tests`. The GitLab file runs validation, `fluid test`, the two generate commands, the same plan, `fluid apply` and `fluid publish`. Neither of those two has a bundle, diff or schedule-sync stage. Open the generated file for the commands a given system runs. That is the 0.30.1 output. *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* Every system gets the same wrapper instead, described in [What a generated pipeline runs](#what-a-generated-pipeline-runs).

::: warning Check the GitHub and GitLab deploy steps before you use them
As of 0.18.1, the per-environment deploy step in those two templates is written `FLUID_ENV=<env> if [ -n "$BUILD_ID" ]; then fluid apply ...; else ...; fi`. `bash` and `sh` both reject that with a syntax error (`near unexpected token 'then'`), and `fluid apply` does not read `FLUID_ENV`, so the environment is not selected by it. Pass `--env <env>` to the stage commands, as the Jenkins template does.
:::

## What a generated pipeline runs

*(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* `fluid generate ci` writes a thin wrapper for each of the 7 systems. GitHub Actions and Jenkins run each stage as a step, `fluid ship [<contract>] --stage <N>`. The other systems run `fluid ship --stage 1-6` in the plan job and `fluid ship --stage 7-11` in the apply job, and ship prints a section per stage. So the 11 stages have one implementation, [`fluid ship`](../cli/ship.md), and the CI file holds the triggers, the gates and the install. No run-time value appears in a script body: values reach ship through the job environment, and only the contract path is written into the commands. The Jenkins stage table below is the 0.30.1 file; in 0.31.0 each of its commands is that `fluid ship` call.

- A pull request or merge request runs stages 1 to 6 (bundle through plan) and keeps `runtime/`, the bundle, the reviewed plan and the reports, as an artifact.
- A push to the default branch, or a manual run on it, also runs stages 7 to 11 in a second job, behind the system's own gate. A pull request never reaches stages 7 to 11 on any system, and a manual run on another branch plans only, with two exceptions: Tekton has no branch rule (nothing starts `fluid-apply` but you), and a Jenkins job that builds no branch (not a multibranch job) applies after the approval.
- `--default-branch BRANCH` names that branch. Without it, the generator uses the remote's default branch (`origin/HEAD`), else `main`. GitLab CI reads the project's own default branch (`$CI_DEFAULT_BRANCH`) instead.

| System | Gate before stages 7 to 11 |
| --- | --- |
| GitHub Actions | The `apply` job runs in an `environment:` named after `FLUID_ENV` (`dev` unless set). Give that environment required reviewers under Settings > Environments, or nothing waits for a person. One apply per environment runs at a time. |
| GitLab CI | `fluid-apply` is a manual job with `environment` and `resource_group`, on the default branch only, so someone starts it. Protect the environment under Settings > CI/CD > Protected environments to choose who may. |
| Jenkins | An `input` approval (`APPLY_APPROVAL`, default `true`; set it to `false` for an unattended job), then a `milestone`, then a per-environment `lock`. A change request (pull request build) stops after stage 6. |
| Azure DevOps | A deployment job in the Azure DevOps environment named after `FLUID_ENV`. Add approvals and checks under Pipelines > Environments. A scheduled run (one you add under Triggers for the add-ons) plans and applies nothing. |
| Bitbucket Pipelines | A manual `deployment` step that someone starts. The step's `deployment` is written from `--fluid-env-default` when the file is generated: `dev` or `test` gives `test`, `staging` or `stage` gives `staging`, anything else gives `production`. A `FLUID_ENV` set at run time does not change it. The custom pipeline runs the plan only (stages 1 to 6) and cannot apply from any branch. |
| CircleCI | An `approve-apply` hold job on the default branch: press Approve in the CircleCI UI. |
| Tekton | A separate `fluid-apply` Pipeline that nothing starts by itself. Start it on the same workspace as the plan, with the plan run's name as `FLUID_RUN_ID`, and limit who may create its PipelineRuns with RBAC. |

The Jenkins file needs the plugins `workflow-aggregator`, `git`, `lockable-resources` and `junit`, plus `copyartifact` with `--diff-last-applied`.


### Where each value comes from

The `RUN_STAGE_<N>_<NAME>` switches and the stage knobs (`APPLY_MODE`, `FLUID_ENV`, `PUBLISH_TARGETS`, `VALIDATE_STRICT` and the rest; [Stage switches and knobs](../cli/ship.md#stage-switches-and-knobs) lists them) come from:

- GitHub Actions, GitLab CI and Bitbucket: a manual run's input, then the repository or project variable of the same name, then the default written in the file. *(since 0.33.0, [forge-cli #987](https://github.com/Agenticstiger/forge-cli/pull/987))* GitLab CI's file has a Run pipeline form of `spec:inputs` instead, and there a project variable of the same name overrides the form's input, so do not set one for a value you want to choose per run: see [GitLab CI: form, release packet and impact report](#gitlab-ci-form-release-packet-and-impact-report). On GitHub Actions a manual run's switch is a `default | true | false` choice, so leaving it at `default` keeps the repository's setting.
- Azure DevOps, CircleCI, Jenkins and Tekton: a pipeline parameter, then its default.

`FLUID_PACKAGE_SPEC`, `FLUID_PIP_INDEX_URL`, `FLUID_PIP_EXTRA_INDEX_URL` and `FLUID_ALLOW_PRERELEASE` are never a run-time input on GitHub Actions, GitLab CI, Azure DevOps, Bitbucket or CircleCI. Whoever starts a run could otherwise choose the package that the apply job installs, with its deploy credentials. Set them as repository or project variables. Without them, the install uses the version that generated the file. Jenkins and Tekton still take these four as build parameters. GitLab CI's Run pipeline form takes any variable, so keep Settings > CI/CD > Variables > Minimum role to use pipeline variables at Maintainer or No one allowed: whoever may set pipeline variables can pass `FLUID_PACKAGE_SPEC` to a run. No one allowed is GitLab.com's default for new projects, and Maintainer is the default on self-managed GitLab. In 0.33.0 the form is `spec:inputs` and needs no pipeline variables, so set the minimum role to No one allowed ([forge-cli #987](https://github.com/Agenticstiger/forge-cli/pull/987)).

### GitLab CI: form, release packet and impact report

*(since 0.33.0, [forge-cli #987](https://github.com/Agenticstiger/forge-cli/pull/987))* The file that `fluid generate ci --system gitlab` writes has three jobs, `fluid-plan`, `fluid-impact` and `fluid-apply` (an add-on adds one more), and declares a `spec:inputs` header.

- **Run pipeline form (GitLab 17.11 or later).** The header declares 20 inputs, which is GitLab's limit: the 11 stage switches (`run_stage_1_bundle` to `run_stage_11_schedule_sync`) and nine knobs, `fluid_env`, `apply_mode`, `allow_data_loss`, `no_verify_digest`, `validate_strict`, `verify_strict`, `publish_targets`, `scheduler` and `schedule_sync_dry_run`. An input sets the job variable of the same name in upper case, and no input is written into a script. Every other value the file sets (the scheduler destination, `GENERATE_EMIT` and the like) is a plain default under `variables:`, which a project CI/CD variable sets. The file's header says a project variable of the same name overrides an input.
- **Inputs are closed.** Each takes a list of options or a pattern, which GitLab checks when the pipeline is created. `fluid_env` matches `^[A-Za-z][A-Za-z0-9_.-]{0,63}$`, `publish_targets` is blank or target names separated by single spaces (letters, digits, `_`, `.` and `-`), `scheduler` is one of `airflow`, `mwaa`, `composer`, `astronomer`, `prefect`, `dagster` or blank, and `validate_strict` and `verify_strict` are `true`, `false` or blank. GitLab expands a `$NAME` in a variable's value, so free text could otherwise copy another variable into a job log or an environment name.
- **Release packet.** On the default branch (`$CI_DEFAULT_BRANCH`), `fluid-plan` runs `fluid ship --stage 1-6 --release-dir release`, and `fluid-apply` downloads that job's artifacts and nothing else (`needs` and `dependencies` both name `fluid-plan`). `fluid-apply` stops with `fluid-plan published no release packet: nothing to apply` unless `release/release.json` exists, then runs `fluid ship --stage 7-11 --yes`. The packet needs stages 1 to 4 to run and `release/` not to be in the repository. Otherwise `fluid ship` refuses, and `fluid-plan` fails with its reason:

  ```text
  fluid ship: --release-dir needs stages 1-4 (bundle to validate-artifacts) in this invocation, and stage 3 generate-artifacts does not run (RUN_STAGE_3_GENERATE_ARTIFACTS=false)
  fluid ship: --release-dir <path>/release already exists: a release goes into a new directory, never one an earlier run wrote
  ```

  [Publishing a release](../cli/ship.md#publishing-a-release) lists what the directory holds. The pipeline runs `--release-dir`, so the version that `FLUID_PACKAGE_SPEC` installs must have it: 0.32.0 stops with `unrecognized arguments: --release-dir`, so on the default branch `fluid-plan` fails. A merge-request plan still passes there, but `fluid-impact` needs `fluid diff --impact`, which 0.32.0 also lacks, so that job fails without blocking the merge.
- **Merge requests.** A merge request runs `fluid-plan` without a packet and never gets `fluid-apply`, and neither does any other ref than the default branch.
- **`fluid-impact`.** A merge request also runs this job after `fluid-plan`. It fetches the merge request's base commit and runs `fluid diff CONTRACT --baseline <the contract at the base> --impact --plan runtime/plan.json --format markdown` (without `--plan` if `runtime/plan.json` is missing), so the report names what the change reaches, as in the [impact report](../cli/diff.md#impact-report-for-a-pull-request). It writes `runtime/impact/impact.md` and `impact.json`, and GitLab links the `runtime/impact/` directory as "fluid impact". If the contract does not exist at the base, the job writes only `impact.md`, with one line that says so, and passes. The job runs on `python:3.12`, pinned by digest, because it needs `git`, and it is `allow_failure`, so a failed report does not block the merge. Its resource section reads `unknown`, with the reason, because stage 6 does not save an OpenTofu plan. Its consumers list is searched only when a committed `fluid.workspace.yaml` sits in the contract's directory or above it.
- **A plan that fails.** `fluid-plan` removes `runtime/bundle.tgz`, `runtime/plan.json`, `runtime/plan.tfplan`, `runtime/plan.tfplan.json`, `runtime/plan.gitlab-tofu.json`, `dist/artifacts/` and `release/` before its artifacts are uploaded, and prints `fluid-plan did not pass: its reports are kept, its bundle, plan and artifacts are not`. The reports, the JUnit file and the bundle's provenance file stay as evidence, and no `release/` is uploaded.

### Container images

*(since 0.33.0, [forge-cli #1000](https://github.com/Agenticstiger/forge-cli/pull/1000))* A generated pipeline that names a container image pins it by digest, as `<tag>@sha256:<index digest>`, the way the GitHub actions are pinned by commit. A tag can move to another image, and the digest cannot. The images are:

| System | Image |
| --- | --- |
| GitLab CI | `python:3.12-slim` for every job but `fluid-impact`, and `python:3.12` for `fluid-impact` |
| Bitbucket Pipelines | `python:3.12-slim` |
| CircleCI | `cimg/python:3.12` |
| Tekton | `python:3.12-slim` for every Task, or the image `--image` sets |

GitHub Actions and Azure DevOps use the runner's own image, and Jenkins the agent's. The digest in a file is the one that was current when forge-cli wrote it, so a file you generated earlier keeps its image until you generate it again.

### Add-ons

`--add security`, `--add compliance` and `--add sbom` (repeatable) add the jobs that the advanced and enterprise tiers carried:

- **`security`**: `fluid policy-check contract.fluid.yaml --strict` and an OSV-Scanner scan. On GitHub Actions it runs daily, on pull requests and on pushes to the default branch, and uploads the result to code scanning. On the other systems it is a job or stage beside the plan (Tekton: its own Pipeline), and the OSV scan runs only when `osv-scanner` is on the runner: the default images do not have it.
- **`compliance`**: a policy report (`runtime/compliance-report.json`) and a lineage check, `fluid verify contract.fluid.yaml --reconcile-lineage --warn-only`, which reaches the cloud. GitHub Actions runs it weekly. GitLab CI runs it on a schedule you create or a pipeline run by hand, CircleCI on a scheduled pipeline or with the `run_compliance` parameter, Azure DevOps on a manual or scheduled run, Bitbucket as the custom pipeline `fluid-compliance`, and Jenkins as a stage after apply on the default branch.
- **`sbom`**: on GitHub Actions, an SPDX SBOM from anchore with an attestation, weekly. On the other systems, `syft` on the default branch when the runner has it. Without `syft`, or when it fails, the job prints that no SBOM was written, and the run carries on.

GitHub Actions writes each add-on to its own workflow (`fluid-security.yml`, `fluid-compliance.yml`, `fluid-sbom.yml`), each with its own schedule. Tekton writes a Pipeline named `fluid-<add-on>`, and the other systems add a job or stage; a schedule there is one you create. Each add-on that runs fluid installs it first. The 0.30.1 security and compliance workflows never did.

### What was run

Only GitHub Actions ran live, on a private scratch repository with `FLUID_PACKAGE_SPEC` set to the branch: a push ran plan and then apply as a deployment to `dev`; a pull request, and a manual run on another branch, ran plan only; a manual run left at its defaults took the repository's variables, and its inputs overrode them. The GitHub files also pass actionlint and zizmor. The GitLab and CircleCI files are checked against the published schemas, and the Azure DevOps, Bitbucket, Tekton and Jenkins files by structure. No generated file for those systems was run on its service. The GitLab file on `main` was not run on GitLab either. Its `fluid ship --release-dir` line, the `fluid-impact` lines and the cleanup after a failed plan were run on their own in a quickstart project, with forge-cli at [#987](https://github.com/Agenticstiger/forge-cli/pull/987).

### Files the old tiers left

On GitHub Actions the file is `.github/workflows/fluid-pipeline.yml`. Earlier tiers wrote `fluid-basic.yml`, `fluid-standard.yml`, `fluid-advanced.yml` or `fluid-enterprise.yml`, and the enterprise tier wrote `security.yml` and `compliance.yml`. Those files keep running beside the new one until you delete them. `fluid generate ci` and `fluid forge` name each one they find, and delete nothing:

```text
These files are from an earlier fluid generate ci and still run beside the new
pipeline; delete them: .github/workflows/fluid-standard.yml,
.github/workflows/security.yml
```

## The Jenkins pipeline: stages 1-11

Stage 1 writes `runtime/bundle.tgz` for one environment. Stages 2, 3, 5, 6, 7 and 9 read that bundle and pass the same `--env`, so every stage works on the bytes stage 1 produced. If a stage runs without the bundle, it stops and says so.

| # | Stage | Command in the generated Jenkinsfile | What it gates |
|---|---|---|---|
| 1 | Bundle | `fluid bundle "$CONTRACT" --env "$FLUID_ENV" --format tgz --out runtime/bundle.tgz` | Deterministic tgz with `MANIFEST.json`, per-file SHA-256 and a merkle root. *(since 0.33.0, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972))* It also packs the dbt project of each dbt build, so run `fluid generate dbt-tests` first |
| 2 | Validate | `fluid validate runtime/bundle.tgz --env "$FLUID_ENV" --report runtime/validate-report.json --strict` | The bundled contract against its schema (`--strict` is the `VALIDATE_STRICT` parameter) |
| 3 | Generate artifacts | `fluid generate artifacts runtime/bundle.tgz --env "$FLUID_ENV" --contract-path "$CONTRACT" --out dist/artifacts/ --emit ...` | ODCS, ODPS-Bitol, schedule and policy artifacts under `dist/artifacts/`. *(since 0.33.0, [forge-cli #979](https://github.com/Agenticstiger/forge-cli/pull/979))* Each Spark build's `job.json` too |
| 4 | Validate artifacts | `fluid validate-artifacts dist/artifacts/ --manifest dist/artifacts/MANIFEST.json --report runtime/validate-artifacts-report.json` | Generated artifacts match their manifest. Skipped when `dist/artifacts/MANIFEST.json` does not exist |
| 5 | Diff (drift gate) | `fluid diff runtime/bundle.tgz --env "$FLUID_ENV" --out runtime/diff-report.json --exit-on-drift` | The bundled contract against the live target. Exit 0 when there is no drift, 1 on drift, 2 when a target could not be read. [`--diff-last-applied`](#fluid-generate-ci-options) keeps a contract change you have not applied from reading as drift; see [`fluid diff`](../cli/diff.md) |
| 6 | Plan | `fluid plan runtime/bundle.tgz --env "$FLUID_ENV" --mode "$APPLY_MODE" --out runtime/plan.json --check-sovereignty` | `plan.json` with `bundleDigest` and `planDigest`; a strict sovereignty violation fails here, before any cloud is touched (see [sovereignty enforcement modes](./governance.md#sovereignty-enforcement-modes-since-0-15-0)) |
| 7 | Apply | `fluid apply runtime/plan.json --bundle runtime/bundle.tgz --mode "$APPLY_MODE" --env "$FLUID_ENV" --yes --ensure-opentofu --report runtime/apply-report.html` | Re-verifies both digests, then executes (see [plan binding](#plan-binding-the-integrity-chain)) |
| 8 | Policy apply | `fluid policy-apply dist/artifacts/policy/bindings.json --mode enforce` | IAM and GRANT bindings; skipped when the file does not exist |
| 9 | Verify | `fluid verify runtime/bundle.tgz --env "$FLUID_ENV" --out runtime/verify-report.json --strict` | Deployed state matches the bundle |
| 10 | Publish | `fluid publish "$CONTRACT" --env "$FLUID_ENV" --format json --target=<catalog>` | Catalog registration, one `--target` per name in `PUBLISH_TARGETS`. Off by default |
| 11 | Schedule sync | `fluid schedule-sync --scheduler "$SCHEDULER" --dags-dir dist/artifacts/schedule/ --env "$FLUID_ENV" --delete-scope product` | Generated DAGs pushed to the scheduler. Off by default; takes no contract argument |

The mode is a build parameter and defaults to **`dry-run`** on Jenkins. Stage 6 plans with it and stage 7 applies with it, so the plan is for the mode that is applied. After a dry-run apply, stage 8 downgrades to `--mode check`, and stages 9, 10 and 11 print that stage 7 applied nothing and skip. To deploy, run with `APPLY_MODE` set to `amend` or `amend-and-build`.

`--build-id` is passed to apply only for `amend-and-build` and `replace-and-build`, from `APPLY_BUILD_ID` (blank runs every build). With any other mode the stage prints that `APPLY_BUILD_ID` is not passed on and carries on. Calling `fluid apply` by hand with `--build-id` and a mode that runs no build is refused with `apply_build_id_requires_build_mode`. *(since 0.27.0, [forge-cli #808](https://github.com/Agenticstiger/forge-cli/pull/808))* An `APPLY_BUILD_ID` that matches none of the contract's builds fails stage 7 with `apply_build_id_not_found` before it applies anything.

::: details Stage 3 and fragment-layout contracts
Stage 3 reads the bundle, not the contract file. As of 0.18.1, `fluid generate artifacts contract.fluid.yaml` on a fragment-layout contract (one whose `exposes` come from `$ref` files) without `--env` fails with `Provider error: FLUID expose has no usable name`. With `--env`, or given the stage-1 bundle, it succeeds. The generated pipeline uses the bundle, so it is not affected; a hand-written step that passes the contract path is.
:::

On 0.18.0, stage 5 refused a BigQuery binding whose project was written `{{ env.NAME }}` and failed `--exit-on-drift` on every build; 0.18.1 resolves it before reading the target. <!-- cli-version: historical -->

### Parameters

The parameters in the table below have defaults, and the stages that read them use the same default as their shell fallback. A job's first build, and its first after a restart that re-seeds jobs from job-dsl or JCasC, run with no parameters exported and still behave correctly.

| Parameter | Default | Purpose |
|---|---|---|
| `CONTRACT` | the path you generated from | Contract path relative to the workspace |
| `FLUID_ENV` | `dev` | Environment overlay every stage passes to `--env`. A plain name of letters, digits, `.`, `_` and `-`, not starting with `.` or `-` |
| `APPLY_MODE` | `dry-run` | `dry-run`, `amend`, `create-only`, `amend-and-build`, `replace`, `replace-and-build` |
| `APPLY_BUILD_ID` | a build id from the contract | Build that an `*-and-build` mode runs; blank runs every build |
| `APPLY_APPROVAL` | `true` | *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* Stages 7 to 11 wait for a person to approve the reviewed plan (an `input` step). `false` for an unattended job |
| `ALLOW_DATA_LOSS` | `false` | Passes `--allow-data-loss`; required for `replace*` outside `dev` or when the target has rows |
| `NO_VERIFY_DIGEST` | `false` | Passes both `--no-verify-plan-binding` and `--no-verify-federation`. A disaster-recovery hatch |
| `RUN_STAGE_<N>_<NAME>` | on, except stages 10 and 11 | One toggle per stage |
| `PUBLISH_TARGETS` | `datamesh-manager` | Space-separated catalog names; not endpoints |
| `SCHEDULER`, `SCHEDULER_DESTINATION`, ... | blank | Stage 11 target. Blank means no-op |
| `FLUID_PACKAGE_SPEC` | the generating version, with extras | Package spec stage 0 installs |

Jenkins learns a job's parameters from its first build. As measured on a Jenkins controller on 4 October 2026, `buildWithParameters` is refused for a job that has never run, so run one plain build first.

### Install

Stage 0 creates `$WORKSPACE/.fluid-venv`, because agents that follow PEP 668 refuse a bare `pip install`, and installs `FLUID_PACKAGE_SPEC` into it. The default is the version that generated the file with the extras the contract's base and overlays need, for example `data-product-forge[local]==0.33.0`. Every stage then runs `fluid` from that venv, and stage 0 fails if the first `fluid` on `PATH` is another one. The agent needs `python3` with the `venv` module, and `rsync` for a `file://` or `ssh://` stage 11 destination. The workspace is removed with Jenkins's core `deleteDir()`, so the `ws-cleanup` plugin is not needed.

Pin a different version at build time with `FLUID_PACKAGE_SPEC=data-product-forge==X.Y.Z`. `FLUID_PIP_INDEX_URL` (blank means PyPI), `FLUID_PIP_EXTRA_INDEX_URL` and `FLUID_ALLOW_PRERELEASE` (`true` adds `pip --pre`) cover TestPyPI pilots and private mirrors. With `--install-mode dev-source` the file installs from a `/forge-cli-src` bind mount and fails if the mount is missing; it never falls back to PyPI.

::: warning Do not pair a test or private index with PyPI
pip picks the highest version of a package across every index it is given, so `FLUID_PIP_EXTRA_INDEX_URL` lets a second index outvote the first for `data-product-forge` and for each of its dependencies. Anyone can register a name on TestPyPI. For private packages, set `FLUID_PIP_INDEX_URL` to one mirror that proxies PyPI and leave `FLUID_PIP_EXTRA_INDEX_URL` empty. Run TestPyPI pilots only on an agent that holds no deploy credentials.
:::

A committed Jenkinsfile keeps what it was generated with. Regenerate it after upgrading the CLI to pick up newer stage logic.

### `fluid generate ci` options

| Flag | Purpose |
|---|---|
| `--system` | The CI system. Default `gitlab` |
| `--complexity {basic,standard,advanced,enterprise}` | 0.30.1: `basic` is validate and apply; `standard` is the default; `advanced` adds multiple environments and approvals; `enterprise` adds governance and compliance. Exits 2 in 0.33.0: use `--add` |
| `--add {security,compliance,sbom}` | *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* Repeatable. Add a job beside the pipeline: a daily scan, a weekly compliance report and lineage check, or an SBOM. See [Add-ons](#add-ons). In 0.31.0, `--complexity` exits 2 and points here |
| `--default-branch <branch>` | *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* The branch whose pushes run stages 7 to 11. Default: the remote's default branch (`origin/HEAD`), else `main`. GitLab CI reads its own `$CI_DEFAULT_BRANCH` |
| `--out <path>` | Output path, for single-file systems |
| `--no-generate-artifacts` | Turn stage 3 off by default, so stage 4 has nothing to check. Through 0.32.0 it was also set for reference-only contracts, detected from `builds[].pattern`. *(since 0.33.0, [forge-cli #1000](https://github.com/Agenticstiger/forge-cli/pull/1000))* It only turns stage 3's default off, and nothing infers it: a contract with reference builds, or only reference builds, still runs stage 3, because `fluid generate artifacts` writes the policy bindings and schedule that stages 4, 8 and 11 read |
| `--install-mode {pypi,dev-source}` | 0.30.1: how the Jenkinsfile installs fluid; other systems ignore it. *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* Every system reads it: `dev-source` imports fluid from a `/forge-cli-src` bind mount and fails if the mount is missing. *(since 0.33.0, [forge-cli #1000](https://github.com/Agenticstiger/forge-cli/pull/1000))* `dev-source` runs `pip install -e /forge-cli-src`, which puts `fluid` on `PATH`, instead of exporting `PYTHONPATH`. On the six other systems it stops with a `FATAL` line when `/forge-cli-src/pyproject.toml` is missing, and when the install fails. The runner needs a package index, or `setuptools` and `setuptools-scm` installed with `PIP_NO_BUILD_ISOLATION=0` (pip reads it inverted). Jenkins keeps the agent's installed `fluid` with `PYTHONPATH=/forge-cli-src`. In 0.32.0 every other system exported `PYTHONPATH=/forge-cli-src` in the install step, which ended with the step and provided no `fluid` command, so the install step failed at `fluid --version`. |
| `--image IMAGE` | *(since 0.33.0, [forge-cli #1000](https://github.com/Agenticstiger/forge-cli/pull/1000))* Tekton only: the image the Task steps run. Default `python:3.12-slim`, pinned by digest. It takes `[registry[:port]/]name[:tag][@sha256:<digest>]`, and a value that is not an image reference is refused with `generate_ci_invalid_option`. Pin yours by digest too (`name:tag@sha256:<digest>`): a tag can move. Another system refuses the flag with `generate_ci_image_unsupported`. |
| `--fluid-package-spec <spec>` | Default of `FLUID_PACKAGE_SPEC` |
| `--fluid-env-default <env>` | Default of `FLUID_ENV` and the fallback every stage uses. Default `dev` |
| `--apply-mode-default <mode>` | Default of `APPLY_MODE`: `dry-run` for Jenkins, `amend` for the other systems |
| `--default-publish-target <name>` | Default of `PUBLISH_TARGETS` and the fallback stage 10 reads. Default `datamesh-manager` |
| `--publish-stage-default`, `--no-publish-stage-default` | Default of `RUN_STAGE_10_PUBLISH`. Off unless set |
| `--publish-include-env`, `--no-publish-include-env` | 0.30.1: whether stage 10 passes `--env` to `fluid publish`. On unless disabled. *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* Removed: ship always passes `--env` |
| `--verify-strict-default`, `--no-verify-strict-default` | Default of `VERIFY_STRICT`. On unless disabled |
| `--schedule-sync-default`, `--no-schedule-sync-default` | Default of `RUN_STAGE_11_SCHEDULE_SYNC`. Off unless set |
| `--scheduler-default {airflow,mwaa,composer,astronomer,prefect,dagster}` | Default of `SCHEDULER`. Blank means no-op |
| `--scheduler-destination-default <url>` | Default of `SCHEDULER_DESTINATION`, a shared DAG root. Stage 11 writes `<root>/<contract id>/` and deletes only there, so every product's pipeline can share one root |
| `--diff-last-applied`, `--no-diff-last-applied` | Jenkins: stage 5 diffs against the plan the last successful build applied, so a contract change is "pending" rather than drift. Needs the `copyartifact` plugin |
| `--runner-host-override <host>` | Written to the pipeline's environment as `FLUID_RUNNER_HOST_OVERRIDE`, for runners inside a container that cannot reach `localhost` |
| `--list-engines` | Print the acquisition and transformation engines the generator knows, then exit |

A pipeline whose parameterless builds run in `aws`, apply with builds, and sync DAGs to a shared root is generated like this:

```bash
fluid generate ci contracts/silver/contract.fluid.yaml --system jenkins \
  --fluid-env-default aws --apply-mode-default amend-and-build \
  --scheduler-default airflow --scheduler-destination-default s3://<your-dags-bucket>/dags
```


## Plan binding: the integrity chain

A bundle is built for one `--env`; see [Environments](../cli/bundle.md#environments). A fragment-layout root is covered in [Contract fragments](../concepts/fragments.md#in-ci-bundle-once-then-pass-the-bundle).

`fluid plan` stamps two digests into `plan.json`:

- **`bundleDigest`**: SHA-256 identity of the tgz bundle the plan was generated against
- **`planDigest`**: digest over the plan body itself

`fluid apply` re-verifies both before any DDL. A mismatch raises `PlanBindingError` with a stable `kind` tag (`bundle-mismatch`, `plan-tamper`, ...) that CI log parsers can match; the full list is in [Production troubleshooting](./production-troubleshooting.md#plan-binding-rejections).

*(since 0.33.0, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))* A plan made from a bundle also records **`packetDigest`**, the sha256 of the bundle file. `bundleDigest` names the resolved contract and its files; the packet names the exact bytes, so a bundle rebuilt from the same checkout with another `SOURCE_DATE_EPOCH` is refused with `apply_plan_digest_packet_mismatch`. The apply job must receive the bundle the plan job made, as an artifact. In 0.32.0 and earlier the plan did not record it.

*(since 0.33.0, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972))* A bundle packs the dbt project of each dbt build, and `fluid plan` records its files as `dbtProjects`. `fluid apply` compares the checkout with them before anything runs, and the dbt runner compares again just before dbt starts; a changed, added or removed file is refused with `apply_plan_digest_bundle_mismatch`. See [The dbt project](../cli/apply.md#the-dbt-project). For a pipeline this means:

- **The apply job needs the checkout.** The dbt files are read from it, not from the artifact. The plan records the absolute path of the source contract, and `fluid apply` compares the project at that path, whatever checkout it runs from. Run plan and apply in the same checkout path: when the recorded path is gone, the apply is refused for a checkout it cannot find.
- **Generate dbt tests before the bundle.** Run `fluid generate dbt-tests` first, with `-o` naming a file inside the project (without it, the file lands in the current directory), then `fluid bundle`. Tests generated after stage 1 are not in the bundle, so the apply is refused for the files that appeared.
- **Install packages in the apply job.** Installed packages are not bound. Run `dbt deps` from `package-lock.yml` in the job that applies: `fluid apply` neither installs nor checks `dbt_packages/`.
- **Plan from the bundle.** A plan made from a contract file binds no dbt project.

Passing `--bundle <path>` to apply pins which tgz the plan is verified against; when omitted, a sibling `.tgz` is auto-discovered. The binding verifies a tgz bundle's `MANIFEST.json`, so use `--format tgz` for the bundle in CI.

Two more checks stop a pipeline that mixes environments. A bundle is never re-overlaid: asking a later stage for another `--env` fails with `bundle_env_mismatch`. A plan records its env, and applying an `*-and-build` plan with a different `--env` fails with `plan_env_mismatch`.

::: warning The disaster-recovery hatches
`fluid apply --no-verify-plan-binding` skips the digest verification and logs at WARNING. It is a narrowly scoped disaster-recovery hatch; never bake it into a pipeline default. The federation check is a different thing, described next.
:::

### The OpenTofu plan is what gets approved

*(since 0.31.0, [forge-cli #898](https://github.com/Agenticstiger/forge-cli/pull/898))* On the OpenTofu engine (`aws`, `gcp`, `snowflake`, `confluent`, `databricks`), a manual approval between plan and apply covers the OpenTofu diff only if the plan stage ran `tofu plan`. Run it with `--tofu` and keep the files together:

```bash
# plan job: needs read and write on the state and its lock
fluid plan runtime/bundle.tgz --env "$FLUID_ENV" --mode "$APPLY_MODE" \
  --out runtime/plan.json --check-sovereignty \
  --tofu --state-backend s3://<your-state-bucket>/<key>
# -> runtime/plan.json, runtime/plan.tfplan, runtime/plan.tfplan.json,
#    runtime/plan.gitlab-tofu.json   (all four are artifacts of the plan job)

# approval: a person reads plan.tfplan.json, or GitLab shows plan.gitlab-tofu.json

# apply job: fetch the four files and the bundle, then
fluid apply runtime/plan.json --bundle runtime/bundle.tgz \
  --mode "$APPLY_MODE" --env "$FLUID_ENV" --state-backend s3://<your-state-bucket>/<key> --yes
```

The apply runs `tofu apply` of `plan.tfplan` and plans nothing of its own. What stops it:

- **A plan file that is not the approved one** (`apply_plan_digest_tofu_plan_mismatch`, or `_missing` when it is not there).
- **State that moved since the plan** (`apply_plan_digest_tofu_plan_stale`), because another apply ran in between. Plan and apply again; the approval covered a state that no longer exists.
- **A plan made for another state** (`apply_plan_digest_tofu_plan_target`). The two jobs must resolve the same provider and state, so use the same `--state-backend` or `FLUID_STATE_BACKEND`. From `main`, the same code covers another state backend configuration.
- **A plan applied against another target** (`apply_plan_digest_tofu_plan_target_mismatch`). *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The plan records the cloud account, project, region or host it was made for, and the apply job refuses credentials that reach another one before it applies or changes anything. When the apply job cannot read a recorded field, for want of `boto3` or credentials, it stops with `apply_plan_digest_tofu_plan_target_unverified`.
- **Another OpenTofu or provider version** (`apply_plan_digest_tofu_plan_toolchain`). *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The apply job needs the same `tofu` version as the plan job, the patch release included.

Three requirements follow:

1. **A remote state.** Local state in a CI workspace is gone when the apply job starts, so the plan is refused as stale or as made for another target, and from `main` as `apply_plan_digest_tofu_plan_state_missing` when it was made against existing state. *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* With a remote state, the apply job can run on another runner, in another checkout path, and the plan still needs the state the plan job used.
2. **Protected artifacts.** The plan files are plaintext unless [`FLUID_STATE_ENCRYPTION`](../cli/apply.md#state-and-plan-encryption) is set, and `plan.tfplan.json` holds every sensitive value. Keep them in short-lived job artifacts that only the plan job can write, because the digests are not signatures.
3. **The same providers.** The apply job's `tofu init` must resolve the provider versions the plan was made with, and the apply job needs the same `tofu` and, if the plan was made with it, the same `FLUID_STATE_ENCRYPTION`. *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* When `tofu init` wrote a lock, the plan job writes one more file, `runtime/plan.terraform.lock.hcl`, beside the four in the example above. Pass it on with them: the apply job installs it before `tofu init`, and refuses a missing or changed one (`apply_plan_digest_tofu_plan_lock_missing`, `_lock_mismatch`).

See [Applying a saved OpenTofu plan](../cli/apply.md#applying-a-saved-opentofu-plan) for the errors and [`fluid plan --tofu`](../cli/plan.md#saving-the-opentofu-plan-tofu) for the files.

### The federation check warns

[Federated upstreams](../concepts/federation.md) explains the pin, the manifest and the digest cache. The [upgrade guide](../upgrading.md) lists when the gate became advisory.

When a `consumes[]` entry names an `upstreamWorkspace`, apply fetches the upstream's live digest and compares it with the pinned `upstreamDigest`. The check is advisory: it logs a warning and applies anyway, because its verdict depends on another team's registry being up.

```text
apply_consumes_drift: 1 federated consumes[] entry could not be confirmed in sync (1 drift). Applying anyway. Details: {...}
```

The payload has `violations[]` with `violation_kind`, `counts_by_kind`, `drift_count` and `unreachable_count`. If the validator itself cannot run, apply logs `federation_gate_error` instead. A pipeline that wants to block on drift has to match `apply_consumes_drift` in the apply log. `--no-verify-federation` silences the check; it does not unblock anything. Each git fetch is bounded by `FLUID_FEDERATION_TIMEOUT_SECONDS` (default 30) and needs the `git` binary on the runner.

## Non-interactive operation

| Setting | Effect |
|---|---|
| `fluid apply --yes` | Skips the confirmation prompt. `fluid apply` only prompts when stdin is a terminal, so a CI runner without a TTY does not block, but `--yes` states the intent |
| `FLUID_NONINTERACTIVE=1` | Skips prompts across the `fluid forge` surfaces and suppresses banners. Does not change `fluid apply` |
| `FLUID_FORGE_NO_PICKER=1` | Suppresses the interactive mode menu of `fluid forge` on runners |
| `FLUID_LOG_FILE=<path>` | Also writes logs to a file you can archive as a build artifact |

The generated Jenkinsfile passes `--yes` to apply; set the variables when you script stages by hand. `FLUID_AUTO_CONFIRM` is not read by 0.18.1; see [Environment variables](./environment-variables.md#variables-with-no-effect-in-0-18-1).

## Keyless cloud login

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))*

`fluid generate ci` reads the contract and writes a pipeline that holds no static cloud key. The CI system hands each job a short-lived OIDC ID token, and the cloud, or your secret store, trusts the CI system's issuer and the job's subject. No generated pipeline file holds a cloud key.

### What it detects

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* The platforms come from the contract and from every overlay, since a pipeline can run any of them:

- A `binding.platform` of `aws`, `gcp`, `snowflake` or `databricks`, with the aliases `fluid apply` accepts (such as `bigquery` or `s3`), and `binding.provider`.
- The runtime platform of each build, because a build there needs a login even beside another cloud's exposes.
- `openbao`, when any `secretRef` is a `vault://` or `openbao://` reference. forge's vault resolver then logs in to OpenBao or Vault with the job's token.

A contract that binds no cloud gets a header that says so, and no login. Run `fluid generate ci <contract>` again after adding a binding.

### What each system gets

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* GitHub Actions:

- `permissions: id-token: write` on the jobs that reach the cloud: the deploy jobs (apply, policy, verify and publish run in them), the enterprise compliance job, and the single job of the basic workflow. The validate, generate, plan and test jobs keep `contents: read`, and the workflow's default is none. *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* The pipeline has two jobs, `plan` (stages 1 to 6) and `apply` (stages 7 to 11), and both get `id-token: write` when the contract binds a cloud, because stages 5 and 6 read the target. The workflow's default stays none.
- AWS: `aws-actions/configure-aws-credentials` v6.3.0, pinned by commit SHA, with `AWS_ROLE_ARN` and `AWS_REGION`.
- GCP: `google-github-actions/auth` v3.0.0, pinned by SHA, with `GCP_PROJECT_NUMBER`, `WIF_POOL`, `WIF_PROVIDER` and `GCP_SA_EMAIL`.
- Snowflake: workload identity federation. The job asks for an ID token for the audience `snowflakecomputing.com`, writes it to a file with mode 600 under `$RUNNER_TEMP`, and exports `SNOWFLAKE_AUTHENTICATOR`, `SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER` and `SNOWFLAKE_TOKEN_FILE_PATH`. `SNOWFLAKE_ACCOUNT` is a repository variable.
- OpenBao: a JWT from the job in a mode-600 file named by `FLUID_VAULT_JWT_FILE`, with `FLUID_VAULT_JWT_ROLE` and `BAO_ADDR` from repository variables.
- Databricks: `DATABRICKS_AUTH_TYPE=github-oidc` with `DATABRICKS_HOST` and `DATABRICKS_CLIENT_ID`. The SDK and the OpenTofu provider make the token exchange themselves.
- GitHub's ID tokens last about five minutes, so the Snowflake and OpenBao token files are replaced every four minutes for the later steps of the job.
- The login steps are skipped on pull requests from forks and from Dependabot, which get no ID token, so the job does not fail before validate runs.

This is an excerpt of a workflow generated for a contract with a Snowflake binding. In 0.33.0 the job is named `apply` and its `environment` follows `FLUID_ENV`; 0.30.1 wrote one `deploy-<env>` job per environment (`deploy-dev` here, with `environment: dev`):

```yaml
jobs:
  apply:
    env:
      SNOWFLAKE_ACCOUNT: ${{ vars.SNOWFLAKE_ACCOUNT }}
    environment: ${{ inputs.fluid_env || vars.FLUID_ENV || 'dev' }}
    # ...
    permissions:
      contents: read
      id-token: write
    runs-on: ubuntu-latest
    steps:
    # ...
    - if: github.event.pull_request.head.repo.fork != true && github.actor != 'dependabot[bot]'
      name: Authenticate to Snowflake (workload identity federation)
      run: |
        set -euo pipefail
        umask 077
        token_file="$RUNNER_TEMP/snowflake-id-token"
        mint() {
          token="$(curl -sSf -H @- "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=snowflakecomputing.com" <<<"Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" | python3 -I -c 'import json, sys; print(json.load(sys.stdin)["value"])')"
          [ -n "$token" ] || return 1
          echo "::add-mask::$token"
          printf '%s' "$token" > "$token_file.new" && mv -f "$token_file.new" "$token_file"
        }
        mint
        # GitHub's ID tokens expire after about five minutes and the request URL stays
        # valid for the whole job, so a fresh one replaces the file every four minutes
        # for the later steps that read it (GitHub ends the loop with the job). A failed
        # refresh keeps the last token. Only the first token is masked in the log, so
        # no step should print this file.
        ( while sleep 240; do mint || true; done ) >/dev/null 2>&1 &
        {
          echo "SNOWFLAKE_AUTHENTICATOR=WORKLOAD_IDENTITY"
          echo "SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER=OIDC"
          echo "SNOWFLAKE_TOKEN_FILE_PATH=$token_file"
        } >> "$GITHUB_ENV"
      shell: bash
```

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* GitLab CI: each job that reaches the cloud gets `id_tokens`, one per platform (`AWS_OIDC_TOKEN` for `sts.amazonaws.com`, `GCP_OIDC_TOKEN`, `SNOWFLAKE_OIDC_TOKEN`, `DATABRICKS_OIDC_TOKEN` for your Databricks account id, `OPENBAO_OIDC_TOKEN`). Its script writes the AWS, GCP, Snowflake and OpenBao tokens to mode-600 files in a private temporary directory that is removed when the job ends, and points the SDKs at them. Databricks reads its token from `DATABRICKS_OIDC_TOKEN` directly, with `DATABRICKS_AUTH_TYPE=env-oidc`, and needs a `DATABRICKS_ACCOUNT_ID` variable. Databricks uses `DATABRICKS_AUTH_TYPE=env-oidc` and needs a `DATABRICKS_ACCOUNT_ID` variable.

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* Jenkins has no native OIDC, so a Jenkinsfile stays on credentials binding. Its header says so and recommends credentials that expire, such as a role session or a short-lived token from your vault, kept in the Jenkins credential store or the agent's environment. Azure DevOps, Bitbucket, CircleCI and Tekton are not wired for OIDC yet: their headers name the system's own mechanism and the variables forge reads once a job holds a token in a file.

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* `fluid forge` scaffolds the same keyless CI from the project's contract.

### The trust you create on the cloud side

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* The header of each pipeline lists the non-secret variables to set and the trust to create. Bind every trust to the job's subject, never to a whole organization.

For GitHub, the subject is immutable: `repo:OWNER@OWNER-ID/REPO@REPO-ID:<context>` is the default for repositories created after 2026-07-15. Older repositories keep `repo:OWNER/REPO:<context>` until they opt in, which makes a renamed or re-created repository unable to inherit the trust. Opt in, then bind to the immutable form. The `<context>` is `environment:<name>` for a job that declares an environment (the deploy jobs do), `pull_request` for a job a pull request runs, and `ref:refs/heads/<branch>` otherwise. *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* The `plan` job declares no environment, so its subject is `pull_request` or `ref:refs/heads/<branch>`: the trust must cover that subject too, with a role that can read the target, besides the `environment:<name>` subject of `apply`. The issuer is `https://token.actions.githubusercontent.com`.

For GitLab, bind to `project_path:GROUP/PROJECT:ref_type:branch:ref:main`, a protected branch or environment. The issuer is your GitLab instance URL.

| Platform | Trust to create |
| --- | --- |
| `aws` | An IAM OIDC provider for the issuer, and a role whose trust policy allows `sts:AssumeRoleWithWebIdentity` with `aud = sts.amazonaws.com` and the subject above. |
| `gcp` | A workload identity pool and an OIDC provider for the issuer, mapping `google.subject=assertion.sub`, and permission for the subject to impersonate the service account. |
| `snowflake` | A service user that trusts the token: `CREATE USER FLUID_CI TYPE = SERVICE WORKLOAD_IDENTITY = (TYPE = OIDC ISSUER = '<issuer>' SUBJECT = '<sub>');`, with the role the contract's bindings use granted to it. |
| `databricks` | A service principal and an account federation policy for it, with the issuer, your Databricks account id as the audience, and the subject. `DATABRICKS_CLIENT_ID` is the service principal's application id. |
| `openbao` | The JWT auth method trusting the issuer, and a role bound to the audience and the subject. |

## Credentials on runners

Do not put credentials in the pipeline file. The generated templates read them from the CI system's secret store at run time:

- **Cloud provider auth**: inject through the provider's own variables or secret files; see the [AWS](../providers/aws.md), [GCP](../providers/gcp.md) and [Snowflake](../providers/snowflake.md) provider pages, and [`fluid auth`](../cli/auth.md) for interactive setup outside CI.
- **Pipeline secrets** (database passwords and API tokens that acquisition runners use): reference them from the contract with `secretRef: env://NAME`, which reads the runner's environment, or with `vault://`, `aws-sm://` or `file://` to read a secret manager or a mounted file. *(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* The runner's environment sets which schemes, locators and stages a contract may use; see [the operator's policy](../cli/secrets.md#the-operator-s-policy). A `{{ env.NAME }}` placeholder also reads the environment. [`fluid secrets`](../cli/secrets.md) reads values only from stdin or an interactive prompt, never from argv.
- **Provider credentials from a store** *(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))*: the Fernet credential file store is removed, so on ephemeral runners set `FLUID_CREDENTIAL_STORE` to a Vault, OpenBao or Secrets Manager prefix, or keep the credential in the environment. See [Provider credentials from a store](../cli/secrets.md#provider-credentials-from-a-store).
- **Masking secrets**: `FLUID_PII_HASH_SECRET`, `FLUID_PII_TOKENIZATION_KEY` and `FLUID_PII_ENCRYPTION_SECRET_KEY` must be present on the runner of any build whose expose declares masking; a missing one refuses the build.

## Command Center in a pipeline

[The Command Center](../concepts/command-center.md) describes what publish sends and what apply reports.

Stage 10 can publish to a Command Center with `--target=fluid-command-center`. Set `FLUID_CC_ENDPOINT` and `FLUID_API_KEY` on the agent, plus `FLUID_CC_ORG_ID` when the key belongs to more than one organization; `PUBLISH_TARGETS` takes catalog names, not URLs.

The Command Center keeps one product per contract id, whichever `--env` published it last: publishing the same contract from two environments overwrites the product's platform and location with the later publish. For a contract deployed to more than one cloud, publish from one environment's pipeline only. Stage 10 is off unless a pipeline is generated with `--publish-stage-default`, and `--no-publish-stage-default` states the off explicitly.

A pipeline that is configured to publish also reports its applies: `fluid apply` registers each run with the Command Center and closes it, best effort, using the same endpoint, key and organization. The report never changes the exit code, nothing is sent without an organization, and `FLUID_COMMAND_CENTER_ENABLED=false` turns it off. Under Jenkins the run is tagged `jenkins`. The variables are in [Environment variables](./environment-variables.md#command-center).

## Cost caps for LLM-driven stages

If a pipeline runs an LLM-driven command, cap spend explicitly:

| Variable | Scope |
|---|---|
| `FLUID_COST_LIMIT_USD` | Per-run LLM cost ceiling |
| `FLUID_COST_LIMIT_USD_PER_PRODUCT` | Per-product ceiling, enforced in the agent coordinator |

`FLUID_STAGE_BUDGET_<STAGE>_S` is a wall-clock budget in seconds for a forge pipeline stage, not a cost cap. See [cost tracking](./cost-tracking.md) for how overruns surface.

## OpenTofu on runners

Cloud applies go through the OpenTofu engine, which runs the `tofu` binary:

- **Version floor.** `tofu` must be 1.6.0 or newer; an older one fails before any state is touched. *(since 0.31.0, [forge-cli #899](https://github.com/Agenticstiger/forge-cli/pull/899))* The floor is 1.12.0, and the module declares `required_version = ">= 1.12"`. On OpenTofu 1.11, adding retention to a live GCP table plans an in-place update that BigQuery refuses at apply, and the data-loss gate sees no removal. From 1.12 the plan replaces the table, which the gate sees.
- **Provision on demand.** `fluid apply --ensure-opentofu` downloads a pinned OpenTofu build when `tofu` is missing, with no root or gpg needed, and checks it against the release's `SHA256SUMS` (integrity, not a signature). The generated apply stage passes it. For production, install OpenTofu on the runner image with a cosign- or gpg-verified install instead.
- **State.** CI wipes the workspace after every run, and a wiped local state re-plans every resource as new. Set `FLUID_STATE_BACKEND=s3://<bucket>` or `gcs://<bucket>` once for the pipeline: each contract and provider then gets its own key. See [Environment variables](./environment-variables.md#apply-state-and-opentofu).
- **S3 state lock.** *(since 0.27.0, [forge-cli #787](https://github.com/Agenticstiger/forge-cli/pull/787))* With OpenTofu 1.10 or newer, S3 state is locked through a `<key>.tflock` object, and `tofu plan` takes the lock too. Every role in the pipeline that plans or applies, a plan-only job and a drift check (`fluid diff`, `fluid verify --state-drift`) included, needs `s3:GetObject`, `s3:PutObject` and `s3:DeleteObject` on that object, or `FLUID_TOFU_S3_LOCKFILE=0` in the job's environment (a project `.env` cannot set it). A job that is killed hard can leave the lock behind; `tofu force-unlock <ID>` in the contract's workdir clears it. See [Locking](../concepts/state.md#locking).
- **Timeouts.** Each `tofu` call is capped at 1800 s by default; raise it for a large first apply with `FLUID_TOFU_TIMEOUT_SECONDS`. *(since 0.27.0, [forge-cli #787](https://github.com/Agenticstiger/forge-cli/pull/787))* A call that runs past the cap is interrupted first, so `tofu` releases its state lock, and killed only if it is still running 30 seconds later.
- **Databricks job runs.** *(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* Under `--mode amend-and-build`, a dbt build that runs as a Databricks job holds the CI job until its run ends, up to `FLUID_DATABRICKS_RUN_TIMEOUT_SECONDS`. A cancelled CI job that stops the apply with SIGINT, SIGTERM or SIGHUP cancels the run too. See [Running the job from `fluid apply`](../providers/databricks.md#running-the-job-from-fluid-apply). *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* A triggered build with `engine: lakeflow` holds the CI job the same way until its pipeline update ends, and a cancelled CI job stops the pipeline. A continuous one starts no update, so it holds nothing. See [Running it from `fluid apply`](../providers/databricks.md#running-it-from-fluid-apply).
- **Review before apply.** `fluid generate iac <contract>` emits a deterministic, credential-free `main.tf.json` you can archive or review in a pull request; see [`fluid generate iac`](../cli/generate-iac.md).

## Contract SQL in CI

Since 0.18.0, SQL in a contract runs in a DuckDB sandbox: it reads the contract's directory and the locations the contract declares, not the rest of the runner. A pipeline that reads data from outside the checkout needs the operator to allow the directory with `FLUID_DUCKDB_ALLOWED_DIRS`, and `$ref` fragments from outside the contract's tree need `FLUID_REF_ROOT`. See the [DuckDB sandbox](./duckdb-sandbox.md) and [Composing a contract with `$ref`](../concepts/contract-refs.md).

## See also

- [Production troubleshooting](./production-troubleshooting.md): when a stage goes red
- [Jenkins CI/CD walkthrough](../walkthrough/jenkins-cicd.md) and the [11-stage pipeline walkthrough](../walkthrough/11-stage-pipeline.md): end-to-end tours
- [`fluid generate`](../cli/generate.md#fluid-generate-ci): the `generate ci` reference
- [`fluid apply`](../cli/apply.md), [`fluid plan`](../cli/plan.md), [`fluid bundle`](../cli/bundle.md): stage command references
- [Environment variables](./environment-variables.md): the variables above in one place
- [OpenTofu state](../concepts/state.md) and [One contract, two clouds](../recipes/one-contract-two-clouds.md): one job per cloud, one state per provider
- [Credential resolver](./credential-resolver.md): how source credentials resolve
