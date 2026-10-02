---
title: Composing a contract with $ref
description: Split a contract into fragments with $ref, and the ref root that confines where a fragment may come from.
---

# Composing a contract with `$ref`

A contract can pull any object from another YAML or JSON file with `$ref`.
`fluid validate`, `fluid plan`, `fluid apply` and `fluid bundle` resolve every
ref before they do anything else, so the rest of the pipeline sees one
document.

::: warning Changed in CLI 0.18.0
A `$ref` may only name a file inside the contract's own directory tree (the
**ref root**). URL refs (`file://` included), absolute paths, and `..` or
symlink escapes are refused. Monorepos that share fragments across products
widen the root with `FLUID_REF_ROOT`. See
[Upgrading monorepos that share fragments](#upgrading-monorepos-that-share-fragments)
and the [0.18.0 upgrade notes](../RELEASE_NOTES_0.18.0.md).
:::

## Example

```text
orders/
├── contract.fluid.yaml
├── owner.yaml
├── data/orders.csv
└── parts/
    ├── build.yaml
    └── policy.yaml
```

```yaml
# orders/contract.fluid.yaml
fluidVersion: 0.7.3
kind: DataProduct
id: sales.orders_v1
name: Orders
domain: sales
metadata:
  layer: Silver
  owner:
    $ref: ./owner.yaml                 # the whole file
builds:
  - $ref: parts/build.yaml             # refs work inside lists
exposes:
  - exposeId: orders_summary
    kind: table
    binding:
      platform: local
      format: csv
      location:
        path: out/summary.csv
    policy:
      $ref: parts/policy.yaml#/gold    # file + JSON pointer
    contract:
      schema:
        - name: id
          type: INTEGER
        - name: doubled
          type: INTEGER
```

```yaml
# orders/parts/policy.yaml
gold:
  classification: Internal
  authz:
    readers:
      - group:sales-analysts
```

```console
$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.3)
Validation completed in 0.001s
```

[`fluid bundle`](../cli/bundle.md) writes the single resolved document. The
ref nodes are replaced by their targets:

```console
$ fluid bundle contract.fluid.yaml
fluidVersion: 0.7.3
kind: DataProduct
id: sales.orders_v1
name: Orders
domain: sales
metadata:
  layer: Silver
  owner:
    team: sales-analytics
    email: sales-analytics@example.com
builds:
- id: summarise
  pattern: embedded-logic
  engine: sql
  properties:
    sql: SELECT id, amount * 2 AS doubled FROM read_csv('data/orders.csv')
exposes:
- exposeId: orders_summary
  ...
  policy:
    classification: Internal
    authz:
      readers:
      - group:sales-analysts
  ...
```

## How a ref is read

- A `$ref` node is an object whose only key is `$ref`.
- A ref is resolved relative to the file that contains it, so
  `parts/build.yaml` may itself say `$ref: ./policy.yaml`.
- `file.yaml#/a/b` selects the object at [JSON pointer](https://www.rfc-editor.org/rfc/rfc6901)
  `/a/b` inside the file. Without a `#`, the whole file is used.
- Same-document refs (`$ref: "#/definitions/x"`) are left in place as written.

## The ref root

Every ref must name a file inside the **ref root**. By default the ref root is
the directory that holds the root contract file (`orders/` above). It applies
to every ref, including refs inside fragments: a fragment in `orders/parts/`
can reach anything under `orders/` and nothing outside it.

The check runs after `..` segments and symlinks are resolved, so neither can
be used to get out. It also runs before the target is opened, so the error is
the same whether or not the target exists.

| `$ref` written in `orders/contract.fluid.yaml` | Result |
|---|---|
| `./owner.yaml`, `parts/policy.yaml#/gold` | resolved |
| `../shared/policy.yaml` | refused: escapes the ref root |
| `./link.yaml`, where `link.yaml` is a symlink to a file outside `orders/` | refused: escapes the ref root |
| `/etc/hosts`, `C:\x.yaml`, `\\server\share\x.yaml` | refused: must be a relative path |
| `file:///etc/hosts`, `https://…`, `s3://…`, `//host/…` | refused: remote refs are not supported |

### What a refused ref looks like

`fluid validate` reports it as `contract_load_failed` and exits `1`:

```console
$ fluid validate contract.fluid.yaml
❌ Validation error: contract_load_failed
   error: $ref '../shared/policy.yaml#/gold' at JSON pointer '/exposes/0/policy' in
   /work/orders/contract.fluid.yaml escapes the ref root /work/orders (after resolving
   '..' and symlinks); refs may only name files inside it. To compose fragments from a
   wider tree (e.g. a monorepo's shared/ directory), set FLUID_REF_ROOT to that
   directory or pass ref_root= to the loader; see docs/contract-refs.md.
   [ERR_CONTRACT_LOAD_FAILED]
```

`fluid bundle` prints the same message and exits `2`. The other refusals name
their reason:

```console
$ fluid bundle contract.fluid.yaml       # with $ref: /etc/hosts
❌ $ref resolution error: $ref '/etc/hosts' at JSON pointer '/exposes/0/policy' in
/work/orders/contract.fluid.yaml must be a relative path, got absolute — use a path
relative to the file that contains the ref

$ fluid bundle contract.fluid.yaml       # with $ref: file:///etc/hosts
❌ $ref resolution error: $ref 'file:///etc/hosts' at JSON pointer '/exposes/0/policy'
in /work/orders/contract.fluid.yaml is a URL; remote refs (including file://) are not
supported — use a relative path to a file inside the ref root
```

Every message names the ref, the JSON pointer of the `$ref` node, and the file
it was written in.

::: tip Why the root exists
Contracts are often untrusted input. A platform such as the FLUID Command
Center runs `fluid validate` and `fluid bundle` on contracts its users upload.
Without a root, a contract could compose any YAML or JSON file the process can
read into itself, and `fluid bundle` would print it back.
:::

## Widening the root for a monorepo

To share fragments between products, set the ref root to a directory that
contains both the contracts and the shared fragments:

```text
repo/
├── shared/policy.yaml
└── products/orders/contract.fluid.yaml   # $ref: ../../shared/policy.yaml#/gold
```

```console
$ cd repo
$ FLUID_REF_ROOT=. fluid validate products/orders/contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.3)
Validation completed in 0.001s
```

Without `FLUID_REF_ROOT`, the same command fails with `escapes the ref root`.

From Python, pass `ref_root=` to the engine's loader. `load_contract`,
`load_with_overlay` and `compile_contract` in `fluid_build.loader` all accept
it, and it wins over `FLUID_REF_ROOT`:

```python
from fluid_build.loader import load_contract

contract = load_contract("repo/products/orders/contract.fluid.yaml", ref_root="repo")
print(contract["exposes"][0]["policy"]["classification"])
# Internal
```

The [public contract-loading API](../advanced/contract-loading-api.md)
(`fluid_build.api.load_contract`) has no `ref_root` argument. It goes through
the same loader, so it honours `FLUID_REF_ROOT`. Its in-memory forms
(`load_contract_from_text`, `load_contract_from_dict`) do not: their ref root
is always the `base_dir` you pass.

### Rules for the wider root

- It widens the root only for a contract inside it, and only if it is an
  existing directory.
- **`FLUID_REF_ROOT` is ignored for a contract outside it**, and when it is not
  a directory or cannot be resolved. That contract gets the default root, its
  own directory, and a `ref_root_env_ignored` warning says so. Refs that leave
  the directory then fail, and the error says the variable was ignored and why:

  ```console
  $ cd repo
  $ FLUID_REF_ROOT=. fluid validate /work/upload-1234/contract.fluid.yaml
  ref_root_env_ignored: contract /work/upload-1234/contract.fluid.yaml is outside
  FLUID_REF_ROOT='.' (resolved to /work/repo); the ref root must contain the contract.
  Ignoring it for this contract: its $refs are confined to the contract's own directory
  /work/upload-1234 (the default). Logged once per value in this process; a later
  contract it is ignored for gets no warning, but its escape errors say the variable
  was ignored and why.
  ❌ Validation error: contract_load_failed
     error: $ref '../shared/policy.yaml#/gold' at JSON pointer '/exposes/0/policy' in
     /work/upload-1234/contract.fluid.yaml escapes the ref root /work/upload-1234 (after
     resolving '..' and symlinks); refs may only name files inside it. FLUID_REF_ROOT is
     set but was ignored for this contract: ...
  ```

- **`ref_root=` is strict.** The caller sets it for one contract, so a
  `ref_root` that cannot be resolved, is not a directory, or does not contain
  the contract raises `RefResolutionError`:

  ```python
  load_contract("repo/products/orders/contract.fluid.yaml", ref_root="orders")
  # RefResolutionError: contract repo/products/orders/contract.fluid.yaml is outside
  # ref_root='orders' (resolved to /work/orders); the ref root must contain the contract
  ```

- A blank `FLUID_REF_ROOT` counts as unset.
- It is only consulted when the contract has a ref to another file.
- It widens the root and nothing else. URLs and absolute paths are still
  refused, and refs that resolve into system directories (`/etc`, `/proc`,
  `/private/etc` on macOS, and so on) are still blocked.

::: danger Scope it to one command
Every contract inside `FLUID_REF_ROOT` is widened, with no warning. A value
left exported in your shell widens every contract under it that you load
later, and a service whose upload directory sits under its `FLUID_REF_ROOT`
widens every uploaded contract. Set it per command, as in the examples, and to
the narrowest directory that works. Setting it to `/` turns the confinement
off.
:::

## Upgrading monorepos that share fragments

Before 0.18.0 a relative ref could climb out of the contract's directory, so
monorepos shared fragments with `$ref: ../other-product/…`. Those refs now
fail with `escapes the ref root` until the root is widened. Set
`FLUID_REF_ROOT` (or `ref_root=`) to the repository root, or to the narrowest
directory that holds the products and their shared fragments:

```bash
FLUID_REF_ROOT="$(git rev-parse --show-toplevel)" \
  fluid validate products/orders/contract.fluid.yaml
```

In CI, set it on the step that runs `fluid`, not for the whole job.

Contracts whose refs stay inside their own directory need no change.

## Catching the error in Python

`RefConfinementError` is a subclass of `RefResolutionError`, so existing
`except RefResolutionError` handlers keep working. It carries the details as
attributes:

```python
from fluid_build.loader import RefConfinementError, load_contract

try:
    load_contract("repo/products/orders/contract.fluid.yaml")
except RefConfinementError as err:
    print(err.ref)                   # ../../shared/policy.yaml#/gold
    print(err.pointer)               # /exposes/0/policy
    print(err.source)                # /work/repo/products/orders/contract.fluid.yaml
    print(err.root)                  # /work/repo/products/orders
    print(err.ignored_ref_root_env)  # None
```

`ignored_ref_root_env` holds the `FLUID_REF_ROOT` value when it was set but did
not apply to this contract.

The public API raises `ContractLoadError` with
`event == "contract_ref_unresolved"` for the same refusal; see
[Contract loading API](../advanced/contract-loading-api.md#contractloaderror).

## OpenAPI fragments inside a bundle

When `fluid validate` checks a `fluid bundle --format tgz` archive, OpenAPI
documents extracted into `sources/openapi/` have no directory of their own, so
the same check applies with **no** root: only same-document refs
(`$ref: "#/components/schemas/Order"`) are allowed. Any other `$ref` is
reported as an `OAS-REF-EXTERNAL` error, and openapi-spec-validator is not run
on that fragment (it would follow `file://` and `http(s)://` refs). Inline the
referenced schemas under `components` instead.

This applies to a `$ref` key anywhere in the fragment, including inside
`example`, `examples.*.value` and `x-*` payloads. If an example payload has to
contain a `$ref`, rename the key in the payload (for example `ref`) or drop the
example.

The check runs where openapi-spec-validator would: when it is not installed,
the fragment is reported as not validated instead.

## Related

- [`fluid bundle`](../cli/bundle.md): write the resolved document or a `.tgz` bundle
- [Contract loading API](../advanced/contract-loading-api.md): load a contract from Python exactly as `fluid plan` sees it
- [DuckDB sandbox](../advanced/duckdb-sandbox.md): the matching confinement for SQL inside a contract
- [Upgrading to 0.18.0](../RELEASE_NOTES_0.18.0.md)

::: tip About the examples
Output on this page was produced with the 0.18.0 code (forge-cli
[#687](https://github.com/Agenticstiger/forge-cli/pull/687)). Long temporary
paths are shortened to `/work`, and long lines are re-wrapped.
:::
