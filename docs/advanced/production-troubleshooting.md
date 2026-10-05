# Production Troubleshooting

Symptom, diagnosis and fix for fluid pipelines in production. The error names, messages and commands on this page were checked against CLI 0.18.1. Many errors the CLI prints end with a link to this page, so the sections below are organized by the event name or class name you see in the output.

::: tip First responder
Start an incident with `fluid doctor`. It reports infrastructure and feature checks, forge copilot readiness and the active state-store backend, and `--env` lists the FLUID runtime kill switches with their current values.
:::

## Reading an error

A failure prints in one of two shapes, and both are catalogued here and on [Typed CLI Errors](./typed-cli-errors.md):

```text
❌ bundle_env_mismatch  [ERR_BUNDLE_ENV_MISMATCH]
  bundle_env: dev
  requested_env: prod
  hint: the bundle was built for env 'dev' but this stage was asked for env 'prod'. ...
```

The event name (`bundle_env_mismatch`) is stable, and so is the `ERR_` code derived from it; match on either in CI. The other shape is a panel titled with the error, with `why`, `fix` and `doc` rows, raised by build runners and providers. Look the name up in the section that matches the stage that failed.

## First responder: `fluid doctor`

| Invocation | What you get |
|---|---|
| `fluid doctor` | Infrastructure and feature checks, forge copilot readiness and the memory-store backend |
| `fluid doctor --env` | The FLUID runtime kill switches doctor knows: current value, source, default and a one-line description |
| `fluid doctor --scope <scope>` | Acquisition-stack checks for one scope: `authoring`, `pipeline`, `ingestion`, `infra`, `catalog` or `all`. There is no default scope: without the flag these checks do not run |
| `fluid doctor --json` | Without `--scope` or `--env`, only the store-backend section. With `--scope`, the checks for that scope as JSON (`scope`, `ok`, `results[]` with `name`, `severity`, `detail`, `fix`, `doc`). With `--env`, the kill-switch table |
| `fluid doctor --features-only` | Feature availability only; skips the infrastructure checks |
| `fluid doctor --extended` | Also runs optional workspace diagnostics through `scripts/diagnose.sh`, when that script is installed |
| `fluid doctor --out-dir runtime/diag` | Where diagnostic files are written. Default `runtime/diag` |

For an escalation, attach the output of `fluid doctor --scope all --json`.

## Pipeline gates

These errors stop a [generated pipeline](./operating-in-ci.md) before it changes anything.

### Plan-binding rejections

**Symptom:** `fluid apply` refuses to run with a `PlanBindingError` before any DDL executes.

Each error carries a stable `kind` tag, a distinct event CI can match:

| `kind` | Diagnosis | Fix |
|---|---|---|
| `bundle-mismatch` | The plan's `bundleDigest` disagrees with the bundle on disk: the bundle was swapped after `plan` ran, or the contract was re-bundled without re-planning | Re-run `fluid bundle`, then `fluid plan`, and apply the fresh pair |
| `plan-tamper` | The plan's `planDigest` disagrees with the recomputed digest: `plan.json` was edited between plan and apply (a missing or empty `planDigest` is treated the same) | Do not hand-edit `plan.json`; regenerate it with `fluid plan` |
| `bundle-missing` | The plan carries a `bundleDigest` but no bundle was supplied or found. The gate fails closed rather than skipping | Pass `--bundle <path-to-tgz>` or restore the sibling `.tgz` |
| `bundle-manifest-missing`, `bundle-manifest-invalid` | The tgz has no `MANIFEST.json`, or its per-file SHAs or merkle root do not verify (a truncated or corrupted archive) | Re-run `fluid bundle --format tgz` |
| `bundle-merkle-mismatch` | The merkle root recomputed from the bundle's bytes disagrees with the root declared in its `MANIFEST.json` | Rebuild the bundle; treat it as possible tampering |
| `binding-mode-missing`, `binding-mode-invalid`, `binding-mode-mismatch` | The plan's `bindingMode` is absent, is neither `bound` nor `raw`, or contradicts the presence of `bundleDigest` (for example `bundleDigest` stripped to dodge the bundle check) | Regenerate through `fluid plan`: the plan came from an older CLI or was edited |

::: warning `--no-verify-plan-binding` is a disaster-recovery hatch, not a fix
When the bundle is unrecoverable, `fluid apply --no-verify-plan-binding` skips the verification and logs at WARNING so the audit trail records it. If you reach for it during routine operations, regenerate the bundle and plan pair instead.
:::

### Environment, mode and plan-file errors

| Event | Diagnosis | Fix |
|---|---|---|
| `bundle_env_mismatch` | A bundle is built for one env and is never re-overlaid. A later stage was asked for another `--env` | Rebuild with `fluid bundle <contract> --env <env> --format tgz`, or pass the env the bundle was built for |
| `plan_env_mismatch` | A plan records the env it was made for, and an `*-and-build` apply was given a different `--env` | Apply with the recorded env (or without `--env`), or re-plan with the env you want |
| `apply_build_id_requires_build_mode` | `--build-id` selects which build runs, and the mode (for example `dry-run`) runs none | Use `--mode amend-and-build` or `replace-and-build`, or drop `--build-id` |
| `apply_plan_unreadable` | The plan file is missing, is not JSON, or is truncated | Regenerate it with `fluid plan --out` |
| `apply_plan_mode_mismatch` | The plan was made for a different `--mode` than apply was given | Re-run `fluid plan --mode <mode>` with the mode you will apply |
| `contract_tests_baseline_missing`, `contract_tests_bad_baseline` | `fluid contract-tests --baseline` names a file that does not exist, or whose content is not a baseline | Create one with `fluid contract-tests <contract> --write-baseline baseline.schema.json` |

### The federation check

**Symptom:** the apply log has `apply_consumes_drift` and the apply carried on.

The check for a `consumes[]` entry that names an `upstreamWorkspace` is advisory: it warns and applies anyway.

```text
apply_consumes_drift: 1 federated consumes[] entry could not be confirmed in sync (1 drift). Applying anyway. Details: {...}
```

The `Details` JSON lists each violation with a `violation_kind` (`drift`, `unreachable`, `unpinned`, `unknown-workspace` or `not-wired`), plus `counts_by_kind`, `drift_count` and `unreachable_count`. A `federation_gate_error` line means the validator itself failed and the pins were not checked. To block a pipeline on this, match `apply_consumes_drift` in the apply log; the exit code does not change. The upstream fetch is bounded by `FLUID_FEDERATION_TIMEOUT_SECONDS` (default 30) and uses the `git` binary. `--no-verify-federation` silences the check.

### Apply data-loss gate

**Symptom:** apply aborts and tells you to re-run with `--allow-data-loss`.

| Situation | Diagnosis | Fix |
|---|---|---|
| `--mode replace` or `replace-and-build` outside `dev`, or the target has rows | Replace modes need an explicit `--allow-data-loss` | Confirm the target should be rebuilt, then re-run with the flag. A pre-replace snapshot is taken, so [`fluid rollback`](../cli/rollback.md) can restore it |
| OpenTofu apply blocked with an `opentofu_data_loss_gate` event | The IaC plan wants to destroy resources that hold data | The same override. The bypass logs a WARNING and an `opentofu_destructive_gate_override` event; search for that tag when auditing who overrode the gate |

## State and region errors

**Symptom:** `fluid apply` stops before `tofu apply` with a state or region error.

Remote OpenTofu state is keyed per contract and provider. See [Environment variables](./environment-variables.md#apply-state-and-opentofu) for the key layout. The first apply after upgrading to a release with per-provider keys moves state from `fluid/<id>/terraform.tfstate` to `fluid/<id>/<provider>/terraform.tfstate` when the old key holds this provider's resources, prints a `state move:` line, and leaves the old object where it was. `--dry-run` never moves state, and `fluid diff` and `fluid verify --state-drift` read the old key while a move is pending.

| Event | Diagnosis | Fix |
|---|---|---|
| `state_shared_with_another_provider` | The remote key does not name this provider and already holds another cloud's resources, so a plan would read them as orphans to destroy | Give each provider its own state: a key that names the provider in `--state-backend` (for example `fluid/<id>/<provider>/terraform.tfstate`), or a bucket-only `FLUID_STATE_BACKEND` |
| `state_migration_ambiguous` | The old key holds a state of two clouds, or of a provider no plugin emits, and the new key holds none, so nothing was moved | Move it yourself (`tofu init -migrate-state` from a directory configured with the old key), or name the key this apply should use |
| `state_migration_raced` | The new key received a different state while this apply was about to move the old one there | Nothing was moved. Re-run once the other job has finished |
| `state_migration_failed` | `tofu init` could not initialise on the old key, or `-force-copy` could not copy | Read the tail of the message for the OpenTofu error (credentials, bucket access); fix it and re-run |
| `state_migration_unverified` | After the copy, the new key holds different resources than the old one. The old object is untouched | Compare the two states before re-running |
| `state_migration_probe_failed` | The old key could not be read | Check access to the bucket and the key named in the message |
| `opentofu_region_moved` | State holds this contract's resources in a region other than the one the bindings now name. Applying would create them again and leave the originals unmanaged | If they should stay, set the binding's `location.region` to the region the error names. If they should move, empty and remove them there first (`tofu destroy` in the state directory named, with `AWS_REGION` set to the old region), then apply again |

## Contract load and overlay errors

**Symptom:** `ERR_CONTRACT_LOAD_FAILED`, or `❌ Validation error: contract_load_failed`. The CLI's suggestions for this code are generic (check the YAML, the encoding); read the `error:` line, which names the real cause.

| What the `error:` line says | Diagnosis | Fix |
|---|---|---|
| `... escapes the ref root ...` | A `$ref` names a file outside the contract's own directory tree. Since 0.18.0 a `$ref` may only name a file inside the **ref root**; URL refs, absolute paths and `..` or symlink escapes are refused | Move the fragment inside the contract's tree, or set `FLUID_REF_ROOT` to the shared directory. See [Composing a contract with `$ref`](../concepts/contract-refs.md) |
| `overlay_declared_but_missing` | `--env <env>` was given, no overlay for it exists, and the workspace's `expected-environments` declares that env for this product. The base contract would be used as if it were that env | Add `overlays/<env>.yaml`, or remove the env from `expected-environments` |
| `overlay_not_found` (a warning) | `--env <env>` matched no overlay and nothing declares it, so the base contract is used unchanged | Add the overlay, or pass an env that exists |
| `OAS-REF-EXTERNAL` in `fluid validate` | A bundled OpenAPI fragment has a `$ref` that leaves the document | Inline the referenced schema into the fragment |

## Builds and masking

**Symptom:** an acquisition or embedded-SQL build failed, or refused to start.

Build refusals print as three lines under the build (`what`, `why: ...`, `fix: ...`) and fail the build; the typed class is in the log as `embedded_sql_io_refused ... code=<Class>`.

| Class or code | Diagnosis | Fix |
|---|---|---|
| `ConsumesResolutionError` | A `consumes[]` entry cannot be bound to a relation the SQL can read | Read the `why` and `fix`. Or bind the input by hand with a `builds[].properties.parameters.inputs` entry of the name the `fix` gives; that entry wins over the `consumes` one |
| `UnreadableBindingError` | The upstream expose resolved, but to a binding this engine cannot read | Land the upstream where the engine can read it, or bind the input by hand |
| `EmbeddedSqlLandingError` | The build's own expose names a landing the embedded-SQL path will not perform | Change the expose's binding, or use an acquisition build |
| `MaskingNotAppliedError` | The expose declares `policy.privacy.masking`, and the embedded-SQL landing does not apply masking, so it refuses rather than land cleartext | Land through the DuckDB acquisition path, which applies masking |
| `EmbeddedSqlSovereigntyError` | A BigQuery read or landing the contract's `sovereignty` block does not allow | Move the binding to an allowed region, or change the policy |
| `masking_strategy_unsupported` | `strategy: k_anonymity` cannot be applied per column | Use `mask`, `hash`, `tokenize` or `encrypt` |
| `masking_secret_missing` | The salt or key variable the rule names is unset, empty, too short or not decodable | Set `FLUID_PII_HASH_SECRET` (16 bytes or more), `FLUID_PII_TOKENIZATION_KEY` (32 bytes or more) or `FLUID_PII_ENCRYPTION_SECRET_KEY` (base64 of a 16, 24 or 32 byte key) on the runner |
| `masking_column_missing`, `masking_type_incompatible` | A rule names a column the landed data lacks, or the contract declares a masked column with a type a treated value cannot have | Declare a masked column as a string type |
| `masking_policy_invalid`, `masking_dependency_missing` | A rule the runner cannot apply, or DuckDB installed without numpy | Read the message, which names columns and variable names, never values |
| `ObjectStoreEndpointError` | An `AWS_ENDPOINT_URL` override is set, but DuckDB could not be pointed at it, so reads and writes would have gone to AWS | Fix the endpoint value, or unset the override |
| `DuckDBSandboxError`, or `Cannot change configuration option ...` | Contract SQL tried to read or write outside the sandbox, fetch a URL, or change a DuckDB setting (0.18.0) | Allow the directory with `FLUID_DUCKDB_ALLOWED_DIRS`, land remote data with an acquisition build, or remove the `SET` or `PRAGMA`. See the [DuckDB sandbox](./duckdb-sandbox.md) |

Treated columns land as strings, and `fluid verify` fails a masked column that landed in cleartext.

### Build and run failures

Work the run-record surface under the state root (`./.fluid` by default; override with `--state-root`):

```bash
fluid runs status <product_id> --last 5             # recent runs of a product
fluid runs status <product_id> --build <build_id>   # pin a specific build
fluid runs logs <product_id> --component build      # component: build|infra|server|worker|dlq
fluid runs logs <product_id> --run-id <id> --grep ERROR --limit 200
fluid runs diff <product_id> --build <b> --run-a <baseline> --run-b <comparison>
```

`runs diff` reports the schema and row-count delta between two runs, the quickest way to tell whether a failure changed the data shape or only the run status. All three verbs accept `--json`.

### Cursor rewind and replay-pending markers

**Symptom:** a file appears at `.fluid/<product_id>/runtime/replay-pending.json`.

An upstream source-aligned product's cursor moved backward (a reprocess), and the runners marked every downstream product that `consumes[]` it as dirty, so a downstream does not go silently stale. The marker records what happened:

```json
{
  "upstream_product_id": "bronze.crm.customers",
  "upstream_build_id": "main_build",
  "upstream_stream": "customers",
  "old_cursor_value": "2026-04-30T00:00:00Z",
  "new_cursor_value": "2026-04-15T00:00:00Z",
  "detected_at": "2026-05-02T12:30:00Z",
  "reason": "upstream cursor rewound from '2026-04-30T00:00:00Z' to '2026-04-15T00:00:00Z'"
}
```

**Fix:** re-run the marked downstream product's build so it re-reads the rewound window, then delete the marker file. Leaving it does not affect execution, but you lose the signal for the next rewind.

## Publishing to the Command Center

**Symptom:** `fluid publish --target fluid-command-center` fails, including with `--dry-run` or `--verify-only`.

| `error_code` | Diagnosis | Fix |
|---|---|---|
| `cc_credential_missing` | No credential is configured, and publish will not call the Command Center anonymously | Set `FLUID_API_KEY` (or `FLUID_BEARER_TOKEN` for a bearer-auth catalog) |
| `cc_organization_unresolved` | No organization id is configured, and the credential belongs to no organization or several, or the organization list could not be read | `export FLUID_CC_ORG_ID=<organization id>`, or set `catalogs.fluid-command-center.organization_id` in the FLUID config |
| `cc_organization_id_blank` | `FLUID_CC_ORG_ID` is set but empty, usually an unset CI parameter. The CLI refuses to fall back, so one estate's products do not land in whichever organization the key belongs to | Set it, or unset the variable to use the fallback on purpose |

The organization comes from `organization_id`, else `FLUID_CC_ORG_ID`; with neither, a configured `organization` slug is matched against the Command Center's organization list; failing that, the credential's only organization. Products publish private unless the contract is classified `public`. For `fluid apply` run reports, see [Environment variables](./environment-variables.md#command-center).

## Generated artifacts and schedules

| Event | Diagnosis | Fix |
|---|---|---|
| `generated_path_outside_output_dir` | A contract field that becomes a file name (for example `builds[].properties.stages[].name`) contains a path separator or `..` | Rename the field |
| `generated_path_collision` | Two generated files would resolve to the same path, so one would overwrite the other | Make the two names distinct |
| `generate_artifacts_skip_schedule_no_engine`, `..._engine_none`, `..._unreadable` | `fluid generate artifacts` skipped schedule artifacts because the contract has no `orchestration.engine` and no build with `execution.trigger.schedule`, the engine is `none`, or the file could not be read | Add the engine or a scheduled build if you want DAGs |
| `schedule_sync_dags_dir_not_product_scoped` (exit 2) | `fluid schedule-sync` defaults to `--delete-scope product`, which mirrors each top-level directory of `--dags-dir` and never deletes another product's DAGs. The directory has loose files | Put the files in `<dags-dir>/<product-id>/`. `fluid generate artifacts` does; for `fluid generate schedule` use `-o <dags-dir>/<product-id>/`. Or pass `--delete-scope none` to copy without deleting |
| `lakeformation-grant-columns` | A Lake Formation grant gives a principal read access, but the contract's column restrictions let it read no column | Remove the grant, or allow the principal at least one column in `policy.authz.columnRestrictions` |
| `generate_iac_aws_account_required` | `fluid generate iac` for AWS needs the account id and does not look it up | Set `AWS_ACCOUNT_ID`. `fluid apply` resolves the account itself |

## Secrets and credentials

| Symptom | Diagnosis | Fix |
|---|---|---|
| `SecretResolutionError` from `fluid secrets login` or `rotate` | No value arrived on stdin and the prompt was cancelled | Pipe the value: `printf '%s' "$VALUE" \| fluid secrets login <ref>`. Values are read from stdin or an interactive prompt, never from argv |
| `secretRef env://NAME: environment variable not set` | A contract's `secretRef: env://NAME` names a variable that is not set on the runner | Set `NAME` in the pipeline's environment |
| `secretRef scheme '<x>' is not supported. Supported schemes: [...]` | A `secretRef` uses a scheme the runner does not implement | Use `env://`, `vault://`, `aws://`, `gcp://`, `azure://` or `file://` |
| `secretRef must be of the form '<scheme>://<identifier>'` | The `secretRef` is malformed | Fix it |
| A stored secret is stale or leaked | Rotation is needed | `printf '%s' "$NEW" \| fluid secrets rotate <ref>` (`--expires-at <ISO-8601>` is supported) |
| `CredentialError`: "Encrypted credential store at ... cannot be decrypted with the current key" | The Fernet key no longer matches the ciphertext: it was regenerated, or the store was copied from another host. The store is deliberately not wiped, so the ciphertext is still recoverable with the original key | Back up first (`cp <store> <store>.bak`). Then restore the original key, or supply it as `FLUID_ENCRYPTION_KEY` or `FLUID_ENCRYPTION_PASSPHRASE`, or, accepting the loss, remove the store and enter the credentials again |

## OpenTofu failures

| Symptom | Diagnosis | Fix |
|---|---|---|
| "tofu X.Y.Z is older than the required minimum 1.6.0" | The runner has an older `tofu`, or only `terraform`, on `PATH` | Upgrade from opentofu.org, or let the CLI provision a pinned, SHA-256-verified build: `fluid apply --ensure-opentofu` |
| `` `tofu apply` exceeded the 1800s wall-clock limit `` (exit code 124) | A large first apply, or a hung provider call, hit the per-subprocess timeout | Raise `FLUID_TOFU_TIMEOUT_SECONDS`; if it recurs on a small change set, look at provider-side throttling |
| `opentofu_init_failed` | `tofu init` failed: provider credentials, network access or the state backend | Check credentials and network, then retry |
| Apply blocked before `tofu apply` with a plan-binding error | The OpenTofu path re-verifies `plan.json` digests too | See [plan-binding rejections](#plan-binding-rejections) |

## LLM and copilot authentication failures

**Symptom:** an LLM-driven command such as `fluid forge` fails with a 401 or invalid-key error, typically right after a key rotation.

```bash
fluid ai status      # which provider, model and key source is configured
fluid ai test --provider anthropic --model <model>   # connectivity test, before saving anything
fluid ai setup       # re-run setup to store the rotated key
```

Update the key at the source `fluid ai status` reports, the provider environment variable (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) or the stored configuration, then confirm with `fluid ai test`. See [LLM providers and backends](./llm-providers.md) for the resolution order.

As of 0.18.1, `fluid ai test` with no provider configured and no `--provider` fails with `❌ Unexpected error: name 'detect_ollama_available' is not defined` and exit code 2. Name the provider, or run `fluid ai setup` first. `fluid ai test --provider <name> --json` prints a report with `ok`, `exit_code` and, on failure, an `error` object with `code`, `message` and `suggestions`.

## Where logs live

| Setting | Effect |
|---|---|
| `FLUID_LOG_FILE=<path>` (or `--log-file`) | Write logs to a file in addition to stderr |
| `FLUID_LOG_LEVEL=DEBUG` (or `--log-level`) | Verbose logging; credential-bearing values are redacted by the logging filter |
| `fluid runs logs ...` | Per-component run logs from the `./.fluid` state root |
| `runtime/out/local_apply_log.jsonl` | The local provider appends each action's result here, together with the `productId`, `exposeId` and `uri` each embedded-SQL input resolved to |
| `fluid doctor --out-dir runtime/diag` | Diagnostic file location |

On the local provider, error text in the build output, in retry log lines and in `local_apply_log.jsonl` is redacted: the value of every credential-named `{{ env.X }}` the build uses is replaced.

## Retention sweep

Run state accumulates under the state root; sweep it on a schedule:

```bash
fluid retention sweep                     # sweep ./.fluid with a structured summary
fluid retention sweep --state-root /data/pipelines/.fluid --json
```

A replay requested past the swept horizon fails with `StaleReplayError` because its manifest is gone; see [Typed CLI Errors](./typed-cli-errors.md#pipeline-operations). Balance the sweep cadence against how far back you replay.

## See also

- [Operating in CI](./operating-in-ci.md): the pipeline these failures occur in
- [Typed CLI Errors](./typed-cli-errors.md): the typed error classes, exit codes and where doc links land
- [`fluid doctor`](../cli/doctor.md), [`fluid runs`](../cli/runs.md), [`fluid retention`](../cli/retention.md), [`fluid secrets`](../cli/secrets.md): command references
- [`fluid rollback`](../cli/rollback.md): restoring a pre-replace snapshot
- [Environment variables](./environment-variables.md): the `FLUID_*` variables
