---
title: fluid split
description: Split a flat contract into a root contract plus fragment files joined by $ref. The inverse of fluid bundle.
---

# `fluid split`

Split a flat contract into a root contract plus fragment files, joined by
`$ref`. The inverse of [`fluid bundle`](./bundle.md). Why you would, and how
the rest of the CLI treats the result, is on
[Contract fragments](../concepts/fragments.md).

## Syntax

```bash
fluid split CONTRACT [--out DIR] [--parts PART[,PART...]] [--dry-run]
```

## Example

```console
$ fluid split contract.fluid.yaml --dry-run
Would create 3 fragments:
   fragments/builds/customer_360_pipeline.yaml
   fragments/exposes/customer_360_master.yaml
   fragments/exposes/high_value_customers.yaml

$ git commit -am "Before split"
$ fluid split contract.fluid.yaml
✅ Split into 3 fragments:
   fragments/builds/customer_360_pipeline.yaml
   fragments/exposes/customer_360_master.yaml
   fragments/exposes/high_value_customers.yaml

   Root contract updated with $ref pointers: contract.fluid.yaml
   Run fluid bundle to see the resolved output.
split_complete

$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.5)
```

The root now holds pointers where the sections were, and every comment of the
root is still there:

```yaml
builds:
- $ref: ./fragments/builds/customer_360_pipeline.yaml
exposes:
- $ref: ./fragments/exposes/customer_360_master.yaml
- $ref: ./fragments/exposes/high_value_customers.yaml
```

Choose other parts with `--parts`. This product keeps its columns in the
exposes, so splitting those too gives each expose a file of its own for the
columns:

```console
$ fluid split contract.fluid.yaml --parts builds,exposes,schema --dry-run
Would create 5 fragments:
   fragments/builds/customer_360_pipeline.yaml
   fragments/exposes/customer_360_master.yaml
   fragments/schemas/customer_360_master.yaml
   fragments/exposes/high_value_customers.yaml
   fragments/schemas/high_value_customers.yaml
```

## Arguments and options

| Argument / option | Default | Description |
|---|---|---|
| `CONTRACT` | required | The flat contract to split, YAML or JSON. |
| `--out`, `-o` `DIR` | the contract's directory | Directory to write the root and the fragment files into. |
| `--parts` `PART[,PART...]` | `sovereignty,accessPolicy,builds,exposes` | Comma-separated parts to move to files of their own; see [What gets split](#what-gets-split). |
| `--dry-run` | off | List the fragment files that would be written, and write nothing. |

## What gets split

| Part | What moves | Written to |
|---|---|---|
| `sovereignty` | the section | `fragments/sovereignty.yaml` |
| `accessPolicy` | the section | `fragments/access-policy.yaml` |
| `builds` | each `builds[]` entry | `fragments/builds/<slug of id>.yaml` |
| `exposes` | each `exposes[]` entry | `fragments/exposes/<slug of exposeId>.yaml` |
| `sql` | a build's `properties.sql` | `sql/<build id>.sql`, or `.py`, `.scala` or `.r` by the build's language |
| `quality` | an expose's `contract.quality` | `fragments/quality/<exposeId>.yaml` |
| `schema` | an expose's `contract.schema` | `fragments/schemas/<exposeId>.yaml` |
| `extensions` | each extension block | `fragments/extensions/<name>.yaml` |
| `extensions.<name>` | that one extension block | `fragments/extensions/<name>.yaml` |
| `description` | the description texts | `docs/<part>.md` |

The first four are the default (`--help` lists them as the default). A name
that is not a part is refused, and the message lists the parts:

```console
$ fluid split contract.fluid.yaml --parts nope
❌ unknown part 'nope'; the parts are sovereignty, accessPolicy, builds, exposes, sql, quality, schema, extensions, description and extensions.<name>
```

Only parts that exist and are not empty are split. Everything else stays
inline in the root, including `metadata`, `consumes`, `lifecycle` and any
other top-level key. Each pointer is written as `./fragments/...`, relative
to the root.

**A part inside another** is referenced from the file it ends up in. With
`--parts builds,exposes,sql,schema`, the build fragment holds the SQL as a
ref, and the expose fragment holds its columns as one:

```yaml
# fragments/builds/summarise.yaml
id: summarise
pattern: embedded-logic
engine: sql
properties:
  sql: {$ref: ../../sql/summarise.sql}
```

```yaml
# fragments/exposes/orders_summary.yaml
exposeId: orders_summary
...
contract:
  schema:
    $ref: ../schemas/orders_summary.yaml
```

**A part that is already a `$ref` is left alone**, so a second run changes
nothing:

```console
$ fluid split contract.fluid.yaml
ℹ Nothing to split — contract has no sections that benefit from fragments.
```

**File names.** The slug of an id replaces every character other than an
ASCII letter, digit, `_` or `-` with `-`, collapses repeated `-`, trims `-`
from both ends, and lowercases the result: `Orders (EU)` becomes
`orders-eu`. A build or expose with no id is written as
`unnamed-<n>.yaml`, where `<n>` is its position in the list. A slug longer
than 100 characters is cut and ends in 8 hex digits of a hash of the whole
id, so two long ids that start alike keep names of their own and a file
system takes the name. A 300-character id gives:

```console
$ fluid split long.fluid.yaml --dry-run
Would create 2 fragments:
   fragments/builds/summarise.yaml
   fragments/exposes/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-9835fa6b.yaml
```

Ids that differ only in case or punctuation do not collide. Two exposes with
`exposeId: customer_360_master` and `exposeId: Customer_360_Master` are
written to `customer_360_master.yaml` and `customer_360_master-2.yaml`: a
file that exists, or that another part is about to write, is never written
over, and the part gets the next free name (`-2`, `-3`).

## What it writes

- **Without `--out`**, the fragments go next to the contract, and the contract
  itself is rewritten with the root. The root is not re-dumped: every byte
  outside a moved part is kept, each part takes its own text, comments and
  block scalars to its fragment, and a JSON root stays JSON (its fragments
  are YAML files). A CRLF root keeps its line ends. A comment on the last line
  of a moved block keeps its CR, a keep-chomped block scalar (`|+`, `>+`)
  keeps its trailing blank lines, and a comment on a block scalar's header line
  stays beside its `$ref`.
- **With `--out DIR`**, the root (same file name as the input) and the
  fragment files are written under `DIR`, and the input is left untouched.
  Nothing else is copied: `data/`, `overlays/` and other files stay where
  they were. Overlays are only found next to the root, so copy `overlays/`
  into `DIR` if the product has any. A relative `$ref` the root already holds
  is resolved from `DIR` once the root has moved, so it must still name a
  file inside the ref root from there. If it does not, the split is refused
  with the ref error (`❌ Split not written: $ref '../../shared/policy.yaml' ... escapes the ref root`)
  and nothing is written.
- **With `--dry-run`**, it prints `Would create <n> fragments:` and the
  paths, and writes nothing. It refuses what the real run would refuse. It
  does not mention the root rewrite.
- **It never writes over another file.** `--out DIR` writes the root to
  `DIR/<contract file name>`. If that file exists and is not the contract being
  split, the split is refused, the dry run included:

  ```console
  $ fluid split flat.fluid.yaml --out o2
  ❌ Split not written: o2/flat.fluid.yaml already exists; split writes over no file but the contract it splits in place. Move it away, or choose another --out
  ```

  A second split into the same `--out` is refused too, because it would only
  add `-2` copies and leave the first run's fragments unreferenced:

  ```console
  $ fluid split flat.fluid.yaml --out o1
  ❌ Split not written: o1/flat.fluid.yaml already holds this contract (it composes to the same document); split writes over no file. To split that one, run: fluid split o1/flat.fluid.yaml
  ```

  The one file `--out` may replace is a byte-for-byte copy of the contract
  that is the only name of its file (no hard link to another file), because
  nothing is lost. It writes no file through a symlink: a symlinked root, or a
  symlinked directory on the way to a fragment, is refused.
- **It composes before it writes.** Split reads the contract as every command
  does, so a contract that does not compose here is not split at all. A ref
  that needs a wider ref root that is not set is such a case:

  ```console
  $ fluid split contract.fluid.yaml
  ❌ Split not written: the contract does not compose here, so its split could not be checked: $ref '../../shared/policy.yaml' at JSON pointer '/exposes/0/policy' in /work/repo/products/orders/contract.fluid.yaml escapes the ref root ...
  ```

  Set the ref root as for any other command, for example
  `FLUID_REF_ROOT=../.. fluid split contract.fluid.yaml`, or declare `ref_root`
  in `fluid.workspace.yaml`; see
  [the ref root](../concepts/contract-refs.md#widening-the-root-for-a-monorepo).
- **A refused split leaves the tree as it was.** Before it ends, split composes
  the result and compares it with the original. If the two differ, or a write
  fails, it takes back every file it wrote, restores the root's old text, and
  removes every directory it made, `--out` included. An empty `fragments/`
  would change what other commands do, so none is left. An interrupt (Ctrl-C)
  halfway through the writes is taken back too. A read-only root is refused like
  any failed write, with exit `1`:

  ```console
  $ fluid split ro.fluid.yaml --parts builds
  ❌ Split not written: [Errno 13] Permission denied: 'ro.fluid.yaml'; nothing was changed
  ```

  So is a JSON root that holds a character with no UTF-8 form.

`fluid split` writes its messages to stderr.

### Relative `$ref` in a part that moves

A relative `$ref` inside a part names a file from the place the part sits in.
When the part moves into `fragments/`, the ref is rewritten to name the same
file from the fragment. A contract with a policy kept outside the product:

```yaml
# products/orders/contract.fluid.yaml, before
exposes:
  - exposeId: orders_summary
    policy:
      $ref: ../../shared/policy.yaml
```

```yaml
# products/orders/fragments/exposes/orders_summary.yaml, after
exposeId: orders_summary
...
policy:
  $ref: ../../../../shared/policy.yaml
```

A `#/pointer` is kept, and a URL, an absolute path and a same-document
pointer are left as written. This is what makes a split in two passes work:
`--parts sql`, then `--parts builds`.

### YAML aliases and merge keys

A root with YAML aliases (`&anchor`, `*alias`, `<<: *defaults`) is split as
data. The aliases and merges are expanded where they are used, and the command
says the comments were not kept:

```console
$ fluid split contract.fluid.yaml --parts sql --out out1
✅ Split into 2 fragments:
   sql/second.sql
   sql/summarise.sql

   Root contract updated with $ref pointers: out1/contract.fluid.yaml
   ℹ Comments in the root were not kept: the contract uses YAML aliases.
   Run fluid bundle to see the resolved output.
```

A part in a container that an alias or `<<` shares is split from its own
place. Two builds that merge the same defaults, each with its own SQL, give
each build a file of its own (`sql/summarise.sql`, `sql/second.sql`). In
0.25.0 this case failed with `write() argument must be str, not dict` and left
an empty file.

## Exit codes

| Code | When |
|---|---|
| `0` | Split written, dry run listed, or nothing to split. |
| `1` | The contract could not be parsed (`❌ Failed to load contract: ...`); a part name that is not a part; a split that is refused (`❌ Split not written: ...`), including a failed write. |
| `2` | The contract file does not exist (`❌ Contract file not found: ...`). |

## Hazards

Commit before you split, and check with `fluid validate` afterwards. Split
checks its own work, but it reads the contract as it is, and cannot know
what you meant.

**Data paths do not move with `--out`.** Relative paths in the contract,
such as SQL reading `data/orders.csv` or a `binding.location.path`, are
resolved from the root contract's directory. A root written to another
directory with `--out` looks for them there.

**Fragments are named after ids.** To re-split a product by new rules,
flatten it first, remove the old fragments, then split. Hand-named fragments
get new names, and fragments shared from outside the product (a monorepo's
`shared/` directory) are inlined into this product, so restore those `$ref`s
by hand.

```bash
fluid bundle contract.fluid.yaml --out contract.fluid.yaml
rm -r fragments
fluid split contract.fluid.yaml
```

## `.fluid/`: what to commit

`fluid init` writes a `.gitignore` block that links to this section. The
block, and where each file lives:

| File | Written by | Commit it? |
|---|---|---|
| `fragments/`, `overlays/`, `contract.fluid.yaml` | you, `fluid split`, `fluid forge` | Yes. This is the product. |
| `<workspace>/.fluid/init-receipt.json` | `fluid init` | No (in the block). |
| `<workspace>/.fluid/logs/` | the CLI | No (in the block). |
| `<workspace>/.fluid/team-memory.yaml` | `fluid init`, and `fluid forge` when it is missing | *On forge-cli `main`, not yet in a release ([forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881)).* Not written on `main`. Yes. Team conventions shared with the AI copilot. |
| `<workspace>/.fluid/skills.yaml` | the industry picker in interactive `fluid init` | Yes. The industry reference pack, shared by the team. |
| `<product>/.fluid/forge-receipt.json` | `fluid forge`, `fluid init` | No. |
| `<product>/.fluid/copilot-memory.json` | the AI copilot | *On forge-cli `main`, not yet in a release ([forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881)).* Not written on `main`. No. |
| `<product>/.fluid/debezium/`, `<product>/.fluid/meltano/` | the embedded Debezium Server and Meltano runners, on each run | No (in the block since [forge-cli #722](https://github.com/Agenticstiger/forge-cli/pull/722)). Regenerated each run. Neither holds a credential the run resolved: Debezium Server gets those through its environment, and a Singer tap or target reads its config from a private temporary directory. |
| `<product>/.fluid/ci-state.json` | `fluid forge` when it scaffolds CI, for example `fluid forge --ci <provider>` | Yes. Records the inputs that produced the committed CI files. Files from `fluid generate ci` have no `ci-state.json` record. |
| `runtime/` | build outputs such as bundles, plans and apply reports | No (in the block). |
| `contract.bundled.fluid.yaml` | `fluid bundle` and `fluid ship` before 0.26.0, on a fragment layout | No. Delete it: it is a stale copy of the contract or, from `fluid ship`, a tarball. |

The rules in the generated block are:

```text
.fluid/init-receipt.json
.fluid/forge-receipt.json
.fluid/copilot-memory.json
.fluid/logs/
**/.fluid/debezium/
**/.fluid/meltano/
runtime/
```

The two `**/` lines come with [forge-cli #722](https://github.com/Agenticstiger/forge-cli/pull/722) and match in every product directory. A
workspace whose `.gitignore` already has the block keeps its old copy: add the two
lines yourself, and check that no `application.properties`, `tap_config.json` or
`target_config.json` under those directories was committed. Earlier releases wrote the
resolved password into them, so rotate any credential you find there.

As of 0.18.1, the `.fluid/...` lines match only the `.fluid/` directory at
the workspace root, because a gitignore pattern with a `/` in the middle is
anchored to the `.gitignore` file's directory. When a product sits in its
own directory, as `fluid init --quickstart` lays it out
(`customer-360/.fluid/forge-receipt.json`), its receipt and copilot memory
are not ignored. Add `**/` patterns yourself:

```text
**/.fluid/forge-receipt.json
**/.fluid/copilot-memory.json
```

## See also

- [Contract fragments](../concepts/fragments.md): why and how to work with the layout
- [`fluid bundle`](./bundle.md): the inverse operation
- [Environments and overlays](../concepts/environments-and-overlays.md): overlays stay beside the root and apply after resolution
- [Composing a contract with `$ref`](../concepts/contract-refs.md): how refs are resolved, and the ref root

::: tip About the examples
Output on this page was produced with forge-cli 0.26.0 on the quickstart
`customer-360` product and on small products made for this page. The fixes
described here for `--out`, relative refs, aliases and refused splits are in 0.26.0
([forge-cli #765](https://github.com/Agenticstiger/forge-cli/pull/765));
`--parts` and the comment-keeping root are in 0.25.0
([#760](https://github.com/Agenticstiger/forge-cli/pull/760)). Long temporary paths are
shortened to `/work`, and long lines are re-wrapped.
:::
