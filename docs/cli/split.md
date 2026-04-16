# `fluid split`

Split a flat contract into a fragment-first layout.

## Syntax

```bash
fluid split CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--out`, `-o` | Output directory |
| `--dry-run` | Preview the split without writing files |

## Examples

```bash
fluid split contract.fluid.yaml
fluid split contract.fluid.yaml --dry-run
fluid split contract.fluid.yaml --out ./contracts
```
