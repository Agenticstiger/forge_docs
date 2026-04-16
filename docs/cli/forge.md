# `fluid forge`

Use AI-assisted scaffolding when you want domain hints, local discovery, or project memory during project creation.

## Syntax

```bash
fluid forge [OPTIONS]
```

## Key options

### Project

| Option | Description |
| --- | --- |
| `--target-dir`, `-d DIR` | Target directory for project creation |
| `--provider`, `-p NAME` | Provider hint |
| `--domain NAME` | Domain hint such as `finance`, `healthcare`, `retail`, or `telco` |
| `--blank` | Create an empty contract without LLM help |
| `--dry-run` | Preview without creating files |
| `--non-interactive` | Use defaults without prompting |
| `--context VALUE` | Additional JSON context or a path to a context file |

### AI config

| Option | Description |
| --- | --- |
| `--llm-provider NAME` | LLM provider |
| `--llm-model NAME` | Model identifier |
| `--llm-endpoint URL` | Override the model endpoint |

### Discovery and memory

| Option | Description |
| --- | --- |
| `--discover` | Inspect local files before generation |
| `--no-discover` | Skip local discovery |
| `--discovery-path PATH` | Add extra paths to scan |
| `--memory` | Load copilot memory |
| `--no-memory` | Skip memory for this run |
| `--save-memory` | Persist memory after a successful run |
| `--show-memory` | Print memory summary and exit |
| `--reset-memory` | Delete memory and exit |

## Examples

```bash
fluid forge
fluid forge --provider gcp
fluid forge --domain finance
fluid forge --llm-provider openai --llm-model gpt-4o-mini
fluid forge --blank --target-dir ./out
```

## Notes

- The current promoted syntax is `fluid forge`, not `fluid forge --mode copilot`.
- Use `--domain` for built-in domain guidance instead of the older `--mode agent` flow shown in some legacy docs.
- Discovery and memory guides live in the advanced docs: [discovery](/advanced/forge-copilot-discovery) and [memory](/advanced/forge-copilot-memory).

## Industry skills — `fluid skills`

`--domain` gives the copilot a high-level role (finance, healthcare, retail, telco). For deeper domain knowledge — the vocabulary, typical data products, standard fact tables, regulatory constraints of an industry — install an **industry skills pack**. Skills live in `.fluid/skills.yaml` inside the project; the compiled form `.fluid/skills.compiled.json` is what the copilot loads at runtime.

```bash
fluid skills <action>
```

### Subcommands

| Subcommand | What it does |
| --- | --- |
| `fluid skills install [INDUSTRY]` | Install a bundled skills pack. `INDUSTRY` is one of `telco`, `retail`, `healthcare`, `finance`. Omit for interactive selection. |
| `fluid skills show` | Display the current industry skills file |
| `fluid skills compile` | Pre-compile `.fluid/skills.yaml` into `.fluid/skills.compiled.json` for faster copilot runs |
| `fluid skills update` | Refresh the tools section of `.fluid/skills.yaml` to match the current CLI version |

### Examples

```bash
fluid skills install telco
fluid skills show
fluid skills compile
fluid skills update
```

Run `fluid skills compile` after any manual edit to `skills.yaml` to keep the compiled form in sync. `fluid skills update` is the right command after upgrading the CLI — it rewrites the tools list so the copilot sees the newest `fluid_*` entries.
