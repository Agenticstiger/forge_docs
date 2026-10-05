---
title: FAQ
description: Common questions about Fluid Forge — comparisons, errors, upgrades, security.
---

# ❓ FAQ

A growing collection of common questions. Each answer either resolves the question on this page or points at the canonical doc.

## How is Fluid Forge different from dbt / Terraform / Airflow / OPA?

Short answer: it unifies the four contracts (schema + infra + orchestration + policy) into one contract, a single resolved document that you can write as one file or as a root plus [fragments](/forge_docs/concepts/fragments.html), so they can't drift. Long answer: see [Concepts → vs alternatives](/forge_docs/concepts/vs-alternatives.html) — there's a side-by-side ownership table.

## Why do I see `pip install fluid-forge` in some old docs and `pip install data-product-forge` in new docs?

The PyPI package was renamed. Canonical name as of v0.8.0: **`data-product-forge`** (the older `fluid-forge` listing is frozen at 0.7.9 and won't receive new releases). [Getting Started](/forge_docs/getting-started/) has the up-to-date install instructions for the current `0.18.1` release.

## What's the difference between `fluidVersion` and the CLI version?

`fluidVersion` is the **contract schema version** declared inside each YAML file (current: `"0.7.5"`). The CLI version is the version of the `data-product-forge` package itself (current: `0.18.1`). The CLI accepts contracts with `fluidVersion` `0.7.1`, `0.7.2`, `0.7.3`, `0.7.4` or `0.7.5`, plus `0.7.6` as a preview. `0.4.0` and `0.5.7` are not accepted and fail with `ERR_CONTRACT_VERSION_UNSUPPORTED`. Run `fluid version` for the authoritative compatibility list.

## Can I extend the CLI with my own scaffolding, validators, or governance rules?

Yes — Fluid Forge ships three plugin extension points (CLI commands, contract validators, apply hooks) and a companion zero-dependency SDK on PyPI. The journey docs walk you through the common cases: ["you have your own CI"](/forge_docs/sdk-and-plugins/journeys/your-own-ci.html), ["you have your own scaffolding"](/forge_docs/sdk-and-plugins/journeys/your-own-scaffolding.html), ["you have governance rules"](/forge_docs/sdk-and-plugins/journeys/custom-validator.html). Start at [SDK & Plugins](/forge_docs/sdk-and-plugins/).

## I get `No module named 'duckdb'` running the local quickstart.

You installed bare `data-product-forge` without the `[local]` extra. Fix:

```bash
pip install "data-product-forge[local]"
```

Or for an isolated CLI install: `pipx install "data-product-forge[local]"`.

## A local build says `duckdb not installed. Install it with: pip install duckdb`.

The same cause as above: the `[local]` extra is missing. Install `data-product-forge[local]`, which pins `duckdb>=1.5.0` for the contract-SQL sandbox.

## A local output file contains `id,value` and `1,materialized`.

That is the placeholder the local planner writes when it has no SQL to run, for example for a Python or acquisition build in the default `fluid apply` mode. The apply still reports success. Run the build with `--mode amend-and-build`; see [the default mode takes a simpler path](../walkthrough/local.md#the-default-mode-takes-a-simpler-path).

## Where do I report a bug or ask a question?

- **Bug?** [open an issue](https://github.com/Agenticstiger/forge-cli/issues/new) with `fluid version` + `fluid doctor` output.
- **Question?** [GitHub Discussions](https://github.com/Agenticstiger/forge-cli/discussions).
- **Security report?** See [SECURITY.md](https://github.com/Agenticstiger/forge-cli/blob/main/SECURITY.md).

## How do I upgrade?

```bash
pip install --upgrade "data-product-forge[local]"
fluid version
```

Then follow the [upgrade guide](../upgrading.md). It has a checklist for each version you cross, because some upgrades need action: `0.17.0`, for example, moves remote state to a per-provider key for a contract that uses a per-contract state key, and needs one `fluid schedule-sync` to retire old Airflow DAGs if you sync Airflow DAGs, and `0.16.3` changed some results on purpose. Pin an exact version in CI (`data-product-forge==0.18.1`), not a range.

Your contracts do not need a new `fluidVersion`: `0.18.1` reads `0.7.1` to `0.7.5`, and `0.7.6` as a preview.

## Where's the playground?

[`/playground/`](/forge_docs/playground/) — Monaco editor pre-loaded with four canonical contracts. No install needed.

---

::: warning This FAQ is a starter set
Each Q&A above is the canonical answer for now. As more questions come in via [GitHub Discussions](https://github.com/Agenticstiger/forge-cli/discussions), they'll be added here. Submitting a Q&A you'd like to see is a great first contribution.
:::
