---
title: Upgrading
description: How to upgrade and pin data-product-forge, and the checklist for each step from 0.15.x to 0.18.1 — what changes, what to do, and how to check it.
---

# Upgrading

This page is the checklist for moving a project to a newer CLI. Each release's notes say why
something changed; this page says what you do about it, in order.

## Upgrade and pin the CLI

```bash
pip install --upgrade "data-product-forge[local]"
fluid version
```

```console
$ fluid version
╭─────────────────────────── 📦 Version Information ───────────────────────────╮
│ FLUID CLI                                                                    │
│ Version: 0.18.1                                                              │
│ API: v1                                                                      │
│                                                                              │
│ Supported Specifications:                                                    │
│ • FLUID 0.7.1, 0.7.2, 0.7.3, 0.7.4, 0.7.5, 0.7.6 (preview)                   │
│ • Default: 0.7.5                                                             │
│ • Latest (stable): 0.7.5                                                     │
╰──────────────────────────────────────────────────────────────────────────────╯
...
```

Install the extras your targets need: `local` (DuckDB and pandas), `aws`, `gcp`, `snowflake`.
Since `0.18.0` the `local` extra requires `duckdb>=1.5.0`, and the engine refuses an older
DuckDB.

**Pin an exact version in CI and production:**

```bash
pip install "data-product-forge[local]==0.18.1"
```

A range such as `>=0.16,<0.17` is not safe for CLI behaviour. Patch releases have changed
results on purpose: `0.16.3` moved relative outputs and made `verify --strict` fail where it
had passed. The SemVer promise covers the `fluid_build.api` Python package only (see
[API Stability](./advanced/api-stability.md)). Upgrade by changing the pin and working
through the checklist below.

**A generated pipeline pins its own version.** A Jenkinsfile written by
`fluid generate ci` installs the version that generated it, through its
`FLUID_PACKAGE_SPEC` parameter:

```console
$ fluid generate ci contract.fluid.yaml --system jenkins
...
  |- FLUID_PACKAGE_SPEC default: data-product-forge[local]==0.18.1
```

Upgrading the CLI on your machine does not upgrade that pipeline. Regenerate it, or set
`FLUID_PACKAGE_SPEC` when you start a build.

## Contracts do not need a new `fluidVersion`

Upgrading the CLI does not change the schema your contracts declare. `0.18.1` reads
`fluidVersion` `0.7.1` to `0.7.5`, and `0.7.6` as a preview (the list `fluid version`
prints). Some fields added in these releases exist only in `0.7.6`:
`lifecycle.expire`, `binding.encryption`, `binding.principals`,
`binding.governance.lakeFormation.bucketPolicy`, and `consumes[].upstreamWorkspace` /
`upstreamDigest`. Declare `fluidVersion: "0.7.6"` only when you use one of them.

## A safe order for any upgrade

1. Upgrade the CLI in a branch, and run `fluid version`.
2. Validate every contract, once per overlay you deploy:

   ```bash
   fluid validate contract.fluid.yaml --env aws
   ```

3. Preview each cloud apply without applying. A dry run runs the pre-plan checks this page
   refers to (state key, shared state, region, GCP grants), then plans:

   ```bash
   fluid apply contract.fluid.yaml --env aws --dry-run
   ```

   It ends with `dry-run: plan only — not applying.` and writes no state.
4. Regenerate committed pipelines, and review the diff:

   ```bash
   fluid generate ci contract.fluid.yaml --system jenkins
   ```

5. Work through the section for each version you cross, below.

## From 0.15.x to 0.16

Release notes: [`0.16.0`](./RELEASE_NOTES_0.16.0.md) (covers `0.15.1` to `0.16.2`).

| Change | What to do | How to check |
|---|---|---|
| Generated SQL scripts create views (`CREATE OR REPLACE VIEW`); on Snowflake and Databricks that drops grants on an existing view | Re-grant after the script runs, or rename an output that collides with an existing table | Each generated file's header says `-- Materialises: <name>  (CREATE OR REPLACE VIEW)` or `-- Not materialised: <reason>` |
| dbt multi-stage models are named after `stages[].outputs`, and `fluid_*` sentinel tests now fire | Update references to the old `stage_*` model names | Regenerate the dbt project and diff `models/` |
| The federation digest gate warns and applies | If CI must block on a drifted pin, fail on the log line | Search the apply log for `apply_consumes_drift` |
| The AWS region comes from the binding | Set `location.region` to where the resources are, or move them | The dry run refuses with `opentofu_region_moved`, naming both regions |
| Athena could not read Glue Parquet tables FLUID created before `0.16.2` | New tables declare the Hive input format and SerDe. Whether a re-apply updates an old table was not checked here: run `fluid apply --dry-run` and look for an in-place change to the table's storage descriptor | `SELECT COUNT(*)` in Athena does not fail with `HIVE_UNSUPPORTED_FORMAT` |
| `fluid import airbyte` needs a server | Pass `--server-url` or set `FLUID_IMPORT_AIRBYTE_URL` | The import refuses by name when neither is set |

The container image has no `0.16.0` tag; `0.16.1` is the first image after `0.15.3`.

## From 0.16 to 0.17

Release notes: [`0.17.0`](./RELEASE_NOTES_0.17.0.md) (covers `0.16.3` to `0.17.0`).

### Results that change on purpose

| Change | What to do | How to check |
|---|---|---|
| Relative local outputs land under the contract's directory (`0.16.3`) | Move readers of the old location | Run a local apply and look under the contract's directory |
| `fluid verify --strict` fails a local output whose columns differ from the schema (`0.16.3`) | Fix the schema or the build | Run `fluid verify --strict` before the upgrade lands in CI |
| `--build-id` with a mode that runs no build, and a plan applied in another mode, are refused (`0.16.3`) | Plan in the mode you apply | The apply fails before any build |
| The drift gate compares the live target (`0.16.3`), and reads the apply's OpenTofu state (`0.16.5`) | Use `--last-applied` to separate a contract change from drift | `fluid diff --exit-on-drift` exits non-zero on real drift |
| Command Center products are private unless the contract is classified `public` (`0.16.3`) | Classify public products as `public` | `fluid publish --dry-run` shows the body it would send |
| Lake Formation bucket policies omit same-account grantees (`0.16.3`) | Set `bucketPolicy: all-grantees` (fluid-schema `0.7.6`) only if you need the old output | The dry run's plan changes the bucket policy |
| A `consumes[]` entry the SQL reads must resolve (`0.16.5`) | Put the upstream under the same `fluid.workspace.yaml`, list its root in `FLUID_UPSTREAM_CONTRACTS`, or bind an explicit input of the same name | The build fails with `ConsumesResolutionError` naming the entry |
| A plan records its env (`0.16.5`) | Apply with the same `--env` you planned with | A different `--env` fails with `plan_env_mismatch` |
| A failed DuckDB S3 secret stops the run when `AWS_ENDPOINT_URL` is set (`0.16.5`) | Fix the endpoint or credentials | The run fails with `ObjectStoreEndpointError` |
| Masked columns land treated (`0.16.5`) | Set `FLUID_PII_HASH_SECRET` (16 bytes or more) for `hash`, the key variables for `tokenize` and `encrypt`, and declare treated columns as strings | An unset secret refuses the build; `fluid verify` fails a column that landed in cleartext |

The plan-env check, in practice:

```bash
fluid plan contract.fluid.yaml --env aws --out plan.json
fluid apply plan.json --env aws
```

### Retire the old Airflow DAGs

`0.17.0` puts the env into the DAG directory and id: `<product-id>__<env>/` with dag id
`<product>__<env>__<build>`, where `0.16.7` and earlier wrote `<product-id>/` with
`<product>__<build>`. The first sync after the upgrade must retire the old DAGs, or Airflow
runs both, and both apply the same product against the same state.

```bash
fluid schedule-sync --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination /opt/airflow/dags/ \
  --env prod --report sync-report.json
```

- With `--delete-scope product` (the default) and a local or `git+ssh` destination, the sync
  deletes, from `<product-id>/`, only the DAGs rendered for the same product and env under
  the old id. Other files stay.
- For any other destination (S3, GCS, MWAA, Composer, Astronomer and the rest) it cannot read
  the destination, so it prints a note instead:
  `[schedule-sync] note: <product>__<env>/ now holds <product>'s DAGs for env <env>. …`
  Delete the old DAG files for that env at the destination once.
- `--delete-scope destination` removes the old directory along with everything else the sync
  does not ship. Use it only for a destination this product owns alone.

**Check:** each entry of `superseded_scopes` in `sync-report.json` names the new `scope`, the
product it `replaces`, the `env`, and `old_dags_retired`. `false` means the deletion is still
yours to do.

### Remote state moves to a per-provider key

The default per-contract state key gains the provider:
`fluid/<id>/<provider>/terraform.tfstate` (for GCS, the prefix `fluid/<id>/<provider>`). This
applies to contracts that use a per-contract key: one with a `packaging` block, or any
contract whose backend comes from a bucket-only `FLUID_STATE_BACKEND`. An explicit key in
`--state-backend`, and the shared legacy key `fluid/terraform.tfstate`, do not move.

The first real apply copies the state with OpenTofu's own migration
(`tofu init -force-copy`), checks the copy, and prints:

```text
state move:  moved <n> resource(s) from <old> to <new> with `tofu init -migrate-state`; the old object is left in place
```

A dry run never moves state. While the move is pending, it plans against the old key and
prints ``state move:  read from <old>: `fluid apply` moves it to <new>``.

When the apply for one cloud finds the other cloud's state at the old key, it leaves it alone.
On a live run on 4 October 2026, the first `--env gcp` apply printed that the old key
`holds the aws provider's state (hashicorp/aws), not this provider's; left in place`, and
wrote the gcp state to `fluid/<id>/gcp/terraform.tfstate`.

**Two refusals to expect:**

- `state_shared_with_another_provider`: the key does not name the provider and already holds
  another cloud's resources, so this plan would destroy them. Give each provider its own key,
  for example `--state-backend s3://<bucket>/fluid/<id>/<provider>/terraform.tfstate`, or use
  a bucket-only `FLUID_STATE_BACKEND`.
- A state that mixes providers is not moved; the apply stops with an error naming both keys,
  so you decide.

The apply does not delete the old object. Once the apply for each provider has moved its
state, nothing reads the old key, and you can remove it.

### GCP dataset grants become member resources

Dataset grants are `google_bigquery_dataset_iam_member` resources, which add to a dataset's
access instead of replacing it. On the first apply to a dataset whose state holds the old
authoritative access list, the apply revokes, once, the entries no grant of the contract
covers, and prints them:

```text
dataset <dataset>: its access list was written by an older forge-cli; this apply revokes the entries no grant of the contract covers: <entries>
```

For that one apply the old list is still authoritative, so an entry added by hand since the
last apply is revoked too. Special groups, views and routines are kept.

**Check before applying:** `fluid diff` makes the same change, so its plan shows the
revocation, and the dry run prints the line above.

```bash
fluid diff contract.fluid.yaml --env gcp
```

If every entry of a dataset's list would be revoked, the apply is refused with
`opentofu_dataset_access_unreconciled`. Revoke those entries yourself (`bq update` or the
console), or keep one of them in the contract for this apply, then re-run.

### Overlays a workspace expects

`--env <name>` with no overlay is refused when the workspace's `fluid.workspace.yaml` lists
that env for the product under `expected-environments`. Before `0.17.0` the base contract
was used as if it were that env.

```yaml
# fluid.workspace.yaml
expected-environments:
  orders: [gcp]
```

The refusal is skipped for `dev` and for an env the base contract already binds to. The
CLI wraps the message at the terminal width; this was run at 80 columns:

```console
$ fluid validate orders/contract.fluid.yaml --env gcp
❌ Validation error: contract_load_failed
   error: --env 'gcp' has no overlay, but fluid.workspace.yaml expected-environments (orders)
declares 'gcp' an environment of this product, so the base contract (bound to local) would be used
as if it were 'gcp'. Add overlays/gcp.yaml, or remove 'gcp' from fluid.workspace.yaml
expected-environments (orders)
   [ERR_CONTRACT_LOAD_FAILED]
...
```

Without that workspace entry, the same command only warns (`overlay_not_found`) and uses
the base contract. A contract's own `environments` block warns but does not refuse.

### Also check

- **A GCP binding with no region is refused**, instead of landing in `US`.
- **Regenerate committed pipelines.** Stage 6 now runs `fluid plan --check-sovereignty`, and
  the DAG ids changed.
- **Command Center run reports.** If the publish configuration is set, each `fluid apply`
  reports its run to the Command Center. Set `FLUID_COMMAND_CENTER_ENABLED=false` to turn it
  off.

## From 0.17 to 0.18.1

Release notes: [`0.18.0` and `0.18.1`](./RELEASE_NOTES_0.18.0.md). That page has a "Do I need
to change anything?" table; the short version:

| Change | What to do | How to check |
|---|---|---|
| `$ref` is confined to the root contract's directory tree; URL, `file://` and absolute refs are refused | Widen with `FLUID_REF_ROOT` per command, or copy the fragment in | `fluid validate` fails with a message that the ref `escapes the ref root` |
| Contract SQL runs in DuckDB's sandbox: no URLs other than declared `s3://`, no `SET` or `PRAGMA` that change a setting, no autoloaded extensions | Allow a directory with `FLUID_DUCKDB_ALLOWED_DIRS`, land remote data first, remove `SET` / `PRAGMA` | Run each local build once: `fluid apply contract.fluid.yaml --mode amend-and-build --yes` |
| OpenAPI documents in a bundle may not `$ref` another file or URL | Inline the schemas under `components` | `fluid validate` on the bundle reports `OAS-REF-EXTERNAL` |
| The `local` extra needs `duckdb>=1.5.0` | `pip install -U "data-product-forge[local]"` | The engine refuses an older DuckDB by version |
| `fluid diff`'s live check resolves `{{ env.* }}` (`0.18.1`) | Upgrade to `0.18.1`; no contract change | Stage 5 (`fluid diff --exit-on-drift`) passes on a BigQuery binding whose project is an env placeholder |

Check a bundle the way CI builds it:

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
fluid validate runtime/bundle.tgz
```

Background: [Composing a contract with `$ref`](./concepts/contract-refs.md),
[DuckDB sandbox for contract SQL](./advanced/duckdb-sandbox.md),
[Contract loading API](./advanced/contract-loading-api.md) (new in `fluid_build.api` `1.1`).

## Older releases

Upgrading from before `0.15.0`? Start with the
[`0.15.0` checklist](./RELEASE_NOTES_0.15.0.md#upgrade-checklist), then continue from
[From 0.15.x to 0.16](#from-0-15-x-to-0-16). Step 11 there, about federation digests, now
warns instead of failing the apply.
