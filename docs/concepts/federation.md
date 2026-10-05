---
title: Consuming products from another mesh
description: Pin an upstream contract that lives in another team's repository or catalog, and what fluid apply does when it changes.
---

# Consuming products from another mesh

A `consumes[]` entry names an upstream data product. When that product lives
in the same workspace, the CLI can read its contract directly. When it lives
in another team's mesh (another git repository, another catalog), the
contract records **which** mesh it comes from and a **digest** of the upstream
contract as it was when you built against it. `fluid apply` then fetches the
upstream's current digest and warns when it no longer matches.

::: warning Preview schema
`upstreamWorkspace` and `upstreamDigest` exist only in the **0.7.6 preview**
schema. Set `fluidVersion: "0.7.6"` to use them. Under 0.7.5, the stable
schema, `fluid validate` rejects both keys.
:::

## Example

Two repositories. The billing team owns `bronze.crm_orders`:

```text
billing-mesh/                      # git repository, reachable by the consumer
└── bronze.crm_orders/
    └── contract.fluid.yaml
```

The analytics team consumes it:

```text
analytics/
├── contract.fluid.yaml
├── data/orders.csv
└── federation/
    └── upstreams.yaml
```

**1. Get the upstream's digest.** Run
[`fluid contract digest`](../cli/contract.md) on the upstream contract, as it is
committed in the upstream repository:

```console
$ fluid contract digest bronze.crm_orders/contract.fluid.yaml
sha256:92280394b3cdf5de3a4bf2725bd079f3fa8210ac15929cfb6ddff0d74e306ba1
```

**2. Declare where the upstream lives.** `federation/upstreams.yaml` lists the
other meshes this workspace reads from:

```yaml
# analytics/federation/upstreams.yaml
workspaces:
  - id: billing
    kind: git_registry
    endpoint: https://github.com/<your-org>/billing-mesh
    auth:
      mode: github_token
      secret_ref: GITHUB_TOKEN     # name of the environment variable holding the token
```

Before you put a real token in CI, read the warning under
[How each kind finds the digest](#how-each-kind-finds-the-digest) on how the
token is handled.

**3. Pin it in the consuming contract:**

```yaml
# analytics/contract.fluid.yaml
fluidVersion: "0.7.6"
kind: DataProduct
id: silver.revenue_daily
name: Revenue
domain: analytics
metadata:
  layer: Silver
  owner:
    team: analytics
    email: analytics@example.com
consumes:
  - productId: bronze.crm_orders
    exposeId: orders
    upstreamWorkspace: billing
    upstreamDigest: sha256:92280394b3cdf5de3a4bf2725bd079f3fa8210ac15929cfb6ddff0d74e306ba1
builds:
  - id: revenue
    pattern: embedded-logic
    engine: sql
    properties:
      sql: SELECT SUM(amount) AS revenue FROM read_csv('data/orders.csv')
exposes:
  - exposeId: revenue
    kind: table
    binding:
      platform: local
      format: csv
      location:
        path: out/revenue.csv
    contract:
      schema:
        - { name: revenue, type: DECIMAL }
```

```console
$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.6)
```

**4. Apply from the `analytics/` directory.** On the `local` provider the build needs DuckDB: install `data-product-forge[local]` ([DuckDB sandbox](../advanced/duckdb-sandbox.md)). While the upstream is unchanged,
the check passes silently. After the billing team commits a change to
`bronze.crm_orders`, the apply still runs, and says why it could not confirm
the pin:

```console
$ fluid apply contract.fluid.yaml --yes
...
apply_consumes_drift: 1 federated consumes[] entry could not be confirmed in sync (1 drift). Applying anyway. Details: {"counts_by_kind": {"drift": 1}, "drift_count": 1, ... "violation_kind": "drift"}]}
  consumes[0] billing/bronze.crm_orders [drift]: Federated upstream digest drift: pinned 'sha256:92280394b3cdf5de3a4bf2725bd079f3fa8210ac15929cfb6ddff0d74e306ba1', live 'sha256:a374f71e902a79914d4e9a2c02f0d43783e09fb224fa463cdb1f493849fde5bc'. Re-run ``fluid forge`` to refresh the pin or investigate why the upstream changed.
...
✅ Data product deployed successfully
```

To accept the new upstream, review its change, run `fluid contract digest` on
the new version and replace `upstreamDigest`. (The message's advice to re-run
`fluid forge` predates `fluid contract digest`, which is the command that
produces the value.)

The outputs above were captured with the upstream served from a local
`git daemon` (`endpoint: git://127.0.0.1:19418/billing-mesh`, `auth.mode:
none`) rather than GitHub.

## The pin

| Key | Value |
|---|---|
| `upstreamWorkspace` | The `id` of a workspace in `federation/upstreams.yaml` |
| `upstreamDigest` | `sha256:` followed by 64 lowercase hex characters |

Setting `upstreamWorkspace` requires `upstreamDigest`; a contract that names a
workspace without a digest fails validation, and `fluid apply` refuses it the
same way:

```console
$ fluid validate contract.fluid.yaml
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.6)
...
 1. consumes[0]: 'upstreamDigest' is a dependency of 'upstreamWorkspace'
```

A `consumes[]` entry without `upstreamWorkspace` is a local upstream and is not
part of this check.

### What the digest covers

`fluid contract digest` and the apply-time check hash the **parsed** contract,
not its bytes: key order, indentation, quoting, comments and line endings do
not change the digest, and any change to a value does. Neither resolves
`$ref`, so a contract composed from fragments is hashed with its `$ref` nodes
as written, and a change inside a fragment does not change the digest.

The digest covers the whole contract, so an upstream change that does not
affect you (a new description, a new expose) also shows up as drift.

## `federation/upstreams.yaml`

`fluid apply` reads `federation/upstreams.yaml` from the **current working
directory**, not from the contract's directory. Run the apply from the
directory that holds `federation/`. A missing file is an empty list of
workspaces.

| Key | Required | Values |
|---|---|---|
| `id` | yes | 1 to 64 of `A-Z a-z 0-9 _ . -`. Used in file names, so other characters are refused |
| `kind` | yes | `git_registry`, `catalog` or `http_registry` |
| `endpoint` | yes | A URL with an explicit scheme: `https`, `http`, `ssh`, `git`, `git+ssh` or `git+https`. A value starting with `-` is refused |
| `auth.mode` | no | `none` (default), `github_token`, `basic`, `oidc` (see below) |
| `auth.secret_ref` | no | The **name** of an environment variable that holds the secret, read at fetch time |

A row with a bad `id` or `endpoint` is skipped with a
`federation_workspace_rejected` warning; the other rows still load.

### How each kind finds the digest

| `kind` | Request | Authentication |
|---|---|---|
| `git_registry` | Clones `endpoint` (depth 1) into `~/.cache/fluid/federation-git/<id>`, or fetches and resets an existing clone, then reads the first of `<productId>/contract.fluid.yaml`, `<productId with dots as slashes>/contract.fluid.yaml`, `<productId>.fluid.yaml` and digests it | `github_token`, `http_token` or `basic`: the secret is put in an `https://` URL as `x-access-token:<secret>@` |
| `http_registry` | `GET <endpoint>/<productId>/<version>/digest`, expecting the digest as plain text | `basic`: `Authorization: Basic <secret>` (already base64-encoded); `oidc`, `bearer`, `http_token`, `token`: `Authorization: Bearer <secret>` |
| `catalog` | `GET <endpoint>/products/<productId>/versions/<version>`, expecting JSON `{"digest": "sha256:..."}` | `oidc`, `bearer`, `http_token`, `token`, `catalog_token`: `Authorization: Bearer <secret>` |

As of 0.18.1:

- `<version>` is always `1`: the check reads a `version` key that `consumes[]`
  entries do not have.
- `git_registry` shells out to the `git` binary for every fetch, so `git` must
  be on the `PATH` of the machine that runs `fluid apply`.
- A manifest row may carry `product_path_template`; it is accepted but not
  used. The git backend tries the three paths above.

Each git operation is bounded by `FLUID_FEDERATION_TIMEOUT_SECONDS` (default
30; a non-numeric, zero, negative or infinite value falls back to 30). HTTP
fetches time out after 15 seconds and do not follow redirects to a private
address. An endpoint whose host resolves to a private, loopback, link-local or
cloud-metadata address is refused for `http_registry` and `catalog` unless the
host is listed in `FLUID_FEDERATION_HOST_ALLOWLIST` (comma-separated host
suffixes). See [Network safety](../advanced/network-safety.md).

::: warning Handling the token
- **Git.** For `github_token`, `http_token` and `basic`, forge-cli writes the
  token into the clone URL (`https://x-access-token:<secret>@host/...`) and
  runs `git clone` with that URL as an argument. It is visible in the process
  list for the duration of the clone, and git keeps it in the cache clone's
  remote URL, in `.git/config` under `~/.cache/fluid/federation-git/<id>/`. The
  clone stays after the job ends.
- **HTTP and catalog.** The secret goes out in an `Authorization` header to
  whatever `endpoint` names. Use `https://` endpoints only: `http://` is
  accepted, and the header then travels unencrypted.
- **`secret_ref` is an environment variable's name.** Any variable in the job's
  environment can be named, and its value is sent to the `endpoint` on the same
  row. Treat an edit to `federation/upstreams.yaml` like a change to a
  credential: put the file under CODEOWNERS and review every `endpoint` and
  `secret_ref` change.

Give the token read-only access to the one repository it must clone. On a shared
or long-lived agent, delete `~/.cache/fluid/federation-git/` after the job.
Better, for a git upstream, use an SSH deploy key
(`endpoint: ssh://git@github.com/<your-org>/billing-mesh.git`) or a git
credential helper with `auth.mode: none`: forge-cli then puts no token in the
URL.
:::

## What `fluid apply` does

The check runs during `fluid apply`, after the contract is validated and
before the apply changes anything. `fluid plan` and `fluid validate` do not
fetch upstream digests.

::: warning As of 0.18.1, only on the native engine
The check sits on the native apply path, which the `local` provider uses.
`aws`, `gcp`, `snowflake` and `confluent` apply through the OpenTofu engine,
which returns before the check is reached: for a contract bound to one of
those clouds, `fluid apply` fetches no upstream digest and logs no
`apply_consumes_drift` line, whatever the pins say. Until that changes, check
pins yourself before a cloud apply, for example by comparing
`fluid contract digest` on the upstream's current contract with the pinned
value.
:::

Each federated `consumes[]` entry ends in one of these:

| `violation_kind` | Meaning |
|---|---|
| (none) | The upstream digest matches the pin |
| `drift` | The upstream digest differs from the pin |
| `unreachable` | The fetch failed (network, authentication, missing file, failed clone). The pin was **not** checked |
| `unknown-workspace` | `upstreamWorkspace` is not an `id` in `federation/upstreams.yaml` |
| `not-wired` | The workspace's `kind` is not one of the three above |
| `unpinned` | `upstreamDigest` is missing. Schema validation refuses this first, so a valid contract does not reach it |

**The check warns; it does not stop the apply.** Every finding is logged at
`WARNING` as one `apply_consumes_drift` line with a JSON payload
(`kind: upstream-mismatch`, `violations[]`, `counts_by_kind`), followed by one
line per entry, and the apply continues with its normal exit code. A gate that
another team's registry outage could fail would end up permanently bypassed,
which is why it reports instead of blocking. In CI, match `apply_consumes_drift`
in the apply log to fail a pipeline on drift.

An unreachable upstream does not hide drift in another one: the entries are
checked one by one and each reports its own result.

If the check itself fails, `fluid apply` logs `federation_gate_error` and the
pins were not verified for that apply. In CI, match both `federation_gate_error`
and `apply_consumes_drift`.

```console
$ fluid apply contract.fluid.yaml --yes        # upstreamWorkspace: payments, not in the manifest
...
  consumes[0] payments/bronze.crm_orders [unknown-workspace]: Federated workspace 'payments' not declared in federation/upstreams.yaml. Add it to the manifest before referencing in consumes[].

$ fluid apply contract.fluid.yaml --yes        # registry down
...
federation_git_clone_failed: workspace=billing err=CalledProcessError — git clone failed (authentication or remote error); refusing to echo the command line
federation_fetch_failed: workspace=billing product=bronze.crm_orders err=FederationFetchError
  consumes[0] billing/bronze.crm_orders [unreachable]: Could not reach federated upstream 'billing' to verify the pin (FederationFetchError). The pinned digest was NOT checked -- this is not a statement that the upstream is unchanged.
```

`--no-verify-federation` skips the check and logs that it did:

```console
$ fluid apply contract.fluid.yaml --yes --no-verify-federation
...
--no-verify-federation: federation digest gate was SKIPPED. Federated consumes[] entries with drifted upstreams will apply against stale data. Make sure this is recorded in the change log.
```

### The digest cache

Each fetched digest is stored in
`.fluid/federation/<workspace id>.digest-cache.json` under the working
directory:

```json
{
  "__updated_at": "2026-10-05T00:18:07Z",
  "bronze.crm_orders@1": "sha256:92280394b3cdf5de3a4bf2725bd079f3fa8210ac15929cfb6ddff0d74e306ba1"
}
```

As of 0.18.1 a cached entry has no expiry, and a later apply uses it **instead
of fetching**. Once a digest is cached, a change the upstream makes afterwards
is not seen by applies on that machine until the cache file is deleted. In the
example above, the apply right after the upstream's change passed silently
because the first apply had cached the old digest; the drift warning appeared
only after:

```bash
rm .fluid/federation/billing.digest-cache.json
```

On a CI runner that starts from a clean checkout each time, the cache does not
survive between builds and every apply fetches.

### Upgrading pins made before 0.15.0

0.15.0 changed how a `git_registry` digest is computed (from the raw file to
the parsed contract), so a pin taken on 0.14.x reads as `drift`. Re-pin with
`fluid contract digest` and delete the cache files, which still hold the old
value. `catalog` and `http_registry` read the digest from the remote and are
not affected.

## Related

- [Consume one contract from another](../recipes/consumes-contract-to-contract.md):
  `consumes[]` within one workspace.
- [`fluid apply`](../cli/apply.md#safety-gates): the other apply gates and their
  waivers.
- [`fluid contract`](../cli/contract.md): the `contract` subcommands.
- [Network safety](../advanced/network-safety.md): the host allowlists.
