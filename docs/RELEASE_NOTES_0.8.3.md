# Fluid Forge Docs Baseline: CLI `0.8.3`

**Release Date:** May 12, 2026
**Status:** Current stable docs baseline (supersedes [`0.8.0`](./RELEASE_NOTES_0.8.0.md))

## Headline

`0.8.3` is the first release on the **plugin-extensible CLI**. Three new entry-point seams let external Python packages register their own `fluid <name>` subcommands, validate sub-keys of `contract.extensions`, and run apply-time invariant checks. The companion zero-dependency **`data-product-forge-sdk`** package and the reference **`data-product-forge-custom-scaffold`** engine are now on PyPI, so an external team can write a plugin with `pip install data-product-forge-sdk` and no further setup.

Beyond plugins, `0.8.3` graduates the v0.7.3 acquisition-pattern engine — six ingestion engines (DuckDB, Airbyte, Meltano, DLT, Kafka Connect, Debezium) are GA — and raises the Python floor to `>=3.10` to match the supported runtime of the SDK + plugin ecosystem.

## What's new in the CLI

### Plugin extension points

Three entry-point groups, discovered at CLI startup via `importlib.metadata.entry_points()`:

| Group | Hook site | What plugins do |
|---|---|---|
| `fluid_build.commands` | `fluid <subcommand>` registration | Add new top-level CLI commands. |
| `fluid_build.extension_validators` | `fluid validate` | Validate sub-keys of `contract.extensions` (e.g. `customScaffold`, your-own-namespace). |
| `fluid_build.apply_hooks` | `fluid apply` | Apply-time invariant checks (e.g. scaffold bundle digest drift). |

All three follow a uniform contract: plugin exceptions are trapped, pre-redacted, and folded into the normal error stream — a broken plugin **cannot** crash the CLI. The new `--force-pattern-drift` flag on `fluid apply` is the documented override for apply-hook errors during legitimate-drift situations. See [SDK & Plugins → Entry Points](./sdk-and-plugins/reference/entry-points.md) for the full reference.

### Companion packages on PyPI

| Package | Purpose | Install |
|---|---|---|
| **`data-product-forge-sdk`** (0.9.0) | Zero-dependency role-typed plugin ABCs + conformance harness | `pip install data-product-forge-sdk` (import: `from fluid_sdk import …`) |
| **`data-product-forge-custom-scaffold`** (0.1.0) | Reference custom-scaffold engine — Jinja+YAML or Python-plugin bundles | `pip install data-product-forge-custom-scaffold` |

Both are independently published and version-pinned. They follow the same `>=3.10` Python floor as the CLI. See [SDK & Plugins → Companion Packages](./sdk-and-plugins/reference/companion-packages.md).

### v0.7.3 acquisition-pattern engine — GA

The Source-Aligned Data Products work that shipped as `v0.8.2b1` on TestPyPI graduates to PyPI proper. All six ingestion engines are GA:

- **`duckdb`** — local-first, includes the late-arrival side-output and replay-on-cursor-rewind.
- **`airbyte`** — full source × destination matrix, signed image support.
- **`meltano`** — tap × target × mode coverage with the new Meltano runner protocol.
- **`dlt`** — declarative pipelines with conformance to the Runner Protocol.
- **`kafka-connect`** — connector emitters with late-arrival policy surfacing.
- **`debezium`** — CDC source emitters with the same late-arrival behavior.

`fluid validate --probe` extends validation with live external probes (secret resolution, source connectivity, image-signature presence, source schema fingerprint vs baseline). The `metadata.productType` field (SDP / ADP / CDP) is now a first-class classification alongside `metadata.layer` (Bronze / Silver / Gold) — both vocabularies coexist; the validator enforces consistency when both are set.

### Security hardening (plugin trust surface)

`0.8.3` adds two defense-in-depth measures on the new plugin path:

- **Apply hooks receive `copy.deepcopy(contract)`** rather than the live reference. A buggy or malicious hook cannot mutate the contract the rest of apply (or other hooks) consume.
- **Plugin exception text is pre-scrubbed** with `redact_secret_text` before reaching logs or the errors list. The existing `SecretRedactingFilter` only scrubs args bound to `password=%s`-style template tokens; plugin exceptions are free-form text that can carry credential-shaped substrings anywhere.

Test pinning lives in `tests/test_cli_plugin_hooks.py` (19 tests). Threat model and override flags are documented at [SDK & Plugins → Trust Model](./sdk-and-plugins/reference/trust-model.md).

### Python floor raised to `>=3.10`

Matches the SDK + scaffold packages. The 3.9 line is no longer in the CI matrix (3.10 / 3.11 / 3.12 / 3.13 / 3.14 are tested per release).

## Notable for upgraders

- **Existing contracts keep working.** `fluidVersion` `0.4.0`, `0.5.7`, `0.7.1`, `0.7.2`, and `0.7.3` all validate against `0.8.3`. The discover emitter populates both `metadata.layer` and `metadata.productType` automatically.
- **The Python `>=3.10` floor** means anyone still on 3.9 should pin to `data-product-forge<0.8.3` or upgrade the interpreter.
- **Plugins are uncontained.** A plugin is third-party Python loaded into the CLI process. Trust = pip trust. Read [SDK & Plugins → Trust Model](./sdk-and-plugins/reference/trust-model.md) before installing community plugins.

## What changed in the docs

- New top-level section: **[SDK & Plugins](./sdk-and-plugins/)** — landing, four runnable examples (`hello-scaffold`, `gitlab-ci-scaffold`, `steward-validator`, `apply-hook-bundle-digest`), four journey-oriented guides ("you have your own CI, no problem" / scaffolding / validator / apply hook), and a reference set (roles, entry-points, trust-model, packaging, companion-packages).
- Docs baseline pinned to `0.8.3` everywhere (`cli-version.json`, getting-started, FAQ, see-it-run).
- Cross-links from `fluid validate` and `fluid apply` CLI pages into the new section.

## Installing

Stable PyPI:

```bash
pip install --upgrade data-product-forge

# Exact docs baseline:
pip install "data-product-forge==0.8.3"
fluid version
# -> 0.8.3
```

Want to try the next release candidate before it goes stable? Pre-releases ship to PyPI as PEP 440 pre-releases — `pip install` skips them by default. Opt in explicitly:

```bash
pip install --pre data-product-forge       # latest pre-release
pip install data-product-forge==0.8.4rc1   # exact pin
```

Author a plugin against the SDK:

```bash
pip install data-product-forge-sdk
# from fluid_sdk import BasePlugin, CustomScaffold, Validator
```

Plug in the reference custom-scaffold engine end-users will use:

```bash
pip install data-product-forge data-product-forge-custom-scaffold
fluid generate custom-scaffold
```

## Archive note

Older release notes remain available for historical context, including [`0.8.0`](./RELEASE_NOTES_0.8.0.md), [`0.7.11`](./RELEASE_NOTES_0.7.11.md), [`0.7.9`](./RELEASE_NOTES_0.7.9.md), and [`0.7.1`](./RELEASE_NOTES_0.7.1.md).
