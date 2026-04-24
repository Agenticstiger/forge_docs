# Fluid Forge Docs Baseline: CLI `0.8.0`

**Release Date:** April 24, 2026
**Status:** Current stable docs baseline (supersedes [`0.7.11`](./RELEASE_NOTES_0.7.11.md))

## What changed in the docs

- Pinned docs consistency checks to the stable PyPI package `data-product-forge==0.8.0`.
- Updated install guidance so normal users install from PyPI, while TestPyPI is documented only for release validation and intentional next-release candidates.
- Promoted the 11-stage production pipeline docs as the current CLI baseline.
- Documented Jenkins generation defaults for verify strictness, publish stage behavior, and publish `--env` handling.
- Documented Data Mesh Manager publishing behavior that uses Entropy Access lineage for Bronze-to-Silver product dependencies instead of duplicating SourceSystems.

## Notable CLI context

CLI `0.8.0` is the first stable release of the 0.8 line. It promotes the production pipeline and catalog-publish work that the docs were already tracking from the release-candidate branch:

- **11-stage CI pipeline** — `fluid generate ci` emits Jenkins and other CI templates for bundle, validate, generate-artifacts, validate-artifacts, diff, plan, apply, policy-apply, verify, publish, and schedule-sync.
- **Supply-chain controls** — bundle digests, plan binding, signed bundle verification, and SLSA-style attestation docs are part of the promoted surface.
- **Apply safety matrix** — `fluid apply --mode` covers dry-run, create-only, amend, amend-and-build, replace, and replace-and-build with explicit data-loss gating.
- **Catalog publishing** — `fluid publish --target ...` is the promoted catalog surface. Data Mesh Manager / Entropy publishing validates ODPS payload shape and emits Access lineage for product-to-product dependencies.
- **Jenkins lab ergonomics** — generated Jenkinsfiles can carry first-class defaults for strict verify, publish stage enablement, and publish `--env` behavior without post-generation text patching.

## Installing

Stable PyPI:

```bash
pip install --upgrade data-product-forge

# Exact docs baseline:
pip install "data-product-forge==0.8.0"
fluid version
# -> 0.8.0
```

TestPyPI is still useful for validating released artifacts and for the next alpha / beta / release-candidate line, but it is not the normal `0.8.0` install path:

```bash
pip install --pre \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  data-product-forge
```

## Archive note

Older release notes remain available for historical context, including [`0.7.11`](./RELEASE_NOTES_0.7.11.md), [`0.7.9`](./RELEASE_NOTES_0.7.9.md), and [`0.7.1`](./RELEASE_NOTES_0.7.1.md).
