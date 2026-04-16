# `fluid demo`

Create and run a working customer-360 example with sample data — local DuckDB, no API key, no cloud account.

## Syntax

```bash
fluid demo [NAME] [--dry-run] [--no-run] [--quiet]
```

## Key options

| Option | Description |
| --- | --- |
| `NAME` | Directory name for the demo project (positional, optional, default: `fluid-demo`). |
| `--dry-run` | Preview what would be created without doing it. |
| `--no-run` | Scaffold the project but skip running the pipeline. |
| `--quiet`, `-q` | Suppress the next-steps panel and other post-success hints. |

## Examples

```bash
fluid demo
fluid demo my-customer-360
fluid demo --dry-run
fluid demo my-project --no-run
```

## Notes

- The fastest "see it working" path — scaffolds a real `contract.fluid.yaml` with sample data, validates, plans, and runs end-to-end via DuckDB in roughly 30 seconds.
- Always runs against the `local` provider; the demo never deploys to a cloud account.
- Refuses to write into a symlinked target or a non-empty existing directory — pick a different name or remove the directory first.
- After it finishes, you have a normal project — try [`fluid validate`](./validate.md), [`fluid plan`](./plan.md), and [`fluid apply`](./apply.md) inside it.
- For the AI-guided scaffold path use [`fluid init`](./init.md) or [`fluid forge`](./forge.md) instead.
