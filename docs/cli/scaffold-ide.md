# `fluid scaffold-ide`

Generate agentic-IDE configuration so an AI-assisted editor can drive Fluid Forge — steering rules, hooks, and an MCP server entry, written from one pack.

## Syntax

```bash
fluid scaffold-ide [--target {kiro,cursor,claude-code,cline,generic}] [--out DIR] [--python PATH] [--force]
```

## Key options

| Option | Description |
| --- | --- |
| `--target` | Which agentic IDE to scaffold for — `kiro`, `cursor`, `claude-code`, `cline`, or `generic`. Default `kiro`. |
| `--out` | Workspace root to scaffold into. Default the current directory. |
| `--python` | Path to the Python interpreter `fluid` is installed under. Baked into the generated MCP config so the IDE can launch `fluid mcp serve` without relying on `PATH`. Default `sys.executable`. |
| `--force` | Overwrite existing files. Off by default, so re-runs stay safe. |

## Examples

```bash
fluid scaffold-ide --target claude-code
fluid scaffold-ide --target cursor --out ../my-workspace
fluid scaffold-ide --target generic --force
```

## What it generates

Each target gets the same configuration pack in that editor's layout. The files written by 0.18.1, measured by running each target into an empty directory:

| `--target` | Writes |
| --- | --- |
| `kiro` | `.kiro/steering/01-forge-cli.md` to `04-guardrails.md` (four files), `.kiro/hooks/on-save-contract.md`, `.kiro/hooks/pre-commit-bundle.md`, `.kiro/specs/first-data-product.md`, `.kiro/settings/mcp.json` |
| `cursor` | `.cursor/rules/01-forge-cli.mdc` to `04-guardrails.mdc` (four files), `.cursor/mcp.json`, `.cursor/HOOKS.md` |
| `claude-code` | `CLAUDE.md`, `.mcp.json`, `.claude/settings.json` |
| `cline` | `.clinerules/01-forge-cli.md` to `04-guardrails.md` (four files), `.clinerules/MCP_SETUP.md`, `.cline/mcp_settings.json` |
| `generic` | `AGENTS.md`, `mcp.json`, `.ai/steering/01-forge-cli.md` to `04-guardrails.md` (four files) |

The pack covers three things: **steering / rules** so the editor's agent understands FLUID contracts and the forge workflow, **hooks** that run the right `fluid` commands at the right time (written as files for `kiro`, and as `.cursor/HOOKS.md` for `cursor`), and an **MCP server entry** pointing at [`fluid mcp serve`](./mcp.md) for the typed forge tools. Choose `generic` for any MCP-capable editor that is not one of the named four.

### Files that already exist

Running into a workspace that has files of its own:

- A root `CLAUDE.md` or `AGENTS.md` is kept, and the pack's section is appended to it between `<!-- BEGIN forge-cli scaffold-ide block -->` and `<!-- END forge-cli scaffold-ide block -->`.
- An existing MCP file (`mcp.json`) or steering file stops the run with `refusing_to_overwrite_existing_file_pass_force_to_override`, which is also what a second run into a directory the first run filled hits. Pass `--force` to write them again.
- The files are written in order and the run stops at the first one that exists, so a refusal can come after some files were already written. With an existing `.ai/steering/01-forge-cli.md`, `--target generic` had already written `mcp.json` and `AGENTS.md`.
- `--force` replaces a file with the pack's version, and does not merge. A root `CLAUDE.md` or `AGENTS.md` loses its other text, and an MCP file such as `.mcp.json` loses servers other than `fluid`. Commit or copy those first.

## Notes

- This is the editor half of the agentic-IDE workflow; the CLI half is [`fluid forge --agent`](./forge.md#headless-agent-mode), which drives Forge headlessly with JSON-Lines progress output.
- The generated MCP server can route LLM calls back through the editor (see [LLM sampling](../advanced/mcp.md#llm-sampling)), so an agentic IDE can run a full AI-assisted forge on its own subscription — no second API key.

## See also

- [`fluid forge`](./forge.md) — AI-assisted scaffolding, including headless `--agent` mode
- [`fluid mcp`](./mcp.md) — the MCP server the generated IDE config points at
- [`fluid scaffold-ci`](./scaffold-ci.md) — the equivalent generator for CI pipelines
- [Advanced MCP server guide](../advanced/mcp.md)
