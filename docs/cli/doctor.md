# `fluid doctor`

Run built-in health checks for the CLI and local environment.

## Syntax

```bash
fluid doctor
```

## Key options

| Option | Description |
| --- | --- |
| `--out-dir` | Output directory for diagnostics |
| `--features-only` | Only check FLUID feature availability |
| `--extended`, `--comprehensive` | Run optional extended diagnostics |
| `--verbose`, `-v` | Detailed output |

## Examples

```bash
fluid doctor
fluid doctor --verbose
fluid doctor --extended
fluid doctor --features-only
```

## Notes

- In `0.7.9`, the default doctor experience is self-contained. Use `--extended` when you explicitly want the optional workspace diagnostics path.
