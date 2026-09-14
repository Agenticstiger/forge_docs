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
| **ODCS schema validation** | All files under `odcs/` are validated against the vendored ODCS v3.1.0 schema from `bitol-io/open-data-contract-standard`. *(since 0.15.0)* Validated with the dialect that schema declares (2019-09), not with Draft 7 — see [Schema dialect](#schema-dialect-since-0-15-0). |
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

## Schema dialect (since 0.15.0)

Since `0.15.0`, every schema is validated with **the dialect it declares** rather than with a pinned `Draft7Validator`. The three `jsonschema` call sites behind this stage (`forge/core/artifact_validators.py`) hardcoded Draft 7, and Draft 7 does not reject keywords it does not recognise — **it ignores them**.

The vendored `odcs-schema-v3.1.0.json` declares 2019-09 and guards nine objects with `unevaluatedProperties: false`, so every constraint expressed in a newer keyword was silently dropped and the document passed. Two concrete holes are now closed:

- A typo'd key in a `servers[]` entry validated with **zero** errors and now reports one (`Unevaluated properties are not allowed`). `servers[]` is the sharp case because, unlike the document root, it has no `additionalProperties`.
- Draft 7 also ignores keywords sitting alongside `$ref`, so `schema[].properties[]` lost the `required: ["name"]` check that `SchemaProperty` carries beside its `$ref`.

Both now fail, naming the offending key.

::: warning Behavior change in 0.15.0
An artifact tree that passed stage 4 on `0.14.1` can now fail it **with no contract change**. The change only tightens — no shipped schema uses a keyword 2019-09 or 2020-12 drops, so nothing that failed before now passes — and every ODCS document fluid itself emits is unaffected: 20 documents generated across ten example contracts validate identically under both dialects. Only hand-authored or third-party artifacts can newly go red.
:::

`fluid validate` on a *contract* is unchanged today, because the bundled FLUID schemas declare 2020-12 but have so far used only `$defs`, which Draft 7 resolves as an ordinary JSON pointer. See [`fluid validate` → Schema dialect](./validate.md#schema-dialect-since-0-15-0).

## Reference-only contracts

Stage 4 runs against whatever stage 3 emitted. For `builds[].pattern: hybrid-reference` contracts, stage 3 auto-skips the `schedule` and `policies` emitters, so stage 4 only validates the catalog artifacts (`odcs/` + `odps-bitol/`) that stage 3 did emit. The self-gate on `fileExists('dist/artifacts/MANIFEST.json')` ensures the stage is skipped entirely if stage 3 was turned off.

## Notes

- The MANIFEST re-verify is the primary trust boundary: a tampered file is caught before any schema validation runs, so schema errors can't mask content swaps.
- For the Rego / OPA integration, see [the governance walkthrough](../advanced/governance.md).
- Report format matches `fluid validate` / `fluid verify` — `{status, issues[], summary}` — so CI dashboards can key off the same shape.
