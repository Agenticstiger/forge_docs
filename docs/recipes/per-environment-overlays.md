---
title: Generate per-environment overlays
description: Run one contract against dev / staging / prod by switching --env, no copy-paste.
---

# Per-environment overlays — one contract, three environments

**Time:** 3 min · **Skill:** comfortable editing a YAML file

A contract is the same in `dev`, `staging`, and `prod` — only a handful of values (project, dataset suffix, retention, alert recipient) actually differ. The right answer is **one base contract + per-environment overlays**, not three near-identical copies.

## The pattern

The base `contract.fluid.yaml` holds what every environment shares. Each environment gets its **own overlay file** beside it. Switch environments with `fluid <command> --env <name>`; the loader (`fluid_build/loader.py::load_with_overlay`, reached through the CLI entry point `fluid_build.cli._common.load_contract_with_overlay`) deep-merges the matching overlay file over the base before plan/apply runs.

::: warning Overlays are separate files, never an inline block
There is no `overlays:` key inside a contract. The root schema declares `additionalProperties: false` in every bundled version (`0.7.1` through `0.7.6`), so a contract carrying an inline `overlays:` block is rejected by `fluid validate`. The loader only ever looks for sidecar files.
:::

For `--env dev`, the loader checks these paths in order and takes the first that exists:

1. `<dir>/overlays/dev.yaml`, `.yml`, `.json`
2. `<dir>/dev.yaml`, `.yml`, `.json`
3. `<dir>/contract.fluid.dev.yaml`, `.yml`, `.json`

So the conventional layout is:

```
orders-enriched/
├── contract.fluid.yaml
└── overlays/
    ├── dev.yaml
    ├── staging.yaml
    └── prod.yaml
```

The base contract is a normal, complete, valid contract:

```yaml
# contract.fluid.yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: silver.orders_enriched
name: Orders Enriched
metadata:
  layer: Silver
  productType: ADP
  owner:
    team: data-platform
    email: data-platform@example.com

exposes:
  - exposeId: orders_enriched
    kind: table
    contract:
      schema:
        - name: order_id
          type: STRING
          required: true
    qos:
      freshnessSLO: PT60M          # base value; overridden per environment
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-dev
        dataset: orders
        table: orders_enriched
```

Each overlay carries only the keys it changes, in the same shape as the base:

```yaml
# overlays/dev.yaml
exposes:
  - binding:
      location:
        project: my-project-dev
        dataset: orders_dev
    qos:
      freshnessSLO: PT240M
```

```yaml
# overlays/staging.yaml
exposes:
  - binding:
      location:
        project: my-project-staging
        dataset: orders_staging
```

```yaml
# overlays/prod.yaml
exposes:
  - binding:
      location:
        project: my-project-prod
        dataset: orders
    qos:
      freshnessSLO: PT30M
```

Run the same contract three ways:

```bash
fluid plan  contract.fluid.yaml --env dev
fluid plan  contract.fluid.yaml --env staging
fluid plan  contract.fluid.yaml --env prod
fluid apply contract.fluid.yaml --env prod --yes
```

## What the overlay loader does

- **Deep-merges** the overlay over the base — maps merge key-by-key; a list of maps is patched **positionally**, so `exposes: [ { ... } ]` in an overlay amends `exposes[0]` of the base rather than replacing the whole list, and overlay entries past the end of the base list are appended. Scalar lists and mismatched types are replaced wholesale.
- **Announces the merge** — an `overlay_applied` line goes to stdout whenever an overlay is merged, so plan and apply runs show that one was active. It is printed by default; the line does **not** name which overlay file was used.
- **Falls back to the base contract** when no overlay file matches `--env <name>` — the miss is logged at DEBUG only (`overlay_not_found`), so a typo'd env name succeeds silently against base values. Pin env names in CI rather than relying on the CLI to catch a typo.

## Env-var templates inside an overlay

Combine overlays with env vars when a value can't live in YAML. The placeholder syntax is `{{ env.VAR }}`; shell-style `${VAR}` is **not** substituted and is carried through as a literal string.

```yaml
# overlays/prod.yaml
exposes:
  - binding:
      location:
        project: "{{ env.GCP_PROD_PROJECT }}"
        dataset: orders
    qos:
      freshnessSLO: PT30M
```

```bash
GCP_PROD_PROJECT=my-project-prod fluid validate contract.fluid.yaml --env prod
```

Substitution runs *after* the overlay merge, so per-env fragments can reference per-env variables without leaking into the base. It runs on the commands that consume contract values — contract validation, builds, and publish — while `fluid plan` writes the placeholder through to `plan.json` unresolved.

## Test all overlays in CI

A common CI shape — validate each overlay in parallel. Note that the CLI does not catch a misspelt `--env`, so keep this matrix as the single list of legal env names:

```yaml
# .github/workflows/contract-ci.yml (fragment)
jobs:
  validate:
    strategy:
      matrix:
        env: [dev, staging, prod]
    steps:
      - run: pip install --pre data-product-forge
      - run: fluid validate contract.fluid.yaml --env ${{ matrix.env }}
      - run: fluid plan     contract.fluid.yaml --env ${{ matrix.env }}
```

## See also

- [`fluid plan`](../cli/plan.md) — every `--env`-aware command takes the same flag
- [`fluid generate iac` `--env`](../cli/generate-iac.md#syntax) — overlays propagate into the IaC emit
- [Switch clouds with one line](./switch-clouds.md) — the sister recipe for swapping `binding.platform`
