---
title: Recipes
description: Short how-to guides, one task each, for a reader who already has a working contract.
---

# Recipes

A recipe solves one task on a contract you already have: add a rule, tag a column, run it in another environment or on another cloud, change it once it is live. Each one starts from the problem, gives the change, and shows what the CLI prints.

Recipes assume you have run [Getting Started](../getting-started/README.md). To learn by building from scratch, use the [tutorials](../walkthrough/README.md); to understand why something works, read the [concepts](../concepts/README.md).

## Recipes

Listed in the order a product meets them. Times are each page's own estimate.

| Recipe | Time | What it does |
|--------|------|--------------|
| [Per-environment overlays](./per-environment-overlays.md) | 3 min | Run one contract in `dev`, `staging` and `prod` by switching `--env`, with no copies. |
| [Switch clouds by editing only `binding`](./switch-clouds.md) | 5 min | Move a local contract to BigQuery, S3 + Glue or Snowflake by changing `platform`, `format` and `location` in its binding. |
| [One contract, two clouds](./one-contract-two-clouds.md) | 15 min | Deploy one contract to AWS and GCP with `--env` overlays, governed the same on both. |
| [Add a quality rule](./add-a-quality-rule.md) | 5 min | Declare `dq.rules` and gate CI on `fluid test`, which exits 1 when a rule at `error` or `critical` fails. `fluid apply` does not evaluate the rules. |
| [Tag PII in your schema](./tag-pii.md) | 10 min | Mask PII columns at landing with `policy.privacy.masking`, and check with `fluid verify` that they landed masked. |
| [Consume one contract from another](./consumes-contract-to-contract.md) | 10 min | Chain a Bronze product into a Silver one with `consumes[]` and an embedded-SQL build. |
| [Change a live data product](./evolve-a-live-product.md) | 15 min | Version a change, check it against consumers, gate on drift, apply, verify, and know what rollback can and cannot undo. |

## Recipes and CLI by task

[CLI by task](../cli/tasks/README.md) is the other set of how-to guides. Its pages follow one scenario through several commands, for example a failed run from `fluid runs status` to the fix:

| Task | Page |
| --- | --- |
| Deploy to a new cloud | [Switch clouds by editing only `binding`](../cli/tasks/switch-clouds.md) |
| Add quality rules | [Add quality rules](../cli/tasks/add-quality-rules.md) |
| Debug a failed pipeline run | [Debug a failed run](../cli/tasks/debug-failed-run.md) |
| Govern AI and agent access | [Add agent governance](../cli/tasks/agent-governance.md) |

Two topics have a page in both sets: switching clouds and quality rules. The recipe is the short version; the task page walks the same change with more context.

For one command's flags and output, use the [CLI reference](../cli/README.md).

## Wanted

These recipes do not exist yet. Pick one, write it up, open a pull request. Each should be runnable as written on the current CLI.

- Ship to Dagster instead of Airflow
- Audit a contract for compliance
- Snapshot a contract before a risky change (`fluid bundle`)
- Hook in custom dbt macros via `hybrid-reference`
- Add a Slack alert when a data-quality rule fails

Tracked in [docs-content](https://github.com/Agenticstiger/forge_docs/issues?q=is%3Aopen+label%3Adocs-content).
