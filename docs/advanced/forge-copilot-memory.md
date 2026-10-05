# Forge Memory Guide

`fluid forge` remembers conventions at three scopes: your team, the project, and you. The team's file is committed to git and shared; the other two stay on one machine. A staged store under `~/.fluid/store/` mirrors them for other tools such as the MCP server, and holds forge history, audit records and semantic memory.

## The three scopes

| Scope | File | In git | Who writes it |
| --- | --- | --- | --- |
| Team | `.fluid/team-memory.yaml` in the workspace root | Yes: commit it | You, by hand |
| Project | `<product>/.fluid/copilot-memory.json` | No: per-engineer state | `fluid forge --save-memory` |
| Personal | `~/.fluid/personal-memory.json` | No | Forge, from your own runs; a plain JSON file you can edit or delete |

When two scopes disagree about a value, the higher one wins:

1. Explicit CLI flags and interview answers
2. The discovery report (the files on disk)
3. Team memory
4. Project memory
5. Personal memory
6. Built-in defaults

Memory is advisory. Current input, current catalog or DDL evidence, and validation gates win over anything saved.

## Team memory

Team memory is for what a team has already decided, so nobody has to answer the same question on every forge run.

```yaml
# .fluid/team-memory.yaml
conventions:
  naming:
    product_prefix: acme
    column_style: snake_case
  defaults:
    provider: gcp
    owner_team: data-platform

decisions:
  - date: "2026-01-15"
    decision: "Use BigQuery for all new analytics products"
    rationale: "Team has GCP expertise"

vocabulary:
  entities: [customer_id, order_id]
  measures: [total_revenue]
  dimensions: [order_date, region]
```

`fluid memory show team` prints what forge will use:

```console
$ fluid memory show team
{
  "conventions": {
    "naming": {
      "product_prefix": "acme",
      "column_style": "snake_case"
    },
    "defaults": {
      "provider": "gcp",
      "owner_team": "data-platform"
    }
  },
  "decisions": [
    {
      "date": "2026-01-15",
      "decision": "Use BigQuery for all new analytics products",
      "rationale": "Team has GCP expertise"
    }
  ],
  "vocabulary": {
    "entities": [
      "customer_id",
      "order_id"
    ],
    "measures": [
      "total_revenue"
    ],
    "dimensions": [
      "order_date",
      "region"
    ]
  }
}
```

### Where the file lives

The workspace root is the directory that holds `fluid.workspace.yaml`. `fluid forge` finds it from any subdirectory, and falls back to the current directory when there is no workspace file. The file is `.fluid/team-memory.yaml` inside that directory.

Forge scaffolds a starter file, with every key commented out except `column_style: snake_case` and `provider: local`, in three places: `fluid init`, the first `fluid forge` that finds none, and `fluid memory save --scope team`. The starter's header links to this page. Set `FLUID_FORGE_NO_TEAM_MEMORY_SCAFFOLD=1` to stop `fluid forge` from scaffolding it.

`fluid memory show team` and `fluid memory save --scope team` look only in the current directory's `.fluid/`. Run them from the workspace root: from a subdirectory, `show team` prints `{}`.

### How forge uses it

Entries under `conventions.defaults` act as soft defaults. A key is applied only when nothing higher in the precedence list already set it, and forge notes in its provenance that the value came from team memory. The whole file goes to the model as guidance for the contract draft: naming conventions, past decisions and vocabulary.

### What reaches the prompt

The file is shared through git, so what reaches the model is bounded:

| Limit | Value |
| --- | --- |
| File size | 64 KiB. A larger file is skipped with a warning. |
| Entries | At most 50 per `naming` map, `defaults` map and vocabulary list |
| String length | 500 characters per key, value, term or decision field |
| Decisions | At most 10; each needs a `decision` text |
| Values | Scalars only. A list or map as a value is dropped, and the file loads with a warning that says how many were dropped |

A file that is not valid YAML, or not a mapping, is skipped with a warning; forge carries on without it. Before 0.16.5 forge never read this file.

## Project and personal memory

Project memory records what past successful runs in this product produced: preferred template and provider, domains, owners, build engines, binding platforms and formats, schema summaries and recent outcomes. It lives at `<product>/.fluid/copilot-memory.json` and holds no raw rows or secrets. A file left at the old `runtime/.state/` location is ignored.

Flags on `fluid forge` control it:

```bash
fluid forge --show-memory      # print the summary and exit
fluid forge --save-memory      # persist memory after a successful run
fluid forge --no-memory        # skip memory for this run
fluid forge --reset-memory     # delete the memory file and exit
```

`--memory` is the default.

## The staged store

The `fluid memory` command works on the scopes and on the store:

```bash
fluid memory status                            # what the store holds
fluid memory show team                         # team, project or personal: read the file
fluid memory show semantic                     # episodic, semantic or history: list the store namespace
fluid memory save --scope project              # copy a scope into the store
fluid memory search semantic "customer order model"
fluid memory clear --ns memory/semantic
```

`fluid memory save --scope <project|team|personal>` copies a scope into the store under `memory/project`, `memory/team` or `memory/personal`, so other tools can read it. The file stays the source of truth.

```text
~/.fluid/store/
├── llm/
├── memory/
│   ├── project/
│   ├── team/
│   ├── personal/
│   ├── episodic/
│   └── semantic/
├── discovery/
├── skills/
├── history/
└── audit/
```

| Namespace | What it stores |
| --- | --- |
| `memory/project`, `memory/team`, `memory/personal` | Copies of the three scopes, written by `fluid memory save` |
| `memory/episodic` | Time-ordered forge episodes |
| `memory/semantic` | Similarity-searchable forged model summaries |
| `history` | Versioned artifact snapshots from write tools |
| `audit` | Catalog reads, MCP mutations, forge events and MCP output-port decisions |

Semantic memory is opt-in:

```bash
FLUID_COPILOT_SEMANTIC_MEMORY=1 fluid forge data-model from-intent intent.yaml -o out.fluid.yaml
```

`fluid memory clear` without `--older-than` removes every record in the namespace it names, or in the whole store when you give no `--ns`. Add `--older-than 30d` to remove only older records.

## Privacy and credentials

Memory is not a raw session dump. It should not contain:

- API keys
- tokens
- raw sample rows
- full source data extracts
- private keys

Catalog credentials live in the OS keyring and `~/.fluid/sources.yaml` references; MCP source-catalog calls pass credential ids, not raw secrets.

## Related guides

- [Forge discovery guide](./forge-copilot-discovery.md)
- [Forge Data Model](../forge-data-model.md)
- [MCP server](./mcp.md)
