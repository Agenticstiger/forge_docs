# Forge Memory Guide

Forge memory now lives in the staged store under `~/.fluid/store/`. The store is shared by forge data-model runs, MCP tools, provider scorecards, and audit/history capture.

## CLI entry point

```bash
fluid memory status
fluid memory show project
fluid memory show semantic
fluid memory search semantic "customer order model"
fluid memory clear --ns memory/semantic
```

The command group is:

```bash
fluid memory <status|show|save|clear|search>
```

## Store layout

```text
~/.fluid/store/
├── llm/
├── memory/
│   ├── project/
│   ├── team/
│   ├── episodic/
│   └── semantic/
├── discovery/
├── skills/
├── history/
└── audit/
```

| Namespace | What it stores |
| --- | --- |
| `memory/project` | Project-scoped preferences and summaries |
| `memory/team` | Shared team conventions when configured |
| `memory/episodic` | Time-ordered forge episodes |
| `memory/semantic` | Similarity-searchable forged model summaries |
| `history` | Versioned artifact snapshots from write tools |
| `audit` | Catalog reads, MCP mutations, and forge events |

Semantic memory is opt-in:

```bash
FLUID_COPILOT_SEMANTIC_MEMORY=1 fluid forge data-model from-intent intent.yaml -o out.fluid.yaml
```

## What memory does

When enabled, memory helps Forge remember stable preferences such as:

- project naming conventions
- preferred modeling technique
- prior source/catalog scopes
- recurring entity vocabulary
- prior model patterns that can improve later drafts

Memory remains advisory. Explicit CLI flags, current user input, current catalog/DDL evidence, and validation gates win over saved memory.

## Privacy and credentials

Memory is not a raw session dump. It should not contain:

- API keys
- tokens
- raw sample rows
- full source data extracts
- private keys

Catalog credentials live in the OS keyring and `~/.fluid/sources.yaml` references; MCP source-catalog calls pass credential ids, not raw secrets.

## Legacy memory

Older workspaces may still contain:

```text
.fluid/copilot-memory.json
```

The current CLI can read that legacy file with a one-time notice, but new writes land in `~/.fluid/store/memory/project/`.

## Related guides

- [Forge discovery guide](./forge-copilot-discovery.md)
- [Forge Data Model](../forge-data-model.md)
- [MCP server](./mcp.md)
