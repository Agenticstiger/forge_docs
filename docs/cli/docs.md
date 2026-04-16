# `fluid docs`

Generate a static index of FLUID contracts found under a source tree.

## Syntax

```bash
fluid docs [--src DIR] [--out DIR]
```

## Key options

| Option | Description |
| --- | --- |
| `--src` | Root directory to scan for contracts. Default `products`. |
| `--out` | Docs output folder. Default `docs`. |

## Examples

```bash
fluid docs
fluid docs --src services --out site/docs
```

## Notes

- Walks `<src>/**/contract.fluid.*` recursively and writes a single `index.json` listing each contract path under `<out>/`.
- This is a minimal indexer, not a full static-site generator. The output is intended to be consumed by an external docs site or a downstream renderer.
- Output directories are created automatically.
- For a full data-product summary view, see [`fluid status`](./status.md).
