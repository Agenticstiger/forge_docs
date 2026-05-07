---
title: FAQ
description: Common questions about Fluid Forge — comparisons, errors, upgrades, security.
---

# ❓ FAQ

A growing collection of common questions. Each answer either resolves the question on this page or points at the canonical doc.

## How is Fluid Forge different from dbt / Terraform / Airflow / OPA?

Short answer: it unifies the four contracts (schema + infra + orchestration + policy) into one YAML so they can't drift. Long answer: see [Concepts → vs alternatives](/forge_docs/concepts/vs-alternatives.md) — there's a side-by-side ownership table.

## Why do I see `pip install fluid-forge` in some old docs and `pip install data-product-forge` in new docs?

The PyPI package was renamed. Canonical name as of v0.8.0: **`data-product-forge`** (the older `fluid-forge` listing is frozen at 0.7.9 and won't receive new releases). [Getting Started](/forge_docs/getting-started/) has the up-to-date install instructions.

## What's the difference between `fluidVersion` and the CLI version?

`fluidVersion` is the **contract schema version** declared inside each YAML file (current: `"0.7.2"`). The CLI version is the version of the `data-product-forge` package itself (current: `0.8.0`). The CLI accepts contracts with `fluidVersion` `0.4.0`, `0.5.7`, `0.7.1`, or `0.7.2`. Run `fluid version` for the authoritative compatibility list.

## I get `No module named 'duckdb'` running the local quickstart.

You installed bare `data-product-forge` without the `[local]` extra. Fix:

```bash
pip install "data-product-forge[local]"
```

Or for an isolated CLI install: `pipx install "data-product-forge[local]"`.

## Where do I report a bug or ask a question?

- **Bug?** [open an issue](https://github.com/Agentics-Rising/forge-cli/issues/new) with `fluid version` + `fluid doctor` output.
- **Question?** [GitHub Discussions](https://github.com/Agentics-Rising/forge-cli/discussions).
- **Security report?** See [SECURITY.md](https://github.com/Agentics-Rising/forge-cli/blob/main/SECURITY.md).

## How do I upgrade?

```bash
pip install --upgrade data-product-forge
fluid doctor                    # verifies the new install
```

Schema migrations are backward-compatible by default — the latest CLI reads older `fluidVersion` contracts.

## Where's the playground?

[`/playground/`](/forge_docs/playground/) — Monaco editor pre-loaded with four canonical contracts. No install needed.

---

::: warning This FAQ is a starter set
Each Q&A above is the canonical answer for now. As more questions come in via [GitHub Discussions](https://github.com/Agentics-Rising/forge-cli/discussions), they'll be added here. Submitting a Q&A you'd like to see is a great first contribution.
:::
