---
title: Environments and overlays
description: How --env picks an overlay file, how the overlay merges over the base contract, what happens when none matches, and which artifacts record the environment.
---

# Environments and overlays

One base contract describes the data product. An **overlay** is a small file
beside it that patches the values one environment changes. `--env <name>` picks
the overlay, and the loader deep-merges it over the base before the command
does anything else.

The environment can be a stage (`dev`, `staging`, `prod`) or a cloud (`aws`,
`gcp`). Since CLI 0.17.0 the second use is how one contract deploys to AWS and
to GCP: each cloud's overlay patches only `exposes[].binding`. The how-to is
[One contract, two clouds](../recipes/one-contract-two-clouds.md).

## Example

```text
customer-events/
├── contract.fluid.yaml        # binds to local
└── overlays/
    ├── aws.yaml
    └── gcp.yaml
```

```yaml
# overlays/gcp.yaml
exposes:
  - binding:
      platform: gcp
      format: bigquery_table
      location:
        project: acme-analytics-prod
        dataset: customer_analytics
        table: customer_events
        region: europe-west3
```

```console
$ fluid validate contract.fluid.yaml --env gcp
overlay_applied
✅ Valid FLUID contract (schema v0.7.6)
Validation completed in 0.002s
```

The same contract without `--env` validates, plans and builds against the local
binding. With `--env gcp`, validate, plan, generate iac, apply and the other commands that take `--env` load the BigQuery binding.

## How `--env` finds the overlay

For `--env <env>`, the loader checks these paths next to the contract, in
order, and uses the first that exists:

1. `overlays/<env>.yaml`, `overlays/<env>.yml`, `overlays/<env>.json`
2. `<env>.yaml`, `<env>.yml`, `<env>.json`
3. `<contract-stem>.<env>.yaml`, `.yml`, `.json` (for example
   `contract.fluid.prod.yaml`)

Overlays are separate files. A contract cannot carry an inline `overlays:`
block: the root schema sets `additionalProperties: false`, so `fluid validate`
rejects one.

When an overlay is merged, the command prints `overlay_applied`. The line does
not name the file.

## How an overlay merges

- Maps merge key by key, recursively.
- A list of maps is patched by position: `exposes: [ {...} ]` in an overlay
  amends `exposes[0]` of the base and leaves the rest of that expose alone.
  Overlay entries past the end of the base list are appended.
- Base keys an overlay does not set survive inside a patched map. A base
  `binding.location.path` is still present in the resolved binding of an overlay
  that sets `project`, `dataset` and `table`: `fluid bundle --env gcp` shows
  `path: output/customer_events.parquet` next to them. Keep keys that only one
  platform uses out of the base binding when you can.
- Any other list (a list of strings, an empty list) and any value whose type
  differs from the base replaces the base value. `exposes: []` in an overlay
  therefore removes every expose.
- `$ref` pointers in the base contract are resolved **before** the overlay is
  merged, so an overlay can patch a field that comes from a fragment (see
  [Composing a contract with `$ref`](./contract-refs.md)). Positional patches
  line up with the order of the `$ref` entries in the root file.

::: warning Do not put `$ref` in an overlay
Overlay files are not ref-resolved. As of 0.18.1, an overlay that contains a
`$ref` is silently ignored by `fluid validate` and `fluid plan`: they print
`overlay_applied` and then check and plan the base contract. Measured with an
overlay that set an invalid `binding.format` next to a `$ref`: validate passed
and the plan kept the base format. Keep overlays as plain values.
:::

## When no overlay matches

| `--env` | No overlay found | Result |
|---|---|---|
| `dev` | `overlay_base_env` at INFO | The base contract. `dev` is the base by convention. |
| any other name | `overlay_not_found` at WARNING | The base contract, unchanged. The command continues (exit 0). |
| a name listed in the workspace's `expected-environments` | refused | Exit 1, nothing runs. |

The warning names the env, the platforms the base binds to, and the overlays
that do exist:

```console
$ fluid validate contract.fluid.yaml --env staging
overlay_not_found: --env 'staging' matched no overlay for /.../customer-events/contract.fluid.yaml, so the BASE contract is used unchanged (it binds to local, not to 'staging'). Overlays that exist: aws, gcp. Add an overlay for it under overlays/ or pass one of the existing environments.
✅ Valid FLUID contract (schema v0.7.6)
...
```

A warning does not stop a CI job. To make a missing overlay an error, declare
the product's environments in the workspace's
[`fluid.workspace.yaml`](./workspaces.md#expected-environments):

```yaml
# fluid.workspace.yaml (at the workspace root)
workspace:
  name: acme-analytics
expected-environments:
  customer-events: [aws, gcp]     # the product's directory name, or its contract id
```

With that file, `--env gcp` and no `overlays/gcp.yaml` is refused. `fluid plan`
and `fluid apply` report `ERR_OVERLAY_DECLARED_BUT_MISSING`; `fluid validate`
reports the same sentence under `ERR_CONTRACT_LOAD_FAILED`:

```console
$ fluid validate contract.fluid.yaml --env gcp
❌ Validation error: contract_load_failed
   error: --env 'gcp' has no overlay, but fluid.workspace.yaml expected-environments (customer-events) declares 'gcp' an environment of this product, so the base contract (bound to local) would be used as if it were 'gcp'. Add overlays/gcp.yaml, or remove 'gcp' from fluid.workspace.yaml expected-environments (customer-events)
   [ERR_CONTRACT_LOAD_FAILED]
   ...
```

Two names are never refused: `dev`, and an env equal to a platform the base
contract already binds to (`--env local` for a local base). As of 0.18.1 the
second still prints the `overlay_not_found` warning, worded "it binds to local,
not to 'local'".

## The `environments:` block applies nothing

The contract schema defines a top-level `environments:` map, and a contract
that carries one validates. forge-cli applies nothing from it: no command reads
a value out of it. It is mentioned only in the missing-overlay warning ("The
contract's environments block names 'staging', but forge-cli applies nothing
from that block; an overlay is what changes a binding"), and it does not make a
missing overlay an error. Use overlay files for values and
`expected-environments` for the list of environments.

## `{{ env.NAME }}` placeholders

A value that cannot live in YAML, such as a project id that differs per CI
account, can be written as `{{ env.NAME }}`. Shell-style `${NAME}` is not
substituted.

```yaml
# overlays/gcp.yaml
exposes:
  - binding:
      location:
        project: "{{ env.FLUID_GCP_PROJECT }}"
```

| Command | `{{ env.NAME }}` |
|---|---|
| `fluid validate` | Kept as written. |
| `fluid plan` | Kept as written in `plan.json`. |
| `fluid generate iac`, `fluid apply`, builds, `fluid publish`, `fluid verify` | Resolved from the process environment. |
| `fluid diff` | Resolved for the state check and, since 0.18.1, for the live check too. |

A variable that is not set is left as written. Measured on 0.18.1:
`fluid generate iac` with `FLUID_GCP_PROJECT` unset wrote
`"project": "{{ env.FLUID_GCP_PROJECT }}"` into `main.tf.json` and exited 0.
Under a strict `sovereignty` block, a region written as a placeholder fails
`fluid validate`, because validate checks the literal text: put the real region
in the overlay instead. See [Sovereignty](./sovereignty.md).

## What records the environment

The env a command ran with travels with what it produced, so a later stage
cannot quietly use another one.

| Artifact | Where the env is recorded | What a mismatch does |
|---|---|---|
| `plan.json` from `fluid plan --env <env>` | `contract_metadata.env` | `fluid apply plan.json` without `--env` uses it. When the apply runs a build, a different `--env` is refused with `ERR_PLAN_ENV_MISMATCH`. |
| A bundle from `fluid bundle --env <env> --format tgz` | `MANIFEST.json` `source.env` and `source.overlay` | A bundle is never re-overlaid. `--env` naming another env is refused with `ERR_BUNDLE_ENV_MISMATCH`. |
| Airflow DAGs from `fluid generate artifacts --env <env>` | directory `<product-id>__<env>/`, dag id `<product>__<env>__<build>` | The aws and gcp DAGs of one product no longer replace each other. |
| A Command Center publish | `metadata.fluid_env` | One catalogue product per contract id; the last publish wins (see below). |

```console
$ fluid bundle contract.fluid.yaml --env gcp --format tgz --out runtime/bundle-gcp.tgz
...
✅ Bundle written to /.../customer-events/runtime/bundle-gcp.tgz
   digest: sha256:21f021cf20cc8a1b784f6b716dcaf6065b8e468eb18a35d91d212e594dabfa84
   env: gcp (overlay: overlays/gcp.yaml)

$ fluid plan runtime/bundle-gcp.tgz --env aws
CLI command error
❌ bundle_env_mismatch  [ERR_BUNDLE_ENV_MISMATCH]
  ...
  bundle_env: gcp
  requested_env: aws
  hint: the bundle was built for env 'gcp' but this stage was asked for env 'aws'. A bundle is never re-overlaid; rebuild it with `fluid bundle <contract> --env aws --format tgz`, or pass the env it was built for.
```

As of 0.18.1, `fluid apply plan.json --env <other>` checks the plan's env only
in the build step. Measured: `fluid apply plan-aws.json --env gcp --dry-run`
ran the AWS OpenTofu engine without a mismatch error. Apply a plan with the env
it was made with, or without `--env`.

::: warning OpenTofu state is keyed by provider, not by environment
The default remote state key is `fluid/<id>/<provider>/terraform.tfstate`, and
the local workdir is `.fluid/iac/<provider>/<id>/`. Two environments of the
**same** cloud (a `gcp` and a `gcp-staging` overlay) applied with the same
bucket-only `FLUID_STATE_BACKEND`, or from the same working directory with
local state, resolve to the **same** state. Give each such environment its own
state bucket, or an explicit key in `--state-backend`. See
[OpenTofu state](./state.md).
:::

### Publishing one contract from two clouds

The Command Center keeps one catalogue product per contract id
(`metadata.fluid_contract_id`), whichever `--env` published it last. Publishing
the same contract from the aws and the gcp environment overwrites the product's
platform and location each time. Publish from one environment. Pipelines
generated with `fluid generate ci` leave the Jenkins publish stage off by
default (`--no-publish-stage-default`); keep it off for the second cloud.

## See also

- [Per-environment overlays](../recipes/per-environment-overlays.md) — the
  dev / staging / prod how-to.
- [One contract, two clouds](../recipes/one-contract-two-clouds.md) — the AWS
  and GCP how-to.
- [Workspaces](./workspaces.md) — `fluid.workspace.yaml` and
  `expected-environments`.
- [Governance parity](./governance-parity.md) — what the same policy fields do
  on each cloud.
- [`fluid bundle`](../cli/bundle.md), [`fluid plan`](../cli/plan.md),
  [`fluid apply`](../cli/apply.md).
