# `fluid bundle`

Stage 1 of the 11-stage pipeline. Package the contract and its source files into a single bundle — either a resolved single-document YAML/JSON (development) or a deterministic content-addressable tgz archive with a SHA-256 MANIFEST (production).

Renamed from `fluid compile` in `0.7.3`. The hidden `fluid compile` alias was removed; use `fluid bundle --format yaml` as the one-to-one replacement for legacy callers.

## Syntax

```bash
fluid bundle CONTRACT
```

## Key options

### Input / output

| Option | Description |
| --- | --- |
| `--out`, `-o` | Output path. Default `-` for stdout (yaml/json) or the current directory (tgz). |
| `--env`, `-e` | Apply an environment overlay after ref resolution. |
| `--format`, `-f` | Output format: `yaml` (default), `json`, or `tgz`. See below. |

### Supply chain (opt-in, `--format tgz` only)

| Option | Description |
| --- | --- |
| `--sign` | Sigstore cosign sign the emitted tgz. Default is keyless OIDC (GitHub / GitLab / CircleCI / GCP WIF all detected automatically). Writes `<bundle>.sig` and — in keyless mode — `<bundle>.pem` next to the tgz. |
| `--sign-key PATH_OR_KMS_URI` | Use keyed cosign signing instead of keyless. Supports file paths and KMS URIs (`awskms://`, `gcpkms://`, `azurekms://`, `hashivault://`, `k8s://`). Required for Bitbucket Pipelines, air-gapped, and regulatory environments without OIDC. |
| `--attest` | Emit a SLSA Level 2 in-toto v1 provenance predicate next to the bundle as `<bundle>.tgz.intoto.jsonl`. Records the build system (GitHub / GitLab / CircleCI / Jenkins / Bitbucket / Azure), invocation ID, git commit SHA, and `subject[0].digest.sha256 = <bundle SHA>`. |

## Output formats

### `yaml` / `json` (default)

Resolves every `$ref` in the contract and emits a single-document YAML or JSON file. Drop-in replacement for the legacy `fluid compile` command.

```bash
fluid bundle contract.fluid.yaml                       # stdout, yaml
fluid bundle contract.fluid.yaml --out bundled.yaml    # file, yaml
fluid bundle contract.fluid.yaml --format json --out bundled.json
fluid bundle contract.fluid.yaml --env prod --out prod-bundled.yaml
```

### `tgz` (canonical production format)

Emits a deterministic content-addressable tgz with:

- `MANIFEST.json` — SHA-256 per file + merkle root (the `bundleDigest` referenced by stage 6 plan and verified by stage 7 apply)
- `contract.resolved.yaml` / `contract.resolved.json` — `$ref` pointers resolved; inline SQL / OpenAPI blocks are extracted into `sources/` and replaced with `{"$source": "sources/..."}` sentinels
- `sources/sql/{id}.sql`, `sources/openapi/{id}.yaml`, `sources/policy/*.yaml` — extracted fragments

Two independent runs produce byte-identical tgz output (tar-header normalisation + `sort_keys=True` + Unicode NFC + enforced trailing newlines). This is what makes `bundleDigest` a stable identifier.

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
```

With keyless cosign signing on a GitHub Actions runner:

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz --sign
# emits: runtime/bundle.tgz, bundle.tgz.sig, bundle.tgz.pem
```

With keyed cosign signing (Bitbucket / air-gapped):

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz \
  --sign --sign-key awskms:///arn:aws:kms:us-east-1:111122223333:key/bc436485-…
# emits: runtime/bundle.tgz, bundle.tgz.sig
```

With SLSA L2 provenance attestation alongside signing:

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz --sign --attest
# emits: runtime/bundle.tgz, .sig, .pem, .intoto.jsonl
```

Verify a signed bundle with [`fluid verify-signature`](./verify-signature.md).

## Examples

```bash
# Dev: resolve-and-inspect (equivalent to legacy fluid compile)
fluid bundle contract.fluid.yaml

# Dev with env overlay
fluid bundle contract.fluid.yaml --env staging --out staging-bundled.yaml

# Prod: canonical content-addressable tgz (stage 1 of the 11-stage pipeline)
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz

# Prod + supply chain (GitHub Actions / keyless OIDC)
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz --sign --attest
```

## Determinism guarantees

The tgz format produces **byte-identical output** across independent runs of the same input. Guaranteed by:

- `tar` header normalisation: `mtime=SOURCE_DATE_EPOCH`, `uid=gid=0`, `uname=gname=""`, mode `0o644` / `0o755`, entries sorted by path.
- YAML via `yaml.safe_dump(sort_keys=True, default_flow_style=False)`.
- JSON via `json.dumps(sort_keys=True, separators=(",", ":"))`.
- SQL / policy / OpenAPI fragments: byte-identical to the source strings after Unicode NFC normalisation + trailing-newline enforcement. No formatter mutation.

Result: the bundle's SHA-256 digest is a stable cryptographic identifier usable as a cache key, a release artifact, or the `bundleDigest` field in `plan.json`.

## Notes

- `fluid bundle --format yaml` is the drop-in replacement for the removed `fluid compile` command.
- `--sign` and `--attest` are **tgz-only**. On `yaml` / `json` they are rejected with a clear error — signing a text format isn't a useful operation.
- Cosign must be on `PATH` for `--sign`. See `fluid doctor` to verify.
- Use `bundle` to inspect or ship a resolved contract after fragmenting with [`fluid split`](./split.md).
