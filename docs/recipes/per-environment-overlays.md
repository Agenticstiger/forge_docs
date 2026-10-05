---
title: Generate per-environment overlays
description: Run one contract against dev / staging / prod by switching --env, no copy-paste.
---

# Per-environment overlays — one contract, three environments

**Time:** 3 min · **Skill:** comfortable editing a YAML file

A contract is the same in `dev`, `staging`, and `prod` — only a handful of values (project, dataset suffix, freshness target) actually differ. The right answer is **one base contract + per-environment overlays**, not three near-identical copies.

The same mechanism puts one contract on two clouds; that how-to is
[One contract, two clouds](./one-contract-two-clouds.md). The full rules are in
[Environments and overlays](../concepts/environments-and-overlays.md).

## The pattern

The base `contract.fluid.yaml` holds what every environment shares. Each environment gets its **own overlay file** beside it. Switch environments with `fluid <command> --env <name>`; the loader deep-merges the matching overlay file over the base before the command runs.

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

- **Deep-merges** the overlay over the base — maps merge key-by-key; a list of maps is patched **positionally**, so `exposes: [ { ... } ]` in an overlay amends `exposes[0]` of the base rather than replacing the whole list, and overlay entries past the end of the base list are appended. Scalar lists, empty lists and mismatched types are replaced wholesale.
- **Resolves `$ref` first.** Fragments the base pulls in with `$ref` are resolved before the overlay is merged, so an overlay can patch a field that lives in a fragment. Do not put a `$ref` in an overlay itself: as of 0.18.1 such an overlay is silently ignored by `fluid validate` and `fluid plan`.
- **Announces the merge** — an `overlay_applied` line is printed whenever an overlay is merged. The line does **not** name which overlay file was used.
- **Warns when no overlay matches** `--env <name>` and runs the base contract unchanged. The warning names the overlays that do exist:

  ```console
  $ fluid validate contract.fluid.yaml --env prdo
  overlay_not_found: --env 'prdo' matched no overlay for /.../orders-enriched/contract.fluid.yaml, so the BASE contract is used unchanged (it binds to gcp, not to 'prdo'). Overlays that exist: dev, prod, staging. Add an overlay for it under overlays/ or pass one of the existing environments.
  ✅ Valid FLUID contract (schema v0.7.5)
  ...
  ```

  `--env dev` with no dev overlay is the base by convention and logs `overlay_base_env` at INFO instead. Either way the command exits 0.

## Declare your environments

A warning does not stop a pipeline. List the product's environments in the
workspace's `fluid.workspace.yaml`, and a declared environment with no overlay
becomes an error:

```yaml
# fluid.workspace.yaml, at the workspace root above orders-enriched/
workspace:
  name: acme
expected-environments:
  orders-enriched: [dev, staging, prod, qa]
```

```console
$ fluid plan contract.fluid.yaml --env qa
CLI command error
❌ overlay_declared_but_missing  [ERR_OVERLAY_DECLARED_BUT_MISSING]
...
```

`fluid validate` reports the same refusal as `ERR_CONTRACT_LOAD_FAILED`. This
catches a declared environment whose overlay is missing. It does not catch a
misspelt env: `--env prdo`, which is not in the list, still only warns. Take
env names in CI from one list, as in the matrix below. See
[Workspaces](../concepts/workspaces.md#expected-environments).

The contract schema also has a top-level `environments:` block. It validates,
but forge-cli applies nothing from it and it does not make a missing overlay an
error. Put per-environment values in overlay files.

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

```console
$ GCP_PROD_PROJECT=my-project-prod fluid generate iac contract.fluid.yaml --env prod --out iac-prod
...
Wrote OpenTofu module: iac-prod/main.tf.json  (provider: gcp, 2 resources)
```

`iac-prod/main.tf.json` names `"project": "my-project-prod"`. Substitution runs
*after* the overlay merge, so per-env values can reference per-env variables
without leaking into the base. It runs where values reach a platform:
`fluid generate iac`, `fluid apply`, builds, `fluid publish`, `fluid verify`
and `fluid diff`. `fluid validate` checks the placeholder as written, and
`fluid plan` writes it to `plan.json` unresolved. An unset variable is left as
the literal `{{ env.GCP_PROD_PROJECT }}`, without an error.

A value shared by several products, such as a data directory, can come from the same mechanism: `path: "{{ env.DATA_DIR }}/orders.csv"` resolves the same way in `fluid apply`, `fluid verify` and `fluid diff`. See [where paths resolve](../providers/local.md#where-paths-resolve).

Under a strict `sovereignty` block, a region written as a placeholder fails
`fluid validate` with `Region '{{ env.GCP_REGION }}' not in allowed regions
list`, because validate checks the literal text. Write the real region in the overlay.

## Logical principals

When one base contract deploys to more than one cloud, keep `accessPolicy` and `columnRestrictions` in the base, written with the principals the business knows, and map each to a real identity in the overlay's binding:

```yaml
# overlays/gcp.yaml
exposes:
  - binding:
      platform: gcp
      principals:
        group:analysts@acme.example: group:analysts@<your-domain>
```

```yaml
# overlays/aws.yaml
exposes:
  - binding:
      platform: aws
      principals:
        group:analysts@acme.example: arn:aws:iam::123456789012:role/analyst
```

Replace `<your-domain>` with the domain of your own groups before `--env gcp` validates; left as written, validate refuses it as not a GCP IAM member. A value is one identity, a list, or `[]` for "no identity on this cloud". `binding.principals` is in schema 0.7.6, so the contract declares `fluidVersion: "0.7.6"`; see [Mapping principals per cloud](../reference/preview-fields.md#mapping-principals-per-cloud) and [Governance parity](../concepts/governance-parity.md#logical-principals-and-binding-principals) for the refusals.

## Environments on one cloud share a state key

The default OpenTofu state key is per contract and **provider**
(`fluid/<id>/gcp/...`), not per environment. If `dev`, `staging` and `prod`
all apply to GCP with the same bucket-only `FLUID_STATE_BACKEND`, or from the
same working directory with local state, they share one state, and each
environment's plan reads the others' resources as orphans to destroy. Give each
environment its own state bucket:

```bash
FLUID_STATE_BACKEND=gcs://<your-state-bucket>-prod fluid apply contract.fluid.yaml --env prod --yes
```

Bucket names are global: use a bucket you own. Or give each environment an
explicit key in `--state-backend`. See [OpenTofu state](../concepts/state.md).

## Test all overlays in CI

A common CI shape — validate each overlay in parallel. Keep this matrix as the
single list of legal env names, and list the same names under
`expected-environments`:

```yaml
# .github/workflows/contract-ci.yml (fragment)
jobs:
  validate:
    strategy:
      matrix:
        env: [dev, staging, prod]
    steps:
      - run: pip install "data-product-forge==0.18.1"
      - run: fluid validate contract.fluid.yaml --env ${{ matrix.env }}
      - run: fluid plan     contract.fluid.yaml --env ${{ matrix.env }}
```

Pin the version: an unpinned `pip install` in a pipeline takes whatever is
newest on the day. Add the extras your clouds need, for example
`"data-product-forge[gcp]==0.18.1"`.

## See also

- [Environments and overlays](../concepts/environments-and-overlays.md) — the
  full merge, warning and refusal rules, and what records the env.
- [`fluid plan`](../cli/plan.md) — every `--env`-aware command takes the same flag
- [`fluid generate iac` `--env`](../cli/generate-iac.md#syntax) — overlays propagate into the IaC emit
- [One contract, two clouds](./one-contract-two-clouds.md) — overlays per cloud
- [Switch clouds by editing only `binding`](./switch-clouds.md) — move a
  contract to another cloud
