# Fluid Forge Docs Baseline: CLI `0.7.11`

**Release Date:** April 16, 2026
**Status:** Current docs baseline (supersedes [`0.7.9`](./RELEASE_NOTES_0.7.9.md))

## What changed in the docs

- Pinned the supported CLI version in [`docs/.vuepress/cli-version.json`](./.vuepress/cli-version.json). One file to bump per CLI release.
- New CI workflow `cli-consistency.yml` installs the pinned CLI from PyPI and fails on docs ↔ CLI drift (version, command list, provider list).
- Documented every command registered by the CLI's `fluid_build/cli/bootstrap.py`. New pages:
  - `demo`, `skills`, `ai`
  - `contract-tests`, `contract-validation`, `policy-compile`, `policy-apply`
  - `scaffold-ci`, `scaffold-composer`, `generate-pipeline`, `provider-init`
  - `odps`, `odps-bitol`, `odcs`, `export`, `export-opds`, `datamesh-manager`
  - `product-new`, `product-add`, `workspace`, `ide`, `docs`
- Hidden / deprecated commands (`compile`, `context`, `graph`, `marketplace`, `preview`, `viz-plan`) are tracked in `scripts/cli-docs-allowlist.yml` rather than left as silent gaps.
- Sidebar regrouped to match the new CLI Reference index (Core, Generate, Standards & Interop, Integrations, Quality & Governance, Project & Workspace, CI & Scaffolding, Utilities).

## Notable CLI context

CLI `0.7.11` is a tooling release with no user-visible behavior changes. It rolls up the post-`0.7.9` work that was previously sitting in `Unreleased`:

- **PyPI distribution rename** — install with `pip install data-product-forge` (the old `fluid-forge` name no longer publishes new versions). The CLI binary stays as `fluid`, the Python import stays as `import fluid_build`, and Snowflake / Airflow runtime identifiers stay as `fluid-forge`.
- **Dynamic versioning via `setuptools-scm`** — wheels are now versioned from the git tag at build time. `fluid_build.__version__` reads from installed-package metadata, removing the version-drift bug that produced a `0.7.10` wheel for a `v0.7.10a1` tag.
- **Sequential TestPyPI → PyPI release pipeline** — every release tag now publishes to TestPyPI first, install-verifies in a fresh venv, then promotes to real PyPI only if the smoke test passes.
- **Master-schema validation on DMM publish** — `fluid datamesh-manager publish` validates the loaded contract against the schema matching its declared `fluidVersion` before constructing any provider payload. Default mode is `warn` (non-breaking); `--validation-mode strict` aborts on schema violations.
- **All 13 bundled init templates migrated to FLUID `0.7.2`** — the `fluid init` scaffolds and `fluid init --blank` now emit `fluidVersion: 0.7.2` contracts that pass strict validation out of the box.
- **ODPS input-port lineage** preserved when publishing to Entropy Data via `fluid datamesh-manager publish` with `provider_hint="odps"`.
- **Cross-version compatibility matrix** in the CLI test suite guards every export path (ODCS, official ODPS, ODPS-Bitol, DMM dry-runs) across FLUID `0.5.7` / `0.7.1` / `0.7.2` schema versions.

## Upgrading

```bash
# Old install
pip uninstall fluid-forge

# New install
pip install data-product-forge==0.7.11
fluid --version
# → 0.7.11
```

## Archive note

Older release notes remain available for historical context, including [`0.7.9`](./RELEASE_NOTES_0.7.9.md) and [`0.7.1`](./RELEASE_NOTES_0.7.1.md).
