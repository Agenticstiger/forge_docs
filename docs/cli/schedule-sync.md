# `fluid schedule-sync`

Stage 11 of the 11-stage pipeline. Push DAG files emitted by `fluid generate schedule` / `fluid generate artifacts` to a scheduler control plane. Path-A-only (DAG-file-push); Path-B engines like EventBridge / Snowflake Tasks apply their schedules inside stage-7 `apply`, so stage 11 is a no-op for them.

Added in `0.8.0`.

## Syntax

```bash
fluid schedule-sync --scheduler NAME --dags-dir PATH [--destination URL] [options]
```

## Key options

### Scheduler target

| Option | Description |
| --- | --- |
| `--scheduler` | One of `airflow`, `mwaa`, `composer`, `astronomer`, `prefect`, `dagster`. Required. |
| `--dags-dir` | Directory of DAG files to push (typically `dist/artifacts/schedule/`). Required. |

### Per-scheduler transport

| Option | Scheduler | Description |
| --- | --- | --- |
| `--destination URL` | `airflow` / `mwaa` | Destination for the DAG files. Supports `s3://`, `gs://`, `az://`, `file://`, `ssh://`, `scp://`, or a bare path. Required for `airflow` and `mwaa`. |
| `--environment-name NAME` | `composer` / `astronomer` | Composer environment name or Astronomer deployment name. |
| `--location REGION` | `composer` | GCP region (e.g. `europe-west1`). |
| `--workspace NAME` | `prefect` / `dagster` | Prefect workspace or dagster-cloud deployment name. |

### Behaviour

| Option | Description |
| --- | --- |
| `--env` | Environment overlay (`dev` / `staging` / `prod`). |
| `--dry-run` | Log the planned subprocess argv without executing — safe to run in any env. |
| `--verify-signature` | Refuse to push DAGs if the source tgz bundle is unsigned or mutated. See [`fluid verify-signature`](./verify-signature.md). |
| `--timeout SECONDS` | Per-subprocess timeout. Default 600, hard cap 3600. |
| `--report PATH` | JSON result summary. |

## Dispatch table

| `--scheduler` | Dispatches to |
| --- | --- |
| `airflow` | URL-scheme-routed: `aws s3 sync`, `gsutil -m rsync`, `az storage blob sync`, `rsync` (file://), `scp` / `rsync -e ssh`. |
| `mwaa` | `aws s3 sync` to the MWAA S3 bucket, with an explicit `--exclude` for `__pycache__/`. |
| `composer` | `gcloud composer environments storage dags import`. |
| `astronomer` | `astro deploy --dags-only`. |
| `prefect` | `prefect deploy --from-dir <dags-dir>` in the named workspace. |
| `dagster` | `dagster-cloud deploy --from-dir <dags-dir>` in the named deployment. |

The CLI **never** invokes a shell; every dispatch builds an argv list and calls `subprocess.run(argv, shell=False)`. User-supplied values (`--destination`, `--environment-name`, `--location`, `--workspace`) are validated against a strict whitelist before reaching `argv`. Shell metacharacters are rejected.

## Self-gating in generated CI

The Jenkins + 7-system templates from `fluid generate ci` self-gate stage 11 on `dist/artifacts/schedule/` existence. Three conditions collapse into one INFO-level skip with `exit 0`:

1. **Reference-only contract** — stage 3 auto-skipped the schedule emitter.
2. **Stage 3 was toggled off** — no `dist/artifacts/` tree at all.
3. **No `orchestration.engine` in the contract** — schedule emitter produced zero DAGs.

Direct CLI callers of `fluid schedule-sync` still get the strict hard-fail (`schedule_sync_dags_dir_missing`, exit 2) so typos surface loud.

## Examples

### Airflow via S3 (production)

```bash
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination s3://my-airflow-dags/team-x/ \
  --env prod
```

### Airflow via shared volume (local lab)

```bash
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination file:///workspace/airflow/dags/team-x \
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

### Prefect / Dagster Cloud

```bash
fluid schedule-sync --scheduler prefect \
  --dags-dir dist/artifacts/schedule/ \
  --workspace team-x/prod

fluid schedule-sync --scheduler dagster \
  --dags-dir dist/artifacts/schedule/ \
  --workspace team-x/prod
```

### Dry-run (preview argv, no push)

```bash
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination s3://my-airflow-dags/team-x/ \
  --dry-run
```

### Signature-gated push (supply chain)

```bash
# Pair with `fluid bundle --sign --attest` in stage 1
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination s3://my-airflow-dags/team-x/ \
  --verify-signature
# Refuses to push if the source tgz bundle's cosign signature doesn't verify
```

## Notes

- Each scheduler's native CLI must be on `PATH`: `aws`, `gcloud`, `astro`, `prefect`, or `dagster-cloud`. `fluid doctor` verifies this.
- `--dry-run` short-circuits before subprocess invocation and emits the (redacted) planned argv. Nothing about the destination changes.
- Exit codes: `0` = pushed (or dry-run complete); `1` = push failure (subprocess exit non-zero); `2` = config error (missing `--dags-dir`, empty dir, bad scheduler choice).
- Path-B schedulers (EventBridge, Snowflake Tasks, MWAA-native) apply their schedules inside stage-7 apply via `SchedulePlanner`. Stage 11 is a no-op for those contracts.
