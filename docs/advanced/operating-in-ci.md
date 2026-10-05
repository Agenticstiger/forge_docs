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
  |- FLUID_PACKAGE_SPEC default: data-product-forge[local]==0.18.1
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

The templates are not the same pipeline. The Jenkins template is the one that runs the stages described next (a stage 0 bootstrap, then stages 1-11). Generated with the default `standard` complexity, the GitHub Actions workflow runs `fluid doctor`, `fluid validate`, `fluid generate speed-transformation` and `fluid generate schedule`, a plan with `--check-sovereignty`, tests, and per-environment `fluid apply`, `fluid policy-apply`, `fluid verify` and `fluid contract-tests`. The GitLab file runs validation, `fluid test`, the two generate commands, the same plan, `fluid apply` and `fluid publish`. Neither has a bundle, diff or schedule-sync stage. Open the generated file for the commands a given system runs.

::: warning Check the GitHub and GitLab deploy steps before you use them
As of 0.18.1, the per-environment deploy step in those two templates is written `FLUID_ENV=<env> if [ -n "$BUILD_ID" ]; then fluid apply ...; else ...; fi`. `bash` and `sh` both reject that with a syntax error (`near unexpected token 'then'`), and `fluid apply` does not read `FLUID_ENV`, so the environment is not selected by it. Pass `--env <env>` to the stage commands, as the Jenkins template does.
:::

## The Jenkins pipeline: stages 1-11

Stage 1 writes `runtime/bundle.tgz` for one environment. Stages 2, 3, 5, 6, 7 and 9 read that bundle and pass the same `--env`, so every stage works on the bytes stage 1 produced. If a stage runs without the bundle, it stops and says so.

| # | Stage | Command in the generated Jenkinsfile | What it gates |
|---|---|---|---|
| 1 | Bundle | `fluid bundle "$CONTRACT" --env "$FLUID_ENV" --format tgz --out runtime/bundle.tgz` | Deterministic tgz with `MANIFEST.json`, per-file SHA-256 and a merkle root |
| 2 | Validate | `fluid validate runtime/bundle.tgz --env "$FLUID_ENV" --report runtime/validate-report.json --strict` | The bundled contract against its schema (`--strict` is the `VALIDATE_STRICT` parameter) |
| 3 | Generate artifacts | `fluid generate artifacts runtime/bundle.tgz --env "$FLUID_ENV" --contract-path "$CONTRACT" --out dist/artifacts/ --emit ...` | ODCS, ODPS-Bitol, schedule and policy artifacts under `dist/artifacts/` |
| 4 | Validate artifacts | `fluid validate-artifacts dist/artifacts/ --manifest dist/artifacts/MANIFEST.json --report runtime/validate-artifacts-report.json` | Generated artifacts match their manifest. Skipped when `dist/artifacts/MANIFEST.json` does not exist |
| 5 | Diff (drift gate) | `fluid diff runtime/bundle.tgz --env "$FLUID_ENV" --out runtime/diff-report.json --exit-on-drift` | The bundled contract against the live target |
| 6 | Plan | `fluid plan runtime/bundle.tgz --env "$FLUID_ENV" --mode "$APPLY_MODE" --out runtime/plan.json --check-sovereignty` | `plan.json` with `bundleDigest` and `planDigest`; a strict sovereignty violation fails here, before any cloud is touched |
| 7 | Apply | `fluid apply runtime/plan.json --bundle runtime/bundle.tgz --mode "$APPLY_MODE" --env "$FLUID_ENV" --yes --ensure-opentofu --report runtime/apply-report.html` | Re-verifies both digests, then executes (see [plan binding](#plan-binding-the-integrity-chain)) |
| 8 | Policy apply | `fluid policy-apply dist/artifacts/policy/bindings.json --mode enforce` | IAM and GRANT bindings; skipped when the file does not exist |
| 9 | Verify | `fluid verify runtime/bundle.tgz --env "$FLUID_ENV" --out runtime/verify-report.json --strict` | Deployed state matches the bundle |
| 10 | Publish | `fluid publish "$CONTRACT" --env "$FLUID_ENV" --format json --target=<catalog>` | Catalog registration, one `--target` per name in `PUBLISH_TARGETS`. Off by default |
| 11 | Schedule sync | `fluid schedule-sync --scheduler "$SCHEDULER" --dags-dir dist/artifacts/schedule/ --env "$FLUID_ENV" --delete-scope product` | Generated DAGs pushed to the scheduler. Off by default; takes no contract argument |

The mode is a build parameter and defaults to **`dry-run`** on Jenkins. Stage 6 plans with it and stage 7 applies with it, so the plan is for the mode that is applied. After a dry-run apply, stage 8 downgrades to `--mode check`, and stages 9, 10 and 11 print that stage 7 applied nothing and skip. To deploy, run with `APPLY_MODE` set to `amend` or `amend-and-build`.

`--build-id` is passed to apply only for `amend-and-build` and `replace-and-build`, from `APPLY_BUILD_ID` (blank runs every build). With any other mode the stage prints that `APPLY_BUILD_ID` is not passed on and carries on. Calling `fluid apply` by hand with `--build-id` and a mode that runs no build is refused with `apply_build_id_requires_build_mode`.

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
| `ALLOW_DATA_LOSS` | `false` | Passes `--allow-data-loss`; required for `replace*` outside `dev` or when the target has rows |
| `NO_VERIFY_DIGEST` | `false` | Passes both `--no-verify-plan-binding` and `--no-verify-federation`. A disaster-recovery hatch |
| `RUN_STAGE_<N>_<NAME>` | on, except stages 10 and 11 | One toggle per stage |
| `PUBLISH_TARGETS` | `datamesh-manager` | Space-separated catalog names; not endpoints |
| `SCHEDULER`, `SCHEDULER_DESTINATION`, ... | blank | Stage 11 target. Blank means no-op |
| `FLUID_PACKAGE_SPEC` | the generating version, with extras | Package spec stage 0 installs |

Jenkins learns a job's parameters from its first build. As measured on a Jenkins controller on 4 October 2026, `buildWithParameters` is refused for a job that has never run, so run one plain build first.

### Install

Stage 0 creates `$WORKSPACE/.fluid-venv`, because agents that follow PEP 668 refuse a bare `pip install`, and installs `FLUID_PACKAGE_SPEC` into it. The default is the version that generated the file with the extras the contract's base and overlays need, for example `data-product-forge[local]==0.18.1`. Every stage then runs `fluid` from that venv, and stage 0 fails if the first `fluid` on `PATH` is another one. The agent needs `python3` with the `venv` module, and `rsync` for a `file://` or `ssh://` stage 11 destination. The workspace is removed with Jenkins's core `deleteDir()`, so the `ws-cleanup` plugin is not needed.

Pin a different version at build time with `FLUID_PACKAGE_SPEC=data-product-forge==X.Y.Z`. `FLUID_PIP_INDEX_URL` (blank means PyPI), `FLUID_PIP_EXTRA_INDEX_URL` and `FLUID_ALLOW_PRERELEASE` (`true` adds `pip --pre`) cover TestPyPI pilots and private mirrors. With `--install-mode dev-source` the file installs from a `/forge-cli-src` bind mount and fails if the mount is missing; it never falls back to PyPI.

A committed Jenkinsfile keeps what it was generated with. Regenerate it after upgrading the CLI to pick up newer stage logic.

### `fluid generate ci` options

| Flag | Purpose |
|---|---|
| `--system` | The CI system. Default `gitlab` |
| `--complexity {basic,standard,advanced,enterprise}` | `basic` is validate and apply; `standard` is the default; `advanced` adds multiple environments and approvals; `enterprise` adds governance and compliance |
| `--out <path>` | Output path, for single-file systems |
| `--no-generate-artifacts` | Skip stages 3 and 4 for reference-only contracts. Auto-detected for `builds[].pattern: hybrid-reference` |
| `--install-mode {pypi,dev-source}` | How the Jenkinsfile installs fluid. Other systems ignore it |
| `--fluid-package-spec <spec>` | Default of `FLUID_PACKAGE_SPEC` |
| `--fluid-env-default <env>` | Default of `FLUID_ENV` and the fallback every stage uses. Default `dev` |
| `--apply-mode-default <mode>` | Default of `APPLY_MODE`: `dry-run` for Jenkins, `amend` for the other systems |
| `--default-publish-target <name>` | Default of `PUBLISH_TARGETS` and the fallback stage 10 reads. Default `datamesh-manager` |
| `--publish-stage-default`, `--no-publish-stage-default` | Default of `RUN_STAGE_10_PUBLISH`. Off unless set |
| `--publish-include-env`, `--no-publish-include-env` | Whether stage 10 passes `--env` to `fluid publish`. On unless disabled |
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
  --scheduler-default airflow --scheduler-destination-default s3://acme-dags/dags
```


## Plan binding: the integrity chain

`fluid plan` stamps two digests into `plan.json`:

- **`bundleDigest`**: SHA-256 identity of the tgz bundle the plan was generated against
- **`planDigest`**: digest over the plan body itself

`fluid apply` re-verifies both before any DDL. A mismatch raises `PlanBindingError` with a stable `kind` tag (`bundle-mismatch`, `plan-tamper`, ...) that CI log parsers can match; the full list is in [Production troubleshooting](./production-troubleshooting.md#plan-binding-rejections).

Passing `--bundle <path>` to apply pins which tgz the plan is verified against; when omitted, a sibling `.tgz` is auto-discovered. The binding verifies a tgz bundle's `MANIFEST.json`, so use `--format tgz` for the bundle in CI.

Two more checks stop a pipeline that mixes environments. A bundle is never re-overlaid: asking a later stage for another `--env` fails with `bundle_env_mismatch`. A plan records its env, and applying an `*-and-build` plan with a different `--env` fails with `plan_env_mismatch`.

::: warning The disaster-recovery hatches
`fluid apply --no-verify-plan-binding` skips the digest verification and logs at WARNING. It is a narrowly scoped disaster-recovery hatch; never bake it into a pipeline default. The federation check is a different thing, described next.
:::

### The federation check warns

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

## Credentials on runners

Do not put credentials in the pipeline file. The generated templates read them from the CI system's secret store at run time:

- **Cloud provider auth**: inject through the provider's own variables or secret files; see the [AWS](../providers/aws.md), [GCP](../providers/gcp.md) and [Snowflake](../providers/snowflake.md) provider pages, and [`fluid auth`](../cli/auth.md) for interactive setup outside CI.
- **Pipeline secrets** (database passwords and API tokens that acquisition runners use): reference them from the contract with `secretRef: env://NAME`, which reads the runner's environment, or with `vault://`, `aws://`, `gcp://`, `azure://` or `file://` to read a secret manager. A `{{ env.NAME }}` placeholder also reads the environment. [`fluid secrets`](../cli/secrets.md) reads values only from stdin or an interactive prompt, never from argv.
- **Encrypted credential store**: on ephemeral runners, supply the Fernet key as `FLUID_ENCRYPTION_KEY` (or `FLUID_ENCRYPTION_PASSPHRASE`) from the secret store.
- **Masking secrets**: `FLUID_PII_HASH_SECRET`, `FLUID_PII_TOKENIZATION_KEY` and `FLUID_PII_ENCRYPTION_SECRET_KEY` must be present on the runner of any build whose expose declares masking; a missing one refuses the build.

## Command Center in a pipeline

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

- **Version floor.** `tofu` must be 1.6.0 or newer; an older one fails before any state is touched.
- **Provision on demand.** `fluid apply --ensure-opentofu` downloads a pinned, SHA-256-verified OpenTofu build when `tofu` is missing, with no root or gpg needed. The generated apply stage passes it.
- **State.** CI wipes the workspace after every run, and a wiped local state re-plans every resource as new. Set `FLUID_STATE_BACKEND=s3://<bucket>` or `gcs://<bucket>` once for the pipeline: each contract and provider then gets its own key. See [Environment variables](./environment-variables.md#apply-state-and-opentofu).
- **Timeouts.** Each `tofu` call is capped at 1800 s by default; raise it for a large first apply with `FLUID_TOFU_TIMEOUT_SECONDS`.
- **Review before apply.** `fluid generate iac <contract>` emits a deterministic, credential-free `main.tf.json` you can archive or review in a pull request; see [`fluid generate iac`](../cli/generate-iac.md).

## Contract SQL in CI

Since 0.18.0, SQL in a contract runs in a DuckDB sandbox: it reads the contract's directory and the locations the contract declares, not the rest of the runner. A pipeline that reads data from outside the checkout needs the operator to allow the directory with `FLUID_DUCKDB_ALLOWED_DIRS`, and `$ref` fragments from outside the contract's tree need `FLUID_REF_ROOT`. See the [DuckDB sandbox](./duckdb-sandbox.md) and [Composing a contract with `$ref`](../concepts/contract-refs.md).

## See also

- [Production troubleshooting](./production-troubleshooting.md): when a stage goes red
- [Jenkins CI/CD walkthrough](../walkthrough/jenkins-cicd.md) and the [11-stage pipeline walkthrough](../walkthrough/11-stage-pipeline.md): end-to-end tours
- [`fluid generate`](../cli/generate.md#fluid-generate-ci): the `generate ci` reference
- [`fluid apply`](../cli/apply.md), [`fluid plan`](../cli/plan.md), [`fluid bundle`](../cli/bundle.md): stage command references
- [Environment variables](./environment-variables.md): the variables above in one place
- [Credential resolver](./credential-resolver.md): how source credentials resolve
