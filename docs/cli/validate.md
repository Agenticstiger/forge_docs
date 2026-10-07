# `fluid validate`

Check a contract against the FLUID schema and the provider-, governance- and policy-aware rules the CLI runs before anything is planned or applied. It validates local files, so it is the cheapest place to find a problem before `fluid plan` or `fluid apply` runs.

## Syntax

```bash
fluid validate [CONTRACT] [options]
```

`CONTRACT` is a contract file (`contract.fluid.yaml` or `.json`) or a `.tgz` bundle built by [`fluid bundle`](./bundle.md). It is optional: [without it](#validating-without-a-contract-path), the command looks for a workspace or for a `contract.fluid.yaml` in the current directory.

## Examples

Validate one contract:

```bash
fluid validate contract.fluid.yaml
```

```text
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.017s
```

A contract that breaks a rule prints each finding and exits `1`:

```text
❌ Invalid FLUID contract (2 error(s)) (schema v0.7.6)
Validation completed in 0.001s

Validation Errors:
==================
 1. exposes[customers] accessPolicy: principal 'group:analysts@northwind.example' resolves to 'group:analysts@northwind.example', a placeholder: ...
 2. exposes[exports] is a GCP gcs_bucket binding and declares lifecycle.expire, which the GCP emitter applies only to BigQuery tables. It would not be enforced. Move the policy to a BigQuery table expose, or remove it from this one.
```

*(forge-cli fix/iceberg-catalog-followups, unreleased)* A finding prints its square brackets, so each one names its expose: `exposes[customers]`. forge-cli 0.19.0 and earlier read bracketed text as console markup and dropped it, so the same findings print as `exposes accessPolicy: ...` and `exposes is a GCP gcs_bucket binding ...`, and a [bundle finding](#validating-a-bundle-tgz) loses its `[error]` or `[warning]` severity. `--format json` was not affected. Since the fix, a finding is printed on one line and the terminal wraps it.

More invocations:

```bash
fluid validate contract.fluid.yaml --env prod             # validate the prod overlay applied to the base
fluid validate contract.fluid.yaml --strict               # warnings become errors
fluid validate contract.fluid.yaml --schema-version 0.7.2 # validate against a specific schema
fluid validate contract.fluid.yaml --format json          # machine-readable result
fluid validate runtime/bundle.tgz                         # validate a bundle
```

For a single contract, `--format json` prints `valid`, `schema_version`, `errors`, `warnings` and `validation_time`. For a `.tgz` bundle it prints the same report `--report` writes (`bundleDigest`, `input`, `strict`, `status`, `summary`, `issues`).

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The contract is valid (and, with `--strict`, has no warnings). |
| `1` | The contract has errors; or `--strict` and it has warnings; or the file was not found or could not be loaded, including an `--env` that [expected-environments refuses](#env-and-environment-overlays). A `.tgz` bundle that fails also exits `1`. |
| `2` | A `--min-version` or `--max-version` constraint was not met, or a bundle could not be read. |

A failure prints a stable `[ERR_<EVENT>]` slug, such as `[ERR_VERSION_BELOW_MINIMUM]` for exit `2`. Most also print suggestions and a documentation link.

## Options

| Option | Description |
| --- | --- |
| `--env ENV` | Apply the `ENV` overlay to the base contract before validating. See [`--env` and environment overlays](#env-and-environment-overlays) and [Environments and overlays](../concepts/environments-and-overlays.md). |
| `--schema-version VERSION` | Validate against this schema version, for example `0.7.6`, instead of the version the contract declares. |
| `--min-version CONSTRAINT` | Fail with exit `2` when the contract's version does not satisfy the constraint, for example `'>=0.7.5'`. |
| `--max-version CONSTRAINT` | Fail with exit `2` when the contract's version does not satisfy the constraint. |
| `--strict` | Treat warnings as errors. |
| `--offline` | Use only cached or bundled schemas. |
| `--force-refresh` | Refresh cached schemas. |
| `--clear-cache` | Clear the schema cache first. |
| `--cache-dir CACHE_DIR` | Use a custom schema cache directory. |
| `--verbose`, `-v` | Detailed validation output. |
| `--quiet`, `-q` | Minimal output. |
| `--format {text\|json}` | Output format. Default `text`. |
| `--list-versions` | List the available schema versions and exit. |
| `--show-schema` | Show the schema used for validation. |
| `--probe` | Accepted and ignored. See [`--probe`](#probe-is-accepted-and-does-nothing). |
| `--report PATH` | Write the structured report of a `.tgz` bundle validation to `PATH`, in addition to stdout. A single contract writes no report file; see [Validating a bundle](#validating-a-bundle-tgz). |
| `--fail-fast` | When validating a `.tgz` bundle, stop at the first error. The default collects every finding, so one bad file does not hide the others. Warnings and infos never stop the traversal. No effect on a single contract. |

## Validating without a contract path

Run `fluid validate` with no argument and it first looks for a workspace: a directory above you that holds `fluid.workspace.yaml`. If it finds one with products in it, it validates each product and prints one line per product:

```bash
fluid validate
```

```text

Validating 1 product in workspace 'proj'...

  ✅ proj                 valid (0.7.5)

All 1 product valid.
```

When there is no workspace, it validates `contract.fluid.yaml` in the current directory. With neither, it fails with `contract_required`.

::: warning The workspace form runs the schema check only
As of 0.18.1, the per-product check in workspace mode is JSON Schema validation. It does not run sovereignty and agent-policy checks, the rules described in [Governance binding checks](#governance-binding-checks-since-0-17-0), the Iceberg and GCP binding checks, packaging, semantics, composition or plugin validators, and it ignores `--probe`, `--report`, `--format json`, `--min-version`, `--max-version` and `--schema-version`. `--strict`, `--offline` and `--env` are honored, and a failing product prints only its first three errors. The contract from the first example on this page, placed in a workspace as `gov/contract.fluid.yaml`, fails with two errors when you pass its path, and the workspace form reports it valid:

```text
$ fluid validate gov/contract.fluid.yaml
❌ Invalid FLUID contract (2 error(s)) (schema v0.7.6)
...

$ fluid validate

Validating 1 product in workspace 'ws3'...

  ✅ gov                  valid (0.7.6)

All 1 product valid.
```

In a workspace, give `fluid validate` the path of each contract you want fully checked. This includes any CI job that gates on `--min-version` or `--max-version`: in the workspace form those flags do nothing and the job passes.
:::

## `--env` and environment overlays

`--env ENV` merges `overlays/ENV.yaml` (or one of the other overlay file names the loader accepts) over the base contract and validates the result. How a missing overlay is handled depends on the environment name and on the workspace:

| Situation | Result |
| --- | --- |
| `--env dev`, no `dev` overlay | An `overlay_base_env` notice. `dev` is the base by convention, so validation continues on the base contract. |
| `--env gcp`, no `gcp` overlay | A warning, `overlay_not_found`, naming the overlays that do exist and the platform the base is bound to. Validation continues on the **base** contract unchanged. |
| `--env gcp`, no overlay, and `fluid.workspace.yaml` lists `gcp` under `expected-environments` for this product | The command fails with exit `1`. |

The warning for a missing overlay:

```text
overlay_not_found: --env 'gcp' matched no overlay for /path/to/solo/contract.fluid.yaml, so the BASE contract is used unchanged (it binds to local, not to 'gcp'). Overlays that exist: none. Add an overlay for it under overlays/ or pass one of the existing environments.
✅ Valid FLUID contract (schema v0.7.5)
```

The warning is a log line, not a validation warning, so it does not fail the run even with `--strict`: `fluid validate contract.fluid.yaml --strict --env gcp` prints it and exits `0`. A mistyped environment name therefore validates cleanly against the base contract. To make a missing overlay a hard error, declare the environments each product is deployed to in the workspace's `fluid.workspace.yaml`:

```yaml
# fluid.workspace.yaml
expected-environments:
  solo: [dev, gcp]       # the product's directory name (or its contract id), then its environments
```

With that in place, `--env gcp` without an overlay is refused:

```text
❌ Validation error: contract_load_failed
   error: --env 'gcp' has no overlay, but fluid.workspace.yaml expected-environments (solo) declares 'gcp' an environment of this product, so the base contract (bound to local) would be used as if it were 'gcp'. Add overlays/gcp.yaml, or remove 'gcp' from fluid.workspace.yaml expected-environments (solo)
   [ERR_CONTRACT_LOAD_FAILED]
```

Two environments are exempt from the refusal: `dev`, and an environment whose name equals a platform the base contract is already bound to (`--env local` on a contract bound to `local`). The second still draws the `overlay_not_found` warning. A contract's own `environments` block does not refuse: it is schema-valid, the CLI applies nothing from it, and the warning says so when the name appears there.

The check lives in the contract loader, which `plan`, `apply`, `verify` and `publish` also use: `fluid apply --env prod` on a contract with no `prod` overlay prints the same warning. See [Per-environment overlays](../recipes/per-environment-overlays.md).

## Contracts split into fragments

A root contract can pull objects from other files with `$ref`. `fluid validate` resolves the pointers before it checks anything, so you pass the root file and validate the whole product. A `$ref` may only name a file inside the contract's own directory tree. One that climbs out of it is refused:

```text
❌ Validation error: contract_load_failed
   error: $ref '../shared-builds/customer_360_pipeline.yaml' at JSON pointer '/builds/0' in /path/to/esc/product/contract.fluid.yaml escapes the ref root /path/to/esc/product (after resolving '..' and symlinks); refs may only name files inside it. To compose fragments from a wider tree (e.g. a monorepo's shared/ directory), set FLUID_REF_ROOT to that directory or pass ref_root= to the loader; see docs/contract-refs.md.
   [ERR_CONTRACT_LOAD_FAILED]
```

The suggestions printed under the slug (check the YAML syntax, file permissions) are generic and do not apply to a refused `$ref`. The error line above them is the diagnosis. How the ref root works, and how to widen it for a monorepo, is in [Composing a contract with `$ref`](../concepts/contract-refs.md).

## Schema versions: stable and preview

The CLI bundles several schema versions; [`fluid version`](./version.md) lists them and says which are preview. `fluid validate --list-versions --offline` prints the bundled ones:

```text
Available FLUID Schema Versions:
==================================
  ...
  0.7.1 (bundled)
  0.7.2 (bundled)
  0.7.3 (bundled)
  0.7.4 (bundled)
  0.7.5 (bundled)
  0.7.6 (bundled)
```

A schema version you fetched into the cache earlier is listed too, marked `(cached)`.

| Version | Status |
| --- | --- |
| `0.7.5` | Latest **stable**. A contract with no `fluidVersion` is validated against it. |
| `0.7.6` | **Preview.** It validates only when a contract declares `fluidVersion: "0.7.6"` or you pass `--schema-version 0.7.6`; it is never chosen automatically. |

The fields that need `0.7.6` include `lifecycle.expire`, `binding.encryption.kms`, `binding.principals`, `packaging`, and `upstreamWorkspace` / `upstreamDigest`. A contract that declares `0.7.5` and uses one of them fails with an error such as `exposes[1].lifecycle: Additional properties are not allowed ('expire' was unexpected)`.

`--schema-version` overrides what the contract declares, which lets you test a contract against a newer schema without editing it. `--min-version` and `--max-version` bound the schema version being validated and fail with exit `2` when it falls outside them.

## Governance binding checks (since 0.17.0)

`fluid generate iac`, `fluid plan` and `fluid apply` refuse a contract whose governance a cloud binding cannot apply. `fluid validate` runs the same derivations and reports each refusal at validation time, with the same message:

- **An unmapped or placeholder principal.** When a binding carries `binding.principals`, every principal the contract names for that expose must be mapped to a real identity, or to `[]` for "no identity on this cloud". Without the map, a principal on GCP that is a placeholder (a reserved top-level domain such as `.example`, or not an IAM member at all) is refused.
- **A column restriction nothing enforces.** On AWS, a `columnRestrictions` entry on a binding with no Lake Formation grants. On GCP, one on an expose with no reader to restrict.
- **A key reference for the wrong cloud.** A Cloud KMS key on an AWS binding, or an AWS key on a GCP binding.
- **Retention or encryption on a GCP target that is not a BigQuery table.** A Cloud Storage bucket, a Pub/Sub topic or Iceberg storage cannot carry `lifecycle.expire` or `binding.encryption.kms`.

The two errors in the example at the top of this page come from this check. A principal ending in `.example` fails on GCP until an overlay's `binding.principals` maps it to a real group, and `lifecycle.expire` on a Cloud Storage expose fails because only BigQuery tables apply it.

AWS has one warning of its own: `accessPolicy.grants` on a contract whose AWS binding declares no `governance.lakeFormation.grants`, where the access intent is not enforced.

Each message names its remedy. How the fields work, and what `fluid apply` emits for them on each cloud, is in [Governance](../advanced/governance.md), the [GCP provider](../providers/gcp.md) and the [AWS provider](../providers/aws.md).

## Validating a bundle (`.tgz`)

Pass a bundle built with `fluid bundle --format tgz` and `fluid validate` checks the bundle itself and the contract inside it:

```bash
fluid validate runtime/bundle.tgz
```

```text
✅ Bundle pass: /path/to/proj/runtime/bundle.tgz
   digest: sha256:c86cb86ccfd50fc12f934c329db845b4248d1ed6a9074aab5195b6879ebecae0
   issues: 0 total (0 error, 0 warning, 0 info)
```

What it checks:

- **The manifest.** The recorded hash of each file must match the bundle. A mismatch is a single `MANIFEST-TAMPER` error, and nothing else is checked.
- **The files in the bundle.** The resolved contract against the JSON Schema, SQL fragments with a SQL parser, and OpenAPI fragments with an OpenAPI validator. When the SQL parser or the OpenAPI validator is not installed, those fragments are reported as an info (an error under `--strict`) instead of being checked.
- **The contract rules.** The resolved contract goes through the same rules a contract file does: sovereignty, agent policy, binding prerequisites, packaging, semantics, composition and plugin validators. Each finding is reported with code `CONTRACT-RULE`.
- **The environment.** `--env` must match the environment the bundle was built for.

A bundle is never re-overlaid, so a mismatched `--env` is an error, `BUNDLE-ENV-MISMATCH`, and exits `1`:

```bash
fluid validate runtime/bundle.tgz --env prod
```

```text
❌ Bundle fail: /path/to/proj/runtime/bundle.tgz
   digest: sha256:c86cb86ccfd50fc12f934c329db845b4248d1ed6a9074aab5195b6879ebecae0
   issues: 1 total (1 error, 0 warning, 0 info)
   [error] bundle-env: MANIFEST.json: the bundle was built for env 'dev' but this stage was asked for env 'prod'. A bundle is never re-overlaid; rebuild it with `fluid bundle <contract> --env prod --format tgz`, or pass the env it was built for.
```

A bundle built from the governance example above fails on its contract rules, the same two errors as validating the file:

```text
❌ Bundle fail: /path/to/gov.tgz
   digest: sha256:f90911539a301cc3e358ce272e57836d80bac2c93aeb52e85851787bce58f2f3
   issues: 2 total (2 error, 0 warning, 0 info)
   [error] contract: contract.resolved.yaml: exposes[customers] accessPolicy: principal 'group:analysts@northwind.example' resolves to ...
   [error] contract: contract.resolved.yaml: exposes[exports] is a GCP gcs_bucket binding and declares lifecycle.expire, ...
```

`--report PATH` writes the full structured report as JSON, on pass and on fail, so a CI job can upload it as an artifact. The report has `bundleDigest`, `input`, `strict`, `status`, `summary` and `issues[]`; each issue carries `file`, `validator`, `severity`, `message` and a `code`. The `BUNDLE-ENV-MISMATCH` finding is written to the report like any other. `--report` has an effect only for a `.tgz` bundle: `fluid validate contract.fluid.yaml --report out.json` writes no file as of 0.18.1.

Codes you will meet in a report:

| Code | Raised when |
| --- | --- |
| `MANIFEST-TAMPER` | A file's hash does not match the manifest. |
| `BUNDLE-ENV-MISMATCH` | `--env` differs from the environment the bundle was built for. |
| `CONTRACT-RULE` | A contract rule failed or warned on the resolved contract. |
| `CONTRACT-LOAD` | The resolved contract inside the bundle could not be loaded. |
| `RESOLVED-PARSE` | The resolved contract could not be parsed. |
| `BUNDLE-UNEXPECTED` | The bundle holds a file that is not a recognised entry (a warning). |
| `SQL-JINJA` | A SQL fragment contains Jinja markers, which the SQL parser cannot read. |
| `OAS-REF-EXTERNAL` | A bundled OpenAPI fragment has a `$ref` that leaves its own document. A fragment in a bundle has no directory of its own, so only `#/...` pointers within it are allowed. See [OpenAPI fragments inside a bundle](../concepts/contract-refs.md#openapi-fragments-inside-a-bundle). |

## Iceberg prerequisite checks (since 0.14.0)

The Snowflake and GCP IaC emitters are *emit-when-derivable*: an `iceberg` expose whose binding is missing a required input used to produce no `EXTERNAL VOLUME`, no catalog integration, and no GCS bucket — nothing failed at `fluid apply`, and the gap only surfaced at `dbt run` when the warehouse rejected the write.

Since `0.14.0`, `fluid validate` reports the skip branches of those emitters as validation **errors that name the missing field**, for example:

- **Snowflake-managed (Horizon) tables** — need `binding.location.warehouse` (`s3://` or `gs://`) or `binding.location.bucket`; an S3-backed `EXTERNAL VOLUME` additionally needs `binding.location.iam_role_arn`.
- **Glue-cataloged tables** — need `binding.location.iam_role_arn` and `binding.location.account` so FLUID can create the Snowflake `CATALOG INTEGRATION`.
- **Volume overrides** — an explicit `binding.icebergConfig.properties.external_volume` must be a legal Snowflake identifier, and two exposes that derive the same volume name but point at different storage are rejected (one expose's data would land in the other's bucket).
- **BigQuery Iceberg tables** — need `binding.location.bucket` or a `gs://` `binding.location.warehouse` that names a bucket.

The emitters themselves are unchanged — the validator is the loud half. See the Iceberg sections of the [Snowflake provider](../providers/snowflake.md) and [GCP provider](../providers/gcp.md) guides for what each emitter provisions.

::: warning Behavior change under `--strict` in 0.14.0
A Snowflake Iceberg catalog that authenticates with a secret — `polaris`, `unity`, `rest` / `iceberg_rest`, `nessie` — is *understood but not emitted*: its `CATALOG INTEGRATION` needs an OAuth secret or bearer token, and the emitted OpenTofu module is credential-free. `fluid validate` now surfaces that as a warning, and because `--strict` promotes warnings to errors, **CI pipelines running `fluid validate --strict` on such contracts start failing on `0.14.0`**. Either run those contracts without `--strict`, or create the catalog integration out of band and take the secret-authenticated catalog out of the contract binding.
:::

With [forge-cli #707](https://github.com/Agenticstiger/forge-cli/pull/707) (unreleased), the warning also covers `lakekeeper` and `bigquery`, and a `hive`, `jdbc`, `hadoop` or `dynamodb` catalog on Snowflake is an error. See [Iceberg catalog checks](#iceberg-catalog-checks).

## Iceberg catalog checks

::: warning Not in a release yet
These checks come with [forge-cli #707](https://github.com/Agenticstiger/forge-cli/pull/707), which no release includes yet, and with the follow-up fixes in forge-cli fix/iceberg-catalog-followups, marked *(forge-cli fix/iceberg-catalog-followups, unreleased)*.
:::

`binding.location.catalog` names the Iceberg catalog that owns an expose's table, and every emitter now reads it through one table. [Iceberg catalogs](../advanced/source-aligned-acquisition.md#iceberg-catalogs-location-catalog) has that table, how spellings fold, and a worked Lakekeeper example. `fluid validate` refuses a contract whose catalog the emitters would disagree about:

- **An unknown catalog.** A `location.catalog` outside the table, on an Iceberg expose, is an error that lists the accepted spellings. On `platform: confluent` every value other than `glue` is an error instead, because the Tableflow module publishes only to AWS Glue.
- **A streaming sink that cannot reach its catalog.** For a Kafka Connect build, or an embedded Debezium Server build, that writes an Iceberg expose:
  - every REST catalog (`rest`, `lakekeeper`, `polaris`, `unity`), `nessie` and `snowflake-managed` needs `location.uri` and `location.warehouse`; `jdbc` needs `uri`, and `hadoop` needs `warehouse`. On 0.19.0 and earlier only the literal `rest` was checked.
  - a `sink.catalog` that names another catalog than the expose is an error, because dbt and the modules read only the expose.
  - an `iceberg_catalog_overrides` entry or a hand-written sink config that would leave the connector with both `type` and `catalog-impl` is an error, because Apache Iceberg refuses that catalog and the sink never starts.
  - `nessie` on a `kafka-connect` build is a warning: the stock Apache Iceberg Kafka Connect runtime has no Nessie client.
  - *(forge-cli fix/iceberg-catalog-followups, unreleased)* `bigquery` on a `kafka-connect` build is a warning: the sink config sets `iceberg.catalog.type=bigquery`, which the published Apache Iceberg Kafka Connect sink (1.9.2) cannot load; Iceberg adds the type in 1.10. This warning and the Nessie one follow the catalog type that reaches the worker, so a hand-written `sink_connector_config` that sets `iceberg.catalog.type: rest` draws neither.
  - *(forge-cli fix/iceberg-catalog-followups, unreleased)* on `platform: gcp`, an Iceberg expose the build writes must name its `location.catalog`, or it is an error: the sink would write through a REST catalog while dbt-bigquery and the GCP module create a BigLake table. See [How a value is read](../advanced/source-aligned-acquisition.md#how-a-value-is-read).
- **Snowflake.** On `platform: snowflake`, a catalog that Snowflake reaches over Iceberg REST (`rest`, `lakekeeper`, `polaris`, `unity`, `nessie`, `bigquery`) draws the warning described above, which `--strict` turns into an error. `hive`, `jdbc`, `hadoop` and `dynamodb` are an error, because Snowflake has no catalog integration for them. A `lakekeeper` expose is no longer asked for an `s3://` or `gs://` warehouse, and two `catalog: snowflake` exposes that derive one EXTERNAL VOLUME on different storage are caught here rather than failing `fluid apply` mid-emit.
- **AWS.** An Iceberg expose in a catalog other than Glue cannot carry `governance.lakeFormation`, `policy.authz.columnRestrictions` or `policy.authz.rowFilters`: each is refused by catalog name. `accessPolicy.grants` on it draws a warning to grant access in that catalog. See [On AWS](../advanced/source-aligned-acquisition.md#on-aws-a-table-in-another-catalog). *(forge-cli fix/iceberg-catalog-followups, unreleased)* An unknown catalog value draws only the unknown-catalog error, not these refusals as well.
- **GCP.** A `platform: gcp` expose in a catalog other than `bigquery` may give the catalog's warehouse name; a warehouse in another object store (`s3://`, `abfss://`) is an error.

A crash inside the Iceberg sink, Confluent or Iceberg prerequisite check now fails validation, with an error such as `Iceberg sink check could not run (...); the contract was NOT checked for streaming-sink defects`. On 0.19.0 and earlier the crash was printed only with `--verbose`, and the contract passed unchecked.

The Kafka Connect runner and the embedded Debezium Server runner run the same streaming-sink checks before they create anything, so a contract that skipped `fluid validate` still fails before any Connect REST call or `application.properties` write. *(forge-cli fix/iceberg-catalog-followups, unreleased)* That holds for a build that declares `sink.format: iceberg`, with a derived or a hand-written sink config, and for an embedded Debezium Server build that derives its sink. On #707 alone a hand-written config was not checked by the runners. [What each kind produces](../advanced/source-aligned-acquisition.md#what-each-kind-produces) lists the builds.

## GCP binding checks (since 0.15.0)

The GCP IaC emitter is *emit-when-derivable*, so a `platform: gcp` expose it cannot resolve to a BigQuery / Cloud Storage / Pub-Sub target emits nothing and says nothing. Since `0.15.0`, `fluid validate` reports those exposes — resolved through the **emitter's own** dispatch, so the gate can neither block a contract that would have emitted nor wave through one that emits nothing.

The error/warning split is deliberate, because `fluid validate` runs for contracts that never reach `fluid generate iac`:

- **Error** — a `format` that *names* a GCP container while omitting the `binding.location` key that container needs. In practice, `format: gcs_file` with no `location.bucket`.
- **Warning** — everything else that resolves to nothing, including the `other` escape hatch. [A resource-free module is itself a hard failure](./generate-iac.md#a-resource-free-module-is-an-error-since-0-15-0) at the stage that actually needs the resource, so the loud stop is already in the right place and this only has to explain it early.

Formats with no `hashicorp/google` resource by design stay silent (`http_api`, `grpc_api`, `kafka_topic`, a store on another platform), and Iceberg exposes are left to the Iceberg gate above, which owns a more specific message for the same input.

## Schema dialect (since 0.15.0)

Since `0.15.0`, every schema is validated with the dialect it declares instead of with a pinned `Draft7Validator` — and Draft 7 ignores keywords it does not recognise rather than rejecting them, so any constraint expressed in a newer keyword was silently dropped.

**`fluid validate` on a contract behaves identically today.** The bundled FLUID schemas declare 2020-12 but have so far used only `$defs`, which Draft 7 resolves as an ordinary JSON pointer; the example contracts validated identically either way. The observable effect of the fix is on [`fluid validate-artifacts`](./validate-artifacts.md#schema-dialect-since-0-15-0), where the vendored ODCS v3.1.0 schema declares 2019-09 and guards objects with `unevaluatedProperties: false`.

One thing did change on this path, in the fail-safe direction: `schema_manager`'s `jsonschema` probe no longer names the unused `Draft7Validator` or the deprecated `RefResolver`. An `ImportError` in that probe sets `JSONSCHEMA_AVAILABLE = False`, which makes contract validation **skip** rather than error — so the day a `jsonschema` release drops `RefResolver`, the probe would have quietly disabled validation across the CLI.

<a id="probe-—-live-external-connectivity-checks"></a>

## `--probe` is accepted and does nothing

As of 0.18.1, `--probe` is parsed and never read. The help text promises live probes for acquisition contracts (secret resolution, source connectivity, image-signature presence, a schema fingerprint against a baseline), but no code runs them. `fluid validate --probe` returns the same result and exit code as `fluid validate`, even when a declared source is unreachable.

Here, with the `source-aligned-postgres-duckdb` example from the forge-cli repository and `PGHOST` set to an address with no listener:

```bash
PGHOST=10.255.255.1 fluid validate contract.fluid.yaml --probe
```

```text
✅ Valid FLUID contract (schema v0.7.3)
Validation completed in 0.007s
```

`fluid validate` never raises `ConnectivityProbeError`. In 0.18.1 only [`fluid init --discover`](./init.md) raises it (see [Connectivity and secrets](../advanced/typed-cli-errors.md#connectivity-secrets)), when it cannot reach the source it was asked to introspect. Do not read a passing `fluid validate --probe` as evidence that a source is reachable. Test the connection with the source's own client, or run `fluid init --discover <uri>` against it.

## Notes

- A contract can declare an older schema than the CLI's newest. A contract with `fluidVersion: 0.7.2` still validates on a current CLI because the older schemas stay bundled. Schema `0.7.5` is the latest stable version; `0.7.6` is a preview.
- *(since 0.15.0)* `fluid validate` shares its sovereignty checker with [`fluid plan --check-sovereignty`](./plan.md#sovereignty-gate-since-0-15-0), and `sovereignty.enforcementMode` now decides severity in both directions: a `strict` contract whose binding region resolves outside its declared `jurisdiction` newly **fails** with exit 1, and an `advisory` contract that failed now only warns. Full table, and the region-table derivation that changes verdicts on contracts nobody edited: [Governance → Sovereignty enforcement modes](../advanced/governance.md#sovereignty-enforcement-modes-since-0-15-0).
- For routine use, `fluid validate contract.fluid.yaml` is enough. Reach for the schema flags when you are debugging compatibility or working across versions.

## Extension point: custom validators

`fluid validate` runs any `Validator` plugin discovered through Python entry-points (since `0.8.3`). After `pip install <some-validator-plugin>`, the validator's findings appear in `fluid validate` output alongside the core schema validation.

This is how teams enforce governance rules (every Gold product MUST declare a steward, every contract MUST have a cost-center label, etc.) without forking the CLI.

- Author a validator: [SDK & Plugins → Custom validator journey](../sdk-and-plugins/journeys/custom-validator.md)
- Reference: [Entry points → `fluid_build.validators`](../sdk-and-plugins/reference/entry-points.md)
- Example: [`steward-validator`](../sdk-and-plugins/examples/steward-validator.md)
