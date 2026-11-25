---
title: Upgrading
description: How to upgrade and pin data-product-forge, the checklist for each step from 0.15.x to 0.40.1, and what moving the local engine from DuckDB 1.x to 2.x changes, including what breaks, what to do, and how to check it.
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
│ Version: 0.40.1                                                              │
│ API: v1                                                                      │
│                                                                              │
│ Supported Specifications:                                                    │
│ • FLUID 0.7.1, 0.7.2, 0.7.3, 0.7.4, 0.7.5, 0.7.6, 0.7.7 (preview)            │
│ • Default: 0.7.6                                                             │
│ • Latest (stable): 0.7.6                                                     │
╰──────────────────────────────────────────────────────────────────────────────╯
...
```

Install the extras your targets need: `local` (DuckDB and pandas), `aws`, `gcp`, `snowflake` and
`databricks` (`fluid apply` on Databricks needs it for metric views and dbt job runs since
`0.30.0`). For AI forge, MCP and lineage (`litellm`, `mcp`, `lineage`, `standard`) see
[Changes in 0.28.0](#changes-in-0-28-0).
Since `0.18.0` the `local` extra requires `duckdb>=1.5.0`, and the engine refuses an older
DuckDB.

**Pin an exact version in CI and production:**

```bash
pip install "data-product-forge[local]==0.40.1"
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
  |- FLUID_PACKAGE_SPEC default: data-product-forge[local]==0.40.1
```

Upgrading the CLI on your machine does not upgrade that pipeline. Regenerate it, or set
`FLUID_PACKAGE_SPEC` when you start a build.

## Contracts do not need a new `fluidVersion`

Upgrading the CLI does not change the schema your contracts declare. `0.29.0` reads
`fluidVersion` `0.7.1` to `0.7.6`, and `0.7.7` as a preview (the list `fluid version`
prints). `0.7.6` is stable since `0.26.0`: it is the default, and the contracts forge-cli
writes declare it. A contract that declares `0.7.5` still validates as `0.7.5`.

Some fields exist only in `0.7.6`: `lifecycle.expire`, `binding.encryption`,
`binding.principals`, `binding.governance.lakeFormation.bucketPolicy`, and
`consumes[].upstreamWorkspace` / `upstreamDigest` among them; the
[0.7.6 field reference](./reference/contract-0.7.6.md) lists every field, and
[Federated upstreams](./concepts/federation.md) covers the last two. Before you move a
contract to `0.7.6`, give each entry of an overlay's `builds`, `exposes` and `consumes` an
`id` (see [Changes in 0.25.0 and 0.26.0](#changes-in-0-25-0-and-0-26-0)). To try what lands
next, declare `fluidVersion: "0.7.7"`.

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

5. Work through the section for each version you cross. The table below says which ones.

Find the row for the version you run now, and read it and every row after it, up to the version
you move to. The last two rows are topic sections that cut across versions: read them as well
when they apply.

| You run | Read |
|---|---|
| `0.15.x` | [From 0.15.x to 0.16](#from-0-15-x-to-0-16) |
| `0.16.x` | [From 0.16 to 0.17](#from-0-16-to-0-17) |
| `0.17.x` | [From 0.17 to 0.18.2](#from-0-17-to-0-18-2) |
| `0.18.x` | [Changes in 0.19.0](#changes-in-0-19-0). On `0.18.0` or `0.18.1`, also the `fluid diff` row of [From 0.17 to 0.18.2](#from-0-17-to-0-18-2) |
| `0.19.x` | [Changes in 0.20.0](#changes-in-0-20-0), which fixes six security advisories |
| `0.20.x` | [Changes in 0.21.0](#changes-in-0-21-0) |
| `0.21.x` | [Changes in 0.22.0](#changes-in-0-22-0) |
| `0.22.x` | [Changes in 0.23.0](#changes-in-0-23-0) |
| `0.23.x` | [Changes in 0.24.0](#changes-in-0-24-0) |
| `0.24.x`, `0.25.x` | [Changes in 0.25.0 and 0.26.0](#changes-in-0-25-0-and-0-26-0) |
| `0.26.x` | [Changes in 0.27.0](#changes-in-0-27-0) and [Extras in 0.27.0](#extras-in-0-27-0) |
| `0.27.x` | [Changes in 0.28.0](#changes-in-0-28-0) |
| `0.28.x` | [Changes in 0.29.0](#changes-in-0-29-0) |
| `0.29.x` | [Changes in 0.30.0](#changes-in-0-30-0) |
| `0.30.0` | [Changes in 0.30.1](#changes-in-0-30-1) and [Changes in 0.31.0](#changes-in-0-31-0) |
| `0.30.1` | [Changes in 0.31.0](#changes-in-0-31-0) |
| `0.31.x` | [Changes in 0.32.0](#changes-in-0-32-0) |
| `0.32.x` | [Changes in 0.33.0](#changes-in-0-33-0) |
| `0.33.x` | [Changes in 0.34.0](#changes-in-0-34-0) |
| `0.34.x` | [Changes in 0.35.0](#changes-in-0-35-0) |
| `0.35.x` | [Changes in 0.36.0](#changes-in-0-36-0) |
| `0.36.x` | [Changes in 0.37.0](#changes-in-0-37-0) |
| `0.37.x` | [Changes in 0.38.0](#changes-in-0-38-0) |
| `0.38.x` | [Changes in 0.39.0](#changes-in-0-39-0) |
| Anything before `0.24.0`, if you read forge's ODCS or ODPS output | [Read this first if you consume the exported artifacts](#read-this-first-if-you-consume-the-exported-artifacts) (`0.23.0` and `0.24.0`) |
| Anything before `0.23.0`, and any DuckDB upgrade | [DuckDB 1.x to 2.x](#duckdb-1-x-to-2-x) (`0.22.0` and `0.23.0`) |

## Read this first if you consume the exported artifacts

::: warning New in `0.23.0` and `0.24.0`
Exported ODCS and ODPS documents change shape. Every change below corrects output that was
wrong, but the old values may be baked into whatever reads them, so this is the section to read
before you upgrade rather than after. The work is
[forge-cli #753](https://github.com/Agenticstiger/forge-cli/pull/753) (`0.23.0`) and
[forge-cli #756](https://github.com/Agenticstiger/forge-cli/pull/756) (`0.24.0`).

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
| `0.24.0`: an ODPS export of a contract with `consumes[]` gains `outputPorts[].inputContracts`, and an input port's `version` may differ from `1.0.0` where the contract states a version range ([forge-cli #756](https://github.com/Agenticstiger/forge-cli/pull/756)) | Update a consumer that compares exported documents byte for byte, or one that expects `1.0.0` on every input port | Export a contract with a `consumes[]` entry that has a `versionConstraint`: the input port's `version` is the lowest version the range accepts, and `outputPorts[].inputContracts` lists the upstream |
| `0.24.0`: an ODCS `sql` quality rule derived from `exposes[].contract.quality[].expression` is a counting query (`SELECT COUNT(*) FROM ${table} WHERE (<expression>) IS NOT TRUE`) with `mustBe: 0`, not the bare expression with `mustBe: true`; its `description` changes with it ([forge-cli #756](https://github.com/Agenticstiger/forge-cli/pull/756)) | Update a DQ configuration or test that pins the old `query` string or the boolean `mustBe`. An expression already written as a `SELECT` or `WITH` query is unchanged | Export the contract and read `query` and `mustBe` on the rule |

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

## From 0.17 to 0.18.2

Release notes: [`0.18.0` to `0.18.2`](./RELEASE_NOTES_0.18.0.md). That page has a "Do I need
to change anything?" table; the short version:

| Change | What to do | How to check |
|---|---|---|
| `$ref` is confined to the root contract's directory tree; URL, `file://` and absolute refs are refused | Widen with `FLUID_REF_ROOT` per command, or copy the fragment in | `fluid validate` fails with a message that the ref `escapes the ref root` |
| Contract SQL runs in DuckDB's sandbox: no URLs other than declared `s3://`, no `SET` or `PRAGMA` that change a setting, no autoloaded extensions | Allow a directory with `FLUID_DUCKDB_ALLOWED_DIRS`, land remote data first, remove `SET` / `PRAGMA` | Run each local build once: `fluid apply contract.fluid.yaml --mode amend-and-build --yes` |
| OpenAPI documents in a bundle may not `$ref` another file or URL | Inline the schemas under `components` | `fluid validate` on the bundle reports `OAS-REF-EXTERNAL` |
| The `local` extra needs `duckdb>=1.5.0` | `pip install -U "data-product-forge[local]"` | The engine refuses an older DuckDB by version |
| `fluid diff` resolves `{{ env.* }}` in a binding. `0.18.1` fixed only the live check ([forge-cli #692](https://github.com/Agenticstiger/forge-cli/pull/692)): `fluid diff` still failed with `diff_failed` for every silver and gold whose gcp binding names its project through `{{ env.* }}`, until `0.18.2` ([forge-cli #696](https://github.com/Agenticstiger/forge-cli/pull/696)) | Upgrade to `0.18.2`, not `0.18.1`; no contract change | Stage 5 (`fluid diff --exit-on-drift`) passes on a silver or gold whose gcp binding names its project through an env placeholder |

Check a bundle the way CI builds it:

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
fluid validate runtime/bundle.tgz
```

Background: [Composing a contract with `$ref`](./concepts/contract-refs.md),
[DuckDB sandbox for contract SQL](./advanced/duckdb-sandbox.md),
[Contract loading API](./advanced/contract-loading-api.md) (new in `fluid_build.api` `1.1`).

## Changes in 0.19.0

`0.19.0` moves the AWS provider to terraform-provider-aws 6, and adds column masking and row
filters ([forge-cli #700](https://github.com/Agenticstiger/forge-cli/pull/700)). The first row can stop an AWS apply that worked before.

| Change | What to do | How to check |
|---|---|---|
| terraform-provider-aws is pinned to `~> 6.0`. Provider 6.23 and later read a bucket's tags through S3 Control, which needs `s3:ListTagsForResource` | Grant `s3:ListTagsForResource` to the identity that applies AWS products | Run `fluid apply contract.fluid.yaml --env aws --dry-run` as that identity on an already applied product: the plan shows no change. With the pin moved and nothing else, eleven applied AWS products planned no change on provider 6.67 |
| A full-refresh BigQuery load uses `WRITE_TRUNCATE_DATA`, where it used `WRITE_TRUNCATE` | Nothing. `WRITE_TRUNCATE` removed every row access policy of the table it wrote, so each build undid the row filters the apply had made. `WRITE_TRUNCATE_DATA` replaces the rows and keeps the table's policies, policy tags and partitioning. An emulator keeps `WRITE_TRUNCATE` | After a full-refresh build, the table still has its row access policies |

A contract that sets neither `columnRestrictions` with `access: mask` nor `policy.authz.rowFilters`
is not affected by the rest of the release. A contract that sets them is refused where its binding
cannot enforce them, with an `unsupported_binding` kind that names the fix:

- `column-mask-unenforceable`: an AWS binding masks a column and declares no
  `governance.lakeFormation.maskedViews` (`definer` and `validationConnection`). Lake Formation
  cannot mask, so a protected Glue view returns the masked columns. Declare the field, or deny the
  columns instead of masking them.
- `row-filter-unenforceable`: an AWS binding filters rows with no Lake Formation grant that lets the
  filtered principal read the table. Grant `SELECT`, or remove the filter.
- `row-filter-view`: a row filter on a BigQuery view. Row access policies attach to tables, so
  filter the table the view reads.

## Changes in 0.20.0

These changes shipped in forge-cli `0.20.0`, after the `0.19.0` the section above covers. It fixes
six security advisories: they come after the first table. Each row of the first table names the
pull request that made it.

| Change | What to do | How to check |
|---|---|---|
| `fluid apply` validates the contract against its schema on both engines and in every mode ([forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714)). A cloud apply (`aws`, `gcp`, `snowflake`, `confluent`) or a build mode skipped the check, so a contract `fluid validate` rejects could apply with exit 0. It now stops before planning with `apply_contract_invalid`, or `contract_version_unsupported` below `fluidVersion` 0.7 | Run `fluid validate <contract> --env <env>` for each overlay you apply, and fix what it reports. No flag skips the check | `fluid apply <contract> --env <env> --dry-run` stops before `tofu plan` with the event |
| A `plan.json` that embeds no contract is refused with `apply_plan_missing_contract` ([forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714)). It used to run its actions unchecked on the native engine | Re-run `fluid plan` and apply the new plan | The apply fails before anything runs |
| An `aws` contract with `orchestration.engine: airflow` or `mwaa` and an `orchestration.schedule` fails `fluid apply` and `fluid generate iac` with `unsupported_binding`, kind `mwaa-environment-not-emitted` ([forge-cli #715](https://github.com/Agenticstiger/forge-cli/pull/715)). The apply reported success and created no MWAA environment | Set `orchestration.engine: none` to schedule through EventBridge Scheduler, or run the DAGs on an MWAA environment you own and drop `orchestration.schedule`. See [Scheduling on AWS](./providers/aws.md#scheduling-on-aws) | `fluid generate iac contract.fluid.yaml` refuses with the kind and writes no module |
| An AWS Iceberg expose with a `location.catalog` other than `glue` (`rest`, `iceberg_rest`, `polaris`, `unity`, `nessie`, `lakekeeper`) holds a Glue database and table that earlier releases created for it. A Snowflake Iceberg expose with `catalog: lakekeeper`, `bigquery`, `iceberg-rest`, `hive`, `jdbc`, `hadoop` or `dynamodb` holds an EXTERNAL VOLUME `0.19.0` and earlier created. `fluid apply` stops before planning with `iceberg_catalog_move_blocked` ([forge-cli #707](https://github.com/Agenticstiger/forge-cli/pull/707)), where it planned to destroy them. Destroying a Glue database deletes every table in it | Run the `tofu state rm` commands the refusal prints, then apply again. The resources stay where they are | `fluid apply <contract> --env <env> --dry-run` stops with the event and prints the commands |
| A Kafka Connect or embedded Debezium build whose Iceberg sink config forge-cli derives is refused when its expose names no table namespace (`location.database`, or `location.dataset` on GCP). A Kafka Connect build is also refused when its expose names no `location.table` ([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710)). The derived config used to name the table `None.<table>`, or leave Debezium Server on its default namespace | Set the field on the expose. An override that sets `iceberg.tables` or `table-namespace` itself is not affected | The build is refused before it runs, with a message that the expose's binding names no table namespace, or no table |

A key the schema does not have is one way a contract fails the first row. With
`fluid apply --dry-run`, a GCP contract that still uses the deprecated `metadata.policies`
went on to `tofu plan` before `0.20.0`, and now stops:

```text
❌ apply_contract_invalid  [ERR_APPLY_CONTRACT_INVALID]
  command: apply
  error_count: 1
  errors: ["metadata: Additional properties are not allowed ('policies' was unexpected)"]
  message: Contract validation failed with 1 error(s); ``fluid apply`` will not proceed on a schema-invalid contract. Run ``fluid validate`` for the full report.
```

Background: [Contract validation](./cli/apply.md#contract-validation).

### Security advisories

`0.20.0` fixes six security advisories. Each changes what a project file, an MCP client or a proxy
may do, so a setup that relied on the old behaviour stops working until you move the setting. The
full upgrade notes are in the
[forge-cli CHANGELOG](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md).

| Change | What to do | How to check |
|---|---|---|
| **Project-config catalog endpoints are no longer trusted** ([GHSA-vw85-xrwh-3p3x](https://github.com/Agenticstiger/forge-cli/security/advisories/GHSA-vw85-xrwh-3p3x)). A catalog endpoint set by `.fluidrc.yaml`, `.fluidrc`, `fluid.config.yaml` or `.fluid/config.yaml` in the checkout (Command Center, Data Mesh Manager, DataHub, OpenMetadata) gets only a key that the same file carries. It no longer gets `FLUID_API_KEY`, `DMM_API_KEY` or any other key from the environment, `/etc/fluid` or `~/.fluid`. `${VAR}` placeholders in it are kept as written. The `fluid apply` Command Center report needs `https://` for every host that is not loopback or on `FLUID_COMMAND_CENTER_HOST_ALLOWLIST` | Set the endpoint yourself: `FLUID_CC_ENDPOINT`, `DMM_API_URL`, `DATAHUB_GMS_URL` or `OPENMETADATA_SERVER_URL`, the endpoint in `~/.fluid/config.yaml`, or `fluid publish --target <name>:<endpoint>`. Move `${VAR}` placeholders out of project configs, and quote credentials | `fluid publish` fails, or `fluid apply` prints `run not reported (...)`. The message names what was withheld, never its value |
| **A workspace root above the project no longer widens the DuckDB sandbox** ([GHSA-58px-v64p-6ppm](https://github.com/Agenticstiger/forge-cli/security/advisories/GHSA-58px-v64p-6ppm)). A `fluid.workspace.yaml` at `$HOME`, above it, in a home-holding directory (`/home`, `/Users`), in a temp directory, at `/`, or above the contract's repository (`.git`, `.hg`) is found but not granted to contract SQL | Move the workspace file into the directory that holds the products. For products cloned side by side, list their common directory in `FLUID_DUCKDB_ALLOWED_DIRS` and declare the file. Move a contract saved straight in `$HOME` or `/tmp` into a directory of its own | The build runs with the contract's own directory and logs `local_workspace_not_granted`, naming the directory and the fix |
| **A project `.env` can no longer set operator-only variables** (same advisory). `FLUID_COMMAND_CENTER_URL`, `DMM_API_URL`, `HTTPS_PROXY`, `FLUID_STATE_BACKEND`, `FLUID_DUCKDB_ALLOWED_DIRS`, `FLUID_SECRETS_FILE`, `PGHOSTADDR`, `PATH` and git transport variables are among them. If CI or your shell exports a credential while a committed `.env` names the matching endpoint (`OPENAI_BASE_URL`, `PGHOST`, `SNOWFLAKE_ACCOUNT`), that endpoint is ignored | Export the variable in the shell or the CI job, or put it in a `FLUID_SECRETS_FILE` you export. See [What a project's `.env` may set](./advanced/project-dotenv-trust.md) | `fluid` prints `Ignored ... from project dotenv files` and runs without the variable |
| **An MCP client can no longer use the host's cloud identity** ([GHSA-m7j5-jcrq-cmxm](https://github.com/Agenticstiger/forge-cli/security/advisories/GHSA-m7j5-jcrq-cmxm)). The source-catalog tools honour a client's `allow_metadata_service: true` only when the server runs with `--allow-metadata-service` (or `FLUID_ALLOW_METADATA_SERVICE=1`). A catalog read that relied on a bare `AWS_REGION`, `GOOGLE_CLOUD_PROJECT` or similar variable now needs the same opt-in, `fluid forge data-model from-source` included | Add `--allow-metadata-service` to the server's `args` in your MCP client config if you rely on instance-role, workload-identity or ADC auth. See [Credential resolver](./advanced/credential-resolver.md) | The tool call fails with an error that names the flag, or a catalog read fails with "No credentials resolved" |
| **Federation credentials need an operator allowlist** ([GHSA-m288-j7hc-rhrj](https://github.com/Agenticstiger/forge-cli/security/advisories/GHSA-m288-j7hc-rhrj)). A federated upstream whose `auth.secret_ref` attaches a credential is refused unless the operator lists it in `FLUID_FEDERATION_SECRET_REF_ALLOWLIST`, except `GITHUB_TOKEN` or `GH_TOKEN` sent to a GitHub host. An `http://` or `git://` endpoint that carries one is refused | Set `FLUID_FEDERATION_SECRET_REF_ALLOWLIST` (for example `CATALOG_TOKEN@catalog.acme.com`, and `GITHUB_TOKEN@<your host>` for GitHub Enterprise Server) in the shell, the CI environment or a `FLUID_SECRETS_FILE` outside the project, with hosts written without a port. Move the endpoint to `https://` (`ssh://` for git) | The upstream is reported as `unreachable`. The federation gate warns and does not stop `fluid apply` |
| **The MCP output port reads a client certificate only from a trusted proxy** ([GHSA-x4fj-f8p7-p9f3](https://github.com/Agenticstiger/forge-cli/security/advisories/GHSA-x4fj-f8p7-p9f3)). `X-Client-CN` and `X-Client-Fingerprint` are read only after `shared-token` or `jwt` auth, from a peer listed in `FLUID_MCP_TRUSTED_PROXIES`. `fluid mcp output-port serve` exits 2 over stdio for an expose whose row filter reads `${caller.client_cn}` or `${caller.client_fingerprint}`, and over HTTP without gateway auth | Set `FLUID_MCP_TRUSTED_PROXIES` to the proxy's address if you run behind an mTLS proxy: `127.0.0.1` for the shipped nginx and Caddy templates. List only the proxy, or the narrowest CIDR that covers its replicas. Serve such an expose over HTTP with gateway auth | Calls a certificate filter applies to fail with `RowFilterIdentityMissing`, and the WARNING names the address to add |
| **`fluid init --discover` keeps passwords out of contracts** ([GHSA-25mh-f2f4-9vxp](https://github.com/Agenticstiger/forge-cli/security/advisories/GHSA-25mh-f2f4-9vxp)). A contract from a Postgres or MySQL/MariaDB URI that holds a password carries `secretRef: env://PGPASSWORD` or `env://MYSQL_PWD`, not `password:`. A URL contract keeps no query string, fragment or `user:password@` part | Export `PGPASSWORD` or `MYSQL_PWD` before `fluid apply`. Add back by hand any query parameter the source needs that is not a credential. Against a remote host the `env://` reference also needs an allowlist since `0.23.0`: see [Changes in 0.23.0](#changes-in-0-23-0) | The contract has no `password:` line, and the closing line of `--discover` lists the URL parameters it dropped |

## Changes in 0.21.0

`0.21.0` caps how far a YAML file may expand, merges overlay lists by id from `fluidVersion`
`0.7.6`, and stops running Flink SQL as SQL of forge-cli's own.

| Change | What to do | How to check |
|---|---|---|
| The YAML guard refuses a file, FLUID contracts included, that nests more than 128 levels, or whose aliases add more than 100,000 nodes or 5,242,880 characters of text, or that grows more than 100-fold past 1,000 nodes ([forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725)). The 5 MiB size cap counts UTF-8 bytes. ODCS and ODPS files now go through the guard too, so `fluid odps import` and `validate`, `fluid odcs validate` and `import`, `fluid odps-bitol validate` and `fluid forge --seed-from` refuse a file over 5 MiB or with more than 50 aliases | Write the repeated blocks out instead of reusing them through anchors | The error names the sizes. A bundle directory whose ODPS document the guard refuses, or that does not parse, fails instead of importing as ODCS-only |
| A file the resolver probes for a port's `contractId` must declare that `contractId` as its `id` ([forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725)) | Make the port's `contractId` and the ODCS `id` agree | A strict import fails, or skips the port under `--lenient` (an input port is always skipped) |
| In a contract whose `fluidVersion` is `0.7.6` or later, an overlay patches `builds`, `exposes` and `consumes` by id, not by position ([forge-cli #732](https://github.com/Agenticstiger/forge-cli/pull/732)). An overlay entry with no id, or two naming the same id, fails the load where the base's entries carry unique ids | Give each overlay entry the id of the entry it patches. See [Changes in 0.25.0 and 0.26.0](#changes-in-0-25-0-and-0-26-0) for the rule, since `0.7.6` became stable in `0.26.0`. A `0.7.5` contract still merges by position | `fluid validate contract.fluid.yaml --env <env>` fails with `contract_load_failed` for an id-less entry. An entry whose id the base lacks is appended and logged as `overlay_entry_added` |
| A build with `properties.language: flink_sql` is no longer run as SQL ([forge-cli #731](https://github.com/Agenticstiger/forge-cli/pull/731)). `fluid apply --mode amend-and-build` ran its Flink SQL on DuckDB or refused it, and the local, AWS, GCP and Snowflake planners planned it as a DuckDB, Athena, BigQuery or Snowflake statement. It is now reported as run outside forge-cli, planned without SQL, and left out of generated schedules | Run the job on the platform that runs Flink. Declare `engine: flink` with `fluidVersion: "0.7.6"` to name the engine too | `fluid apply --mode amend-and-build` counts the build on its own summary line as run outside forge-cli |

## Changes in 0.22.0

`0.22.0` makes `--strict` fail on a retargeted overlay patch, changes the operators in generated
Airflow DAGs, and lets the local engine run on DuckDB 2.x. The DuckDB changes are in
[DuckDB 1.x to 2.x](#duckdb-1-x-to-2-x), which follows this section.

| Change | What to do | How to check |
|---|---|---|
| `fluid validate --env <env> --strict` (one contract or a whole workspace), `fluid contract-validation --env <env> --strict` and `fluid test --env <env> --strict` fail when an overlay patch lands on an entry that names another id (`overlay_patch_retargeted`), which an overlay merged by position can do ([forge-cli #734](https://github.com/Agenticstiger/forge-cli/pull/734)). `fluid validate <bundle>.tgz --strict` fails on one the bundle recorded ([forge-cli #735](https://github.com/Agenticstiger/forge-cli/pull/735)), and stage 2 of the generated pipelines runs `--strict` | Put the overlay's entries in the base's order, or set `fluidVersion: "0.7.6"` with a unique id on every base entry, so overlays patch by id. Rebuild a bundle made before `0.22.0`: it records no such warning and passes as before. `fluid contract-validation` and `fluid test` do not read the bundle's record, so run them on the contract file with `--env` | `fluid validate contract.fluid.yaml --env <env> --strict` fails. Without `--strict` the finding is a warning |
| Generated Airflow DAGs run Snowflake SQL through `SQLExecuteQueryOperator` with `conn_id`, because apache-airflow-providers-snowflake 6.0 removed `SnowflakeOperator`. A GCP `create_table` task uses `BigQueryCreateTableOperator` where the google provider has it (13 and later), and `BigQueryCreateEmptyTableOperator` before that ([forge-cli #736](https://github.com/Agenticstiger/forge-cli/pull/736)) | Regenerate each committed DAG: a DAG generated before does not load on providers-snowflake 6.0 | Generate the schedule again and diff the DAG: the operator names change |
| The new operators render more of their arguments as Jinja: `SQLExecuteQueryOperator` renders `conn_id` and `hook_params` (the warehouse and database), and `BigQueryCreateTableOperator` renders `table_resource` (the schema). A literal `{{`, `{%` or `{#` in a warehouse or database name, or in a schema field such as a description, now fails the task when it runs ([forge-cli #736](https://github.com/Agenticstiger/forge-cli/pull/736)) | Escape it as `{{ '{{' }}`, `{{ '{%' }}` or `{{ '{#' }}`, or wrap the value in `{% raw %}` ... `{% endraw %}` | The task fails at run time, not at generation |
| `fluid scaffold-composer` writes no DAG for a contract whose every build runs outside forge-cli (`engine: flink`, `properties.language: flink_sql`) or continuously and that declares no `orchestration.tasks`, where it used to write one. It takes the DAG's cron from the first build a scheduler starts ([forge-cli #737](https://github.com/Agenticstiger/forge-cli/pull/737)) | Delete a DAG it wrote for such a contract before, from `--out-dir` and from Cloud Composer if you deployed it. The command names the file when it finds it under the name it writes now | `fluid scaffold-composer` writes no file for such a contract |
| A product whose every build becomes `continuous` (or runs outside forge-cli) gets no `schedule/` artifacts, so pipeline stage 11 skips `fluid schedule-sync` ([forge-cli #734](https://github.com/Agenticstiger/forge-cli/pull/734)) | Remove by hand a DAG deployed for it earlier: it stays in the scheduler | `fluid generate schedule` writes no files for the contract |
| An environment overlay cannot turn a scheduled build `continuous` (`trigger.type: continuous`, a `0.7.6` preview): overlays cannot delete the base's `cron` or `schedule`, which a continuous trigger refuses ([forge-cli #734](https://github.com/Agenticstiger/forge-cli/pull/734)) | Declare the trigger in each environment's overlay instead of in the base | The schema error names the field and the trigger type that takes it |

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
| A **DuckDB acquisition build now resolves a Postgres source's `connection.secretRef`** (`0.22.0`). It used to ignore it, and libpq's `PGPASSWORD` or `~/.pgpass` supplied the password | In `0.22.0`, remove the `secretRef` to keep using `PGPASSWORD`. From `0.23.0` an acquisition build no longer sees `PGPASSWORD` from the environment (see [Changes in 0.23.0](#changes-in-0-23-0)): declare the credential on the connection. An inline `password` still wins over a `secretRef` | The build fails, naming the reference, where the `secretRef` does not resolve on the host that runs `fluid apply` |
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

## Changes in 0.23.0

`0.23.0` changes what forge exports, fixes three DuckDB 2.0 defects, and stops a contract from
choosing where an environment variable is sent.

| Change | What to do | How to check |
|---|---|---|
| Exported ODCS and ODPS documents change shape ([forge-cli #753](https://github.com/Agenticstiger/forge-cli/pull/753)) | Read [Read this first if you consume the exported artifacts](#read-this-first-if-you-consume-the-exported-artifacts) before you upgrade | See that section's table |
| Three DuckDB 2.0 defects are fixed: an incremental cursor written on 1.5 and read on 2.0 dropped or duplicated rows, a pipeline discovered on 1.5 failed `SchemaDriftError` on 2.0, and `fluid init --discover` wrote types `fluid validate` rejected ([forge-cli #749](https://github.com/Agenticstiger/forge-cli/pull/749)) | Upgrade to `0.23.0` before you move an incremental build across DuckDB versions. See [The two drift defects, and what fixes them](#the-two-drift-defects-and-what-fixes-them) | See that section |
| **A contract that uses `env://` in `connection.secretRef` against a remote host fails until the operator allows it** ([forge-cli #751](https://github.com/Agenticstiger/forge-cli/pull/751)). All six acquisition runners (airbyte, debezium, dlt, duckdb, kafka_connect, meltano) refuse to resolve the reference unless every destination the connection block carries is loopback | Set `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST` to the variable's own name: `PG_PASSWORD@db.example.com` for that host only, or `PG_PASSWORD` for any host. Write the host without a port. Set it in the shell, in CI or in a `FLUID_SECRETS_FILE` outside the project, not in a project `.env`, where it is ignored. `localhost`, `127.0.0.0/8` and `::1` need nothing. For a production credential, use `vault://`, `aws://`, `gcp://`, `azure://` or `file://`, which are not policed. See [Environment variables](./advanced/environment-variables.md) | The build fails before the secret is read, with a refusal that names the variable and the host, never the value |
| `fluid init --discover` against a remote host writes a contract with `env://` | Set the same allowlist before `fluid apply`. The discover hint does not print it yet: the refusal from `apply` does | `fluid apply` refuses the contract until the variable is allowlisted |
| An acquisition source no longer receives this host's ambient database credentials: `PGPASSWORD`, `PGPASSFILE`, `PGSERVICE`, `MYSQL_PWD` and ten more variables are hidden while a postgres or mysql source is attached ([forge-cli #750](https://github.com/Agenticstiger/forge-cli/pull/750)). A source whose declared connection carries its own credentials is unaffected | Put the credential on the connection (`secretRef` or an inline `password`) | A build that took its password from `PGPASSWORD` or `MYSQL_PWD` alone now fails to authenticate |

## Changes in 0.24.0

`0.24.0` fixes three more exports: lineage, versions and quality SQL ([forge-cli #756](https://github.com/Agenticstiger/forge-cli/pull/756)). Exported
documents change shape again, so read the `0.24.0` rows of
[Read this first if you consume the exported artifacts](#read-this-first-if-you-consume-the-exported-artifacts)
before you upgrade:

- An ODPS export of a contract with `consumes[]` gains `outputPorts[].inputContracts`, and an input
  port's `version` may differ from `1.0.0`.
- An ODCS `sql` quality rule becomes a counting query with `mustBe: 0`.

Nothing else in this release asks you to act. `consumes[].contractVersion` is new and optional
(`0.7.6`): the exact upstream version a product was built against, within `versionConstraint`. It
wins over the lowest version of the range as the version an exported input port claims.

## Changes in 0.25.0 and 0.26.0

`0.25.0` added [contract fragments](https://github.com/Agenticstiger/forge-cli/pull/760)
(`$ref`). `0.26.0` made schema `0.7.6` stable and added the [Databricks](./providers/databricks.md)
provider. Each item names the pull request that made the change; the
[forge-cli CHANGELOG](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md)
carries the full upgrade notes of both releases.

### 0.25.0

- **A `$ref` that 0.24.0 left in the contract now composes or fails**
  ([forge-cli #760](https://github.com/Agenticstiger/forge-cli/pull/760)). A ref with keys
  beside it, a same-file `#/` pointer, or a ref inside an overlay used to stay a literal key. It
  now resolves, and one that cannot be resolved fails every command, naming the file and the
  place. A contract that embeds a document with its own `$ref` keys (a JSON Schema or OpenAPI
  fragment inside `parameters` or an extension) now fails too: keep such a payload as a string.
- **Contracts that use the new forms need 0.25.0 or later.** Text refs, list-root fragments,
  keys beside a `$ref`, pointers, refs inside overlays and a workspace `ref_root` fail on
  0.24.0, or load differently there. Pin `data-product-forge>=0.25.0` wherever such contracts are
  validated or planned.
- **Overlays are held to the ref root, and `--env` names an environment.** An `overlays/`
  directory or overlay file that links outside the contract's tree is refused: widen the root
  with `ref_root` in `fluid.workspace.yaml`, or `FLUID_REF_ROOT`, to share one. `--env ../x` and
  `--env /abs/x` are refused by every command.
- **A root contract must be a regular file of at most 5 MiB**, and a composed contract nests at
  most 128 levels. A contract read through a pipe (`fluid validate <(git show HEAD:contract.fluid.yaml)`)
  is refused: write it to a file, or move its large parts into fragments.
- **`fluid split` keeps the root's text and comments** instead of re-dumping it, and writes no
  file through a symlink. The fragments are the same as before.
- **A contract whose orchestrator is on a public host fails until the operator allows it**
  ([forge-cli #758](https://github.com/Agenticstiger/forge-cli/pull/758)). Set
  `FLUID_ACQUISITION_DEPLOYMENT_HOST_ALLOWLIST` to the host or its parent domain, without a port,
  in the shell, in CI, or in a `FLUID_SECRETS_FILE` outside the project. A project `.env` cannot
  set it. Deployments on `localhost`, loopback or a private network need nothing.

### 0.26.0

- **Schema 0.7.6 is stable, and 0.7.7 is the preview**
  ([forge-cli #768](https://github.com/Agenticstiger/forge-cli/pull/768)). What forge-cli writes
  now declares `0.7.6`: the importers, `fluid product-new`, `fluid init --discover` and the
  `fluid forge --scaffold` templates. Running `fluid import` again over a contract it wrote changes
  its `fluidVersion` from `0.7.3` to `0.7.6`. A `0.7.6` contract merges an overlay's `builds`,
  `exposes` and `consumes` by id, so an overlay entry that names no id fails to load where the base
  list has more than one entry, or where another overlay entry names an id.
- **`fluid bundle` no longer writes `contract.bundled.fluid.yaml` on its own**
  ([forge-cli #763](https://github.com/Agenticstiger/forge-cli/pull/763)). Without `--out`, `yaml`
  and `json` go to stdout and a `tgz` to `<contract id>.fluid.bundle.tgz`. A script that read that
  file must pass `--out contract.bundled.fluid.yaml`. Delete a `contract.bundled.fluid.yaml` an
  earlier run left beside a contract: from `fluid ship` it is a tarball, from `fluid bundle` a
  copy that may be stale.
- **`fluid apply` checks every platform the contract declares**
  ([forge-cli #766](https://github.com/Agenticstiger/forge-cli/pull/766)). It stops with
  `apply_platform_unsupported` (exit 2) where a platform has no provider; `provider_unknown` now
  means a `--provider` value no provider has. A contract with an expose on such a platform beside
  the exposes that chose the provider used to apply with exit 0, and now stops: pass `--provider`
  to apply it as before. With the `local` provider, a later build declared for a platform no
  provider serves (`composer`, `kubernetes`, ...) now stops the run: declare it as the job it is,
  or drop the platform.
- **A contract can no longer name the host a dbt build's credential goes to**
  ([forge-cli #773](https://github.com/Agenticstiger/forge-cli/pull/773)). A dbt build on
  Databricks, Redshift or Postgres that sets `builds[].execution.runtime.resources.host` now fails
  before dbt starts, with `DbtProfileError` naming the field. Remove it and set `DATABRICKS_HOST`,
  `REDSHIFT_HOST` or `PGHOST`. A Databricks catalog or schema must be a plain identifier, or come
  from a variable whose name ends in `_CATALOG` or `_SCHEMA`; or leave the field out and set
  `DATABRICKS_CATALOG` / `DATABRICKS_SCHEMA`.
- **A dbt build with no `execution.runtime.platform` takes its platform from the first expose's
  binding**, for the generated `profiles.yml` and the model-contract column types. It used to get a
  DuckDB profile whatever the binding said.
- **A dbt build on Databricks runs in the workspace**
  ([forge-cli #774](https://github.com/Agenticstiger/forge-cli/pull/774)). With
  `execution.runtime.platform: databricks`, `fluid apply` provisions it as a job through OpenTofu,
  and `--mode amend-and-build` no longer runs dbt on this machine. See
  [Databricks](./providers/databricks.md).
- **`fluid auth logout databricks` removes only the profile you name**
  ([forge-cli #772](https://github.com/Agenticstiger/forge-cli/pull/772)):
  `fluid auth logout databricks <profile>`. It never deletes `~/.databrickscfg`. With no profile
  named, it leaves the file alone, lists the profiles and exits 1.
- **ODCS and ODPS round trips:** an ODCS export records `fluidVersion` in `fluidExtras`
  whatever the version, and `fluid odcs import` / `fluid odps import` of a document that records
  no version declare `0.7.6`. Re-importing such a document writes a different file.

## Changes in 0.27.0

These changes shipped in 0.27.0. Most fail closed where a contract used to apply without them, so read them before upgrading from 0.26.0 or earlier. The Databricks ones come first; see [Databricks](./providers/databricks.md). The OpenTofu, AWS and GCP ones follow, then `fluid diff --baseline`.

- **A Databricks contract with a `sovereignty` block and no `binding.location.region` is now a finding**
  ([forge-cli #778](https://github.com/Agenticstiger/forge-cli/pull/778)): an error under
  `enforcementMode: strict`, a warning under `advisory`. `fluid apply` and `fluid generate iac` now
  hold the policy, and refuse a forbidden placement with `SovereigntyViolationError`. Set
  `binding.location.region` to the region of the workspace `DATABRICKS_HOST` names. It was refused as
  a field the module would drop; it is read now. Write it as a plain lower-case name
  (`databricks-region-invalid` otherwise), and declare one region per contract
  (`databricks-region-conflict`). `tofu plan` fails when the workspace's metastore is in another
  region.
- **A contract's labels become Unity Catalog tags**
  ([#779](https://github.com/Agenticstiger/forge-cli/pull/779)). They were dropped silently. A key's
  `-` becomes `_`. A contract whose labels collide once `-` is read as `_`
  (`databricks-tag-collision`), or that puts more than 50 tags on one schema or table
  (`databricks-tags-too-many`), is now refused. `fluid verify` checks the tags.
- **`fluid publish` sends `metadata.workspace_host`** for a Databricks product
  ([#780](https://github.com/Agenticstiger/forge-cli/pull/780)), from `DATABRICKS_HOST`. Nothing to do.
- **Column restrictions and row filters are accepted on Databricks**
  ([#785](https://github.com/Agenticstiger/forge-cli/pull/785)). `policy.authz.columnRestrictions`
  and `rowFilters` were refused (`databricks-governance-unmapped`). `fluid apply` now binds them on
  the table in Unity Catalog, after creating `fluid_`-prefixed SQL functions, and needs the
  `[databricks]` extra and `DATABRICKS_WAREHOUSE_ID` to do it. A denied column reads `NULL`. New
  refusals: `access: allow`, a text mask on a non-string column, a principal with no `group:`,
  `user:` or `serviceAccount:` prefix, and a predicate outside the allowlist. `fluid generate iac`
  now refuses such a contract (`databricks-enforcement-outside-module`): use `fluid apply`. A dbt job
  that writes a table not yet protected is created paused, and the next `fluid apply` unpauses it.
- **Databricks retention, bronze landing and scoped grants**
  ([forge-cli #801](https://github.com/Agenticstiger/forge-cli/pull/801), since 0.27.0). `lifecycle.expire` was
  refused (`databricks-retention-unmapped`). It is accepted now for a table rebuilt in full on every
  run, when `lifecycle.retention` covers the Delta history (30 days by default); `fluid verify` checks
  it. A DuckDB acquisition that writes a Databricks expose now uploads Parquet to the volume
  `DATABRICKS_STAGING_VOLUME` names and loads the table, where it wrote a local file; it needs
  `DATABRICKS_WAREHOUSE_ID` too, and refuses a source mode other than `full_refresh`
  (`databricks-landing-unsupported`). `policy.privacy.masking` is accepted for such an expose.
  An `accessPolicy` grant with `resources` was refused whatever it named
  (`databricks-grant-scope-unmapped`). The three shapes forge-cli can evaluate are placed now, only on
  the tables they name; any other path is still refused. A superseded `fluid_` function is dropped after a successful apply.
  See [Retention](./providers/databricks.md#retention) and
  [Landing a DuckDB acquisition](./providers/databricks.md#landing-a-duckdb-acquisition).
- **S3 state is locked** ([forge-cli #787](https://github.com/Agenticstiger/forge-cli/pull/787)),
  when the installed OpenTofu is 1.10 or newer. Before you upgrade, give every role that runs
  `fluid apply` (a `--dry-run` included), `fluid diff` or `fluid verify --state-drift` against S3
  state `s3:GetObject`, `s3:PutObject` and `s3:DeleteObject` on `<key>.tflock`, or set
  `FLUID_TOFU_S3_LOCKFILE=0` in the job's environment (a project `.env` cannot set it). A plan-only
  CI role fails without one of the two. A run killed
  hard can leave the lock behind: `tofu force-unlock <ID>` in the contract's workdir clears it. An
  older OpenTofu logs `s3_state_unlocked` and keeps working, unlocked. See [Locking](./concepts/state.md#locking).
- **A column type Glue or BigQuery cannot hold is refused**
  ([#793](https://github.com/Agenticstiger/forge-cli/pull/793)). A column typed `array`, `struct`,
  `map`, `object`, `record` or `row` fails `fluid validate`, `fluid generate iac` and `fluid apply`
  with `column-type`; declare it `json` or `string`, or, on AWS with a 0.7.7 contract, declare the column's `fields`, `element`, or `key` and `value` (see [Nested columns](./providers/aws.md#nested-columns)). On Glue, `geography`, `geometry`, `geom`,
  `point`, `hll`, a decimal Hive rejects and `bit(n)` over one bit are refused too. Some types are
  still written with a fallback and now warn, so `fluid validate --strict` fails until you declare
  the type you mean: on Glue `json`, `jsonb`, `variant`, `super`, `time`, `interval` and
  `bignumeric` (written as `string`), on BigQuery `geometry`, `geom` and a decimal wider than a
  `NUMERIC` holds. The first apply on a Glue table an earlier release created changes the types of columns
  that were `string` (`smallint`, `timestamptz` and the rest now get their Hive type), and
  `fluid apply` refuses until `--allow-data-loss`: Parquet written under the old schema may stop
  reading until it is rewritten, and reverting the column type restores reads. Until that apply,
  `fluid verify` and `fluid diff` report the mismatch. See [AWS column types](./providers/aws.md#column-types)
  and [BigQuery column types](./providers/gcp.md#exact-warned-and-refused-types).
- **An AWS schedule is no longer dropped silently**
  ([#794](https://github.com/Agenticstiger/forge-cli/pull/794)). A dotted or long contract id gets a
  valid name, with a hash when it had to change. Any AWS plan the plan validator refuses now fails
  `fluid generate iac` and `fluid apply` even for a contract with no schedule, where it used to emit
  the module and exit `0`; `fluid plan` already refused these, so run it before you upgrade. A plan
  that emits the scheduled Lambda warns `schedule_placeholder_lambda`: the function only logs its
  tasks, and the roles `fluid-workflow-execution` and `EventBridgeSchedulerRole` must already exist.
  See [Schedule names and refusals](./providers/aws.md#schedule-names-and-refusals).
- **A build mode refuses an id the build phase cannot use, before anything is applied**
  ([#803](https://github.com/Agenticstiger/forge-cli/pull/803)). `fluid apply --mode
  amend-and-build` and `replace-and-build` check `id` and every `builds[].id` before the apply
  hooks, `tofu` and any build. Each id must start with a letter or `_`, use only letters, digits,
  `_`, `.` and `-`, and be at most 128 characters. Such an id (`1orders`, or a longer one) passes
  `fluid validate`. On the OpenTofu engine the product used to be provisioned and the run then
  stopped with "Unexpected error". Now the run stops first with `apply_build_identifier_invalid`.
  Rename the id. A renamed `id` gets a new `.fluid/iac/<provider>/<id>` workdir, and its builds
  start without their cursors and watermarks. See [Build ids](./cli/apply.md#build-ids).
- **A build mode refuses a `--build-id` that names no build, before anything is applied**
  ([#808](https://github.com/Agenticstiger/forge-cli/pull/808)). `fluid apply --mode
  amend-and-build --build-id <id>` (and `replace-and-build`) checks the id against the
  contract's `builds[].id` before the apply hooks, `tofu` and any build. Ids match exactly,
  case and spaces included. On the OpenTofu engine a mistyped id used to provision the
  product, and the run then stopped with `Build not found`. Now it stops first with
  `apply_build_id_not_found`, which lists the contract's build ids. The exit code is still
  `1`. A Command Center run records the event `apply_build_id_not_found` where it recorded
  `build_not_found:<id>`. See [Build ids](./cli/apply.md#build-ids).
- **`fluid validate` and `fluid plan` warn about an id the build phase refuses**
  ([#813](https://github.com/Agenticstiger/forge-cli/pull/813)). For a contract with
  `builds`, an `id` or `builds[].id` that starts with a digit or is longer than 128 characters is
  a validate warning, so `fluid validate --strict` fails on it. `fluid plan` prints it and still
  writes the plan. Rename the id: `fluid apply` in a build mode refuses it anyway. See
  [An id the build phase refuses](./cli/validate.md#an-id-the-build-phase-refuses).
- **`fluid doctor --strict` and a readable failed apply**
  ([#786](https://github.com/Agenticstiger/forge-cli/pull/786)). `fluid doctor --strict` exits `1`
  when the summary says "Action needed", copilot readiness included; the default exit code does not
  change. A failed OpenTofu apply names the first error, its resource and the provider's detail,
  where it used to print the raw tail of `tofu`'s `-json` stream; a script that matched that text
  needs the new one. See [`fluid doctor`](./cli/doctor.md#strict) and
  [A failed OpenTofu apply](./cli/apply.md#a-failed-opentofu-apply).
- **`fluid diff --baseline` compares a 0.7.x contract's columns**
  ([forge-cli #789](https://github.com/Agenticstiger/forge-cli/pull/789)). It read only `exposes[].schema`, so a removed column, a type
  change that is not a widening and an added `required: true` column passed
  `--fail-on-breaking`. A pipeline that runs it can start exiting 1. See
  [Contract version diff](./cli/diff.md#contract-version-diff).
- **`fluid diff --baseline` refuses a contract its schema does not accept**
  ([forge-cli #805](https://github.com/Agenticstiger/forge-cli/pull/805)): exit 2, `diff_contract_invalid`. Run `fluid validate` on
  both files first. A pre-0.7 baseline is refused too. It also reports more breaking changes
  in a 0.7.x contract: a quality rule whose severity becomes `error` or `critical`, and a key
  column (a `primary-key` tag, `semanticType: identifier`, ...) that stops being `required`.
  A `sensitivity` change is an info
  finding. A bot that parses `--format markdown` now finds the path and the description each
  in a code span. See [Both contracts must be valid](./cli/diff.md#both-contracts-must-be-valid).
- **A provider plugin that replaces a built-in provider now needs the operator's grant**
  ([forge-cli #812](https://github.com/Agenticstiger/forge-cli/pull/812)). A `fluid_build.providers`
  entry point that claims `aws`, `gcp`, `snowflake`, `databricks` or `local` is skipped without
  being imported unless `FLUID_PLUGINS_ALLOWLIST` grants it, for example `acme-fluid-gcp:gcp`.
  `fluid providers` now lists providers without importing them, and `azure` is no longer accepted
  as a provider name anywhere.
- **An IaC plugin that replaces a built-in platform now needs the operator's grant**
  ([forge-cli #807](https://github.com/Agenticstiger/forge-cli/pull/807)). A package on the
  `fluid_build.iac_providers` entry point is imported only when a contract's `binding.platform` needs
  it. An entry point that claims `aws`, `gcp`, `snowflake`, `confluent`, `databricks`, an alias such as
  `glue` or `bigquery`, or `local` is skipped without being imported, with a WARNING. To keep an
  override you rely on, add a distribution-qualified entry to `FLUID_PLUGINS_ALLOWLIST`, for example
  `acme-fluid-aws:aws`; it restricts no other plugin. `redshift` and `datamesh-manager` can never be
  granted, and two distributions that ship the same platform name are both refused. Allow and block
  names now match case-insensitively with `-` equal to `_`. The global `--provider` flag accepts
  built-in providers only; a plugin platform is reached through `binding.platform`. See
  [Shipping an IaC plugin](./sdk-and-plugins/reference/entry-points.md#shipping-an-iac-plugin).
- **Redirects and CA bundles**
  ([forge-cli #804](https://github.com/Agenticstiger/forge-cli/pull/804)). The Data Mesh Manager
  client refuses a redirect to another origin instead of forwarding its API key; the error names the
  new origin and says to update `DMM_API_URL`. A `REQUESTS_CA_BUNDLE` or `CURL_CA_BUNDLE` that names a
  path that cannot be loaded switches the Command Center reporter off for the run with a warning;
  TLS is never relaxed. See [`fluid datamesh-manager`](./cli/datamesh-manager.md#configuration) and
  [Command Center reporting](./cli/apply.md).
- **`redshift` and `datamesh-manager` are no longer providers.** `--provider` or `FLUID_PROVIDER` naming
  either one now exits 2. For `redshift` the message points to `--provider aws`; for Data Mesh Manager,
  to `fluid publish --target datamesh-manager`. A contract's `runtime.platform: redshift` is served by
  `aws`, so it needs no change. A plugin cannot claim either name. See
  [Retired provider names](./cli/providers.md#retired-provider-names).
- **A Kafka Connect or embedded Debezium Iceberg sink's `catalogAuth` needs the operator's say**
  ([forge-cli #818](https://github.com/Agenticstiger/forge-cli/pull/818)). A sink whose
  `catalogAuth` reaches a non-loopback host fails its run until the operator pairs the variable with
  the host as `NAME@host` in `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST` and, for a hostname, lists it
  in `FLUID_ACQUISITION_DEPLOYMENT_HOST_ALLOWLIST`. A catalog or token endpoint on `http://`, a
  loopback host included, fails `fluid validate`; move it to `https://`. `fluid validate` warns, with
  the `export` line the run needs, when only an entry is missing. A derived sink whose
  `binding.location` holds text that starts with `env:`, or holds `${` or a control character, or a
  `region` that is not one label, now fails `fluid validate` and the run, `catalogAuth` or not;
  write the value itself. See [Operator allowlists](./advanced/source-aligned-acquisition.md#operator-allowlists).
- **A value that ends in a line break is refused**
  ([forge-cli #797](https://github.com/Agenticstiger/forge-cli/pull/797),
  [#799](https://github.com/Agenticstiger/forge-cli/pull/799),
  [#811](https://github.com/Agenticstiger/forge-cli/pull/811)). Whole-string validators and
  schema `pattern`s no longer let a trailing newline through, which an `id: |` block scalar, a
  `.env` value or a `%0A` in a URL produces. `fluid validate` refuses `id: "orders\n"` under every
  bundled schema version, with the hint `(it ends in a line break, which a YAML | or > block keeps
  and |- or >- drops)`; write the value with `|-` or `>-`, or plainly. Strip the value where an
  environment variable or file sets it. An AWS binding region with whitespace around it is refused
  (`aws-region-whitespace`). See [A value that ends in a line break](./cli/validate.md#a-value-that-ends-in-a-line-break).
- **Cloud-metadata addresses are refused even when listed**
  ([forge-cli #823](https://github.com/Agenticstiger/forge-cli/pull/823)). The acquisition
  orchestrator guard (kafka_connect, debezium, airbyte) and the OpenLineage emitter now refuse
  `fd00:ec2::254`, `fd00:ec2::23`, `fd20:ce::254`, `fd00:c1::a9fe:a9fe` and `100.100.100.200`, and
  any IPv4-mapped or NAT64 address that carries a link-local or metadata address, where they allowed
  them like any private host. A Tailscale tailnet or an IPv6 cluster on ULA addresses needs no
  change. See [Network safety](./advanced/network-safety.md).
- **The orchestrator guard judges the address the connection is pinned to**
  ([forge-cli #814](https://github.com/Agenticstiger/forge-cli/pull/814)). For kafka_connect,
  debezium and airbyte, the check on a contract-named `deployment.server_url` no longer resolves the
  hostname a second time. The name still decides the allowlist and the pinned address decides public
  or private; a link-local address is refused even for a listed name, and the refusal names both, as
  in `host 'connect.example.com', connecting to '93.184.216.34', is public`. A URL it cannot parse is
  refused with "it has no host".

## Extras in 0.27.0

*(since 0.27.0)* Four extras were added next to the base install, so you could switch before 0.28.0 took their packages out of it. [Changes in 0.28.0](#changes-in-0-28-0) says what that change does.

| Extra | Installs | For |
| --- | --- | --- |
| `litellm`, alias `ai` | `litellm` | The AI backend of `fluid forge`, `fluid forge data-model` with an API-key provider (`--llm-provider openai|anthropic|gemini|ollama`), `fluid ai setup` and the copilot |
| `mcp` | `mcp` | The MCP server SDK: `fluid mcp serve`, MCP output ports, `fluid scaffold-ide` and the keyless `mcp-sampling` provider |
| `lineage` | `openlineage-python` | Lineage events when `OPENLINEAGE_URL` is set |
| `standard` | `litellm` and `mcp` | The AI and MCP behaviour a base install had through 0.27.0 |

The extras that already existed are `all`, `aws`, `catalogs`, `copilot`, `databricks`, `datahub`, `dev`, `docs`, `gcp`, `local`, `odcs-strict`, `odps`, `opds`, `postgres`, `sdk`, `snowflake`, `test-emulators`, `test-emulators-heavy`, `tui`, `vector` and `viz`. Since 0.28.0 `viz`, `tui` and `odps` are empty aliases: nothing imports `graphviz`, `textual` or `ruamel.yaml`, and `pip install 'data-product-forge[viz]'` still works.

*(since 0.27.0)* When an optional package is missing, the CLI prints a message naming the feature, the package and the extra, then exits 1 with no traceback; see [Production troubleshooting](./advanced/production-troubleshooting.md#an-optional-package-is-not-installed). `fluid doctor` reads the litellm version from package metadata instead of importing it.

## Changes in 0.28.0

These changes shipped in 0.28.0. The first is a breaking change to the install, not to any contract or command: read it before you move a pipeline, a Docker image or a CI install line. After it come the pins that changed with it, the dependency list, the Debezium `.env` names, the Iceberg `catalogAuth` checks, Databricks and the smaller changes.

### The base install

*(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* litellm, mcp and openlineage-python are no longer in the base install; with litellm went boto3, aiohttp, openai, tokenizers and about fifty more packages. Counted with `uv pip compile` for a base install with no extras, the number of packages goes from 88 to 41 (Linux, Python 3.12), from 86 to 45 (Linux, Python 3.10) and from 89 to 40 (Windows, Python 3.12); litellm alone was 30 of them. `packaging` is now a declared base dependency, since it used to arrive through litellm.

The base install keeps the core pipeline: `validate`, `plan`, `apply`, `verify`, `publish`, `generate iac`, `bundle`, `diff`, `doctor`, and template or blank `forge`. If that is all you run, you need nothing.

If you use AI forge, MCP or lineage, name the extra. These install lines also work on 0.27.0, where they change nothing.

```bash
pip install "data-product-forge[litellm]"   # AI forge; [ai] is the same extra
pip install "data-product-forge[mcp]"
pip install "data-product-forge[lineage]"
pip install "data-product-forge[standard]"  # litellm and mcp: the pre-0.28.0 AI and MCP behaviour
```

| You run | You need |
| --- | --- |
| `fluid forge` with an API-key provider (`--llm-provider openai`, `anthropic`, `gemini`, `ollama`), `fluid forge data-model` with an API-key provider (`--llm-provider openai|anthropic|gemini|ollama`), the `fluid ai setup` provider wizard (not `--clear` or `--source`), the `fluid init` hand-off to AI, `--agent-loop` | `litellm` (alias `ai`) |
| `fluid mcp serve`, `fluid mcp output-port serve`, `fluid scaffold-ide` | `mcp` |
| `OPENLINEAGE_URL` set on `fluid apply` through the OpenTofu engine, or on an acquisition build | `lineage` |
| A native AWS plan that must resolve the account id (a contract that declares orchestration), live AWS reads, the Glue catalog import blocks of `apply` | `aws` |
| `litellm` and `mcp` together, the AI and MCP packages a 0.27.0 base install had | `standard` |

`[dev]` and `[all]` include all three. The Docker image profiles already install `[standard]` and `[lineage]`.

**The CLI stops before it does any work.** An explicit `--llm-provider` naming an API-key provider (`fluid forge`, `fluid forge data-model`, `--agent-loop`), the `fluid ai setup` wizard and the MCP commands (`mcp serve`, `mcp output-port serve`, `scaffold-ide`) print the exact `pip install` line and exit 1, with no traceback. `--llm-model` alone resolves to the provider saved with `fluid ai setup`, and to `ollama` when none is saved. For AI forge the check runs before the interview reads any context or memory, and before the `fluid ai setup` wizard reads the OS keyring or asks for a key. The forge message names `--llm-provider claude-code` (your Claude Code login) and `--template starter`; the `--agent-loop` message names only `--template starter`; `ai setup` and `init` name `claude-code`, `codex`, `cursor`, `kiro`, `mcp-sampling` and `--template starter`. Only Claude Code needs no setup of its own: `codex`, `cursor` and `kiro` reuse their own CLI login or key, and `mcp-sampling` runs inside `fluid mcp serve`, which needs `[mcp]`. `fluid forge data-model` with no provider flags runs offline. `fluid init` does not exit 1 for a missing extra: its AI hand-off prints the line and the options, then continues in template mode (it picks Claude Code if `claude` is on `PATH`). Since 0.30.0 it does exit 1 in one case: with litellm installed and keys for two or more providers set, with no provider named, the AI path stops instead of writing a template ([forge-cli #857](https://github.com/Agenticstiger/forge-cli/pull/857); see [Changes in 0.30.0](#changes-in-0-30-0)). Bare interactive `fluid forge` with no provider uses Claude Code when it is installed, and otherwise prints the hint and offers guided mode. Template and blank forge are unchanged. `fluid scaffold-ide` writes nothing without `mcp`, because every entry it writes launches `fluid mcp serve`.

```text
❌ The MCP server needs mcp, which is not installed.

    pip install 'data-product-forge[mcp]'
[ERR_MCP_SDK_UNAVAILABLE]
```

**Lineage is the one that does not stop.** Lineage is emitted only by `fluid apply` through the OpenTofu engine and by acquisition builds; a native local apply never emits it. Without `lineage`, those print one warning naming the extra on the console (and log it) and carry on without sending events.

**AWS needs `aws`.** boto3 used to arrive through litellm. Without it, a native AWS plan that cannot resolve the account id fails with `The AWS account id could not be resolved: boto3 is not installed, so sts:GetCallerIdentity cannot be called`, followed by the install line, instead of the misleading bucket-name error it used to give. Only a contract that declares orchestration (`orchestration.schedule`, `triggers` or `tasks`) reaches that plan; other contracts skip it. `fluid apply` without boto3 instead warns that the Glue catalog import blocks are omitted. Setting `AWS_ACCOUNT_ID` avoids the lookup.

`fluid doctor` no longer reports a configured provider as ready when litellm is missing; its Next steps panel names the extra.

**Before you move,** put the extra in `FLUID_PACKAGE_SPEC` in CI, or in your own install step.

### Pins that changed with it

*(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* The `mcp` extra now needs `mcp>=1.30,!=2.0.*,!=2.1.*,<3.0` (it was `mcp>=1.22`), because earlier releases have published advisories, among them an SSE session that was not bound to the principal that opened it; `fluid mcp output-port serve` uses that transport. The `litellm` extra excludes litellm 1.107.0, a malicious release since removed from PyPI (MAL-2026-2144).

### The dependency list now matches the imports

*(since 0.28.0, [forge-cli #829](https://github.com/Agenticstiger/forge-cli/pull/829))* `typing-extensions` and the Windows-only `colorama` leave the base install, because nothing imports them (`pydantic` and `click` still bring them where needed). `anyio` is named in it. The `[gcp]` extra drops `google-auth-oauthlib` and `google-cloud-iam`. The GCP project-access probe, which is the one user of `google-api-python-client` (still not in `[gcp]`), reports "not checked" when that package is absent, where it used to report "no access". `fluid odcs validate --roundtrip` needs `deepdiff`, which now belongs to the `[odcs-strict]` extra; a missing one says so.

### A project `.env` can no longer configure the embedded Debezium Server

*(since 0.28.0, [forge-cli #833](https://github.com/Agenticstiger/forge-cli/pull/833))* If you set any of these in a project `.env`, `.env.<environment>` or `.env.local`, move it to the shell or the CI job: it is ignored now, with the usual warning. The names are `DEBEZIUM_*`, `QUARKUS_*`, `SMALLRYE_*` and `MP_CONFIG_*` in the forms SmallRye Config matches, `JDK_JAVA_OPTIONS`, `JAVA_OPTS`, `JAVA_HOME`, and the launcher's `EXTRA_CONNECTOR`, `JMX_HOST`, `JMX_PORT`, `JMX_EXPORTER_PORT`, `JMX_EXPORTER_CONFIG` and `OTEL_JAVAAGENT_*`. See [Project dotenv trust](./advanced/project-dotenv-trust.md).

### Iceberg sink `catalogAuth` checks are stricter

*(since 0.28.0, [forge-cli #828](https://github.com/Agenticstiger/forge-cli/pull/828) and [#830](https://github.com/Agenticstiger/forge-cli/pull/830))* On a Kafka Connect or embedded Debezium build with `sink.catalogAuth`, `fluid validate` and the run's preflight now refuse a catalog or token endpoint at a cloud metadata address (AWS, GCP, Oracle and Alibaba, IPv6 and NAT64 forms included) even when you list it, and a catalog URL that holds `${`, starts with `env:` or holds a control character, wherever it is set (`binding.location.uri`, `iceberg_catalog_overrides`, the `iceberg.*` keys of `sink_connector_config` except `iceberg.kafka.*`, `server.sink.config`). A build without `catalogAuth` is unchanged. See [Operator allowlists](./advanced/source-aligned-acquisition.md#operator-allowlists) and [Network safety](./advanced/network-safety.md).

### Databricks tables get tags and comments

*(since 0.28.0, [forge-cli #831](https://github.com/Agenticstiger/forge-cli/pull/831))* `fluid apply` writes the table comment and column comments from the contract (on a table a dbt build writes, the comments stay dbt's), and every Databricks table gets the product's identity tags (`fluid_product_id`, `fluid_layer`, `fluid_owner_team` and others), which count toward Unity Catalog's 50 tags per securable together with your labels. A contract that used to apply may now be refused: a label that becomes one of those keys (`databricks-tag-collision`), a tag value over 256 characters (`databricks-tag-value-too-long`), more than 1,000 column tags on a table (`databricks-tags-too-many`), and a description holding a backslash or `${` (`databricks-comment-unsafe`). A table is certified through Unity Catalog's `system.certification_status`: `certified` when the label `certification: certified` is set, `deprecated` when `lifecycle.state` is `deprecated`; any other value of the label is refused (`databricks-certification-invalid`). Setting it needs the ASSIGN permission on that governed tag for the deploy identity (from Databricks' documentation; not verified on a live workspace), and the plan names the tables. After a load, *(since 0.28.0, [forge-cli #835](https://github.com/Agenticstiger/forge-cli/pull/835))* the bronze landing deletes the local masked Parquet copy under `.fluid/staging/<build>/` and fails the run if it cannot. See [Databricks](./providers/databricks.md).

### Other changes

- *(since 0.28.0, [forge-cli #840](https://github.com/Agenticstiger/forge-cli/pull/840))* For a local-provider deployment, `fluid publish` reports a relative `location.path` anchored at the contract's directory, so the Command Center gets the file the engine writes. The contract itself is unchanged.
- *(since 0.28.0, [forge-cli #835](https://github.com/Agenticstiger/forge-cli/pull/835))* `fluid generate iac` prints the reason, fix and doc of a sovereignty refusal, as `fluid apply` does.
- *(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* The CLI prints install hints as written, and masks GitHub, Anthropic and OpenAI keys, JWTs and `password=...` pairs in the error text it prints.
- *(since 0.28.0, [forge-cli #836](https://github.com/Agenticstiger/forge-cli/pull/836))* `fluid --help` and each command import only the module of the command being run: about 300 modules on a bare install instead of about 857. The command list and every help line are unchanged.
- *(since 0.28.0, [forge-cli #832](https://github.com/Agenticstiger/forge-cli/pull/832))* Nine internal modules that nothing imported are removed: `fluid_build.logging_utils`, `fluid_build.cli.init_samples`, `fluid_build.copilot.schemas.table_metadata`, `fluid_build.providers.local.ducksql`, `.mocks` and `.samples`, and `fluid_build.runtimes.dataform_gcp`, `.dbt_bigquery` and `.dbt_duckdb`. No command or contract behaves differently. It matters only to code that imported one of them directly.


## Changes in 0.29.0

These changes to AI authoring can change what a script, a CI job or an IDE agent sees.

### Which provider and which key

- *(since 0.29.0, [forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850))* **A run with nothing configured and no terminal picks an LLM.** It uses a running local Ollama, else the first coding-agent CLI on `PATH`, where it used to fall back to `gemini`. Name the provider to keep a job from picking one. See [When nothing is configured](./advanced/llm-providers.md#when-nothing-is-configured).
- *(since 0.29.0, [forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852))* **No `gemini` fallback.** When nothing selects a provider, forge stops with `copilot_no_llm_provider` and says why. It used to fall back to `gemini`, and sent `FLUID_LLM_API_KEY` there whatever key it was. Pass `--llm-provider`, set `FLUID_LLM_PROVIDER` or the key of exactly one provider, or save a provider with `fluid ai setup`. See [No LLM provider is selected](./advanced/production-troubleshooting.md#no-llm-provider-is-selected).
- *(since 0.29.0, [forge-cli #854](https://github.com/Agenticstiger/forge-cli/pull/854))* **Runs without a terminal use the provider `fluid ai setup` saved**, with its model and Ollama host, and `fluid doctor` walks the same ladder. A saved coding agent is passed over when a run states an endpoint or a model, or runs the agent loop. See [Which provider a run uses](./advanced/llm-providers.md#which-provider-a-run-uses).
- *(since 0.29.0, [forge-cli #853](https://github.com/Agenticstiger/forge-cli/pull/853))* **`FLUID_LLM_API_KEY` goes only to a provider you name.** A job that used it with a provider forge picked, such as a running Ollama or the provider of the one key variable set, now sends that provider's own key, or none, and forge warns. Name the provider: `--llm-provider <name>` or `FLUID_LLM_PROVIDER=<name>`. See [Which key a provider gets](./advanced/llm-providers.md#which-key-a-provider-gets).
- *(since 0.29.0, [forge-cli #853](https://github.com/Agenticstiger/forge-cli/pull/853))* **A project `.env` endpoint for OpenAI, Anthropic, Gemini or GitHub Models needs the provider's own key beside it.** `FLUID_LLM_API_KEY` no longer pairs it, and interactive setup no longer copies your saved key over the project's key. See [LLM endpoints in a project file](./advanced/project-dotenv-trust.md#llm-endpoints-in-a-project-file).
- *(since 0.29.0, [forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850))* **`claude -p` no longer reads your Claude Code settings.** Authentication kept there (an `apiKeyHelper`, or Bedrock or Vertex variables in `settings.json`) must come from the shell environment. See [Claude Code](./advanced/llm-providers.md#claude-code).

### Ollama

- *(since 0.29.0, [forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850))* **Ollama calls reach the daemon.** They go to `--llm-endpoint`, else `OLLAMA_HOST`, else `localhost:11434`, and a remote `OLLAMA_HOST` is honoured. See [The Ollama endpoint](./advanced/llm-providers.md#the-ollama-endpoint).
- *(since 0.29.0, [forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852))* **`OLLAMA_HOST` may name any machine everywhere.** The probe for a running Ollama, the default-model pick and `fluid ai setup` no longer swap a non-local host for `localhost`, and `fluid ai test --endpoint` takes an Ollama address on any host.
- *(since 0.29.0, [forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852))* **Forge looks for Ollama models where it sends the call.** With `--llm-endpoint` or `FLUID_LLM_ENDPOINT`, the default-model pick and the model check ask that daemon, and each `--tiered` stage calls it. A `user:password@` in the address goes as basic auth to the call and to the model lookups. See [One address for every Ollama read](./advanced/llm-providers.md#one-address-for-every-ollama-read).

### `fluid forge --agent`, `fluid ai test` and provider code

- *(since 0.29.0, [forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850))* **`fluid forge --agent` honours the AI flags.** With `--llm-provider`, `--llm-model`, `--llm-endpoint` or `--context`, it authors with forge's AI instead of writing the blank TODO contract, and a failed generation exits non-zero. See [Headless agent mode](./cli/forge.md#headless-agent-mode).
- *(since 0.29.0, [forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852))* **In AI mode, `fluid forge --agent` reports the contract for any `--target-dir`.** See [Headless agent mode](./cli/forge.md#headless-agent-mode).
- *(since 0.29.0, [forge-cli #854](https://github.com/Agenticstiger/forge-cli/pull/854))* **`fluid forge --agent` stdout is JSON Lines only.** Panels, other output and the missing-extra message go to stderr.
- *(since 0.29.0, [forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850))* **`fluid ai test` probes the real call.** A rejected key exits `3`, a model the provider does not have exits `4`, and other failed calls exit `5`. See [`ai test`](./cli/ai.md#ai-test).
- *(since 0.29.0, [forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852))* **`LlmProvider.list_available_models` takes an `endpoint` keyword**, the address the call will go to. Forge passes it only when an endpoint is stated, so code that subclasses `LlmProvider` and overrides the method with two arguments keeps working until then. With an endpoint stated and the model check on (`--require-llm`, `--tiered` or `FLUID_LLM_MODEL_PREFLIGHT`), the check fails with `copilot_llm_model_preflight_failed`; add the keyword to avoid it.

## Changes in 0.30.0

These changes shipped in 0.30.0. The first can stop a plan that used to pass: read it before you upgrade a pipeline.

### `fluid plan` checks sovereignty by default

*([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* `fluid plan` now refuses a contract that `fluid validate` refuses for its sovereignty policy. It exits 1 with `ERR_SOVEREIGNTY_VIOLATION` and writes no plan. Up to 0.29.0 plain `fluid plan` wrote a plan for such a contract and exited 0; only `--check-sovereignty` checked. Under `enforcementMode: strict`, the schema default, the refused contracts include one with a binding outside `allowedRegions`, in another jurisdiction, or on AWS, GCP, Azure or Databricks with no region declared. In every mode they include one with a binding in a region listed in `deniedRegions`.

- **A plan step can now fail.** Before you upgrade, run `fluid validate` on each contract: the sovereignty errors it reports are the ones `plan` now refuses. To write the plan anyway, pass `--no-check-sovereignty`. It prints a warning and logs a WARNING (`sovereignty_check_skipped`), and `fluid apply` keeps its own checks.
- **A failing plan stage writes no plan file.** The pipelines `fluid generate ci` writes already pass `--check-sovereignty`. On 0.29.0 a failing stage still wrote `plan.json`; now it writes none, and a file an earlier run left at `--out` stays as it was. A provider hook that reports nothing no longer passes a contract `fluid validate` refuses, because the same check runs first.

See [Sovereignty gate](./cli/plan.md#sovereignty-gate-since-0-15-0).

### Databricks

- *([forge-cli #865](https://github.com/Agenticstiger/forge-cli/pull/865), since 0.30.0)* **A Databricks expose with `semantics` now gets a metric view, and the apply needs `databricks-sdk`.** `fluid apply` creates `<table>_semantic_model` beside the table. Without `pip install 'data-product-forge[databricks]'`, the apply is refused before anything is applied. A `semantics` block the view cannot hold (a derived metric, say) now fails `fluid validate` for a Databricks binding: express it as a ratio, or remove it. See [Metric views](./providers/databricks.md#metric-views).
- *([forge-cli #873](https://github.com/Agenticstiger/forge-cli/pull/873), since 0.30.0)* **A schema the contract stops using is now destroyed, not left failing the apply.** When a table moves to another schema or a schema's last expose is removed, `fluid apply` drops the metric views and the mask and row filter functions this product made there, when the deploy identity owns them, so OpenTofu can destroy the schema. Anything else the schema holds is named and left. `--mode dry-run` lists the drops and runs none. See [A schema the contract stops using](./providers/databricks.md#a-schema-the-contract-stops-using).
- *([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* **Unity Catalog tag values are written as the contract states them.** A tag value is now the contract's text less surrounding whitespace. Up to 0.29.0 it was the GCP label slug: lower-cased, with each character other than a letter, a digit, `_` or `-` turned into `-`, and cut at 63 characters. So `fluid_jurisdiction` is `US` where it was `us`, and `fluid_regulation` is `GDPR, CCPA` where it was `gdpr_ccpa`. Tag keys are unchanged, and so are GCP labels and AWS tags. See [Governance tags](./providers/databricks.md#governance-tags).
  - **The next `fluid apply` updates the tags in place.** The plan shows each changed tag as `~`. Nothing is replaced or destroyed, and no `--allow-data-loss` is needed. Until that apply, `fluid verify` reports each old value as a changed tag (`CRITICAL`). On Databricks Free Edition, a product carrying the old values planned `+0 ~17 -0`.
  - **A value over 256 characters is refused** as `databricks-tag-value-too-long` by `fluid validate`, `fluid generate iac` and `fluid apply`. Up to 0.29.0 it was cut to 63 characters. Shorten the value before you upgrade.
  - **Anything that reads a tag value sees the new text**, for example a query on `information_schema.table_tags` that matches `'us'`.
- *(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* **`fluid apply --mode amend-and-build` on Databricks runs each dbt job build now, and waits for it.** Up to 0.29.0 it only provisioned the job, so a manual job never ran. A pipeline that applies with `amend-and-build` or `replace-and-build` now waits for each run, up to `FLUID_DATABRICKS_RUN_TIMEOUT_SECONDS` (by default an hour, or the job's own limits plus 15 minutes), and fails when a run fails. It needs `databricks-sdk`: without `pip install 'data-product-forge[databricks]'`, the apply is refused before anything is applied. To provision a job without running it, apply with `--mode amend`. See [Running the job from `fluid apply`](./providers/databricks.md#running-the-job-from-fluid-apply).
- *(since 0.30.0, [forge-cli #864](https://github.com/Agenticstiger/forge-cli/pull/864))* **A Databricks expose with a freshness or completeness SLO turns on data quality monitoring at the next `fluid apply`.** A contract that already states `qos.freshnessSLO`, `qos.completenessTarget`, an `observability.defaultSLIs` freshness or completeness block, or a `contract.dq.rules` entry of type `freshness`, `completeness` or `anomaly_detection` gets a `databricks_data_quality_monitor` on the schema it owns. Its scans run on serverless compute, billed as `DATA_QUALITY_MONITORING`. On Databricks Free Edition, expect them to count toward the daily compute quota (not measured), and a workspace over it stops all compute for the rest of the day. If Databricks refuses the monitor (it documents that monitoring needs serverless compute and `MANAGE` on the schema or its catalog), the apply now fails after the tables are created. To keep an expose unwatched, set `contract.dq.monitoring.enabled: false` on it. See [Data quality monitoring](./providers/databricks.md#data-quality-monitoring).
- *(since 0.30.0, [forge-cli #871](https://github.com/Agenticstiger/forge-cli/pull/871))* **A Databricks dbt job runs the contract's `dq.rules` as dbt tests at the next `fluid apply`, and a rule that cannot run is refused.** Up to 0.29.0 the job ignored these rules, and `fluid validate` accepted them whatever they said. The upload now gains the generated test files, one or more per rule, in a `fluid_dq/` folder under the first of the project's `test-paths`, and `dbt build` runs each test right after its model. A rule of severity `critical` or `error` that fails now fails the run, skips the models below it, and fails the `--mode amend-and-build` apply that started it. A `warn` or `info` rule is reported and does not. Before you upgrade, run `fluid validate` on each contract. On an expose a Databricks dbt job writes, it now refuses a `drift_detection` rule, an `anomaly_detection` rule on an expose with monitoring turned off, a `valid_values` rule with no allowed values, a rule that names a column the schema does not declare, a build whose `repository` is a Git URL while an expose it writes has rules, and a project that already holds a test with a rule's name, or a file at the path of a generated test (`<test path>/fluid_dq/<model>/<name>.sql`). To keep a rule from failing runs, set its `severity` to `warn`. See [Contract rules as dbt tests](./providers/databricks.md#contract-rules-as-dbt-tests).

### Other changes

- *([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* Logs and printed errors no longer mask a fully qualified name such as `catalog.schema.table`: `fluid apply` printed `databricks.load table=***REDACTED***`, and now prints the table's name. A JWT or JWE is still masked, recognised by its JOSE header (a first part that decodes to a JSON object). `redact_secret_text()` no longer takes the `keep_dotted_names` keyword, so code that passes it gets a `TypeError`.
- *([forge-cli #857](https://github.com/Agenticstiger/forge-cli/pull/857), since 0.30.0)* **Keys for two or more providers stop the run, even with Ollama running.** With `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` both set (or one provider's key and `OLLAMA_HOST`) and nothing naming a provider, a run without a terminal used a running local Ollama, and interactive setup used the first key it found. Forge now stops with `copilot_no_llm_provider` and names the keys, without asking Ollama. `fluid ai test` and `fluid doctor` say the same, and `fluid init`'s AI path exits 1 where it used to write a template. A `fluid ai setup` choice and a single keyring key still come first, and `GEMINI_API_KEY` with `GOOGLE_API_KEY` is one provider. Pick one with `--llm-provider` or `FLUID_LLM_PROVIDER`. See [No LLM provider is selected](./advanced/production-troubleshooting.md#no-llm-provider-is-selected).

## Changes in 0.30.1

`0.30.1` fixes one regression of `0.30.0`. Use `0.30.1`, not `0.30.0`.

| Change | What to do | How to check |
|---|---|---|
| `fluid validate --strict` no longer fails a dbt-built Databricks product that describes its tables. `0.30.0` warned on every Databricks expose a dbt build writes when the contract has a table or column description, because dbt's `CREATE OR REPLACE` sets the comments and `fluid apply` sets none. `--strict` turned that warning into an error, so stage 2 of the generated pipelines (`VALIDATE_STRICT` defaults to true) failed for every such product. The message is now a note with the same text | Upgrade to `0.30.1`, not `0.30.0` | `fluid validate --strict` passes. The note is under "Validation Notes:", `--format json` lists it under `notes`, and a bundle reports it as an `info` issue |

## Changes in 0.31.0

These changes are in 0.31.0. Several remove a command, flag, tool or variable: read them before you upgrade a pipeline.

*(since 0.31.0, [forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879))*

- **`fluid mcp output-port serve --transport http` speaks MCP Streamable HTTP at `/mcp`. The HTTP+SSE endpoints `/sse` and `/messages/` are gone.** The MCP specification deprecated HTTP+SSE in its 2025-03-26 revision. Point each client at `http://<host>:<port>/mcp` and set its transport to Streamable HTTP, `--transport http` in `claude mcp add` for example. A client still set up for SSE fails: `/sse` answers 404 once a request passes auth, and at `/mcp` its `GET` gets 400 (`Missing session ID`). Behind the shipped proxy templates the URL becomes `https://<your domain>/mcp`, and their settings for streamed responses stay as they are.
- **An MCP server without auth no longer listens beyond loopback.** A `--host` other than `127.0.0.0/8`, `::1` or `localhost` now stops at startup, with exit 2 and the fix, when auth is off: the default `shared-token` mode with no `FLUID_MCP_AUTH_TOKEN`, `jwt` without its three settings, or `FLUID_MCP_AUTH_MODE=none`. Up to 0.30.1 the output port warned and served. Off loopback, a shared token must also be at least 32 characters: `openssl rand -hex 32` makes one.
- **Without auth, a request's `Host` must be `127.0.0.1`, `localhost` or `[::1]` (or the bound address) with a port, or it gets 421.** So a gateway behind a reverse proxy that forwards its public name needs `FLUID_MCP_AUTH_TOKEN` (or `jwt`) set on the gateway itself.
- **A browser request from a page not served from this machine gets 403**, with or without auth: an `Origin` that is not `http` or `https` on a loopback host, `Origin: null` included. With auth off, the `Origin` must also be `127.0.0.1`, `localhost` or `[::1]` (or the bound address) with a port. Clients that are not browsers send no `Origin` header and are not affected.
- **`fluid mcp serve` gains `--transport http`**, which serves the authoring tools the same way, by default at `http://127.0.0.1:8766/mcp`. stdio stays the default. See [Serve over HTTP](./cli/mcp.md#serve-over-http).

*(since 0.31.0, [forge-cli #880](https://github.com/Agenticstiger/forge-cli/pull/880))*

- **`fluid validate --strict` fails on placeholder emails, starter-template values and TODO markers, on an SDP build that joins, and on an SDP that consumes a product whose type the workspace cannot read.** Each is a new warning, so `fluid validate` without `--strict` still passes. A CI job that runs `--strict`, stage 2 of a generated pipeline among them, now fails on a contract that still has an owner email at `example.com` or `company.com`, a `TODO`, or the values of an unedited template: a contract scaffolded from a template (`fluid init --quickstart`, `fluid init --template`, `fluid forge --template`) has a placeholder owner email until you edit it. Replace each value with the real one, or delete an optional key such as `metadata.owner.email`. See [Placeholders and starter values](./cli/validate.md#placeholders-and-starter-values) and [What an SDP does not do](./cli/validate.md#what-an-sdp-does-not-do).
- **`fluid validate --format json` adds `issues`, with a code, a JSON pointer, a fix and an example for each finding.** It is there only when there is a finding, and `errors`, `warnings` and `notes` are unchanged. A bundle's `CONTRACT-RULE` findings gain `rule`, `pointer`, `fix`, `example` and `docs_url`. See [Finding codes and `issues`](./cli/validate.md#finding-codes-and-issues).

*(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))*

- **`fluid forge` AI mode runs on the four FLUID Agent Skills, and the embedded copilot is removed.** With a coding agent and a terminal, forge opens the agent in the workspace with the skills loaded; with no terminal, it drives Claude Code headless, and Codex, Cursor and Kiro take the one-call path. Without a coding agent, it makes one LLM call with the skills' text and sends `fluid validate --offline` errors back, for at most 3 attempts. AI mode no longer overwrites a contract: use `--refine` to change one. A run with no terminal needs `--context`, and `--forge-agent-mode` defaults to `agentic`. See [AI mode in 0.31.0](./cli/forge.md#ai-mode-in-0-31-0).
- **`fluid memory`, `fluid mission`, `fluid stats --judge`, `fluid init --agent`, `fluid init --show-work` and 30 `fluid forge` flags are removed.** A command that still passes one exits 2, with `unrecognized arguments`, or with `invalid choice` for the word after a flag that took a value. Take it out: [Removed flags](./cli/forge.md#removed-flags) lists each forge flag with what to use instead. `fluid forge --no-memory` is still accepted and ignored.
- **`fluid mcp serve` loses five tools.** `forge_run`, `forge_from_source`, `score_contract_quality`, `enrich_contract_suggestions` and `search_semantic_memory` are removed, and so is `--llm-provider mcp-sampling`. Take them out of `--allow-tools` and `--deny-tools` lists and agent instructions. See [Authoring tools](./advanced/mcp.md#authoring-tools).
- **The store's `postgres` and `vector` backends and the `[vector]` extra are removed.** `FLUID_STORE_BACKEND=postgres` or `vector` logs a warning and uses the file store, and `fluid doctor` asks you to unset it. Drop `[vector]` from install specs.
- **Variables only the copilot read are ignored**, among them `FLUID_PROMPT_PROFILE`, `FLUID_PROMPT_OVERLAYS`, `FLUID_AGENT_WEB_TOOLS`, `FLUID_FORGE_AUTO_RESUME`, `FLUID_INTERVIEW_LEGACY` and `FLUID_LLM_FALLBACK_CHAIN`. [Environment variables](./advanced/environment-variables.md) marks each one.
- **`fluid forge data-model` is unchanged.** Every subcommand and flag stays, `--tiered` and the routing-model flags included, and so does `fluid stats --json`. Command Center's `from-intent` path, with `--deterministic` or `--llm-provider`, runs on them as before.

*(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))*

- **`fluid mcp serve` reads source catalogs with one tool, `source_catalog`, and serves 7 tools.** `list_source_adapters`, `list_source_tables`, `inspect_source_table`, `list_source_lineage` and `list_source_glossary` are now `source_catalog` with `kind` set to `adapters`, `tables`, `table`, `lineage` or `glossary`. The other arguments keep their names, and no alias keeps the old tool names: rename the calls in agent instructions and scripts. Every result names its `kind`, and a `table` or `lineage` result now sits under it, as in `{"kind": "table", "table": {...}}`. A result is `concise` unless the call asks for `"response_format": "detailed"`, which returns every field, as the five tools did. See [`source_catalog`](./advanced/mcp.md#source-catalog).
- **An unknown tool name in `--allow-tools` or `--deny-tools` stops `fluid mcp serve` with exit 2.** A name that is not a tool now fails at startup: a typo, one of the five tools, or a tool that [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881) removed. In 0.30.1 those tools were still served, and a typo was ignored. Replace the five names with `source_catalog`. An IDE config that an older `fluid scaffold-ide` wrote lists the five old tools under `autoApprove`, so the client does not auto-approve `source_catalog`: add it to the list by hand, or run `fluid scaffold-ide --force`, which writes the scaffold's files again over any edits. See [Access controls](./cli/mcp.md#access-controls).
- **A result estimated at more than 6,000 tokens comes back as a resource.** The call returns a short envelope and a `resource_link` to `fluid://artifacts/<id>`, which the client reads with `resources/read`. Over stdio the envelope also names a file holding the same JSON. A client that reads only a result's text sees the envelope where it used to see the result. `FLUID_MCP_INLINE_TOKEN_LIMIT=0` keeps every result inline. See [Large results](./advanced/mcp.md#large-results).
- **A catalog listing with a scope now works through an MCP client.** On MCP SDK 2.x, `list_source_tables` (now `source_catalog` with `kind` set to `tables`) and a scoped `list_source_glossary` failed with `Error executing tool` for an ordinary scope such as `{"database": "DB", "schema": "SALES"}`: the server sent the scope's unset `tables` back as `null`. Unset fields are now left out.

*(since 0.31.0, [forge-cli #887](https://github.com/Agenticstiger/forge-cli/pull/887))*

- **An unknown tool name in `--allow-tools` or `--deny-tools` stops `fluid mcp output-port serve` with exit 2.** The check runs before either transport binds, as it does for `fluid mcp serve`. In 0.30.1 a mistyped name was accepted: a deny list denied nothing and the tool stayed callable, and a mistyped allow list served fewer tools without a word. The tools are `describe`, `query`, `query_sql` and `sample`, and matching is exact and case-sensitive. Fix the name in the launcher script or IDE config that starts the gateway. See [`serve` flags](./cli/mcp.md#serve-flags).

*(since 0.31.0, [forge-cli #888](https://github.com/Agenticstiger/forge-cli/pull/888))*

- **`FLUID_TELEMETRY`, `DO_NOT_TRACK` and `telemetry.enabled` in `~/.fluid/config.yaml` do nothing.** The UX telemetry and its consent are removed, and nothing emits the `forge.invocation` span fields. `fluid doctor --env` no longer lists the two variables or prints the telemetry line, and `fluid doctor --env --json` is `{"env": [...]}` without the `telemetry` key. A script that reads that key gets nothing: stop reading it.
- **`FLUID_COPILOT_AGENT_LOOP` no longer stops forge from picking a saved or detected coding agent.** The variable does nothing, like `FLUID_COPILOT_FORCE_INTERVIEW`, `FLUID_COPILOT_JUDGE`, `FLUID_COPILOT_SELF_EVAL` and `FLUID_COPILOT_SEMANTIC_MEMORY`, which nothing reads either. Drop all of them from env files and CI settings.

*(since 0.31.0, [forge-cli #891](https://github.com/Agenticstiger/forge-cli/pull/891))*

- **A contract that pins `sovereignty.jurisdiction` starts `fluid mcp output-port serve --transport http` only with JWT auth that maps a claim to `jurisdiction`.** In 0.30.1 it also started under `shared-token`, under `jwt` without its issuer, audience or JWKS URL, and under a `FLUID_MCP_JWT_CLAIM_MAPPING` that maps the claim away, then denied every call as `missing-caller-jurisdiction`. Each now exits 2 before it listens and says why. Such a gateway answered no call, so nothing that worked stops working: switch it to `FLUID_MCP_AUTH_MODE=jwt`, or set `sovereignty.crossBorderTransfer: true` if the data may leave. See [Caller-jurisdiction enforcement](./advanced/mcp.md#caller-jurisdiction-enforcement-since-0-15-0).

*(since 0.31.0, [forge-cli #906](https://github.com/Agenticstiger/forge-cli/pull/906))*

- **`fluid validate --strict` fails on two new warnings about dbt MetricFlow names**: a dimension with the name of an entity or another dimension of its expose, and a name that is a dimension of one expose and an entity of another, which `dbt parse` rejects whenever the project declares a metric. Rename one of the two. See [Names dbt MetricFlow holds once](./concepts/semantic-layer.md#names-dbt-metricflow-holds-once).
- **A contract that `fluid forge data-model` writes with one expose per dataset gives each relationship's foreign entity to its `from` expose only.** Every expose used to get the foreign entity of every relationship, most of them on a column the expose does not have, and `fluid generate transformation` exported them to dbt. Forge the contract again, then generate its dbt project again.
- **`fluid generate transformation` reads a `semantics` collection that is not a list as empty, with a warning**, where it stopped with a `TypeError`.

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))*

- **BREAKING: `tofu` runs with an environment allowlist, not a copy of your environment.** `fluid apply`, `fluid plan --tofu`, `fluid diff`, `fluid verify --state-drift` and `fluid generate iac --validate` pass `tofu` the process basics, proxies and CA bundles, OpenTofu's settings by name plus `TF_TOKEN_*`, `TOFU_CLI_PATH` and `GITHUB_OUTPUT`, the credential families of the plugin (`AWS_`, `GOOGLE_`, `SNOWFLAKE_`, `DATABRICKS_` and the others), and the cloud of the state backend and of the encryption key. `TF_CLI_ARGS*`, `TF_VAR_*`, `TF_ENCRYPTION`, `TF_INPUT` and `TF_REATTACH_PROVIDERS` no longer pass, and neither do model keys such as `GOOGLE_API_KEY` or `AZURE_OPENAI_API_KEY`. A job that set one of them to change what `tofu` does stops doing so: a `tofu_env_dropped` warning names the variables. An IaC plugin that lives outside forge declares what its provider reads in `credential_env_vars` and `credential_env_prefixes`. See [What `tofu` gets from the environment](./cli/apply.md#what-tofu-gets-from-the-environment).
- **BREAKING: `PipelineConfig.oidc_provider` and `generate_pipeline_template(oidc_provider=)` are replaced by `cloud_auth`.** No CLI flag ever set them, so their OIDC steps never reached a generated pipeline, and the Azure login step went with them. Code that calls the library passes `cloud_auth`, a tuple of `aws`, `gcp`, `snowflake`, `databricks` and `openbao`, which `fluid generate ci` fills from the contract. See [Keyless cloud login](./advanced/operating-in-ci.md#keyless-cloud-login).
- **A Databricks run with an OIDC auth type needs `DATABRICKS_CLIENT_ID`.** `github-oidc`, `azure-devops-oidc`, `env-oidc` and `file-oidc` exchange the job's token for the service principal the client id names. forge used to blank it for any type but `oauth-m2m`. See [Credentials](./providers/databricks.md#credentials).
- **New, opt-in: `FLUID_STATE_ENCRYPTION` encrypts the OpenTofu state and saved plan.** Nothing changes until you set it, and it needs OpenTofu 1.13 or newer. See [State and plan encryption](./cli/apply.md#state-and-plan-encryption).
- **New: generated GitHub Actions and GitLab pipelines log in to the cloud with OIDC**, and Snowflake accepts workload identity federation. Regenerate a committed pipeline with `fluid generate ci` and create the cloud-side trust its header lists. See [Keyless cloud login](./advanced/operating-in-ci.md#keyless-cloud-login) and [Workload identity federation](./providers/snowflake.md#workload-identity-federation).

*(since 0.31.0, [forge-cli #909](https://github.com/Agenticstiger/forge-cli/pull/909), [forge-cli #925](https://github.com/Agenticstiger/forge-cli/pull/925), [forge-cli #946](https://github.com/Agenticstiger/forge-cli/pull/946), [forge-cli #949](https://github.com/Agenticstiger/forge-cli/pull/949))*

- **`fluid profile` is a new command.** It reads one expose's records where they live and writes a FLUX profile document of output-checked aggregates, which a Simulation pins by digest. It reads every value and forms every statistic with `flux-stats`, the registry FLUX's fidelity check uses. Nothing that exists changes. The `[profile]` extra adds DuckDB and flux-stats (`>=0.6.0,<0.7`) from PyPI; `fluid profile` says what to install when flux-stats is missing. See [`fluid profile`](./cli/profile.md).

*(since 0.31.0, [forge-cli #951](https://github.com/Agenticstiger/forge-cli/pull/951))*

- **`fluid profile` writes FLUX's `mean/1` statistic for each number column**, so a run checked against the profile can pass `fluxsim verify` and `fluxsim ship`. A profile you wrote before keeps its digest. Written again, it carries `mean/1` and gets a new digest, so pin the new one. `--fractional-bits` sets the grid, 16 by default, and it must equal the fidelity block's `encoding.fractionalBits`. See [The `mean/1` statistic](./cli/profile.md#the-mean-1-statistic).

*(since 0.31.0, [forge-cli #911](https://github.com/Agenticstiger/forge-cli/pull/911))*

- **0.7.7 (preview) contracts can state rules about valid data, and `fluid validate` checks them.** `exposes[].contract.invariants[]` holds checks, derived columns and dependencies, written in FLUID SQL/1. Columns gain `identifierFormat`, `placeholders` and `sharedAttribute`, and relationships gain `sharedColumns`. Every field is optional. A 0.7.7 contract that uses none of them gets no new errors, though it may get notes, which `--strict` never counts. See [Rules about valid data](./concepts/data-rules.md).

*(since 0.31.0, [forge-cli #917](https://github.com/Agenticstiger/forge-cli/pull/917))*

- **`fluid ship` runs the 11-stage pipeline in place of the four-stage macro.** It bundles, validates, generates and validates artifacts, checks drift, plans, applies the reviewed `runtime/plan.json` against `runtime/bundle.tgz`, applies policy and verifies; `--publish` and `--schedule-sync` add stages 10 and 11. A script that runs `fluid ship` now also runs `diff`, `policy-apply` and `verify`, so a drifted target or a failed verify stops it. See [The 11-stage runner in 0.31.0](./cli/ship.md#the-11-stage-runner-in-0-31-0).
- **`validate` and `validate-artifacts` run with `--strict` by default.** A contract with a warning, a placeholder owner email among them, now stops at stage 2. `--no-strict` drops it.
- **`--skip-plan` is removed and exits 2; `--skip-bundle` is accepted and ignored.** Use `--stage` or `--until` to run part of the pipeline.
- **The exit status is ship's own**: 0 passed, 1 a stage failed, 2 ship refused its arguments, 3 a stage failed after apply changed something, 130 interrupted. Through 0.30.1 ship exited with the failing stage's code, which is now in `runtime/ship-report.json`.
- **Ship refuses before anything is written**, with exit 2: an environment name a stage would refuse (it must start with a letter, at most 64 characters), a contract that is missing, symlinked or under a system path, and an unknown stage.
- **A contract outside the current directory runs in its own directory**, so `runtime/` and `dist/` land beside it.

*(since 0.31.0, [forge-cli #928](https://github.com/Agenticstiger/forge-cli/pull/928))*

- **The templates and scaffolds write no stand-in owner email.** The templates bundled for `fluid init` carry none, and `fluid init`, `fluid market --instantiate`, `fluid forge --template`, `fluid product-new` and `fluid import` leave `metadata.owner.email` out rather than write one (`--owner-email` gives one to `fluid init --blueprint` and `--discover`). `fluid init --template csv-basics` and the `fluid market` blueprints' default no longer write the starter team `data-team`. A contract you scaffolded before keeps its placeholder: replace it with the team's real address, or delete it, before `fluid validate --strict`, `fluid ship` or a generated pipeline's stage 2.

*(since 0.31.0, [forge-cli #929](https://github.com/Agenticstiger/forge-cli/pull/929))*

- **`fluid ship` reads the generated pipelines' switches and stage knobs.** A `RUN_STAGE_<N>_<NAME>=false` in the environment switches that stage off, `--stage` included, and `VALIDATE_STRICT`, `VERIFY_STRICT`, `GENERATE_EMIT`, `DIFF_EXIT_ON_DRIFT`, `DIFF_LAST_APPLIED`, `PLAN_HTML` and `POLICY_APPLY_MODE` reach their stage. A job that exports one of them for another tool now changes what ship runs: unset it in that step (for a knob, its flag also beats the variable). After a dry-run apply, stage 8 checks the bindings only when stage 7 is in the pipeline; without it, stage 8 enforces them. See [Stage switches and knobs](./cli/ship.md#stage-switches-and-knobs).

*(since 0.31.0, [forge-cli #941](https://github.com/Agenticstiger/forge-cli/pull/941))*

- **`fluid scaffold-ci` and `fluid generate-pipeline` are removed.** Both exit 2 as unknown commands. Run `fluid generate ci --system <system>` instead (`github`, `gitlab`, `jenkins`, `azure`, `bitbucket`, `circleci` or `tekton`). A script or CI job that calls either one needs the change; `fluid forge --ci <provider>` still writes CI files.

*(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))*

- **`fluid generate ci --complexity` exits 2.** One pipeline shape replaces the four tiers. Drop the flag from scripts and add what the advanced and enterprise tiers carried with `--add security`, `--add compliance` and `--add sbom` (repeatable). See [`fluid generate ci`](./cli/generate.md#fluid-generate-ci).
- **GitHub Actions: the file is `.github/workflows/fluid-pipeline.yml`.** It replaces `fluid-basic.yml`, `fluid-standard.yml`, `fluid-advanced.yml` and `fluid-enterprise.yml`. The old tier files and the old `security.yml` and `compliance.yml` still run until you delete them. `fluid generate ci` and `fluid forge` name each one they find and do not delete it.
- **Give the GitHub environment required reviewers before you regenerate.** An apply (stages 7 to 11) now runs on a push to the default branch, in the environment named after `FLUID_ENV` (`dev` unless you set it). With no reviewers on that environment nothing waits for a person. Settings > Environments is where they go. The other systems have their own gate: see [Operating in CI](./advanced/operating-in-ci.md#what-a-generated-pipeline-runs).
- **The install settings are repository or project variables.** `FLUID_PACKAGE_SPEC`, `FLUID_PIP_INDEX_URL`, `FLUID_PIP_EXTRA_INDEX_URL` and `FLUID_ALLOW_PRERELEASE` are no longer a run-time input on GitHub Actions, GitLab CI, Azure DevOps, Bitbucket or CircleCI. A pipeline that passed one when it started a run now sets it as a variable in the repository or project settings. Jenkins and Tekton still take them as build parameters. On GitLab CI, keep the minimum role to use pipeline variables at Maintainer or No one allowed (Settings > CI/CD > Variables), since the Run pipeline form takes any variable.
- **`--publish-include-env` is removed.** `fluid ship` always passes `--env` to `fluid publish`, so drop `--publish-include-env` and `--no-publish-include-env` from scripts.
- **`fluid forge --ci-complexity` is removed.** Forge asks for the CI provider only, and `.fluid/ci-state.json` records the provider and the add-ons. A file written by an earlier forge still loads.
- **New: `--default-branch BRANCH` names the branch whose pushes apply.** The default is the remote's default branch (`origin/HEAD`), else `main`; GitLab CI reads its own `$CI_DEFAULT_BRANCH`. A pull request or merge request against it, or a manual run on another branch, runs stages 1 to 6 only.
- **`fluid ship` stage 11 writes `runtime/schedule-sync-report.json` when it runs.** See [Stage switches and knobs](./cli/ship.md#stage-switches-and-knobs).

*(since 0.31.0, [forge-cli #897](https://github.com/Agenticstiger/forge-cli/pull/897), [forge-cli #900](https://github.com/Agenticstiger/forge-cli/pull/900), [forge-cli #907](https://github.com/Agenticstiger/forge-cli/pull/907))*

- **BREAKING: three kinds of AWS contract that used to be accepted are refused.** Run `fluid validate` on each AWS contract before you upgrade, because the same checks run at `fluid generate iac` and `fluid apply`.
  - A row filter or a column restriction whose principal also holds a grant that could undo it. `row-filter-unenforceable` or `column-restriction-unenforceable` names the grant. The causes: `SELECT` or `ALL` in `permissionsWithGrantOption` for a filtered role, a read grant to `IAM_ALLOWED_PRINCIPALS`, to the filtered role's account or `:root` ARN, or to an organization, two filters on one role, and a second grant for the same role in another spelling beside a column limit. Principals are compared by IAM identity: the path is dropped and the name is read in lower case. See [Who a grant, a row filter and a column restriction name](./providers/aws.md#who-a-grant-a-row-filter-and-a-column-restriction-name).
  - A contract that plans `iam.bind_glue_database`, `iam.bind_s3_bucket`, `athena.create_view`, `redshift.ensure_schema`, `redshift.ensure_table` or `events.ensure_schedule` fails with `aws-op-not-emitted`. Through 0.30.1 `fluid generate iac` wrote the module without them and `fluid apply` exited 0. Create the view, schema or table in a build step, and for a schedule set `orchestration.schedule` with an engine other than `airflow` or `mwaa`. See [Planned operations the module does not create](./providers/aws.md#planned-operations-the-module-does-not-create).
  - `governance.lakeFormation.admins` is refused in every contract, and `tagDefinitions` unless the contract declares `packaging.containers.lfTagVocabulary: isolated`. Move the admins to your platform's bootstrap state. A product's state used to own the account's Lake Formation settings, and destroying the product left the account with no Lake Formation admin. A product whose state already holds `aws_lakeformation_data_lake_settings` needs care: with `admins` removed, the next apply plans to destroy that resource, which empties the account's admin list. The [data-loss gate](./cli/apply.md#opentofu-data-loss-gate) stops it, because the type is not one of the access grants it exempts. Put the admins in your platform's state first, and then release the resource from the product's state with `tofu -chdir=.fluid/iac/aws/<safe-id> state rm <address>`, as [Packaging modes](./cli/apply.md#packaging-modes) shows for another resource, rather than passing `--allow-data-loss`. See [Account-wide Lake Formation objects](./providers/aws.md#account-wide-lake-formation-objects).
  - Every data cells filter now writes `excluded_column_names`, so a filter that only restricts rows applies on real AWS, where it failed with `Provider produced inconsistent result after apply`. A masked view is built only for a grant that reads, so the later `<table>_masked_N` names of a contract that had a `DESCRIBE`-only grant renumber, and the next apply changes them in state.

*(since 0.31.0, [forge-cli #898](https://github.com/Agenticstiger/forge-cli/pull/898))*

- **New, opt-in: `fluid plan --tofu` saves the OpenTofu plan, and `fluid apply plan.json` runs exactly that plan.** Nothing changes until a pipeline passes `--tofu`. A pipeline that does needs a remote state both jobs share, protected plan artifacts, and a plan role that can write the state and its lock. See [Saving the OpenTofu plan](./cli/plan.md#saving-the-opentofu-plan-tofu) and [The OpenTofu plan is what gets approved](./advanced/operating-in-ci.md#the-opentofu-plan-is-what-gets-approved).

*(since 0.31.0, [forge-cli #899](https://github.com/Agenticstiger/forge-cli/pull/899))*

- **The OpenTofu floor is 1.12.0, and `--ensure-opentofu` installs 1.13.9.** A runner with `tofu` 1.6 to 1.11 stops with `tofu X.Y.Z is older than the required minimum 1.12.0`. Upgrade the runner image, or run `fluid apply --ensure-opentofu`, which now replaces an older `tofu`. On 1.11, adding retention to a live GCP table plans an in-place update that BigQuery refuses. The generated module declares `required_version = ">= 1.12"`.

*(since 0.31.0, [forge-cli #901](https://github.com/Agenticstiger/forge-cli/pull/901))*

- **`--state-backend s3://<bucket>/<key>?region=<region>` names the state bucket's region.** Only that exact tail is read as a region, so no existing key changes. After a state move to the provider key, the summary prints the commands that remove the old state object and its lock; forge never deletes state. See [Remote state](./cli/apply.md#remote-state).
- **The Snowflake provider pin moves from `~> 2.0` to `~> 2.23`.** 2.23 adds the `token_file_path` field. The next `tofu init` takes a provider of 2.23 or newer.

*(since 0.31.0, [forge-cli #915](https://github.com/Agenticstiger/forge-cli/pull/915))*

- **A new Glue Iceberg table gets its first metadata from Glue, and an existing table is never replaced.** A table that an earlier release created has no metadata, so Athena still refuses it until you replace it. See [Iceberg tables in Glue](./providers/aws.md#iceberg-tables-in-glue) for the check and the two ways to replace one that is empty.

*(since 0.31.0, [forge-cli #910](https://github.com/Agenticstiger/forge-cli/pull/910), [forge-cli #921](https://github.com/Agenticstiger/forge-cli/pull/921))*

- **The ODCS export mirrors `dq.rules` thresholds.** A FLUID threshold is the share of rows that pass, and ODCS `nullValues`, `duplicateValues` and `invalidValues` count rows that fail. Through 0.30.1 the threshold was copied across, so `threshold: 1.0` with `>=` came out as "at least one null". A full share is `mustBe: 0`, a partial completeness share is the null share as a percentage, `valid_values` is `mustBe: 0`, and a partial uniqueness share is not exported. A rule now lands on the columns it checks. Re-export every contract and re-publish the ones a catalog or a quality engine reads. See [Quality rules in the export](./cli/odcs.md#quality-rules-in-the-export).

*(since 0.31.0, [forge-cli #908](https://github.com/Agenticstiger/forge-cli/pull/908), [forge-cli #914](https://github.com/Agenticstiger/forge-cli/pull/914), [forge-cli #916](https://github.com/Agenticstiger/forge-cli/pull/916), [forge-cli #920](https://github.com/Agenticstiger/forge-cli/pull/920))*

- **Both Data Mesh Manager publish paths send lineage Entropy draws, retire stale contracts and send the archetype.** Publish again to get the product-to-product and source-system edges, the archetype, and the retirement of contracts no port names any more. Retired contracts are never deleted.
- **A product with an upper-case letter in its id is published under a lower-case id by both paths.** The registrar used the id as written. After the first publish the old product stays in Entropy until you delete it there.
- **`fluid publish --target datamesh-manager` refuses plain http to a non-local host** unless `DMM_ALLOW_INSECURE_HTTP=true`, and warns about settings it does not use. See [`fluid datamesh-manager`](./cli/datamesh-manager.md#odps-lineage-and-access-agreements).

*(since 0.31.0, [forge-cli #923](https://github.com/Agenticstiger/forge-cli/pull/923))*

- **One renderer writes every Airflow DAG a contract's `orchestration` section describes.** A DAG id drops `.` and `-` for AWS too, a bare-word schedule such as `daily` is the Airflow keyword for AWS (00:00, where it ran at 02:00), a task with no operator fails closed for every provider, and a value that did not resolve is refused, where it used to render `my-project` or `UNKNOWN_DB`. Regenerate and review each committed DAG. `fluid generate-airflow` is an alias of `fluid generate schedule --scheduler airflow`, and must run from the project directory for a contract with scheduled builds. See [`fluid generate-airflow`](./cli/generate-airflow.md#what-it-writes).

*(since 0.31.0, [forge-cli #902](https://github.com/Agenticstiger/forge-cli/pull/902), [forge-cli #903](https://github.com/Agenticstiger/forge-cli/pull/903), [forge-cli #904](https://github.com/Agenticstiger/forge-cli/pull/904), [forge-cli #912](https://github.com/Agenticstiger/forge-cli/pull/912), [forge-cli #913](https://github.com/Agenticstiger/forge-cli/pull/913), [forge-cli #918](https://github.com/Agenticstiger/forge-cli/pull/918), [forge-cli #927](https://github.com/Agenticstiger/forge-cli/pull/927), [forge-cli #932](https://github.com/Agenticstiger/forge-cli/pull/932), [forge-cli #936](https://github.com/Agenticstiger/forge-cli/pull/936), [forge-cli #938](https://github.com/Agenticstiger/forge-cli/pull/938), [forge-cli #939](https://github.com/Agenticstiger/forge-cli/pull/939), [forge-cli #950](https://github.com/Agenticstiger/forge-cli/pull/950))*

- **New, opt-in, 0.7.7 preview: Spark to Iceberg on AWS and the schema registry.** `fluid apply` starts a Spark build's run and keeps a streaming one running; a scheduled one runs through `fluid apply --mode amend-and-build --build-id <id>`, as every scheduled build does. There is no `fluid spark` command. A contract that uses none of the new fields is unaffected. `fluid plan` checks a consumed topic against its registry, and `fluid generate iac` registers a produced one, only where the contract names a registry. See [Spark to Iceberg on AWS](./advanced/spark-iceberg-aws.md), [Scheduled Spark builds](./advanced/airflow.md#scheduled-spark-builds), [Schema registry](./advanced/schema-registry.md) and [`fluid import schema-registry`](./cli/import.md#importing-a-schema-registry-subject).
- **A running Glue Avro stream restarts once** on the release that adds the pinned jars to its config hash. Plan and apply need the same `FLUID_SPARK_GLUE_JARS_URL`.

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))*

- **A `secretRef` is one grammar, `<scheme>://<locator>[#<field>][?version=<n>]`, and `fluid validate` refuses what does not follow it.** It also refuses a scheme the operator has not enabled, a locator outside the allowed prefixes and a connection host the allowlist does not cover, and its message names the setting that allows it. A contract that validated on 0.30.1 can fail now. A `secretRef` that may be a pasted secret (no `://`, or a URL with `user:password@`) is refused, and never printed. Run [`fluid secrets check`](./cli/secrets.md#fluid-secrets-check) on every contract before you upgrade a pipeline. See [What is refused](./cli/secrets.md#what-is-refused).
- **`file://` takes an absolute path, and `file://name` is gone.** The lookup in `~/.fluid/secrets/<name>` no longer exists. Write `file:///run/secrets/name`. The path has to sit under an allowed prefix, `/run/secrets/` by default, and a symlink is checked again. Mount the secret there, or add your directory to `FLUID_SECRET_PREFIXES`. See [Schemes](./cli/secrets.md#schemes).
- **`vault://` needs `#field`.** `vault://kv/orders/pg` is refused: name the key, as in `vault://kv/orders/pg#db_pass`. A reference reads KV v2 on OpenBao or Vault, with the address in `BAO_ADDR` or `VAULT_ADDR`. See [Vault and OpenBao](./cli/secrets.md#vault-and-openbao).
- **`aws://` is `aws-sm://`, and `gcp://` and `azure://` need a resolver pack.** `aws-sm://` needs the `[aws]` extra. `gcp-sm://` and `azure-kv://` resolve only when a pack for the scheme is installed and the operator lists the scheme in `FLUID_SECRET_SCHEMES`. On the default policy a `gcp-sm://` or `azure-kv://` reference is refused as `not enabled`, with a warning that no resolver is installed. Once the scheme is listed, `fluid validate` only warns, and `fluid apply` stops with the install hint. See [Schemes](./cli/secrets.md#schemes).
- **The destination policy covers every scheme, not only `env://`.** A value from `vault://`, `aws-sm://`, `file://` or a pack is sent to a host that leaves the machine only when `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST` allows it, with `<reference>@<host>`, `<reference>@*` or `<prefix>*@<host>`, beside the `NAME` and `NAME@host` entries that worked before. A pipeline that reads a non-`env` secret for a remote source now fails until you set it, in the shell or CI job that runs `fluid apply`. See [`FLUID_ACQUISITION_SECRET_REF_ALLOWLIST`](./cli/secrets.md#fluid-acquisition-secret-ref-allowlist).
- **The operator now decides which stores, which locators and which stages.** `FLUID_SECRET_SCHEMES` (default `env,file,vault,aws-sm`), `FLUID_SECRET_PREFIXES` (default: `file` under `/run/secrets/`) and `FLUID_SECRET_STAGES` (default `apply`) are read only from the real environment, and a project `.env` cannot set them. `validate`, `plan`, `bundle` and `diff` never fetch a value. A pipeline that needs a value in another stage has to list that stage. See [The operator's policy](./cli/secrets.md#the-operator-s-policy).
- **A Debezium `extra_config` may not set a host or credential key** (`database.hostname`, `mongodb.connection.string` and the like) when the connection has a `secretRef`. Name the host in the connection block. See [`FLUID_ACQUISITION_SECRET_REF_ALLOWLIST`](./cli/secrets.md#fluid-acquisition-secret-ref-allowlist).
- **`fluid_build.secrets.SecretManager` and `build_runners._secret_policy` are removed.** The `fluid_build.secrets` package replaces them, with no compatibility shim. Library code that imports either one moves to the package's `resolve_secret`. See [How a value is fetched](./cli/secrets.md#when-a-value-is-fetched).
- **The Fernet credential file store and plaintext credentials in `~/.fluidrc.yaml` are removed.** `~/.fluid/credentials.enc`, `FLUID_ENCRYPTION_KEY`, `FLUID_ENCRYPTION_PASSPHRASE`, `~/.fluid/.key` and the `fluid auth doctor` check of it are gone. Move each credential to the OS keyring, a secret store or the environment. See [Provider credentials from a store](./cli/secrets.md#provider-credentials-from-a-store).
- **The credential chain asks a secret store only when `FLUID_CREDENTIAL_STORE` names one.** Setting `GCP_PROJECT` or `AWS_REGION` no longer sends credential lookups to a cloud secret manager. To keep reading provider credentials from a store, set `FLUID_CREDENTIAL_STORE=vault://<mount>/<prefix>` or `aws-sm://<prefix>`, and store each credential at `<prefix>/<provider>#<key>`. See [Provider credentials from a store](./cli/secrets.md#provider-credentials-from-a-store).
- **New: `fluid secrets check`, the run-secrets file and the Vault JWT login.** `fluid secrets check <contract>` lints references and, with `--resolve`, proves they exist without reading a value. `FLUID_RUN_SECRETS_FILE` hands a run exactly the secrets it may use. `FLUID_VAULT_JWT_ROLE` logs a CI job in to OpenBao or Vault. Nothing changes until you use them. See [`fluid secrets check`](./cli/secrets.md#fluid-secrets-check), [The run-secrets file](./cli/secrets.md#the-run-secrets-file) and [JWT login for CI](./cli/secrets.md#jwt-login-for-ci).

## Changes in 0.32.0

These changes are in 0.32.0. Two change what a contract or a generated file looks like: read them before you upgrade a pipeline.

*(since 0.32.0, [forge-cli #952](https://github.com/Agenticstiger/forge-cli/pull/952))*

- **In the 0.7.7 preview, an `enum` level may hold any character, and an empty item or an unescaped quote is now refused.** A level is a quoted string with its own quote doubled, as SQL writes a string literal, so `enum('Dr.', '>10000', 'O''Brien', 'a, b')` is valid. An unquoted word list such as `enum(IE, United Kingdom)` reads as before. An empty item, such as `enum(a,,b)`, and a level with an unescaped quote, such as `enum('it's')`, now fail `fluid validate` on a contract that declares `fluidVersion: "0.7.7"`. Fix them before you upgrade. The schemas for 0.7.6 and earlier are unchanged.
- **The 0.7.7 schema file changed, and 0.7.1 to 0.7.6 keep their bytes.** If you copy schema files out of the package, copy 0.7.7 again.
- **Generated files stop carrying an enum's levels.** dbt model contracts and casts wrote `varchar('a','b')` for an enum column, and the ODCS `physicalType` wrote `VARCHAR('a','b')`. Each now gives the plain string type, and ODCS no longer reads `enum(10)` as a `maxLength` of 10. Regenerate what you commit and expect that one diff.

*(since 0.32.0, [forge-cli #953](https://github.com/Agenticstiger/forge-cli/pull/953))*

- **`fluid generate transformation` keeps contract values as data in the Glue, Dataflow and Spark job scripts.** A column name or type, the expose id, the contract name, a stage name or embedded SQL that held a quote, a line break or `"""` could end its place in the script and add a statement that runs with it. Each value is now written as a string literal, a one-line comment or an escaped block. Regenerate and review the diff: the string literals these scripts write now use single quotes, the Glue script's SQL summary comment is one line, and two stages whose names sanitise alike, such as `a-b` and `a.b`, get two functions, `stage_a_b` and `stage_a_b_2`, where the second used to replace the first.

*(since 0.32.0, [forge-cli #957](https://github.com/Agenticstiger/forge-cli/pull/957))*

- **New, opt-in: `fluid_build.testing`, a test kit for packages that plug into `fluid`.** It holds `run_fluid`, `isolated_env`, `installed_plugin` and `FakeHttpServer`, with no third-party imports, and nothing in the CLI imports it. Nothing changes until a plugin's tests use it. See [Test kit](./sdk-and-plugins/reference/testing-kit.md).

*(since 0.32.0, [forge-cli #959](https://github.com/Agenticstiger/forge-cli/pull/959))*

- **`fluid profile --bundle DIR` answers a Simulation's fidelity block.** The profile then carries the statistic each declared property is compared with, grouped means, histograms, supports and quantiles among them, so the engine scores every property but a correlation. Without `--bundle`, a profile holds what it held before. The `[profile]` extra needs flux-stats 0.6.2 or newer, which `pip install -U 'data-product-forge[profile]'` brings. See [Answering a fidelity block](./cli/profile.md#answering-a-fidelity-block-bundle).

## Changes in 0.33.0

These changes are in 0.33.0. Several change what a plan or a generated file does: read them before you upgrade a pipeline. A BigQuery decimal with a precision replaces its live table once, behind `--allow-data-loss`; a Snowflake column whose type changes needs its table migrated; a Glue table that declares `partitionBy` is replaced the first time it is partitioned; and a generated CI file changes only when you run `fluid generate ci` again.

*(since 0.33.0, [forge-cli #965](https://github.com/Agenticstiger/forge-cli/pull/965), [forge-cli #967](https://github.com/Agenticstiger/forge-cli/pull/967))*

- **`fluid profile --bundle` writes `C` for every withheld group and cell of a histogram or a quantile.** In 0.32.0 each kept the code of the check that withheld it, `A` for a small count, and a code that names the check tells a reader a range. Now `C` marks them all, whatever withheld them. The summary still counts each by its check, and a new line counts the histogram cells withheld inside groups that were published. Every other statistic keeps the code of its check. A profile you wrote before is unchanged and still reads. Profile again to get these checks, and pin the new digest. See [What leaves: the output checks](./cli/profile.md#what-leaves-the-output-checks).
- **A quantile is published only when at least 10 records lie below its value and at least 10 lie above it.** In 0.32.0 a quantile was published when 10 records held its value, so its ranks could show that fewer than 10 records lie below it or above it. No record below or above counts as a zero, which `acro-default` withholds, so a quantile at the smallest or the largest value of its records is withheld. A column's `quantiles` metric is checked as before. See [The checks on each group](./cli/profile.md#the-checks-on-each-group).
- **A quantile is published only as its column's one histogram or quantile.** A block that declares a median and a histogram of one column now gets the histogram and no median, and a block that declares two quantiles of one column gets neither. To keep a quantile, declare no other histogram or quantile on its column.
- **A group withheld for its size withholds its siblings in a grouped histogram or quantile.** When a group of a `groupBy` holds fewer than 10 records with a value in a column, every group of that column's histograms and quantiles by that `groupBy` is withheld too, as the groups of a grouped mean and a grouped support already were. The summary counts a sibling that passed its own checks as `D`.
- **The checks still leave one gap.** A reader can still subtract one histogram's published counts from another's, or from a level histogram's group size, and read a withheld cell, a zero included, to within the rounding. forge-cli plans to close that with FLUX's `check_edge_counts`, which a flux-stats release has to carry first, and to ship it in a later release. That would change what a bundle profile publishes again.

*(since 0.33.0, [forge-cli #978](https://github.com/Agenticstiger/forge-cli/pull/978))*

- **`fluid profile --help` and the profile page say what a published `min` or `max` leaves readable.** A published `min` shows that no record lies below it, and a published `max` that none lies above it. No check withholds a `min` or a `max` for that. A quantile whose value is the smallest or the largest of its records shows the same, and under `acro-default` it is withheld for that. Nothing the profiler writes changes. See [The checks on each group](./cli/profile.md#the-checks-on-each-group).

*(since 0.33.0, [forge-cli #966](https://github.com/Agenticstiger/forge-cli/pull/966))*

- **`fluid generate schedule` renders `builds[].dependencies` and dataset triggers.** Builds that `builds[].dependencies` link now run in one Airflow DAG, one `fluid apply --build-id` task per build, each after the builds it names, and a dependency's `condition` becomes the task's trigger rule. If you gave those builds cron triggers of their own to fake the order, keep one trigger and regenerate with `--overwrite`, which now removes the DAG files the contract no longer makes. Two different triggers in one linked group stop generation. See [Build graphs and dataset triggers](./advanced/airflow.md#build-graphs-and-dataset-triggers).
- **`dataset` and `schedule_and_dataset` builds get a DAG.** A `dataset` build runs when the datasets in `trigger.datasets` are updated (all of them, or any one with `datasetsOperator: any`), and `schedule_and_dataset` runs on its cron and on those updates. A task now declares the exposes its build writes as `outlets`, where an expose has an asset URI, so a regenerated one-build DAG gains an `Asset` import and an `outlets=` list when its build writes such an expose. The files need Airflow 2.6 or later (2.9 for `any` and `schedule_and_dataset`), or Airflow 3.
- **A contract whose only builds are streams that `fluid apply` keeps running** now gets `No build needs a DAG` from `fluid generate schedule`, where it used to get `No scheduler engine specified` (when the contract set no engine) or an error that the orchestration section has no task to render (with `orchestration.engine: airflow`). `fluid validate` warns about an Airflow task's `buildStepRef`, which no generated DAG runs: list the build in `builds[].dependencies` instead.

*(since 0.33.0, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972))*

- **The bundle packs the dbt project a build runs, and `fluid apply` refuses a checkout whose dbt files changed.** `fluid bundle --format tgz` packs each dbt build's project under `sources/dbt/<build id>/`: `dbt_project.yml`, the package and selector files, `.dbtignore` and the files under the `*-paths` directories, never `profiles.yml`, `target/`, `logs/` or `dbt_packages/`. It refuses what it cannot bind: a symbolic link, a model in a hidden or `__pycache__` directory, a path key outside the project or written as Jinja, and a file over 64 MiB. `fluid plan` records the files, and `fluid apply` compares the checkout with them before anything runs. The dbt runner compares again just before dbt starts. A changed, added or removed file, or a bundle made before this change that packs no project for a dbt build, fails with `apply_plan_digest_bundle_mismatch`. Run `fluid generate dbt-tests` before `fluid bundle`, install packages from `package-lock.yml` in the job that applies (installed packages are not bound), and plan and apply in the same checkout path. `--no-verify-plan-binding` skips the check and logs a warning. See [The dbt project of a dbt build](./cli/bundle.md#the-dbt-project-of-a-dbt-build) and [The dbt project](./cli/apply.md#the-dbt-project).

*(since 0.33.0, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))*

- **A bundle's bytes no longer depend on where it was written.** `fluid bundle --format tgz` used to record the source contract's path, relative to `--out`, in `MANIFEST.json`, so the same checkout bundled to two paths gave two archives with one digest. Those paths (`source.contract` and `source.overlay`) now go to `<bundle>.provenance.json` beside the archive. It names the archive's sha256 and is ignored when it names other bytes. `MANIFEST.json` keeps `source.env` and the overlay warnings. Copy the provenance file with the bundle, and keep the contract at the same relative path: without the file, relative paths anchor at the bundle's own directory, and a bundle that packs a dbt project is refused at apply. Paths inside an older bundle's MANIFEST are not read, so bundle again. See [The provenance file](./cli/bundle.md#the-provenance-file).
- **`fluid bundle` prints a packet digest, and a plan is bound to it.** The new `packet:` line is the sha256 of the `.tgz` file, and `digest:` stays the merkle digest of the resolved contract and its files. `fluid plan <bundle>` records the packet as `packetDigest`. `fluid apply` refuses a bundle with other bytes (`apply_plan_digest_packet_mismatch`) and a bound plan that records none (`apply_plan_digest_packet_missing`), so run `fluid plan` again on a plan made by 0.32.0 or earlier. See [The packet digest](./cli/bundle.md#the-packet-digest).
- **`fluid bundle --attest` names the bundle file as its subject.** The in-toto subject digest is the sha256 of the bundle file in bare hex, so `sha256sum bundle.tgz` matches it. It used to be the merkle root with a `sha256:` prefix. The merkle root, the packet digest and the checkout paths are in the statement's external parameters. A verifier that matched the old subject has to match the file's hash.

*(since 0.33.0, [forge-cli #979](https://github.com/Agenticstiger/forge-cli/pull/979))*

- **`fluid generate artifacts` writes each Spark build's `job.json`.** The new `spark` emit key is on by default, so a contract with a forge Spark build gets `spark/<build id>/job.json` and one more entry in the artifacts `MANIFEST.json`, and a generated Jenkinsfile lists `spark` in `GENERATE_EMIT`. A Spark build that the compiler refuses, or that the upload would refuse, now fails stage 3 with `generate_artifacts_failed` instead of waiting for `fluid apply`. The operator's rules for contract SQL and hosts are still enforced only by `fluid apply`. A contract with no Spark build is unchanged. See [Spark job configs](./cli/generate-artifacts.md#spark-job-configs).

*(since 0.33.0, [forge-cli #983](https://github.com/Agenticstiger/forge-cli/pull/983))*

- **A Spark job's role can look up the directories it is granted.** On 0.32.0 and earlier, a stream on AWS failed within minutes of starting, because S3 refused the lookup of its checkpoint directory with a 403. The role forge creates, and the policy for an EMR on EC2 cluster, now read each granted directory's own key and list it by its exact name. Run `fluid apply` to update the policy. A role you name with `executionRoleArn` is yours, and needs the same two permissions. See [What the job's role may do in S3](./advanced/spark-iceberg-aws.md#what-the-job-s-role-may-do-in-s3).

*(since 0.33.0, [forge-cli #984](https://github.com/Agenticstiger/forge-cli/pull/984))*

- **Each EMR runtime takes its own `releaseLabel` form.** `emr-serverless` and `emr-ec2` keep the plain `emr-7.12.0`. `emr-eks` takes `emr-X.Y.Z-latest` or a dated `emr-X.Y.Z-YYYYMMDD`, with an optional variant such as `emr-7.12.0-java11-latest`, and `fluid validate` now refuses the plain form there. An `emr-eks` build with no `releaseLabel` runs on `emr-7.12.0-latest`, so its config hash changes: run `fluid plan` again. The config hash of an `emr-serverless` or `emr-ec2` build does not change. Change an `emr-eks` build that names `emr-7.12.0` to `emr-7.12.0-latest` when you upgrade: 0.32.0 and earlier refuse that label. See [Release labels](./advanced/spark-iceberg-aws.md#release-labels).

*(since 0.33.0, [forge-cli #990](https://github.com/Agenticstiger/forge-cli/pull/990))*

- **`fluid validate` stops warning about SQL the operator listed.** The warning that a build's own `properties.sql` runs only if the operator lists it was printed for every Spark and managed Flink build with SQL, whatever `FLUID_SPARK_CONTRACT_SQL_ALLOWLIST` or `FLUID_FLINK_CONTRACT_SQL_ALLOWLIST` held, so `fluid validate --strict` failed such a build even after the list named it. Validate now reads the list, under the same environment as `fluid apply`, and warns only while apply would refuse the build. An entry that pins other SQL gets a warning that says the SQL changed after review. A build listed by product, by build or with the digest of its SQL is quiet, so `--strict` passes when nothing else warns. Export the variable in the job that runs `fluid validate` as well as in the one that runs `fluid apply`: a validate job without it keeps the warning, and a pipeline whose stage 2 is `fluid validate --strict` fails on it. See [Contract SQL and `fluid validate`](./advanced/spark-iceberg-aws.md#contract-sql-and-fluid-validate).

*(since 0.33.0, [forge-cli #994](https://github.com/Agenticstiger/forge-cli/pull/994))*

- **`fluid plan` and `fluid apply` warn when an EMR on EC2 cluster can lose a Spark build to Spot.** For the cluster of each `emr-ec2` build they read its instance groups or fleets once, with the default AWS credential chain, and warn, never refuse, when the primary node runs on Spot, when core nodes run on Spot, or when core or task nodes run on Spot and the `yarn-site` does not keep YARN application masters on On-Demand nodes. Each warning names its fix. A cluster they cannot read prints nothing, `fluid apply --dry-run` reads nothing, and `plan.json` does not change. Give the role that runs plan and apply, and the scheduler's role for a scheduled build, `elasticmapreduce:DescribeCluster`, `ListInstanceGroups` and `ListInstanceFleets` on the cluster, or the check stays silent. See [What plan and apply check on the cluster](./advanced/spark-iceberg-aws.md#what-plan-and-apply-check-on-the-cluster).

*(since 0.33.0, [forge-cli #973](https://github.com/Agenticstiger/forge-cli/pull/973), [forge-cli #968](https://github.com/Agenticstiger/forge-cli/pull/968))*

- **A BigQuery table is partitioned and clustered as its binding declares, and a layout BigQuery cannot honour is refused.** `binding.location.partitionBy` and `binding.properties.cluster_by` were dropped without a word, and `fluid validate --strict` passed. Run `fluid validate` on each BigQuery contract with the new CLI: the old one passed them. A `partitionBy` with more than one column or a non-time column, a `cluster_by` with more than four columns or a column BigQuery cannot cluster by, and either key on a view now fail, naming the field. BigQuery cannot partition an existing table, so a live table whose contract already declared `partitionBy` without retention plans a replacement, which `fluid apply` refuses without `--allow-data-loss`. See [Partitioning and clustering](./providers/gcp.md#partitioning-and-clustering).
- **New: a 0.7.7 column that declares its `element`, `fields`, or `key` and `value` is written to BigQuery as REPEATED and RECORD fields.** A nullable array, a nullable element and a map are written but warn, so `--strict` fails on them. Nothing changes for a contract that declares no nested column. See [Nested columns](./providers/gcp.md#nested-columns).

*(since 0.33.0, [forge-cli #971](https://github.com/Agenticstiger/forge-cli/pull/971), [forge-cli #980](https://github.com/Agenticstiger/forge-cli/pull/980))*

- **`fluid ship` generates artifacts for a reference-only contract, and its report changes shape.** Stage 3 used to skip a contract with a `hybrid-reference`, `reference` or `external-reference` build, and the run exited 0 with no `MANIFEST.json`. It now runs, and stage 4 fails where it used to skip when stage 3 was to write `dist/artifacts/` and did not. In `ship-report.json`, `"schema"` is `fluid-ship-report/2`, a stage's `skipped` status is now `skipped-by-policy`, `unsupported` or `not-run`, and an interrupted stage is `unknown`, and `skip_reason` and `failure_reason` are one `reason`. A script that reads the report should read the new statuses; a version 1 record still merges. See [Reports](./cli/ship.md#reports).
- **New, opt-in: `fluid ship --require-artifacts KEYS` and `--release-dir DIR`.** The first fails the run unless stage 3 writes what it promised. The second publishes a run's bundle, artifacts, plan and reports as a release directory once every stage it ran passed. Nothing changes until you pass them. See [Requiring artifacts](./cli/ship.md#requiring-artifacts) and [Publishing a release](./cli/ship.md#publishing-a-release).

*(since 0.33.0, [forge-cli #970](https://github.com/Agenticstiger/forge-cli/pull/970))*

- **The ODCS export of a 0.7.7 contract writes its declared invariants as executable quality rules.** A contract with `invariants`, `identifierFormat`, `placeholders`, `sharedColumns` or `sharedAttribute` now has more `quality` entries, on the schema object and on the property, each marked `fluidGenerated`. Where a column declares placeholders, its existing enum and regex rules change: the placeholders join an enum's `validValues` and extend the pattern. Re-export and re-publish a contract a catalog or a quality engine reads. A contract that declares none of them exports as before. See [Declared invariants as quality rules](./cli/odcs.md#declared-invariants-as-quality-rules).

*(since 0.33.0, [forge-cli #969](https://github.com/Agenticstiger/forge-cli/pull/969), [forge-cli #981](https://github.com/Agenticstiger/forge-cli/pull/981))*

- **New, opt-in: `fluid validate --diagnostics` and `--format sarif`, and `fluid diff --baseline --impact` with `--plan`.** The first puts each finding at the file, line and column that wrote it, and writes a SARIF 2.1.0 log for code scanning. The second adds an impact report to the version diff for a pull request. Without the flags, the output of both commands is unchanged. See [Findings at the line that wrote them](./cli/validate.md#findings-at-the-line-that-wrote-them) and [Impact report for a pull request](./cli/diff.md#impact-report-for-a-pull-request).

*(since 0.33.0, [forge-cli #986](https://github.com/Agenticstiger/forge-cli/pull/986))*

- **New, opt-in: `fluid verify --require-every-port`.** `--strict` fails a run that verified nothing, so a run that verified one port passed while the others were skipped. With the flag, each skipped expose fails the run and is named with the reason. Nothing changes until you pass it. See [Requiring every port](./cli/verify.md#requiring-every-port).
- **`fluid ship --release-dir` passes it to stage 9.** A release run now fails at stage 9, and publishes nothing, when an expose was skipped (no verifier for its binding, or a reference-only table that is not built yet), when an entry has no id or repeats one, or when the contract declares no expose. `--skip-stage verify` takes stage 9 out of the run. See [Publishing a release](./cli/ship.md#publishing-a-release).

*(since 0.33.0, [forge-cli #991](https://github.com/Agenticstiger/forge-cli/pull/991))*

- **`fluid generate dbt-tests` writes a `fluid_rule` test for each declared rule, and a macro.** On a 0.7.7 contract, each invariant, identifier format, bounded placeholder declaration, shared column and shared attribute becomes a model-level test, and `fluid_rule.sql` goes to `<project>/<first macro-paths entry>/fluid/`. The command now fails with `dbt_tests_no_macro_dir` when the contract declares such rules and no `dbt_project.yml` is above `--out`: write `--out` inside the project, or pass the new `--macros-dir`. It never overwrites a macro file it did not write. A column's placeholders are also exempt from its `accepted_values` and range tests. A contract that declares none of these generates what it did before. See [Declared rules as dbt tests](./cli/generate.md#declared-rules-as-dbt-tests).
- **A `schema.yml` no longer carries contract text that dbt would run as Jinja.** A column name, description, enum value or test argument that holds `{{`, `{%` or `{#`, or looks like a call to `env_var`, `var`, `source` or `doc`, or to `ref` with anything but a plain model name, is written as a literal of itself. Run `fluid generate dbt-tests` again to rewrite a file made before. Any other string is written as before.

*(since 0.33.0, [forge-cli #987](https://github.com/Agenticstiger/forge-cli/pull/987))*

- **The GitLab pipeline from `fluid generate ci --system gitlab` has a Run pipeline form and hands `fluid-apply` a release packet.** The file starts with `spec:inputs` (GitLab 17.11 or later): the 11 stage switches and nine knobs, 20 inputs in all, each closed by options or a pattern. On the default branch `fluid-plan` runs `fluid ship --stage 1-6 --release-dir release`, and `fluid-apply` uses only that job's artifacts and stops without `release/release.json`. A merge request plans without a packet and gets a `fluid-impact` job instead of an apply. A failed `fluid-plan` keeps its reports and removes its bundle, plan and artifacts. The pipeline runs `--release-dir` and `fluid diff --impact`, which 0.32.0 lacks: with a `FLUID_PACKAGE_SPEC` that installs 0.32.0 or older, the default-branch `fluid-plan` fails and a merge request's `fluid-impact` fails without blocking the merge. A file written by 0.32.0 or older has no form and none of this; run `fluid generate ci --system gitlab` again to get it. See [GitLab CI: form, release packet and impact report](./advanced/operating-in-ci.md#gitlab-ci-form-release-packet-and-impact-report).

*(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))*

- **A saved OpenTofu plan is bound to its target and applies on another runner.** `fluid plan --tofu` now records the cloud account and region (AWS), the project and region (GCP), the organization and account (Snowflake) or the host (Databricks), plus the state backend, the `tofu` version and the provider versions, and prints `target: ...`. `fluid apply plan.json` reads them again after `tofu init` and before it applies or changes anything, the state-key migration and hooks included, and refuses another target, an unreadable recorded field, another `tofu` or provider version, another backend, or a plan with no target. With a state backend that both runners reach, a plan made on one runner applies on another, at another checkout path. A plan made against existing local state that the applying runner does not have is refused as `apply_plan_digest_tofu_plan_state_missing`. See [The target a plan is bound to](./cli/plan.md#the-target-a-plan-is-bound-to).
- **The provider lock travels with the plan.** When `tofu init` wrote one, `fluid plan --tofu` writes `<stem>.terraform.lock.hcl` next to `plan.json` and binds its sha256. Pass it on with the plan: `fluid apply` installs it before `tofu init`, and refuses a missing or changed one.
- **A plan saved by 0.32.0 or earlier records no target.** `fluid apply` in 0.33.0 refuses it with `apply_plan_digest_tofu_plan_target_missing`: run `fluid plan --tofu` again. Reading the AWS account needs `boto3` (`pip install 'data-product-forge[aws]'`) on both runners.

*(since 0.33.0, [forge-cli #997](https://github.com/Agenticstiger/forge-cli/pull/997))*

- **New: `fluid generate dbt-tests --coverage`, `--coverage-out`, `--require-rule`, `--require-all-rules` and `--adapter`.** `--coverage` prints which declared rules each engine can run, and the reason where one cannot, and `--coverage-out` writes the report as JSON. `--require-rule ID` (repeatable) and `--require-all-rules` fail the command, before it writes any test, when a selected adapter cannot run a required rule, when a rule named by `--require-rule` has nothing to test, and when the contract declares rules below 0.7.7. `--adapter TYPE` selects the adapters, by default one for each platform the exposes bind to (never `spark` or `trino`). See [Which engines run each rule](./cli/generate.md#which-engines-run-each-rule).
- **A Databricks dbt job tests the declared rules too.** `fluid apply` adds each declared rule that has a bound, on an expose the build writes, to the uploaded project as a singular test, `<test path>/fluid_dq/<model>/fluid_dq_<id>.sql`, and the run report names it. A rule with no exact Databricks SQL, or one that reads an expose the build does not write, is refused when the build is planned, and so is a declared rule on a build whose `repository` is a Git URL. A contract that declares such a rule and builds a Databricks dbt job now fails at plan, where 0.32.0 ignored the rule. See [Declared rules about valid data](./providers/databricks.md#declared-rules-about-valid-data).

*(since 0.33.0, [forge-cli #1002](https://github.com/Agenticstiger/forge-cli/pull/1002))*

- **A saved-plan target field that was not bound is logged when the plan is applied, and a provider with no target reader is named.** The WARNING `apply_tofu_plan_target_field_unbound` names the provider, the field and the reason. A provider that forge reads no target for (`confluent`, a plugin installed through an entry point) is named at plan and at apply, as `plan_tofu_target_provider_unbound` and `apply_tofu_plan_target_provider_unbound`.
- **The AWS region falls back to the profile's, and the profile is chosen in the order the AWS provider's SDK reads them.** A region set only in the named profile's shared config binds. The profile is `AWS_PROFILE`, else `AWS_DEFAULT_PROFILE`, in the order the AWS provider's SDK reads them. See [The target a plan is bound to](./cli/plan.md#the-target-a-plan-is-bound-to).

*(since 0.33.0, [forge-cli #993](https://github.com/Agenticstiger/forge-cli/pull/993))*

- **`fluid policy apply` grants a Lakekeeper table in Lakekeeper.** An Iceberg expose whose `binding.location.catalog` is `lakekeeper` used to compile to a warning that said to enforce access in Lakekeeper itself, and stage 8 granted nothing there. `fluid policy compile` now writes one `provider: lakekeeper` binding for each principal that has access to the table, from `accessPolicy.grants`, the deprecated `metadata.policies` and the expose's `policy.authz.readers` and `writers`. `fluid policy apply --mode enforce` grants them in Lakekeeper, and revokes any other direct `describe`, `select` or `modify` grant on that table, whoever added it. Ownership and the right to grant are never touched. `--mode check` reads the grants and plans, and changes nothing: run it on a contract with a Lakekeeper table and read the revokes before you enforce. A table its writer has not created yet is reported and left for a later run, and a principal that Lakekeeper does not know leaves its table's grants as they are. See [Lakekeeper tables](./cli/policy-apply.md#lakekeeper-tables) and [`fluid policy compile`](./cli/policy-compile.md#lakekeeper-tables).
- **Stage 8 needs the operator's Lakekeeper settings, or a pipeline that grants nothing today fails.** By default `fluid ship` runs `fluid policy-apply --mode enforce`, which exits `1` on a Lakekeeper table when no credential is configured or the namespace is not allowed, where it used to exit `0` with a warning. After a dry-run apply, or with `--policy-mode check`, it runs `--mode check` instead. That exits `0` when no credential is configured, and reports the tables as not checked. It still exits `1` for a namespace that is not allowed or for any table it cannot check. Export `FLUID_LAKEKEEPER_CREDENTIAL_REF` with `FLUID_LAKEKEEPER_OAUTH2_SERVER_URI` and `FLUID_LAKEKEEPER_SCOPE`, or `FLUID_LAKEKEEPER_TOKEN_REF`, and `FLUID_LAKEKEEPER_NAMESPACE_ALLOWLIST` in the job that runs stage 8, or take the stage out with `--skip-stage policy-apply`. A project `.env` cannot set these names. The credential's reference has to be allowed for the catalog's host in `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST`, and `binding.location.uri` and the token endpoint have to be `https://` URLs. See [The operator's settings](./cli/policy-apply.md#the-operator-s-settings).

*(since 0.33.0, [forge-cli #1000](https://github.com/Agenticstiger/forge-cli/pull/1000))*

- **`fluid generate ci` runs stage 3 for a contract with reference builds.** Through 0.32.0 it switched `RUN_STAGE_3_GENERATE_ARTIFACTS` off by default when any build was `hybrid-reference`, `reference` or `external-reference`, so stage 4 had nothing to check and stages 8 and 11 ran without the policy bindings and schedule that stage 3 writes. Only `--no-generate-artifacts` turns it off now. A file generated by 0.32.0 keeps the old default until you generate it again.
- **`--install-mode dev-source` puts `fluid` on `PATH`.** On GitHub Actions, GitLab CI, Azure DevOps, Bitbucket, CircleCI and Tekton the install step ran `export PYTHONPATH=/forge-cli-src`, which ended with the step and never provided the command, so the install step failed at `fluid --version` with `command not found`, and no `fluid ship` step ran. It now runs `pip install -e /forge-cli-src`, and a missing checkout or a failed install stops the job with a `FATAL` line. Jenkins is unchanged.
- **Generated pipelines pin their container images by digest, and `fluid generate ci --system tekton --image IMAGE` sets the Task image.** Tekton, GitLab, Bitbucket and CircleCI named `python:3.12-slim` and `cimg/python:3.12` by tag (and, on `main`, `python:3.12` for the GitLab `fluid-impact` job). See [Container images](./advanced/operating-in-ci.md#container-images).

*(since 0.33.0, [forge-cli #988](https://github.com/Agenticstiger/forge-cli/pull/988))*

- **A BigQuery `decimal(p,s)` is written as `NUMERIC(p,s)`, or `BIGNUMERIC(p,s)` where only that holds the range, and the first plan replaces each live table that declares one.** In 0.32.0 it was a bare `NUMERIC`, which is `NUMERIC(38,9)`, while dbt wrote `numeric(p,s)`. BigQuery cannot give an existing `NUMERIC` column a precision, so the first plan after the upgrade replaces each live table with a parameterised decimal, once, and `fluid apply` refuses it without `--allow-data-loss`. Declare the column `decimal` to keep the table as it is. Each contract with a BigQuery table gains one `terraform_data` resource, so that plan adds one resource. See [Decimal precision and scale](./providers/gcp.md#decimal-precision-and-scale).
- **A decimal's arguments are a precision and scale its engine holds, or the column is refused (on BigQuery, a decimal wider than a `BIGNUMERIC` is written as `BIGNUMERIC` with a warning).** `decimal(1;drop table x)` went into the Snowflake DDL as `NUMBER(1;drop table x)`, and `decimal(40,20)` became a `NUMBER` that Snowflake rejects at apply. The arguments are digits, a precision of at least 1 and a scale no larger, within the limits of Snowflake NUMBER (precision to 38, scale to 37), Databricks DECIMAL (precision to 38) and BigQuery. `fluid validate` refuses the rest on Snowflake, as on Databricks and BigQuery, and `fluid generate iac` refuses it.
- **The dbt engine and the IaC emitters type a column alike on BigQuery and Snowflake.** A dbt model builds into the table `fluid apply` creates, and the two wrote many types differently. On Snowflake `smallint`, `money`, `json`, `geography`, `timestamp_ntz`, `timestamptz` and `timestamp_ltz` were `VARCHAR`; they are now typed from one table. A Snowflake table applied before keeps its types, and Snowflake cannot change a live column to another type, so migrate the table of a column whose type changes. See [Column types](./providers/snowflake.md#column-types).

*(since 0.33.0, [forge-cli #992](https://github.com/Agenticstiger/forge-cli/pull/992))*

- **New: `fluid doctor --contract`, `--operation`, `--live`, `--provider`, `--state-backend` and `--compare`.** A preflight that says whether an operation can run here, offline by default: each capability is `exact`, `lossy`, `unsupported` or `requires-live-proof`, and the exit code is `1` when one is `unsupported`. `--live` adds read-only identity and state-backend checks. `fluid doctor --env` alone still lists the runtime switches. See [`fluid doctor --contract`](./cli/doctor.md#contract-can-this-operation-run-here).

*(since 0.33.0, [forge-cli #1004](https://github.com/Agenticstiger/forge-cli/pull/1004))*

- **A project `.env` can no longer set a name that is not a shell identifier, a `BASH_FUNC_` name, or `BASH_XTRACEFD`, `ZDOTDIR`, `FPATH`, `NULLCMD` or `READNULLCMD`.** Bash reads `BASH_FUNC_<name>%%` as the function `<name>`, so a project file could replace a command, or `exec`, in a bash script the CLI starts, such as Debezium Server's `run.sh`, with your credentials in scope. The names go with the shell start-up settings that were already refused. A name has to be letters, digits and underscores, and not start with a digit: a key such as `my.setting`, `A-B` or `1ABC` in `.env`, `.env.<environment>` or `.env.local` is now ignored too. `fluid` names each ignored variable and file with the usual warning, and never a value. Search the project's dotenv files for such a key, and set what you need in the shell or the CI job. See [What a project's `.env` may set](./advanced/project-dotenv-trust.md).

*(since 0.33.0, [forge-cli #996](https://github.com/Agenticstiger/forge-cli/pull/996))*

- **A Glue table is partitioned as `binding.location.partitionBy` declares.** Through 0.32.0 `partitionBy` and `binding.properties.cluster_by` never reached the Glue table, and both passed `fluid validate --strict`. On a Hive table the `partitionBy` columns become `partition_keys`, with Athena partition projection when the contract gives every key's values. A live table whose keys or projection change, or that is partitioned for the first time, is replaced, and `fluid apply` refuses that without `--allow-data-loss`. `partitionBy` on an Iceberg or Delta table in Glue and `cluster_by` on any Glue table are now refused at `fluid validate`, so a contract that set either fails it. See [Partitioned Glue tables](./providers/aws.md#partitioned-glue-tables).

*(since 0.33.0, [forge-cli #1001](https://github.com/Agenticstiger/forge-cli/pull/1001))*

- **The dbt engine writes no contract text into `schema.yml`, `sources.yml` or `semantic_models.yml` as Jinja.** A name, description or value that holds `{{`, `{%` or `{#`, or looks like an `env_var(...)` or `ref(...)` call, ran when dbt parsed a project generated by 0.32.0. It is now written as a literal of itself, as `fluid generate dbt-tests` writes it. A model, source or table name or a version that holds a quote, a backslash, a brace or a control character is refused when the project is generated. An `accepted_values` test with a quote or backslash in a value is written with `quote: false` and each adapter's SQL literal. The SQL of the models is not escaped: it is dbt Jinja, and only its `{{ env.X }}` placeholders are rewritten. See [Contract text in a generated dbt project](./cli/generate.md#contract-text-in-a-generated-dbt-project).

*(since 0.33.0, [forge-cli #1005](https://github.com/Agenticstiger/forge-cli/pull/1005))*

- **`fluid apply` starts no EMR on EC2 step until the build's policy is attached to the cluster's instance-profile role.** A step runs as that role, which the cluster's owner holds, and forge creates the build's least-privilege policy for the owner to attach. The first apply of a stream used to start it before anyone could, so, unless the role already held the job's permissions, the step failed at once and was not started again with the same config. Now the apply refuses, names the policy and prints the `aws iam attach-role-policy` command, and ends with exit code `1`. Nothing was started, so the apply after the attach starts the stream. When forge cannot read the cluster's role, or the build names its own `executionRoleArn`, the step starts as before. Give the identity that runs `fluid apply`, and a scheduler's role, `elasticmapreduce:DescribeCluster`, `iam:GetInstanceProfile` and `iam:ListAttachedRolePolicies`: the generated `fluid-<product>-spark-caller` policy, which a scheduled build's scheduler attaches, now carries them. See [An EMR on EC2 step starts once its policy is attached](./advanced/spark-iceberg-aws.md#an-emr-on-ec2-step-starts-once-its-policy-is-attached).

*(since 0.33.0, [forge-cli #975](https://github.com/Agenticstiger/forge-cli/pull/975))*

- **A Spark build can run on the machine `fluid apply` runs on: `parameters.spark.runtime: local`.** `fluid apply` writes the build's job config and the runner under a root of its own, and starts `spark-submit` on that machine, on a laptop or a lab host. The output is a table in an Iceberg REST catalog on `platform: local`. The operator sets which `spark-submit` runs (`FLUID_SPARK_SUBMIT_EXECUTABLE`), the Spark properties file that declares the catalog (`FLUID_SPARK_SUBMIT_PROPERTIES_FILE`), the artifact root (`FLUID_SPARK_LOCAL_ROOT`) and the namespaces a local run may write (`FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST`). A project `.env` cannot set them, and an unset list of namespaces allows none. Nothing changes for a contract with no `runtime: local` build. See [Running a build on this machine](./advanced/spark-iceberg-aws.md#running-a-build-on-this-machine).
- **Each Spark stream that runs on AWS restarts once on its next `fluid apply`.** The runner file changed, and a build's config hash covers the runner's sha256, so every Spark stream gets a new hash: apply stops the running job and starts it again on the same checkpoint. A build that runs to completion is not restarted. See [Starting and reconciling runs](./advanced/spark-iceberg-aws.md#starting-and-reconciling-runs).
- **A Spark stream can send the records it cannot land to dead letters: `properties.stream.deadLetter` (0.7.7 preview).** A record whose value or key is not the declared JSON, or that lacks a required field, goes to a table beside the output (`<table>__dead_letter` by default) or to a Kafka topic, and the stream keeps running until more than `maxRecordsBeforeAbort` dead letters (10000 by default) have gone out since the job started. It then stops after the batch that crossed the limit, and `fluid apply` starts it again only when the build changes. A topic is written only once the operator lists it in `FLUID_SPARK_TARGET_ALLOWLIST`, as `msk-write:<cluster ARN>/<topic>` or `kafka-write:<host:port>/<topic>`, on every runtime. An Avro stream, the managed Flink lane, and a table beside a bucket-root output, a location forge registers with Lake Formation or an output whose lifecycle expires its objects are refused. A stream with no `deadLetter` block keeps its job config, and restarts once with the new runner, as the entry above says. See [Dead letters](./advanced/spark-iceberg-aws.md#dead-letters).
- **A project `.env` can no longer set a name that starts with `SPARK_`, `PYSPARK_`, `HADOOP_` or `YARN_`.** `spark-submit` reads these to choose the program, the JVM options, the Python and the cluster it uses. The names are ignored, in any letter case, with the usual warning. Set what you need in the shell or the CI job. See [What a project's `.env` may set](./advanced/project-dotenv-trust.md).

*(since 0.33.0, [forge-cli #1003](https://github.com/Agenticstiger/forge-cli/pull/1003))*

- **New, opt-in: `fluid ship --journal-dir` keeps a stage journal, and every `--release-dir` run keeps one.** Each stage writes a `started` event before it runs and a `finished` event after, with its status and the digests of what it wrote. Before an `apply` that is not a dry run, an enforcing `policy-apply`, `publish` or a `schedule-sync` that is not a dry run, ship refuses the stage when an earlier attempt of it, or of `apply`, has no known outcome, until you inspect the target and pass `--acknowledge-inspected STAGE`. An `apply` that did not pass is refused until stage 6 has planned again. `--explain` shows what the journal would refuse. Without either flag no journal is kept and no stage is refused, and the run report records a stage killed by a signal (exit 129 to 159) as `unknown` instead of `failed`. See [The stage journal](./cli/ship.md#the-stage-journal).

*(since 0.33.0, [forge-cli #982](https://github.com/Agenticstiger/forge-cli/pull/982))*

- **An empty `connection.host` with a `secretRef` is refused.** A source whose `host` is empty or `null`, or whose `{{ env.NAME }}` placeholder renders empty because the variable is not set where `fluid apply` runs, used to pass the destination check, and the database client then picked a host itself (libpq reads `PGHOST`). `fluid validate` and `fluid apply` now stop with `connection.host is empty`. An empty `uri`, `server`, `endpoint`, `instance_url` or `connection_string` passed in the same way, and now stops as `a host that could not be determined` unless the connection names another destination. Name the host, or have the operator allow the reference for any host. The DuckDB runner also hides `PGHOST` and `PGHOSTADDR` while it attaches a Postgres source, so a connection with no host reaches only libpq's default local socket. See [A placeholder or an empty host](./cli/secrets.md#a-placeholder-or-an-empty-host).
- **A placeholder host is a `fluid validate` warning, not an error.** `fluid validate` and `fluid secrets check` no longer judge the text of `host: "{{ env.PGHOST }}"`. They warn that only `fluid apply` knows the host, and `fluid apply` judges the host it renders to. Remove any `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST` entry written as `NAME@{{ env.PGHOST }}`: it matches nothing, and `NAME@<rendered host>` is the entry that counts. `fluid validate --strict` fails on the warning unless the reference is allowed for any host.
- **A project `.env`'s Vault token no longer replaces yours.** `BAO_TOKEN` is read first, so a project file that set it was used in place of your exported `VAULT_TOKEN` or your `~/.vault-token`, to read your own store. A project's `BAO_TOKEN` or `VAULT_TOKEN` now loads only while you have no token of your own, and the CLI warns when a project's token would otherwise have been read in its place. If a pipeline relied on a project token over yours, export that token in the shell or the CI job. See [Which token is used](./cli/secrets.md#which-token-is-used).
- **Secret refusals read `<reference> cannot resolve, because ...` and `<reference> was not fetched, because ...`.** They had a colon after the reference, and the log redactor reads a colon after a credential-shaped word as an assignment and masks the word after it: a reference that ended in `#password` came out as `vault://kv/orders/pg#password: ***REDACTED*** vault:// scheme is not enabled`. A CI job or an alert that matches the old wording can match `is not enabled`, `outside the prefixes`, `never fetches a secret value` or `may not fetch secret values`, which are in both. See [What is refused](./cli/secrets.md#what-is-refused).

## Changes in 0.34.0

These changes are in 0.34.0.

*(since 0.34.0, [forge-cli #1008](https://github.com/Agenticstiger/forge-cli/pull/1008))*

- **`fluid apply` stops a removed Spark build's runs on AWS before it destroys what they run with.** When a plan deletes a build's resources, because the build left the contract or the product went, the apply cancels the build's active runs and waits for them (`FLUID_SPARK_WAIT_SECONDS`, 900 seconds by default), and empties and stops the product's own EMR Serverless application. It refuses first, with the `aws iam detach-*-policy` commands, when an IAM policy that the plan destroys is still attached, and a run that is still going after the wait refuses the apply before anything is destroyed. `--dry-run` says what it would cancel. The first apply after the upgrade adds three tags, `fluid_runtime`, `fluid_run_target` and `fluid_run_region`, in place to each Spark build's log group and to an EMR on EC2 build's job policy. The identity that runs `fluid apply` needs `iam:ListEntitiesForPolicy`, the list, get and cancel actions of the runtime that a removed build ran on, and, for the product's own application, `emr-serverless:GetApplication` and `emr-serverless:StopApplication` besides the EMR Serverless list, get and cancel actions. See [When a build leaves the contract](./advanced/spark-iceberg-aws.md#when-a-build-leaves-the-contract).

*(since 0.34.0, [forge-cli #1007](https://github.com/Agenticstiger/forge-cli/pull/1007))*

- **Removing a Spark build on AWS needs no `--allow-data-loss`, unless the build has a dead-letter table.** The data-loss gate counted what a removed build ran with (its runner and job config objects, role and policies, log group and the key its logs are encrypted with, Glue job and connection, and the product's own EMR Serverless application) as data, so a plan that drops a build was refused unless the apply was allowed to destroy data, and that allowance also let a real data loss in the same plan through. They are now listed as removed and not gated. An output table, a bucket and a bucket's own key still count, and so does a stream's dead-letter table (`sink: table`), which goes with the build, so a plan that removes one of them needs the flag as before. A pipeline that passes it only to remove a build that has no dead-letter table no longer needs to. See [When a build leaves the contract](./advanced/spark-iceberg-aws.md#when-a-build-leaves-the-contract).

*(since 0.34.0, [forge-cli #1015](https://github.com/Agenticstiger/forge-cli/pull/1015))*

- **A Spark stream can bound what one batch reads: `properties.stream.maxOffsetsPerTrigger` (0.7.7 preview).** A whole number from 1 to 9223372036854775807, passed to Spark's Kafka source, so a stream that catches up after a stop, or starts from `earliest`, lands in batches of bounded size, `trigger.availableNow` runs included. Unset, a batch reads everything that is waiting and the job config has no key. Managed Flink refuses the key. Setting it changes the job config, so a running stream restarts once on its next apply. See [Bounding a batch](./advanced/spark-iceberg-aws.md#bounding-a-batch).
- **Dead letters sent to a topic are keyed by where they came from.** The key was the record's own key. It is `<topic>-<partition>@<offset>` now, and the record's own key is in the header `fluid.dead-letter.raw-key`, null for a record without a key and for a build that masks fields. A consumer that reads the key reads the header instead. A batch sent again after a failure carries the same keys, so a consumer drops repeats by key. Table dead letters are unchanged. See [The topic](./advanced/spark-iceberg-aws.md#the-topic).
- **The runner sets `failOnDataLoss` to `true` on every Kafka source.** That is Spark's default, so a stream whose offsets the topic no longer holds fails, as before, and does not skip records.
- **Each running Spark stream restarts once on its next apply, on its checkpoint.** The runner changed, and its sha256 is part of the config hash, so the hash of a build whose contract did not change is another one.

*(since 0.34.0, [forge-cli #1014](https://github.com/Agenticstiger/forge-cli/pull/1014), [forge-cli #1019](https://github.com/Agenticstiger/forge-cli/pull/1019))*

- **A Spark run starts only on the job config that `fluid apply` compiled.** Every runtime, local included, passes the config's digest at submit (`--fluid-job-sha256`), and forge's runner refuses any other config before it reads anything. On AWS, `fluid apply` first reads the job config and the runner back from S3, and starts nothing unless they are the ones this apply compiled: the build fails with `or its runner is not the one this apply compiled`, and `fluid apply` ends with exit code `1`. A running job of another config is not cancelled, and keeps going: run `fluid apply` again, and it uploads both and starts the run. The identity that runs `fluid apply` needs `s3:GetObject` on both objects, and `kms:Decrypt` where the bucket encrypts them with a KMS key (the scheduler's `fluid-<product>-spark-caller` policy holds both). Write access to the artifact bucket stays the boundary. The runner changed, so each running Spark stream restarts once on its next apply, on its checkpoint. See [A run starts only on the config this apply compiled](./advanced/spark-iceberg-aws.md#a-run-starts-only-on-the-config-this-apply-compiled).

*(since 0.34.0, [forge-cli #1009](https://github.com/Agenticstiger/forge-cli/pull/1009))*

- **`fluid apply` runs a dbt or Python build whatever its trigger.** A dbt or Python build of type `dataset`, `schedule_and_dataset`, `event`, `dependency` or `timetable` failed under `fluid apply` with `Unknown trigger type`. That included the task of the DAG that `fluid generate schedule` renders for a `dataset` or `schedule_and_dataset` build (`fluid apply --build-id`). The dbt and Python runners now run such a build once. `manual` keeps its iterations, `continuous` is still refused, and a `trigger.type` that is none of the names the schema knows is refused. See [What the DAG does](./advanced/airflow.md#what-the-dag-does).
- **`fluid apply` finds the dbt that has the build's adapter.** An engine named after its package, `dbt-athena-community`, was looked for as `athena-community`, so a local dbt with the Athena plugin was never used. forge now asks for dbt's plugin name (`athena`), reads the adapter of an engine without one (`dbt`, `dbt-core`) from the build's platform, and matches the `Plugins:` list of `dbt --version` exactly.
- **The dbt container fallback is pinned, and refuses what it cannot pin or authenticate.** It runs `python:3.12-slim` pinned by digest and installs `dbt-core==1.11.17` and an exact adapter package from wheels only, with pip run isolated against PyPI. `DBT_ADAPTER_PACKAGE` must list exact pins, `DBT_DOCKER_IMAGE` and `DBT_BOOTSTRAP_IMAGE` must be pinned by digest, and an adapter with no pin of its own (`glue`, for one) runs in a container only with `DBT_ADAPTER_PACKAGE` or `DBT_DOCKER_IMAGE`. A build of an AWS adapter (`athena`, `glue`, `redshift`) whose dbt profile names an AWS profile, or of `athena`, `glue` or a Redshift IAM build that has no AWS keys in the environment or the dbt profile, is refused before `docker` starts, with the command that installs the adapter next to dbt or exports short-lived keys. forge mounts nothing of `~/.aws`. See [Which dbt `fluid apply` runs](./cli/generate.md#which-dbt-fluid-apply-runs).

*(since 0.34.0, [forge-cli #1010](https://github.com/Agenticstiger/forge-cli/pull/1010))*

- **A Spark job on AWS can write its own table where Lake Formation governs new tables.** forge granted a job's role Lake Formation access to its table only when the output's binding declared a non-empty `governance.lakeFormation` block, so in an account that removed the `IAM_ALLOWED_PRINCIPALS` default for new tables, a stream without that block could not see its own table. The grant (`INSERT`, `ALTER`, `DESCRIBE`, `SELECT`, and `DELETE` for a batch job) is now emitted for such an output and for a stream's dead-letter table beside it, with a `count` that the plan decides from the account's settings: 1 where Lake Formation governs new tables, 0 where IAM alone decides, so an account that keeps the default creates nothing new. The identity that runs `fluid plan` and `fluid apply` needs `lakeformation:GetDataLakeSettings`. An output with a non-empty `governance.lakeFormation` block keeps its grants, and an EMR on EC2 job, which runs as the cluster's own role, gets none. See [Lake Formation writes](./advanced/spark-iceberg-aws.md#lake-formation-writes).

*(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013), [forge-cli #1019](https://github.com/Agenticstiger/forge-cli/pull/1019))*

- **`fluid apply --mode reconcile` keeps the Spark streams running and deploys nothing.** It runs no `tofu`, no DDL and no build, and it takes no plan. It starts a stream that died again on its checkpoint, within its restart budget, when what the last apply deployed is what the contract compiles to. When it is not, it starts nothing, exits `1` and names what to run. `--build-id <stream>` picks one stream, and a keepalive, a scheduler task every few minutes, is what runs it. See [Reconcile mode](./cli/apply.md#reconcile-mode).
- **A Spark stream that died starts again within a restart budget, on a plain `fluid apply` too.** On EMR on EC2, Glue and a local build, a stream whose last run ended `FAILED` was an error until the build changed. It is started again on its checkpoint now, up to `execution.retries.maxAttempts` times per rolling hour (5 when unset, at most 10), each restart carrying `--fluid-restart-of <run id>`, and a spent budget is the error. EMR Serverless and EMR on EKS keep their own retries, and forge starts nothing on top of them. A run cancelled through the runtime is left stopped by `--mode reconcile` and started again by a plain `fluid apply`. `execution.retries` is no longer part of the config hash on EMR on EC2 and Glue, so a stream there that declares it restarts once on its next apply. A local run whose supervisor got a signal from outside forge, a shutdown of the machine say, reads as failed, not cancelled. Of two copies of one config the older is kept, where the newer was. See [The restart budget](./advanced/spark-iceberg-aws.md#the-restart-budget).
- **The scheduler policy `fluid-<product>-spark-caller` covers always-on streams, and its statements change shape.** It lets a role start, watch and stop a stream's runs and read its job config and runner, so a keepalive can run on MWAA. It holds one statement for each runtime, with every build's target, role and artifacts, where it held one for each build, which reached the 6,144-character limit of a managed policy at about six builds. It holds `kms:Decrypt` through S3 only, for those artifacts, so a bucket that encrypts them with a KMS key needs no IAM addition for the scheduler's role (the key's own policy must still allow it, unless it leaves that to the account's IAM policies). See [The caller's permissions](./advanced/spark-iceberg-aws.md#the-caller-s-permissions).

*(since 0.34.0, [forge-cli #1017](https://github.com/Agenticstiger/forge-cli/pull/1017))*

- **A destroy waits for an EMR Serverless application that is still being created or started.** A `CREATING` or `STARTING` application is waited for until it settles: a created one is deleted as it is, a started one is stopped first, and one still moving after `FLUID_SPARK_WAIT_SECONDS` refuses the apply. The refusal's hint names `iam:ListEntitiesForPolicy`, `emr-serverless:GetApplication` and `emr-serverless:StopApplication`, which the identity that runs the destroy needs beyond the runtime's list and cancel actions. See [When a build leaves the contract](./advanced/spark-iceberg-aws.md#when-a-build-leaves-the-contract).

*(since 0.34.0, [forge-cli #1012](https://github.com/Agenticstiger/forge-cli/pull/1012))*

- **An Iceberg table on Glue plans no change after an engine commits to it.** forge emitted the table's location with a trailing slash. Iceberg keeps it without one and writes it back into Glue on every commit, so each `fluid apply` after a commit planned an update (`~1`) for each table that had been written, and sent an `UpdateTable` while a stream kept committing. The location is now emitted as Iceberg keeps it. The first apply after the upgrade updates once, in place, the location of each Iceberg table that Glue still holds with the trailing slash, and a table in a Hive format keeps its trailing slash. See [Iceberg tables in Glue](./providers/aws.md#iceberg-tables-in-glue).

*(since 0.34.0, [forge-cli #1018](https://github.com/Agenticstiger/forge-cli/pull/1018))*

- **`fluid generate schedule` writes a keepalive DAG for an always-on stream that declares `execution.retries`.** On Airflow, a Spark stream that is not `trigger.availableNow` and not `trigger.type: continuous` gets a DAG whose one task, `fluid_keepalive`, runs `fluid apply <contract> --mode reconcile --build-id <stream> --yes` every 5 minutes, or on the build's `execution.orchestration.airflow.dagConfig.schedule`. A stream that died starts again on its checkpoint, within the restart budget that `execution.retries` sets, and a run fails when the stream cannot be kept running. A stream that already declares `execution.retries` gets the DAG from its next `fluid generate schedule` or `fluid generate artifacts`. A stream without `execution.retries` gets no DAG, as before. A contract whose only builds are such streams gets this DAG instead of `No build needs a DAG`; Prefect, Dagster and `fluid scaffold-composer` still write nothing for it. The worker needs the `FLUID_SPARK_*` settings and the forge release that the CI apply has. See [Keeping a stream running](./advanced/airflow.md#keeping-a-stream-running).

## Changes in 0.35.0

These changes are in 0.35.0.

*(since 0.35.0, [forge-cli #1022](https://github.com/Agenticstiger/forge-cli/pull/1022))*

- **A plan made from a `fluid ship --release-dir` release can be applied when the contract has a dbt build.** The release now holds `bundle.tgz.provenance.json`, listed in `release.json` `files` and outside `identity`. Through 0.34.0 `fluid apply` refused such a plan with `apply_plan_digest_bundle_mismatch`. `fluid ship` warns `release_provenance_missing` when it cannot write the file. See [Publishing a release](./cli/ship.md#publishing-a-release).
- **A plan can be applied in another checkout of the same tree.** When the paths the plan records are gone, `fluid apply` finds the contract through the provenance file beside the bundle it verified the plan against. The dbt files must still match the packed copy. See [The dbt project](./cli/apply.md#the-dbt-project).

*(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))*

- **`data-product-forge[profile]` installs flux-stats 0.7.0.** The extra asked for `flux-stats>=0.6.2,<0.7` in 0.34.0 and asks for `flux-stats[yaml]>=0.7.0,<0.8` now. Upgrade the extra with `pip install -U 'data-product-forge[profile]'`. `fluid profile` stops with `profile_statistics_unavailable` on an older flux-stats. See [fluid profile](./cli/profile.md).

## Changes in 0.36.0

These changes are in 0.36.0. They all concern `fluid profile` and FLUID SQL/1. A profile you pin by digest changes bytes, and a profile run can now be refused where it was not: read them before you re-profile.

*(since 0.36.0, [forge-cli #1024](https://github.com/Agenticstiger/forge-cli/pull/1024))*

- **Without `--bundle`, `fluid profile` declares a fidelity block from the contract and answers it.** Every `enum(...)` column gets a level histogram over every declared level. A number whose `validationRules` declare both ends of a range, each inside its type, gets a marginal histogram of about ten bins. Any other number of a bounded type, and every date and timestamp, gets quantiles at 0.25, 0.5 and 0.75. Each categorical `semantics.dimensions` entry on an `enum` column groups the other `enum` columns' level histograms by its levels; a column's groupings hold at most 10,000 cells together, and a grouping past that is left out and named. A number with neither a two-ended range nor a bounded type, such as a `decimal` without `(p,s)`, gets no such statistic, and the summary says so.
- **A profile that holds a quantile names format `1-1-0`.** flux-stats reads it from 0.7. A profile without `--bundle` of a contract with a bounded number, a date or a timestamp is now a `1-1-0` document with new bytes and a new digest, so a Simulation that pins the old digest has to pin the new one.
- **A record outside what the contract declares refuses the profile.** A level its type does not list, a value outside its type or its declared range, a strict bound included, stops the run with `profile_record_outside_declared_domain`. The refusal names the column and the row and never the value. Fix the data or the contract before you re-profile.
- **`fluid profile` profiles a whole data product in one call.** `--expose` repeats, and each expose takes its records as `--source <exposeId>=<location>`, with a database's table as `--table <exposeId>=<table>`. With no `--expose`, every expose a source names is profiled, in the contract's order. The result is one profile document whose `tables` hold every expose, written to `<contract id>.profile.json` unless `--out` names it. One `--expose` with one bare `--source` works as before. A source that pairs with no expose, an expose without a source, a source no `--expose` names and a second source for one expose are refused before any record is read, and a database source's password is masked in every refusal.
- **Several `--expose` flags used to keep only the last.** `--expose org --expose account --source org.csv` profiled `org.csv` as the `account` expose. Each flag now needs its own `--source <exposeId>=<location>`, and without one the run is refused with `profile_source_unpaired`; an expose named twice is `profile_expose_repeated`. Check a script that repeats `--expose`: what it profiled before was the wrong expose's records.
- **A CSV date column is read.** A column the contract types `date` reads a `YYYY-MM-DD` text as that day's midnight in UTC, as a Parquet date always read. It used to be refused. Anything but a calendar day written `YYYY-MM-DD` is refused as before.
- **A grouped statistic's `sampleSize` counts only non-null records.** It used to band the records its groups hold, which gave back how many records hold a value and a null `groupBy` key. It now bands the column's non-null records, as the column's ungrouped statistics do. Three further ways a count table could pin a small count are closed: a column's `distinctCount` is withheld under `D` when a level histogram counts the column or a grouped statistic groups by it, a number with a default histogram withholds its exact `sum`, `min`, `max`, `quantiles` and `distinctCount` under `D` and has no `mean/1`, and a column gets a histogram or quantiles on the same bins, not both.
- **FLUID SQL/1 moves a date by whole days, months and years.** `ADD_DAYS(d, n)`, `ADD_MONTHS(d, n)` and `ADD_YEARS(d, n)` take a date and a count of scale 0 and give a date. A month or year move keeps the day of the month or clamps it to the last day of a shorter month, so 31 January plus one month is 28 or 29 February. A NULL argument gives NULL, and a result outside 0001-01-01 to 9999-12-31 is NULL, never an error. Every dialect renders them with a guarded count, and Snowflake gets `DATEADD`, never its own `ADD_MONTHS`, which keeps month ends. The conformance vectors are version 1.1.0. See [fluid profile](./cli/profile.md).

## Changes in 0.37.0

*(since 0.37.0, [forge-cli #1043](https://github.com/Agenticstiger/forge-cli/pull/1043), [forge-cli #1049](https://github.com/Agenticstiger/forge-cli/pull/1049))*

- **A contract that applies on 0.36.0 can be refused on 0.37.0.** Beside a `secretRef`, every host the `connection` block names is now judged against `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST`, so the first `fluid apply` or CI run after an upgrade can stop at a host nobody listed. The hosts that are new are one in a query string or a query mapping, a URI that names a host anywhere in the block (`api_url: https://api.example.com`, say), a field named for a host under another setting (`options.host`), and an SSH tunnel in use. Before you upgrade a pipeline, run [`fluid secrets check`](./cli/secrets.md#fluid-secrets-check) on its contracts with the new release, which fetches nothing, and act on what it prints. A refusal that names a host, such as `to host 'api.example.com' (connection.api_url)`, takes an entry for that host in the operator's `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST` (a shell or CI variable, not a project `.env`): `NAME@host` for an `env://NAME` reference, `<reference>@host` for another. A refusal that says `which this check does not read`, `more than a database name` or `could not be determined` names no host that an entry could match. For a host in a query string or a query mapping, move it into the URI's host part or the connection's `host` field, where an entry judges it; for the others, write a plain URI or the database's own name. An entry for any host (`NAME@*`, a bare `NAME`, `<reference>@*`) clears all of them, and then nothing is judged. The check reports one host per reference at a time, so run it again after each change. See [Hosts a connection can name another way](./cli/secrets.md#hosts-a-connection-can-name-another-way) and [Hosts a connector takes from its own settings](./cli/secrets.md#hosts-a-connector-takes-from-its-own-settings).

*(since 0.37.0, [forge-cli #1051](https://github.com/Agenticstiger/forge-cli/pull/1051))*

- **A Debezium or Kafka Connect build fails on a `${...}` expression in contract text.** The source, `properties.debezium`, `properties.kafka-connect` and the sink's config may no longer hold `${`, in a value of any type or in a key. The build fails before it reads a secret, writes a file or makes a REST call, with `<path> holds a ${...} expression (the value is not shown)`. That includes a config-provider reference such as `${file:/path:key}` on a Kafka Connect build, and a Java replacement such as `transforms.route.replacement: "${tbl}"` in an `extra_config`; `$1` still works. A contract that validates and applies on 0.36.0 can fail on `main`, because `fluid validate` does not check this. Write the value itself, and a secret as a `secretRef`. See [Contract text a connector expands](./advanced/source-aligned-acquisition.md#contract-text-a-connector-expands).
- **A credential that holds `${` is refused for embedded Debezium Server.** The operator's secret counts: `debezium config entry <key> holds ${ in its value (the value is not shown)`. Change the credential. A Kafka Connect build does not check a resolved secret.
- **A connection block of more than 10,000 values has a refusal of its own.** `... over a connection block that holds more than 10,000 values, more than this check reads`, where it read `a host that could not be determined` before.

*(since 0.37.0, [forge-cli #1043](https://github.com/Agenticstiger/forge-cli/pull/1043))*

- **The secret destination check reads more than `host`.** Beside a `secretRef`, `fluid validate` and `fluid apply` now refuse a query string that names a host (`host`, `hostaddr` and others, in a URI field or in `jdbc_url_params`), URL syntax in `database` or `dbname`, a URI whose authority a database client could read as another host, the host of an SSH tunnel in use, a host with an IPv6 zone id, and a host in `sqlalchemy_url` that has no entry. The operator can allow a reference for any host. A tunnel needs an entry for its host, and a loopback database host behind it needs `NAME@localhost`. A Debezium `extra_config` that sets `database.port`, `database.dbname`, `database.names` or `connector.class` is refused whatever the allowlist says. See [Hosts a connection can name another way](./cli/secrets.md#hosts-a-connection-can-name-another-way).
- **A runner keeps each connection field in its own part of the URL.** dlt's `sql_database` source, the Kafka Connect JDBC source and Debezium fail the build, with or without a secret, when `host` or `database` holds URL syntax or a port is not a number. dlt's `drivername` has to be `dialect[+driver]`, such as `postgresql+psycopg`.
- **`NAME@*` allows any host for `env://NAME`.** In `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST` it used to name a literal host `*`, which no destination matches. A bare `NAME` and `env://NAME@*` already meant any host.
- **Refusals name the field they judged and print no value from the environment.** A refusal reads `... to host 'db.example.com' (connection.host) as a credential`. At `fluid apply`, a host that came from a placeholder appears as `the host '{{ env.PGHOST }}' renders to (connection.host)`, where it used to show the value it rendered to, and a keyword string shows its host part and not the password beside it. A script that matches the old wording can match `would send` and `as a credential`, which are in both. A URI whose query names a host no longer waits for `fluid apply` when its host part is a placeholder, and a placeholder that names a tunnel host waits as `host` does.
- **An OpenBao or Vault address with an IPv6 zone id is not loopback.** `http://[::1%25lo0]:8200` needs `https` now.

*(since 0.37.0, [forge-cli #1042](https://github.com/Agenticstiger/forge-cli/pull/1042))*

- **`fluid ship` opens a wrapped store token once and hands it to every stage.** A response-wrapped OpenBao or Vault token (`FLUID_VAULT_WRAPPED_TOKEN`) opens once, and ship runs each stage as its own process, so only the first stage that reached the store could use it: with OpenBao state encryption, `diff` spent it and `apply` failed. A ship of two or more stages now opens it before the first stage, hands each stage the token through a pipe (`FLUID_VAULT_SHIP_TOKEN_FD` names it, and `FLUID_VAULT_SHIP_TOKEN` carries the token on Windows) and revokes it when the run ends. dbt, a project's build steps and the stage's other child processes never see the token, and `tofu` gets it only for OpenBao state encryption. A wrapper that cannot be opened stops the run before any stage, with exit 2. A wrapper serves one `fluid ship` invocation, so a run split over several invocations needs one for each. A ship of one stage works as before. See [A wrapped store token](./cli/ship.md#a-wrapped-store-token).
- **A `fluid ship` stage no longer imports modules from the checkout.** A `yaml.py` or a `fluid_build/` in the contract's directory used to run inside every stage, before the CLI started, with your environment. See [Where it runs](./cli/ship.md#where-it-runs).
- **Generated GitHub Actions workflows pin newer commits of four actions.** `actions/checkout` v4.4.0, `google/osv-scanner-action` v2.7.1, `github/codeql-action/upload-sarif` v3.39.4 and `anchore/sbom-action` v0.24.3. A workflow you generated keeps its old commits until you run `fluid generate ci` again. See [What each system gets](./advanced/operating-in-ci.md#what-each-system-gets).
- **`fluid doctor` reports the auth method `ship-token`** in a process that `fluid ship` handed its store token to.
- **`tofu --version` runs with a short environment.** The check that runs before a cloud apply and before `fluid diff` used to get every variable of the job. It now gets `PATH`, `HOME`, what a Go program needs on Windows, and `TOFU_CLI_PATH` and `GITHUB_OUTPUT`. See [What `tofu` gets from the environment](./cli/apply.md#what-tofu-gets-from-the-environment).

*(since 0.37.0, [forge-cli #1049](https://github.com/Agenticstiger/forge-cli/pull/1049))*

- **The secret destination check reads the settings a connector takes a host from.** Beside a `secretRef`, `fluid validate` and `fluid apply` refuse a host key in a mapping a connector reads as query parameters or driver arguments (`sqlalchemy_url_query`, `sqlalchemy_options`, `connect_args` under `sqlalchemy_eng_params`, any `*_query` mapping, `jdbc_url_params` as a mapping), `socketFactory`, `socketFactoryClass` and `FILEDSN`, a parameter name that holds connection-string syntax, a `connect_args` value that holds `;`, `{` or `}`, a URI or a field named for a host under any other setting of the block, a JDBC URL that is not an embedded database, and a block of more than 10,000 values. The operator can allow a reference for any host. See [Hosts a connector takes from its own settings](./cli/secrets.md#hosts-a-connector-takes-from-its-own-settings).
- **Some setups need no entry.** An absolute socket path in a query's `host` or `unix_socket` names this machine. A Singer tap's `ssh_tunnel` is off when its `enable` is absent, false or empty, and Airbyte's `tunnel_method` is off when it is `NO_TUNNEL` in any letter case, so neither needs an entry for its host. A `#` in a query string ends no parameter.
- **A Debezium `extra_config` may not set more.** Under `database.` or `driver.`, `hostname`, `port`, `dbname`, `names`, `url`, `password` and `protocol` are refused whatever the allowlist says, and so are a driver property that names a host (`failoverPartner`, `serverName`, `PGHOST`, `socksProxyHost`, `socketFactory`) and Oracle's `rac.nodes`.
- **A refusal quotes less.** A keyword connection string shows its host only when the host comes before a key that may hold a secret, and a host that is not a plain name or address (`user:password@host`, a path) is not quoted: `the host in connection.host`. At `fluid apply` a host is quoted as written only when the `connection` block the contract wrote holds it in that field, and a refusal for a rendered database name says `holds a character`.

## Also in 0.37.0

Features: `fluid import pyspark` and `fluid import airflow` ([guide](./advanced/importing-existing-pipelines.md)), `fluid generate pyspark-schema` ([page](./cli/generate-pyspark-schema.md)), `fluid datamesh-manager` batch `publish`, `promote` and `status` ([page](./cli/datamesh-manager.md)), the `freshness` dimension in `fluid verify` ([page](./cli/verify.md#freshness-of-an-iceberg-table)), `--odcs-version 3.2.0` ([page](./cli/odcs.md)), `fluid runs status --release-dir` ([page](./cli/runs.md)), `--adopt-tables` ([page](./cli/apply.md)), prebuilt PySpark package builds and Iceberg commit stamps ([page](./advanced/spark-iceberg-aws.md)), `fluid schedule-sync --airflow-url` ([page](./cli/schedule-sync.md)), `fluid describe --commands` ([page](./cli/describe.md)).

What to do when you upgrade:

- **An existing Glue table forge did not make is no longer taken over silently.** `fluid apply` refuses it with `table_adoption_requires_flag`. Pass `--adopt-tables` after reviewing the match. A table forge made for the same product is re-attached as before. A table forge made from a contract over 50 KB before 0.37.0 has no product id: add the table parameter `fluid_product_id=<product id>` once, with the writers paused, using `aws glue update-table` with `--version-id` from a fresh `aws glue get-table`. See [Adopting existing Glue tables](./cli/apply.md).
- **`--fail-on-breaking` fails on a changed product id.** A contract that only changed its id passed before. Keep the id, or see [A changed product id](./cli/diff.md).
- **Every running Spark stream is replaced once** by the first `fluid apply` after the upgrade, by a cancel. A plan made before the upgrade is refused with `apply_spark_artifact_mismatch`: plan again.
- **`fluid apply` waits on a released Spark stream** for up to `FLUID_SPARK_RELEASE_PROBATION_SECONDS` (300 by default, `0` turns it off). A run that fails in that time is rolled back and the apply fails. Set it to `0` where a scheduler's timeout is shorter. See [Rolling back a failed release](./advanced/spark-iceberg-aws.md).
- **A scheduled run has its own run id.** Under a scheduler the run id comes from the scheduler's job and run, no longer from `.fluid/run-id.txt`. `FLUID_RUN_ID` still wins.
- **Entropy Data's product list is read whole or not at all.** A bad page is now a typed error.

## Changes in 0.38.0

These changes are in 0.38.0. Four need an action before you upgrade a pipeline: a stream's identity needs `s3:ListBucket`, a secret may not sit in a maintenance option, a live Iceberg table in Glue is no longer updated in place, and short credentials are now masked in output.

### Steps to take

1. **Grant `s3:ListBucket` on the release prefix to the identity that runs `fluid apply` for a Spark stream.** Limit it to the build's prefix, `_fluid/spark/<product>/<build>`, and nothing wider. Without it S3 answers a missing key with 403, so forge cannot tell a missing failed-release marker from a refused one. *(since 0.38.0, [forge-cli #1062](https://github.com/Agenticstiger/forge-cli/pull/1062))* When the job config reads but the marker read is refused, the start now fails closed with `apply_spark_artifact_read_denied`, and the error names the marker's key; in 0.37.0 forge read the marker as missing, with a warning. A throttle or a timeout while reading the job config beside the marker is reported as a read failure, not as a denial. `FLUID_SPARK_ACCEPT_FAILED_RELEASE=1` lets one apply start through, but it also skips a real failed-release marker, so never set it permanently, a keepalive's environment least of all. See [Rolling back a failed release](./advanced/spark-iceberg-aws.md#rolling-back-a-failed-release).
2. **Move a secret out of a maintenance action option.** An option whose key names a credential (`api_key`, `password` and the like) is refused by `fluid validate`, `fluid plan` and `fluid apply`, whatever its value, and the message does not show the value. Before, such a value reached `plan.json` and the deployed job config. Put the secret in a connection or a secret reference the action's package reads itself. *(since 0.38.0, [forge-cli #1063](https://github.com/Agenticstiger/forge-cli/pull/1063))* See [Iceberg table maintenance](./advanced/spark-iceberg-aws.md#iceberg-table-maintenance).
3. **Expect short credentials to be masked.** A password or a token under a credential-named key is now replaced by `***REDACTED***` in logs and output (`[REDACTED]` in the Snowflake provider's logs) even when it is short. Before, a short value was left as it was unless it had a known shape. A script that reads such a value out of a log line stops finding it. *(since 0.38.0, [forge-cli #1063](https://github.com/Agenticstiger/forge-cli/pull/1063))*
4. **Plan again after upgrading if you hold a saved plan that updates a live Iceberg table in place.** `fluid apply plan.json` refuses it. See the first item below.

### What changed

- **A live Iceberg table in Glue is not updated in place by `fluid apply`.** A change to its description, column comments or columns is held, and the run prints what waits. To apply it, change the table through its Iceberg catalog (`ALTER TABLE ... SET TBLPROPERTIES ('comment' = '...')`, or `ALTER TABLE ... ALTER COLUMN ... COMMENT '...'`, in Spark), whose commit writes Glue with the version it read; or pause the table's writers and run `fluid apply --allow-iceberg-update` once. A table whose Iceberg schema changed outside the contract gets the note on every apply while the two differ. A saved plan made before this release that updates a live Iceberg table in place is refused by `fluid apply plan.json`: plan again. A plan that `tofu show -json` cannot read back is refused when it changes anything in place, even with `--allow-data-loss`. See [Live Iceberg tables are not updated in place](./cli/apply.md#live-iceberg-tables-are-not-updated-in-place). *(since 0.38.0, [forge-cli #1054](https://github.com/Agenticstiger/forge-cli/pull/1054))*
- **A contract declares each Iceberg table's maintenance, and forge runs it beside the table's stream (schema 0.7.7).** `exposes[].iceberg.maintenance` takes compaction, manifest rewrites, snapshot expiry, orphan-file removal and a package's own actions. `fluid plan` lists a `spark.maintain` action, `fluid generate schedule` writes a maintenance DAG, and `fluid apply --mode maintain --expose-id <expose>` runs it. The change is additive: a contract without the block behaves as before. See [Iceberg table maintenance](./advanced/spark-iceberg-aws.md#iceberg-table-maintenance). *(since 0.38.0, [forge-cli #1057](https://github.com/Agenticstiger/forge-cli/pull/1057))*
- **Generated Airflow DAGs can alert on failure, retry, success and a missed SLA.** A contract with no `alerts` block renders the same file as before. `fluid plan` and `fluid apply` now run the same alert-route checks as `fluid validate`, and a schema error under `alerts` no longer quotes the field's value. See [Alerts](./advanced/airflow.md#alerts). *(since 0.38.0, [forge-cli #1056](https://github.com/Agenticstiger/forge-cli/pull/1056))*
- **Generated Airflow DAGs can serialize the writers of a table.** With `orchestration.airflow.poolPerOutputTable: true` (0.7.7), each task that writes an output table runs in a one-slot pool named after the table. It is off by default. A build that writes more than one table is refused, so declare one output per build. `fluid schedule-sync --airflow-url` creates the pools Airflow lacks and never changes one that exists; without `--airflow-url`, `fluid generate schedule` and `fluid schedule-sync` print the `airflow pools set` lines. See [Writer pools](./advanced/airflow.md#writer-pools). *(since 0.38.0, [forge-cli #1062](https://github.com/Agenticstiger/forge-cli/pull/1062))*
- **The DAGs `fluid generate schedule` writes for AWS, GCP and Snowflake set `max_active_runs=1`**, as the `fluid apply` DAGs already did, so two runs of one DAG never write the same tables at the same time. A DAG that relied on overlapping runs now queues the second run. *(since 0.38.0, [forge-cli #1062](https://github.com/Agenticstiger/forge-cli/pull/1062))*
- **In the 0.7.7 preview, `airflowOrchestration.dagId` is optional and takes Airflow's own spelling.** `dagId` and `airflowTask.taskId` follow Airflow's rule for these ids (ASCII letters of either case, digits, underscore, dot and dash, at most 250 characters), so every id the lowercase rule took is still taken. `fluid validate` refuses an empty id, a space, a slash and an id over 250 characters. The schemas for 0.7.6 and older are unchanged: a contract written for them keeps lowercase ids. *(since 0.38.0, [forge-cli #1059](https://github.com/Agenticstiger/forge-cli/pull/1059))*
- **`fluid import airflow` follows Python tasks.** A `PythonOperator` or `@task` function is read for the Spark jobs it submits, and the conventions file gains `submit_helpers`. A dict key written before a `**` spread that does not fold is no longer taken as known, so what it names is reported as not read. A DAG or task id with capitals is now kept, recorded under the importer's identifier of it. See [Importing existing pipelines](./advanced/importing-existing-pipelines.md). *(since 0.38.0, [forge-cli #1055](https://github.com/Agenticstiger/forge-cli/pull/1055), [forge-cli #1058](https://github.com/Agenticstiger/forge-cli/pull/1058))*
- **`fluid profile` answers a FLUX profile request, profiles boolean columns and can release a table under differential privacy.** `--request FILE` measures what a request lists and nothing else, and names each item it cannot answer as `Not measured`, with the reason. `--privacy-unit` with `--rho` and `--release-record` releases a table under zero-concentrated differential privacy (profile format 1-2-0); it needs the `[privacy]` extra only when a selection runs. A column typed `boolean`, `bool` or `bit` is read as the category `false` or `true`. A histogram over a declared range now ends at the column's maximum, so a bundle written from the profile no longer reads a maximum the contract never declared. The `[profile]` extra takes flux-stats `>=0.9,<1`; a flux-stats below 0.9 is replaced when the extra is installed. See [fluid profile](./cli/profile.md). *(since 0.38.0, [forge-cli #1040](https://github.com/Agenticstiger/forge-cli/pull/1040))*
- **`fluid datamesh-manager publish|promote|status --format json` print a typed error on stderr**, so stdout stays one JSON document.

### Security

- **Both redaction layers mask more.** A short credential under a credential-named key, a token of 16 or more characters that is the only user info of a URL, AWS SigV4 `Authorization` values, camelCase alert keys (`routingKey`, `integrationKey`, `genieKey`), Teams and Discord webhook URLs, the `sig=` of a signed URL, a credential key spelled with hyphens (`x-api-key`) and a log argument that is an object. The Zenduty, Opsgenie and PagerDuty connection values of an alert route are masked too. *(since 0.38.0, [forge-cli #1063](https://github.com/Agenticstiger/forge-cli/pull/1063))*
- **The importer's command-line scrubber masks `--login user/pw`, a split `--conf <secret.key> <value>` and a provider token in a path segment.** An exported ODCS `catalogUrl` never carries a password, and a Data Mesh Manager error body that echoes the API key no longer shows it. *(since 0.38.0, [forge-cli #1063](https://github.com/Agenticstiger/forge-cli/pull/1063))*
- **A `.` or `..` segment in an object-store binding location, or in a Data Mesh Manager product id, is refused.** *(since 0.38.0, [forge-cli #1063](https://github.com/Agenticstiger/forge-cli/pull/1063))*

### Also in 0.38.0

A Jenkins `GENERATE_EMIT` default that includes `opds`; GitHub Actions uploads that keep their dot folders; a `parquet_variant` column read as a variant by the live `fluid diff` of a DuckDB table; an Airflow client that bounds the whole time it takes to read an answer; generated DAG file names that differ only in case are refused; and a generated Glue table helper that leaves Iceberg tables alone. The full list is in the forge-cli [CHANGELOG](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md).

## Changes in 0.39.0

These changes are in 0.39.0. Six need an action, and only if they apply to you: a saved plan that holds a Spark action, every running Spark stream (it restarts once), a maintenance DAG that runs before the next `fluid apply`, orphan removal on a REST-catalog table, a command plugin that takes a core command's name, and a FLUX simulation pinned to a profile that lists facts. Everything else is additive or loosens a rule that was wrong.

### Steps to take

1. **Plan again after upgrading if you hold a saved plan with a Spark action.** `fluid apply plan.json` refuses a plan made by 0.38.0 or earlier that lists a `spark.reconcile` or a `spark.maintain` action, with `apply_spark_artifact_mismatch`: the runner changed, and a maintenance action now also lists each plugin action (`actions[]`) and carries other compaction options. Run `fluid plan`, then `fluid apply`. A plan with no Spark action is not affected. *(since 0.39.0, [forge-cli #1068](https://github.com/Agenticstiger/forge-cli/pull/1068))* To check: `fluid apply plan.json --dry-run` on a plan made by 0.38.0 prints the refusal, and on a plan made by 0.39.0 it does not.
2. **Expect each running Spark stream to restart once on its next `fluid apply`, on its checkpoint.** The runner file changed, and a build's config hash covers the runner's sha256, so the hash of a Spark build whose contract did not change is another one: apply asks the running stream to stop between batches, and starts it again on the same checkpoint. A stream that a 0.37.0 or later `fluid apply` started has a stop key, and one that an older apply started is cancelled instead. A build that runs to completion is not restarted, and its next run uses the new runner. Apply when a restart is acceptable. *(since 0.39.0, [forge-cli #1068](https://github.com/Agenticstiger/forge-cli/pull/1068))* To check: `fluid plan` on the same contract with 0.38.0 and with 0.39.0 lists a different `configHash` and `runnerSha256` for each `spark.reconcile` action and the same `jobConfigDigest`. See [Starting and reconciling runs](./advanced/spark-iceberg-aws.md#starting-and-reconciling-runs) and [Replacing a changed stream](./advanced/spark-iceberg-aws.md#replacing-a-changed-stream).
3. **Run `fluid apply` once for each product whose tables declare maintenance, before the next scheduled maintenance run.** The maintenance job config changed (the runner, and compaction now writes `max-concurrent-file-group-rewrites=5`), and `fluid apply --mode maintain` starts a run only with the config that the last `fluid apply` deployed when that is the config the contract compiles to now. Step 2's apply does this too. *(since 0.39.0, [forge-cli #1068](https://github.com/Agenticstiger/forge-cli/pull/1068))* To check: `fluid apply contract.fluid.yaml --mode maintain --expose-id <expose> --dry-run` lists `max-concurrent-file-group-rewrites=5` on its compaction line.
4. **Check that the Spark runtime of a REST-catalog table has Iceberg's prefix listing.** Orphan removal on a table in an Iceberg REST catalog (such as Lakekeeper) now lists only the table's own folder, through Iceberg's prefix listing. A Spark runtime whose Iceberg has none stops that step with an error and deletes nothing, and compaction and snapshot expiry still run. A Glue-catalog table keeps the default listing. *(since 0.39.0, [forge-cli #1068](https://github.com/Agenticstiger/forge-cli/pull/1068))* To check: the first scheduled `removeOrphanFiles` step of such a table ends without that error.
5. **Give a command plugin command names of its own.** A `fluid_build.commands` plugin that asks for the name of a core command or of another plugin's command is skipped whole, with a `cli_plugin_command_shadow` warning that names the plugin and the command, and the other plugins still load. Rename the command it adds. On Python 3.10 such a plugin used to replace the core command without a word, and on Python 3.11 and later it failed with `Failed to load CLI plugin <name>: ArgumentError`. *(since 0.39.0, [forge-cli #1065](https://github.com/Agenticstiger/forge-cli/pull/1065))* To check: `fluid describe --commands` loads every plugin and prints no `cli_plugin_command_shadow` warning. See [Command names are new ones](./sdk-and-plugins/reference/entry-points.md#command-names-are-new-ones).
6. **Profile again, and pin again, if a FLUX simulation pins a profile that lists facts.** `fluid profile --request` now checks the facts of a table together, so a fact that 0.38.0 published may be withheld (`C` in the document, `D` in the summary), and the profile's digest changes with it. Read the report, then update the digest your simulation pins. A profile with no facts is not affected. *(since 0.39.0, [forge-cli #1066](https://github.com/Agenticstiger/forge-cli/pull/1066))* See [The facts of a table are checked together](./cli/profile.md#the-facts-of-a-table-are-checked-together).

### What changed

- **Iceberg maintenance for a table forge does not write (schema 0.7.7 preview).** `exposes[].iceberg.maintenance.runtime` takes the place of `build` for a table that no forge build writes, such as one whose streams run on its team's own runner. It names `emr-serverless`, `emr-ec2` or `emr-eks` with the runtime's target and an explicit `executionRoleArn`, or `local` for a table in an Iceberg REST catalog on platform local. `glue` is refused. The operator's `FLUID_SPARK_EXECUTION_ROLE_ALLOWLIST`, `FLUID_SPARK_TARGET_ALLOWLIST` and `FLUID_SPARK_CONF_ALLOWLIST` apply to it, the role must be able to read the run's files under `_fluid/spark/<product>/maintain_<expose>/`, `removeOrphanFiles` needs an explicit `olderThan` there, and `fluid validate` warns when it is under `P3D`. The maintenance DAG has no writer build, so its `BUILD_ID` is empty. The change is additive: a contract without `runtime` behaves as before. See [A table forge does not write](./advanced/spark-iceberg-aws.md#a-table-forge-does-not-write). *(since 0.39.0, [forge-cli #1068](https://github.com/Agenticstiger/forge-cli/pull/1068))*
- **The plan binds each maintenance action on its own.** The `spark.maintain` action lists `actions[] = {name, kind, distribution, version, statementsSha256}`, never the SQL. `fluid apply` compares the actions by name, and refuses with `apply_plan_digest_maintenance_actions_changed` (plan-binding kind `maintenance-actions-changed`) when an action's statements hash differently or only one side lists it. The message names the action and the package and version on each side. A new version that renders the same statements only warns. See [A package's maintenance action](./advanced/spark-iceberg-aws.md#a-package-s-maintenance-action). *(since 0.39.0, [forge-cli #1068](https://github.com/Agenticstiger/forge-cli/pull/1068))*
- **Compaction in a maintenance run rewrites at most 5 file groups at once.** The job config now says `max-concurrent-file-group-rewrites=5`, Iceberg's own default, unless `compaction.maxConcurrentRewrites` sets another value. Partial progress stays on, so a conflict with a live writer fails only one file group. *(since 0.39.0, [forge-cli #1068](https://github.com/Agenticstiger/forge-cli/pull/1068))*
- **Two runner fixes for table maintenance.** A maintenance run started through `spark-submit` (`fluid apply --mode maintain` on `runtime: local`) stopped with `NameError` before its first step, because the runner's script entry point sat above the maintenance functions. And on a table in an Iceberg REST catalog (such as Lakekeeper), removing orphan files waited on Hadoop S3A credentials that the catalog never hands out. The runner now lists through the table's own FileIO, under the table's location and a `/`, so a sibling table whose location starts the same is never listed. A Glue-catalog table keeps the default listing. There is nothing to configure: the fixes arrive with the runner that `fluid apply` uploads, so run `fluid apply` (step 3). *(since 0.39.0, [forge-cli #1068](https://github.com/Agenticstiger/forge-cli/pull/1068))*
- **`fluid import airflow|pyspark SOURCE --check` is a drift gate.** It compares the DAGs or job files with the contracts the import wrote, writes nothing, and exits 0 (in sync), 1 (drift) or 2 (it cannot decide). `--format text|json|github`, `--strict` and `--out-report PATH` shape the report. `fluid generate ci --add import-drift` puts it in a generated pipeline for every CI system. See [Checking for drift in CI](./advanced/importing-existing-pipelines.md#checking-for-drift-in-ci) and [Add-ons](./advanced/operating-in-ci.md#add-ons). Output without the add-on is the same bytes as before. *(since 0.39.0, [forge-cli #1067](https://github.com/Agenticstiger/forge-cli/pull/1067))*
- **An alert route names a connection only when its kind has no default.** A kind with `requires_connection` and a `default_connection` refused every route that named none in 0.38.0. A route that names none now uses the default, in the notifier's arguments and in the DAG's notes, and a connection the route names wins. `webhook` still needs one. See [Extending alerts](./advanced/airflow.md#extending-alerts). *(since 0.39.0, [forge-cli #1065](https://github.com/Agenticstiger/forge-cli/pull/1065))*
- **`data-team` is template residue at `metadata.owner.team` only.** `fluid validate` no longer warns (`contract_template_residue`) about `channel: data-team` in an alert route, or a tag or a label of that name. A run with `--strict` that failed on one of those now passes. See [`fluid validate`](./cli/validate.md). *(since 0.39.0, [forge-cli #1065](https://github.com/Agenticstiger/forge-cli/pull/1065))*
- **The entry point of a command plugin is any callable `(subparsers) -> None`**, whatever it is named. The docs and `AGENTS.md` said `register(subparsers)`. *(since 0.39.0, [forge-cli #1065](https://github.com/Agenticstiger/forge-cli/pull/1065))*
- **The 0.7.7 `dagId` and `taskId` patterns end where the value ends.** They ended in `$`, which Python's `re` also matches before a final line break, so a validator that runs `pattern` as it is (stock `jsonschema`) took `"abc\n"` where an ECMA-262 validator, such as node's, refused it. `fluid validate` already refused it. Both patterns now end in `(?![\s\S])`, as 34 other patterns of the file do, and `minLength` 1 and `maxLength` 250 are unchanged. The descriptions now say the schema takes the ASCII part of Airflow's rule: Airflow's own pattern also takes Unicode letters and digits. A contract that passed `fluid validate` before still passes. The [0.7.7 reference](./reference/contract-0.7.7-preview.md) shows the new text. *(since 0.39.0, [forge-cli #1065](https://github.com/Agenticstiger/forge-cli/pull/1065))*
- **`fluid profile --privacy-unit` warns when `--rho` is above 1.** The release still runs, and `--rho` still takes any number above zero. The warning cites OpenDP's rule of thumb (an epsilon of at most 1, rho 0.5) and the rho of about 2.6 to 7.7 that the US Census Bureau's 2020 Census products used. The `--privacy-unit` help now says what the privacy unit is: one row of the unit's expose, or with `--release-table` or `--unit-key` every row that belongs to one entity. A script that treats any output on stderr as failure sees the warning. See [Releasing a table under differential privacy](./cli/profile.md#releasing-a-table-under-differential-privacy). *(since 0.39.0, [forge-cli #1066](https://github.com/Agenticstiger/forge-cli/pull/1066))*

### Also in 0.39.0

`fluid profile --help` imports at most 328 modules beyond the plain CLI, one more than before, which keeps the startup budget test from failing in an environment with more packages installed. The full list is in the forge-cli [CHANGELOG](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md).

## Changes in 0.40.0

These changes are in 0.40.0. One may need an action, and only if you use the new `fluid profile` options: the `[profile]` extra now asks for flux-stats 0.11. Everything else is additive, and a profile that uses none of the new options keeps the format and the bytes it had.

### Steps to take

1. **Upgrade the `[profile]` extra if you use a new `fluid profile` option.** The extra asks for `flux-stats[yaml]>=0.11,<1` now, the first release that holds rank correlations, the follows reach of a release and profile format 1-4-0. It asked for `>=0.9,<1` in 0.39.0. Run `pip install -U 'data-product-forge[profile]'`. A profile that uses none of the new options still runs on an older flux-stats. A request of format 1-2-0, which can ask for rank correlations, is refused by an older flux-stats's request reader with `profile_request_refused`, and a noisy rank correlation or `--follow` stops with an error that says it needs flux-stats 0.11. *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))* To check: `pip show flux-stats` reports 0.11 or newer after the upgrade. See [fluid profile](./cli/profile.md); `fluid profile --help` lists the new flags (`--row-floor`, `--clique-method`, `--follow`).

### What changed

- **`fluid profile --request` answers more of a profile request: format 1-2-0 asks, in a profile of format 1-4-0.** A table's `rankCorrelations` are answered with one `kendallTau/1` or `spearmanRho/1` entry (`columnPairs`) for each pair of the listed columns, in the order the request lists them. A correlation over fewer than the records the group-size check needs is withheld like any other group. A table's `cliqueColumns` are answered with one two-way statistic for each pair of the first 32 listed columns, and the pairs not measured are named in the report with the reason. A relationship's `groupBy` asks its statistics grouped by each named parent column, and its `linked` asks a child column's histogram grouped by a column of the parent row its key reaches (`groupByLink`). Each group of a grouped statistic is checked on its own, and the rows of a parent with no value in the column are never a group. A profile names the least format that holds it, so a profile with none of these keeps the format and the bytes it had. `--row-floor N` (a public count of 2 or more) is written as the `rowFloor` of each rank correlation, and the records are counted as the larger of their number and N; without it a rank correlation states no floor. *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))*
- **`fluid profile --privacy-unit` releases rank correlations and clique marginals over numbers and timestamps.** Each noisy rank correlation carries `--row-floor` (default 1000) as its public `rowFloor`. Its sensitivity for one row is 4 / (floor + 1) for Kendall's tau and 9 / (floor + 1) for Spearman's rho, times the rows one unit contributes (at least two in a keyed or related release, since replacing a row can change which row of a unit is kept). The value is rounded onto a lattice of 2^20 steps per sensitivity and an exact discrete Gaussian is added on it, so no floating-point noise is drawn. A clique that holds a number or timestamp column is released as `cliqueMarginal/2` on the public bins of the column's declared range, and the bins are never chosen from the data. The cliques are chosen with OpenDP's AIM or, with `--clique-method mst`, its MST, and the profile records the method, the OpenDP version and the tenth of `rho` the choice cost in `cliqueSelection`. Each noisy statistic is one part with an equal share of the rest, and every noise block is in the profile's account once. *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))*
- **`fluid profile --privacy-unit --follow PARENT.COL[,COL]=CHILD.COL[,COL]:MAX` makes the unit follow its child rows.** The unit is a row of the privacy unit's expose with at most MAX of its children through each followed relationship, and repeating the flag follows a tree. The profile names the follows in `privacy.privacyUnit.follows` (format 1-4-0), and the tree is checked before any record is read. A parent's children are cut to MAX by a keyed priority that reads only that parent's children, a child that is dropped takes its descendants, and a row that follows no kept row is dropped, so what a unit keeps depends on the seed and that unit alone. The release holds every table the unit reaches, each charged for the rows one unit contributes to it, and a noisy children-per-parent histogram for each declared relationship (bins 0 to MAX when followed, and a cap whose bins pass the release's cell limit is refused by name; a fixed public ladder when not), grouped by parent columns, and histograms grouped through a link by the contract's levels, each charged as a count table of the child. A table the unit does not reach is treated as fixed: the report names those tables and warns when a labelled (`pii` or `restricted`) column of one groups a noisy statistic. `--follow` is not combined with `--release-table`, `--unit-key` or `--max-rows-per-unit`. `--rederive` draws the same release again from the record, which now holds each part. *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))*

## Changes in 0.40.1

`0.40.1` publishes the container image that 0.40.0 did not get. Nothing needs an action. The PyPI package is the same as 0.40.0 apart from the change in the last item.

- **The container image is published again.** The release's image scan stopped the 0.40.0 image on CVE-2026-119170, a regression in how CPython 3.14.10's `hashlib` enforces FIPS algorithms, which matters only where OpenSSL runs in FIPS mode. The image does not run it so, and the fix is in CPython 3.14.11, which was not out when 0.40.1 was cut. The scan's configuration lists the CVE with that reason until a `python:3.14-slim` with CPython 3.14.11 ships. *(since 0.40.1, [forge-cli #1076](https://github.com/Agenticstiger/forge-cli/pull/1076))*
- **Five names that nothing read are gone from the profiler and its tests.** They are `_COUNT_KINDS`, and the `itertools`, `math`, `_stats` and `selection` imports, as GitHub code quality found. *(since 0.40.1, [forge-cli #1076](https://github.com/Agenticstiger/forge-cli/pull/1076))*

## Not in a release yet

*On forge-cli `main`, not yet in a release ([forge-cli #1099](https://github.com/Agenticstiger/forge-cli/pull/1099)).*

Nothing in forge-cli #1099 needs an action. A contract that declares none of the new members validates and exports as before, except that the dbt semantic model of a validity window gains a `config` block.

- **A table that keeps history can be read through a relationship (schema 0.7.7 preview).** A validity window takes `validityParams.openEnd` and `chain` on its `isEnd` dimension, the natural entity takes a `lifecycle` of `activation`, `endMarker` and `currentFlag`, and a relationship takes `asOf`, a date or time column that picks the version it reads. A FLUID SQL/1 path or a `sharedColumns` entry through a relationship into such a table was refused on 0.40.1 and earlier. It now reads the natural key and the columns a `dependency` from the key makes stable, by entity, or any column as of the `asOf` date. A summary into such a table is still refused. `fluid validate` reports a misplaced or mistyped member, and the exported rules and `fluid generate dbt-tests` render both joins. See [Versioned tables](./concepts/semantic-layer.md#versioned-tables-window-conventions-and-as-of-reads).
- **The dbt semantic model of a validity window carries `config.meta.snapshot_config`.** It holds `unique_key`, `snapshot_meta_column_names` and, where the contract declares them, `dbt_valid_to_current` and `hard_deletes: new_record`. A regenerated dbt project shows the block in `semantic_models.yml`, for a window that declares no conventions too. To check: `fluid generate transformation contract.fluid.yaml` on a contract with a window, and compare `semantic_models.yml`. See [dbt MetricFlow](./concepts/semantic-layer.md#dbt-metricflow).
- **The error for a refused read into a validity window has new text.** For a path, a `sharedColumns` entry or a shared attribute, it no longer says that FLUID SQL/1 v1 reads no slowly changing dimension (or "copies nothing from" one) through a relationship, and it ends with both ways to declare the read: a column stable per entity, or an `asOf` column on the relationship. The error for a summary into such a table has new text too: it ends "summarize into an expose without a validity window, or copy the column through a relationship that reaches the entity". A script that matches an old sentence needs the new one.

*On forge-cli `main`, not yet in a release ([forge-cli #1105](https://github.com/Agenticstiger/forge-cli/pull/1105)).*

On an expose with restricted columns, redacted columns or row filters, `query` and `query_sql` refuse some expressions and statements that `0.40.1` and earlier ran. An expose with none of these answers as before, except that every term of a `query` `WHERE` is parenthesised and the Postgres XML functions below are refused on every expose.

- **`query` evaluates every expression over the allowed columns.** On an expose with `policy.authz.columnRestrictions` (`access: deny`) or `policy.privacy.masking`, the statement now reads `FROM (SELECT <allowed columns> FROM <table>) AS _fluid_allowed`. The allowed columns are the ones `contract.schema` declares, less the restricted ones, so a measure, dimension or metric `filter` that uses a column the schema does not declare now fails in the engine, and an expose whose schema declares no readable column is refused. A subquery in an expression is refused on an expose that restricts or redacts columns or declares row filters. To check: call `query` and read `compiled.sql` in the result. See [Restricted columns on the query tools](./advanced/mcp.md#restricted-columns-on-the-query-tools). A column qualified with the table name in an expression (`customers.amount`) no longer resolves on such an expose: write the bare column.
- **`query` refuses an expression that selects redacted columns without naming them.** On an expose with `sensitivity: pii`, `phi` or `sensitive` columns, `COLUMNS(...)`, `IDENTIFIER(...)`, a `*` that stands for columns and the table as a whole-row value are refused in a measure, dimension, metric `filter` or filter key. `count(*)`, arithmetic and `count(DISTINCT col)` still run, and an expression that names a redacted column is redacted as before.
- **`query_sql` reads only the allowed columns.** On an expose that restricts or redacts columns, each reference to the exposed table becomes a projection of the allowed columns, so `SELECT *`, `alias.*` and a whole-row value return only those. Table functions, a quoted file path as a table, the `TABLE` keyword, any other source that is not a plain table, `UNNEST` or `VALUES`, and SQL the parser cannot read are refused. A column written as `schema.table.column` no longer resolves: give the table an alias, or write `table.column`. A `SELECT *` result no longer carries the redacted columns, which it carried with `[REDACTED-PII]` values, or a column the schema does not declare.
- **`query` parenthesises every term of its `WHERE`.** Each term of the `WHERE` is now parenthesised, which changes the text of the compiled `WHERE`. This change also refused a malformed `policy.rowFilters[]` entry. forge-cli #1107, below, replaces that key with `policy.authz.rowFilters`, and an expose that still carries `policy.rowFilters` is refused whole.
- **The Postgres functions that return a whole table, schema, database or query result as XML are refused.** `table_to_xml`, `query_to_xml`, `cursor_to_xml`, every `schema_to_xml*` and `database_to_xml*` function and their `*xmlschema` variants are refused in `query_sql` and in `query` expressions, on every engine. A column or alias that only shares one of those names is unaffected.

*On forge-cli `main`, not yet in a release ([forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106)).*

One change in forge-cli #1106 needs an action: a default `fluid profile` of a table with a date or timestamp column changes its format and its digest. The new flags and the report lines are additive.

- **The profile format moves from 1-1-0 to 1-3-0.** A date or timestamp column with no declared range gets a histogram over the calendar months or years it spans in place of its quartiles on a ladder of years, and each date and timestamp column gains a calendar. A default profile also gains date pairs, a relationship's `dates`, `structural`, `exposure`, `periods` and `per` wherever the contract declares what they need, so more contracts change digest than those with a date column alone. The document therefore names format 1-3-0 even with no date pair or relationship in it, and its digest changes. `fluxsim` 0.10.0 is the first release that reads format 1-3-0, and 0.9 and older refuse it. To act: profile again after upgrading, and pin the new digest wherever the old one was pinned. See [Time and structure statistics](./cli/profile.md#time-and-structure-statistics).
- **`fluid profile` has two new flags.** `--strict` refuses a `--request` before any record is read when the request or the contract alone shows that an ask cannot be formed, with the code `profile_request_not_formed`. `--timings` prints how long each table took to read, measure and check, and a private release refuses it with `profile_timings_with_release`. `--strict` without `--request` is refused with `profile_strict_needs_request`. See [Asks the profile does not form](./cli/profile.md#asks-the-profile-does-not-form-strict) and [Where the time goes](./cli/profile.md#where-the-time-goes-timings).
- **A request's asks that the profile does not form are named.** A `--request` can ask for a workload, a consumer query, a date pair, a calendar, a relationship's dates or an exposure. The asks that were not formed were dropped without a word before. They are now named under `Not measured` (under `Not released` with `--privacy-unit`) with their reason, so the report has these lines where it had none.
- **A parent table publishes one lifetime's exposure.** Every other lifetime's exposure is written withheld whole, with the code `D`. The output-checked tier does not protect across runs, so separate runs that request different lifetimes can be combined.


*On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).*

One change in forge-cli #1107 needs an action: an expose that still declares `policy.rowFilters` is refused. The rest tightens what `query_sql` and the Postgres driver accept.

- **The MCP output port enforces `policy.authz.rowFilters` and no longer reads `policy.rowFilters`.** The gateway read row filters from `policy.rowFilters`, a key no contract schema allows, and served every row of an expose whose row-level security was declared under `exposes[].policy.authz.rowFilters`. It now applies the schema's filters to `sample`, `query` and `query_sql`, and refuses an expose that still carries the old key, on every call and at `serve`. To act: write one `policy.authz.rowFilters` entry, `{principal, where}`, per principal in place of each filter, with the value in the predicate (`tenant_id = 'acme'` for `tenant:acme`), on `fluidVersion: "0.7.6"`. Serve the expose over HTTP with JWT auth and map the claim that carries a caller's principal: `FLUID_MCP_JWT_CLAIM_MAPPING=<claim>=principal`. To check: `fluid validate` accepts the contract, and `fluid mcp output-port serve` starts. See [Row-level security](./advanced/mcp.md#row-level-security-—-policy-authz-rowfilters).
- **`serve` refuses an expose whose row filters no request could satisfy.** Over stdio, over HTTP without auth or with a shared token, and over JWT with no claim mapped to `principal`, it exits 2 and names the fix. A request with no principal that a filter or `policy.authz.readers` names is refused with `RowFilterIdentityMissing`, and a filter that cannot be applied with `RowFilterUnavailable`. A client that states its own `principal` is ignored in every auth mode, and `accessPolicy` grantees are not consulted: a principal must be in `policy.authz.readers` to read every row.
- **`query_sql` on an expose that restricts columns or filters rows reads only the exposed table.** A join with another table, a catalog view and the exposed table's name under another schema or catalog are refused. Read another table through its own expose. On DuckDB, `main` counts as the schema of an unqualified binding, so `main.customers` still reads the exposed table. On an expose with row filters, `query` and `query_sql` read only the columns `contract.schema` declares, as they already did with column restrictions.
- **On every expose, `query_sql`, the `query` expressions and the drivers' statement guard refuse more Postgres functions.** They refuse the functions that run a query given as text, the catalog and statistics functions, the functions that read raw pages or other requests' statements, and `set_config`, and a name or a string written with Unicode escapes. A string literal that contains `u&"` or `u&'` is refused too, and the rule also applies to the contract expressions that the Snowflake planner and the Databricks Genie and metrics emitters read. To check: run the statement and read the refusal. See [Postgres functions that read past the projection](./advanced/mcp.md#postgres-functions-that-read-past-the-projection).
- **Each Postgres request runs in a read-only transaction of its own, rolled back at the end.** A session setting that one request changed no longer stays for the next, and the per-request query timeout takes effect.
- **The `expose.json` and `contract.yaml` resources omit `policy.authz`.** The statement that `query` and `query_sql` return shows `(<row filter>)` in place of the predicate.
- **`fluid generate iac` and `fluid apply` refuse a row filter with a double-quoted column name for BigQuery and Databricks.** Both read the name as a string, so the policy kept every row. Write the name bare. The check also refuses `EXISTS (SELECT ...)`, `HAVING`, `QUALIFY`, `WINDOW`, bind placeholders and an unterminated quote in a predicate, and a `rowFilters` value that is not a list. The emitted policy is otherwise unchanged.
- **sqlglot 26.20 or newer is required.** Older releases record no identifier positions, so the gateway refused every row filter on them, and without sqlglot every row filter is refused.
- **On BigQuery, the gateway's own account must be a grantee of the every-row policy.** `fluid apply` writes `fluid_all_rows` for the members that hold a grant on the expose and that no filter names, and BigQuery shows an account no policy names no rows. Grant the gateway's service account a read permission in `accessPolicy`, and name it in no row filter. To check: call `sample` as a caller whose principal a filter names, and it returns rows.
- **Give the gateway a least-privilege database role.** No superuser, `SELECT` on the exposed tables only, a fixed `search_path` and `default_transaction_read_only` on the role. See [The database role of the gateway](./advanced/mcp.md#the-database-role-of-the-gateway). The error side channel is closed on Postgres only, and timing and planner output are not hidden. See [What a row filter does not cover](./advanced/mcp.md#what-a-row-filter-does-not-cover).

*On forge-cli `main`, not yet in a release ([forge-cli #1108](https://github.com/Agenticstiger/forge-cli/pull/1108)).*

One change in forge-cli #1108 needs no action unless a lock file pins the provider: a fresh Snowflake workspace resolves to provider 2.23.x.

- **The Snowflake provider pin is `~> 2.23.0`, held below 2.24.** The constraint moves from `~> 2.23`. Provider 2.24 reworked the preview `snowflake_table` resource (`column.nullable` became `column.not_null`), which forge does not emit yet, and `tofu validate` refused the table output. What the emitter writes is unchanged. A workspace whose `.terraform.lock.hcl` already holds 2.24 needs `tofu init -upgrade` to move to 2.23.x. See [Snowflake](./providers/snowflake.md).

## Older releases

Upgrading from before `0.15.0`? Start with the
[`0.15.0` checklist](./RELEASE_NOTES_0.15.0.md#upgrade-checklist), then continue from
[From 0.15.x to 0.16](#from-0-15-x-to-0-16). Step 11 there, about federation digests, now
warns instead of failing the apply.
