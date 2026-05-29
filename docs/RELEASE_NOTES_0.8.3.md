# Fluid Forge Docs Baseline: CLI `0.8.3`

**Release Date:** May 25, 2026
**Status:** Current stable docs baseline (supersedes [`0.8.0`](./RELEASE_NOTES_0.8.0.md))

## Headline

`0.8.3` is the **first stable release on the `0.8.x` line after `v0.8.0`**. It folds five post-`v0.8.0` PRs — ODCS + Bitol ODPS bidirectional provider with SSRF-hardened HTTP (#136), CLI dispatch + smoke hardening on `stats` and `generate-pipeline` (#137), unified catalog registry with world-class DataHub + Data Mesh Manager `SourceSystem` lineage (#138), tier-0 import-hygiene SSRF gate with `import-linter` contracts (#139), and the **OpenTofu autogenerator** that recasts `fluid apply` for cloud providers as a contract compiler (#140). It also graduates the previously-pre-released `v0.8.3rc1` plugin extension points + `v0.7.3` acquisition-pattern engine as stable. No schema break vs `v0.8.0`.

## Folds from `v0.8.0` — five PRs since the previous tagged release

### PR #136 — ODCS + Bitol ODPS bidirectional provider + `--seed-from`

`BitolOdpsProvider` (registered as `odps_bitol`, alias `odps-standard`) emits the canonical Bitol fragments layout (one ODPS doc + N sibling `<contractId>.odcs.yaml` files); the linking invariant `port.contractId == odcs.id` is asserted in tests. A new unified `fluid odps` command dispatches between specs via `--spec`:

- `fluid odps export <contract> [--spec bitol-1.0.0|odpi-4.1]`
- `fluid odps import <path>     [--spec bitol-1.0.0] [--allow-remote]`
- `fluid odps validate <file>`
- `fluid odps info`

`fluid odps import` accepts three entry shapes — single ODPS doc, directory bundle, or a lone ODCS file. The `ContractResolver` resolves `contractId` references through local probes + opt-in `http(s)` fetch with the full SSRF guard (see Security below).

`fluid forge --seed-from <path>` accepts an ODCS contract, a Bitol ODPS product, or a directory bundle as a **structural seed** for the copilot. The schema / quality / qos from the seed are treated as ground truth; the LLM fills in builds, execution, and governance. Pair with `--seed-allow-remote` to opt in to `http(s)` seed sources; remote fetch is **off by default**.

The ODCS provider was modularised under `providers/odcs/` with paired `to_fluid()` / `to_odcs()` mappers and per-level `odcs_passthrough` buckets for lossless round-trip. `roundtrip_check()` returns a structured diff used by tests and the forge ground-truth guard.

### PR #137 — CLI dispatch wired on `stats` and `generate-pipeline`

Both subparsers now carry `set_defaults(func=run)` so `fluid stats` and `fluid generate-pipeline` dispatch to the implementation instead of falling through to the no-subcommand-selected help guide. Pinned by a smoke test that parses every registered subparser and asserts the `func` attribute is set.

If you've been hitting "no subcommand selected" on `fluid stats` or `fluid generate-pipeline` on `v0.8.0`, this release fixes it.

### PR #138 — Unified catalog registry + world-class DataHub + DMM `SourceSystem` lineage

One registry (`build_runners/catalog_registrars/__init__.py::build_registrar`) instantiates every backend from a uniform `CatalogPublicationPayload`. **Three active publish-side registrars:** `datahub`, `openmetadata`, `datamesh_manager`. Contracts opt in via `properties.catalog.register: [<name>]`.

- **DataHub** emits canonical MCPs with full schema + ownership + tags + descriptions; `FLUID_LAYER_PROPERTY_ID` / `FLUID_PRODUCT_TYPE_PROPERTY_ID` structured properties surface medallion classification.
- **Data Mesh Manager** emits proper `SourceSystem` lineage links rather than the prior flat dataset list; per-port `contractId` references resolve to sibling ODCS contracts.

**Retired publish-side registrars** — `glue` and `snowflake_horizon` are gone (see PR #140 below). Contracts that still list them under `properties.catalog.register` get a "not configured" result; drop the entry and let the auto-routed OpenTofu engine (`fluid apply` against an `aws` / `snowflake` provider) manage the catalog metadata as IaC.

See the new [catalog overview](./cli/catalogs/overview.md) for the full publish-side flow.

### PR #139 — Tier-0 SSRF gate + import-linter architecture contracts

The canonical post-DNS-resolution SSRF check (`_hostname_is_private` — RFC1918 + link-local 169.254.0.0/16 + loopback + reserved + IPv4-mapped IPv6 unwrap, fails closed on DNS errors) moved to a new tier-0 leaf module so `observability/reporter.py` can use it without importing `build_runners` (closes a cycle that previously broke `cli/__init__.py` import).

Two declarative `[tool.importlinter]` contracts in `pyproject.toml` gate the architecture in CI:

1. `observability ↛ build_runners`
2. `_net` is tier-0 (no `fluid_build.*` upstreams)

Wired into the pre-commit hook and a new `import-hygiene` CI job. Four subprocess-isolated regression tests pin the contracts.

User-visible effect: there is no new `fluid lint-imports` subcommand. The contracts are enforced by the upstream `import-linter` tool during development; runtime CLI behaviour is unchanged.

### PR #140 — OpenTofu autogenerator: `fluid apply` becomes a contract compiler for cloud providers

New `fluid_build/iac/` module with a modular `IacProviderPlugin` per cloud (dbt-adapter pattern). Built-in plugins for **AWS / GCP / Snowflake**. The cloud providers compile the contract to a deterministic OpenTofu `main.tf.json` and delegate apply / state / drift / idempotency to the `tofu` binary; `local` keeps its native apply.

New CLI surface:

- `fluid generate iac <contract>` — review-only emit of `.tf.json`
- `fluid apply` auto-routes cloud providers through `iac.cutover.resolve_engine`

The plan-binding integrity gate from the native engine is replicated at `_apply_opentofu_engine.py::_verify_plan_binding_for_opentofu` — a tampered `plan.json` is rejected before any `tofu apply`. `--no-verify-plan-binding` is the emergency escape hatch and logs at WARNING.

**Operational requirement:** `tofu ≥ 1.6.0` on `PATH` for cloud provider apply. `require_tofu_version()` catches the silent `terraform`-on-`PATH`-as-`tofu` mixup. Per-subprocess timeout defaults to 1800 s; override via `FLUID_TOFU_TIMEOUT_SECONDS`.

**Brownfield import:** `tofu import` is wired for all three plugins via `discover_imports`, so existing cloud resources can be folded into the IaC layer without recreate.

See the new [`fluid generate iac` page](./cli/generate-iac.md).

## What was already in `v0.8.3rc1` (graduates to stable here)

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

All six ingestion engines are GA: `duckdb`, `airbyte`, `meltano`, `dlt`, `kafka-connect`, `debezium`. `fluid validate --probe` extends validation with live external probes (secret resolution, source connectivity, image-signature presence, source schema fingerprint vs baseline). The `metadata.productType` field (SDP / ADP / CDP) is now a first-class classification alongside `metadata.layer` (Bronze / Silver / Gold); both vocabularies coexist and the validator enforces consistency when both are set.

### Security hardening (plugin trust surface)

- **Apply hooks receive `copy.deepcopy(contract)`** rather than the live reference. A buggy or malicious hook cannot mutate the contract the rest of apply (or other hooks) consume.
- **Plugin exception text is pre-scrubbed** with `redact_secret_text` before reaching logs or the errors list.

## Security

### Shared SSRF guard across every HTTP fetch surface (#136)

One factory routes every outbound `http(s)` call through: scheme allowlist + private / loopback / link-local / CGNAT / 6to4 / NAT64 / ORCHIDv2 / IPv6-SR / RFC-TEST-NET filter + IPv4-mapped IPv6 unwrap (closes a Python 3.10 / 3.11 bypass — stdlib `is_private` only recurses into IPv4-mapped in 3.12+) + reject-all on mixed-public+private DNS + connection-layer DNS pin (via httpx's `sni_hostname` extension) + `follow_redirects=False` default + streaming body cap (10 MiB).

Seven fetch surfaces were migrated in one pass: `ContractResolver`, `KafkaConnectRestClient` + its schema-registry client, the Airbyte REST client, the three publish-side catalog registrars, the Databricks auth-provider's API check, and the schema-manager remote fetcher.

See the new [network safety](./advanced/network-safety.md) page.

### Plan-binding gate replicated in the OpenTofu engine (#140)

`_apply_opentofu_engine.py::_verify_plan_binding_for_opentofu` mirrors the native engine's stage-7 `bundleDigest` + `planDigest` verification. A tampered `plan.json` is rejected before any `tofu apply` for AWS / GCP / Snowflake. `--no-verify-plan-binding` is the emergency escape hatch and logs at WARNING.

### `bootstrap.py` imports `redact_secret_text` at module top

Rather than nested inside an except branch — closes a defense-in-depth gap surfaced by security review.

## Notable for upgraders

- **BREAKING (caller API) — `allow_remote` defaults to `False`** across CLI + library (#136). `fluid odps import` and `fluid forge --seed-from` no longer fetch `http(s)` `contractId` references unless `--allow-remote` / `--seed-allow-remote` is passed explicitly. Python callers of `BitolOdpsProvider().import_contract(...)`, `BitolOdpsProvider().import_directory(...)`, `ContractResolver(...)`, and `forge_copilot_seed.load_seed(...)` must now pass `allow_remote=True` for the previous behaviour. `--no-remote` / `--seed-no-remote` remain as hidden no-op aliases.
- **Operational requirement: `tofu ≥ 1.6.0` on `PATH`** for cloud-provider `fluid apply` (#140). `local` is unaffected.
- **Catalog registrar retirement** — drop `glue` and `snowflake_horizon` from `properties.catalog.register`; the metadata they previously pushed is now emitted by the auto-routed OpenTofu engine when you `fluid apply` against the `aws` / `snowflake` provider (#140).
- **Existing contracts keep working.** `fluidVersion` `0.4.0`, `0.5.7`, `0.7.1`, `0.7.2`, and `0.7.3` all validate against `0.8.3`. The discover emitter populates both `metadata.layer` and `metadata.productType` automatically.
- **Python `>=3.10` floor** remains — anyone still on 3.9 should pin to `data-product-forge<0.8.3`.
- **Plugins are uncontained.** A plugin is third-party Python loaded into the CLI process. Trust = pip trust. Read [SDK & Plugins → Trust Model](./sdk-and-plugins/reference/trust-model.md) before installing community plugins.

## Dependency floor & supply-chain hygiene

`v0.8.3` raises minimum-version pins on several deps to close known CVEs:

- `jinja2 >= 3.1.6` — closes CVE-2025-27516 (sandbox escape via `|attr`)
- `h11 >= 0.16` — closes CVE-2025-43859 (chunked request smuggling)
- `litellm >= 1.83.7, < 2` — closes CVE-2026-42208 (CVSS 9.3 SQLi); **skips the compromised `1.82.7` / `1.82.8` PyPI artifacts**
- `cryptography >= 46.0.7` — closes CVE-2026-26007 / 39892 / 34073
- `mcp >= 1.20` — required for `sampling_capabilities` in `fluid mcp serve`
- `keyring >= 24.0` — **now a hard dependency** (was opt-in). Catalog source secrets default to the OS keyring; the legacy plaintext YAML fallback is gated behind `FLUID_ALLOW_PLAINTEXT_SOURCE_SECRETS=1` *and* file `chmod 600`.

## What changed in the docs

- New top-level section: **[SDK & Plugins](./sdk-and-plugins/)** — landing, four runnable examples (`hello-scaffold`, `gitlab-ci-scaffold`, `steward-validator`, `apply-hook-bundle-digest`), four journey-oriented guides, and a reference set.
- New CLI pages: [`fluid generate iac`](./cli/generate-iac.md), [`fluid forge --seed-from`](./cli/forge.md#seeding-from-an-existing-odcs-or-bitol-odps-contract), [catalog overview](./cli/catalogs/overview.md), [OpenMetadata catalog](./cli/catalogs/openmetadata.md).
- New advanced references: [environment variables index](./advanced/environment-variables.md), [network safety](./advanced/network-safety.md).
- New recipes: [consumes-contract-to-contract](./recipes/consumes-contract-to-contract.md), [per-environment overlays](./recipes/per-environment-overlays.md).
- Docs baseline pinned to `0.8.3` across `getting-started`, `providers`, FAQ, see-it-run.

## Installing

The `v0.8.3` stable tag is in the source tree; the PyPI publish lands shortly after the tag. While the publish is in flight (or if your environment has cached the older PyPI index), use `--pre` to pull the functionally-equivalent release candidate:

```bash
# Once 0.8.3 stable is on PyPI:
pip install --upgrade data-product-forge
pip install "data-product-forge==0.8.3"

# While the PyPI publish is in flight:
pip install --pre data-product-forge        # resolves to 0.8.3rc1
fluid version
# -> 0.8.3rc1   (functionally equivalent to the 0.8.3 stable tag)
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
