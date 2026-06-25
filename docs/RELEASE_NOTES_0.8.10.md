# Fluid Forge Docs Baseline: CLI `0.8.10`

**Release Date:** June 8, 2026
**Status:** Superseded by [`0.8.11`](./RELEASE_NOTES_0.8.11.md) (supersedes [`0.8.9`](./RELEASE_NOTES_0.8.9.md))

## Headline

`0.8.10` makes the CLI **introspectable** and hardens day-2 operations. `fluid describe --self` now returns a complete, machine-readable picture of the installed CLI — version, schema, providers, build engines, templates, capabilities, and the full command tree — so tooling can render the live CLI surface without lagging it. Alongside it: opt-in (default-OFF) usage telemetry, BigQuery `fluid rollback` support, broader `fluid generate iac` cloud detection, and a batch of security fixes. No contract-schema change — contracts stay at `fluidVersion: 0.7.4`.

::: tip Who should upgrade
Everyone on `0.8.x`. The security fixes in this release (`#215`) close injection / RCE / RLS findings across generated Airflow DAGs, the Redshift external-schema emit, and the MCP query tools — upgrading is recommended for any production deployment.
:::

## What changed in `v0.8.10`

### Added

- **`fluid describe --self` capability introspection.** Library-callable `fluid_build.describe.self_describe()` returns `fluid_version`, `schema_version`, `providers`, `build_engines`, `templates`, `capabilities`, and the full **command tree** (every subcommand + its flags), consumed via `GET /api/v1/forge/capabilities` so a UI can render the CLI surface without lagging it. (#220)
- **Opt-in usage telemetry, default OFF.** Nothing is emitted unless you explicitly opt in; honours `FLUID_TELEMETRY=0` and the `DO_NOT_TRACK` standard, and the resolved state is surfaced in `fluid doctor`. (#217)
- **Reuse an existing LLM API key during AI setup.** `fluid` AI setup now offers to persist a recognised built-in-provider key already present in your environment — read-only, explicit confirmation, never logged. (#217)
- **Contract diff before writing on refine/regenerate.** The refine/preview flow now shows what changed (reusing the changelog differ) before the contract is written. (#217)

### Fixed

- **BigQuery rollback restore.** `fluid rollback` now restores BigQuery products (previously Snowflake only), replaying the snapshot's `CREATE OR REPLACE TABLE … AS SELECT` via the BigQuery client with a `gcp` dispatch alias. (#217)
- **`fluid generate iac --provider auto` detection broadened.** The target cloud is now detected from top-level `binding.{provider,platform}`, `builds[].provider`, and the runtime platform — not just `exposes[].binding.platform` — fixing the common single-binding contract that previously errored as "could not detect a supported cloud". `local` / DuckDB now raises an actionable `generate_iac_local_target` error. (#211)
- **`odps` export fails loud.** `fluid generate standard --format odps-v4.1` / `fluid odps export` now error instead of silently writing the literal `[]` to disk while exiting 0. (#211)
- **CI resilient to transient OpenTofu registry outages** — `tofu init` 504 / network failures convert to skips while real `tofu validate` schema errors still fail. (#218)

### Changed

- Renamed `providers/snowflake/provider_enhanced.py` → `provider.py` (canonical `SnowflakeProvider`); class name and entry points are unchanged. (#217)
- Added a startup-budget perf gate (`fluid --help` module-count + cold wall-time in clean subprocesses) to catch CLI-startup regressions. (#217)

### Security

- **Fixed injection / RCE / RLS findings across the platform. (#215)**
  - Code-injection (RCE) in generated Airflow DAGs — untrusted contract values are now routed through repr-escaped literals / sanitised identifiers.
  - Shell-RCE + SQL injection in the Redshift external-schema emit — closed.
  - Multi-tenant row-level-security **bypass** in the MCP `query` / `query_sql` tools — they now apply `policy.rowFilters[]` and fail closed on missing caller identity.
