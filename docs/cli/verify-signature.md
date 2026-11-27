# `fluid verify-signature`

Verify a Sigstore cosign signature (and optional SLSA Level 2 in-toto attestation) on a tgz bundle emitted by `fluid bundle --format tgz --sign`.

Added in `0.8.0`.

*(since 0.42.0, [forge-cli #1126](https://github.com/Agenticstiger/forge-cli/pull/1126))* The signature, the certificate (keyless) and the transparency-log proof are one Sigstore bundle, `<BUNDLE_TGZ>.sigstore.json`, which `fluid bundle --sign` writes and this command reads with `cosign verify-blob --bundle`. Through 0.41.0 they were `<BUNDLE_TGZ>.sig` and `<BUNDLE_TGZ>.pem`, which cosign 3.x no longer writes for a blob; those files are not read any more. cosign 2.x writes its own bundle format and 3.x the Sigstore one, so sign and verify with the same cosign major version.

## Syntax

```bash
fluid verify-signature BUNDLE_TGZ [options]
```

## Key options

| Option | Description |
| --- | --- |
| `BUNDLE_TGZ` | Path to the tgz bundle to verify. |
| `--bundle PATH` | The Sigstore bundle. Default `<BUNDLE_TGZ>.sigstore.json`. |
| `--key PATH_OR_KMS_URI` | Keyed-mode verification. Path or KMS URI of the public key; selects keyed over keyless. Supports file paths + `awskms://`, `gcpkms://`, `azurekms://`, `hashivault://`, `k8s://`, `pkcs11://`, `file://`. |
| `--certificate-identity ID`, `--certificate-oidc-issuer URL` | Keyless: the signer's exact certificate identity and OIDC issuer, both required. They replace the regexps below. |
| `--identity-regexp PATTERN` | Keyless: a regexp the signer's certificate identity must match, instead of `--certificate-identity`. |
| `--oidc-issuer-regexp PATTERN` | Keyless: a regexp the signer's OIDC issuer must match (e.g. `https://token\.actions\.githubusercontent\.com`), instead of `--certificate-oidc-issuer`. |
| `--timeout SECONDS` | Per-subprocess cosign timeout. Default 120. |

Keyless verification names its signer: an identity and an issuer, each exactly or as a regexp. There is no default, since anyone can get a Sigstore certificate for their own identity, so a check that names none proves nothing about who signed. A missing or empty value (an unset CI variable) exits `2` with `signing_identity_not_pinned` before cosign runs. Through 0.41.0 both regexps defaulted to `.*`. `--signature` and `--certificate` exit `2` with `verify_signature_sig_pem_gone`, naming `--bundle`.

::: tip Got `SupplyChainViolationError` instead?
That error is not raised by this command. It comes from an Airbyte acquisition build whose connector image failed its Cosign check. The check is configured on the build, under `builds[].properties.airbyte.image_signature` (`verifier: cosign`, `publicKey`, `slsaProvenance`), and the failing image is named in the error. Its fix text also mentions `sovereignty.allowedSigners`; as of 0.18.1 no bundled contract schema defines that field, so pin the signer with `publicKey`. See [typed CLI errors](../advanced/typed-cli-errors.md#governance) and [Source-Aligned Acquisition](../advanced/source-aligned-acquisition.md). `fluid verify-signature` checks a `fluid bundle` tarball, not a container image.
:::

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Signature valid. |
| `1` | Invalid signature or identity mismatch. |
| `2` | Config error — bundle not found, cosign not on PATH, no Sigstore bundle (`signing_sigstore_bundle_missing`), no signer named or an empty one (`signing_identity_not_pinned`), etc. |

## Examples

### Keyless (GitHub Actions / GitLab / CircleCI / GCP WIF)

Default mode. Uses Sigstore's Fulcio cert + Rekor transparency log, and names the signer (below): a keyless check without one is refused.

### Keyless, pinned to one workflow

Pin the signer exactly in production: the workflow's certificate identity and the CI's issuer.

```bash
fluid verify-signature runtime/bundle.tgz \
  --certificate-identity 'https://github.com/<your-org>/<repo>/.github/workflows/ci.yml@refs/heads/main' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'
```

### Keyless, pinned to a specific org + issuer

Or match by regexp, so only signatures from your org's GitHub Actions workflows verify:

```bash
fluid verify-signature runtime/bundle.tgz \
  --identity-regexp 'https://github.com/<your-org>/.*' \
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
  --verify-signature \
  --verify-certificate-identity 'https://github.com/<your-org>/<repo>/.github/workflows/ci.yml@refs/heads/main' \
  --verify-certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  --bundle runtime/bundle.tgz
```

`--verify-signature` requires `--bundle`. Without it, `schedule-sync` aborts with `schedule_sync_verify_signature_missing_bundle` (exit `2`).

For manual verification in a CI step, just chain `verify-signature` before the destructive / publish actions:

```bash
fluid verify-signature runtime/bundle.tgz \
  --identity-regexp "https://github.com/${GITHUB_REPOSITORY_OWNER}/.*" \
  --oidc-issuer-regexp 'https://token.actions.githubusercontent.com'
# Exit 1 stops the pipeline before publish
fluid publish ... --target ...
```

## Notes

- Cosign must be on `PATH`. Install from https://docs.sigstore.dev/cosign/installation/ or via `brew install cosign`. `fluid doctor --scope infra` checks that it is on `PATH`.
- The Sigstore bundle must be next to the tgz as `<BUNDLE_TGZ>.sigstore.json`, or named with `--bundle PATH`. `fluid bundle --sign` writes it there.
- A failed check prints cosign's last line of error output, after any warnings it gave.
- The SLSA attestation (`<bundle>.tgz.intoto.jsonl` from `fluid bundle --attest`) is **not** verified by `verify-signature` — it's a separate predicate that stakeholders read offline. A future release may add an `--attest` verification mode.
