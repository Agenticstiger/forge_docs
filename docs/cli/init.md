# `fluid init`

Create a new project with the fastest local-first path into Fluid Forge.

## Syntax

```bash
fluid init NAME
```

## Key options

| Option | Description |
| --- | --- |
| `--quickstart` | Create a working example with sample data |
| `--blank` | Create an empty project skeleton |
| `--template NAME` | Create from a named template |
| `--list-templates` | Show available templates and exit |
| `--provider` | Target provider, defaulting to local |
| `--yes`, `-y` | Skip confirmation prompts |
| `--dry-run` | Preview what would be created |
| `--dir`, `-C` | Initialize in a specific directory |
| `--quiet`, `-q` | Suppress post-success hints |
| `--agent NAME` | Scaffold a custom domain agent spec in `.fluid/agents/` |

## Examples

```bash
fluid init my-project
fluid init my-project --quickstart
fluid init my-project --template customer-360
fluid init --list-templates
fluid init my-project --provider snowflake
```

## Notes

- The promoted newcomer path is `fluid init ... --quickstart`, then `validate`, `plan`, and `apply`.
- Current scaffolds emit contracts using `fluidVersion: 0.7.2`.
- If you want AI-assisted scaffolding instead, use [`fluid forge`](./forge.md).
