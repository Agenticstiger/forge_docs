# `fluid validate-artifacts`

Stage 4 of the 11-stage pipeline. Verify that a `dist/artifacts/` tree emitted by [`fluid generate artifacts`](./generate-artifacts.md) matches its `MANIFEST.json` cryptographically and satisfies per-format schema checks.

Added in `0.8.0`.

## Syntax

```bash
fluid validate-artifacts ARTIFACTS_DIR
```

## Key options

| Option | Description |
| --- | --- |
| `ARTIFACTS_DIR` | Path to the artifacts directory (typically `dist/artifacts/`). |
| `--manifest` | Path to the MANIFEST to verify against (default `<ARTIFACTS_DIR>/MANIFEST.json`). |
| `--report` | Output JSON report path (default `runtime/validate-artifacts-report.json`). |
| `--strict` | Treat warnings as errors. |

## What it checks

| Check | Detail |
| --- | --- |
| **MANIFEST SHA-256 re-verify** | Every file listed in `MANIFEST.json` is re-hashed and compared byte-for-byte. Tamper detection: flipping one byte in any artifact surfaces as a hard-fail. |
| **ODCS schema validation** | All files under `odcs/` are validated against the vendored ODCS v3.1.0 schema from `bitol-io/open-data-contract-standard`. |
| **ODPS-Bitol schema validation** | All files under `odps-bitol/` are validated against the vendored ODPS-Bitol v1.0.0 schema from `bitol-io/open-data-product-standard`. |
| **Schedule DAG syntax** | `.py` files under `schedule/` are compiled with `python -m py_compile`. |
| **Policy bindings key-check** | `policy/bindings.json` is loaded and a shallow `provider` / `bindings` key-check runs. |
| **OPA conftest (optional)** | If `tests/policies/*.rego` exists next to the contract, `conftest test dist/artifacts/policy/bindings.json --policy tests/policies/` runs. Soft-import — no Rego rules → silent skip. |

## Examples

### Verify the output of stage 3

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
fluid validate-artifacts dist/artifacts/
```

### CI-gated verification with explicit MANIFEST

```bash
fluid validate-artifacts dist/artifacts/ \
  --manifest dist/artifacts/MANIFEST.json \
  --report runtime/validate-artifacts-report.json \
  --strict
```

### Tamper-detection spot-check

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
echo " extra" >> dist/artifacts/odcs/product.odcs.foo.yaml   # simulate tamper
fluid validate-artifacts dist/artifacts/
# ❌ exit 1: MANIFEST SHA-256 mismatch on odcs/product.odcs.foo.yaml
```

## Reference-only contracts

Stage 4 runs against whatever stage 3 emitted. For `builds[].pattern: hybrid-reference` contracts, stage 3 auto-skips the `schedule` and `policies` emitters, so stage 4 only validates the catalog artifacts (`odcs/` + `odps-bitol/`) that stage 3 did emit. The self-gate on `fileExists('dist/artifacts/MANIFEST.json')` ensures the stage is skipped entirely if stage 3 was turned off.

## Notes

- The MANIFEST re-verify is the primary trust boundary: a tampered file is caught before any schema validation runs, so schema errors can't mask content swaps.
- For the Rego / OPA integration, see [the governance walkthrough](../advanced/governance.md).
- Report format matches `fluid validate` / `fluid verify` — `{status, issues[], summary}` — so CI dashboards can key off the same shape.
