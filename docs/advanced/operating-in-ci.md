# Operating in CI

Runbook for running fluid pipelines unattended — on Jenkins, GitHub Actions, GitLab CI, or any other runner. Everything on this page is verified against CLI `v0.11.0`.

::: tip Companion page
When a CI stage fails, jump to [Production Troubleshooting](./production-troubleshooting.md) for the symptom → diagnosis → fix tables.
:::

## The 11-stage pipeline

Every generated CI template drives the same 11 stages, one CLI command per stage. Stages 1–7 form the integrity chain: the bundle digest computed in stage 1 is stamped into the plan in stage 6 and re-verified in stage 7 before any DDL runs.

| # | Stage | Command | What it gates |
|---|---|---|---|
| 1 | Bundle | `fluid bundle <contract> --format tgz --out runtime/bundle.tgz` | Deterministic tgz with `MANIFEST.json`, per-file SHA-256, merkle root |
| 2 | Validate | `fluid validate <contract>` | Contract vs the versioned JSON schema (`--strict` treats warnings as errors) |
| 3 | Generate artifacts | `fluid generate artifacts <contract>` | Transformation + schedule artifacts under `dist/artifacts/` |
| 4 | Validate artifacts | `fluid validate-artifacts dist/artifacts/` | Generated artifacts are internally consistent |
| 5 | Diff (drift gate) | `fluid diff <contract> --out runtime/diff.json` | Drift between the contract and the last applied state |
| 6 | Plan | `fluid plan <contract> --out plan.json` | Emits `plan.json` carrying `bundleDigest` + `planDigest` |
| 7 | Apply | `fluid apply plan.json --yes` | Re-verifies both digests, then executes (see [plan binding](#plan-binding-the-integrity-chain)) |
| 8 | Policy apply | `fluid policy-apply dist/artifacts/policy/bindings.json` | Governance policy bindings |
| 9 | Verify | `fluid verify <contract> --out runtime/verify.json` | Deployed state matches the contract |
| 10 | Publish | `fluid publish <contract> --target <catalog>` | Catalog registration (repeatable `--target`) |
| 11 | Schedule sync | `fluid schedule-sync <contract>` | Declared schedules match the scheduler |

Use the tgz bundle format in CI: stages 4, 6, and 7 all require the tgz `MANIFEST.json`. A `yaml`/`json` bundle is valid for `fluid bundle` itself but breaks every downstream stage of this pipeline.

## Generating a pipeline

```bash
fluid generate ci                          # GitLab CI (default)
fluid generate ci --system github          # GitHub Actions
fluid generate ci --system jenkins         # Jenkins (Jenkinsfile)
fluid generate ci --system azure           # Azure DevOps
fluid generate ci --system bitbucket       # Bitbucket Pipelines
fluid generate ci --system circleci        # CircleCI
fluid generate ci --system tekton          # Tekton (writes tekton/*.yaml)
```

Useful knobs:

| Flag | Purpose |
|---|---|
| `--complexity {basic,standard,advanced,enterprise}` | `basic` = validate+apply; `standard` (default) = full workflow; `advanced` = multi-env + approvals; `enterprise` = + governance/compliance |
| `--install-mode {pypi,dev-source}` | How the generated **Jenkinsfile** installs fluid (Jenkins only today; other systems ignore it) |
| `--out <path>` | Output path override (single-file systems only) |
| `--no-generate-artifacts` | Skip stages 3–4 for reference-only contracts (hybrid-reference dbt, external Airflow); auto-detected for `builds[].pattern: hybrid-reference` |
| `--default-publish-target <TARGET>` | Bake a fallback catalog target into stage 10's publish shell (`${PUBLISH_TARGETS:-<TARGET>}`) — matters for the first Pipeline-from-SCM build Jenkins auto-triggers, where parameter defaults are not yet exported as env vars |

The Jenkins template is the reference implementation of the 11 stages: every stage gets a boolean `RUN_STAGE_*` toggle plus per-stage config in the `parameters { }` block, so operators can run a subset from "Build with Parameters" without editing Groovy.

### Install modes (Jenkins)

- **`pypi`** (default, production) — `pip install data-product-forge` from stable PyPI. Overridable at build time via the four parameters below.
- **`dev-source`** (lab / contributor) — installs from a `/forge-cli-src` bind mount inside the Jenkins container and **fails loud** if the mount is missing. No silent fallback to PyPI. The generated Jenkinsfile carries exactly one mode's logic — regenerate to switch.

### The four Jenkins build parameters (pypi mode)

| Parameter | Default | Purpose |
|---|---|---|
| `FLUID_PACKAGE_SPEC` | `data-product-forge` | Package spec for pip. Pin a version via `data-product-forge==X.Y.Z` |
| `FLUID_PIP_INDEX_URL` | *(blank)* | Primary pip index. Blank = stable PyPI; set `https://test.pypi.org/simple/` for TestPyPI pilots, or a private mirror |
| `FLUID_PIP_EXTRA_INDEX_URL` | *(blank)* | Fallback index — usually `https://pypi.org/simple/` when the primary points at TestPyPI so transitive deps still resolve |
| `FLUID_ALLOW_PRERELEASE` | `false` | Pass `pip --pre` (pulls alpha/rc releases). Leave `false` in prod |

Two global parameters ride alongside them: `CONTRACT` (contract path, default `contract.fluid.yaml`) and `FLUID_ENV` (environment overlay, default `dev`).

## Plan binding: the integrity chain

`fluid plan` stamps two digests into `plan.json`:

- **`bundleDigest`** — SHA-256 identity of the tgz bundle the plan was generated against
- **`planDigest`** — digest over the plan body itself

`fluid apply` re-verifies both **before any DDL**. A mismatch raises `PlanBindingError` with a stable `kind` tag (`bundle-mismatch`, `plan-tamper`, …) that CI log parsers can grep — the full catalog is on the [troubleshooting page](./production-troubleshooting.md#plan-binding-rejections).

::: warning The DR escape hatches log at WARNING
`fluid apply --no-verify-plan-binding` skips the digest verification and `--no-verify-federation` skips the federated-consumes upstream-digest gate. Each is a **narrowly-scoped disaster-recovery hatch** (they were deliberately split — a single waiver for both trust domains was a security finding), and each logs at WARNING level so audit trails catch every use. Never bake either into a pipeline default.
:::

Passing `--bundle <path>` to apply pins which tgz the plan is verified against; when omitted, a sibling `.tgz` is auto-discovered.

## Non-interactive operation

| Setting | Effect |
|---|---|
| `fluid apply --yes` | Skip the apply confirmation prompt |
| `FLUID_AUTO_CONFIRM=1` | Env-var equivalent of `--yes` |
| `FLUID_NONINTERACTIVE=1` | Skip prompts and use defaults across prompting surfaces (also set by `fluid forge --non-interactive`) |
| `FLUID_FORGE_NO_PICKER=1` | Suppress the interactive 5-mode `fluid forge` menu on runners |
| `FLUID_LOG_FORMAT=json` | Structured logs — parseable by CI log processors |
| `FLUID_LOG_FILE=<path>` | Also write logs to a file you can archive as a build artifact |

Generated templates already run every stage with non-interactive flags; set the env vars when you script stages by hand.

## Credentials on runners

Never bake credentials into the pipeline file. The generated templates read them from the CI system's secret store at runtime:

- **Cloud provider auth** — inject via the provider's own env-var / secret-file conventions; see the [AWS](../providers/aws.md), [GCP](../providers/gcp.md), and [Snowflake](../providers/snowflake.md) provider pages for the exact variables, and [`fluid auth`](../cli/auth.md) for interactive setup outside CI.
- **Pipeline secrets** (database passwords, API tokens consumed by acquisition runners) — resolve through `${SECRET:...}` references; see the [credential resolver](./credential-resolver.md). [`fluid secrets`](../cli/secrets.md) reads secret values **only from stdin or an interactive prompt, never from argv** — so a CI seeding step is `printf '%s' "$DB_PASSWORD" | fluid secrets login postgres.prod.password`.
- **Encrypted credential store** — on ephemeral runners, supply the Fernet key via `FLUID_ENCRYPTION_KEY` (or `FLUID_ENCRYPTION_PASSPHRASE`) from the CI secret store.

## Cost caps for LLM-driven stages

If the pipeline invokes any LLM-driven command, cap spend explicitly:

| Variable | Scope |
|---|---|
| `FLUID_COST_LIMIT_USD` | Global cap across a CLI invocation |
| `FLUID_COST_LIMIT_USD_PER_RUN` | Per-run cap |
| `FLUID_COST_LIMIT_USD_PER_PRODUCT` | Per-product cap (multi-product runs) |
| `FLUID_STAGE_BUDGET_<STAGE>` | Per-stage budget, e.g. `FLUID_STAGE_BUDGET_PLAN` |

See [cost tracking](./cost-tracking.md) for how overruns surface.

## OpenTofu on runners

Cloud applies route through the OpenTofu engine, which shells out to the `tofu` binary:

- **Version floor** — `tofu` must be **>= 1.6.0**; older versions fail loud before any state is touched.
- **Provision on demand** — `fluid apply --ensure-opentofu` downloads a pinned, SHA-256-verified OpenTofu build when `tofu` is missing (no root or gpg needed). `fluid generate ci` bakes this into the apply stage so generated pipelines work on any runner.
- **Timeouts** — each `tofu` subprocess has a wall-clock cap of 1800 s by default; raise it for very large first applies with `FLUID_TOFU_TIMEOUT_SECONDS`.
- **Review before apply** — `fluid generate iac <contract>` emits a deterministic, credential-free `main.tf.json` you can archive or review in a PR; see [`fluid generate iac`](../cli/generate-iac.md).

## See also

- [Production Troubleshooting](./production-troubleshooting.md) — when a stage goes red
- [Jenkins CI/CD walkthrough](../walkthrough/jenkins-cicd.md) and [11-Stage Production Pipeline walkthrough](../walkthrough/11-stage-pipeline.md) — end-to-end tours
- [`fluid generate`](../cli/generate.md#fluid-generate-ci) — full `generate ci` reference
- [`fluid apply`](../cli/apply.md) / [`fluid plan`](../cli/plan.md) / [`fluid bundle`](../cli/bundle.md) — stage command references
- [Environment variables](./environment-variables.md) — the canonical `FLUID_*` index
- [Credential resolver](./credential-resolver.md) — `${SECRET:...}` resolution order
