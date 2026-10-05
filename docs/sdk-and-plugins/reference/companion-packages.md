# Companion packages

Three packages ship together as one platform. End users only need the CLI; plugin authors need the SDK; plugin authors who want to ship file-emitting plugins via Jinja+YAML bundles also need the custom-scaffold engine.

## Quick reference

| Package | Version | PyPI | Import path | What you reach for it for |
|---|---|---|---|---|
| **`data-product-forge`** | `0.18.1` | [pypi.org/project/data-product-forge](https://pypi.org/project/data-product-forge/) | `import fluid_build` | The CLI itself — `fluid` command, all built-in providers, the `fluid generate`/`validate`/`apply`/`publish` lifecycle, and the `fluid forge` copilot. Plugin governance (`FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST`) and the `fluid plugins` / `fluid exporters` commands |
| **`data-product-forge-sdk`** | `0.10.0` | [pypi.org/project/data-product-forge-sdk](https://pypi.org/project/data-product-forge-sdk/) | `from fluid_sdk import …` | Zero-dependency ABCs (`BasePlugin`, `CustomScaffold`, `Validator`, `InfraProvider`, `CatalogAdapter`) + typed value domains (`Severity` / `ActionStatus` / `Phase`) + SDK↔CLI compat declaration + three role conformance harnesses + `iter_extension_schemas()` discovery helper. Plugin authors only. |
| **`data-product-forge-custom-scaffold`** | `0.4.1` | [pypi.org/project/data-product-forge-custom-scaffold](https://pypi.org/project/data-product-forge-custom-scaffold/) | `from data_product_forge_custom_scaffold import …` | Reference Jinja+YAML bundle engine; it registers the `fluid custom-scaffold` command. Use it when your plugin distributes templates via a git bundle. 0.4.0 adds copier-parity reproducibility: a `fluid-scaffold.lock` lockfile, `--pin` (byte-reproducible re-render at the locked commit), and `--update [--target REF]` (3-way re-render onto your working tree). White-label spec dialects (`ScaffoldDialect`) shipped in 0.1.1. |

## Who installs what

| You are… | Install |
|---|---|
| **End user** consuming someone else's plugins | `pip install data-product-forge data-product-forge-custom-scaffold <plugin-package>` |
| **Plugin author** writing a new role subclass | `pip install data-product-forge-sdk` for development; the CLI itself for testing |
| **Bundle author** distributing Jinja templates to other teams | No extra install — consumers install `data-product-forge-custom-scaffold`; you just host the bundle in git |
| **Platform team** building a custom CLI subcommand | `pip install data-product-forge-sdk` if your plugin subclasses anything, otherwise no SDK needed (entry-point can be a plain function) |

## The SDK dual-naming explained

PyPI distribution: `data-product-forge-sdk`. Python import path: `fluid_sdk`.

```bash
pip install data-product-forge-sdk
```

```python
from fluid_sdk import CustomScaffold, ContractHelper, write_file_action
```

This is **deliberate**, and standard PyPI practice. Same pattern as:

- `pillow` ↔ `from PIL import Image`
- `scikit-learn` ↔ `from sklearn import …`
- `pyyaml` ↔ `import yaml`
- `attrs` ↔ `import attr`

The PyPI name reflects the product brand (`data-product-forge`). The import path stays short, version-stable, and module-friendly (`fluid_sdk` was its name before the rename and hasn't changed).

**You don't have to do anything special** — `pip install data-product-forge-sdk` makes `import fluid_sdk` work. The CLI's `requirements.txt` and your plugin's `pyproject.toml` both use the dist name; only your Python source uses the import path.

## Version pinning recommendations

### If you're consuming the CLI

```toml
dependencies = [
    "data-product-forge==0.18.1",  # pin exact for reproducibility
]
```

Pin exactly (`==`) for CI and production. For development, a bound such as `>=0.18.1,<0.19` is workable, and a minor is not a compatibility promise: the CLI is pre-1.0, and a patch release can change behaviour on purpose: the forge-cli [CHANGELOG](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md) entry for 0.16.3 has an "Upgrading can change results, deliberately" list. Only the `fluid_build.api` surface follows SemVer (see [API stability](../../advanced/api-stability.md)). The [upgrade guide](../../upgrading.md) lists what to check between releases. Read each release's notes before widening a bound; the [0.18.0 release notes](../../RELEASE_NOTES_0.18.0.md) cover the `$ref` and DuckDB-sandbox confinement.

### If you're writing a plugin

```toml
dependencies = [
    "data-product-forge-sdk>=0.10,<1",   # upper bound is important
]
```

The upper bound `<1` matters: the SDK is on the 0.x line and a minor version may break the API. Widen it (`<1` → `<2`) only after testing against the new major version.

For the custom-scaffold engine (if you're shipping bundles that ride on it):

```toml
dependencies = [
    "data-product-forge-sdk>=0.10,<1",
    "data-product-forge-custom-scaffold>=0.4,<0.5",
]
```

### If you're a plugin author shipping to PyPI

Your **plugin** ships with a pinned SDK requirement; your **users** install your plugin and let pip resolve the SDK transitively. That means **you control which SDK version they use**.

Best practice:
1. Pin to the lowest SDK version your plugin actually needs.
2. Run CI against multiple SDK versions to confirm the lower bound is real.
3. Bump the upper bound only after testing against a new SDK release.

## Version stability commitments

### `data-product-forge` (CLI)

- **Pre-1.0.** The `fluid_build.api` package follows SemVer ([API stability](../../advanced/api-stability.md)). CLI behaviour outside it can change in a minor or a patch release; the CHANGELOG lists the changes.
- **Contract versions.** CLI 0.18.1 validates contracts declaring `fluidVersion` `0.7.1` through `0.7.5` (0.7.5 is the latest stable) and `0.7.6`, a preview you opt in to by declaring it.
- **Pre-releases** are tagged with PEP 440 suffixes (`0.8.4rc1`, `0.8.4b1`, etc.). They publish to PyPI but `pip install` skips them by default.

### `data-product-forge-sdk`

- **Currently 0.10.0, with a Beta classifier.**
- **0.10.0** is additive in practice (still pin the upper bound `<1`). It adds: four real role ABCs — `InfraProvider` (role `"provider"`) and `CatalogAdapter` (role `"catalog"`) are now first-class roles whose `apply` is abstract on purpose (a plugin that forgets to implement it fails loud, never a silent no-op), each with an action builder (`provision_action` / `catalog_entry_action`); typed value domains `Severity` / `ActionStatus` / `Phase` plus `FAILING_SEVERITIES`, with a fail-safe `Severity.coerce` (an unrecognised severity counts as ERROR, never silently passes); `PluginCapabilities` + `BasePlugin.capabilities()` for typed plugin self-description; an SDK↔CLI compat declaration (`SDK_PROTOCOL_VERSION` / `MIN_CLI_VERSION` / `cli_requirement()` / `PluginMetadata.requires_cli`) — the SDK declares, the CLI gates; and three role conformance harnesses (`ValidatorTestHarness`, `InfraProviderTestHarness`, `CatalogAdapterTestHarness`).
- **0.9.1** added `iter_extension_schemas()` and the `fluid_build.extension_schemas` group — additive, no breaking change.
- Minor versions (0.9 → 0.10) may break the API; 0.10.0 did not. Pin the upper bound (`<1`).

### `data-product-forge-custom-scaffold`

- **Currently 0.4.1, with a Beta classifier.**
- **0.4.0** adds copier-parity reproducibility — a deterministic, credential-free `fluid-scaffold.lock` written to the output root after a successful (non-dry-run) generation (records the resolved git commit); `--pin` to resolve git sources to the locked commit (npm-ci / poetry-frozen semantics, byte-reproducible); `--update [--target REF]` to re-render at the locked base plus a new ref and 3-way-merge onto your working tree via `git merge-file` (conflict markers + exit code 4 on overlap, the lock advancing on a clean merge); a fix for `git@<full-commit-sha>` source pinning; and real enforcement of a bundle's `variables_schema` (JSON Schema Draft 7) at plan time plus `supportedProductTypes` vs `metadata.productType` (the `when` / `environments` pattern fields remain RESERVED). All additive.
- **0.1.1** shipped the `customScaffold` JSON-Schema as a real package artifact, advertised it to the `fluid forge` copilot via `fluid_build.extension_schemas`, and added **white-label spec dialects** (`ScaffoldDialect` + `make_validator()` / `make_register()` factories) so a third party can reuse the engine under their own `apiVersion`, `extensions.<key>`, and subcommand.
- The bundle manifest format is **`fluid.dev/custom-scaffold.v1`**; a bundle declares it in `apiVersion`.

## Where to find the source

| Package | Repo | License |
|---|---|---|
| `data-product-forge` | [`Agenticstiger/forge-cli`](https://github.com/Agenticstiger/forge-cli) | Apache-2.0 |
| `data-product-forge-sdk` | [`Agenticstiger/forge-cli-sdk`](https://github.com/Agenticstiger/forge-cli-sdk) | Apache-2.0 |
| `data-product-forge-custom-scaffold` | [`Agenticstiger/data-product-forge-custom-scaffold`](https://github.com/Agenticstiger/data-product-forge-custom-scaffold) | Apache-2.0 |

Issues, PRs, and discussions all happen on the upstream repos. The `examples/` directories on each contain runnable starting points.

## Upgrade compatibility

| You're upgrading | From → To | What might break |
|---|---|---|
| CLI | 0.9.0 → 0.10.0 | Released. Additive — adds plugin governance (`FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST`), the `fluid plugins` / `fluid exporters` commands, and wires the `Validator` / `CatalogAdapter` / IaC-provider roles end-to-end. (odps/odcs were reclassified from providers to exporters; the export commands are unchanged.) |
| SDK | 0.9 → 0.10 | Released. Additive in practice — new first-class roles (`InfraProvider` / `CatalogAdapter`), typed value domains, `PluginCapabilities`, the SDK↔CLI compat declaration, and three role harnesses. Keep the upper bound (`<1`). |
| Custom-scaffold | 0.1.x → 0.4.0 | Released. Additive — new `--pin` / `--update` flags and a new `fluid-scaffold.lock` lockfile; bundle manifest format unchanged (`v1`). Bump the upper bound (`>=0.4,<0.5`). |

## Reference

- [Packaging](./packaging.md) — how to ship a plugin to PyPI
- [Roles](./roles.md) — the four roles and their helpers
- [Entry points](./entry-points.md) — the entry-point groups and when to use each
- [Trust model](./trust-model.md) — what the CLI guarantees about plugins
