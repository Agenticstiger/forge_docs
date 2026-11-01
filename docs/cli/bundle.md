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
| `--attest` | Write an in-toto v1 Statement with a SLSA Provenance v1 predicate next to the bundle as `<bundle>.intoto.jsonl`. Records the git commit SHA, CI run URL, bundle digest and builder identity. Works offline with a localhost builder and a random run id; full SLSA Level 2 needs a trusted build service. |

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
```

The archive holds the resolved document only. Your fragment files, their
names and boundaries are not kept: a flat contract and its split layout give
the same files and the same digest.

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

#### `MANIFEST.json`

```console
$ tar -xzOf runtime/bundle.tgz MANIFEST.json | python3 -m json.tool
{
    "contractId": "gold.customer.analytics_360_v1",
    "digest": "sha256:98400a7caca4ca8ed6a6a30934d1d283394f515cc176cfae5423e6989805fccb",
    "files": {
        "contract.resolved.json": "sha256:eff83c5b1694a85aca596960a416311771cd26e1c7ccd37f8c9a266fe8f39ae7",
        "contract.resolved.yaml": "sha256:87e89795dcdb076453781da9decb3521cf7aced2fb058d200e6e2ff978c87291"
    },
    "generator": "fluid bundle",
    "source": {
        "contract": "../contract.fluid.yaml",
        "env": "prod",
        "overlay": "overlays/prod.yaml"
    },
    "version": "1.0"
}
```

The file itself is compact JSON with sorted keys.

| Field | Meaning |
|---|---|
| `files` | SHA-256 of each file in the archive except `MANIFEST.json`. |
| `digest` | The bundle digest (`bundleDigest` in `plan.json`): SHA-256 over the sorted `<path>:<file digest>` lines, one per file. |
| `source.contract` | The source contract, relative to the directory the bundle was written to. |
| `source.env` | The `--env` the bundle was built with, or `null`. |
| `source.overlay` | The overlay file that was merged, relative to the contract's directory, or `null`. |
| `source.overlayWarnings` | *(since 0.22.0, [forge-cli #735](https://github.com/Agenticstiger/forge-cli/pull/735))* The overlay merge warnings `fluid validate --strict` fails on, one message each: a patch that landed on another entry. Present only when the merge raised one. |

The `source` block is outside the digest, so the digest names the resolved
contract alone: the same contract bundled into two directories keeps one
digest. The same holds for the manifest's integrity check: it recomputes the
digest from the files, so it does not cover `source`, and later stages read
`source.env` to refuse a mismatched `--env`. Only a cosign signature
(`--sign`) over the whole tgz covers it. You can recompute the digest from an extracted bundle:

```bash
mkdir bundle && tar -xzf runtime/bundle.tgz -C bundle && cd bundle
find . -type f ! -name MANIFEST.json | sed 's|^\./||' | LC_ALL=C sort | while read -r f; do
  printf '%s:sha256:%s\n' "$f" "$(shasum -a 256 "$f" | cut -d' ' -f1)"
done | shasum -a 256
```

Later stages use `source` to resolve relative `binding.location.path` values
against the source contract's directory, and to refuse a mismatched
environment. `fluid validate` reports the overlay warnings it records, with
any character that is not printable escaped.

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

Result: the bundle's SHA-256 digest is a stable identifier usable as a cache key, a release artifact, or the `bundleDigest` field in `plan.json`. It does not depend on how the contract is split into fragments.

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

## See also

- [Contract fragments](../concepts/fragments.md): the fragment layout, CI usage and digests
- [`fluid split`](./split.md): the inverse operation
- [Composing a contract with `$ref`](../concepts/contract-refs.md): how refs are resolved, and the ref root
- [Operating in CI](../advanced/operating-in-ci.md): the 11-stage pipeline

::: tip About the examples
Output on this page was produced with CLI 0.18.1 on the quickstart
`customer-360` product, flat or split into fragments as each example shows,
except [Default output location](#default-output-location), which was
produced with 0.26.0. Long temporary paths are
shortened to `/work`, and long lines are re-wrapped.
:::
