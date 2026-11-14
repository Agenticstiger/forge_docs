---
title: Upgrading
description: How to upgrade and pin data-product-forge, the checklist for each step from 0.15.x to 0.30.1, and what moving the local engine from DuckDB 1.x to 2.x changes — what breaks, what to do, and how to check it.
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
│ Version: 0.29.0                                                              │
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
pip install "data-product-forge[local]==0.29.0"
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
  |- FLUID_PACKAGE_SPEC default: data-product-forge[local]==0.29.0
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
| `0.30.0` | [Changes in 0.30.1](#changes-in-0-30-1) |
| Anything before `0.24.0`, if you read forge's ODCS or ODPS output | [Read this first if you consume the exported artifacts](#read-this-first-if-you-consume-the-exported-artifacts) (`0.23.0` and `0.24.0`) |
| Anything before `0.23.0`, and any DuckDB upgrade | [DuckDB 1.x to 2.x](#duckdb-1-x-to-2-x) (`0.22.0` and `0.23.0`) |

What is not in any release yet is under [Not in a release yet](#not-in-a-release-yet).

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

## Not in a release yet

*On forge-cli `main`, not yet in a release ([forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879)).*

- **`fluid mcp output-port serve --transport http` speaks MCP Streamable HTTP at `/mcp`. The HTTP+SSE endpoints `/sse` and `/messages/` are gone.** The MCP specification deprecated HTTP+SSE in its 2025-03-26 revision. Point each client at `http://<host>:<port>/mcp` and set its transport to Streamable HTTP, `--transport http` in `claude mcp add` for example. A client still set up for SSE fails: `/sse` answers 404 once a request passes auth, and at `/mcp` its `GET` gets 400 (`Missing session ID`). Behind the shipped proxy templates the URL becomes `https://<your domain>/mcp`, and their settings for streamed responses stay as they are.
- **An MCP server without auth no longer listens beyond loopback.** A `--host` other than `127.0.0.0/8`, `::1` or `localhost` now stops at startup, with exit 2 and the fix, when auth is off: the default `shared-token` mode with no `FLUID_MCP_AUTH_TOKEN`, `jwt` without its three settings, or `FLUID_MCP_AUTH_MODE=none`. Up to 0.30.1 the output port warned and served. Off loopback, a shared token must also be at least 32 characters: `openssl rand -hex 32` makes one.
- **Without auth, a request's `Host` must be `127.0.0.1`, `localhost` or `[::1]` (or the bound address) with a port, or it gets 421.** So a gateway behind a reverse proxy that forwards its public name needs `FLUID_MCP_AUTH_TOKEN` (or `jwt`) set on the gateway itself.
- **A browser request from a page not served from this machine gets 403**, with or without auth: an `Origin` that is not `http` or `https` on a loopback host, `Origin: null` included. With auth off, the `Origin` must also be `127.0.0.1`, `localhost` or `[::1]` (or the bound address) with a port. Clients that are not browsers send no `Origin` header and are not affected.
- **`fluid mcp serve` gains `--transport http`**, which serves the authoring tools the same way, by default at `http://127.0.0.1:8766/mcp`. stdio stays the default. See [Serve over HTTP](./cli/mcp.md#serve-over-http).

*On forge-cli `main`, not yet in a release ([forge-cli #880](https://github.com/Agenticstiger/forge-cli/pull/880)).*

- **`fluid validate --strict` fails on placeholder emails, starter-template values and TODO markers, on an SDP build that joins, and on an SDP that consumes a product whose type the workspace cannot read.** Each is a new warning, so `fluid validate` without `--strict` still passes. A CI job that runs `--strict`, stage 2 of a generated pipeline among them, now fails on a contract that still has an owner email at `example.com` or `company.com`, a `TODO`, or the values of an unedited template: a contract scaffolded from a template (`fluid init --quickstart`, `fluid init --template`, `fluid forge --template`) has a placeholder owner email until you edit it. Replace each value with the real one, or delete an optional key such as `metadata.owner.email`. See [Placeholders and starter values](./cli/validate.md#placeholders-and-starter-values) and [What an SDP does not do](./cli/validate.md#what-an-sdp-does-not-do).
- **`fluid validate --format json` adds `issues`, with a code, a JSON pointer, a fix and an example for each finding.** It is there only when there is a finding, and `errors`, `warnings` and `notes` are unchanged. A bundle's `CONTRACT-RULE` findings gain `rule`, `pointer`, `fix`, `example` and `docs_url`. See [Finding codes and `issues`](./cli/validate.md#finding-codes-and-issues).

*On forge-cli `main`, not yet in a release ([forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881)).*

- **`fluid forge` AI mode runs on the four FLUID Agent Skills, and the embedded copilot is removed.** With a coding agent and a terminal, forge opens the agent in the workspace with the skills loaded; with no terminal, it drives Claude Code headless, and Codex, Cursor and Kiro take the one-call path. Without a coding agent, it makes one LLM call with the skills' text and sends `fluid validate --offline` errors back, for at most 3 attempts. AI mode no longer overwrites a contract: use `--refine` to change one. A run with no terminal needs `--context`, and `--forge-agent-mode` defaults to `agentic`. See [AI mode on forge-cli main](./cli/forge.md#ai-mode-on-forge-cli-main).
- **`fluid memory`, `fluid mission`, `fluid stats --judge`, `fluid init --agent`, `fluid init --show-work` and 30 `fluid forge` flags are removed.** A command that still passes one fails with exit 2. Take it out: [Removed flags](./cli/forge.md#removed-flags) lists each forge flag with what to use instead. `fluid forge --no-memory` is still accepted and ignored.
- **`fluid mcp serve` loses five tools.** `forge_run`, `forge_from_source`, `score_contract_quality`, `enrich_contract_suggestions` and `search_semantic_memory` are removed, and so is `--llm-provider mcp-sampling`. Take them out of `--allow-tools` and `--deny-tools` lists and agent instructions. See [Authoring tools](./advanced/mcp.md#authoring-tools).
- **The store's `postgres` and `vector` backends and the `[vector]` extra are removed.** `FLUID_STORE_BACKEND=postgres` or `vector` logs a warning and uses the file store, and `fluid doctor` asks you to unset it. Drop `[vector]` from install specs.
- **Variables only the copilot read are ignored**, among them `FLUID_PROMPT_PROFILE`, `FLUID_PROMPT_OVERLAYS`, `FLUID_AGENT_WEB_TOOLS`, `FLUID_FORGE_AUTO_RESUME`, `FLUID_INTERVIEW_LEGACY` and `FLUID_LLM_FALLBACK_CHAIN`. [Environment variables](./advanced/environment-variables.md) marks each one.
- **`fluid forge data-model` is unchanged.** Every subcommand and flag stays, `--tiered` and the routing-model flags included, and so does `fluid stats --json`. Command Center's `from-intent` path, with `--deterministic` or `--llm-provider`, runs on them as before.

*On forge-cli `main`, not yet in a release ([forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884)).*

- **`fluid mcp serve` reads source catalogs with one tool, `source_catalog`, and serves 7 tools.** `list_source_adapters`, `list_source_tables`, `inspect_source_table`, `list_source_lineage` and `list_source_glossary` are now `source_catalog` with `kind` set to `adapters`, `tables`, `table`, `lineage` or `glossary`. The other arguments keep their names, and no alias keeps the old tool names: rename the calls in agent instructions and scripts. Every result names its `kind`, and a `table` or `lineage` result now sits under it, as in `{"kind": "table", "table": {...}}`. A result is `concise` unless the call asks for `"response_format": "detailed"`, which returns every field, as the five tools did. See [`source_catalog`](./advanced/mcp.md#source-catalog).
- **An unknown tool name in `--allow-tools` or `--deny-tools` stops `fluid mcp serve` with exit 2.** A name that is not a tool now fails at startup: a typo, one of the five tools, or a tool that [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881) removed. In 0.30.1 those tools were still served, and a typo was ignored. Replace the five names with `source_catalog`. An IDE config that an older `fluid scaffold-ide` wrote lists the five old tools under `autoApprove`, so the client does not auto-approve `source_catalog`: add it to the list by hand, or run `fluid scaffold-ide --force`, which writes the scaffold's files again over any edits. See [Access controls](./cli/mcp.md#access-controls).
- **A result estimated at more than 6,000 tokens comes back as a resource.** The call returns a short envelope and a `resource_link` to `fluid://artifacts/<id>`, which the client reads with `resources/read`. Over stdio the envelope also names a file holding the same JSON. A client that reads only a result's text sees the envelope where it used to see the result. `FLUID_MCP_INLINE_TOKEN_LIMIT=0` keeps every result inline. See [Large results](./advanced/mcp.md#large-results).
- **A catalog listing with a scope now works through an MCP client.** On MCP SDK 2.x, `list_source_tables` (now `source_catalog` with `kind` set to `tables`) and a scoped `list_source_glossary` failed with `Error executing tool` for an ordinary scope such as `{"database": "DB", "schema": "SALES"}`: the server sent the scope's unset `tables` back as `null`. Unset fields are now left out.

## Older releases

Upgrading from before `0.15.0`? Start with the
[`0.15.0` checklist](./RELEASE_NOTES_0.15.0.md#upgrade-checklist), then continue from
[From 0.15.x to 0.16](#from-0-15-x-to-0-16). Step 11 there, about federation digests, now
warns instead of failing the apply.
