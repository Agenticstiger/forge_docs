# `fluid schedule-sync`

Stage 11 of the 11-stage pipeline. Push the DAG files that [`fluid generate artifacts`](./generate-artifacts.md) (or `fluid generate schedule`) wrote to a scheduler control plane. Path-A only (DAG-file push); Path-B engines like EventBridge and Snowflake Tasks apply their schedules inside stage-7 `apply`, so stage 11 is a no-op for them.

Added in `0.8.0`.

## Syntax

```bash
fluid schedule-sync --scheduler NAME --dags-dir PATH [--destination URL] [options]
```

## Example

Sync one product's DAGs into a shared Airflow DAG bucket. Stage 3 wrote one directory per product and environment under `dist/artifacts/schedule/`:

```bash
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination s3://my-airflow-dags/team-x/ \
  --env prod
```

```text
[schedule-sync] scheduler=airflow dags-dir=.../dist/artifacts/schedule env=prod delete-scope=product dry-run=False
[schedule-sync] → /usr/local/bin/aws s3 sync .../schedule/bronze.customer_subscriptions__prod/ s3://my-airflow-dags/team-x/bronze.customer_subscriptions__prod/ --delete
[schedule-sync] note: bronze.customer_subscriptions__prod/ now holds ...
[schedule-sync] ✔ airflow sync complete (1 subprocess(es))
```

The `note` line is the [upgrade step](#upgrading-from-0-16-7-and-earlier) for a destination the CLI cannot read.

Each top-level directory of `--dags-dir` is mirrored into the same-named directory of the destination, with deletion. Nothing outside those directories is touched, so other products' DAGs in the same bucket survive.

## DAG layout

Stage 3 writes `<out>/schedule/<product-id>[__<env>]/<build-id>_dag.py`: one directory per product and environment, one file per DAG: one for each scheduled build, and one for builds that `builds[].dependencies` link, named after the build that carries the trigger (*since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966)*; see [Build graphs and dataset triggers](../advanced/airflow.md#build-graphs-and-dataset-triggers)). The environment comes from `--env`, or from `$FLUID_ENV` when `--env` is not given. With no environment the directory is just `<product-id>/`.

| | With an environment | With no environment |
| --- | --- | --- |
| Directory | `<product-id>__<env>/` | `<product-id>/` |
| Airflow `dag_id` | `<product>__<env>__<build>` | `<product>__<build>` |

Airflow keys run history on the `dag_id`, so a DAG that moves to an environment-bound id starts a new history. [Stage 11 of the pipeline walkthrough](../walkthrough/11-stage-pipeline.md#stage-11-schedule-sync) runs this step in a generated pipeline.

## Options

### Scheduler target

| Option | Description |
| --- | --- |
| `--scheduler` | One of `airflow`, `mwaa`, `composer`, `astronomer`, `prefect`, `dagster`. Required. |
| `--dags-dir` | Directory of DAG files to push (typically `dist/artifacts/schedule/`). Required. |

### Per-scheduler transport

| Option | Scheduler | Description |
| --- | --- | --- |
| `--destination URL` | `airflow` / `mwaa` | Destination for the DAG files. `airflow` supports `s3://`, `gs://`, `az://`, `file://`, `ssh://`, `scp://`, `git+ssh://`, or a bare path. `mwaa` supports `s3://` only. Required for both. |
| `--environment-name NAME` | `composer` / `astronomer` | Composer environment name or Astronomer deployment name. |
| `--location REGION` | `composer` | GCP region (e.g. `europe-west1`). |
| `--workspace NAME` | `prefect` / `dagster` | Prefect workspace or dagster-cloud deployment name. See [Dispatch](#dispatch) for what each scheduler does with it. |

`--workspace` and `--environment-name` accept only letters, digits, `.`, `_` and `-`, up to 128 characters. A value such as `team-x/prod` is refused with `schedule_sync_invalid_ident` (exit `2`).

### Behaviour

| Option | Description |
| --- | --- |
| `--env` | Env tag recorded in the logs and in the `--report`. Defaults to `$FLUID_ENV`, else `dev`. It does not load an overlay: `schedule-sync` takes no contract. Which environment's old DAGs are retired comes from each DAG's own `FLUID_ENV_NAME`, not from `--env`. |
| `--delete-scope {product,destination,none}` | Where stale DAGs may be deleted at the destination. Default `product`. See [What gets deleted](#what-gets-deleted). |
| `--dry-run` | Log the planned subprocess argv, with secrets redacted, without executing it. The scheduler's CLI must still be on `PATH`: without it the run fails with `schedule_sync_binary_not_on_path` and prints no argv. |
| `--bundle PATH` | Path to the signed source tgz bundle the DAGs were generated from. Required whenever `--verify-signature` is set; ignored otherwise. |
| `--verify-signature` | Refuse to push DAGs unless the bundle's cosign signature verifies, from the Sigstore bundle beside it (`<bundle>.sigstore.json`, what `fluid bundle --sign` writes; *on forge-cli `main`, not yet in a release, [forge-cli #COS](https://github.com/Agenticstiger/forge-cli/pull/COS)*). **Requires `--bundle PATH`**: passing `--verify-signature` alone aborts with `schedule_sync_verify_signature_missing_bundle`. See [`fluid verify-signature`](./verify-signature.md). |
| `--verify-key PATH` | Keyed-mode verification public key (path or KMS URI), matching bundles signed with `bundle --sign --sign-key`. Selects keyed verification over the default keyless mode. Ignored unless `--verify-signature` is set. |
| `--verify-certificate-identity ID`, `--verify-certificate-oidc-issuer URL` | Keyless: the signer's exact certificate identity and OIDC issuer. *On forge-cli `main`, not yet in a release ([forge-cli #COS](https://github.com/Agenticstiger/forge-cli/pull/COS)).* |
| `--verify-identity-regexp REGEXP` | Keyless: a regexp the signer's identity must match, instead of the exact identity. Keyless verification names its signer, exactly or by regexp: there is no default (through 0.41.0 it was `.*`, which any Sigstore certificate matches), and a missing or empty one exits `2` with `signing_identity_not_pinned`. |
| `--verify-oidc-issuer-regexp REGEXP` | Keyless: a regexp the signer's OIDC issuer must match, instead of the exact issuer. |
| `--git-commit-author "Name <email@host>"` | Override the git commit author for `git+ssh://` destinations. When unset, git uses the runner's `user.name` / `user.email` from git config. Recommended for CI and service accounts so commits are attributable to a deterministic identity (e.g. `fluid-bot <bot@example.com>`). |
| `--timeout SECONDS` | Per-subprocess timeout. Default 600, hard cap 3600. |
| `--report PATH` | Write a JSON result summary. See [The report](#the-report). |

## Waiting for Airflow to parse the files (since 0.37.0)

A push only puts files in place. Airflow reads them later, and a file with an import error never becomes a DAG. With `--airflow-url`, stage 11 waits until Airflow has parsed every pushed file, on Airflow 2 and Airflow 3, and fails the stage when one does not import.

```bash
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination s3://my-airflow-dags/team-x/ \
  --airflow-url https://airflow.example.org
```

To check files your own deploy already put in place, push nothing:

```bash
fluid schedule-sync --scheduler airflow --dags-dir dist/artifacts/schedule/ --check-only \
  --airflow-url https://airflow.example.org
```

The check works with `--scheduler airflow`, `astronomer` and `composer`. MWAA, Prefect and Dagster are refused with `--airflow-url` (`schedule_sync_airflow_unsupported_scheduler`, exit `2`). Without `--airflow-url` the stage behaves as before.

### Flags

| Option | Description |
| --- | --- |
| `--airflow-url URL` | The Airflow API server (on Airflow 2, the webserver). `https`, or `http` to a loopback host. The URL holds no user name, password, query or fragment. |
| `--airflow-api {auto,v1,v2}` | The REST dialect: `v2` for Airflow 3 (`/api/v2`), `v1` for Airflow 2 (`/api/v1`). Default `auto` detects it. |
| `--airflow-wait SECONDS` | How long to wait for the parse. Default 600, at most 3600. No request outlives it. Airflow lists new files every `dag_dir_list_interval` (Airflow 2) or `refresh_interval` (Airflow 3), 300 seconds by default, so keep it above that. |
| `--airflow-bundle NAME` | Airflow 3: the DAG bundle the files belong to. DAGs and import errors of other bundles are ignored. |
| `--airflow-bundle-version VERSION` | Airflow 3, a versioned bundle: wait until the pushed DAGs report this version. A commit may be abbreviated to 7 or more hex digits. Default: the commit a `git+ssh` push made, where the bundle is versioned. |
| `--check-only` | Push nothing. Check the files under `--dags-dir` in Airflow. |

`--airflow-bundle` and `--airflow-bundle-version` need Airflow 3.

### Credentials

Give the credential as a secret reference in the operator environment. A project `.env` file cannot set these variables. Set one, not both.

| Variable | Holds | Sent as |
| --- | --- | --- |
| `FLUID_AIRFLOW_TOKEN_REF` | An API token | A bearer token, on both majors |
| `FLUID_AIRFLOW_CREDENTIAL_REF` | `user:password` | HTTP Basic on Airflow 2. On Airflow 3, exchanged for a token at `POST /auth/token`. |

A reference is `env://NAME`, `file://`, `vault://` or `aws-sm://`. Run [`fluid secrets check`](./secrets.md) to see why one does not resolve. The Airflow user needs read access to DAGs and import errors (the Viewer role). To compare the source Airflow stores with the pushed file, it also needs to read DAG code.

Plain HTTP is refused for any host but loopback, unless `FLUID_AIRFLOW_ALLOW_INSECURE_HTTP` is set to `true` where plain HTTP is intended. A request to a loopback host never goes through a proxy. A redirect is never followed.

### What the check does

1. Before anything is pushed, it reads the Airflow version, signs in, and reads import errors and DAGs. A check that cannot run leaves nothing pushed.
2. It pushes the files (unless `--check-only`).
3. It waits, up to `--airflow-wait`, until every pushed file is parsed with no import error.

What counts as parsed:

- On an Airflow 3 Git DAG bundle, the file's DAGs must report the commit the `git+ssh` push made (or `--airflow-bundle-version`).
- Elsewhere, the source Airflow stores for the file must be the pushed file, and Airflow must then save two clean parses of it, the later at least 60 seconds after the parse it showed when the source first matched. A parse already running when the files landed read the old file.
- A user who may not read DAG code gets a pass marked not proven after two clean parses 60 seconds apart.
- A failure counts from two stamps of the file's import error and stands once they are 60 seconds apart.
- A DAG that never appears is reported as not parsed. On Airflow 3, an import error of a file with no registered DAG is shown only to a user who may read all import errors.
- A file whose DAG ids forge cannot read holds the wait until Airflow lists a DAG from it or shows its import error. A helper module is not waited for (its import makes no call and it never names `globals`), but an import error Airflow shows for it fails the check.

### The result

| Result | Exit | Code |
| --- | --- | --- |
| Every file parsed, no import error | `0` | |
| Parsed, but not proven (the user may not read DAG code) | `0` | `schedule_sync_airflow_unproven` |
| A file fails to import | `1` | `schedule_sync_airflow_import_errors` |
| A file is not parsed in time | `1` | `schedule_sync_airflow_not_parsed` |

The [report](#the-report) holds an `airflow_check` block that names each file and its result.

### Errors

| Code | Cause and fix |
| --- | --- |
| `schedule_sync_airflow_flags` | An `--airflow-*` flag or `--check-only` without `--airflow-url`, or a bundle flag on Airflow 2. Exit `2`. |
| `schedule_sync_airflow_unsupported_scheduler` | `--airflow-url` with `mwaa`, `prefect` or `dagster`. Exit `2`. |
| `schedule_sync_airflow_no_dag_files` | `--dags-dir` holds no `.py` file Airflow would parse. Exit `2`. |
| `schedule_sync_airflow_bad_url` | Pass `https://<host>[/<prefix>]` with no credentials, query or fragment. |
| `schedule_sync_airflow_insecure_url` | Use `https`, or set `FLUID_AIRFLOW_ALLOW_INSECURE_HTTP=true`. |
| `schedule_sync_airflow_credentials` | Set exactly one of the two credential variables to a secret reference. |
| `schedule_sync_airflow_unreachable` | The server did not answer. A restarting server answers 502 or 503 for a while: raise `--airflow-wait` or re-run. |
| `schedule_sync_airflow_api_not_found` | Pass the root URL of the API server, with the path prefix it is served under. |
| `schedule_sync_airflow_api_mismatch` | Leave `--airflow-api` at `auto`, or pass `v2` for Airflow 3 and `v1` for Airflow 2. |
| `schedule_sync_airflow_unsupported_version` | The URL is not an Airflow 2.x or 3.x API server. |
| `schedule_sync_airflow_auth_failed` | The credential was refused. Airflow 2 takes a password only with the `basic_auth` API backend enabled; Airflow 3 issues a token at `POST /auth/token`. |
| `schedule_sync_airflow_forbidden` | Give the Airflow user read access to DAGs and import errors. |
| `schedule_sync_airflow_redirect` | Pass the URL the redirect points at. A sign-in page means a proxy sits in front of Airflow. |
| `schedule_sync_airflow_bad_response` | The URL points at another service, not Airflow's API server. |
| `schedule_sync_airflow_import_errors` | Fix the import error the report names, then re-run. Parse the DAG locally against the same Airflow major before pushing. |
| `schedule_sync_airflow_not_parsed` | Raise `--airflow-wait`. On an Airflow 3 Git bundle, check that the bundle tracks the branch the push went to. |
| `schedule_sync_airflow_unproven` | Let the Airflow user read DAG code so the check can compare the stored source with the pushed file. Exit `0`. |

## What gets deleted

`--delete-scope` decides which files the sync may remove at the destination.

| Value | Behaviour |
| --- | --- |
| `product` (default) | Every top-level directory of `--dags-dir` is one product's DAGs. Each is mirrored, with deletion, into the same-named directory at the destination. Nothing outside those directories is touched. |
| `destination` | Mirror `--dags-dir` onto the whole destination and delete everything else there. Use it only for a destination that this product owns alone. |
| `none` | Copy, delete nothing. |

Only some transports delete:

| Transport | Deletes |
| --- | --- |
| `airflow` with `s3://` (`aws s3 sync --delete`), `gs://` (`gsutil -m rsync -r -d`), `file://` or a bare path (`rsync -av --delete`), `ssh://` (`rsync -av --delete -e ssh`), `git+ssh://` (rsync into a clone, then commit and push) | Yes, as `--delete-scope` says |
| `mwaa` (`aws s3 sync --delete`) | Yes, as `--delete-scope` says |
| `airflow` with `az://` or `scp://`, `composer`, `astronomer`, `prefect`, `dagster` | Never; `--delete-scope` has no effect |

On the transports that delete, `--delete-scope product` refuses a `--dags-dir` that has loose files, symlinks or directory names that are not plain identifiers at the top, with exit `2`, even under `--dry-run`:

```text
❌ schedule_sync_dags_dir_not_product_scoped  [ERR_SCHEDULE_SYNC_DAGS_DIR_NOT_PRODUCT_SCOPED]
  loose_files: ['my_dag.py']
  hint: --delete-scope product (the default) mirrors each top-level directory of --dags-dir into the
same-named directory of the destination, so it never deletes another product's DAGs. Put the files in a
<product-id>/ directory (fluid generate artifacts does; for fluid generate schedule use -o
<dags-dir>/<product-id>/), or pass --delete-scope none to copy without deleting, or --delete-scope
destination to mirror onto (and delete everything else in) the whole destination
```

A flat DAG folder, such as the default output of `fluid generate schedule`, therefore needs one of: writing the DAGs to `<dags-dir>/<product-id>/` with `fluid generate schedule -o`, `--delete-scope none`, or `--delete-scope destination`. The pipelines [`fluid generate ci`](./generate.md) writes pass `--delete-scope product`.

## Upgrading from 0.16.7 and earlier

Before `0.17.0`, an environment's DAGs were written to `<product-id>/` with `dag_id` `<product>__<build>`. Now they go to `<product-id>__<env>/` as `<product>__<env>__<build>`. The first sync after upgrading has to retire the old DAGs. If it does not, Airflow runs `<product>__<build>` beside `<product>__<env>__<build>`, and both apply the same product against the same state.

`schedule-sync` retires them itself when `--scheduler airflow` and `--delete-scope product` are used with a local path (`file://` or a bare path) or a `git+ssh://` destination, the two it can read. It deletes only the files in `<product-id>/` that were rendered for the same product and the same environment under the old id. A DAG with no environment, another environment's DAG, and any file that is not a rendered DAG stay. For every other transport it prints the one step left to do. It prints it on every sync to such a destination, because it cannot tell whether the old DAGs are there:

```text
[schedule-sync] note: bronze.customer_subscriptions__aws/ now holds bronze.customer_subscriptions's DAGs for env aws. forge-cli 0.16.7 and earlier synced them to bronze.customer_subscriptions/ with dag ids bronze.customer_subscriptions__<build>, and this destination cannot be read here to retire those. Delete bronze.customer_subscriptions/'s DAG files for env aws at the destination once (each is a DAG whose FLUID_ENV_NAME is 'aws'), or Airflow runs bronze.customer_subscriptions__<build> beside bronze.customer_subscriptions__aws__<build>.
```

With `--delete-scope destination` on a transport that deletes, the whole-destination mirror removes the old directory.

## The report

*(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* When stage 11 of [`fluid ship`](./ship.md) runs, it passes `--report runtime/schedule-sync-report.json`, so a generated pipeline keeps this report there.

`--report PATH` writes a JSON summary with these keys: `command`, `scheduler`, `env`, `dags_dir`, `delete_scope`, `dry_run`, `overall_exit`, `results` and `superseded_scopes`. *(since 0.37.0)* With `--airflow-url` it also holds `airflow_check`. Each entry of `results` has `argv`, `dry_run`, `duration_s`, `exit_code`, `stdout_tail` and `stderr_tail`. Each entry of `superseded_scopes` names an environment directory that replaced an old one:

```json
"superseded_scopes": [
  {
    "env": "aws",
    "old_dags_retired": true,
    "replaces": "bronze.customer_subscriptions",
    "scope": "bronze.customer_subscriptions__aws"
  }
]
```

`old_dags_retired` is `false` when the note above was printed and the step is yours.

## Dispatch

| `--scheduler` | Dispatches to |
| --- | --- |
| `airflow` | Routed by the destination's URL scheme: `aws s3 sync`, `gsutil -m rsync`, `az storage blob upload-batch`, `rsync` (`file://` and `ssh://`), `scp -r`, or `git` plus `rsync` (`git+ssh://`). |
| `mwaa` | `aws s3 sync <source> <destination> --delete` (no `--delete` under `--delete-scope none`). |
| `composer` | `gcloud composer environments storage dags import --environment <name> --location <region> --source=<dags-dir>`. |
| `astronomer` | `astro deploy [<environment-name>] --dags`, run from the parent of `--dags-dir`, where `astro` reads its project configuration. |
| `prefect` | `prefect deploy --all`, run in `--dags-dir`, against the `prefect.yaml` there. |
| `dagster` | `dagster-cloud deploy [--deployment <workspace>] --location-file dagster_cloud.yaml`, run in `--dags-dir`. |

`--workspace` does not select a Prefect workspace: for `prefect` it is only logged, and the deploy goes to whichever workspace is current, so run `prefect cloud workspace set` first. Prefect needs a `prefect.yaml`, and Dagster Cloud a `dagster_cloud.yaml`, inside `--dags-dir`.

The dispatch does not invoke a shell: it builds an argv list and calls `subprocess.run(argv, shell=False)`. User-supplied values (`--destination`, `--environment-name`, `--location`, `--workspace`) are validated against a strict whitelist before they reach `argv`, and shell metacharacters are rejected.

## Self-gating in generated CI

The Jenkins and 7-system templates from `fluid generate ci` self-gate stage 11 on `dist/artifacts/schedule/` existing and holding files. These cases collapse into one INFO-level skip with `exit 0`:

1. **Reference-only contract**: stage 3 auto-skipped the schedule emitter.
2. **Stage 3 was toggled off**: there is no `dist/artifacts/` tree at all.
3. **Nothing to schedule**: the contract has no `orchestration.engine` and no build with a schedule trigger, so stage 3 emitted no DAG. *(since 0.34.0, [forge-cli #1018](https://github.com/Agenticstiger/forge-cli/pull/1018))* A Spark stream that declares `execution.retries` counts as a build with a schedule.

Direct callers of `fluid schedule-sync` still get the strict hard-fail (`schedule_sync_dags_dir_missing`, exit `2`), so typos surface loudly.

## More examples

### Airflow via a shared volume

```bash
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination file:///opt/airflow/dags \
  --env dev
```

### Composer

```bash
fluid schedule-sync \
  --scheduler composer \
  --dags-dir dist/artifacts/schedule/ \
  --environment-name my-composer-env \
  --location europe-west1 \
  --env prod
```

### Astronomer

```bash
fluid schedule-sync \
  --scheduler astronomer \
  --dags-dir dist/artifacts/schedule/ \
  --environment-name my-deployment \
  --env prod
```

### Prefect and Dagster Cloud

```bash
prefect cloud workspace set --workspace myorg/prod

fluid schedule-sync --scheduler prefect \
  --dags-dir dist/artifacts/schedule/

fluid schedule-sync --scheduler dagster \
  --dags-dir dist/artifacts/schedule/ \
  --workspace prod
```

### Hand-generated DAGs

`fluid generate schedule` writes a flat folder by default. Write it into a product directory so that `--delete-scope product` accepts it:

```bash
fluid generate schedule contract.fluid.yaml -o dags/gold.orders_v1/
fluid schedule-sync --scheduler airflow --dags-dir dags --destination s3://my-airflow-dags/team-x/
```

### Dry run (preview argv, no push)

```bash
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination s3://my-airflow-dags/team-x/ \
  --dry-run
```

### Signature-gated push (supply chain)

```bash
# Pair with `fluid bundle --sign --attest` in stage 1.
# --verify-signature requires --bundle pointing at the signed tgz.
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination s3://my-airflow-dags/team-x/ \
  --verify-signature \
  --verify-certificate-identity 'https://github.com/<your-org>/<repo>/.github/workflows/ci.yml@refs/heads/main' \
  --verify-certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  --bundle dist/bundle.tgz
# Refuses to push if the source tgz bundle's cosign signature doesn't verify for that signer
```

## Notes

- Each dispatch needs its tool on `PATH`: `aws` (`s3://` destinations and `mwaa`), `gsutil` (`gs://`), `az` (`az://`), `rsync` (`file://`, `ssh://`, `git+ssh://`), `scp` (`scp://`), `git` (`git+ssh://`), `gcloud` (`composer`), `astro`, `prefect` or `dagster-cloud`. [`fluid doctor`](./doctor.md) does not check for `astro`, `prefect` or `dagster-cloud`. A missing tool fails `schedule-sync` with `schedule_sync_binary_not_on_path` (exit `2`) before anything is pushed, `--dry-run` included.
- `--dry-run` short-circuits before the subprocess runs and emits the (redacted) planned argv. Nothing about the destination changes.
- Exit codes: `0` = pushed (or dry run complete); `1` = push failure (a subprocess exited non-zero, or the bundle signature did not verify); `2` = config error: a missing or empty `--dags-dir`, a `--dags-dir` that is not product-scoped, an invalid identifier, a bad scheduler choice or destination, or a scheduler binary missing from `PATH`.
- Path-B schedulers (EventBridge, Snowflake Tasks) apply their schedules inside stage-7 apply via `SchedulePlanner`. Stage 11 is a no-op for those contracts. *([forge-cli #715](https://github.com/Agenticstiger/forge-cli/pull/715), since 0.20.0)* MWAA is not one of them. On `aws`, `fluid apply` refuses a contract that asks it for an MWAA environment (`orchestration.engine: airflow` with an `orchestration.schedule`) with `unsupported_binding`, kind `mwaa-environment-not-emitted`; it used to report success and create none. Run the DAGs on an environment you own and push them with `--scheduler mwaa`; see [MWAA on AWS](../advanced/airflow.md#mwaa-on-aws).
