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

Stage 3 writes `<out>/schedule/<product-id>[__<env>]/<build-id>_dag.py`: one directory per product and environment, one file per scheduled build. The environment comes from `--env`, or from `$FLUID_ENV` when `--env` is not given. With no environment the directory is just `<product-id>/`.

| | With an environment | With no environment |
| --- | --- | --- |
| Directory | `<product-id>__<env>/` | `<product-id>/` |
| Airflow `dag_id` | `<product>__<env>__<build>` | `<product>__<build>` |

Airflow keys run history on the `dag_id`, so a DAG that moves to an environment-bound id starts a new history.

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
| `--verify-signature` | Refuse to push DAGs unless the bundle's cosign signature verifies. **Requires `--bundle PATH`**: passing `--verify-signature` alone aborts with `schedule_sync_verify_signature_missing_bundle`. See [`fluid verify-signature`](./verify-signature.md). |
| `--verify-key PATH` | Keyed-mode verification public key (path or KMS URI), matching bundles signed with `bundle --sign --sign-key`. Selects keyed verification over the default keyless mode. Ignored unless `--verify-signature` is set. |
| `--verify-identity-regexp REGEXP` | Regexp matching the acceptable OIDC signer identity (keyless mode). Default `.*` accepts **any** signer: pin this in production to `https://github.com/<your-org>/.*` or equivalent. Ignored unless `--verify-signature` is set, and ignored in keyed mode (`--verify-key`). |
| `--verify-oidc-issuer-regexp REGEXP` | Regexp matching the acceptable OIDC issuer (keyless mode). Default `.*` accepts any. Pin to `https://token.actions.githubusercontent.com` to force GitHub Actions signers only, or to your GitLab OIDC issuer URL. Ignored unless `--verify-signature` is set, and ignored in keyed mode (`--verify-key`). |
| `--git-commit-author "Name <email@host>"` | Override the git commit author for `git+ssh://` destinations. When unset, git uses the runner's `user.name` / `user.email` from git config. Recommended for CI and service accounts so commits are attributable to a deterministic identity (e.g. `fluid-bot <bot@example.com>`). |
| `--timeout SECONDS` | Per-subprocess timeout. Default 600, hard cap 3600. |
| `--report PATH` | Write a JSON result summary. See [The report](#the-report). |

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
[schedule-sync] note: bronze.customer_subscriptions__aws/ now holds bronze.customer_subscriptions's DAGs for env aws. forge-cli 0.16.7 and earlier synced them to bronze.customer_subscriptions/ with dag ids bronze.customer_subscriptions__<build>, and this destination cannot be read here to retire those. Delete bronze.customer_subscriptions/'s DAG files for env aws once (each is a DAG whose FLUID_ENV_NAME is 'aws'), or Airflow runs bronze.customer_subscriptions__<build> beside bronze.customer_subscriptions__aws__<build>.
```

With `--delete-scope destination` on a transport that deletes, the whole-destination mirror removes the old directory.

## The report

`--report PATH` writes a JSON summary with these keys: `command`, `scheduler`, `env`, `dags_dir`, `delete_scope`, `dry_run`, `overall_exit`, `results` and `superseded_scopes`. Each entry of `results` has `argv`, `dry_run`, `duration_s`, `exit_code`, `stdout_tail` and `stderr_tail`. Each entry of `superseded_scopes` names an environment directory that replaced an old one:

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
3. **Nothing to schedule**: the contract has no `orchestration.engine` and no build with a schedule trigger, so stage 3 emitted no DAG.

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
  --bundle dist/bundle.tgz
# Refuses to push if the source tgz bundle's cosign signature doesn't verify
```

## Notes

- Each dispatch needs its tool on `PATH`: `aws` (`s3://` destinations and `mwaa`), `gsutil` (`gs://`), `az` (`az://`), `rsync` (`file://`, `ssh://`, `git+ssh://`), `scp` (`scp://`), `git` (`git+ssh://`), `gcloud` (`composer`), `astro`, `prefect` or `dagster-cloud`. [`fluid doctor`](./doctor.md) does not check for `astro`, `prefect` or `dagster-cloud`. A missing tool fails `schedule-sync` with `schedule_sync_binary_not_on_path` (exit `2`) before anything is pushed, `--dry-run` included.
- `--dry-run` short-circuits before the subprocess runs and emits the (redacted) planned argv. Nothing about the destination changes.
- Exit codes: `0` = pushed (or dry run complete); `1` = push failure (a subprocess exited non-zero, or the bundle signature did not verify); `2` = config error: a missing or empty `--dags-dir`, a `--dags-dir` that is not product-scoped, an invalid identifier, a bad scheduler choice or destination, or a scheduler binary missing from `PATH`.
- Path-B schedulers (EventBridge, Snowflake Tasks, MWAA-native) apply their schedules inside stage-7 apply via `SchedulePlanner`. Stage 11 is a no-op for those contracts.
