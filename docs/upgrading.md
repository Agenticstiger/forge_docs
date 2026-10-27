---
title: Upgrading
description: How to upgrade and pin data-product-forge, the checklist for each step from 0.15.x to 0.18.1, and what moving the local engine from DuckDB 1.x to 2.x changes — what breaks, what to do, and how to check it.
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
`upstreamDigest`. Declare `fluidVersion: "0.7.6"` only when you use one of them; the
[preview fields](./reference/preview-fields.md) page lists them, and
[Federated upstreams](./concepts/federation.md) covers the last two.

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

## Read this first if you consume the exported artifacts

::: warning New in `0.23.0`
Exported ODCS and ODPS documents change shape. Every change below corrects output that was
wrong, but the old values may be baked into whatever reads them, so this is the section to read
before you upgrade rather than after. The work is
[forge-cli #753](https://github.com/Agenticstiger/forge-cli/pull/753).

Nothing here changes a FLUID contract. If you do not consume `fluid generate standard`,
`fluid odcs export`, `fluid odps export` or `fluid generate artifacts` output, skip it.
:::

| Change | What to do | How to check |
|---|---|---|
| A Kafka column's ODCS `physicalType` is an Avro type name. **`bigint` now exports as `long`, where it exported `integer`** | Re-derive and re-register any Avro schema built from a forge ODCS export of a Kafka topic with a 64-bit column | Export the contract and read `physicalType` on that column |
| A **per-port** ODCS contract's `name` is the port's, not the product's; the product name moves to a `fluidProductName` custom property | Re-key anything that keys files, registry subjects or display names on the contract `name`; read the product from `fluidProductName` | Export a product with more than one expose: the two documents no longer share a `name` |
| ODPS `inputPorts[].contractId` is `<productId>.<exposeId>`, not the bare upstream product id | Point any resolver that looks an input port up by that id at the port-scoped form | Export a contract with a `consumes[]` entry and read `inputPorts[].contractId` |
| A Kafka server's ODCS `format` becomes a message format **once the contract declares `binding.serialization`** | Nothing, until you adopt that field | A contract without it exports the same bytes as before |
| Derived quality rules carry an `id`, and rules declared in `dq.rules` are exported as ODCS quality | Nothing. A DQ engine that labels results by rule id stops refusing the document | `quality[].id` is present on every rule the exporter mints |
| `fluid odps import` refuses to write a contract that does not validate, and its pass-through bucket moved from `metadata.odps_passthrough` to the root `extensions.odps` | Read the bucket at its new address. Pass `--lenient` if you need the old write-anyway behaviour | An import that used to print a success tick and write an invalid file now fails and writes nothing |
| **Breaking.** Two exposes resolving to one contract id fail `fluid validate` and every export | Give each expose its own `exposes[].contract.id`, or rename the expose whose id is derived | `fluid validate` names both exposes and the shared id |

### The Kafka `physicalType` change is the urgent one

This was silent data corruption, not a cosmetic fix. Kafka had no physical-type table, so
`fluid_to_physical` fell back to the ODCS *logicalType* — and ODCS's own schema defaults an
unqualified `integer` to `i32`. A tool deriving an Avro schema from the exported contract
therefore read 32 bits for a column a producer such as Flink `BIGINT` writes as 64. The
registered schema and the data disagreed, and nothing signalled it.

The physical type is now the Avro type name, from a table measured against the Avro 1.12
specification and against datacontract-cli's own ODCS→Avro exporter. The integer family is
split by width, because Avro has no 8- or 16-bit integer: `int`, `integer`, `int2`, `int4` and
`serial` are `int`, while `bigint`, `long`, `int8`, `int64`, `longint` and `bigserial` are
`long`. `decimal` carries its precision and scale in `customProperties`.

If you build Avro schemas from these exports, treat every 64-bit column as having been wrong
and re-register.

### The per-port ODCS name

A per-port export — `fluid generate standard --format odcs`, and the per-expose documents
`fluid generate artifacts` writes — used to name every document after the **product**, so a
product with two exposes published two contracts both called "Orders Product". The `id` was
already per-port; the `name` was not, so a tool that keys files, registry subjects or display
names on the name could not tell them apart.

The name is now the port's `title`, falling back to its `exposeId`, and the product's name is
in a `fluidProductName` custom property.

There is deliberately **no** special case for a single-port product: making the exported name
depend on how many siblings a port has would change that name the day a second port is added.
So a single-expose product's exported name changes too, whenever its port's title (or
`exposeId`) differs from the product's name. The ODCS `id` is unchanged in every case, and a
whole-contract export is untouched.

### Input ports, and the version constraint that used to be dropped

`inputPorts[].contractId` carried the bare upstream *product* id, which is not the id anything
publishes: an output port is published under `<productId>.<exposeId>`. It is now that
port-scoped form — or the upstream's own id when the contract names one in the new
`consumes[].contractId`.

A `consumes[].versionConstraint` was dropped outright, because ODCS's input-port object has no
field for it. It now rides in a `fluidVersionConstraint` custom property.

### The Kafka server `format`

A Kafka binding declares `format: kafka_topic`, which says nothing about whether the values on
the topic are Avro or JSON — the one thing a consumer has to know to read it at all. With the
new `binding.serialization.value`, the exported ODCS server `format` is the message format ODCS
means by that field: `avro`, `json`, `protobuf` or `xml`, with `avro-confluent` and
`json-confluent` collapsing onto the wire format they carry. Whether a schema registry is
involved is not lost — `binding.serialization` rides along verbatim in the `fluidExtras`
custom property, unless `ODCS_FLUID_EXTRAS=false` opts out of that blob.

**A contract that has not adopted the field exports exactly as before.** The exporter will not
guess a wire format from a contract that never stated one: `binding.format` passes through as
it always has, and where a contract sets neither, the pre-existing `json` default still
applies. So this changes a Kafka export only once the contract says what its messages are.

### Quality rules

Rules the exporter derives from `required`, the primary-key tag and `validationRules` now carry
an `id`. The ids are derived rather than counted, so two renders of one contract produce the
same ids and an export is not a spurious diff. That matters twice: a DQ engine that labels its
results by rule id refuses a whole contract whose rules have none, and DataHub's ODCS ingestion
seeds its assertion URNs from `quality.id`, so a stable id is what keeps an assertion's
identity across a rename or a reorder.

Rules an author declared in `dq.rules` used to be parked in the `fluidExtras` custom property
and nowhere else, so a consumer running the published contract's quality saw only the checks
forge had synthesised. They are now exported as ODCS quality for the four types ODCS can
express:

| `dq.rules` type | Exported as |
|---|---|
| `completeness` | library metric `nullValues`, dimension `completeness` |
| `uniqueness` | library metric `duplicateValues`, dimension `uniqueness` |
| `valid_values` | library metric `invalidValues`, dimension `conformity` |
| `freshness` | a `text` rule — ODCS has no library metric for it |

The other four — `accuracy`, `schema`, `anomaly_detection` and `drift_detection` — have no
executable ODCS form, so each is **logged by name with the reason** and still carried in
`fluidExtras`. Silence was the bug; a rule with no ODCS form is now reported rather than
dropped without a word.

### `fluid odps import`

The command's own help said it "always emits one validated FLUID contract" while never running
the validator, so importing its own export printed a success tick and wrote a file
`fluid validate` then rejected with ten errors. It now validates before writing:

```bash
fluid odps import product.odps.yaml -o contract.fluid.yaml
```

A document that does not produce a valid contract fails, names the problem and **writes
nothing**. `--lenient` writes it anyway — note that this widens a flag that already existed:
it used to mean only "downgrade output-port resolution failures to warnings", and it now also
means "write the contract even when it does not validate".

The pass-through bucket the importer writes for everything ODPS carries that FLUID has no field
for moved from `metadata.odps_passthrough` to the root `extensions.odps`. `metadata` is
`additionalProperties: false`, so the old address could never validate; root `extensions` is
the one object the FLUID schema declares open. Root `extensions` arrived in FLUID 0.7.3, so an
import whose source document records an older `fluidVersion` warns and declares the default
instead, because the older schema cannot hold the bucket.

### The breaking one: two ports under one contract id

A contract whose `exposes[].contract.id` collides with a sibling's **resolved** id — pinned or
derived — now fails `fluid validate` and every export door. The check compares the ids the
exporters will actually mint, so a pin equal to a sibling's derived `<productId>.<exposeId>`
is caught too:

```bash
fluid validate contract.fluid.yaml
```

The message names both exposes and the shared id, and the advice fits which side pinned it:
change the `contract.id` where one is pinned, rename the expose where the id is derived.

That export used to succeed. It wrote one per-port ODCS document for two output ports, so the
losing port's schema was absent from the bundle and both ports resolved to the survivor — and
`fluid generate artifacts` sealed it under a MANIFEST merkle root. The failure is the fix.

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

How state keys, backends and the commands that read state fit together is in
[OpenTofu state](./concepts/state.md); deploying one contract to two clouds is in
[One contract, two clouds](./recipes/one-contract-two-clouds.md).

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

The policy table for AWS and GCP, and what `fluid verify` checks on each, is in
[Governance parity](./concepts/governance-parity.md).

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
was used as if it were that env. See [Environments and overlays](./concepts/environments-and-overlays.md#when-no-overlay-matches)
and [Workspaces](./concepts/workspaces.md#expected-environments).

```yaml
# fluid.workspace.yaml
expected-environments:
  orders: [gcp]
```

The refusal is skipped for `dev` and for an env the base contract already binds to. The
CLI wraps the message at the terminal width; this was run at 100 columns:

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
  reports its run to the Command Center ([what it sends](./concepts/command-center.md#what-fluid-apply-reports)). Set `FLUID_COMMAND_CENTER_ENABLED=false` to turn it
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

## Changes in 0.20.0

These changes shipped in forge-cli `0.20.0`, after the `0.18.1` the sections above cover.
Each row names the pull request that made it.

| Change | What to do | How to check |
|---|---|---|
| `fluid apply` validates the contract against its schema on both engines and in every mode ([forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714)). A cloud apply (`aws`, `gcp`, `snowflake`, `confluent`) or a build mode skipped the check, so a contract `fluid validate` rejects could apply with exit 0. It now stops before planning with `apply_contract_invalid`, or `contract_version_unsupported` below `fluidVersion` 0.7 | Run `fluid validate <contract> --env <env>` for each overlay you apply, and fix what it reports. No flag skips the check | `fluid apply <contract> --env <env> --dry-run` stops before `tofu plan` with the event |
| A `plan.json` that embeds no contract is refused with `apply_plan_missing_contract` ([forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714)). It used to run its actions unchecked on the native engine | Re-run `fluid plan` and apply the new plan | The apply fails before anything runs |
| An `aws` contract with `orchestration.engine: airflow` and an `orchestration.schedule` fails `fluid apply` and `fluid generate iac` with `unsupported_binding`, kind `mwaa-environment-not-emitted` ([forge-cli #715](https://github.com/Agenticstiger/forge-cli/pull/715)). The apply reported success and created no MWAA environment | Set `orchestration.engine: none` to schedule through EventBridge Scheduler, or run the DAGs on an MWAA environment you own and drop `orchestration.schedule`. See [Scheduling on AWS](./providers/aws.md#scheduling-on-aws) | `fluid generate iac contract.fluid.yaml` refuses with the kind and writes no module |

A key the schema does not have is one way a contract fails the first row. With
`fluid apply --dry-run`, a GCP contract that still uses the deprecated `metadata.policies`
went on to `tofu plan` on forge-cli main before #714, and now stops:

```text
❌ apply_contract_invalid  [ERR_APPLY_CONTRACT_INVALID]
  command: apply
  error_count: 1
  errors: ["metadata: Additional properties are not allowed ('policies' was unexpected)"]
  message: Contract validation failed with 1 error(s); ``fluid apply`` will not proceed on a schema-invalid contract. Run ``fluid validate`` for the full report.
```

Background: [Contract validation](./cli/apply.md#contract-validation).

## DuckDB 1.x to 2.x

`0.22.0` raised the local engine's DuckDB range to `duckdb>=1.5.0` with no upper bound, so
`pip install -U "data-product-forge[local]"` can now resolve DuckDB 2.x. DuckDB 2.0 needs
Python 3.11, so a Python 3.10 install stays on 1.5.x and nothing below changes for it.

Nothing here asks you to upgrade DuckDB. Read it before you do, and before anything else in
your stack does it for you — `pip install -U` on a fresh environment, a rebuilt CI image, or
another tool in the same environment pulling DuckDB 2.x in.

```bash
python -c "import duckdb; print(duckdb.__version__)"
```

| Change | What to do | How to check |
|---|---|---|
| A DuckDB **database file** another 2.x tool wrote cannot be opened on 1.5. That covers dbt-duckdb, dlt, and forge-cli `0.21.0` or older running on DuckDB 2.0 | Convert it, or keep every reader of that file on 2.x. The conversion is below | `fluid apply` on 1.5.x fails to open the file |
| **Contract SQL runs on the DuckDB that is installed**, and 2.0 changed some SQL: `x -> x + 1` is an error, and integer `//` and `%` by zero raise instead of returning NULL | Write `lambda x: x + 1`; wrap a division that can divide by zero in `TRY(...)` | Run each local build once: `fluid apply contract.fluid.yaml --mode amend-and-build --yes` |
| A **DuckDB acquisition build now resolves a Postgres source's `connection.secretRef`** (`0.22.0`). It used to ignore it, and libpq's `PGPASSWORD` or `~/.pgpass` supplied the password | To keep using `PGPASSWORD`, remove the `secretRef`. An inline `password` still wins over it | The build fails, naming the reference, where the `secretRef` does not resolve on the host that runs `fluid apply` |
| An **incremental timestamp cursor** written on 1.5 and read on 2.0 could silently drop or duplicate rows | Nothing: no state file needs rewriting. Upgrade to the release below before you move an incremental build across DuckDB versions | A run that lands fewer rows than are due, at exit code 0, with the stream recorded `succeeded` |
| A pipeline **discovered on 1.5 failed `SchemaDriftError` on 2.0** on a false positive | Nothing, in the release below | `fluid apply` fails the drift gate after a DuckDB upgrade, with no contract edit and no new data |

A file forge-cli itself creates on 2.x — `fluid demo`'s `.fluid/db.duckdb`, the local
provider's session and `persist` databases, a Meltano acquisition's DuckDB destination — is
written in the format DuckDB 1.5 writes, which DuckDB 1.0 and later open. A column type that
needs a newer format, such as `VARIANT`, is refused in it on 2.x exactly as it is on 1.5. A
file that already exists keeps the format it has.

To convert a file that only opens on 2.x, run this on 2.x:

```sql
ATTACH 'old.duckdb' AS src (READ_ONLY);
ATTACH 'new.duckdb' AS dst (STORAGE_VERSION 'v1.0.0');
COPY FROM DATABASE src TO dst;
```

DuckDB's own [2.0 migration notes](https://duckdb.org/docs/2.0/operations_manual/migration.html)
cover the SQL changes in full.

### The two drift defects, and what fixes them

::: tip Fixed in `0.23.0`
Both fixes shipped in `0.23.0`, in
[forge-cli #749](https://github.com/Agenticstiger/forge-cli/pull/749).
:::

**An incremental cursor written on 1.5 and read on 2.0 silently dropped or duplicated rows.**
A cursor is stored as text and pasted into `WHERE <field> > '<text>'` as an untyped literal,
so DuckDB coerces it to the column's type — and the two versions disagree about that type.
`read_json_auto` over a timestamp carrying `Z` gives `TIMESTAMP` on 1.5 and
`TIMESTAMP WITH TIME ZONE` on 2.0, where a naive literal is read in the session time zone,
which is the host's. On a host at a non-zero UTC offset the `>` boundary therefore moved. An
end-to-end run that wrote its cursor on 1.5 and continued on 2.0 landed 5 of 6 rows and
advanced the cursor past the row it skipped — exit code 0, stream recorded `succeeded`. Both
versions satisfy `duckdb>=1.5.0`, so one install can write state another reads. CSV sources
were never affected: `read_csv_auto` already sniffed `TIMESTAMPTZ` on 1.5.

A timestamp cursor now compares **instants** (`epoch_us`), which no session time zone can
shift, and the stored text is normalised to a naive UTC instant.

- **No state file needs rewriting.** A cursor a shipped 2.0 install already wrote carries an
  explicit offset, and is normalised when it is read.
- The instant comparison is used only for a column whose type `epoch_us` accepts
  (`TIMESTAMP`, `TIMESTAMP WITH TIME ZONE`, `TIMESTAMPTZ`, `TIMESTAMP_S`, `TIMESTAMP_MS`,
  `TIMESTAMP_NS`, `TIMESTAMPTZ_NS`, `DATE`, `TIME`). Integer, date-as-integer and opaque
  string cursors keep the plain comparison, because `epoch_us` raises `BinderException` on
  them. The choice is made from the **column's** type, never from the cursor text's shape: a
  `VARCHAR` column of timestamp-looking strings yields a cursor indistinguishable from a real
  timestamp's.
- Pinning the session time zone to UTC would also have worked, and is deliberately not used.
  `TimeZone` is an ICU-backed setting, the [DuckDB sandbox](./advanced/duckdb-sandbox.md)
  forbids autoloading extensions, and where ICU is absent DuckDB does not recognise the option
  at all — so a pin would fail the connection in exactly the hardened environments the sandbox
  exists for.
- The accepted cost: wrapping the column in a function can stop the predicate being pushed
  into the Parquet or JSON reader, so a large source scans more than it would have.

**A pipeline discovered on 1.5 failed `SchemaDriftError` on 2.0.** The drift gate compared
type *names*, and 2.0 infers `HUGEINT` where 1.5 infers `DOUBLE` for the same integer literal,
and `TIMESTAMP WITH TIME ZONE` where 1.5 infers `TIMESTAMP` for the same JSON timestamp.
Upgrading DuckDB — no contract edit, no new data — broke a working pipeline on a false
positive: the inferrer drifted, the data did not. Those pairs are now treated as one physical
type under two names.

- The widening and narrowing classification is unchanged. The family check runs *after* it, so
  `type_widened` and `type_narrowed` still fire for every ordered numeric pair.
- `DOUBLE` and `HUGEINT` are **not** value-identical: for the same literal 1.5 landed a lossy
  17-significant-digit float where 2.0 lands the exact 128-bit integer. So the non-failing path
  says the physical type moved rather than passing silently, with a line that ends "the same
  physical type under two names ... The stored width does change, so a value's precision may
  differ between the two."

**`fluid init --discover` emitted contracts its own `fluid validate` rejected.** The emitter
wrote the source's type name straight through, so a discover on DuckDB 2.0 produced
`type: hugeint` and `type: '"null"'`, and `fluid validate` then exited 1 on the file the tool
had just written. Validating every name in DuckDB's own `duckdb_types()` against the bundled
schema showed **35 rejected names**, not the two reported: `uinteger` and `integer[]` were
rejected on 1.5 as well, so this was never only a 2.0 problem. Discovered types are now
canonicalised at the emitter, each rejected name mapping to the nearest one the schema accepts
and every already-valid name left untouched. An unsigned or 128-bit type maps to a width that
holds its range (`uinteger` → `bigint`, `hugeint` → `numeric`) rather than to the
similar-sounding name. A contract already emitted with an invalid type stays invalid — the fix
is at emit time — but such a contract already failed validation, so nothing working changes.

Background: [DuckDB sandbox for contract SQL](./advanced/duckdb-sandbox.md),
[Source-aligned acquisition](./advanced/source-aligned-acquisition.md).

## Older releases

Upgrading from before `0.15.0`? Start with the
[`0.15.0` checklist](./RELEASE_NOTES_0.15.0.md#upgrade-checklist), then continue from
[From 0.15.x to 0.16](#from-0-15-x-to-0-16). Step 11 there, about federation digests, now
warns instead of failing the apply.
