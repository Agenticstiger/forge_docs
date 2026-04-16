# `fluid bundle`

Resolve a multi-file contract into a single bundled document.

## Syntax

```bash
fluid bundle CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--out`, `-o` | Output path, default stdout |
| `--env`, `-e` | Apply an environment overlay after ref resolution |
| `--format`, `-f` | Output format, `yaml` or `json` |

## Examples

```bash
fluid bundle contract.fluid.yaml
fluid bundle contract.fluid.yaml --out bundled.yaml
fluid bundle contract.fluid.yaml --env prod
fluid bundle contract.fluid.yaml --format json
```

## Notes

- Use `bundle` to inspect or ship a resolved contract after fragmenting with [`fluid split`](./split.md).
