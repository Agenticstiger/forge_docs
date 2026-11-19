---
title: fluid bundle
description: Resolve a contract's $ref fragments and environment overlay into one document, or into a deterministic, env-bound tgz bundle for the pipeline.
---

# `fluid bundle`

Stage 1 of the 11-stage pipeline. Resolve every `$ref` in a contract, apply
an environment overlay, and write the result either as one YAML/JSON document
(to read, or to hand to another tool) or as a deterministic, content-addressed
tgz with a SHA-256 `MANIFEST.json` (the input to the later pipeline stages).
The inverse of [`fluid split`](./split.md); see
[Contract fragments](../concepts/fragments.md) for how the two fit together.

Renamed from `fluid compile` in `0.7.3`. The hidden `fluid compile` alias was removed; use `fluid bundle --format yaml` as the one-to-one replacement for legacy callers.

## Syntax

```bash
fluid bundle [CONTRACT] [--format yaml|json|tgz] [--out PATH] [--env ENV]
             [--sign [--sign-key REF]] [--attest]
```

## Examples

```bash
# Read the resolved contract
fluid bundle contract.fluid.yaml --out runtime/contract.bundled.yaml

# The same, for one environment
fluid bundle contract.fluid.yaml --env staging --out runtime/staging.yaml

# Stage 1 of a pipeline: one env-bound tgz per environment
fluid bundle contract.fluid.yaml --env prod --format tgz --out runtime/bundle.tgz

# Stage 1 with supply-chain evidence (GitHub Actions, keyless OIDC)
fluid bundle contract.fluid.yaml --env prod --format tgz --out runtime/bundle.tgz --sign --attest
```

## Arguments and options

### Input / output

| Option | Default | Description |
| --- | --- | --- |
| `CONTRACT` | `./contract.fluid.yaml` | The root contract. Optional: without it, `fluid bundle` uses `contract.fluid.yaml` in the current directory, and fails with `contract_required` when there is none. |
| `--out`, `-o` | `-` | Output path. `-` (the default) is stdout for `yaml` and `json`, and `<contract id>.fluid.bundle.tgz` beside the contract for `tgz`: see [Default output location](#default-output-location). |
| `--format`, `-f` | inferred | `yaml`, `json` or `tgz`. Without `--format`, an `--out` ending in `.tgz` or `.tar.gz` means `tgz`, one ending in `.json` means `json`, and anything else means `yaml`. |
| `--env`, `-e` | none | Environment overlay to merge after the refs are resolved. With `tgz`, recorded in the bundle; see [Environments](#environments). |

### Supply chain (opt-in, `--format tgz` only)

| Option | Description |
| --- | --- |
| `--sign` | Sigstore cosign sign the emitted tgz. Default is keyless OIDC (GitHub / GitLab / CircleCI / GCP WIF are detected by cosign). Writes `<bundle>.sig` and, in keyless mode, `<bundle>.pem` next to the tgz. Needs `cosign` on `PATH`. |
| `--sign-key PATH_OR_KMS_URI` | Use keyed cosign signing instead of keyless. Accepts a key file path or a KMS URI (`awskms://`, `gcpkms://`, `azurekms://`, `hashivault://`, `k8s://`, `pkcs11://`, `file://`). Needs `COSIGN_PASSWORD` for an encrypted local key. Ignored without `--sign`. For Bitbucket Pipelines, air-gapped and regulated environments without OIDC. |
| `--attest` | Write an in-toto v1 Statement with a SLSA Provenance v1 predicate next to the bundle as `<bundle>.intoto.jsonl`. Records the git commit SHA, CI run URL, bundle digest and builder identity. *On forge-cli `main`, not yet in a release ([forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985)).* The statement's subject is the sha256 of the bundle file; see [Signing and attestation](#signing-and-attestation). Works offline with a localhost builder and a random run id; full SLSA Level 2 needs a trusted build service. |

With `--format yaml` or `json`, `--sign` and `--attest` are ignored without a
warning: the command exits `0` and writes no `.sig` or `.intoto.jsonl`. CI
that expects a signature must use `--format tgz`.

## Default output location

Without `--out`, or with `--out -`, the output goes to the same place for
every contract, whether or not a `fragments/` directory sits beside it:

| Format | `--out` omitted or `-` |
|---|---|
| `yaml`, `json` | stdout |
| `tgz` | `<contract dir>/<contract id>.fluid.bundle.tgz` |

The command writes no file for `yaml` or `json`, so
`fluid bundle contract.fluid.yaml | ...` receives the document. Log lines go to stderr.

The tgz name is the contract `id` made filename-safe, for example
`gold.customer.analytics_360_v1.fluid.bundle.tgz`, and the command says so:

```console
$ fluid bundle contract.fluid.yaml --format tgz
ℹ️  --out not specified; defaulting to /work/customer-360/gold.customer.analytics_360_v1.fluid.bundle.tgz
   (derived from contract.id; override with --out <path>)
✅ Bundle written to /work/customer-360/gold.customer.analytics_360_v1.fluid.bundle.tgz
   digest: sha256:7e8e5318810f3359ee9958c2fd49a5dfe21b29a486b0d59f3119691831f8b3af
```

The default tgz path gets the same write check an explicit `--out` gets. A
symlink planted at `<contract id>.fluid.bundle.tgz` cannot point the write at a
forbidden path; it is refused, with exit `1`:

```console
$ ln -s /etc/fluid-test.tgz sales.orders_v1.fluid.bundle.tgz
$ fluid bundle contract.fluid.yaml --format tgz
❌ Access to system path forbidden: /private/etc/fluid-test.tgz  [ERR_FORBIDDEN_PATH_ACCESS]
```

::: warning Changed in 0.26.0
([forge-cli #763](https://github.com/Agenticstiger/forge-cli/pull/763))
In 0.25.0 and earlier, a `fragments/` directory beside the contract sent a
no-`--out` run to `contract.bundled.fluid.yaml`. `yaml` and `json` printed
nothing to stdout, and `--format tgz` wrote its gzip tarball under that
`.yaml` name, which the next stage read as YAML
(`'utf-8' codec can't decode byte 0x8b`) and `--sign` and `--attest` refused
(`signing_bundle_wrong_format`). `fluid ship` bundled that way on every run.

`fluid bundle` no longer writes `contract.bundled.fluid.yaml` on its own. A
script that bundled a split contract and then read that file must pass
`--out contract.bundled.fluid.yaml`. A `contract.bundled.fluid.yaml` that an
earlier `fluid ship` left beside a contract is a tarball, and one an earlier
`fluid bundle` left is a copy of the contract that may be stale. Delete either.
:::

## Output formats

### `yaml` / `json` (default)

One resolved contract document. Use it to read what the engine sees, or to
give the contract to a tool that does not understand `$ref`
(see [Sharing a contract outside the CLI](../concepts/fragments.md#sharing-a-contract-outside-the-cli)).

The document is the contract with:

- every `$ref` replaced by what it names: the value of a file, the text of a
  SQL or Markdown file, or the place a same-document pointer (`$ref: "#/..."`)
  names in the composed contract. Keys written beside a `$ref` are merged over
  the target, as [Composing a contract with `$ref`](../concepts/contract-refs.md#keys-beside-a-ref)
  describes. No `$ref` is left in the output;
- the `--env` overlay merged on top, with its own refs resolved relative to the
  overlay file.

Nothing else is changed. Value aliases (such as `binding.format: kafka`), a
legacy singular `build:` key and `{{ env.* }}` placeholders stay as authored;
`fluid validate` and `fluid plan` normalise and resolve those when they load
the contract. `fluid generate artifacts <contract> --env <env>` builds from
this same document.

On a contract with no refs and no `--env`, the output has the same content as the input (comments and formatting are not kept) and
the command says so on stderr:

```console
$ fluid bundle contract.fluid.yaml > /dev/null
ℹ️  Contract has no $ref pointers — already a single file.
   Use 'fluid split' first to break it into fragments,
   then 'fluid bundle' to reassemble.
```

When writing to stdout, log lines go to stderr so the document stays clean.

### `tgz` (canonical production format)

A deterministic, content-addressed archive:

```text
MANIFEST.json            SHA-256 of every other file, the bundle digest, and the source block
contract.resolved.yaml   the resolved contract, keys sorted
contract.resolved.json   the same, as JSON
sources/                 extracted inline sources, when there are any (see below)
sources/dbt/<build id>/  the dbt project of each dbt build (see below)
```

The archive holds the resolved document only. Your fragment files, their
names and boundaries are not kept: a flat contract and its split layout give
the same files and the same digest. The one thing it carries beyond the
resolved contract is the dbt project of each dbt build, described under
[The dbt project of a dbt build](#the-dbt-project-of-a-dbt-build).

**Extracted sources.** Inline SQL and OpenAPI are moved into `sources/` and
replaced by a `{"$source": "sources/..."}` pointer:

| Field | Extracted to |
|---|---|
| `builds[N].embeddedLogicPattern.sql` | `sources/sql/builds_<N>__<build id>.sql` |
| `exposes[N].view.sql` | `sources/sql/exposes_<N>__<expose id>__view.sql` |
| `exposes[N].openapi` | `sources/openapi/exposes_<N>__<expose id>.yaml` |

The expose segment comes from the expose's `id` or `name`, else
`expose<N>`; FLUID exposes carry `exposeId`, so in practice it is
`expose<N>`. As of 0.18.1, these three fields are not allowed by the 0.7.5
or 0.7.6 schema (embedded SQL lives in `builds[].properties.sql`, which is
not extracted). For a contract that passes `fluid validate`, `sources/` is
therefore absent and the tgz holds the three files above.

When `fluid validate` checks a bundle, OpenAPI documents in `sources/openapi/`
may only use same-document refs; see
[OpenAPI fragments inside a bundle](../concepts/contract-refs.md#openapi-fragments-inside-a-bundle).

#### The dbt project of a dbt build

*On forge-cli `main`, not yet in a release ([forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972)).*
`fluid bundle --format tgz` packs the dbt project of each dbt build under
`sources/dbt/<build id>/`, byte for byte, so that a model edited after the
plan was made cannot run unreviewed. In 0.32.0 and earlier the bundle holds no
dbt file, and a model edited between `fluid plan` and `fluid apply` runs as it
stands in the checkout.

The example below is a contract with one dbt build (`repository: ./dbt`) and
the project beside it: `dbt_project.yml`, `models/orders.sql` and a
`profiles.yml`. It ran on forge-cli `main`.

```console
$ fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
...
✅ Bundle written to /work/orders/runtime/bundle.tgz
   digest: sha256:c8e0d69396d694546601d6dfd9cc0be1b87ee6d5609b24a33092706005d78eed
   packet: sha256:b92783ba770db2b65e7934cb7a56330c7760fb2fb203afe877bf9026c491543f
   provenance: bundle.tgz.provenance.json
   dbt project: transform (2 files, sources/dbt/transform/)

$ tar -tzf runtime/bundle.tgz
MANIFEST.json
contract.resolved.json
contract.resolved.yaml
sources/
sources/dbt/
sources/dbt/transform/
sources/dbt/transform/dbt_project.yml
sources/dbt/transform/models/
sources/dbt/transform/models/orders.sql
```

`profiles.yml` stays out: it names connections and may hold a password.

**Which build, and where the project is.** A build binds a project when its
engine is `dbt` or `dbt-<adapter>`, it holds no inline SQL, no other
platform's engine runs it, and its `repository` is a path. The project is the
directory `repository` names (default `./`), resolved from the contract's
directory, inside the contract's workspace: where `fluid apply` runs it. A Git
`repository` is not packed, because its ref pins it. Such a build needs an `id`
that is a valid identifier, and two of them cannot share one.

**What is packed.** Every file is taken as it is on disk, with no newline or
Unicode change:

- the files in the project root that dbt reads: `dbt_project.yml`,
  `packages.yml`, `dependencies.yml`, `package-lock.yml`, `selectors.yml` and
  `.dbtignore`, when they exist;
- the regular files under the directories the `dbt_project.yml` path keys
  name, except those listed below: `model-paths`, `macro-paths`, `seed-paths`, `snapshot-paths`,
  `test-paths`, `analysis-paths`, `function-paths`, `docs-paths` and
  `asset-paths`. A key that is absent or `null` takes dbt's default (`models`,
  `macros`, `seeds`, `snapshots`, `tests`, `analyses` and `functions`;
  `docs-paths` and `asset-paths` default to none), and the older `source-paths`
  and `data-paths` count when the newer key is absent. A directory that does not
  exist is skipped, as dbt skips it.

**What is never packed.**

- `profiles.yml` and `profiles.yaml`, in any directory it reads, whatever the case.
- The directories dbt writes into: `target/`, `logs/`, `dbt_packages/` and
  `dbt_modules/` by default, or the ones `target-path`, `log-path`,
  `packages-install-path` and `modules-path` name. They sit outside every path
  key, so they are not read. One nested inside a directory dbt reads is refused,
  as the table below says.
- A file whose name starts with `.`, `#` or `~` (`.DS_Store`, an editor's
  `#orders.sql#`): dbt never reads such a name. `.dbtignore` in the project
  root is the one exception.

**What `fluid bundle` refuses.** A project it cannot bind as one tree fails
the whole command with `❌ Bundle tgz build failed: ...` and exit `1`. Most
refusals name the build: `build '<id>': ...`.

| Cause | What to do |
|---|---|
| A symbolic link where dbt reads. | Replace the link with the file. |
| A file dbt reads (`.sql`, `.py`, `.csv`, `.md`, `.yml` or `.yaml`) inside a hidden directory or `__pycache__` under a path key. | Move it out, or delete it if it is a stray copy. |
| An output directory inside a directory dbt reads. | Keep the output directories apart from the path keys' directories. |
| A path key that names a place outside the project, the project root, a hidden directory, or a path through a link. | Name a plain directory inside the project. |
| A path key or an output key written as Jinja (`{{ ... }}`). | Write the directory literally: `fluid bundle` does not render Jinja. |
| A directory that cannot be listed. | Make it readable. |
| A `dbt_project.yml` that is missing or unreadable, or a `repository` written as a template. | Check the project out beside the contract, or point `repository` at it. |
| A file over 64 MiB. | Load data that size as a table, not a dbt seed. |
| More than 128 MiB of dbt files, all builds together. | The same. |
| More than 10,000 entries in the bundle, files and directories counted. | Trim the project. |
| A file path too long for the bundle's tar format. | Shorten the build id, or the project's file and directory names. |

A hidden directory with a model in it, for example:

```console
$ fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
...
❌ Bundle tgz build failed: build 'transform': models/.old/a.sql is a file dbt reads inside a hidden or __pycache__ directory, which the bundle does not pack; move it out, or delete it if it is a stray copy
```

**Binding.** Each file is listed in the MANIFEST and sits under its digest, so
the same tree bundles to the same digest. `fluid plan <bundle>` records each
project's files in `plan.json` as `dbtProjects` (see
[What `plan.json` records](./plan.md#what-plan-json-records)), `fluid apply`
compares the checkout with the bundle's copy before anything runs, and the dbt
runner compares the directory again just before dbt starts. Plan from the
bundle, then change the project:

```console
$ fluid plan runtime/bundle.tgz --out runtime/plan.json
...
dbt project bound: transform (2 files, sha256:e73871e51224311be6a6eee84689d8412dbfc0a6a0992331a5cb83c7d033e35e)
...
$ echo "select 1 as id, 99.5 as amount" > dbt/models/orders.sql
$ echo "select 2 as id" > dbt/models/extra.sql
$ fluid apply runtime/plan.json --dry-run --yes
Loading pre-generated execution plan
Auto-discovered bundle for plan-binding: /work/orders/runtime/bundle.tgz
CLI command error
❌ apply_plan_digest_bundle_mismatch  [ERR_APPLY_PLAN_DIGEST_BUNDLE_MISMATCH]
  kind: bundle-mismatch
  error: the dbt project of build 'transform' at /work/orders/dbt differs from the copy /work/orders/runtime/bundle.tgz packs: changed models/orders.sql; added models/extra.sql. Re-run ``fluid bundle`` and ``fluid plan`` to bind the files as they are now, or restore them.
```

The refusal comes before a provider is touched, and `--dry-run` does not skip
it. [`fluid apply`](./apply.md#plan-binding) lists the other cases (a removed
file, a bundle made before this change) and the flag that skips the check.

Two limits. Installed packages are not bound: dbt reads whatever
`packages-install-path` holds, and `fluid apply` neither installs nor checks
it, so install them from `package-lock.yml` in the job that applies. And a plan
made from a contract file binds no dbt project, because there is no bundle to
take it from.

Run [`fluid generate dbt-tests`](./generate.md#fluid-generate-dbt-tests) before
`fluid bundle`, with `-o` naming a file inside the project (it writes
`./schema.yml` in the current directory by default), so the tests are packed
and bound with the models:

```bash
fluid generate dbt-tests contract.fluid.yaml -o dbt/models/schema.yml
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
```

`fluid validate <bundle>` reports one `info` finding per packed project, which
`--verbose` prints:

```console
$ fluid validate runtime/bundle.tgz --verbose
✅ Bundle pass: /work/orders/runtime/bundle.tgz
   digest: sha256:c8e0d69396d694546601d6dfd9cc0be1b87ee6d5609b24a33092706005d78eed
   issues: 1 total (0 error, 0 warning, 1 info)
   [info] dbt: sources/dbt/transform/: binds the dbt project of build 'transform' (2 files); fluid validate does not parse dbt's Jinja SQL. Run `dbt parse` on the project in CI
...
```

#### `MANIFEST.json`

```console
$ tar -xzOf runtime/bundle.tgz MANIFEST.json | python3 -m json.tool
{
    "contractId": "demo.orders_dbt",
    "digest": "sha256:c8e0d69396d694546601d6dfd9cc0be1b87ee6d5609b24a33092706005d78eed",
    "files": {
        "contract.resolved.json": "sha256:a1a7802eacbbcae28f5f4a62f318d29848be15c560bf4d0056bb95708c1dfcc3",
        "contract.resolved.yaml": "sha256:4ff5a848dedffe971620d542b13304befa59361e6365944475a449fa3575e6d3",
        "sources/dbt/transform/dbt_project.yml": "sha256:8d5d99087d75f8c1147d4e7195c15278e9b5f1d5fa8ba14dc46887b17c0af0b0",
        "sources/dbt/transform/models/orders.sql": "sha256:4e65c7c3c4bc6e8c6604aad92341c4f8a0dfb3a8c3c7ef8c4e741996140d1ee1"
    },
    "generator": "fluid bundle",
    "source": {
        "env": null
    },
    "version": "1.0"
}
```

This manifest came from forge-cli `main`. In 0.32.0 and earlier the `source`
block also held `contract` and `overlay` (for example
`"contract": "../contract.fluid.yaml"`), and a bundle holds no `sources/dbt/`.

The file itself is compact JSON with sorted keys.

| Field | Meaning |
|---|---|
| `files` | SHA-256 of each file in the archive except `MANIFEST.json`. |
| `digest` | The bundle digest (`bundleDigest` in `plan.json`): SHA-256 over the sorted `<path>:<file digest>` lines, one per file. |
| `source.contract` | 0.32.0 and earlier: the source contract, relative to the directory the bundle was written to. *On forge-cli `main`, not yet in a release ([forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985)),* the MANIFEST does not hold it: see [The provenance file](#the-provenance-file). Paths inside the MANIFEST of an older bundle are not read. |
| `source.env` | The `--env` the bundle was built with, or `null`. |
| `source.overlay` | 0.32.0 and earlier: the overlay file that was merged, relative to the contract's directory, or `null`. *On `main`,* it moved to the provenance file with `source.contract`. |
| `source.overlayWarnings` | *(since 0.22.0, [forge-cli #735](https://github.com/Agenticstiger/forge-cli/pull/735))* The overlay merge warnings `fluid validate --strict` fails on, one message each: a patch that landed on another entry. Present only when the merge raised one. |

The `source` block is outside the digest, so the digest names the resolved
contract alone: the same contract bundled into two directories keeps one
digest. The same holds for the manifest's integrity check: it recomputes the
digest from the files, so it does not cover `source`, and later stages read
`source.env` to refuse a mismatched `--env`. A cosign signature
(`--sign`) over the whole tgz covers it. *On forge-cli `main`, not yet in a release ([forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985)).* So does the
`packetDigest` that a plan records: see [The packet digest](#the-packet-digest).
You can recompute the digest from an extracted bundle:

```bash
mkdir bundle && tar -xzf runtime/bundle.tgz -C bundle && cd bundle
find . -type f ! -name MANIFEST.json | sed 's|^\./||' | LC_ALL=C sort | while read -r f; do
  printf '%s:sha256:%s\n' "$f" "$(shasum -a 256 "$f" | cut -d' ' -f1)"
done | shasum -a 256
```

Later stages use the source contract to resolve relative
`binding.location.path` values against its directory, and `source.env` to
refuse a mismatched environment. `fluid validate` reports the overlay warnings
the manifest records, with any character that is not printable escaped.

#### The provenance file

*On forge-cli `main`, not yet in a release ([forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985)).*
In 0.32.0 and earlier the MANIFEST recorded the source contract relative to the
directory of `--out`. One checkout bundled to `out.tgz` and to `x/y/out.tgz`
gave two different archives with one digest. The paths now go to a file beside
the archive, named after it with `.provenance.json` added, so the archive's
bytes do not depend on where it was written.

```console
$ cat runtime/bundle.tgz.provenance.json
{"bundleDigest":"sha256:c8e0d69396d694546601d6dfd9cc0be1b87ee6d5609b24a33092706005d78eed","packetDigest":"sha256:b92783ba770db2b65e7934cb7a56330c7760fb2fb203afe877bf9026c491543f","source":{"contract":"../contract.fluid.yaml","overlay":null},"version":"1"}
```

| Field | Meaning |
|---|---|
| `version` | The format of the file: `"1"`. |
| `bundleDigest` | The bundle's merkle digest. |
| `packetDigest` | The sha256 of the archive file; see [The packet digest](#the-packet-digest). |
| `source.contract` | The source contract, relative to the bundle's directory. |
| `source.overlay` | The overlay file that was merged, relative to the contract's directory, or `null`. |

`fluid bundle` writes the file readable by its owner only, because it names
paths on the machine that built the bundle, and replaces one that is already
there. When a build has no path to record, it removes a file an earlier build
left at that name.

Like the manifest's `source` block, the file is outside every digest: later
stages treat it as a hint and check it. A stage ignores it when it is not a
file (a link to a file is followed), is over 64 KiB, is not a JSON object, has another
`version`, or names other bytes (its `packetDigest` is not the sha256 of the
archive beside it). The recorded contract must also be a relative path ending in
`.yaml`, `.yml` or `.json`, still exist, and carry the id of the contract inside
the bundle, read with the bundle's environment overlay applied.

Without a usable file, `fluid plan` and `fluid apply` log
`source_contract_unresolved` and anchor relative paths at the bundle's own
directory. Copy the bundle together with its provenance file, to a place where
the recorded relative path still reaches the contract, or expect that.
For a bundle that packs a dbt project it is stricter: the checkout to compare
against cannot be found, and `fluid apply` refuses with
`apply_plan_digest_bundle_mismatch`, saying the bundle does not record a source
contract.

#### The packet digest

*On forge-cli `main`, not yet in a release ([forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985)).*
`fluid bundle` prints two digests. They name different things:

| Digest | Printed as | Covers |
|---|---|---|
| Bundle digest (merkle) | `digest:` | The files in the archive except `MANIFEST.json`: the resolved contract, and the dbt files it packs. It does not cover the manifest's own fields or the tar and gzip headers. |
| Packet digest | `packet:` | Every byte of the `.tgz` file: the manifest (the `--env` it records and its overlay warnings) and the headers. |

Two archives can share a bundle digest and differ in the packet digest: one
bundled with `--env prod` and one without, when the overlay changes nothing in
the contract, or with another `SOURCE_DATE_EPOCH`. `fluid plan <bundle>` records the packet digest, and
`fluid apply` refuses a bundle with other bytes; see
[`fluid apply`](./apply.md#plan-binding).

The same checkout bundled to two output paths gives one packet:

```console
$ fluid bundle contract.fluid.yaml --format tgz --out x/y/b.tgz
...
   digest: sha256:c8e0d69396d694546601d6dfd9cc0be1b87ee6d5609b24a33092706005d78eed
   packet: sha256:b92783ba770db2b65e7934cb7a56330c7760fb2fb203afe877bf9026c491543f
...
$ fluid bundle contract.fluid.yaml --format tgz --out b2.tgz
...
   digest: sha256:c8e0d69396d694546601d6dfd9cc0be1b87ee6d5609b24a33092706005d78eed
   packet: sha256:b92783ba770db2b65e7934cb7a56330c7760fb2fb203afe877bf9026c491543f
...
```

The packet digest is `shasum -a 256` of the `.tgz` file, with a `sha256:` prefix.

## Environments

`--env <env>` merges the overlay found next to the root contract
(`overlays/<env>.yaml` first) after the refs are resolved, so an overlay can
change a field that lives in a fragment. With `--format tgz` the run prints
what it applied:

```console
$ fluid bundle contract.fluid.yaml --env prod --format tgz --out runtime/bundle.tgz
...
overlay_applied
✅ Bundle written to /work/customer-360/runtime/bundle.tgz
   digest: sha256:98400a7caca4ca8ed6a6a30934d1d283394f515cc176cfae5423e6989805fccb
   env: prod (overlay: overlays/prod.yaml)
```

An `--env` with no overlay bundles the base contract, says so, and records
the env. `dev` is the base by convention, so it gets a quieter notice:

```console
$ fluid bundle contract.fluid.yaml --env staging --format tgz --out runtime/st.tgz
overlay_not_found: --env 'staging' matched no overlay for /work/customer-360/contract.fluid.yaml,
so the BASE contract is used unchanged (it binds to local, not to 'staging'). Overlays that
exist: prod. Add an overlay for it under overlays/ or pass one of the existing environments.
...
   env: staging (overlay: none (base contract))

$ fluid bundle contract.fluid.yaml --env dev --format tgz --out runtime/dev.tgz
overlay_base_env: --env 'dev' has no overlay for /work/customer-360/contract.fluid.yaml;
using the base contract (dev is the base by convention)
...
   env: dev (overlay: none (base contract))
```

**A tgz is bound to its environment.** It is never re-overlaid, so a later
stage given a bundle and a different `--env` refuses it with
`bundle_env_mismatch`. Pass the same `--env` to every stage, or none:

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

The environment is read from `MANIFEST.json`'s `source` block, which
`bundleDigest` does not cover; only a cosign signature (`--sign`, checked with
[`fluid verify-signature`](./verify-signature.md)) does.

`fluid verify`, `fluid diff` and `fluid generate artifacts` refuse it the
same way; `fluid validate` reports it as a `bundle-env` issue. A bundle built
without `--env` is accepted with `--env dev`, unless a dev overlay exists next
to the source contract. A bundle from an older CLI that recorded no `source`
block is accepted with a `bundle_env_unrecorded` warning.

An overlay may hold a `$ref`. Since 0.25.0 it resolves relative to the
overlay file, inside the same ref root, and nothing falls back to the base
contract. Before, `fluid bundle --env` kept the `$ref` key in its output
unresolved, and `fluid validate`, `fluid plan` and `fluid apply` ignored the
whole overlay. `--env` must name an environment, not a path: `--env ../x` is
refused. See
[Environments: overlays apply after resolution](../concepts/fragments.md#environments-overlays-apply-after-resolution).

## Signing and attestation

With keyless cosign signing on a GitHub Actions runner:

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz --sign
# emits: runtime/bundle.tgz, bundle.tgz.sig, bundle.tgz.pem
```

With keyed cosign signing (Bitbucket / air-gapped):

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz \
  --sign --sign-key awskms:///arn:aws:kms:us-east-1:111122223333:key/<key-id>
# emits: runtime/bundle.tgz, bundle.tgz.sig
```

With a SLSA provenance attestation (no cosign needed):

```console
$ fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz --attest
...
✅ Bundle written to /work/customer-360/runtime/bundle.tgz
   digest: sha256:6db90412513e10d5ed5c0bd02f465dbc76cdeec505997e6e65828f62b03521e0
attestation_written
✅ Attestation written (SLSA Provenance v1)
   intoto: /work/customer-360/runtime/bundle.tgz.intoto.jsonl
```

*On forge-cli `main`, not yet in a release ([forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985)).*
The statement's subject is the bundle file: its name and its sha256 in bare
hex, the form in-toto's digest set takes. A verifier that runs `sha256sum` on
the file finds that value. The subject of a run on `main`, trimmed:

```json
"subject": [{"name": "att.tgz", "digest": {"sha256": "b92783ba770db2b65e7934cb7a56330c7760fb2fb203afe877bf9026c491543f"}}]
```

In 0.32.0 and earlier the subject digest was the merkle `digest:` the command
prints, with a `sha256:` prefix. No file hashes to it, so a verifier could not
match the statement to the file. On `main` the merkle digest (`bundleDigest`),
the packet digest (`packetDigest`) and the checkout paths (`sourceContract`,
`overlay`) are among the statement's `externalParameters`, next to `env`,
`format`, `sign_mode` and `bundleOut`. The checkout paths are in the statement
because the archive no longer holds them.

The bundle is written before signing starts. When `cosign` is missing the
command exits `2` with `❌ --sign requires the cosign binary on PATH.`, and
the unsigned tgz is already on disk; do not ship it. Run `fluid doctor` to
check for cosign.

Verify a signed bundle with [`fluid verify-signature`](./verify-signature.md).

## Determinism guarantees

The tgz format produces **byte-identical output** across independent runs of the same input. Guaranteed by:

- `tar` header normalisation: `mtime=SOURCE_DATE_EPOCH`, `uid=gid=0`, `uname=gname=""`, mode `0o644` / `0o755`, entries sorted by path.
- YAML via `yaml.safe_dump(sort_keys=True, default_flow_style=False)`.
- JSON via `json.dumps(sort_keys=True, separators=(",", ":"))`.
- Extracted SQL / OpenAPI sources: byte-identical to the source strings after Unicode NFC normalisation + trailing-newline enforcement. No formatter mutation.
- *On forge-cli `main`, not yet in a release ([forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972)).* The dbt files of a dbt build: the bytes on disk, listed in sorted order, with no newline or Unicode change.

Result: the bundle's SHA-256 digest is a stable identifier usable as a cache key, a release artifact, or the `bundleDigest` field in `plan.json`. It does not depend on how the contract is split into fragments.

*On forge-cli `main`, not yet in a release ([forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985)).*
The archive does not depend on where it was written either: the same checkout
bundled to two `--out` paths gives the same bytes, and the `packet:` digest
`fluid bundle` prints is the same (see [The packet digest](#the-packet-digest)).
The checkout paths that used to differ with `--out` are in the
[provenance file](#the-provenance-file). A different `--env` or
`SOURCE_DATE_EPOCH` still gives a different packet. In 0.32.0 and earlier the
same checkout bundled to two `--out` depths gave two archives with one digest.

## Exit codes

| Code | When |
|---|---|
| `0` | Bundle written. Also when `--sign` / `--attest` were ignored for `yaml` / `json`. |
| `1` | No contract given and none in the current directory (`contract_required`); any other load or build failure (`❌ Compilation failed: ...`, `❌ Bundle tgz build failed: ...`); cosign or attestation failed; a CONTRACT or `--out` path that contains `..` (`ERR_PATH_TRAVERSAL_DETECTED`), or names a protected system directory (`ERR_FORBIDDEN_PATH_ACCESS`). |
| `2` | The contract file does not exist; a `$ref` could not be resolved (`❌ $ref resolution error: ...`, including ref-root refusals); `--sign` without `cosign` on `PATH`. |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `bundle_env_mismatch` in plan, verify, diff or generate artifacts | The bundle was built for another `--env`. | Pass the env it was built for, or rebuild with `--env <env>`. |
| `Failed to read file .../contract.bundled.fluid.yaml: 'utf-8' codec can't decode byte 0x8b` | A `contract.bundled.fluid.yaml` that is really a tarball, written by `fluid bundle --format tgz` or `fluid ship` in 0.25.0 or earlier on a fragment layout. | Delete it and bundle again; 0.26.0 writes `<contract id>.fluid.bundle.tgz`. |
| `❌ $ref resolution error: ... escapes the ref root` | A ref leaves the contract's directory tree. | See [The ref root](../concepts/contract-refs.md#the-ref-root). |
| `ERR_PATH_TRAVERSAL_DETECTED` | CONTRACT or `--out` contains `..`. | Pass a path without `..`, for example an absolute path. |
| `ERR_FORBIDDEN_PATH_ACCESS` | CONTRACT or `--out` is under a protected system directory such as `/etc`. | Write under the project directory. |
| No `.sig` after `--sign` | The format was `yaml` or `json`. | Use `--format tgz`. |
| `❌ Bundle tgz build failed: build '<id>': ... symbolic link`, `... hidden or __pycache__ directory`, `... outside the project` and the other refusals in [The dbt project of a dbt build](#the-dbt-project-of-a-dbt-build) *(on `main`, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972))* | The dbt project of a build holds something the bundle cannot bind as one tree. | Fix what the message names: it gives the file or key and what to do. |
| `no dbt_project.yml at ...` in a bundle build *(on `main`, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972))* | The build's `repository` names no dbt project, or one outside the contract's workspace. | Check the project out beside the contract, or point `repository` at it. |
| `apply_plan_digest_bundle_mismatch` naming dbt files *(on `main`, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972))* | A dbt file in the checkout differs from the bundle's copy, or the bundle packs no project for a dbt build (it was made before `main`). | Run `fluid bundle` and `fluid plan` again, or restore the files. See [`fluid apply`](./apply.md#plan-binding). |
| `apply_plan_digest_packet_mismatch` or `apply_plan_digest_packet_missing` *(on `main`, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))* | The bundle file has other bytes than the plan was made from, or the plan records none (an older `fluid plan` made it). | Run `fluid plan` on the bundle you apply. See [`fluid apply`](./apply.md#plan-binding). |
| `source_contract_unresolved` in plan or apply, or a dbt bundle refused as recording no source contract *(on `main`, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))* | The bundle was copied without its `.provenance.json`, the file names another packet, or the bundle and its file moved to a place where the recorded relative path no longer reaches the contract. | Copy `<bundle>.provenance.json` with the bundle, keep the relative path to the contract, or bundle again where you apply. See [The provenance file](#the-provenance-file). |

## See also

- [Contract fragments](../concepts/fragments.md): the fragment layout, CI usage and digests
- [`fluid split`](./split.md): the inverse operation
- [Composing a contract with `$ref`](../concepts/contract-refs.md): how refs are resolved, and the ref root
- [Operating in CI](../advanced/operating-in-ci.md): the 11-stage pipeline

::: tip About the examples
Output on this page was produced with CLI 0.18.1 on the quickstart
`customer-360` product, flat or split into fragments as each example shows,
except [Default output location](#default-output-location), which was
produced with 0.26.0. The examples under
[The dbt project of a dbt build](#the-dbt-project-of-a-dbt-build),
[The provenance file](#the-provenance-file) and
[The packet digest](#the-packet-digest) ran on forge-cli `main`, on a small `orders` contract with one dbt build. Long temporary
paths are shortened to `/work`, and long lines are re-wrapped.
:::
