# Fluid Forge Docs Baseline: CLI `0.10.0`

**Release Date:** June 27, 2026
**Status:** Current stable docs baseline (supersedes [`0.9.0`](./RELEASE_NOTES_0.9.0.md))

## Headline

`0.10.0` is the **plugin-governance and roster-clarity** release. It adds two new
introspection commands — **`fluid plugins`** (what's installed, per role, with allow/block
status) and **`fluid exporters`** (the open standards a contract can serialize to) — and
introduces an operator-facing **plugin trust boundary** (`FLUID_PLUGINS_ALLOWLIST` /
`FLUID_PLUGINS_BLOCKLIST`) that gates every code-executing plugin **before** it loads. It also
**reclassifies `odps` / `odcs` from cloud providers to spec exporters** (they were never
deployment targets), wires the SDK `Validator` and `CatalogAdapter` roles end-to-end, and ships
the companion SDK `0.10.0` and custom-scaffold `0.4.0`. Contract schema is **unchanged at
`0.7.5`**; existing contracts validate exactly as before. (`fluid init --quickstart` still
scaffolds the pinned customer-360 template at `0.7.2`.)

::: tip Who should upgrade
Anyone running third-party plugins (the new allow/block governance is the headline), and anyone
who wants accurate `fluid providers` output. The change is additive — no contract changes, no
schema bump, and every spec-export command works exactly as before. `pip install --upgrade
data-product-forge`.
:::

## What changed in `v0.10.0`

### Added — `fluid plugins`

- **New command `fluid plugins`** (subcommand `list`; options `--json`, `--role`, `--detailed`).
  Lists installed plugins grouped by role, each with its **allow/block** governance status. Roles
  surfaced: `provider` / `validator` / `catalog` / `iac_provider` / `custom_scaffold` (the `--json`
  form additionally shows `apply_hook`, `command`, `extension_schema`, `extension_validator`,
  `modeling_technique`, `source_adapter`).
- **`--detailed` is a security boundary.** It LOADS only **allowed** plugins to surface their
  declared metadata (version / author / license / url); **blocked plugins are never loaded.** See
  [`fluid plugins`](./cli/plugins.md).

### Added — `fluid exporters`

- **New command `fluid exporters`** (option `--json`). Lists the **spec-export formats** — the open
  standards a `contract.fluid.yaml` can be serialized to:
  - `odcs` — Bitol Open Data Contract Standard v3.1.0
  - `odps` — LF/ODPI Open Data Product Specification v4.1 (alias `opds`)
  - `odps-bitol` — Bitol Open Data Product Standard v1.0.0 (alias `odps-standard`)

  Each row shows the spec, its URL, and the `fluid generate standard --format <fmt>` invocation. The
  CLI's own tagline says it best: *"Exporters serialize a contract to a SPEC — they are not cloud
  providers (see `fluid providers` for deployment targets)."* See [`fluid exporters`](./cli/exporters.md).

### Changed — `odps` / `odcs` are now exporters, not providers

- **`odps` / `odcs` were reclassified from cloud providers to spec exporters.** They had been
  mis-registered as `fluid_build.providers` entry-points — a bug, since neither deploys
  infrastructure (`OdpsProvider.apply()` was a no-op stub and `OdcsProvider.apply()` raised "does not
  support apply()"). They are de-registered from the provider registry, the `--provider` choices, and
  the plugin manager. **`fluid providers` now lists exactly: `aws`, `datamesh_manager`, `gcp`,
  `local`, `redshift`, `snowflake`** (no `odps` / `odcs`), and the global `--provider` choices are
  `{local, gcp, snowflake, aws, azure}`.

::: tip Migration — export commands are unchanged
Only the **classification** changed. Every spec-export command works exactly as before:
`fluid odps`, `fluid odcs`, `fluid odps-bitol`, `fluid export-odps`, and `fluid generate standard
--format odps|odcs|odps-bitol` are all fully supported. `odps` / `odcs` are now surfaced by
[`fluid exporters`](./cli/exporters.md) instead of `fluid providers`. No action is required unless
you scripted `fluid providers` output expecting `odps` / `odcs` in the roster.
:::

### Added — plugin governance (operator trust boundary)

- **`FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST`** (comma-separated entry-point names) gate
  **every code-executing entry-point group BEFORE the plugin is loaded.** If `ALLOWLIST` is set, only
  those plugins load; `BLOCKLIST` plugins never load. A blocked plugin's code never executes — a real
  trust boundary, not a display filter. Governed groups: providers, validators, catalog adapters,
  commands, apply_hooks, extension_schemas, extension_validators, modeling_techniques, source_adapters,
  iac_providers. `fluid plugins` surfaces each plugin's allow/block status.
- **`FLUID_PLUGIN_STRICT_COMPAT=1`** (opt-in) — an SDK↔CLI version-compat gate. The CLI reads a
  plugin's declared `requires_cli` (a PEP 440 specifier from the SDK) and refuses to load any plugin
  whose requirement the running CLI version does not satisfy. Default (unset) is warn-only. This is the
  dbt `require-dbt-version` model: the SDK declares, the CLI gates.

### Changed — SDK roles wired end-to-end

- The SDK **`Validator`** role now runs inside `fluid validate`; the **`CatalogAdapter`** role runs
  inside `fluid publish`; and **IaC providers** are entry-point pluggable via the new
  `fluid_build.iac_providers` group.

## Companion packages

### SDK `0.10.0` (`data-product-forge-sdk`, import `fluid_sdk`)

- **Four real role ABCs:** `CustomScaffold`, `Validator`, `InfraProvider`, `CatalogAdapter`.
  `InfraProvider` (role `provider`) and `CatalogAdapter` (role `catalog`) are **new first-class
  roles**; their `apply` is abstract on purpose, so a plugin that forgets to implement it fails loud
  rather than silently no-op'ing. Each role ships an action builder (`provision_action` /
  `catalog_entry_action`).
- **Typed value domains** (zero-dependency str-enums): `Severity`, `ActionStatus`, `Phase`, plus the
  `FAILING_SEVERITIES` set. `Severity.coerce` **fails safe** — an unrecognised severity counts as
  ERROR, never silently passes.
- **`PluginCapabilities` + `BasePlugin.capabilities()`** — typed plugin self-description.
- **SDK↔CLI compat declaration:** `SDK_PROTOCOL_VERSION` (=1), `MIN_CLI_VERSION` (`"0.7.0"`),
  `MAX_CLI_VERSION` (`None` = open-ended), `cli_requirement()` (→ `">=0.7.0"`), and
  `PluginMetadata.{sdk_protocol_version, requires_cli}`.
- **Three role conformance harnesses now ship:** `ValidatorTestHarness`, `InfraProviderTestHarness`,
  `CatalogAdapterTestHarness` (previously documented but raised `ImportError` on use). Subclass the
  harness matching your role for the generic invariants plus role-specific conformance.

### Custom-scaffold engine `0.4.0` (`data-product-forge-custom-scaffold`, CLI `fluid custom-scaffold`)

- **Reproducibility (copier-parity).** A deterministic, credential-free **`fluid-scaffold.lock`** is
  written to the output root after a successful (non-dry-run) generation, recording the resolved git
  commit. **`--pin`** resolves git sources to the locked commit (npm-ci / poetry-frozen semantics;
  byte-reproducible). **`--update [--target REF]`** re-renders the template at the locked base plus the
  new ref and 3-way-merges the result onto your working tree via `git merge-file` — conflict markers
  and exit code 4 on overlap, with the lock advancing on a clean merge.
- **SHA-pinning fixed** — `git@<full-commit-sha>` sources now resolve correctly.
- **Real enforcement** of what used to be silently ignored: a bundle's `variables_schema` (JSON Schema
  Draft 7) is enforced at plan time, and `supportedProductTypes` is checked against
  `metadata.productType`. (The `when` / `environments` pattern fields remain RESERVED / not yet
  evaluated.)
- **`fluid custom-scaffold` is fixed** — it was broken in `0.1.x` (a host-dispatcher arity bug); the
  reproducibility work above ships in `0.4.0`.

## Version summary

| Package | Version | Notes |
|---|---|---|
| `data-product-forge` | **0.10.0** | The CLI (this docs set) |
| `data-product-forge-sdk` | **0.10.0** | Four role ABCs, typed value domains, compat declaration, three role conformance harnesses |
| `data-product-forge-custom-scaffold` | **0.4.0** | Reproducible builds — `fluid-scaffold.lock` + `--pin` / `--update`; `variables_schema` enforcement |

Contract schema is unchanged at **`0.7.5`**; `fluid init --quickstart` still scaffolds at `0.7.2`.
