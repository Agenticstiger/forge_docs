# `fluid odps`

Unified command for the Open Data Product Standard (ODPS). Dispatches between:

- **Bitol ODPS v1.0.0** — the center-stage format for Entropy Data / Data Mesh Manager marketplace integrations (`--spec bitol-1.0.0` or omit for the default).
- **LF/ODPI ODPS v4.1** — the Linux Foundation / Open Data Product Initiative specification, opt-in via `--spec odps-v4.1`.

## Syntax

```bash
fluid odps export CONTRACT  [--spec SPEC] [--out PATH] [--out-dir DIR] [--env ENV] [--no-validate] [--compact]
fluid odps import PATH       [--spec SPEC] [--allow-remote] [-o OUTPUT]
fluid odps validate FILE     [--spec SPEC] [--no-full-schema]
fluid odps info              [--spec SPEC] [--json]
```

::: tip Back-compat alias
`fluid opds` remains registered as a hidden back-compat alias for `fluid odps` and will be removed in a future major release.
:::

## Key options

### `odps export`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file (YAML/JSON). |
| `--spec` | `bitol-1.0.0` (default, center-stage) or `odps-v4.1` (LF/ODPI, opt-in). |
| `--out` | Output file path, or `-` for stdout. Default `-`. |
| `--out-dir` | Write to a named directory (useful for Bitol bundles which emit a product doc + sibling ODCS files). |
| `--env` | Environment name for overlay application. |
| `--validate` / `--no-validate` | Validate output against the spec schema. Default on. |
| `--pretty` / `--compact` | Pretty-print or compact JSON output. Default pretty. |

### `odps import`

Accepts three entry shapes: a single ODPS doc, a directory bundle (ODPS product + sibling ODCS files), or a lone ODCS file.

| Option | Description |
| --- | --- |
| `PATH` | Path to an ODPS doc, directory bundle, or ODCS file. |
| `--spec` | `bitol-1.0.0` (only spec with import support today). |
| `--allow-remote` | Resolve `contractId` references via HTTP (SSRF-guarded — off by default). |
| `-o OUTPUT` | Write the resulting FLUID contract to this path. Default stdout. |

### `odps validate`

| Option | Description |
| --- | --- |
| `FILE` | Path to an ODPS JSON/YAML file. |
| `--spec` | Spec to validate against. Default `bitol-1.0.0`. |
| `--full-schema` / `--no-full-schema` | Full JSON schema validation (requires `jsonschema`) or basic checks. Default full. |

### `odps info`

| Option | Description |
| --- | --- |
| `--spec` | Show info for one spec only. |
| `--json` | Machine-readable JSON output. |

## Examples

```bash
# Bitol ODPS v1.0.0 (default — center-stage)
fluid odps export contract.yaml
fluid odps export contract.yaml --out product.odps.yaml
fluid odps export contract.yaml --out-dir ./dist/odps-bundle/

# LF/ODPI v4.1 (opt-in)
fluid odps export contract.yaml --spec odps-v4.1 --out product.odps.json

# Import a Bitol ODPS product (or bundle) back to FLUID
fluid odps import product.odps.yaml -o recovered.fluid.yaml
fluid odps import ./odps-bundle/ -o recovered.fluid.yaml --allow-remote

# Validate an existing ODPS file
fluid odps validate product.odps.yaml
fluid odps validate product.odps.json --spec odps-v4.1

# List available specs
fluid odps info
fluid odps info --spec bitol-1.0.0 --json
```

## Spec at a glance

| `--spec` | Standard | Governed by | Typical use |
| --- | --- | --- | --- |
| `bitol-1.0.0` *(default)* | Open Data Product Standard v1.0.0 | [Bitol.io](https://bitol.io) | Entropy Data / DMM marketplace |
| `odps-v4.1` | Open Data Product Specification v4.1 | LF / Open Data Product Initiative | ODPI-aligned catalogs |

::: warning Deprecation — `--spec odpi-4.1`
The old `--spec odpi-4.1` token (note the letter swap) is accepted with a WARNING and redirected to `odps-v4.1`. Update any scripts that use `--spec odpi-4.1`.
:::

## Notes

- The default spec (`bitol-1.0.0`) is the **center-stage** format for Entropy Data and the Data Mesh Manager marketplace. Use it for day-to-day DMM publishing workflows.
- If the file passed to `validate` is a wrapped render envelope (contains an `artifacts` key), it is unwrapped automatically.
- `odps import` with a directory bundle resolves sibling ODCS files referenced by `contractId` — useful for round-tripping Bitol bundles produced by `fluid generate standard --format odps`.
- For a one-shot export to file, see [`fluid export-odps`](./export-odps.md).
- For the Open Data Contract Standard, use [`fluid odcs`](./odcs.md).
- For ODPS publishing to Entropy Data / Data Mesh Manager, see [`fluid datamesh-manager publish`](./datamesh-manager.md).
