---
title: Composing a contract with $ref
description: Pull any part of a contract from another file with $ref, and the ref root that confines which files a fragment may come from.
---

# Composing a contract with `$ref`

A contract can pull any part of itself from another file with `$ref`: an
object, a list or a scalar from a YAML or JSON file, or the text of a SQL,
Markdown or other text file. `fluid validate`, `fluid plan`, `fluid apply`,
`fluid bundle` and every other command resolve every ref before they do
anything else, so the rest of the pipeline sees one document.

This page covers how a single ref is read and which files it may name. For
working with a split product (the layout `fluid split` writes, which commands
read it, overlays, CI and digests), see [Contract fragments](./fragments.md).

::: tip Which release
Refs to files and the ref root date from 0.18.0. Text files, keys beside a
`$ref`, same-document pointers, refs inside overlays and the workspace
`ref_root` are new in 0.25.0
([forge-cli #760](https://github.com/Agenticstiger/forge-cli/pull/760)). A
contract that uses them fails, or loads differently, on 0.24.0 and earlier, so
pin `data-product-forge>=0.25.0` wherever it is validated or planned.
:::

## Example

```text
orders/
├── contract.fluid.yaml
├── owner.yaml
├── data/orders.csv
├── sql/summary.sql
└── parts/
    ├── build.yaml
    └── policy.yaml
```

```yaml
# orders/contract.fluid.yaml
fluidVersion: 0.7.5
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
# orders/parts/build.yaml
id: summarise
pattern: embedded-logic
engine: sql
properties:
  sql:
    $ref: ../sql/summary.sql           # the text of the file, not parsed
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
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.001s
```

[`fluid bundle`](../cli/bundle.md) prints the single resolved document. The
ref nodes are replaced by their targets:

```console
$ fluid bundle contract.fluid.yaml
fluidVersion: 0.7.5
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
    sql: 'SELECT id, amount * 2 AS doubled FROM read_csv(''data/orders.csv'')

      '
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

### What a ref may name

- **A YAML or JSON file.** The fragment may be any value: an object, a list
  (a file that is the list of quality rules itself) or a scalar. The root
  contract and an overlay must be objects. A file with no known suffix is
  read as JSON of any shape, otherwise as a YAML object, so a dotfile such as
  `.env` never composes as a string.
- **A text file.** A target ending in `.sql`, `.md`, `.markdown`, `.txt`,
  `.py`, `.scala` or `.r` (any case) becomes its text, UTF-8, never parsed.
  The BOM is dropped and CRLF line ends become LF. The file may be at most
  5 MiB. Other text-like suffixes (`.hql`, `.ddl`, `.j2`) are read as YAML or
  JSON, not as text.
- **A place inside a file**, with a [JSON pointer](https://www.rfc-editor.org/rfc/rfc6901):
  `parts/policy.yaml#/gold`. The escapes `~0` (for `~`) and `~1` (for `/`)
  decode, so a key containing `/` can be addressed. A pointer into a text
  file is refused:

  ```text
  ❌ $ref resolution error: $ref './sql/t.sql#/x' at JSON pointer '/builds/0/properties/sql' in
  /work/p/contract.fluid.yaml points into t.sql with '#/x', but a .sql file is read as text and
  a JSON pointer only selects inside a JSON or YAML document. Drop '#/x', or keep the text in a
  YAML file under a key and point at that key.
  ```

- **A place in the composed contract**, with a same-document pointer:
  `$ref: "#/builds/0/properties/parameters/shared"`. See
  [Same-document pointers](#same-document-pointers).

A ref is resolved relative to the file that contains it, so
`parts/build.yaml` above reaches the SQL file as `../sql/summary.sql`. A
`$ref` in an overlay resolves relative to the overlay file.

`file.yaml#key`, without the slash after `#`, is accepted as 0.24.0 accepted
it. Write `file.yaml#/key`. A bare `#foo` is not a JSON pointer and is refused.

### Keys beside a `$ref`

Keys written beside `$ref` are merged over a copy of what it names, as a
[JSON Merge Patch](https://www.rfc-editor.org/rfc/rfc7386) (RFC 7386): objects
merge, a list or a scalar replaces, and `null` removes a key. This reuses a
shared column with one field changed:

```yaml
# shared/columns.yaml
order_id:
  name: order_id
  type: INTEGER
  description: Order id
  sensitivity: low
```

```yaml
# the contract
contract:
  schema:
    - $ref: shared/columns.yaml#/order_id
      description: Order key      # replaces
      sensitivity: null           # removes the key
```

```text
# fluid bundle
    schema:
    - name: order_id
      type: INTEGER
      description: Order key
```

Refs inside those keys resolve relative to the file that holds them and are
confined like any other. A target that is not an object cannot take keys
beside its `$ref`, and a text file is such a target:

```text
❌ $ref resolution error: $ref './sql/t.sql' at JSON pointer '/builds/0/properties/sql' in
/work/p/contract.fluid.yaml has sibling keys ('extra'), which are merged over its target, but
the target is text, not an object. Move those keys into the target, or drop them.
```

Before 0.25.0 these keys stayed in the contract as a literal `$ref` key and the
target was never read. If two `$ref` keys appear in one mapping, the last one
wins, as YAML has it for any repeated key.

### Same-document pointers

`{$ref: "#/a/b"}` names a place in the **composed** contract: every fragment
read and the `--env` overlay merged, whichever file the pointer is written in.
So splitting a contract never changes what a pointer names, and an overlay that
changes a shared value reaches every pointer to it. A pointer may go through
other refs, and keys beside a pointer merge like keys beside a file ref.
A pointer that reaches itself is a cycle.

A pointer resolves after every merge, so it cannot take part in one. These
are refused, naming the file and the place:

- a pointer that would be merged into an object already at its place (a key
  beside a file `$ref` whose target holds an object there, or an overlay
  value over a base object);
- an overlay pointer over a base list of objects (which the overlay would
  merge entry by entry), the base list written out or itself a pointer;
- an overlay object or list of objects over a base pointer.

Write those values out, or name a file (`./x.yaml#/a`), which is read before the
merge. Anything else replaces, as any value does.

### No `$ref` survives

After composition no `$ref` is left anywhere, open objects such as
`parameters`, `labels` and `extensions` included. A ref that cannot be
resolved fails the command and names the file and the place it was written
at. There is no fallback to the base contract.

So a contract cannot embed a document that carries its own `$ref` keys, such
as a JSON Schema or an OpenAPI fragment inside `parameters` or an extension:
every `$ref` key is read as a contract reference. Keep such a payload as a
string.

### YAML anchors and `<<` merges

YAML anchors, aliases and `<<` merge keys are resolved by the YAML parser,
file by file, **before** any `$ref` is looked at. Two things follow.

An anchor is local to its file. An alias in a fragment cannot name an anchor in
the root; the fragment fails to parse:

```text
❌ $ref resolution error: Failed to parse $ref target 'fragments/build2.yaml' at JSON pointer
'/builds/1' in /work/p/c2.yaml: found undefined alias 'base'
  in "build2.yaml", line 2, column 9:
    engine: *base
            ^
```

An alias or `<<` copies the `$ref` node with the rest of its mapping, and each
copy is resolved on its own. Two builds can share one fragment and differ in
the keys beside the ref:

```yaml
builds:
  - &base
    $ref: fragments/build.yaml
    id: summarise
  - <<: *base          # copies the $ref, then id replaces the copied id
    id: second
```

`fluid bundle` gives two builds, `summarise` and `second`, each with the
fragment's `pattern`, `engine` and `properties`. For how `fluid split` treats
a root with aliases, see
[YAML aliases and merge keys](../cli/split.md#yaml-aliases-and-merge-keys).

### Limits

- A ref that leads back to itself fails with `Circular $ref detected`:

  ```text
  ❌ $ref resolution error: Circular $ref detected: /work/p/a.yaml# (at JSON pointer '/x' in /work/p/b.yaml)
  ```

- Resolution stops past a nesting depth of 20 refs with
  `$ref nesting depth exceeded 20`.
- One composition resolves at most 10,000 refs and brings in at most
  1,000,000 nodes and 52,428,800 characters of copied text. The composed
  contract may nest at most 128 levels, the cap every YAML file already has.
- Every file the composition reads is read bounded and only as a regular
  file. A root contract must be a regular file of at most 5 MiB, so a contract
  read through a pipe (`fluid validate <(git show HEAD:contract.fluid.yaml)`)
  is refused; write it to a file first.
- Errors found after composition name the file and line they were written in:

  ```text
   1. fragments/schemas/orders_summary.yaml:4 (exposes[0].contract.schema[0].type): 42 is not valid under any of the given schemas
  ```

  A value an overlay set names the overlay. In Python,
  `LoadedContract.origin_of(path)` answers the same question.

## The ref root

Every ref must name a file inside the **ref root**. By default the ref root is
the directory that holds the root contract file (`orders/` above). It applies
to every ref, including refs inside fragments and overlays: a fragment in
`orders/parts/` can reach anything under `orders/` and nothing outside it.

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

Overlays are held to the same root: an `overlays/` directory or an overlay
file that links outside the contract's tree is refused. `--env` must name an
environment, not a path; `--env ../x` and `--env /abs/x` are refused by every
command.

### What a refused ref looks like

`fluid validate` reports it as `contract_load_failed` and exits `1`:

```console
$ fluid validate contract.fluid.yaml
❌ Validation error: contract_load_failed
   error: $ref '../../shared/policy.yaml' at JSON pointer '/exposes/0/policy' in
   /work/repo/products/orders/contract.fluid.yaml escapes the ref root
   /work/repo/products/orders (after resolving '..' and symlinks); refs may only
   name files inside it. To compose fragments from a wider tree (e.g. a monorepo's
   shared/ directory), declare ref_root in the workspace's fluid.workspace.yaml,
   set FLUID_REF_ROOT to that directory, or pass ref_root= to the loader; see
   docs/contract-refs.md.
   [ERR_CONTRACT_LOAD_FAILED]
```

`fluid bundle` prints the same message after `❌ $ref resolution error:` and
exits `2`. The other refusals name their reason:

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

These errors name the ref, the JSON pointer of the `$ref` node, and the file it
was written in: the confinement refusals above (a URL, an absolute path, an
escape from the ref root), a ref blocked because it resolves into a system
directory, a missing target file, and a JSON pointer that does not resolve.

::: tip Why the root exists
Contracts are often untrusted input: services, CI jobs or shared hosts run
`fluid validate` and `fluid bundle` on contracts other people wrote. Without a
root, a contract could compose any YAML or JSON file the process can read into
itself, and `fluid bundle` would print it back.
:::

## Widening the root for a monorepo

To share fragments between products, set the ref root to a directory that
contains both the contracts and the shared fragments. There are three ways to
set it. When more than one is set, the first in this list wins:

1. `ref_root=` passed to the loader, from Python.
2. The `FLUID_REF_ROOT` environment variable.
3. `ref_root` in the workspace's `fluid.workspace.yaml`.

With none of them, the root is the contract's own directory.

```text
repo/
├── fluid.workspace.yaml                  # ref_root: .
├── shared/policy.yaml
└── products/orders/contract.fluid.yaml   # $ref: ../../shared/policy.yaml
```

### In the workspace

*(since 0.25.0, [forge-cli #760](https://github.com/Agenticstiger/forge-cli/pull/760))*
`ref_root` in `fluid.workspace.yaml` widens the root once for every product
under it, so shared fragments need no `FLUID_REF_ROOT` in CI, in the editor
or in any other tool on the library:

```yaml
# repo/fluid.workspace.yaml
ref_root: .        # relative to this file; refRoot and workspace: {ref_root} are read too
```

```console
$ cd repo
$ fluid validate products/orders/contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.001s
```

The workspace file is found by walking up from the contract, and it is read
only for a contract that names another file. A project file must not widen
confinement past its own tree. This is also why a project `.env` cannot set
`FLUID_REF_ROOT`. So the workspace's root is used only when it is:

- a relative directory at or below the workspace file's own directory;
- a directory that contains the contract;
- not `/`, a home directory or a temporary directory, and not above the
  repository the contract is in.

Anything else is ignored with a warning (see
[When a setting is ignored](#when-a-setting-is-ignored)), and the contract
keeps its own directory. `FLUID_IGNORE_WORKSPACE_REF_ROOT=1` turns the setting
off for the process, so that every contract keeps its own directory; a project
`.env` cannot set it.

### In the environment

```bash
FLUID_REF_ROOT=repo fluid validate repo/products/orders/contract.fluid.yaml
```

### From Python

`load_contract`, `load_with_overlay` and `compile_contract` in
`fluid_build.loader` all accept `ref_root`:

```python
from fluid_build.loader import load_contract

contract = load_contract("repo/products/orders/contract.fluid.yaml", ref_root="repo")
print(contract["exposes"][0]["policy"]["classification"])
# Internal
```

### Rules for the wider root

- It widens the root only for a contract inside it, and only if it is an
  existing directory.
- `FLUID_REF_ROOT` applies to every contract the process loads. It is
  ignored for a contract outside it, and when it is not a directory or cannot
  be resolved at all (a `~user` that no longer exists, a symlink loop, a
  parent the process cannot enter). That contract gets the root it would get
  without the variable (the workspace's `ref_root`, else its own directory),
  and a warning says so.
- `ref_root=` is set by the caller for one contract, so it is strict: a
  `ref_root` that cannot be resolved, is not a directory, or does not contain
  the contract raises `RefResolutionError`, naming `ref_root`:

  ```python
  load_contract("repo/products/orders/contract.fluid.yaml", ref_root="orders")
  # RefResolutionError: contract repo/products/orders/contract.fluid.yaml is outside
  # ref_root='orders' (resolved to /work/orders); the ref root must contain the contract
  ```

- A blank `FLUID_REF_ROOT` counts as unset: the default root applies.
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

### When a setting is ignored

Two warnings say that a setting did not apply. Each is logged **once** per
process, not once per contract, so a service that loads every upload from a
fresh directory logs it once.

**`ref_root_env_ignored`** is logged once per `FLUID_REF_ROOT` value, for a
contract the variable does not apply to:

```console
$ cd repo
$ FLUID_REF_ROOT=../other fluid validate products/orders/contract.fluid.yaml
ref_root_env_ignored: contract /work/repo/products/orders/contract.fluid.yaml is outside
FLUID_REF_ROOT='../other' (resolved to /work/other); the ref root must contain the
contract. Ignoring it for this contract: its $refs are confined to
/work/repo/products/orders, the root it gets without the variable. Logged once per value
in this process; a later contract it is ignored for gets no warning, but its escape
errors say the variable was ignored and why.
❌ Validation error: contract_load_failed
   error: $ref '../../shared/policy.yaml' at JSON pointer '/exposes/0/policy' in
   /work/repo/products/orders/contract.fluid.yaml escapes the ref root
   /work/repo/products/orders (after resolving '..' and symlinks); refs may only
   name files inside it. FLUID_REF_ROOT is set but was ignored for this contract:
   contract /work/repo/products/orders/contract.fluid.yaml is outside
   FLUID_REF_ROOT='../other' (resolved to /work/other); the ref root must contain
   the contract. To compose fragments from a wider tree, set FLUID_REF_ROOT to a
   directory that contains the contract or pass ref_root= to the loader; see
   docs/contract-refs.md.
```

The root-escape error repeats the reason on every load, because in a service
the warning reaches the server log and the caller sees only the error.

**`workspace_ref_root_ignored`** is logged once per workspace file, when its
`ref_root` cannot be used (it is absolute, resolves outside the workspace
directory, is not a directory, does not contain the contract, is too broad, or
the file cannot be parsed):

```text
workspace_ref_root_ignored: ref_root '../..' resolves to /work, outside the workspace
directory /work/repo; a workspace file may only widen the root within its own tree
(/work/repo/fluid.workspace.yaml). Contracts under it keep their own directory as the ref root.
```

A `ref_root` the file system could not stat, and a `fluid.workspace.yaml` that
cannot be read, are ignored the same way. A root-escape error says that the
workspace's `ref_root` was ignored and why. While
`FLUID_IGNORE_WORKSPACE_REF_ROOT` is set, it ends with `FLUID_IGNORE_WORKSPACE_REF_ROOT
is set, so no workspace's ref_root applies in this process.`

## Upgrading monorepos that share fragments

Before 0.18.0 a relative ref could climb out of the contract's directory, so
monorepos shared fragments with `$ref: ../other-product/…`. Those refs now
fail with `escapes the ref root` until the root is widened. Declare
`ref_root` in the workspace file, or set `FLUID_REF_ROOT` (or `ref_root=`) to
the repository root, or to the narrowest directory that holds the products
and their shared fragments:

```bash
FLUID_REF_ROOT="$(git rev-parse --show-toplevel)" \
  fluid validate products/orders/contract.fluid.yaml
```

In CI, prefer the workspace setting. If you use the variable, set it on the
step that runs `fluid`, not for the whole job.

Contracts whose refs stay inside their own directory need no change.

## Upgrading from 0.24.0

A `$ref` that 0.24.0 left in the contract now composes or fails. A `$ref` with
keys beside it, a same-file `#/` pointer, or a ref inside an overlay used to
stay a literal key (and, on the library path, drop the whole overlay). It now
resolves, and one that cannot be resolved fails every command, naming the
file and the place.

## Catching the error in Python

`RefConfinementError` is a subclass of `RefResolutionError`, so existing
`except RefResolutionError` handlers keep working. It carries the details as
attributes:

```python
from fluid_build.loader import RefConfinementError, load_contract

try:
    load_contract("repo/products/orders/contract.fluid.yaml")
except RefConfinementError as err:
    print(err.ref)                   # ../../shared/policy.yaml
    print(err.pointer)               # /exposes/0/policy
    print(err.source)                # file that contains the ref
    print(err.root)                  # the ref root it escaped
    print(err.ignored_ref_root_env)  # None
```

`ignored_ref_root_env` holds the `FLUID_REF_ROOT` value when it was set but did
not apply to this contract (it cannot be resolved, is not a directory, or does
not contain the contract). The root is then the contract's own directory (or
its workspace's), whatever the environment says.

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

- [Contract fragments](./fragments.md): working with a product split into fragment files
- [`fluid split`](../cli/split.md) and [`fluid bundle`](../cli/bundle.md): write the layout, and resolve it again
- [`fluid validate --fragment`](../cli/validate.md#validating-one-fragment): check one fragment file
- [Contract loading API](../advanced/contract-loading-api.md): load a contract from Python exactly as `fluid plan` sees it
- [DuckDB sandbox](../advanced/duckdb-sandbox.md): the matching confinement for SQL inside a contract
- [Upgrading to 0.18.0](../RELEASE_NOTES_0.18.0.md)

::: tip About the examples
Output on this page was produced with forge-cli 0.26.0 on small products made
for this page. Long temporary paths are shortened to `/work`, and long lines
are re-wrapped.
:::
