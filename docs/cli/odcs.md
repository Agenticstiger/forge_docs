# `fluid odcs`

Convert between FLUID contracts and the Open Data Contract Standard (ODCS) v3.1.0 from Bitol.io, in either direction.

## Syntax

```bash
fluid odcs export CONTRACT [--output PATH] [--format FMT] [--no-quality] [--no-sla]
fluid odcs import ODCS_FILE [--output PATH] [--format FMT]
fluid odcs validate ODCS_FILE
fluid odcs info
```

## Key options

### `odcs export`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file. |
| `--output`, `-o` | Output file path. Default `<contract-name>-odcs.<format>`. |
| `--format`, `-f` | Output format: `yaml` or `json`. Default `yaml`. |
| `--no-quality` | Exclude quality checks from the output. |
| `--no-sla` | Exclude SLA properties from the output. |

### `odcs import`

| Option | Description |
| --- | --- |
| `ODCS_FILE` | Path to ODCS contract file. |
| `--output`, `-o` | Output file path. Default `<file>-fluid.<format>`. |
| `--format`, `-f` | Output format: `yaml` or `json`. Default `yaml`. |

### `odcs validate`

| Option | Description |
| --- | --- |
| `ODCS_FILE` | Path to an ODCS file to validate against the v3.1.0 JSON schema. |

### `odcs info`

No options. Prints exporter info (version, spec URL, schema status).

## Examples

```bash
fluid odcs export contract.fluid.yaml
fluid odcs export contract.fluid.yaml -o contract.json -f json --no-sla
fluid odcs import third-party-contract.yaml -o my-contract.fluid.yaml
fluid odcs validate contract.odcs.yaml
```

## Notes

- ODCS is bidirectional: `export` goes FLUID -> ODCS, `import` goes ODCS -> FLUID. The underlying exporter was modularised under `providers/odcs/` in `v0.8.3` with paired `to_fluid()` / `to_odcs()` mappers and per-level `odcs_passthrough` buckets for lossless round-trip. As of `0.10.0`, ODCS is a spec exporter (surfaced by [`fluid exporters`](./exporters.md)), not a registered cloud provider — it is not listed by [`fluid providers`](./providers.md).
- Validation uses the bundled ODCS v3.1.0 JSON Schema from Bitol.io. Validation runs by default on every export (`ODCS_VALIDATE=true`); failures warn rather than raise. Hard-fail via `ODCS_VALIDATE_STRICT=true`. *(since 0.15.0)* That schema is now validated with the 2019-09 dialect it declares rather than with Draft 7, which **ignored** the nine `unevaluatedProperties: false` guards it carries — so an export that validated clean on `0.14.1` may now warn. Same change, same cause, as [`fluid validate-artifacts` → Schema dialect](./validate-artifacts.md#schema-dialect-since-0-15-0).
- **`description` field mapping.** ODCS models `description` as an object of string fields (`purpose`, `limitations`, `usage`); FLUID models it as a single string, so converting needs a type check in both directions. *(since 0.15.0)* The exporter mirrors the importer: a mapping passes through as siblings under `description`, a string is still wrapped as `{purpose: <string>}`, and an empty mapping emits no `description` key at all. Previously the exporter wrapped **unconditionally**, so a mapping came out as `description.purpose: {purpose: …, limitations: …, usage: …}` — an object where the schema declares a string, i.e. invalid ODCS written with only a warning (or, on installs carrying the optional `vowl` validator via `fluid-build[odcs-strict]`, an aborted `fluid generate artifacts` that wrote no artifacts at all). Round-trips never saw it, because the import path stashes the original object in metadata passthrough and the exporter reads it back; only a caller rendering a document it had not imported reached the broken branch. The old shape was already schema-invalid, so only a consumer written against the bug breaks.
- The unified [`fluid odps`](./odps-bitol.md#unified-fluid-odps-since-v0-8-3) command also accepts a lone ODCS file under `fluid odps import` — useful when you want one entry point for both spec families.
- For Bitol.io's data-product variant (ODPS-Bitol), use [`fluid odps-bitol`](./odps-bitol.md). For the official ODPS (Open Data Product Initiative), use [`fluid odps`](./odps.md).
- To publish ODCS contracts to Entropy Data alongside a data product, see [`fluid datamesh-manager publish --with-contract`](./datamesh-manager.md).
