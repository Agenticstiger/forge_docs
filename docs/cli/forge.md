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

## Mode picker, refine, compose

::: tip Available in 0.8.3
The 5-mode picker, `--refine`, `--from-product`, slash commands, preview panel, and the streaming contract preview ship in `0.8.3` (schema `0.7.3`). Pre-0.8.3 releases had the older single-shot interview shape.
:::

Bare `fluid forge` (TTY, no flags) lands on a 5-mode menu instead of dropping straight into AI:

```text
What kind of run is this?
  1. AI Copilot                  — full interview, LLM-driven (default for fresh products)
  2. Compose from existing       — build on top of products already in the workspace
  3. Refine a contract           — load a contract, ask 'what to change?'
  4. Template                    — start from one of the 5 built-in templates
  5. Blank scaffold              — empty contract, no AI
```

The picker pre-highlights based on a parallel welcome scan that runs in <50 ms. Skip with `FLUID_FORGE_NO_PICKER=1`.

### `--from-product` — composition

Pick one or more upstream products; Forge resolves them, validates composition rules (SDP rejects upstreams; ADP/CDP accept SDP+ADP — see [Product Types](/data-products/product-type.html#composition-rules)), and pre-fills `consumes[]`:

```bash
fluid forge --from-product bronze.crm_orders
fluid forge --from-product bronze.crm_orders --from-product bronze.crm_customers
fluid forge --from-product-list ./upstreams.json
```

### `--refine` — load a contract and tweak

```bash
fluid forge --refine                          # auto-discover from cwd
fluid forge --refine ./products/orders.fluid.yaml
```

Loads the contract, asks "what to change?", feeds the contract verbatim to the LLM as the seed. One question, no full interview.

### Slash commands inside the interview

| Command | Effect |
|---|---|
| `:ai-setup` | Re-run AI provider setup mid-interview |
| `:override` | Switch engine / restart / export state |
| `:show-work` | Toggle live streaming of agent reasoning + tool calls |
| `:doctor` | Inline `fluid doctor` |
| `:help` | List commands |
| `:quit` | Abort gracefully (saves partial state) |

### Pre-write preview panel

Before any file is written, Forge renders a panel showing files, cost, and run-id so users see exactly what they're about to commit to. `--yes` skips the confirmation prompt but the panel still renders. Suppress with `FLUID_FORGE_NO_PREVIEW=1`.

For the full picture see [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html).

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
