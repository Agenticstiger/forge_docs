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
fluid forge --llm-provider openai --llm-model gpt-4.1-mini
fluid forge --llm-provider gemini --tiered --require-llm
fluid forge --blank --target-dir ./out
```

For a guided walkthrough of every public forge journey, see [AI Forge And Data-Model Journeys](../walkthrough/ai-forge-data-model.md).

## Forging a data model

The model-first path is `fluid forge data-model`. It writes a Fluid contract, a `.model.json` logical sidecar, and a human-readable Mermaid + Markdown model document.

```bash
fluid forge data-model from-intent intent.yaml -o customer_orders.fluid.yaml
fluid generate transformation customer_orders.fluid.yaml -o ./dbt_customer_orders --dbt-validate
```

::: tip See it run
The 60-second [Fluid Forge in action](/forge_docs/see-it-run.html#the-60-second-walkthrough) reel runs exactly this command against four LLM providers and shows the resulting contract — every token count is captured live.
:::

Use `from-intent` for YAML/JSON business intent files, `from-ddl` for SQL DDL, and `from-source` for configured metadata catalogs.

The intent format is discoverable from the CLI:

```bash
fluid forge data-model from-intent --example
fluid forge data-model from-intent --example retail
fluid forge data-model from-intent --example telco
fluid forge data-model from-intent --example finance
fluid forge data-model from-intent --schema
fluid forge data-model from-intent --validate intent.yaml
```

See the [Forge Data Model guide](../forge-data-model.md) for the field mapping, generated artifacts, deterministic mode, strict LLM mode, and dbt generation flow.

For hosted provider smoke tests, export a provider key in your shell and use `--require-llm`. Do not paste API keys into command examples, contracts, intent files, or docs.

## Forging from a source catalog

If your team already maintains rich metadata (descriptions, tags,
lineage, classifications) in a data catalog, you can skip the
intent / DDL inputs entirely and forge **directly from the catalog**:

```bash
fluid ai setup --source snowflake --name snowflake-prod      # one-time setup
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB --schema SEEDED \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml
```

Seven catalogs are supported — Snowflake Horizon, Databricks Unity,
BigQuery, Dataplex, AWS Glue, DataHub, Data Mesh Manager. Each
ships with privilege grant scripts, auth methods, and an
end-to-end demo. See the **[catalogs index](catalogs/README.md)**
for the full list.

The same flow is exposed via the MCP `forge_from_source` tool, so
Claude Code / Cursor agents can drive a catalog forge from inside
the editor.

## Multi-turn agent loop — `--agent-loop`

Add `--agent-loop` to use the multi-turn agent loop instead of the single-shot prompt. The LLM discovers your workspace, picks a template, builds and validates the contract iteratively via tool calls. Requires a tool-use-capable model (`gpt-4.1-mini`, `claude-sonnet-4-6`, `gemini-2.5-flash`).

```bash
fluid forge --agent-loop --domain retail --target-dir ./demo
fluid forge --agent-loop --llm-provider anthropic --llm-model claude-sonnet-4-6
```

<iframe
  src="/forge_docs/reels/agent-loop-live.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Agent loop, live — Fluid Forge">
</iframe>

The 60-second reel above traces a single `--agent-loop` run turn-by-turn: workspace inspection → template list → template intent read → scaffold → self-validate → done. Six turns, five tool calls, $0.018 cost. See [Agentic primitives](/forge_docs/advanced/agentic-primitives.html) for the underlying framework, [Capability Warnings](/forge_docs/advanced/capability-warnings.html) for the per-model tool-use accuracy notes, and [Forge Tools](/forge_docs/advanced/forge-tools.html) for the `@forge_tool` decorator that powers the tool calls.

## Notes

- The current promoted syntax is `fluid forge`, not `fluid forge --mode copilot`.
- Use `--domain` for built-in domain guidance instead of the older `--mode agent` flow shown in some legacy docs.
- Discovery and memory guides live in the advanced docs: [discovery](/forge_docs/advanced/forge-copilot-discovery) and [memory](/forge_docs/advanced/forge-copilot-memory).

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
