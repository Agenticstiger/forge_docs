# `fluid odps`

Unified command for the Open Data Product Standard (ODPS). Dispatches between:

- **Bitol ODPS v1.0.0** — the center-stage format for Entropy Data / Data Mesh Manager marketplace integrations (`--spec bitol-1.0.0` or omit for the default).
- **LF/ODPI ODPS v4.1** — the Linux Foundation / Open Data Product Initiative specification, opt-in via `--spec odps-4.1`.

## Syntax

```bash
fluid odps export CONTRACT  [--spec SPEC] [--out PATH] [--out-dir DIR] [-f FORMAT] [--env ENV] [--no-validate-strict] [--compact]
fluid odps import PATH       [--spec SPEC] [--allow-remote] [--lenient] [-f FORMAT] [-o OUTPUT]
fluid odps validate FILE     [--spec SPEC] [--no-full-schema]
fluid odps info              [--spec SPEC] [--json]
```

## Key options

### `odps export`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file (YAML/JSON). |
| `--spec` | `bitol-1.0.0` (default, center-stage) or `odps-4.1` (LF/ODPI, opt-in). `odpi-4.1` is still accepted as a deprecated alias that warns. Note: `fluid generate standard` spells the same spec `--format odps-v4.1`. |
| `--out` | Output file path, or `-` for stdout. Default stdout. With `bitol-1.0.0`, `--out FILE` writes the product document only; the sibling ODCS contracts are written only with `--out-dir`. |
| `--out-dir` | `bitol-1.0.0` only. Write the product document plus one ODCS contract per output port into this directory. Mutually exclusive with `--out`. |
| `--format`, `-f` | `yaml` (default) or `json`. Sets the format of files written with `--out` or `--out-dir`. Stdout always uses JSON. |
| `--env` | Environment name for overlay application. |
| `--validate-strict` / `--no-validate-strict` | `bitol-1.0.0` only. Validate the emitted documents against the vendored schemas. Default on; `--no-validate-strict` downgrades failures to warnings. |
| `--pretty` / `--compact` | `odps-4.1` only. Pretty-print or compact JSON. Default pretty. |

### `odps import`

Accepts three entry shapes: a single ODPS doc, a directory bundle (ODPS product + sibling ODCS files), or a lone ODCS file.

| Option | Description |
| --- | --- |
| `PATH` | Path to an ODPS doc, directory bundle, or ODCS file. |
| `--spec` | `bitol-1.0.0`. `odps-4.1` is export-only. |
| `--allow-remote` | Resolve `contractId` references via HTTP (SSRF-guarded — off by default). |
| `--lenient` | Downgrade an output port whose `contractId` cannot be resolved to a warning. Input ports are always lenient. Without it, an unresolved output-port `contractId` fails the import with exit 1. |
| `-f`, `--format` | `yaml` (default) or `json`. Format of the FLUID contract written. |
| `-o`, `--out` | Write the resulting FLUID contract to this path. Default stdout. |

### `odps validate`

| Option | Description |
| --- | --- |
| `FILE` | Path to an ODPS JSON/YAML file. |
| `--spec` | Spec to validate against. Default `bitol-1.0.0`. |
| `--full-schema` / `--no-full-schema` | `odps-4.1` only. Full JSON schema validation (requires `jsonschema`) or basic checks. Default full. |

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
fluid odps export contract.yaml --spec odps-4.1 --out product.odps.json

# Import a Bitol ODPS bundle (product + sibling ODCS files) back to FLUID
fluid odps import ./dist/odps-bundle/ -o recovered.fluid.yaml
# Import a product document on its own: output ports it cannot resolve become warnings
fluid odps import product.odps.yaml -o recovered.fluid.yaml --lenient

# Validate an existing ODPS file
fluid odps validate product.odps.yaml
fluid odps validate product.odps.json --spec odps-4.1

# List available specs
fluid odps info
fluid odps info --spec bitol-1.0.0 --json
```

## Round trip: export a bundle, import it back

Export to a directory, so the product document and the ODCS contracts its output ports point at land together:

```bash
fluid odps export contract.fluid.yaml --out-dir dist/odps
```

```text
✓ Exported Bitol ODPS v1.0.0: 1 product + 2 ODCS contract(s) → dist/odps
```

```text
dist/odps/
├── gold.customer.analytics_360_v1.odps.yaml
├── gold.customer.analytics_360_v1.customer_360_master.odcs.yaml
└── gold.customer.analytics_360_v1.high_value_customers.odcs.yaml
```

Import the directory:

```bash
fluid odps import dist/odps -o recovered.fluid.yaml
```

```text
✓ Imported dist/odps → recovered.fluid.yaml
```

Importing the product file alone fails, because `--out FILE` wrote no ODCS files beside it for its output ports:

```bash
fluid odps export contract.fluid.yaml --out p.odps.yaml
fluid odps import p.odps.yaml -o r.fluid.yaml
```

```text
❌ Error importing: Could not resolve contractId
'gold.customer.analytics_360_v1.customer_360_master'. Tried:
  gold.customer.analytics_360_v1.customer_360_master.odcs.yaml
  ...
```

The command exits 1. Add `--lenient` to import the document anyway, with each unresolved output port reported as a warning. The recovered contract then has no schema for those ports.

## How a port's `contractId` is resolved

`odps import` replaces each port's `contractId` with the ODCS contract it names. It looks, in order:

1. In a directory bundle, at the directory's ODCS contracts, matched by the `id` each one declares.
2. Beside the product document and in its `contracts/` subdirectory, at `<name>.odcs.yaml`, `<name>.odcs.yml`, `<name>.odcs.json` and `<name>.yaml`, where `<name>` is the whole `contractId`, then its part after the last dot. For `commerce.orders` that is `commerce.orders.odcs.yaml` first and `orders.odcs.yaml` later.
3. Over HTTP, only when the `contractId` is itself a URL and you pass `--allow-remote`.

*(unreleased, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* A file found in step 2 is used only when it declares the `contractId` as its `id`. An `orders.odcs.yaml` that declares `billing.orders` is skipped for `commerce.orders` with a warning naming both ids, and the search goes on. A bundle that relied on a file named after the port but declaring another id now fails a strict import, or skips the port under `--lenient` (an input port is always skipped). Make the port's `contractId` and the ODCS `id` agree.

*(unreleased, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* A `contractId` that cannot name a contract is an unresolved one, like a `contractId` no file matches: `--lenient` and input ports skip it with a warning, and a strict import fails with exit 1. That covers a NUL byte, a value that is not a string (`false` and `0` included), a segment longer than a file name may be, and an unparsable URL such as `http://[::1`. A missing or empty `contractId` leaves the port without a contract and no warning, as before.

### Files a directory bundle cannot read

*(unreleased, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* Every `.yaml`, `.yml` and `.json` file in the directory is read to find the product document, upper-case suffixes such as `PRODUCT.ODPS.YAML` included. A file that does not parse, or that the [YAML limits](./validate.md#yaml-limits) refuse, is skipped with a warning naming it. When no readable ODPS document is left, the import fails rather than importing the ODCS contracts on their own, because the skipped file may be the product:

```text
❌ Error importing: import_directory: found no readable ODPS doc in
dist/odps, and could not read 1 file(s) that may be it:
['dist/odps/product.odps.yaml']
```

Fix or remove the file the error names. An unreadable file next to a readable product document, such as a stray `docker-compose.yaml`, is only skipped.

## Spec at a glance

| `--spec` | Standard | Governed by | Typical use |
| --- | --- | --- | --- |
| `bitol-1.0.0` *(default)* | Open Data Product Standard v1.0.0 | [Bitol.io](https://bitol.io) | Entropy Data / DMM marketplace |
| `odps-4.1` | Open Data Product Specification v4.1 | LF / Open Data Product Initiative | ODPI-aligned catalogs |

::: warning Deprecation — `--spec odpi-4.1`
The old `--spec odpi-4.1` token (note the letter swap) is accepted with a WARNING and redirected to `odps-4.1`. Update any scripts that use `--spec odpi-4.1`.
:::

## Notes

- The default spec (`bitol-1.0.0`) is the **center-stage** format for Entropy Data and the Data Mesh Manager marketplace. Use it for day-to-day DMM publishing workflows.
- If the file passed to `validate` is a wrapped render envelope (contains an `artifacts` key), it is unwrapped automatically.
- `odps import` with a directory bundle resolves sibling ODCS files referenced by `contractId` — useful for round-tripping Bitol bundles produced by `fluid generate standard --format odps`.
- Bitol ODPS **v1.1.0** documents (RFC 0029 top-level `type`) are accepted on import since 0.13.1 — `sourceAligned` / `aggregate` / `consumerAligned` map bidirectionally to `metadata.productType` (SDP / ADP / CDP), and custom organisation types round-trip verbatim. To *emit* v1.1.0, use [`fluid odps-bitol export --api-version v1.1.0`](./odps-bitol.md) or set `ODPS_API_VERSION=v1.1.0`; the default stays v1.0.0 until Bitol cuts the release.
- For a one-shot export to file, see [`fluid export-odps`](./export-odps.md).
- For the Open Data Contract Standard, use [`fluid odcs`](./odcs.md).
- For ODPS publishing to Entropy Data / Data Mesh Manager, see [`fluid datamesh-manager publish`](./datamesh-manager.md).
