---
title: Contract fragments
description: Write one data product as a root contract plus fragment files — why you would, the layout fluid split writes, which commands read it, and how environments, CI, digests and catalogs see it.
---

# Contract fragments

A data product does not have to live in one file. You can write it as a
**root contract** that points at **fragment files** with `$ref`. `fluid validate`, `plan`, `apply` and the
other commands in [the table below](#which-commands-read-a-fragment-root)
resolve the refs before they work, so the engine sees one document; only the
authoring is split.

This page is about working with that layout. How a single `$ref` is read,
and which files it may name, is on
[Composing a contract with `$ref`](./contract-refs.md).

::: tip "Fragment" on this page
Here a fragment is a YAML file under `fragments/` that a root contract pulls
in with `$ref`. It is not the `#/...` part of a ref (a JSON pointer), not the
files a [tgz bundle](../cli/bundle.md#tgz-canonical-production-format) extracts
into `sources/`, not the multi-file layout the Bitol ODPS exporter writes, and
not the per-domain prompt fragments the AI copilot loads.
:::

## Example: split the quickstart product

Start from the product `fluid init --quickstart` scaffolds, with a
`sovereignty` block and an `accessPolicy` block added to the root (any
block you add becomes one more fragment, so your file counts and digests
will differ from the ones shown). Preview the split first:

```console
$ cd customer-360
$ fluid split contract.fluid.yaml --dry-run
Would create 5 fragments:
   fragments/sovereignty.yaml
   fragments/access-policy.yaml
   fragments/builds/customer_360_pipeline.yaml
   fragments/exposes/customer_360_master.yaml
   fragments/exposes/high_value_customers.yaml
```

Commit, then split:

```console
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
```

```text
customer-360/
├── .fluid/                      # forge-receipt.json, untouched by split
├── README.md                    # untouched by split
├── contract.fluid.yaml          # the root, rewritten in place
├── data/
│   ├── customers.csv
│   ├── interactions.csv
│   └── orders.csv
└── fragments/
    ├── access-policy.yaml
    ├── sovereignty.yaml
    ├── builds/
    │   └── customer_360_pipeline.yaml
    └── exposes/
        ├── customer_360_master.yaml
        └── high_value_customers.yaml
```

The root keeps identity, metadata, `consumes` and lifecycle inline, and
points at the rest:

```yaml
# contract.fluid.yaml (excerpt)
sovereignty:
  $ref: ./fragments/sovereignty.yaml
accessPolicy:
  $ref: ./fragments/access-policy.yaml
consumes:
- productId: bronze.customer.raw_customers_v1
  exposeId: raw_customer_data
  purpose: Customer master data from CRM
  ...
builds:
- $ref: ./fragments/builds/customer_360_pipeline.yaml
exposes:
- $ref: ./fragments/exposes/customer_360_master.yaml
- $ref: ./fragments/exposes/high_value_customers.yaml
```

Nothing else changes. The same commands work on the root:

```console
$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.006s
```

`fluid status` reports the layout. It counts `*.yaml` files under
`fragments/` (and overlays under `overlays/`, when there are any):

```text
│    Authoring       fragment-first (5 fragments)                              │
```

A product with no `fragments/` directory, or one holding no `*.yaml` file,
is reported as `flat`.

## Why split a contract

**Ownership.** Each fragment is a file, so each can have its own owner and
reviewers. On GitHub, a `CODEOWNERS` file can route governance changes to
the governance team and leave builds to the data engineers:

```text
# .github/CODEOWNERS
/customer-360/fragments/sovereignty.yaml     @example-org/governance
/customer-360/fragments/access-policy.yaml   @example-org/security
/customer-360/fragments/builds/              @example-org/data-engineering
/customer-360/fragments/exposes/             @example-org/platform
```

**Review.** A change to one expose is a diff in one small file, not a hunk in
the middle of a long contract.

**Reuse.** Several products can point at one shared fragment, such as an EU
sovereignty block. Since 0.18.0 a `$ref` may only name files inside the
contract's own directory tree, so a monorepo widens that tree with
`FLUID_REF_ROOT` for the command that needs it:

```text
repo/
├── shared/
│   └── sovereignty-eu.yaml
└── products/
    └── customer-360/
        ├── contract.fluid.yaml     # sovereignty: {$ref: ../../shared/sovereignty-eu.yaml}
        └── fragments/...
```

```console
$ cd repo
$ FLUID_REF_ROOT=. fluid validate products/customer-360/contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.005s
```

Without `FLUID_REF_ROOT` the same command fails with `escapes the ref root`.
The rules, and why to set the variable per command rather than export it, are
in [Widening the root for a monorepo](./contract-refs.md#widening-the-root-for-a-monorepo).

A small product with one build and one expose gains little from splitting.

## The layout

`fluid split` moves four sections into files and leaves everything else
inline:

| Section in the flat contract | Fragment file it becomes |
|---|---|
| `sovereignty` | `fragments/sovereignty.yaml` |
| `accessPolicy` | `fragments/access-policy.yaml` |
| each `builds[]` item | `fragments/builds/<build id>.yaml` |
| each `exposes[]` item | `fragments/exposes/<exposeId>.yaml` |

File names come from the ids, lowercased, with characters other than
letters, digits, `_` and `-` replaced by `-`. The exact rules and hazards are
on the [`fluid split`](../cli/split.md) reference.

The layout is a convention, not a requirement. You can write fragments by
hand, name them as you like, and point at any object in a file with a JSON
pointer (`parts/policy.yaml#/gold`). The loader does not care where a
fragment lives inside the ref root. These CLI behaviours, among others, look for a
directory called `fragments/` next to the root contract:

- `fluid status` reports `fragment-first` only when it finds one.
- [`fluid bundle`](../cli/bundle.md) without `--out` writes
  `contract.bundled.fluid.yaml` instead of printing to stdout.
- `fluid forge` keeps a product in the fragment layout when it finds one
  (see [Projects `fluid forge` writes](#projects-fluid-forge-writes)).

## The round trip: split, edit, bundle

[`fluid bundle`](../cli/bundle.md) is the inverse of `fluid split`. It
resolves every ref and writes the single document:

```console
$ fluid bundle contract.fluid.yaml --out runtime/contract.bundled.yaml
...
✅ Bundled contract written to /work/customer-360/runtime/contract.bundled.yaml
```

For the product above, bundling the split layout gives back a document equal
to the original flat contract. YAML comments are not part of it:
`fluid split` rewrites the root with a YAML serializer, so comments in the
root are lost.

Day to day you do not need the bundle. Edit the fragment, then run
`fluid validate`, `fluid plan` or `fluid apply` on the root. Use `fluid bundle`
to see what the engine sees, to hand the contract to something outside the
CLI, or to freeze it for CI.

Errors in a fragment are reported against the resolved document, not the
fragment file:

```console
$ fluid validate contract.fluid.yaml
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
...
 1. exposes[1].binding.format: 'parquett' is not one of ['bigquery_table',
...
```

`exposes[1]` is the second entry in the root's `exposes:` list, here
`fragments/exposes/high_value_customers.yaml`.

::: warning Split once
`fluid split` expects a flat contract. Running it on a root that is already
split overwrites `fragments/sovereignty.yaml` and
`fragments/access-policy.yaml` with a `$ref` that points nowhere, so their
content is lost and the product no longer loads. To re-split, bundle to a flat file first. Details:
[`fluid split` hazards](../cli/split.md#hazards).
:::

## Projects `fluid forge` writes

The AI copilot's default path (`fluid forge` without `--agent-loop`,
`--blank` or `--template`) picks a layout for the contract it generates:

1. `--fragments` writes the fragment layout; `--no-fragments` writes one file.
   The two flags cannot be combined.
2. Otherwise, if the target directory already has a `fragments/` directory,
   it keeps the fragment layout.
3. Otherwise it splits the contract when it has two or more builds, two or
   more exposes, or a `sovereignty` or `accessPolicy` block, and reports
   `Layout: Fragment-first (modular)`.

So a forged product can arrive as a root plus `fragments/` without you
running `fluid split`. As of 0.18.1, the other forge paths always write a
single `contract.fluid.yaml` and ignore `--fragments`, and neither flag is
listed in `fluid forge --help`. After a fragment-layout forge, the next-steps
panel suggests `fluid bundle --check`; that flag does not exist in 0.18.1.

## Which commands read a fragment root

Measured on CLI 0.18.1 with the product above, against the same product in
flat form:

| Command | Given the fragment root |
|---|---|
| `fluid validate`, `plan`, `apply`, `test`, `verify`, `diff` | Resolves the refs. Same result as the flat file. |
| `fluid contract-tests`, `policy check`, `viz-graph` | Resolves the refs. Same result as the flat file. |
| `fluid odcs export`, `odps-bitol export` | Resolves the refs. Byte-identical output to the flat file. |
| `fluid publish` | Resolves the refs (measured with `--dry-run`). The payload is the resolved document. |
| `fluid bundle` | Resolves the refs. This is what it is for. |
| `fluid generate artifacts` | **Fails** without `--env` (see below). Works with `--env`, or when given a tgz bundle. |
| `fluid contract digest` | Hashes the root as written, without resolving refs (see [Digests](#digests)). |
| `fluid split` | Treats the refs as content. Do not run it on a root. |

As of 0.18.1, `fluid generate artifacts` reads the root without resolving it
unless `--env` is given, and fails:

```console
$ fluid generate artifacts contract.fluid.yaml --out runtime/artifacts
...
❌ Provider error: FLUID expose has no usable name — Bitol ODPS v1.0.0
OutputPort requires a stable port name. Set expose.exposeId, expose.id, or
expose.name.
```

Pass the environment (`--env dev` uses the base contract when there is no
dev overlay) or the stage-1 bundle:

```bash
fluid generate artifacts contract.fluid.yaml --env dev --out runtime/artifacts
fluid generate artifacts runtime/bundle.tgz --out dist/artifacts
```

Tools that read the contract file directly, without the CLI's loader, see the
`$ref` nodes too. `fluid mcp serve`'s authoring tools that take a
`contract_path` read the file with a plain YAML parser in 0.18.1. Give such a
tool the bundled file.

## Environments: overlays apply after resolution

An overlay (`overlays/<env>.yaml` next to the root) is merged into the
**resolved** document, so it can change any field, including fields that live
in a fragment. This overlay moves the first expose, which is defined in
`fragments/exposes/customer_360_master.yaml`:

```yaml
# overlays/prod.yaml
exposes:
  - binding:
      location:
        path: output/prod/customer_360.parquet
```

```console
$ fluid bundle contract.fluid.yaml --env prod --out runtime/prod.yaml
...
overlay_applied
✅ Bundled contract written to /work/customer-360/runtime/prod.yaml
$ grep 'path: output' runtime/prod.yaml
      path: output/prod/customer_360.parquet
      path: output/high_value_customers.parquet
```

A list in an overlay patches the resolved list by position, so `exposes[0]`
in the overlay is the first `$ref` in the root's `exposes:` list. Reordering
the refs in the root changes which expose an overlay patches. The merge rules
are on [Per-environment overlays](../recipes/per-environment-overlays.md).

Keep two things in mind:

- **Overlays are not ref-resolved.** Do not put a `$ref` in an overlay. As of
  0.18.1, when an overlay contains one, `fluid validate`, `fluid plan` and
  `fluid apply` drop the **whole** overlay without an error: `plan --env prod`
  logs `overlay_applied` and then plans the base contract. `fluid bundle
  --env` keeps the overlay but leaves its `$ref` in the output as a literal
  key. Write the overlay's values inline.
- **Overlays stay next to the root.** They are found beside the root contract,
  so `fluid split --out <dir>` writes a root into `<dir>` that has no
  overlays. Copy `overlays/` across yourself.

## In CI: bundle once, then pass the bundle

Resolve the fragments and apply the environment once, in the first stage, and
hand the tgz to every later stage. Later stages then work from one frozen,
content-addressed document instead of re-reading the fragments:

```console
$ fluid bundle contract.fluid.yaml --env prod --format tgz --out runtime/bundle.tgz
...
✅ Bundle written to /work/customer-360/runtime/bundle.tgz
   digest: sha256:98400a7caca4ca8ed6a6a30934d1d283394f515cc176cfae5423e6989805fccb
   env: prod (overlay: overlays/prod.yaml)
```

```bash
fluid validate runtime/bundle.tgz --env prod
fluid generate artifacts runtime/bundle.tgz --env prod --out dist/artifacts
fluid plan runtime/bundle.tgz --env prod --out runtime/plan.json
fluid apply runtime/plan.json --yes
```

The bundle records the source contract and the environment it was built for
in its `MANIFEST.json` (see [`fluid bundle`](../cli/bundle.md#manifest-json)).
That has two effects:

- **A bundle is never re-overlaid.** A stage asked for a different `--env`
  refuses it instead of silently using the wrong environment:

  ```console
  $ fluid plan runtime/bundle.tgz --env staging
  CLI command error
  ❌ bundle_env_mismatch  [ERR_BUNDLE_ENV_MISMATCH]
    bundle: /work/customer-360/runtime/bundle.tgz
    bundle_env: prod
    requested_env: staging
    hint: the bundle was built for env 'prod' but this stage was asked for env
  'staging'. A bundle is never re-overlaid; rebuild it with `fluid bundle
  <contract> --env staging --format tgz`, or pass the env it was built for.
  ```

  Pass the same `--env` or none. `fluid verify`, `fluid diff` and
  `fluid generate artifacts` refuse the mismatch the same way, `fluid test`
  fails with `contract_load_failed` naming `bundle_env_mismatch`, and
  `fluid validate` reports it as a `bundle-env` issue. Build one bundle per
  environment.
- **Relative paths still mean what they meant.** A relative
  `binding.location.path` in a bundled run is resolved against the source
  contract's directory, not the bundle's or the working directory's.
  `fluid apply /work/customer-360/runtime/bundle.tgz --env prod --yes`, run
  from another directory, wrote `/work/customer-360/output/prod/customer_360.parquet`.

### Breaking-change gates on a pull request

`fluid diff --baseline` compares two resolved documents, so moving content
between the root and its fragments is never reported as a change: a split
product against its own flat original prints `No changes detected.`

The baseline needs its fragments. A root copied out of its tree on its own,
for example with `git show main:customer-360/contract.fluid.yaml > /tmp/old.yaml`,
fails with `diff_failed` and `$ref target not found`. Check out the base
branch as a whole tree and pass an absolute path (a relative path containing
`..` is refused):

```bash
git worktree add /tmp/base origin/main
fluid diff contract.fluid.yaml --baseline /tmp/base/customer-360/contract.fluid.yaml
```

## Digests

There are two different digests, and they treat fragments differently.

**`bundleDigest` does not depend on the layout.** It is computed over the
resolved document, so the flat contract, the split layout, and the monorepo
layout with a shared sovereignty fragment above all give the same tgz digest
(`sha256:6db904…` for this product without an overlay).

**`fluid contract digest` hashes the file as parsed, without resolving refs.** It does not resolve
refs, so for a fragment root it hashes the `$ref` strings, not the fragments:

```console
$ fluid contract digest contract.fluid.yaml
sha256:5a756e619b4518a53896b11777724712f3e240efb4910da3a2cafacd26392710
$ sed -i.bak 's/type: INTEGER/type: BIGINT/' fragments/exposes/customer_360_master.yaml
$ fluid contract digest contract.fluid.yaml
sha256:5a756e619b4518a53896b11777724712f3e240efb4910da3a2cafacd26392710
```

A federation `upstreamDigest` pin is computed the same way from the upstream's
contract file. As of 0.18.1, a pin on an upstream written as fragments does
not change when the upstream edits a fragment, so the apply-time federation
check cannot see that change. Keep the contract of a product that others pin
flat. To get the digest of the resolved document, bundle it and digest the
bundle's YAML; for this product that equals the flat file's digest:

```console
$ fluid bundle contract.fluid.yaml --out runtime/contract.bundled.yaml
...
$ fluid contract digest runtime/contract.bundled.yaml
sha256:026f6cd88725229966983901f8d15c1bf6e335c742db2d8cab16eceb79233738
```

## Sharing a contract outside the CLI

Tools that read the contract file with a plain YAML or JSON parser do not
resolve `$ref`; give them the bundled document. From Python,
[`fluid_build.api.load_contract`](../advanced/contract-loading-api.md)
resolves the refs the way the CLI does.


- **Catalogs and the Command Center.** `fluid publish` resolves the refs and
  sends one document; fragment files are not published. The Command Center
  refuses contract text that contains a `$ref` to a file or a URL with
  `422 contract_ref_not_allowed`, so paste or upload the bundled file.
- **JSON Schema validators and IDE schema checks.** A fragment root is not a
  valid FLUID document on its own. The published schema does not allow `$ref`
  where a build or an expose is expected. Run against the 0.7.5 schema, the
  root above fails with errors such as
  `builds[0]: Additional properties are not allowed ('$ref' was unexpected)`
  and `exposes[0]: 'exposeId' is a required property`. The bundled document
  passes the same schema with none. Validate the output of `fluid bundle`.
- **Other tools that read the file directly** follow the same rule: give them the bundled file.

## Limits as of 0.18.1

- `fluid split` must be run once, on a flat YAML contract, with ids that stay
  distinct after lowercasing. See [`fluid split` hazards](../cli/split.md#hazards).
- `fluid generate artifacts` needs `--env` or a tgz for a fragment root.
- `fluid contract digest` and federation pins do not see fragment edits.
- An overlay that contains a `$ref` is dropped by validate, plan and apply.
- On a fragment layout, `fluid bundle --format tgz` without `--out` writes the
  tarball as `contract.bundled.fluid.yaml`; pass `--out`. See
  [`fluid bundle`](../cli/bundle.md#default-output-location).

## Prior art

Splitting one specification into files and bundling it back is a common
pattern; Redocly CLI's
[`split` and `bundle`](https://redocly.com/docs/cli/file-management) do the
same for OpenAPI documents.

## Related

- [Composing a contract with `$ref`](./contract-refs.md): how a ref is read, and the ref root
- [`fluid split`](../cli/split.md) and [`fluid bundle`](../cli/bundle.md): command references
- [Per-environment overlays](../recipes/per-environment-overlays.md)
- [Operating in CI](../advanced/operating-in-ci.md)
- [What is a contract?](./contract.md)

::: tip About the examples
Output on this page was produced with CLI 0.18.1 on the quickstart
`customer-360` product split into fragments. Long temporary paths are
shortened to `/work`, and long lines are re-wrapped.
:::
