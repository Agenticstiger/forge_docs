# Fluid Forge Docs Baseline: CLI `0.8.9`

**Release Date:** June 1, 2026
**Status:** Superseded by [`0.8.10`](./RELEASE_NOTES_0.8.10.md) (supersedes [`0.8.8`](./RELEASE_NOTES_0.8.8.md))

## Headline

`0.8.9` makes the `fluid forge` copilot **extension-aware**: any plugin that ships a JSON-Schema for its `contract.extensions.<key>` block is now **generated and validated like a core contract field**, with **zero per-extension CLI changes**. A new `fluid_build.extension_schemas` entry-point group lets a plugin advertise its schema; the copilot grounds contract generation on every installed schema and validates the emitted block *before* writing it. No schema change vs `0.8.8` (contract schema stays at `fluidVersion 0.7.4`).

Shipped alongside two companion releases:

- **`data-product-forge-sdk` 0.9.1** — adds the reference `iter_extension_schemas()` helper and documents the new group.
- **`data-product-forge-custom-scaffold` 0.1.1** — ships the `customScaffold` JSON-Schema as a real artifact, advertises it via the new group, and adds **white-label spec dialects**.

::: tip Who should upgrade
Anyone authoring contracts with the `fluid forge` copilot who also uses a plugin extension (e.g. `extensions.customScaffold`). Before `0.8.9` the copilot couldn't see plugin extension shapes, so AI-authored contracts silently omitted them; now they're generated and validated. Plugin authors who want their extension to be AI-native should register a `fluid_build.extension_schemas` provider.
:::

## What changed in `v0.8.9`

### Added

- **Native `contract.extensions.*` support in the `fluid forge` copilot.** A new
  `fluid_build.extension_schemas` entry-point group lets any plugin advertise the
  JSON-Schema for its extension sub-key via a
  `get_extension_schema(fluid_version=None) -> dict` provider. During `fluid forge`
  generation the copilot enumerates every installed schema, injects it into the
  modeler prompt so the LLM can propose a valid block, keeps only proposals that
  validate against the schema, and attaches them to the emitted contract. The
  mechanism is extension-agnostic — adding a new extension needs **no** CLI
  change. See [Entry points → `fluid_build.extension_schemas`](./sdk-and-plugins/reference/entry-points.md).

  ```bash
  # With the custom-scaffold plugin installed, the copilot now emits a valid
  # extensions.customScaffold block grounded on the plugin's shipped schema:
  fluid forge data-model from-intent intent.yaml -o contract.fluid.yaml
  fluid validate contract.fluid.yaml      # the extension validator runs and passes
  ```

### Fixed

- **Pre-emit extension validation.** The copilot's conformance pass now runs the
  registered `fluid_build.extension_validators` (the same plugins `fluid validate`
  uses) **before** the contract is written. A malformed `extensions.<key>` block
  becomes an error-severity finding that enters the repair loop instead of being
  emitted silently — the core schema treats `extensions` as
  `additionalProperties: true`, so without this a bad block would pass the
  pre-emit gate.
- **Hardened, leak-safe discovery.** Extension-schema discovery mirrors the
  existing validator / apply-hook walkers: per-plugin `try/except` isolation, a
  non-`dict` guard, `redact_secret_text` on any failure message (logged by
  exception **type** only), and a fail-open to `{}` so a broken plugin never
  blocks generation.
- Updated the `sdk` optional extra from the retired `fluid-provider-sdk` to
  `data-product-forge-sdk>=0.9,<1`.

## Companion package releases

| Package | Version | Highlights |
|---|---|---|
| `data-product-forge` | **0.8.9** | Native `contract.extensions.*` generation + pre-emit validation in the copilot |
| `data-product-forge-sdk` | **0.9.1** | `iter_extension_schemas()` + the `fluid_build.extension_schemas` convention |
| `data-product-forge-custom-scaffold` | **0.1.1** | Shipped `customScaffold` schema artifact; schema provider; white-label `ScaffoldDialect` |

See [Companion packages](./sdk-and-plugins/reference/companion-packages.md) for version-pinning guidance, and [Entry points](./sdk-and-plugins/reference/entry-points.md) for the full `fluid_build.extension_schemas` reference.
