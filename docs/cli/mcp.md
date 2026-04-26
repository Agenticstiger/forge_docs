# `fluid mcp`

Run the Fluid Forge MCP stdio server so MCP-compatible clients can inspect, validate, and carefully edit forge artifacts.

## Syntax

```bash
fluid mcp                                                                   # interactive guide (no subcommand → friendly panel)
fluid mcp serve [--read-only]
fluid mcp serve [--allow-tools TOOL[,TOOL...]] [--deny-tools TOOL[,TOOL...]]
fluid mcp serve [--readable-paths PATH[,PATH...]] [--writable-paths PATH[,PATH...]]
fluid mcp serve [--writable-namespaces NS[,NS...]]
```

::: tip Bare invocation is friendly
Running `fluid mcp` with no subcommand renders a Rich panel describing the
single `serve` action and surfaces `fluid mcp serve --read-only` as the
recommended quick-start.
:::

## Recommended start

For review-only client sessions:

```bash
FLUID_QUIET=1 fluid mcp serve --read-only
```

For a scoped workspace where the client may update generated model sidecars and regenerate artifacts:

```bash
FLUID_QUIET=1 fluid mcp serve \
  --readable-paths ./forge-output \
  --writable-paths ./forge-output \
  --writable-namespaces history,audit
```

`FLUID_QUIET=1` keeps stdout reserved for MCP JSON-RPC frames.

## Access controls

| Flag | Purpose |
| --- | --- |
| `--read-only` | Reject all mutating tools. |
| `--allow-tools` | Advertise and allow only the named tools. |
| `--deny-tools` | Block the named tools; denial wins over allow. |
| `--readable-paths` | Limit path-based read tools to these roots. |
| `--writable-paths` | Limit file writes to these roots. |
| `--writable-namespaces` | Limit staged-store writes to these namespaces. |

Inline catalog credentials are blocked by default. Configure source credentials outside MCP and pass credential ids from the client.

## Related guides

- [Advanced MCP server guide](../advanced/mcp.md)
- [AI Forge And Data-Model Journeys](../walkthrough/ai-forge-data-model.md)
- [Forge Memory Guide](../advanced/forge-copilot-memory.md)
