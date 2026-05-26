# `fluid odps-bitol`

Export FLUID contracts to and validate Bitol.io's ODPS (Open Data Product Standard) v1.0 format, used for marketplace integrations such as Entropy Data.

::: tip Use `fluid odps` for new workflows
Since v0.8.4, the unified [`fluid odps`](./odps.md) command dispatches between Bitol 1.0.0 and LF/ODPI 4.1 via `--spec`, and adds an `import` subcommand. `fluid odps-bitol` remains for backward compatibility and more explicit Bitol-only workflows.
:::

## Syntax

```bash
fluid odps-bitol export CONTRACT [--output PATH] [--format FMT] [--no-custom]
fluid odps-bitol validate ODPS_FILE
fluid odps-bitol info
```

## Key options

### `odps-bitol export`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file. |
| `--output`, `-o` | Output file path. Default `<contract-name>-odps.<format>`. |
| `--format`, `-f` | Output format: `yaml` or `json`. Default `yaml`. |
| `--no-custom` | Exclude custom properties from the output. |

### `odps-bitol validate`

| Option | Description |
| --- | --- |
| `ODPS_FILE` | Path to an ODPS-Bitol data product file. |

### `odps-bitol info`

No options. Prints provider information (version, spec URL, capabilities).

## Examples

```bash
fluid odps-bitol export contract.fluid.yaml
fluid odps-bitol export contract.fluid.yaml -o product.json -f json
fluid odps-bitol validate product.yaml
fluid odps-bitol info
```

## Unified `fluid odps` (since v0.8.3, renamed from `fluid opds` in v0.8.4)

The unified `fluid odps` command dispatches between Bitol 1.0.0 and LF/ODPI 4.1 via `--spec`, and adds an `import` subcommand:

```bash
fluid odps export <contract> [--spec bitol-1.0.0|odps-v4.1] [--out PATH] [--out-dir DIR]
fluid odps import <path>     [--spec bitol-1.0.0] [--allow-remote] [-o PATH]
fluid odps validate <file>   [--spec ...]
fluid odps info              [--spec ...]
```

`fluid odps import` accepts three entry shapes — single ODPS doc, directory bundle (ODPS + sibling ODCS files), or a lone ODCS file. Remote `contractId` references are off by default; opt in with `--allow-remote` (SSRF-guarded — see [network safety](/forge_docs/advanced/network-safety.html)).

::: tip `--spec` rename in v0.8.4
`--spec odpi-4.1` (the old LF/ODPI token, note the letter swap) is accepted with a WARNING and redirected to `--spec odps-v4.1`. Update any scripts that use the old token.
:::

## Notes

- Despite the source file being named `odps_standard.py`, the canonical command name registered in `fluid --help` is `odps-bitol`. This avoids confusion with the LF/ODPI variant.
- For the unified dispatch (Bitol + LF/ODPI), use [`fluid odps`](./odps.md).
- For the Open Data Contract Standard (ODCS), use [`fluid odcs`](./odcs.md).
- Validation checks `apiVersion` (`v1.0.0` expected), requires `kind: DataProduct`, and verifies output ports have a `name` field.
