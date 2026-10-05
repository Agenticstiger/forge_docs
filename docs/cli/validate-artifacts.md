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
| `--report` | Write a structured JSON report to PATH (same shape as `fluid validate <tgz> --report`). No default — omit it and no report file is written. |
| `--strict` | Treat warnings as errors in the final status; hard-fail when optional tools (jsonschema, conftest, dbt) are absent. |
| `--opa-policy-dir` | Directory containing `*.rego` files for OPA conftest. Default `tests/policies`. Skipped silently if the directory is absent or empty; a missing `conftest` binary is INFO without `--strict` and ERROR with it. |
| `--fail-fast` | Stop at the first error-severity issue instead of collect-all. |
| `--format {text,json}` | stdout format (`text` = human summary, `json` = full report). Default `text`. |
| `--verbose`, `-v` | Print every issue, not just the summary. |
| `--quiet`, `-q` | Suppress status output; rely on exit code and `--report`. |

## What it checks

| Check | Detail |
| --- | --- |
| **MANIFEST SHA-256 re-verify** | Every file listed in `MANIFEST.json` is re-hashed and compared byte-for-byte, and the MANIFEST's own digest is recomputed. Tamper detection: flipping one byte in any artifact surfaces as a hard-fail. While a MANIFEST error stands, no per-format check runs. |
| **ODCS schema validation** | Files under `odcs/` are validated against the vendored ODCS v3.1.0 schema from `bitol-io/open-data-contract-standard`. *(since 0.15.0)* Validated with the dialect that schema declares (2019-09), not with Draft 7 — see [Schema dialect](#schema-dialect-since-0-15-0). |
| **ODPS-Bitol schema validation** | Files under `odps-bitol/` are validated against the vendored ODPS-Bitol v1.0.0 schema from `bitol-io/open-data-product-standard`. Sibling `*.odcs.yaml`, `*.odcs.yml` and `*.odcs.json` files in that directory are validated as ODCS instead. |
| **OPDS schema validation** | Files under `opds/` (and the older `odps/` prefix) are validated against the vendored OPDS v4.1 schema. |
| **Schedule DAG syntax** | `.py` files under `schedule/` are compiled with `python -m py_compile`. Stage 3 writes them to `schedule/<product-id>/`, with an `__<env>` suffix on the directory when you generate with `--env`. |
| **Policy bindings key-check** | `policy/bindings.json` is loaded and a shallow `provider` / `bindings` key-check runs. |
| **OPA conftest (optional)** | If `tests/policies/*.rego` exists next to the contract, `conftest test dist/artifacts/policy/bindings.json --policy tests/policies/` runs. Soft-import — no Rego rules → silent skip. |
| **dbt parse (optional)** | If `<ARTIFACTS_DIR>/dbt/dbt_project.yml` exists, `dbt parse --no-partial-parse` runs on it. When `dbt` is not on `PATH` the check is skipped with an INFO note, or fails with `--strict`. |

Two situations produce a warning, and `--strict` turns each into a failure:

- A file on disk that `MANIFEST.json` does not declare: `MANIFEST-UNDECLARED-FILE`.
- A file the MANIFEST declares that has no validator for its path: `ARTIFACT-UNEXPECTED`. Only the prefixes in the table above have one.

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

### Pass: a clean tree

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts
fluid validate-artifacts dist/artifacts
```

```text
✅ Artifacts pass: dist/artifacts
   digest:
sha256:d7c7871b28c2397ae2fa45436b606a203337becb778454d0b7567d943e779e52
   issues: 0 total (0 error, 0 warning, 0 info)
```

### Tamper-detection spot-check

```bash
cp -r dist/artifacts dist/t
echo " extra" >> dist/t/odcs/product.odcs.customer_360_master.yaml   # simulate tamper
fluid validate-artifacts dist/t -v
```

```text
❌ Artifacts fail: dist/t
   digest:
sha256:d7c7871b28c2397ae2fa45436b606a203337becb778454d0b7567d943e779e52
   issues: 2 total (2 error, 0 warning, 0 info)
    manifest: odcs/product.odcs.customer_360_master.yaml: SHA-256 mismatch:
expected
sha256:ad75a7231f58e8fa87064dc25d386e9dea8b259b39ac8d4ae29f28a9f66129b3, got
sha256:c6862511134460f1f059265195abc5eb6e4150f5fa3e7a7bd783bc01450aa255
    manifest: dist/t/MANIFEST.json: merkle root mismatch: expected
sha256:d7c7871b28c2397ae2fa45436b606a203337becb778454d0b7567d943e779e52, got
sha256:cd7224f6c254ce0920d05ba266269668d5a134246906e559cf4829f2a887a432
```

The command exits `1`. The second line is the MANIFEST's own digest no longer matching its file list.

### A stray file

A file dropped into the tree after generation is not in the MANIFEST:

```bash
echo hi > dist/artifacts/stray.txt
fluid validate-artifacts dist/artifacts -v        # exit 0, one warning
fluid validate-artifacts dist/artifacts --strict  # exit 1
```

```text
✅ Artifacts pass: dist/artifacts
   digest:
sha256:d7c7871b28c2397ae2fa45436b606a203337becb778454d0b7567d943e779e52
   issues: 1 total (0 error, 1 warning, 0 info)
    manifest: stray.txt: present in dist/artifacts but not declared in MANIFEST
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
