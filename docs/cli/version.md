# `fluid version`

Show the CLI release and, optionally, more environment detail.

## Syntax

```bash
fluid version
```

## Key options

| Option | Description |
| --- | --- |
| `--verbose`, `-v` | Show detailed system information |
| `--format` | Output format, `text` or `json` |
| `--short` | Print only the version number |

## Examples

```bash
fluid version
fluid version --verbose
fluid version --format json
fluid version --short
```

## Notes

- `fluid version` reports the CLI release, such as `0.7.9`.
- That is separate from `fluidVersion` inside `contract.fluid.yaml`.
