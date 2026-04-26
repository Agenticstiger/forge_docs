# MCP Server

`fluid mcp serve` exposes the staged forge pipeline as a stdio MCP server for clients such as Claude Code, Cursor, Continue, and VS Code MCP integrations. It is a foreground process: no daemon, no HTTP port, and no background service.

## Start the server

```bash
fluid mcp serve
```

For read-only inspection:

```bash
fluid mcp serve --read-only
```

For scoped write access:

```bash
fluid mcp serve \
  --readable-paths ./forge-output \
  --writable-paths ./forge-output \
  --writable-namespaces history,audit
```

## Access controls

Every `tools/call` is checked by policy before it executes.

| Control | Flag | What it does |
| --- | --- | --- |
| Read-only mode | `--read-only` | Rejects every mutating tool |
| Read scope | `--readable-paths PATH[,PATH...]` | Path-based read tools may only inspect files below these roots |
| Tool allowlist | `--allow-tools TOOL[,TOOL...]` | Hides and blocks tools outside the allowlist |
| Tool blocklist | `--deny-tools TOOL[,TOOL...]` | Blocks named tools; denial wins over allow |
| Filesystem scope | `--writable-paths PATH[,PATH...]` | Mutating tools may only write below these roots |
| Store scope | `--writable-namespaces NS[,NS...]` | Mutating tools may only write listed store namespaces |

The default readable and writable path is the current working directory. The default writable namespaces are `history,audit`.

## Tools

| Tool | Mode | What it does |
| --- | --- | --- |
| `read_logical_model` | read | Load a `.model.json` sidecar and return the typed logical model |
| `validate_contract` | read | Validate a Fluid contract or forged model sidecar |
| `diff_models` | read | Compare two logical model sidecars |
| `search_semantic_memory` | read | Search the semantic memory namespace for similar prior models |
| `update_entity` | write | Rename or update one logical model entity |
| `add_relationship` | write | Add a relationship to a logical sidecar |
| `regenerate_physical` | write | Regenerate the contract and physical fanout from a logical sidecar |
| `list_source_adapters` | read | List available source-catalog adapters |
| `list_source_tables` | read | Enumerate tables from a configured source catalog |
| `inspect_source_table` | read | Inspect a source table profile and metadata |
| `list_source_lineage` | read | Read lineage from a configured source catalog |
| `list_source_glossary` | read | Read glossary terms from a configured source catalog |
| `forge_from_source` | write | Forge a contract and `.model.json` sidecar from a configured source catalog |

Every advertised tool includes an MCP `inputSchema`, so clients can provide typed autocomplete and validate arguments before dispatch.

## Claude Code example

```json
{
  "mcpServers": {
    "fluid-forge": {
      "command": "fluid",
      "args": [
        "mcp",
        "serve",
        "--read-only"
      ],
      "env": {
        "FLUID_QUIET": "1"
      }
    }
  }
}
```

Remove `--read-only` and add both `--readable-paths` and `--writable-paths` when you want the client to patch model sidecars or regenerate artifacts inside a specific workspace directory.

## Cursor example

```json
{
  "mcp.servers": {
    "fluid-forge": {
      "command": "fluid",
      "args": ["mcp", "serve"],
      "env": {
        "FLUID_QUIET": "1"
      }
    }
  }
}
```

`FLUID_QUIET=1` is important because stdout is reserved for MCP JSON-RPC frames.

## Credential handling

The MCP wire format does not accept inline catalog credentials. Source-catalog tools resolve credentials from saved Fluid source configs, environment variables, or explicit credential IDs that were configured outside the MCP call.

Set up a source first:

```bash
fluid ai setup --source snowflake --name snowflake-prod
```

Then an MCP client can call `forge_from_source` with `source: "snowflake"` and `credentials.credential_id: "snowflake-prod"` without receiving raw secrets.

## Certification

Before publishing a release, run:

```bash
PYTHONPATH=. python scripts/mcp_client_certify.py
```

The certification script checks the JSON-RPC lifecycle, `tools/list`, `tools/call`, MCP Inspector when available, and Claude Code config health when the `claude` CLI is installed. Optional client checks are skipped when their tools are not installed; protocol failures fail the script.
