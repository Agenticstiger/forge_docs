# `fluid verify-signature`

Verify a Sigstore cosign signature (and optional SLSA Level 2 in-toto attestation) on a tgz bundle emitted by `fluid bundle --format tgz --sign`.

Added in `0.8.0`.

## Syntax

```bash
fluid verify-signature BUNDLE_TGZ [options]
```

## Key options

| Option | Description |
| --- | --- |
| `BUNDLE_TGZ` | Path to the tgz bundle to verify. |
| `--signature PATH` | `.sig` file path. Default `<BUNDLE_TGZ>.sig`. |
| `--certificate PATH` | `.pem` file path for keyless verification. Default `<BUNDLE_TGZ>.pem`. |
| `--key PATH_OR_KMS_URI` | Keyed-mode verification. Path or KMS URI of the public key; selects keyed over keyless. Supports file paths + `awskms://`, `gcpkms://`, `azurekms://`, `hashivault://`, `k8s://`, `pkcs11://`, `file://`. |
| `--identity-regexp PATTERN` | Regexp matching the acceptable OIDC subject (keyless mode). Default `.*` accepts any — tighten in production to pin signer identity. |
| `--oidc-issuer-regexp PATTERN` | Regexp matching the acceptable OIDC issuer. Default `.*`; tighten to pin the CI system (e.g. `https://token.actions.githubusercontent.com`). |
| `--timeout SECONDS` | Per-subprocess cosign timeout. Default 120. |

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Signature valid. |
| `1` | Invalid signature or identity mismatch. |
| `2` | Config error — bundle not found, cosign not on PATH, missing .sig / .pem, etc. |

## Examples

### Keyless (GitHub Actions / GitLab / CircleCI / GCP WIF)

Default mode. Uses Sigstore's Fulcio cert + Rekor transparency log:

```bash
# Accepts any keyless signature (default regexps are permissive)
fluid verify-signature runtime/bundle.tgz
```

### Keyless, pinned to a specific org + issuer

Tighten the regexps in production so only signatures from your org's GitHub Actions workflows verify:

```bash
fluid verify-signature runtime/bundle.tgz \
  --identity-regexp 'https://github.com/myorg/.*' \
  --oidc-issuer-regexp 'https://token.actions.githubusercontent.com'
```

### Keyed (Bitbucket / air-gapped / regulatory)

```bash
# File-path public key
fluid verify-signature runtime/bundle.tgz \
  --key cosign.pub

# AWS KMS public-key URI
fluid verify-signature runtime/bundle.tgz \
  --key awskms:///arn:aws:kms:us-east-1:111122223333:key/bc436485-…
```

When `--key` is supplied, `--identity-regexp` and `--oidc-issuer-regexp` are ignored (keyed mode doesn't have OIDC identities).

## Relationship with `fluid bundle --sign`

| `fluid bundle --sign …` | `fluid verify-signature …` |
| --- | --- |
| No `--sign-key` → keyless OIDC | Default mode; use `--identity-regexp` + `--oidc-issuer-regexp` to pin identity. |
| `--sign-key <path>` | `--key <path>` |
| `--sign-key awskms://…` | `--key awskms://…` |

## Use in CI

`fluid schedule-sync` has a `--verify-signature` flag that refuses to push DAGs from unsigned or mutated bundles:

```bash
# Pair at stage 1
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz --sign --attest

# Verify at stage 11 before pushing to the scheduler
fluid schedule-sync --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination s3://my-airflow-dags/team-x/ \
  --verify-signature
```

For manual verification in a CI step, just chain `verify-signature` before the destructive / publish actions:

```bash
fluid verify-signature runtime/bundle.tgz \
  --identity-regexp "https://github.com/${GITHUB_REPOSITORY_OWNER}/.*" \
  --oidc-issuer-regexp 'https://token.actions.githubusercontent.com'
# Exit 1 stops the pipeline before publish
fluid publish ... --target ...
```

## Notes

- Cosign must be on `PATH`. Install from https://docs.sigstore.dev/cosign/installation/ or via `brew install cosign`. `fluid doctor` verifies.
- The `--sig` / `--pem` files must be next to the tgz (or passed explicitly via `--signature` / `--certificate`). `fluid bundle --sign` writes them next to the tgz by default.
- The SLSA attestation (`<bundle>.tgz.intoto.jsonl` from `fluid bundle --attest`) is **not** verified by `verify-signature` — it's a separate predicate that stakeholders read offline. A future release may add an `--attest` verification mode.
