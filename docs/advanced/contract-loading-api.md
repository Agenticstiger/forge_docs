---
title: Contract loading API
description: Load a contract from Python exactly as fluid plan sees it, with fluid_build.api.load_contract, load_contract_from_text and load_contract_from_dict.
---

# Contract loading API — `fluid_build.api.load_contract`

`fluid_build.api.load_contract` returns the contract that `fluid plan` plans:
the same dict `plan.json` embeds as `contract`, after every rewrite the engine
makes on the way in. Use it when your code has to agree with the engine about
what a contract *is*: comparing a contract to the plan made from it, diffing
two revisions, rendering a contract in a UI, or checking it in CI.

Added in CLI 0.18.0, `fluid_build.api` version **1.1**
([forge-cli #688](https://github.com/Agenticstiger/forge-cli/pull/688)). It is
part of the [stable public API](./api-stability.md).

```python
import fluid_build.api
print(fluid_build.api.__api_version__)
# 1.1
```

## Load a contract file

The contract below is the one from
[Composing a contract with `$ref`](../concepts/contract-refs.md): an owner, a
build and a policy, each composed from a fragment.

```python
from fluid_build.api import load_contract

loaded = load_contract("orders/contract.fluid.yaml")

loaded.origin           # 'file'
loaded.digest           # 'sha256:ffb903222a5ab79af24df49dcf2729924b7756dc11e0ab221775df93df6dd391'
loaded.files
# (PosixPath('/work/orders/contract.fluid.yaml'), PosixPath('/work/orders/owner.yaml'),
#  PosixPath('/work/orders/parts/build.yaml'), PosixPath('/work/orders/parts/policy.yaml'))
loaded.unresolved_refs  # ()
loaded.contract["exposes"][0]["policy"]
# {'classification': 'Internal', 'authz': {'readers': ['group:sales-analysts']}}
```

### With an environment overlay

```python
loaded = load_contract("contract.fluid.yaml", env="prod")

loaded.overlay   # PosixPath('/work/orders/overlays/prod.yaml')
loaded.contract["exposes"][0]["binding"]["location"]
# {'path': 'out/prod/summary.csv'}
```

`env` is an environment *name*, never a path. The engine turns `env` into
overlay paths (`overlays/<env>.yaml`, `<env>.json`, …), so an env holding `..`
or an absolute path would merge whichever file it named into the contract. An
env that is not a single path component is refused before a file is read:

```python
from fluid_build.api import ContractLoadError

try:
    load_contract("contract.fluid.yaml", env="../../etc/x")
except ContractLoadError as err:
    err.event  # 'contract_env_invalid'
    str(err)
    # "env '../../etc/x' is not an environment name: an env names an overlay file
    # next to the contract, so it must be one path component: not empty, not '.' or
    # '..', no '/', '\' or NUL, not drive-qualified ('C:prod')"
```

Refused: `""` (not read as `None`), `.`, `..`, anything holding `/`, `\` or a
NUL byte, and a drive-qualified name (`C:prod`, on every platform). Every other
string loads exactly as `fluid plan --env` loads it. Pass `None` for no env.

A `fluid bundle` archive loads the same way, and is refused for an env it was
not built for, as on the CLI:

```python
load_contract("runtime/bundle.tgz", env="prod")
```

## Is this the contract that plan was made from?

```console
$ fluid plan contract.fluid.yaml --env prod --out runtime/plan.json
```

```python
import json
from pathlib import Path

from fluid_build.api import load_contract
from fluid_build.forge.core.plan_digest import compute_contract_digest

plan = json.loads(Path("runtime/plan.json").read_text())
loaded = load_contract("contract.fluid.yaml", env="prod")

loaded.digest == compute_contract_digest(plan["contract"])
# True
```

Formatting, comments, key order, quoting, Unicode normal form, an alias beside
its canonical value (`format: bigquery-table` / `bigquery_table`) and a legacy
`build:` beside `builds:` do not change the digest. Every other value does.

**Compare digests, not dicts.** `loaded.contract` keeps a YAML magic-word or
numeric key (`on:`, `no:`, `1:` in an open block such as `extensions`) as the
Python `bool` / `int` the engine plans with, while `plan.json` writes every key
as a string. The digest coerces keys the same way `plan.json` does.

::: warning `digest` is not `fluid contract digest`
`loaded.digest` is the digest of the **planned** contract: normalised,
composed and overlaid. It is not the value `fluid contract digest` prints, and
not what a federation `upstreamDigest` pins: those hash the file as parsed,
before any alias rewrite, `$ref` or overlay. Do not pin `upstreamDigest` from
`loaded.digest`.
:::

## Contract text or a parsed dict, without touching the disk

```python
from fluid_build.api import load_contract_from_dict, load_contract_from_text

loaded = load_contract_from_text(text)                    # YAML by default
loaded = load_contract_from_text(text, suffix=".json")    # or JSON
loaded = load_contract_from_dict(document)                # already parsed
```

Neither reads a file. A `$ref` is left in place and listed in
`unresolved_refs`; you decide whether that is an error. For the contract
above, sent as text from a form or a database row:

```python
submitted = load_contract_from_text(text)
submitted.origin           # 'memory'
submitted.unresolved_refs  # ('./owner.yaml', 'parts/build.yaml', 'parts/policy.yaml#/gold')
```

### Text with its fragments and an overlay

Pass `base_dir` to resolve file refs against a directory. The refs are
confined to `base_dir`, as the
[ref root](../concepts/contract-refs.md#the-ref-root); `FLUID_REF_ROOT` is not
consulted on this path (see [below](#fluid-ref-root)):

```python
loaded = load_contract_from_text(text, base_dir="orders")
loaded.unresolved_refs                                       # ()
loaded.digest == load_contract("orders/contract.fluid.yaml").digest
# True
```

```python
loaded = load_contract_from_text(
    text,
    base_dir="orders",
    overlay={"exposes": [{"binding": {"location": {"path": "out/prod/summary.csv"}}}]},
)
```

With `base_dir` set to a contract's directory and `overlay` set to the parsed
overlay file `--env` would select, the result equals
`load_contract(that_file, env=...)`, provided no ref needs a root wider than
`base_dir` (see [`FLUID_REF_ROOT`](#fluid-ref-root)). Without `base_dir`,
passing `overlay` for a document that holds file `$ref` values raises
`contract_overlay_needs_base_dir`, because whether the engine would apply the
overlay depends on what the fragments hold.

## What "as plan sees it" means

In the engine's order:

1. **Parse**: JSON, or YAML through the engine's billion-laughs guard.
2. **`$ref` composition**: each `{"$ref": "./file.yaml#/pointer"}` replaced by
   its target, resolved against the contract's directory (or `base_dir`) under
   the [ref root](../concepts/contract-refs.md#the-ref-root). Same-document
   `#/...` pointers are kept, and listed in `unresolved_refs`.
3. **Overlay**: for `env`, the first of `overlays/<env>.yaml|yml|json`,
   `<env>.yaml|yml|json`, `<contract-stem>.<env>.yaml|yml|json` next to the
   contract, deep-merged over the base (objects key by key, lists of objects
   by position, anything else replaced). A bundle is never re-overlaid.
4. **Alias values**: human-friendly values rewritten to the schema's enum
   value, for example `source.kind: pg` → `postgres`,
   `source.mode: incremental` → `incremental_append`,
   `binding.format: kafka` → `kafka_topic`, `iceberg-table` → `iceberg`.
5. **Legacy `build:`**: a singular `build:` becomes `builds: [build]`; when
   both are present `builds:` wins.

Step 4 runs before step 5, as in the engine, so an alias under a legacy
singular `build:` is **not** rewritten (and `fluid plan` then rejects it at the
schema gate). Write `builds:` to get alias rewriting for builds.

**Validation is not part of loading.** A schema-invalid contract loads;
`fluid validate` and `fluid plan` reject it.

### Edge case: an overlay next to a `$ref`

When the overlay file, or the merged contract, still holds a `$ref` (an
overlay that references a fragment, or a same-document `#/...` pointer in the
contract), the engine reloads the contract from the base file and the overlay
is dropped: `fluid plan --env prod` plans the base contract. `load_contract`
returns the base too, and says so: `overlay` is `None`, the overlay is not in
`files`, and a `contract_overlay_not_applied` WARNING names the file. Keep
`$ref` out of overlays, and use file refs rather than `#/...` pointers in a
contract that has overlays.

### `FLUID_REF_ROOT`

These functions have no `ref_root` argument, and the environment variable
reaches only one of them.

- **`load_contract(path)`**, the file form, goes through the engine's file
  loader, so `FLUID_REF_ROOT` in the process environment applies to it as it
  does to the CLI.
- **`load_contract_from_text` and `load_contract_from_dict`** with `base_dir`
  always use `base_dir` as the ref root. `FLUID_REF_ROOT` is not consulted, and
  a ref that leaves `base_dir` is refused with `ContractLoadError`, even when
  the same contract loads from its file with `FLUID_REF_ROOT` set. The error
  text still suggests setting `FLUID_REF_ROOT`; on this path that has no effect.

To compose a monorepo fragment in memory, pass the wider directory as
`base_dir` and write the refs relative to it (`./shared/policy.yaml#/gold`
with `base_dir` at the repository root, not `../shared/...` with `base_dir` at
the product). Otherwise write the contract to a file and use `load_contract`,
or call `fluid_build.loader.load_contract(path, ref_root=...)`; see
[Widening the root for a monorepo](../concepts/contract-refs.md#widening-the-root-for-a-monorepo).

## Reference

### `load_contract(path, *, env=None, logger=None) -> LoadedContract`

Loads a contract file or a bundle through `fluid plan`'s own loader. `path` is
resolved to an absolute path first, as `fluid plan` does. The CLI's gate on
operator-typed paths (no `..`, no symlink) is not applied to `path`: a library
caller chooses its own paths. `env` must be a single path component or `None`.

### `load_contract_from_text(text, *, suffix=".yaml", base_dir=None, overlay=None, logger=None) -> LoadedContract`

Parses `text` with the engine's parser (`suffix` picks it as a file extension
would), then loads the result as `load_contract_from_dict` does.

### `load_contract_from_dict(document, *, base_dir=None, overlay=None, logger=None) -> LoadedContract`

Loads a parsed document. `document` and `overlay` are never modified. `logger`
receives the `contract_overlay_not_applied` WARNING (default: the
`fluid.api.contract` logger).

### `LoadedContract`

A frozen dataclass.

| Field | Type | Meaning |
|---|---|---|
| `contract` | `dict` | The contract as planned, keys as the engine holds them. A fresh dict each call; yours to mutate. |
| `origin` | `"file"` \| `"bundle"` \| `"memory"` | Which entry point and input shape produced it. |
| `source` | `Path \| None` | The resolved contract or bundle path; `None` for the in-memory forms. |
| `env` | `str \| None` | The env requested. |
| `overlay` | `Path \| None` | The overlay file merged for `env`. Never set for a bundle, or when the engine dropped the overlay. |
| `files` | `tuple[Path, ...]` | Every file composed: the source, each `$ref` target in first-read order, the overlay. Empty for the in-memory forms without `base_dir`. |
| `unresolved_refs` | `tuple[str, ...]` | `$ref` values left in `contract`, in document order. |
| `digest` | `str` (property) | `sha256:<hex>` of the planned contract via `compute_contract_digest`. Raises `contract_not_serialisable` when JSON cannot represent the contract. |

### `ContractLoadError`

Every failure raises `ContractLoadError` with a stable `event` (safe to route
on), `message`, `path` when there is one, and the engine's exception as
`__cause__`:

```python
from fluid_build.api import ContractLoadError, load_contract

try:
    load_contract("orders/escape.fluid.yaml")
except ContractLoadError as err:
    print(err.event)
    # contract_ref_unresolved
    print(err)
    # $ref '../shared/policy.yaml#/gold' at JSON pointer '/exposes/0/policy' in
    # /work/orders/escape.fluid.yaml escapes the ref root /work/orders (after resolving
    # '..' and symlinks); refs may only name files inside it. ...
```

| `event` | When |
|---|---|
| `contract_not_found` | The contract file does not exist, or `path` / `base_dir` cannot name a file (it holds a NUL byte). |
| `contract_parse_failed` | The text is not valid JSON/YAML, is not UTF-8, or trips the YAML size/anchor guard. |
| `contract_not_a_mapping` | The document (or overlay) root is not an object. |
| `contract_ref_unresolved` | A `$ref` target is missing, cyclic, outside the ref root, or its pointer does not resolve. |
| `contract_env_invalid` | `env` is not a single path component. |
| `contract_overlay_needs_base_dir` | In-memory form: `overlay` given for a document with file `$ref` values but no `base_dir`. |
| `contract_not_serialisable` | Raised by `.digest`: the contract holds a value JSON cannot represent (an unquoted YAML date, a set, binary, a self-referencing alias). `fluid plan` cannot write it either; quote the value. |
| `contract_load_failed` | Any other loader failure. |
| *engine event* | Passed through unchanged, for example `overlay_declared_but_missing`, `bundle_not_found`, `bundle_env_mismatch`, `bundle_manifest_invalid`. |

## Stability

`fluid_build.api` follows the SemVer policy in
[API Stability](./api-stability.md); these names were added in 1.1 and are
locked by the API surface snapshot test. The behavioural promise:
`load_contract(path, env=env).contract` is the contract
`fluid plan path --env env` plans, equal to `plan.json["contract"]` once keys
are written as strings, and always equal by `.digest`.

- The file form calls the engine's loader itself, so a new loader step reaches
  it with no change. A test runs the real `fluid plan` on fixtures that
  exercise every rewrite and fails if the two differ.
- The in-memory forms have no file to hand the loader, so they replay a fixed
  sequence of the loader's steps. Tests pin them to the file form, and a guard
  test fails when the engine loader gains, loses or reorders a step that
  touches the contract.

::: tip Not the private helpers
Do not import helpers from `fluid_build._contract_loader` (for example
`_normalize_contract_aliases`) to reproduce this. They are private, their
order matters, and they are not the whole pipeline.
:::

## Related

- [Composing a contract with `$ref`](../concepts/contract-refs.md)
- [API Stability](./api-stability.md)
- [DuckDB sandbox](./duckdb-sandbox.md)
- [Upgrading to 0.18.0](../RELEASE_NOTES_0.18.0.md)

::: tip About the examples
Output on this page was produced by running the snippets against the 0.18.0
code (forge-cli #687, #688 and #689 together). Long temporary paths are
shortened to `/work`.
:::
