# Fluid Forge Docs Baseline: CLI `0.8.8`

**Release Date:** May 31, 2026
**Status:** Current stable docs baseline (supersedes [`0.8.7`](./RELEASE_NOTES_0.8.7.md))

## Headline

`0.8.8` delivers two headline improvements: an **on-demand OpenTofu provisioner** — `fluid apply --ensure-opentofu` downloads a pinned, SHA-256-verified `tofu` using only the Python standard library (no root, gpg, cosign, curl, or unzip), so cloud applies finally run on locked-down / non-root CI runners (a non-root Jenkins agent is the canonical case); and a **real `fluid market`** — catalog discovery now runs over MCP against DataHub, OpenMetadata, and Data Mesh Manager (replacing the previous demo data), with two-phase metadata enrichment and offline blueprints. No schema change vs `0.8.7` (contract schema stays at `fluidVersion 0.7.4`).

::: tip Who should upgrade
Anyone running `fluid apply` against AWS / GCP / Snowflake from CI — especially non-root runners that previously failed with `opentofu_engine_no_tofu`. Also anyone using `fluid market` against a real DataHub / OpenMetadata / Data Mesh Manager catalog.
:::

## What changed in `v0.8.8`

### Added

- **On-demand OpenTofu provisioner — `fluid apply --ensure-opentofu`.** Cloud
  applies (AWS / GCP / Snowflake) run through the OpenTofu engine, which shells
  out to `tofu`. The official standalone installer needs **root** (`/usr/local/bin`)
  and **gpg/cosign** to verify — which a non-root CI agent can't provide, so
  generated cloud-apply pipelines failed on a fresh runner with
  `opentofu_engine_no_tofu`. When `--ensure-opentofu` is set and `tofu` is
  missing, FLUID downloads the pinned OpenTofu release zip + its `SHA256SUMS`
  over TLS, **verifies the SHA-256 before extracting**, extracts **only** the
  `tofu` entry (no zip-slip), installs it to a writable dir (the console-scripts
  dir, else `~/.cache/fluid`), and prepends it to the process `PATH`. It uses
  **only the Python standard library** — no root, gpg, cosign, curl, or unzip —
  and is **idempotent** (a usable `tofu` at/above the engine's version floor is
  left untouched, so a pre-baked runner image still wins). Override the pinned
  version with `FLUID_OPENTOFU_VERSION`.

  ```bash
  # provision tofu on demand if it's missing, then apply
  fluid apply runtime/plan.json --ensure-opentofu --yes
  ```

  `fluid generate ci` bakes `--ensure-opentofu` into the apply stage of **all
  seven CI runners** (Jenkins, GitHub Actions, GitLab, Azure DevOps, Bitbucket,
  CircleCI, Tekton). The flag is idempotent and a no-op for native / `local`
  applies that never touch the OpenTofu engine.

- **`fluid market` real catalog discovery over MCP** — DataHub, OpenMetadata,
  and Data Mesh Manager, replacing the previous demo data.
- **`fluid market` metadata enrichment** — a two-phase fetch surfaces full
  product detail plus data-asset column schema; `--detailed` is now a true
  superset of the listing rather than a replacement.
- **`fluid market` onboarding + trust/usage surfacing** — actionable next steps
  and trust / usage signals in the listing.
- **`fluid market --blueprints` works offline** via bundled blueprints.

### Changed

- `fluid market` no longer serves fabricated demo data for roadmap-only catalog
  connectors (datahub / glue / data-catalog / rest); they are skipped with a
  clear roadmap note.
- `fluid market --format json` emits clean, machine-parseable output.
- Faster CLI startup — validation providers are lazy-loaded.

### Fixed

- **Generated dev-source Jenkins pipelines could not call `fluid`.** The
  dev-source bootstrap ran `pip uninstall -y data-product-forge` — deleting the
  `fluid` console script (the package's entry point) — then invoked `fluid`
  relying only on `PYTHONPATH`, so stage 0 died with `fluid: not found`. The
  bootstrap now keeps the installed console script (a `PYTHONPATH` prepend
  already shadows its modules with the bind-mounted checkout) and sanity-checks
  the import.
- **Generated Jenkins `policy-apply` stage emitted an empty `--mode`** on the
  first build (before the param is injected), which `fluid policy-apply`
  rejected; it now defaults to `enforce`.
- `fluid forge --from-source` sanitizes the contract id derived from a sqlite
  file path.
- build-runners now warn when an inline-SQL build declares `engine: dbt`
  (previously silently ignored).
- `fluid policy-apply` surfaces a no-op message when a provider has no policy
  applier instead of appearing to succeed silently.
- `fluid market` per-catalog MCP search-limit param corrected (OpenMetadata
  `size`, DataHub `num_results`), and the command raises a proper error instead
  of crashing with a `TypeError`.

### Removed

- Dead, never-wired-in modules: `fluid_build/validation.py` and the unused
  SQL-allowlist helpers (`parse_and_allowlist_sql` + type/language validators).

### Security

- Re-symmetrized the Snowflake provider-local secret redactor with the global
  logging filter so new secret shapes are masked in both layers.

---

## Upgrade

```bash
pip install --upgrade "data-product-forge==0.8.8"
```

Contracts need no changes — contract schema stays at `fluidVersion 0.7.4`,
unchanged from `0.8.7`.
