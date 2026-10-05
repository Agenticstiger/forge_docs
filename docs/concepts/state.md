---
title: OpenTofu state
description: Where fluid apply keeps OpenTofu state for a cloud contract, how a remote key is chosen, the per-provider key and its one-time migration, and which commands read the state.
---

# OpenTofu state

`fluid apply` deploys a cloud binding (AWS, GCP, Snowflake, Confluent) by emitting an
OpenTofu module and running `tofu`. OpenTofu records what it created in a
**state**. The next apply, `fluid diff` and `fluid verify --state-drift` read
that state, so where it lives decides whether they see the real deployment.

Every apply, `--dry-run` included, prints where its state is. The bucket name
`acme-tfstate` in the transcripts on this page is illustrative: bucket names are
global, so use a bucket you own.

```console
$ FLUID_STATE_BACKEND=s3://acme-tfstate fluid apply contract.fluid.yaml --env aws --dry-run
...
OpenTofu engine — provider: aws
  module:      .fluid/iac/aws/analytics_customer_events_v1/main.tf.json
  state:       remote: s3://acme-tfstate/fluid/analytics.customer_events_v1/aws/terraform.tfstate (from FLUID_STATE_BACKEND)
...
```

## Local state

With no backend configured, state is a file in the contract's OpenTofu workdir:

```text
<workspace-dir>/.fluid/iac/<provider>/<contract id, with . and - as _>/
├── main.tf.json          # the module apply emitted
└── terraform.tfstate     # local state
```

`<workspace-dir>` is `--workspace-dir`, which defaults to the directory you run
`fluid apply` in, not the contract's directory. The directory is per
provider and per folded id. Ids that differ only in `.`, `-` or `_` fold to the
same directory and so share one local state; give such products different
`--workspace-dir` values.

Local state suits a laptop. A CI job usually starts from a clean checkout, and a
wiped local state makes the next apply plan every resource as new. Use a remote
backend there.

## Remote state

A backend spec is `s3://<bucket>[/<key>]` or `gcs://<bucket>[/<prefix>]`. The
backend block carries no credentials: `tofu` reads them from the environment.

| Where the spec comes from | Example | Resulting state |
|---|---|---|
| `--state-backend` with a key | `--state-backend s3://<your-state-bucket>/team/orders.tfstate` | Exactly that key. |
| `FLUID_STATE_BACKEND`, bucket only | `FLUID_STATE_BACKEND=s3://<your-state-bucket>` | `fluid/<id>/<provider>/terraform.tfstate` (GCS: prefix `fluid/<id>/<provider>`). |
| `--state-backend`, bucket only, contract with a `packaging` block | `--state-backend s3://<your-state-bucket>` | `fluid/<id>/<provider>/terraform.tfstate`, with `.` and `-` in the id folded to `_`. |
| `--state-backend`, bucket only, contract without `packaging` | `--state-backend s3://<your-state-bucket>` | S3: the shared key `fluid/terraform.tfstate`, for every such contract. GCS: no prefix, so the bucket's root. |
| `--state-backend ""` | | Local state, even when `FLUID_STATE_BACKEND` is set. |
| neither | | Local state. |

The flag wins over the variable. `FLUID_STATE_BACKEND` is meant to be set once
for a CI job that applies many products: a bucket-only value gives each contract
its own key, keyed by the id exactly as written, whether or not it has a
`packaging` block. The bucket-only flag keeps the older shared key for a
contract without `packaging`. Measured on 0.18.1 with the same contract:

```console
$ FLUID_STATE_BACKEND=s3://acme-tfstate fluid apply contract.fluid.yaml --env aws --dry-run
...
  state:       remote: s3://acme-tfstate/fluid/analytics.customer_events_v1/aws/terraform.tfstate (from FLUID_STATE_BACKEND)

$ fluid apply contract.fluid.yaml --env aws --dry-run --state-backend s3://acme-tfstate
...
  state:       remote: s3://acme-tfstate/fluid/terraform.tfstate (from --state-backend)

$ FLUID_STATE_BACKEND=s3://acme-tfstate fluid apply contract.fluid.yaml --env aws --dry-run --state-backend ""
...
  state:       local (from --state-backend)
```

A bucket name may hold only `[A-Za-z0-9._-]`; anything else, and a key with a
control character, is refused (`ERR_APPLY_STATE_BACKEND_INVALID`) without
echoing the spec. A `<your-state-bucket>` placeholder left in a command is
refused the same way.

::: warning Protect the state bucket
State can hold sensitive values: OpenTofu records the attributes of the
resources it manages. Keep the bucket private, with versioning on, readable and
writable only by the identity that runs the apply, and with default encryption
on. Bucket names are global: create the bucket yourself, and never point
`--state-backend` at a name you did not create.

The backend block `fluid apply` emits for S3 sets only `bucket` and `key`. It
sets no `dynamodb_table` and no `use_lockfile`, so S3 state is not locked: run
the applies of one state key one at a time. OpenTofu's own `gcs` backend locks
state itself.
:::

## The provider is part of the key

One contract applied to AWS and to GCP through `--env` overlays is one contract
id. Since CLI 0.17.0 every per-contract default key carries the provider, so the
two clouds keep two states:

```text
s3://<your-state-bucket>/fluid/analytics.customer_events_v1/aws/terraform.tfstate
gcs://<your-state-bucket>/fluid/analytics.customer_events_v1/gcp
```

The environment is **not** part of the key. Two environments of one cloud (a
`gcp` and a `gcp-staging` overlay) resolve to the same state when they share a
bucket-only `FLUID_STATE_BACKEND`, or the same working directory with local
state. Give each such environment its own bucket, or name an explicit key.

### The one-time move from the old key

Before 0.17.0 the per-contract default was `fluid/<id>/terraform.tfstate`. On
the first apply after upgrading, when the new key holds no state and the old
key does, `fluid apply` looks at whose resources the old state holds:

| The old state holds | What apply does |
|---|---|
| only this provider's resources | Copies it to the new key with OpenTofu's own `tofu init -force-copy`, reads the copy back to check it holds the same resources, and prints `state move:  moved <n> resource(s) from <old> to <new> with `tofu init -migrate-state`; the old object is left in place`. |
| only another provider's resources | Leaves it, and prints `state move:  <old> holds the <provider> provider's state (<source>), not this provider's; left in place`. |
| resources of two clouds, or none it can attribute | Refuses with `state_migration_ambiguous`, naming both keys. Move it yourself, or name the key in `--state-backend` / `FLUID_STATE_BACKEND`. |

The old object is never deleted. Only a default key moves: an explicit key in
the spec, and the shared `fluid/terraform.tfstate`, stay where they are.

On 4 Oct 2026 the first `--env gcp` apply of a product whose AWS state sat at
the old key reported that state as the aws provider's and left it in place; the
GCP state went to `fluid/<id>/gcp/terraform.tfstate`.

Other refusals of the move: `state_migration_raced` (another job wrote the new
key in the meantime; nothing was moved), `state_migration_failed`,
`state_migration_unverified` (the copy does not hold the same resources; the old
object is untouched) and `state_migration_probe_failed` (the old state could not
be read).

`fluid apply --dry-run` never moves state: while the move is pending it plans
against the old key.

### A shared key that already holds another cloud

A remote key that does not name the provider, such as the shared
`fluid/terraform.tfstate` or an explicit key, can still end up used by two
clouds. Before planning, apply reads such a key once; if it holds another
cloud's resources, the apply is refused with
`ERR_STATE_SHARED_WITH_ANOTHER_PROVIDER`:

```text
s3://<bucket>/<key> holds resources of the aws provider, and this is the gcp apply:
its plan would read them as orphans to destroy. Give each provider its own state,
with a key that names the provider in --state-backend (for example
fluid/<id>/<provider>/terraform.tfstate) or a bucket-only FLUID_STATE_BACKEND,
which keys state by contract and provider
```

## A region change under existing state

When the state holds the contract's resources in one region and the bindings
now name another, apply is refused with `opentofu_region_moved`, naming the
regions the state holds. Applying would create the resources again in the new
region and leave the originals unmanaged, and no destroy would show in the plan.
`fluid diff` runs the same check.

## Which commands read the state

| Command | Reads |
|---|---|
| `fluid apply` | The state it resolves as above. It writes it. |
| `fluid diff` (drift mode) | The live targets, and the apply's state through the same resolution: `--state-backend` (default `FLUID_STATE_BACKEND`) and `--workspace-dir`. `--no-state-drift` skips the state. |
| `fluid verify --state-drift` | The apply's state, refreshed, through the same `--state-backend` and `--workspace-dir`. Skipped with a note when no state is reachable. |

`fluid diff` and `fluid verify --state-drift` never move state. While the
one-time move is still pending (no upgraded apply has run yet), they read the
old key, so a drift gate that runs before the first upgraded apply sees the real
deployment. Pass them the same `--state-backend`, `--workspace-dir` and `--env`
that the apply used.

```bash
fluid diff contract.fluid.yaml --env gcp --exit-on-drift
fluid verify contract.fluid.yaml --env gcp --state-drift --strict
```

## See also

- [`fluid apply`](../cli/apply.md), [`fluid diff`](../cli/diff.md),
  [`fluid verify`](../cli/verify.md)
- [Environments and overlays](./environments-and-overlays.md)
- [One contract, two clouds](../recipes/one-contract-two-clouds.md)
