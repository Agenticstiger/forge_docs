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
