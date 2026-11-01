---
title: Contract fragments
description: Write one data product as a root contract plus fragment files — why you would, the layout fluid split writes, which commands read it, and how environments, CI, digests and catalogs see it.
---

# Contract fragments

A data product does not have to live in one file. You can write it as a
**root contract** that points at **fragment files** with `$ref`. `fluid validate`, `plan`, `apply`, `bundle`,
`generate` and `docs` resolve the refs before they work, so the engine sees one
document; only the authoring is split. The other commands are listed
[below](#which-commands-read-a-fragment-root).

This page is about working with that layout. How a single `$ref` is read,
and which files it may name, is on
[Composing a contract with `$ref`](./contract-refs.md).

::: tip "Fragment" on this page
Here a fragment is a file that a root contract pulls in with `$ref`: usually a
YAML file under `fragments/`, or the text of a SQL or Markdown file. It is not
the `#/...` part of a ref (a JSON pointer), not the files a
[tgz bundle](../cli/bundle.md#tgz-canonical-production-format) extracts into
`sources/`, not the multi-file layout the Bitol ODPS exporter writes, and not
the per-domain prompt fragments the AI copilot loads.
:::

Fragments arrived in 0.25.0
([forge-cli #760](https://github.com/Agenticstiger/forge-cli/pull/760)), with
fixes to `fluid validate --fragment` ([#761](https://github.com/Agenticstiger/forge-cli/pull/761)),
`fluid bundle` ([#763](https://github.com/Agenticstiger/forge-cli/pull/763)),
`fluid docs` ([#764](https://github.com/Agenticstiger/forge-cli/pull/764)) and
`fluid split` ([#765](https://github.com/Agenticstiger/forge-cli/pull/765)) in 0.26.0.
`fluid split` and `$ref` to a file are older; what 0.25.0 added is listed at the
top of [Composing a contract with `$ref`](./contract-refs.md).

## Example: split the quickstart product

Start from the product `fluid init --quickstart` scaffolds. Preview the split
first:

```console
$ cd customer-360
$ fluid split contract.fluid.yaml --dry-run
Would create 3 fragments:
   fragments/builds/customer_360_pipeline.yaml
   fragments/exposes/customer_360_master.yaml
   fragments/exposes/high_value_customers.yaml
```

Commit, then split:

```console
$ fluid split contract.fluid.yaml
✅ Split into 3 fragments:
   fragments/builds/customer_360_pipeline.yaml
   fragments/exposes/customer_360_master.yaml
   fragments/exposes/high_value_customers.yaml

   Root contract updated with $ref pointers: contract.fluid.yaml
   Run fluid bundle to see the resolved output.
split_complete
```

```text
customer-360/
├── README.md                    # untouched by split
├── contract.fluid.yaml          # the root, rewritten in place
├── data/
│   ├── customers.csv
│   ├── interactions.csv
│   └── orders.csv
└── fragments/
    ├── builds/
    │   └── customer_360_pipeline.yaml
    └── exposes/
        ├── customer_360_master.yaml
        └── high_value_customers.yaml
```

The root keeps identity, metadata, `consumes` and lifecycle inline, **with
its comments**, and points at the rest:

```yaml
# contract.fluid.yaml (excerpt)
# FLUID Data Product Contract
# Docs: https://agenticstiger.github.io/forge_docs/concepts/contract.html
fluidVersion: 0.7.5
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
Validation completed in 0.003s
```

`fluid status` reports the layout. It counts `*.yaml` files under
`fragments/` (and overlays under `overlays/`, when there are any):

```text
│    Authoring       fragment-first (3 fragments)                              │
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
sovereignty block or a policy. A `$ref` may only name files inside the
contract's own directory tree (the ref root), so a monorepo widens that tree
once, in `fluid.workspace.yaml`:

```text
repo/
├── fluid.workspace.yaml            # ref_root: .
├── shared/
│   └── policy.yaml
└── products/
    └── orders/
        └── contract.fluid.yaml     # policy: {$ref: ../../shared/policy.yaml}
```

```console
$ fluid validate products/orders/contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.001s
```

Without the `ref_root` line the same command fails with `escapes the ref
root`. The rules, the environment variable and the Python argument, and why to
set the variable per command rather than export it, are in
[Widening the root for a monorepo](./contract-refs.md#widening-the-root-for-a-monorepo).

**Reuse inside a product.** A fragment can be a column, a list of quality
rules or a block of SQL. Keys written beside a `$ref` change a field of the
fragment without copying it; see
[Keys beside a `$ref`](./contract-refs.md#keys-beside-a-ref).

A small product with one build and one expose gains little from splitting.

## The layout

By default `fluid split` moves four sections into files and leaves everything
else inline. `--parts` chooses other parts:

| Part | What moves | Where it goes |
|---|---|---|
| `sovereignty` | the section | `fragments/sovereignty.yaml` |
| `accessPolicy` | the section | `fragments/access-policy.yaml` |
| `builds` | each `builds[]` entry | `fragments/builds/<build id>.yaml` |
| `exposes` | each `exposes[]` entry | `fragments/exposes/<exposeId>.yaml` |
| `sql` | a build's `properties.sql` | `sql/<build id>.sql` (`.py`, `.scala` or `.r` by its language) |
| `quality` | an expose's `contract.quality` | `fragments/quality/<exposeId>.yaml` |
| `schema` | an expose's `contract.schema` | `fragments/schemas/<exposeId>.yaml` |
| `extensions`, `extensions.<name>` | each extension block, or that one | `fragments/extensions/<name>.yaml` |
| `description` | the description texts | `docs/<part>.md` |

The first four are the default. A part inside another is referenced from the
file it ends up in: with `--parts builds,sql`, the build fragment holds
`sql: {$ref: ../../sql/<build id>.sql}`. File names come from the ids,
lowercased, with characters other than letters, digits, `_` and `-` replaced
by `-`. The exact rules, and what split refuses, are on the
[`fluid split`](../cli/split.md) reference.

The layout is a convention, not a requirement. You can write fragments by
hand, name them as you like, and point at any object in a file with a JSON
pointer (`parts/policy.yaml#/gold`). The loader does not care where a
fragment lives inside the ref root. Two CLI behaviours look for a directory
called `fragments/` next to the root contract:

- `fluid status` reports `fragment-first` only when it finds one.
- `fluid forge` keeps a product in the fragment layout when it finds one
  (see [Projects `fluid forge` writes](#projects-fluid-forge-writes)).

[`fluid bundle`](../cli/bundle.md) does not look for it: since 0.26.0 the
output goes to the same place with or without a `fragments/` directory.

## The round trip: split, edit, bundle

[`fluid bundle`](../cli/bundle.md) is the inverse of `fluid split`. It
resolves every ref and writes the single document:

```console
$ fluid bundle contract.fluid.yaml --out runtime/contract.bundled.yaml
...
✅ Bundled contract written to /work/customer-360/runtime/contract.bundled.yaml
```

Bundling the split layout gives back a document equal to the original flat
contract. YAML comments are not part of it, but `fluid split` keeps them: it
splices the moved parts out of the root instead of re-writing it, so every
byte outside a moved part stays, and each part takes its own comments to its
fragment. A root with YAML aliases is split as data, and the command says its
comments were not kept. The split is checked before it ends: `fluid split`
composes the result, compares it with the original, and takes back every file
it wrote if they differ.

Day to day you do not need the bundle. Edit the fragment, then run
`fluid validate`, `fluid plan` or `fluid apply` on the root. Use `fluid bundle`
to see what the engine sees, to hand the contract to something outside the
CLI, or to freeze it for CI.

An error in a fragment names the fragment file and the line, then the place in
the composed contract:

```console
$ fluid validate contract.fluid.yaml
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
...
 1. fragments/exposes/high_value_customers.yaml:17 (exposes[1].binding.format): 'parquett' is not one of ['bigquery_table',
...
```

`exposes[1]` is the second entry in the root's `exposes:` list. A value an
overlay set names the overlay file. Errors in the root contract read as they
always did.

::: tip Splitting twice is safe
`fluid split` leaves a part that is already a `$ref` alone, so a second run
changes nothing (`ℹ Nothing to split`). It writes over no file but the root it
splits in place, and it composes the contract before it writes anything: a
contract that does not compose (a ref that needs a wider ref root, unset) is
not split at all. Details, and what a refused split leaves behind, are on
[`fluid split`](../cli/split.md).
:::

### Check one fragment

Validate a fragment on its own, against the part of the schema it stands for:

```console
$ fluid validate --fragment expose fragments/exposes/high_value_customers.yaml
❌ Invalid expose fragment (1 error(s)) (schema v0.7.5)

Validation Errors:
==================
 1. fragments/exposes/high_value_customers.yaml:17 (binding.format): 'parquett' is not one of ['bigquery_table', ...
```

The kind is a `$defs` name of the schema (`expose`, `build`, `column`,
`sovereignty`, `accessPolicy`, ...), or `quality` or `schema` for an expose's
lists. The schema version comes from `--schema-version`, else from the nearest
`contract.fluid.yaml` above the file. It checks the schema only, not the rules
that need the whole contract. See [`fluid validate`](../cli/validate.md#validating-one-fragment).

## The authoring schema and the compiled contract

Two documents are called "the contract" once you split it:

- **The authored contract** is the root plus its fragments, with `{$ref: ...}`
  where a build, an expose or a block of SQL is kept elsewhere.
- **The compiled contract** is what composition makes of it: every fragment
  read, the `--env` overlay merged, every `$ref` and same-document pointer
  replaced. `fluid bundle` prints it.

Every command validates the compiled contract against the canonical schema,
`fluid_build/schemas/fluid-schema-<version>.json`. The canonical schema is
unchanged by fragments, and it is what Command Center generates its models from.

An editor checks the files people write, and a fragment root fails the canonical
schema: it does not allow a `$ref` where a build or an expose is expected.
Checked against the 0.7.6 canonical schema, the root of the quickstart product
above fails with errors such as
`builds[0]: Additional properties are not allowed ('$ref' was unexpected)` and
`exposes[0]: 'exposeId' is a required property`.

For editors, forge-cli ships the **authoring schema**,
`fluid_build/schemas/fluid-authoring-schema-0.7.6.json`. It is the 0.7.6
schema with `{$ref: ...}`, keys beside it included, accepted at every value
position, wrapped the way the OpenAPI 3.1 meta-schema admits a Reference
Object. A value that is not a `$ref` gets exactly the canonical checks and
messages. The same root passes it with no errors.

```bash
python -c "from fluid_build.schema_authoring import authoring_schema_path; print(authoring_schema_path('0.7.6'))"
```

prints the path of the file in your installation; point your editor's
JSON-schema association for fragment files at it. Only 0.7.6 has an authoring
variant. It is generated from the canonical schema (`python -m fluid_build.schema_authoring`)
and a test fails when it drifts, so do not edit it. It checks the shape of a
`$ref` (a file, optionally with a JSON pointer, or a same-document pointer),
not that the target exists or fits where it lands: for that, run
`fluid validate` on the root, or `fluid validate --fragment` on the file.

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
single `contract.fluid.yaml` and ignore `--fragments`. As of 0.26.0, neither flag is
listed in `fluid forge --help`, and after a fragment-layout forge the next-steps
panel suggests `fluid bundle --check`, a flag `fluid bundle` does not have.

## Which commands read a fragment root

Since 0.25.0 these read the same composed document: the contract's
fragments, then the overlay with its own refs resolved relative to the
overlay file, then same-document pointers.

| Command | Given the fragment root |
|---|---|
| `fluid validate`, `plan`, `apply`, `bundle` | Compose the contract. A split contract plans the same actions as the flat one. |
| `fluid generate artifacts`, `standard`, `ci`, `airflow` | Compose the contract, with or without `--env`. A split contract gets byte-identical artifacts to the flat one. |
| `fluid docs` | Composes each root contract it finds. |
| `fluid odcs export`, `odps-bitol export` | Compose the contract. Byte-identical output to the flat file. |
| `fluid publish` | Composes the contract (measured with `--dry-run`). The payload is the resolved document. |
| `fluid diff` | Compares composed documents, so moving content between the root and its fragments is no change. |
| MCP `validate_contract`, `score_contract_quality`, `enrich_contract_suggestions` (the `contract_path` form) | Compose the contract, with fragments confined to the contract's directory unless widened. |
| `fluid contract digest` | **Hashes the root as written**, without composing (see [Digests](#digests)). |
| `fluid status`, `stats`, `viz-graph`'s workspace view, the workspace product listing, the forge welcome scan, the copilot's contract tools and `forge --refine` | **Read the root as written**, so they do not see what fragments hold. |

A library caller gets the same document from `fluid_build.loader.load_contract`
(see the [Contract loading API](../advanced/contract-loading-api.md)). Tools
that read the contract file directly, with a plain YAML parser and no loader,
see the `$ref` nodes too. Give them the bundled file.

In 0.24.0 and earlier, `fluid generate artifacts` read a split root without
resolving it unless `--env` was given, and failed with `FLUID expose has no
usable name`. That is fixed in 0.25.0.

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

An overlay patches the *resolved* list, so its `exposes:` entries patch the
exposes the `$ref`s pulled in, not the `$ref` lines themselves.

*(since 0.21.0, [forge-cli #732](https://github.com/Agenticstiger/forge-cli/pull/732))*
In a contract whose `fluidVersion` is 0.7.6 or later, `builds`, `exposes` and
`consumes` are matched by identity — `builds[].id`, `exposes[].exposeId`, and
`consumes[]` by `productId` + `exposeId` — so reordering the refs in the root
no longer changes which expose an overlay patches. An overlay entry whose id
the base does not have is appended, and logged as `overlay_entry_added` naming
the ids the base does have, so a typo shows instead of silently adding an
expose. An entry that names no id, or an id named twice, fails the load.

Below 0.7.6, and in any contract whose base entries lack unique ids, these
lists still merge by position: `exposes[0]` in the overlay is the first `$ref`
in the root's `exposes:` list, and reordering the refs retargets the overlay.
The merge rules, the warnings and what `--strict` does with them are on
[Per-environment overlays](../recipes/per-environment-overlays.md).

Keep two things in mind:

- **Overlays are ref-resolved.** Since 0.25.0 an overlay may hold a `$ref`,
  and the ref resolves relative to the overlay file, inside the same ref
  root. Before, `fluid validate`, `fluid plan` and `fluid apply` dropped the
  whole overlay without an error when it held one. A `$ref` left anywhere in
  the base no longer drops an overlay either. An overlay that links outside the
  ref root is refused, and `--env` must name an environment, not a path.
  Same-document pointers in an overlay have [limits](./contract-refs.md#same-document-pointers).
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
   digest: sha256:e57915a0cc5171a20d9fcaed9acac1ba7f8e85bc196b28356b6d6c318574d94a
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

Pin `data-product-forge>=0.25.0` on the CI image if any contract uses text
refs, keys beside a `$ref`, pointers, refs in overlays or a workspace
`ref_root`.

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
resolved document, so the flat contract and its split layout give the same tgz
digest (`sha256:7e8e53…` for the quickstart product without an overlay).

**`fluid contract digest` hashes the file as parsed, without resolving refs.**
For a fragment root it hashes the `$ref` strings, not the fragments, so an
edit inside a fragment does not change it. The same holds for a federation
`upstreamDigest` pin, which is computed the same way from the upstream's
contract file: an upstream written as fragments does not change its pin when
it edits a fragment, so the apply-time federation check cannot see that
change. Keep the contract of a product that others pin flat. (`LoadedContract.digest`
in the library does cover the composed contract. Changing the CLI digest
would change existing pins, so it waits for a decision.) To get the digest of
the resolved document, bundle it and digest the bundle's YAML; for the
quickstart product that equals the flat file's digest:

```console
$ fluid bundle contract.fluid.yaml --out runtime/contract.bundled.yaml
...
$ fluid contract digest runtime/contract.bundled.yaml
sha256:d86a03af64f3ff55257bd0386d4c9a6664c1c429acc4fd8166a2e0f4be796b39
$ fluid contract digest ../customer-360-flat/contract.fluid.yaml
sha256:d86a03af64f3ff55257bd0386d4c9a6664c1c429acc4fd8166a2e0f4be796b39
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
  valid FLUID document under the canonical schema: it does not allow `$ref`
  where a build or an expose is expected. Use the
  [authoring schema](#the-authoring-schema-and-the-compiled-contract) for the
  files people write, or validate the output of `fluid bundle`.
- **Other tools that read the file directly** follow the same rule: give them the bundled file.

## Limits as of 0.26.0

- `fluid contract digest` and federation pins do not see fragment edits.
- `fluid status`, `stats`, the workspace views, the forge welcome scan, the
  copilot's contract tools and `forge --refine` read the root as written.
- A contract that embeds a document carrying its own `$ref` keys (a JSON
  Schema or OpenAPI fragment in `parameters` or an extension) fails to
  compose; keep such a payload as a string.
- `fluid split` splits parts it knows. See [`fluid split`](../cli/split.md)
  for what it refuses.

## Prior art

Splitting one specification into files and bundling it back is a common
pattern; Redocly CLI's
[`split` and `bundle`](https://redocly.com/docs/cli/file-management) do the
same for OpenAPI documents.

## Related

- [Composing a contract with `$ref`](./contract-refs.md): how a ref is read, and the ref root
- [`fluid split`](../cli/split.md) and [`fluid bundle`](../cli/bundle.md): command references
- [`fluid validate`](../cli/validate.md#validating-one-fragment): check one fragment
- [Per-environment overlays](../recipes/per-environment-overlays.md)
- [Operating in CI](../advanced/operating-in-ci.md)
- [What is a contract?](./contract.md)

::: tip About the examples
Output on this page was produced with forge-cli 0.26.0 on the quickstart
`customer-360` product split into fragments. Long temporary paths are
shortened to `/work`, and long lines are re-wrapped.
:::
