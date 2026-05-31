# Fluid Forge Docs Baseline: CLI `0.8.7`

**Release Date:** May 30, 2026
**Status:** Superseded by [`0.8.8`](./RELEASE_NOTES_0.8.8.md) (supersedes [`0.8.6`](./RELEASE_NOTES_0.8.6.md))

## Headline

`0.8.7` is a **schema-correctness patch**: it makes contract schema `fluidVersion` **`0.7.4` a true backward-compatible superset of `0.7.3`** again. The `0.7.4` schema that shipped in `0.8.6` — introduced by the MCP "schema-minimize" refactor — silently dropped fields that `0.7.4` still advertised as fully `0.7.3`-compatible, so some valid `0.7.3` contracts failed `0.7.4` validation. `0.8.7` restores every dropped field. No new schema features and no CLI surface changes.

::: tip Who should upgrade
If you authored or validated contracts on `0.8.6` and hit unexpected validation errors on `governance`, Snowflake / Redshift bindings, or the `athena` / `glue` / `redshift` platforms, upgrade to `0.8.7`. Contracts need no edits.
:::

## What changed in `v0.8.7`

### Fixed

- **`0.7.4` is backward-compatible with `0.7.3` again (#162).** The schema-minimize refactor that introduced `fluid-schema-0.7.4.json` dropped fields `0.7.4` claimed to keep. Restored:
  - top-level and per-binding **`governance`** — AWS Lake Formation admins, LF-tag definitions, principal grants, row/column filters;
  - the **`snowflake_view`**, **`redshift_table`**, **`redshift_serverless`**, and **`redshift_external_schema`** binding formats;
  - the **`athena`**, **`glue`**, and **`redshift`** runtime platforms;
  - **`datamesh_manager`** catalog registration and the **`opentofu`** deployment target.

  Every genuine `0.7.4` addition is retained — `expose.mcp`, the `postgres` platform, and the `postgres_table` / `athena_table` / `glue_table` binding formats.
- **Stale `0.7.3` schema fallbacks no longer freeze the default (#163).** Three "schema-discovery-came-up-empty" fallbacks (`cli/validate.py`, `cli/version_cmd.py`, `forge/core/validation.py`) and four hardcoded defaults in `cli/plan.py` still pointed at `0.7.3`. They now derive from `FluidSchemaManager.latest_bundled_version()`, so the bundled-schema default tracks the newest version instead of drifting each release.

### Unchanged

No new commands, flags, or schema features. The `0.8.6` surface — the MCP output-port gateway, JWT / mTLS gateway identity, the BigQuery row-access + AWS Lake Formation IAM compilers, the PostgreSQL + Athena drivers, PII / PHI redaction, and the audit webhook — carries forward as-is. Contract schema stays at `fluidVersion 0.7.4`.

---

## Upgrade

```bash
pip install --upgrade "data-product-forge==0.8.7"
```

Contracts need no changes — both `0.7.3` and `0.7.4` contracts validate.
