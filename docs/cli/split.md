---
title: fluid split
description: Split a flat contract into a root contract plus fragment files joined by $ref. The inverse of fluid bundle.
---

# `fluid split`

Split a flat contract into a root contract plus fragment files under
`fragments/`, joined by `$ref`. The inverse of [`fluid bundle`](./bundle.md).
Why you would, and how the rest of the CLI treats the result, is on
[Contract fragments](../concepts/fragments.md).

## Syntax

```bash
fluid split CONTRACT [--out DIR] [--dry-run]
```

## Example

```console
$ fluid split contract.fluid.yaml --dry-run
Would create 5 fragments:
   fragments/sovereignty.yaml
   fragments/access-policy.yaml
   fragments/builds/customer_360_pipeline.yaml
   fragments/exposes/customer_360_master.yaml
   fragments/exposes/high_value_customers.yaml

$ git commit -am "Before split"
$ fluid split contract.fluid.yaml
✅ Split into 5 fragments:
   fragments/access-policy.yaml
   fragments/builds/customer_360_pipeline.yaml
   fragments/exposes/customer_360_master.yaml
   fragments/exposes/high_value_customers.yaml
   fragments/sovereignty.yaml

   Root contract updated with $ref pointers: contract.fluid.yaml
   Run fluid bundle to see the resolved output.
split_complete

$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.5)
```

The root now holds pointers where the sections were:

```yaml
sovereignty:
  $ref: ./fragments/sovereignty.yaml
accessPolicy:
  $ref: ./fragments/access-policy.yaml
builds:
- $ref: ./fragments/builds/customer_360_pipeline.yaml
exposes:
- $ref: ./fragments/exposes/customer_360_master.yaml
- $ref: ./fragments/exposes/high_value_customers.yaml
```

## Arguments and options

| Argument / option | Default | Description |
|---|---|---|
| `CONTRACT` | required | The flat contract to split. YAML only in practice; see [Hazards](#hazards). |
| `--out`, `-o` `DIR` | the contract's directory | Directory to write the root and `fragments/` into. |
| `--dry-run` | off | List the fragment files that would be written, and write nothing. |

## What gets split

| Section | Written to | Header comment in the file |
|---|---|---|
| `sovereignty` | `fragments/sovereignty.yaml` | `# Data sovereignty rules.` |
| `accessPolicy` | `fragments/access-policy.yaml` | `# Access policy — defines who can read and write the data product.` |
| each `builds[]` item | `fragments/builds/<slug of id>.yaml` | `# Build: <id>` |
| each `exposes[]` item | `fragments/exposes/<slug of exposeId>.yaml` | `# Expose: <exposeId>` |

Only sections that exist and are not empty are split. Everything else stays
inline in the root, including `metadata`, `consumes`, `lifecycle` and any
other top-level key. Each pointer is written as `./fragments/...`, relative
to the root.

**File names.** The slug of an id replaces every character other than an
ASCII letter, digit, `_` or `-` with `-`, collapses repeated `-`, trims `-`
from both ends, and lowercases the result: `Orders (EU)` becomes
`orders-eu`. A build or expose with no id is written as
`unnamed-<n>.yaml`, where `<n>` is its position in the list.

## What it writes

- **Without `--out`**, the fragments go into `fragments/` next to the
  contract, and **the contract itself is overwritten** with the root. The
  root is re-serialised, so comments and formatting in it are lost.
- **With `--out DIR`**, the root (same file name as the input) and
  `fragments/` are written under `DIR`, and the input is left untouched.
  Nothing else is copied: `data/`, `overlays/` and other files stay where
  they were. Overlays are only found next to the root, so copy `overlays/`
  into `DIR` if the product has any.
- **Existing files are overwritten without asking**, both fragment files and
  the root.
- **With `--dry-run`**, it prints `Would create <n> fragments:` and the
  paths, and writes nothing. It does not mention the root rewrite.
- A contract with nothing to split is left alone:

  ```console
  $ fluid split contract.fluid.yaml
  ℹ Nothing to split — contract has no sections that benefit from fragments.
  ```

`fluid split` writes its messages to stderr.

## Exit codes

| Code | When |
|---|---|
| `0` | Split written, dry run listed, or nothing to split. |
| `1` | The contract could not be parsed (`❌ Failed to load contract: ...`). |
| `2` | The contract file does not exist (`❌ Contract file not found: ...`). |

## Hazards

As of 0.18.1, `fluid split` does not check what it is about to do. These
cases exit `0` and leave a broken or changed product behind. Commit before
you split, and check with `fluid validate` afterwards.

**Running it on a root that is already split destroys fragments.** Each
existing `{$ref: ...}` is treated as content. `fragments/sovereignty.yaml`
and `fragments/access-policy.yaml` are overwritten with a ref that resolves
to a file that does not exist, so the governance content in them is gone, and each build and expose ref
becomes `fragments/{builds,exposes}/unnamed-<n>.yaml` holding a ref that
resolves to the wrong directory:

```console
$ fluid split contract.fluid.yaml        # second run, on the root
✅ Split into 5 fragments:
   fragments/access-policy.yaml
   fragments/builds/unnamed-0.yaml
   fragments/exposes/unnamed-0.yaml
   fragments/exposes/unnamed-1.yaml
   fragments/sovereignty.yaml
...
$ cat fragments/sovereignty.yaml
# Data sovereignty rules.

$ref: ./fragments/sovereignty.yaml
$ fluid validate contract.fluid.yaml
❌ Validation error: contract_load_failed
   error: $ref target not found: ./fragments/sovereignty.yaml (resolved to
/work/customer-360/fragments/fragments/sovereignty.yaml)
   [ERR_CONTRACT_LOAD_FAILED]
```

Restore from git. To re-split a product, flatten it first, remove the old
fragments, then split:

```bash
fluid bundle contract.fluid.yaml --out contract.fluid.yaml
rm -r fragments
fluid split contract.fluid.yaml
```

Fragment files are named after the ids again, so hand-named fragments get
new names, and fragments shared from outside the product (a monorepo's
`shared/` directory) are inlined into this product. Restore those `$ref`s by
hand.

**Ids that differ only in case or punctuation collide.** Two exposes with
`exposeId: customer_360_master` and `exposeId: Customer_360_Master` both map
to `fragments/exposes/customer_360_master.yaml`. The second overwrites the
first, both refs point at it, and one expose is lost. `fluid validate` still
passes. Keep ids distinct after lowercasing.

**A JSON contract is rewritten as YAML under its `.json` name.**
`fluid split contract.fluid.json` writes YAML text into
`contract.fluid.json`, which then fails to load (`Failed to parse ...
Expecting value: line 1 column 1`). Convert the contract to YAML before
splitting.

**Data paths do not move with `--out`.** Relative paths in the contract,
such as SQL reading `data/orders.csv` or a `binding.location.path`, are
resolved from the root contract's directory. A root written to another
directory with `--out` looks for them there.

## `.fluid/`: what to commit

`fluid init` writes a `.gitignore` block that links to this section. The
block, and where each file lives:

| File | Written by | Commit it? |
|---|---|---|
| `fragments/`, `overlays/`, `contract.fluid.yaml` | you, `fluid split`, `fluid forge` | Yes. This is the product. |
| `<workspace>/.fluid/init-receipt.json` | `fluid init` | No (in the block). |
| `<workspace>/.fluid/logs/` | the CLI | No (in the block). |
| `<workspace>/.fluid/team-memory.yaml` | `fluid init`, and `fluid forge` when it is missing | Yes. Team conventions shared with the AI copilot. |
| `<workspace>/.fluid/skills.yaml` | the industry picker in interactive `fluid init` | Yes. The industry reference pack, shared by the team. |
| `<product>/.fluid/forge-receipt.json` | `fluid forge`, `fluid init` | No. |
| `<product>/.fluid/copilot-memory.json` | the AI copilot | No. |
| `<product>/.fluid/ci-state.json` | `fluid forge` when it scaffolds CI, for example `fluid forge --ci <provider>` | Yes. Records the inputs that produced the committed CI files. Files from `fluid generate ci` have no `ci-state.json` record. |
| `runtime/` | build outputs such as bundles, plans and apply reports | No (in the block). |
| `contract.bundled.fluid.yaml` | `fluid bundle` without `--out` on a fragment layout | No. A build output; regenerate it. |

The rules in the generated block are:

```text
.fluid/init-receipt.json
.fluid/forge-receipt.json
.fluid/copilot-memory.json
.fluid/logs/
runtime/
```

As of 0.18.1, the `.fluid/...` lines match only the `.fluid/` directory at
the workspace root, because a gitignore pattern with a `/` in the middle is
anchored to the `.gitignore` file's directory. When a product sits in its
own directory, as `fluid init --quickstart` lays it out
(`customer-360/.fluid/forge-receipt.json`), its receipt and copilot memory
are not ignored. Add `**/` patterns yourself:

```text
**/.fluid/forge-receipt.json
**/.fluid/copilot-memory.json
**/contract.bundled.fluid.yaml
```

## See also

- [Contract fragments](../concepts/fragments.md): why and how to work with the layout
- [`fluid bundle`](./bundle.md): the inverse operation
- [Environments and overlays](../concepts/environments-and-overlays.md): overlays stay beside the root and apply after resolution
- [Composing a contract with `$ref`](../concepts/contract-refs.md): how refs are resolved, and the ref root

::: tip About the examples
Output on this page was produced with CLI 0.18.1 on the quickstart
`customer-360` product split into fragments. Long temporary paths are
shortened to `/work`, and long lines are re-wrapped.
:::
