# `fluid validate`

Check a contract against the FLUID schema and the provider-, governance- and policy-aware rules the CLI runs before anything is planned or applied. It validates local files, so it is the cheapest place to find a problem before `fluid plan` or `fluid apply` runs.

## Syntax

```bash
fluid validate [CONTRACT] [options]
fluid validate --fragment KIND FILE [options]
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

*([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* A finding prints its square brackets, so each one names its expose: `exposes[customers]`. forge-cli 0.19.0 and earlier read bracketed text as console markup and dropped it, so the same findings print as `exposes accessPolicy: ...` and `exposes is a GCP gcs_bucket binding ...`, and a [bundle finding](#validating-a-bundle-tgz) loses its `[error]` or `[warning]` severity. `--format json` was not affected. Since the fix, a finding is printed on one line and the terminal wraps it.

More invocations:

```bash
fluid validate contract.fluid.yaml --env prod             # validate the prod overlay applied to the base
fluid validate contract.fluid.yaml --strict               # warnings become errors
fluid validate contract.fluid.yaml --schema-version 0.7.2 # validate against a specific schema
fluid validate contract.fluid.yaml --format json          # machine-readable result
fluid validate runtime/bundle.tgz                         # validate a bundle
fluid validate --fragment expose fragments/exposes/orders.yaml  # one fragment on its own
```

For a single contract, `--format json` prints `valid`, `schema_version`, `errors`, `warnings` and `validation_time`. A [fragment run](#validating-one-fragment) adds a `fragment` field after `valid`, naming the kind (`"fragment": "expose"`); the JSON of a whole-contract run has no such field. For a `.tgz` bundle it prints the same report `--report` writes (`bundleDigest`, `input`, `strict`, `status`, `summary`, `issues`).

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
| `--fragment KIND` | Validate the file as one fragment of a contract, against the schema definition `KIND` names. The file is required. See [Validating one fragment](#validating-one-fragment). |
| `--schema-version VERSION` | Validate against this schema version, for example `0.7.6`, instead of the version the contract declares. With `--fragment`, the version to check the fragment against. A value that is not a version stops the run with `invalid_schema_version`. See [Schema version flags](#schema-version-flags). |
| `--min-version CONSTRAINT` | Fail with exit `2` when the schema version does not satisfy the constraint, for example `'>=0.7.5'`. A value that is not a constraint stops the run with `invalid_min_version` (exit `1`). |
| `--max-version CONSTRAINT` | Fail with exit `2` when the schema version does not satisfy the constraint, for example `'<0.7.7'`. A value that is not a constraint stops the run with `invalid_max_version` (exit `1`). |
| `--strict` | Treat warnings as errors. |
| `--offline` | Use only cached or bundled schemas. |
| `--force-refresh` | Refresh cached schemas. |
| `--clear-cache` | Clear the schema cache first. |
| `--cache-dir CACHE_DIR` | Use a custom schema cache directory. |
| `--verbose`, `-v` | Detailed validation output. |
| `--quiet`, `-q` | Minimal output: errors only. A run that stops on an error such as `contract_load_failed` still prints the error and the line that says what failed; the `[ERR_...]` slug, the suggestions and the documentation link stay hidden. See [Quiet output](#quiet-output). |
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

*(since 0.22.0, [forge-cli #734](https://github.com/Agenticstiger/forge-cli/pull/734))* An overlay patch that lands on another entry is a validation warning, so `--strict` fails on it. A contract that merges overlays by position (0.7.5 or older, or a 0.7.6 base whose entries lack unique ids) can do that: an overlay written against `builds: [ingest, transform]` patches the wrong build once the base gains one in front.

```text
✅ Valid FLUID contract (schema v0.7.5)
⚠️  1 warning(s)
Validation completed in 0.001s

Validation Warnings:
====================
 1. overlay_patch_retargeted: in network.service-instances, the overlay's builds[1] names id transform but patches the base's builds[1], id ingest, because lists merge by position. Put the overlay's entries in the base's order, or set fluidVersion 0.7.6 or later to merge builds by id.

❌ Validation failed: warnings treated as errors (--strict)
```

- Without `--strict` it exits `0`; with it, `1`. `--format json` lists it under `warnings`.
- `--quiet` prints it as a `WARNING:` line, and with `--strict` as `ERROR (--strict): <warning>`.
- Workspace mode lists it under the product, and `--strict` fails the product.
- `fluid contract-validation --env` and `fluid test --env` (the native engine) report it too; `fluid test` shows it as an "Environment overlay" row.
- `overlay_entry_added`, an overlay entry the base does not have, stays a log line and does not fail `--strict`: a build only one environment runs is often intended.
- *(since 0.22.0, [forge-cli #735](https://github.com/Agenticstiger/forge-cli/pull/735))* A bundle carries it. `fluid bundle --env --format tgz` records it in the bundle's manifest, so `fluid validate <bundle>.tgz` reports it as an `OVERLAY-WARNING` finding and `--strict` (pipeline stage 2) fails on it: see [Validating a bundle](#validating-a-bundle-tgz). A bundle built before that change records none and passes. `fluid contract-validation` and `fluid test` do not read the record, so run them on the contract file with `--env`.

## Contracts split into fragments

A root contract can pull parts of itself from other files with `$ref`. `fluid validate` resolves the pointers before it checks anything, so you pass the root file and validate the whole product. An error names the file and the line it was written in, then the place in the composed contract:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)

Validation Errors:
==================
 1. fragments/exposes/high_value_customers.yaml:17 (exposes[1].binding.format): 'parquett' is not one of ['bigquery_table', ...
```

A `$ref` may only name a file inside the ref root, which is the contract's own directory tree unless `ref_root` in `fluid.workspace.yaml` or `FLUID_REF_ROOT` widens it. One that climbs out of it is refused:

```text
❌ Validation error: contract_load_failed
   error: $ref '../shared-builds/customer_360_pipeline.yaml' at JSON pointer '/builds/0' in /path/to/esc/product/contract.fluid.yaml escapes the ref root /path/to/esc/product (after resolving '..' and symlinks); refs may only name files inside it. To compose fragments from a wider tree (e.g. a monorepo's shared/ directory), declare ref_root in the workspace's fluid.workspace.yaml, set FLUID_REF_ROOT to that directory, or pass ref_root= to the loader; see docs/contract-refs.md.
   [ERR_CONTRACT_LOAD_FAILED]
```

The suggestions printed under the slug (check the YAML syntax, file permissions) are generic and do not apply to a refused `$ref`. The error line above them is the diagnosis. How the ref root works, and how to widen it for a monorepo, is in [Composing a contract with `$ref`](../concepts/contract-refs.md).

## Validating one fragment

*(since 0.25.0, [forge-cli #760](https://github.com/Agenticstiger/forge-cli/pull/760); corrected in 0.26.0, [#761](https://github.com/Agenticstiger/forge-cli/pull/761))*
`--fragment KIND FILE` checks one fragment against the part of the schema it stands for, without the root contract:

```bash
fluid validate --fragment expose fragments/exposes/orders.yaml
```

```text
✅ Valid expose fragment (schema v0.7.5)
```

`KIND` is the name of a definition in the schema's `$defs` (`expose`, `build`, `column`, `sovereignty`, `accessPolicy`, ...), or `quality` or `schema` for an expose's lists. A name that is not a kind stops the run with `fragment_kind_unknown` and lists the kinds the schema has. The file's own `$ref`s are resolved and confined as the contract it belongs to would confine them: the nearest `contract.fluid.yaml` above it, or the file's own directory when there is none. The nearest contract is not taken past the top of the file's repository or workspace (a directory holding `.git`, `.hg`, `.svn` or `fluid.workspace.yaml`), nor past a home directory, a temporary directory or `/`, and a symlinked contract is never taken. An error reads as the whole contract's do, and names the file and line, with the path relative to the fragment:

```text
❌ Invalid expose fragment (1 error(s)) (schema v0.7.5)

Validation Errors:
==================
 1. fragments/exposes/high_value_customers.yaml:17 (binding.format): 'parquett' is not one of ['bigquery_table', ...
```

With `--format json`, the result names the kind in a `fragment` field after `valid`:

```json
{
  "valid": true,
  "fragment": "expose",
  "schema_version": "0.7.5",
  "errors": [],
  "warnings": [],
  "validation_time": null
}
```

**Which schema version.** `--schema-version` wins. Otherwise the version is the `fluidVersion` of the nearest root contract, read as every command reads it: a root that is a `$ref` to its base, a `fluidVersion` kept in a fragment and a same-document pointer are all followed. With neither, the run stops with `schema_version_required` and says why: no root contract above the fragment could be taken, or the nearest one cannot be read or declares no `fluidVersion`. The command does not guess a version: before 0.26.0 it used the newest stable schema, so a valid fragment of a newer schema failed on a field the older one does not have.

```console
$ fluid validate --fragment column col.yaml
❌ Validation error: schema_version_required
   error: cannot tell which schema version to check the fragment against: no contract.fluid.yaml above col.yaml could be taken (a symlinked one is not, and the search stops at the top of its repository or workspace, and before a home or temp directory). Pass --schema-version <version>; fluid validate --list-versions lists them.
   [ERR_SCHEMA_VERSION_REQUIRED]
$ fluid validate --fragment column col.yaml --schema-version 0.7.6
✅ Valid column fragment (schema v0.7.6)
```

**What it refuses.** Each stops the run with exit `1`:

| Event | When |
| --- | --- |
| `fragment_file_required` | No file was given. Before 0.26.0 `--fragment KIND` validated the `contract.fluid.yaml` of the working directory as if it were the fragment. When the KIND was left out, so that the file was read as the KIND, the error says that instead. |
| `fragment_bundle_unsupported` | The file is a `.tgz` bundle. A bundle holds a whole contract, so validate it without `--fragment`. Before 0.26.0 it validated the bundle and ignored `--fragment`. |
| `fragment_env_unsupported` | `--env` was given. An environment applies to a whole contract. |
| `fragment_has_pointers` | The fragment holds a same-document pointer (`#/...`), which names a place in the whole contract. Validate the contract that uses it. |
| `fragment_kind_unknown` | `KIND` is not a kind in the schema version. |

It checks the schema only. The rules that need the whole contract (sovereignty against regions, overlays, provider and governance checks) run when you validate the root.

## YAML limits

A contract is read through a guard that refuses YAML built to exhaust memory or CPU, for example a few hundred bytes of nested anchors that expand to millions of nodes (the "billion laughs" shape). It refuses a file that:

| Refused when | Limit | Message |
|---|---|---|
| The file is too large | 5 MiB (5,242,880 bytes; *(since 0.21.0, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* counted in UTF-8 bytes for text too) | `YAML input is over the 5242880-byte safety cap` |
| It has too many alias references (`*name`) | 50 | `YAML input has more than 50 alias references` |
| *(since 0.21.0, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* It nests too deep | 128 levels of mappings and lists | `YAML input nests more than 128 levels deep` |
| *(since 0.21.0, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* Its aliases add too many nodes | 100,000 added nodes, or 100-fold growth once the document is past 1,000 nodes | `YAML aliases expand this document from <n> to <m> nodes, ...` |
| *(since 0.21.0, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* Its aliases repeat too much text | 5,242,880 characters of scalar text added | `YAML aliases repeat <n> characters of text in this document, ...` |

`fluid validate` reports a refused contract as `contract_load_failed`:

```text
❌ Validation error: contract_load_failed
   error: Failed to parse ./contract.fluid.yaml: YAML aliases repeat 20000000 characters of text in this document, over the cap of 5242880 — possible anchor-expansion (billion-laughs) DoS. Write the repeated blocks out, or nest fewer anchors.
   [ERR_CONTRACT_LOAD_FAILED]
```

Reusing an anchored block a few times stays far inside every limit, and no file shipped with the CLI nests more than 9 levels. A contract that hits one is generated or hostile: write the repeated blocks out instead of reusing them through anchors. A document that contains itself through an alias is refused with `contract_load_failed` as well.

*(since 0.21.0, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* The same guard reads ODCS and ODPS files: [`fluid odps import` and `fluid odps validate`](./odps.md), [`fluid odcs validate` and `fluid odcs import`](./odcs.md), [`fluid odps-bitol validate`](./odps-bitol.md), the contracts `odps import` fetches for a `contractId`, and [`fluid forge --seed-from`](./forge.md). Before, those read YAML with no limit at all. `fluid odps`, `fluid odcs` and `fluid odps-bitol` report a refused file as a failed import or validation and exit 1.

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
  0.7.7 (bundled)
```

A schema version you fetched into the cache earlier is listed too, marked `(cached)`.

| Version | Status |
| --- | --- |
| `0.7.6` | Latest **stable**, since `0.26.0`. A contract with no `fluidVersion` is validated against it. |
| `0.7.7` | **Preview.** It validates only when a contract declares `fluidVersion: "0.7.7"` or you pass `--schema-version 0.7.7`; it is never chosen automatically. At open it is identical to `0.7.6`. |

The fields that need `0.7.6` include `lifecycle.expire`, `binding.encryption.kms`, `binding.principals`, `packaging`, and `upstreamWorkspace` / `upstreamDigest`. A contract that declares `0.7.5` and uses one of them fails with an error such as `exposes[1].lifecycle: Additional properties are not allowed ('expire' was unexpected)`.

*([forge-cli #711](https://github.com/Agenticstiger/forge-cli/pull/711), since 0.20.0)* So do the values `lakekeeper` and `polaris` in `builds[].properties.sink.catalog`. On `0.7.5` they fail with `builds[0].properties.sink.catalog: 'lakekeeper' is not one of ['rest', 'glue', 'nessie', 'unity', 'snowflake-managed', 'hive']`; leave `sink.catalog` unset there, and the sink uses the expose's `location.catalog`. See [How a value is read](../advanced/source-aligned-acquisition.md#how-a-value-is-read).

*([forge-cli #712](https://github.com/Agenticstiger/forge-cli/pull/712), since 0.20.0)* So does `builds[].properties.sink.catalogAuth`, which authenticates a streaming sink to an Iceberg REST catalog. On `0.7.5` it fails with `builds[0].properties.sink: Additional properties are not allowed ('catalogAuth' was unexpected)`. See [Authenticate a sink to a REST catalog](../advanced/source-aligned-acquisition.md#authenticate-a-sink-to-a-rest-catalog).

### Schema version flags

`--schema-version` overrides what the contract declares, which lets you test a contract against a newer schema without editing it.

`--min-version` and `--max-version` bound the schema version being validated and fail with exit `2` when it falls outside them. Their values are constraints: an operator and a version, one of `>=`, `>`, `<=`, `<`, `~` (the same minor version, at or above the version) or `=`, and a bare version means `=`. When the contract declares no `fluidVersion`, the two flags also narrow the versions `fluid validate` picks from: it takes the newest stable version that satisfies them, and a preview version only when nothing else does.

```console
$ fluid validate contract.fluid.yaml --min-version '>=0.7.6'
❌ Contract version 0.7.5 does not meet minimum requirement >=0.7.6
   [ERR_VERSION_BELOW_MINIMUM]
```

A value that is not a version or a constraint is a typed error with exit `1`, named for the flag: `invalid_schema_version`, `invalid_min_version` or `invalid_max_version`. Before 0.26.0 each ended as `cli_unhandled_exception`. The `invalid_schema_version` hint names `fluid validate --list-versions`, the command that lists the versions.

```console
$ fluid validate contract.fluid.yaml --schema-version banana
❌ Validation error: invalid_schema_version
   version: banana
   error: Invalid FLUID version format: banana
   [ERR_INVALID_SCHEMA_VERSION]
   💡 Use a supported version (current line: 0.7.x) in fluidVersion or --schema-version
   💡 Run 'fluid validate --list-versions' to see the supported versions
```

## Quiet output

`--quiet` is "errors only". Before 0.26.0 it printed nothing at all when a run stopped on an error such as `contract_load_failed`. The error now prints, and the hints, the slug and the documentation link stay hidden:

```console
$ fluid validate contract.fluid.yaml --quiet
❌ Validation error: contract_load_failed
   error: $ref target not found: nope.yaml (resolved to /work/nope.yaml), at JSON pointer '/builds/0' in /work/contract.fluid.yaml
```

Without `--quiet` the same run adds the `[ERR_CONTRACT_LOAD_FAILED]` line, the suggestions and the link.

A contract path that does not exist is named in the error: `❌ Contract file not found: missing.fluid.yaml`. Before 0.26.0 the message read `Contract file not found: None`.

## Governance binding checks (since 0.17.0)

`fluid generate iac`, `fluid plan` and `fluid apply` refuse a contract whose governance a cloud binding cannot apply. `fluid validate` runs the same derivations and reports each refusal at validation time, with the same message:

- **An unmapped or placeholder principal.** When a binding carries `binding.principals`, every principal the contract names for that expose must be mapped to a real identity, or to `[]` for "no identity on this cloud". Without the map, a principal on GCP that is a placeholder (a reserved top-level domain such as `.example`, or not an IAM member at all) is refused.
- **A column restriction nothing enforces.** On AWS, a `columnRestrictions` entry on a binding with no Lake Formation grants. On GCP, one on an expose with no reader to restrict.
- **A key reference for the wrong cloud.** A Cloud KMS key on an AWS binding, or an AWS key on a GCP binding.
- **Retention or encryption on a GCP target that is not a BigQuery table.** A Cloud Storage bucket, a Pub/Sub topic or Iceberg storage cannot carry `lifecycle.expire` or `binding.encryption.kms`.

The two errors in the example at the top of this page come from this check. A principal ending in `.example` fails on GCP until an overlay's `binding.principals` maps it to a real group, and `lifecycle.expire` on a Cloud Storage expose fails because only BigQuery tables apply it.

AWS has one warning of its own: `accessPolicy.grants` on a contract whose AWS binding declares no `governance.lakeFormation.grants`, where the access intent is not enforced.

Each message names its remedy. How the fields work, and what `fluid apply` emits for them on each cloud, is in [Governance](../advanced/governance.md), the [GCP provider](../providers/gcp.md) and the [AWS provider](../providers/aws.md).

## A continuous trigger on a batch build

*(since 0.22.0, [forge-cli #737](https://github.com/Agenticstiger/forge-cli/pull/737))* `trigger.type: continuous` (schema 0.7.6, see [Continuous builds](../concepts/builds-exposes-bindings.md#continuous-builds-trigger-type-continuous)) says the job's platform keeps it running, so no scheduler starts the build. On a build forge-cli runs as a batch run, which ends, `fluid validate` warns:

```text
✅ Valid FLUID contract (schema v0.7.6)
⚠️  1 warning(s)
Validation completed in 0.002s

Validation Warnings:
====================
 1. builds[0] (id 'customer360_build'): trigger.type continuous on engine 'dbt': forge-cli runs dbt builds as batch runs, which end, and its dbt runner refuses a continuous trigger: forge-cli never runs this build. Use trigger.type schedule or manual, or run the job on a platform that keeps it running.
```

Without `--strict` it exits `0`; with it, `1`. `--format json` lists it under `warnings`.

| Build | What forge-cli does with a continuous one | Warning |
| --- | --- | --- |
| `engine: dbt`, `dbt-<adapter>` or `python`, or any build the python runner takes: no engine, `spark`, `glue` or `custom` without a `runtime.platform` of its own, an ingestion engine without `pattern: acquisition` | Its runner refuses the trigger, so `fluid apply --mode amend-and-build` fails on the build (exit `1`) and nothing else runs it. | Yes |
| Inline SQL (`engine: sql`, or `pattern: embedded-logic` with `properties.sql`) on the local DuckDB engine or Snowflake, or a `duckdb`, `airbyte`, `meltano` or `dlt` acquisition | Runs only when `fluid apply` runs builds; no scheduler starts it. | Yes |
| A `kafka-connect` or `debezium` acquisition, `engine: flink`, or `properties.language: flink_sql` | The connector or job keeps running on its platform. | No |
| `engine: spark`, `glue` or `custom` with a `runtime.platform` other than `local`, or inline SQL on a platform with no embedded-SQL executor | forge-cli does not run it, so `fluid apply --mode amend-and-build` leaves it to that platform, as it does a Flink job, and records it as skipped with `reason: runs_outside_forge`. | No |

For a build of the last kind, `fluid apply --mode amend-and-build` prints:

```text
⏭️  Build 'ingest_events' - trigger.type continuous on engine 'spark': databricks keeps the job running, outside forge-cli; there is nothing for forge-cli to run.
```

The check runs on the contract file and on a bundle's resolved contract, not in [workspace mode](#validating-without-a-contract-path).

## An id the build phase refuses

*(since 0.27.0, [forge-cli #813](https://github.com/Agenticstiger/forge-cli/pull/813))* The build phase puts `id` and each `builds[].id` in directory names and generated code, so its rule is narrower than the schema's: an id must start with a letter or `_`, use only letters, digits, `_`, `.` and `-`, and be at most 128 characters. The schema also accepts a leading digit and any length. For a contract with `builds`, `fluid validate` warns about such an id:

```text
✅ Valid FLUID contract (schema v0.7.5)
⚠️  1 warning(s)
Validation completed in 0.003s

Validation Warnings:
====================
 1. contract.id '1orders' cannot be used by the build phase, which puts it in directory names and generated code, so it must start with a letter or underscore, use only letters, digits, '_', '.' and '-', and be at most 128 characters. fluid apply in a build mode (amend-and-build, replace-and-build) refuses this id before it applies anything. Rename it to fit.
```

Without `--strict` it exits `0`; with it, `1`. `--format json` lists it under `warnings`. The warning names the first id that fails, the one [`fluid apply` refuses](./apply.md#build-ids); after a rename, validate again for the next. A contract without `builds` is not checked. [`fluid plan`](./plan.md#notes) prints the same warning and still writes the plan.

The check runs on the contract file and on a bundle's resolved contract, not in [workspace mode](#validating-without-a-contract-path).

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
- **The overlay warnings.** *(since 0.22.0, [forge-cli #735](https://github.com/Agenticstiger/forge-cli/pull/735))* An overlay patch that `fluid bundle --env` merged onto another entry is recorded in the manifest and reported as a warning, `OVERLAY-WARNING`, so `--strict` fails on it. A bundle is never re-overlaid, so the record is how validate sees it.

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

A bundle built with `--env prod` from the 0.7.5 contract in [`--env` and environment overlays](#env-and-environment-overlays), whose overlay patches the wrong build, fails under `--strict`:

```bash
fluid validate runtime/bundle.tgz --env prod --strict
```

```text
❌ Bundle fail: /path/to/proj/runtime/bundle.tgz
   digest: sha256:6238f9c15525142e3b67ff343171cf10631c0e5f85504608bec05ad8e2380db7
   issues: 1 total (0 error, 1 warning, 0 info)
   [warning] overlay: MANIFEST.json: overlay_patch_retargeted: in network.service-instances, the overlay's builds[1] names id transform but patches the base's builds[1], id ingest, because lists merge by position. Put the overlay's entries in the base's order, or set fluidVersion 0.7.6 or later to merge builds by id.
❌ Validation failed: warnings treated as errors (--strict)
```

*(since 0.22.0, [forge-cli #735](https://github.com/Agenticstiger/forge-cli/pull/735))* Without `--strict` the same bundle passes and still lists the warning: a bundle that passes lists its warnings, not only their count. `--quiet`, which printed nothing for a bundle, prints each error as `ERROR: <finding>`, a recorded overlay warning as `WARNING: <finding>`, and under `--strict` each warning as `ERROR (--strict): <finding>`.

`--report PATH` writes the full structured report as JSON, on pass and on fail, so a CI job can upload it as an artifact. The report has `bundleDigest`, `input`, `strict`, `status`, `summary` and `issues[]`; each issue carries `file`, `validator`, `severity`, `message` and a `code`. The `BUNDLE-ENV-MISMATCH` finding is written to the report like any other. `--report` has an effect only for a `.tgz` bundle: `fluid validate contract.fluid.yaml --report out.json` writes no file as of 0.18.1.

Codes you will meet in a report:

| Code | Raised when |
| --- | --- |
| `MANIFEST-TAMPER` | A file's hash does not match the manifest. |
| `BUNDLE-ENV-MISMATCH` | `--env` differs from the environment the bundle was built for. |
| `OVERLAY-WARNING` | `fluid bundle --env` recorded an overlay patch that landed on another entry (a warning; `--strict` fails on it). |
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

With [forge-cli #707](https://github.com/Agenticstiger/forge-cli/pull/707) (since 0.20.0), the warning also covers `lakekeeper` and `bigquery`, and a `hive`, `jdbc`, `hadoop` or `dynamodb` catalog on Snowflake is an error. See [Iceberg catalog checks](#iceberg-catalog-checks).

## Iceberg catalog checks

::: tip Since `0.20.0`
These checks come with [forge-cli #707](https://github.com/Agenticstiger/forge-cli/pull/707), the follow-up fixes in [forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709) and [forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), the Lakekeeper, Polaris and Unity checks of [forge-cli #711](https://github.com/Agenticstiger/forge-cli/pull/711), and the `sink.catalogAuth` checks of [forge-cli #712](https://github.com/Agenticstiger/forge-cli/pull/712). All five shipped in `0.20.0`.
:::

`binding.location.catalog` names the Iceberg catalog that owns an expose's table, and every emitter now reads it through one table. [Iceberg catalogs](../advanced/source-aligned-acquisition.md#iceberg-catalogs-location-catalog) has that table, how spellings fold, and a worked Lakekeeper example. `fluid validate` refuses a contract whose catalog the emitters would disagree about:

- **An unknown catalog.** A `location.catalog` outside the table, on an Iceberg expose, is an error that lists the accepted spellings. On `platform: confluent` every value other than `glue` is an error instead, because the Tableflow module publishes only to AWS Glue.
- **A streaming sink that cannot reach its catalog.** For a Kafka Connect build, or an embedded Debezium Server build, that writes an Iceberg expose:
  - every REST catalog (`rest`, `lakekeeper`, `polaris`, `unity`), `nessie` and `snowflake-managed` needs `location.uri` and `location.warehouse`; `jdbc` needs `uri`, and `hadoop` needs `warehouse`. On 0.19.0 and earlier only the literal `rest` was checked.
  - *([forge-cli #711](https://github.com/Agenticstiger/forge-cli/pull/711), since 0.20.0)* `lakekeeper`, `polaris` and `unity` address a warehouse by name, so an object-store URI in `location.warehouse`, such as `s3://`, `gs://` or `abfss://`, is an error. A `lakekeeper` `uri` that does not end in `/catalog`, where Lakekeeper serves the Iceberg REST API, is a warning. Both checks read `binding.location`, not an override. See [What a Lakekeeper, Polaris or Unity sink needs](../advanced/source-aligned-acquisition.md#what-a-lakekeeper-polaris-or-unity-sink-needs).
  - *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), since 0.20.0)* `dynamodb` and `jdbc` need a warehouse: `location.warehouse`, one derived from `location.bucket` on `platform: aws` or `gcp`, or the sink's `warehouse` property in an override. `bigquery` needs `location.project`, or `gcp.bigquery.project-id` in an override. A value of only whitespace counts as missing. A `bigquery` expose with no `gs://` warehouse to derive is a warning. See [What a DynamoDB, JDBC or BigQuery sink needs](../advanced/source-aligned-acquisition.md#what-a-dynamodb-jdbc-or-bigquery-sink-needs).
  - *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), since 0.20.0)* a warehouse that derives from a `location.bucket` written as a `{{ env.* }}` template, whose variable is unset or empty where `fluid validate` runs, is a warning that names the variable. The run preflight refuses the build when the variable is unset or empty where the sink config is derived.
  - *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), since 0.20.0)* a build whose sink config forge-cli derives must name the Iceberg exposes it writes in its `outputs`. A Kafka Connect build writes exactly one, so outputs that name none or several of them are an error, and so is a build with no outputs in a contract with several. An embedded Debezium Server build is an error when its outputs name none of them, or when the exposes it writes sit in more than one `location.database`, resolve to different catalogs, or are DynamoDB or JDBC exposes with different warehouses derived from `location.bucket`. See [Which exposes a streaming sink writes](../advanced/source-aligned-acquisition.md#which-exposes-a-streaming-sink-writes).
  - a `sink.catalog` that names another catalog than the expose is an error, because dbt and the modules read only the expose. *([forge-cli #711](https://github.com/Agenticstiger/forge-cli/pull/711), since 0.20.0)* `lakekeeper` and `polaris` are `sink.catalog` values on the 0.7.6 preview only; see [Schema versions](#schema-versions-stable-and-preview).
  - *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* a `sink_connector_config`, an `iceberg_catalog_overrides` entry or an embedded Debezium Server `server.sink.config` whose `type` or `catalog-impl` selects another catalog than the expose's is an error, on every platform: the sink would write one catalog while dbt and the modules read the other. They are compared as the catalog the worker builds, so `type=rest` matches `rest`, `lakekeeper`, `polaris`, `unity` and `snowflake-managed`. Declare the catalog the sink writes to in `location.catalog`; a REST endpoint that fronts Glue (Glue's Iceberg REST endpoint) is `catalog: rest`. A `catalog: bigquery` expose on `platform: gcp` whose hand-written config sets `iceberg.catalog.type: rest`:
    ```text
     1. iceberg sink (build 'stream_events'): sink_connector_config sets iceberg.catalog.type='rest', so the sink would write through a REST catalog while dbt and the IaC read the expose's catalog 'bigquery' (binding.location.catalog). Declare the catalog the sink writes to in binding.location.catalog; a REST endpoint that fronts Glue (Glue's Iceberg REST endpoint) is catalog: rest
    ```
  - an `iceberg_catalog_overrides` entry or a hand-written sink config that would leave the connector with both `type` and `catalog-impl` is an error, because Apache Iceberg refuses that catalog and the sink never starts.
  - `nessie` on a `kafka-connect` build is a warning: the stock Apache Iceberg Kafka Connect runtime has no Nessie client.
  - *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* `bigquery` on a `kafka-connect` build is a warning: the sink config sets `iceberg.catalog.type=bigquery`, which the published Apache Iceberg Kafka Connect sink (1.9.2) cannot load; Iceberg adds the type in 1.10. This warning and the Nessie one follow the catalog that reaches the worker, selected by `type` or by a `catalog-impl` class, so a hand-written `sink_connector_config` that sets `iceberg.catalog.type: rest` draws neither; for a `bigquery` or `nessie` expose that config is an error instead (above).
  - *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* on `platform: gcp`, an Iceberg expose the build writes must name its `location.catalog`, or it is an error when a catalog other than BigLake reaches the worker: the sink would write through that catalog while dbt-bigquery and the GCP module create a BigLake table. It is REST by default, and Glue for `sink.catalog: glue` or a hand-written `catalog-impl` of `org.apache.iceberg.aws.glue.GlueCatalog`. See [How a value is read](../advanced/source-aligned-acquisition.md#how-a-value-is-read).
- **A streaming sink's catalog auth.** *([forge-cli #712](https://github.com/Agenticstiger/forge-cli/pull/712), since 0.20.0)* `sink.catalogAuth` names the environment variable that authenticates a derived Iceberg sink to a REST catalog. `fluid validate` refuses it:
  - when it is malformed: a variable name that is not one, or that has the shape of a personal access token; an `oauth2ServerUri` that does not start with a lowercase `http://` or `https://`, or that has a `user:password@` part; a `${...}` expression, a control character or an `env:` value in `oauth2ServerUri`, `scope`, `audience` or `resource`; a missing field, or a field its `type` does not take. The schema and the sink check usually both report the problem, and neither message shows the value;
  - on a build that writes no Iceberg sink config forge-cli derives: a Kafka Connect build with another `sink.format`, a Debezium build that is not `embedded`, or another engine;
  - on a sink config that is hand-written, or whose derivation is turned off;
  - on a catalog not reached over REST, that is, any kind but `rest`, `lakekeeper`, `polaris`, `unity` and `snowflake-managed`;
  - next to an override that also sets `rest.auth.type`, `credential`, `token`, `oauth2-server-uri`, `scope`, `audience`, `resource`, `rest.sigv4-enabled` or a `header.Authorization`.

  Where no `catalogAuth` applies, an override or hand-written sink config that sets `credential` or `token` to a literal value is a warning; a value that starts with `env:` or carries a `${...}` expression is not. `fluid validate` does not check that the variable is set, since only the process that runs the sink reads it. See [What `fluid validate` refuses](../advanced/source-aligned-acquisition.md#what-fluid-validate-refuses).
- **Snowflake.** On `platform: snowflake`, a catalog that Snowflake reaches over Iceberg REST (`rest`, `lakekeeper`, `polaris`, `unity`, `nessie`, `bigquery`) draws the warning described above, which `--strict` turns into an error. `hive`, `jdbc`, `hadoop` and `dynamodb` are an error, because Snowflake has no catalog integration for them. A `lakekeeper` expose is no longer asked for an `s3://` or `gs://` warehouse, and two `catalog: snowflake` exposes that derive one EXTERNAL VOLUME on different storage are caught here rather than failing `fluid apply` mid-emit.
- **AWS.** An Iceberg expose in a catalog other than Glue cannot carry `governance.lakeFormation`, `policy.authz.columnRestrictions` or `policy.authz.rowFilters`: each is refused by catalog name. `accessPolicy.grants` on it draws a warning to grant access in that catalog. See [On AWS](../advanced/source-aligned-acquisition.md#on-aws-a-table-in-another-catalog). *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* An unknown catalog value draws only the unknown-catalog error, not these refusals as well.
- **GCP.** A `platform: gcp` expose in a catalog other than `bigquery` may give the catalog's warehouse name; a warehouse in another object store (`s3://`, `abfss://`) is an error. *([forge-cli #711](https://github.com/Agenticstiger/forge-cli/pull/711), since 0.20.0)* When a streaming sink writes a `lakekeeper`, `polaris` or `unity` expose, a `gs://` warehouse is an error too, because those catalogs address a warehouse by name.

A crash inside the Iceberg sink, Confluent or Iceberg prerequisite check now fails validation, with an error such as `Iceberg sink check could not run (...); the contract was NOT checked for streaming-sink defects`. On 0.19.0 and earlier the crash was printed only with `--verbose`, and the contract passed unchecked.

The Kafka Connect runner and the embedded Debezium Server runner run the same streaming-sink checks before they create anything, so a contract that skipped `fluid validate` still fails before any Connect REST call or `application.properties` write. *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* That holds for a build that declares `sink.format: iceberg`, with a derived or a hand-written sink config, and for an embedded Debezium Server build that derives its sink. On #707 alone a hand-written config was not checked by the runners. *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), since 0.20.0)* The one difference is a `location.bucket` template whose variable is unset or empty: a warning here, since the variable may be set where the sink runs, and an error in the runner when it is unset or empty there and the sink would use the warehouse. *([forge-cli #712](https://github.com/Agenticstiger/forge-cli/pull/712), since 0.20.0)* The embedded Debezium Server runner also refuses a run whose `sink.catalogAuth` variable is unset or empty in its environment, which `fluid validate` does not check; the Kafka Connect runner cannot see the worker's environment, so it does not check the variable. A `catalogAuth` on a build that writes no derived Iceberg sink is refused by `fluid validate` only. [What each kind produces](../advanced/source-aligned-acquisition.md#what-each-kind-produces) lists the builds.

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

- A contract can declare an older schema than the CLI's newest. A contract with `fluidVersion: 0.7.2` still validates on a current CLI because the older schemas stay bundled. Schema `0.7.6` is the latest stable version; `0.7.7` is a preview.
- *(since 0.15.0)* `fluid validate` shares its sovereignty checker with [`fluid plan --check-sovereignty`](./plan.md#sovereignty-gate-since-0-15-0), and `sovereignty.enforcementMode` now decides severity in both directions: a `strict` contract whose binding region resolves outside its declared `jurisdiction` newly **fails** with exit 1, and an `advisory` contract that failed now only warns. Full table, and the region-table derivation that changes verdicts on contracts nobody edited: [Governance → Sovereignty enforcement modes](../advanced/governance.md#sovereignty-enforcement-modes-since-0-15-0).
- For routine use, `fluid validate contract.fluid.yaml` is enough. Reach for the schema flags when you are debugging compatibility or working across versions.

## Extension point: custom validators

`fluid validate` runs any `Validator` plugin discovered through Python entry-points (since `0.8.3`). After `pip install <some-validator-plugin>`, the validator's findings appear in `fluid validate` output alongside the core schema validation.

This is how teams enforce governance rules (every Gold product MUST declare a steward, every contract MUST have a cost-center label, etc.) without forking the CLI.

- Author a validator: [SDK & Plugins → Custom validator journey](../sdk-and-plugins/journeys/custom-validator.md)
- Reference: [Entry points → `fluid_build.validators`](../sdk-and-plugins/reference/entry-points.md)
- Example: [`steward-validator`](../sdk-and-plugins/examples/steward-validator.md)
