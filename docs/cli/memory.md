# `fluid memory`

Inspect and manage the staged memory store used by AI-assisted forge runs, MCP tools, audit capture, and model reuse.

## Syntax

```bash
fluid memory                                                                # interactive guide (no subcommand → friendly panel)
fluid memory status
fluid memory show {project|team|personal|episodic|semantic|history} [--limit N]
fluid memory save --scope {project|team|personal}
fluid memory search QUERY [--ns NAMESPACE] [--mode exact|keyword|vector|hybrid]
fluid memory clear [--ns NAMESPACE] [--older-than DURATION]
```

::: tip Bare invocation is friendly
Running `fluid memory` with no subcommand renders a Rich panel listing every
verb with a one-line description and a quick-start. When `~/.fluid/store/`
already exists, the guide highlights `status` as the recommended next step.
:::

## Common flows

Check whether memory is enabled and where the store lives:

```bash
fluid memory status
```

Review project-scoped preferences:

```bash
fluid memory show project
```

Search prior semantic model summaries:

```bash
fluid memory search "customer order model" --ns memory/semantic --mode hybrid
```

Clear old episodic records without wiping the whole store:

```bash
fluid memory clear --ns memory/episodic --older-than 30d
```

## Notes

- Memory is advisory. Explicit CLI flags, current intent files, source metadata, DDL evidence, and validators take precedence.
- Memory must not be used for API keys, passwords, private keys, raw sample rows, or source-data extracts.
- Semantic memory for forge data-model runs is opt-in with `FLUID_COPILOT_SEMANTIC_MEMORY=1`.
- For the storage layout and privacy model, see [Forge Memory Guide](../advanced/forge-copilot-memory.md).
