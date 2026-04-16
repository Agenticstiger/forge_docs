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

## Fastest path — `fluid demo`

If you want to *see* FLUID working end-to-end in about 30 seconds rather than create your own project first, use `fluid demo`. It scaffolds a working customer-360 example with sample data **and** runs the pipeline immediately — zero setup, no API key, no cloud account, local DuckDB.

```bash
fluid demo [NAME]
```

### Options

| Option | Description |
| --- | --- |
| `NAME` | Directory name for the demo project (positional, optional). Default: `customer-360`. |
| `--dry-run` | Preview what would be created without writing anything |
| `--no-run` | Scaffold the project but skip running the pipeline |
| `--quiet`, `-q` | Suppress post-success hints |

### Examples

```bash
fluid demo
fluid demo my-customer-360
fluid demo --dry-run
fluid demo my-project --no-run
```

After `fluid demo` completes you have a normal FLUID project — `fluid validate`, `fluid plan`, `fluid apply` all work against it. Use `--no-run` when you want to inspect the generated contract and SQL before executing the pipeline.
