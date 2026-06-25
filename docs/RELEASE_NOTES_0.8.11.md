# Fluid Forge Docs Baseline: CLI `0.8.11`

**Release Date:** June 16, 2026
**Status:** Superseded by [`0.9.0`](./RELEASE_NOTES_0.9.0.md) (supersedes [`0.8.10`](./RELEASE_NOTES_0.8.10.md))

## Headline

`0.8.11` makes `fluid forge data-model` **extensible without forking the CLI**. Two new entry-point groups let a third-party package plug in its own behaviour: `fluid_build.source_adapters` registers a custom metadata-catalog source (e.g. an internal / enterprise catalog) that merges into the `--source` choices, and `fluid_build.modeling_techniques` makes `--modeling-technique` open-ended. Two new built-in techniques ship too: **`flat`** (source-aligned 1:1) and **`custom`** (bring-your-own logical model). No contract-schema change — contracts stay at `fluidVersion: 0.7.4`.

::: tip Who should upgrade
Teams that want `fluid forge data-model` to read from an in-house metadata catalog, or to model with a technique beyond the built-in `data_vault_2` / `dimensional` — both are now pluggable. Also recommended for anyone authoring dbt-engine contracts: `fluid validate` now accepts the full `dbt-<adapter>` engine family and the `properties.target` / `select` / `models` keys the dbt runner already honoured.
:::

## What changed in `v0.8.11`

### Added

- **Pluggable metadata source adapters for `fluid forge data-model from-source`.** A new `fluid_build.source_adapters` entry-point group lets a third-party package register a custom `CatalogAdapter` (e.g. an internal / enterprise metadata catalog) that merges into the `--source` choices and dispatch — and into the `forge_from_source` MCP tool — without forking the CLI. Built-in catalog + JDBC sources now resolve through one shared registry (the two previously duplicated dispatch tables are gone). (#247)
- **Pluggable modeling techniques, plus `flat` and `custom`.** A new `fluid_build.modeling_techniques` entry-point group makes `--modeling-technique` extensible. Two new built-ins: **`flat`** (source-aligned 1:1 — one expose per source table, no reshaping) for bronze / source-aligned products, and **`custom`** (bring-your-own logical model used verbatim via `--logical-model <path>`, no reshaping). The closed `{data_vault_2, dimensional}` enum is now a registry the modeler and contract emitter read instead of branching on the technique name. (#248)

### Fixed

- **Contract schema now accepts dbt features the build runner already supported.** `build.engine` accepts the whole `dbt-<adapter>` family (`dbt-glue`, `dbt-snowflake`, …) generically, and the hybrid-reference build pattern accepts `properties.target`, `properties.select`, and `properties.models` — all of which the dbt runner already honoured but `fluid validate` rejected. Applied across every bundled schema (0.7.1–0.7.4). (#249)
- **Nightly live-LLM / TS-conformance gate** no longer false-fails when no LLM API key is wired; duplicate `CircuitBreakerOpenError` definitions consolidated into `fluid_build/errors.py`. (#223)
- **CI Docker base bumped to `python:3.13-slim`** with grype-ignores for the unfixable CPython CVEs. (#226)

### Security

- **`Dockerfile.verify` now runs as a non-root user** (`fluid`, UID/GID 1000, overridable via `--build-arg UID/GID` for Linux hosts), closing trivy DS-0002 and matching the production image's non-root posture. (#235)
- **`.gitleaks.toml` with triaged allowlists** so full-history `gitleaks detect` scans run clean. Requires gitleaks ≥ 8.25.0. (#236)

### Changed

- Dependency / CI-action bumps via Dependabot: black 26.3.1→26.5.1 (#232), plus `actions/setup-node`, `actions/setup-go`, `actions/github-script`, `github/codeql-action`, `docker/metadata-action`, `docker/login-action`, `docker/setup-buildx-action`, `aws-actions/configure-aws-credentials`, `peter-evans/create-pull-request`, and `softprops/action-gh-release`.
