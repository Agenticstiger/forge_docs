# `fluid scaffold-ide`

Generate agentic-IDE configuration so an AI-assisted editor can drive Fluid Forge — steering rules, hooks, and an MCP server entry, written from one pack.

Needs the `mcp` extra: `pip install 'data-product-forge[mcp]'`. *(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* Without it the command writes nothing, prints that line and exits 1 with `[ERR_MCP_SDK_UNAVAILABLE]`, because every entry it writes launches `fluid mcp serve`.

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

### The Claude Code validate hook

*(since 0.29.0, [forge-cli #851](https://github.com/Agenticstiger/forge-cli/pull/851))* `--target claude-code` also copies the FLUID agent skills into `.claude/skills/`, and writes a `PostToolUse` hook into `.claude/settings.local.json` instead of the `.claude/settings.json` in the table above. The hook names this machine's Python, so it goes in the personal settings file, and the run adds that file to `.gitignore`. An existing `.claude/settings.local.json` keeps its other settings, and a second run with `--force` replaces the hook instead of adding another. The `fluid` Claude Code plugin runs the same hook script; install it with `/plugin marketplace add Agenticstiger/forge-cli`, then `/plugin install fluid@forge-cli`.

After each `Edit` or `Write` of a file whose name ends in `.fluid.yaml`, `.fluid.yml` or `.fluid.json`, the hook runs `fluid validate <file> --offline` and tells the agent what it found. It runs the `fluid` next to the Python that runs the hook, or else the first one on `PATH`, and never one in the project directory, where the agent writes. *On forge-cli `main`, not yet in a release ([forge-cli #880](https://github.com/Agenticstiger/forge-cli/pull/880)).* It adds `--format json`, and reads each finding's code, pointer and fix from [`issues`](./validate.md#finding-codes-and-issues):

| Result | What the agent gets |
| --- | --- |
| The contract fails | Exit 2, which Claude Code shows the agent. *On forge-cli `main`, not yet in a release ([forge-cli #880](https://github.com/Agenticstiger/forge-cli/pull/880)).* One line per error and warning, with its code and [pointer](./validate.md#finding-codes-and-issues), then its fix. In 0.30.1 and earlier, the text that `fluid validate` prints. |
| It passes, with warnings | *On forge-cli `main`, not yet in a release ([forge-cli #880](https://github.com/Agenticstiger/forge-cli/pull/880)).* The warnings, the same way, as `additionalContext`, with exit 0, so the edit is not blocked. In 0.30.1 and earlier, nothing. |
| It passes with no warning | Nothing. |
| No `fluid` is found, or `fluid validate` takes more than 60 seconds | Exit 2, with the command to run by hand. |

*On forge-cli `main`, not yet in a release ([forge-cli #880](https://github.com/Agenticstiger/forge-cli/pull/880)).* A contract that passes with warnings reaches the agent like this, as the `hookSpecificOutput.additionalContext` of the `PostToolUse` event (two of its four warnings shown):

```text
fluid validate passed for /work/contract.fluid.yaml, with warnings that fail --strict:
...
- ERR_CONTRACT_PLACEHOLDER_EMAIL at /metadata/owner/email: metadata.owner.email: 'owner@example.com' is a placeholder address: example.com is reserved for documentation (RFC 2606), so no mailbox is at it. Use the owning team's real address, never a guess; if there is none, delete the key (it is optional).
- ERR_CONTRACT_PLACEHOLDER_VALUE at /description: description: 'TODO' is a placeholder, not a value. Write the real value, or delete the key when it is optional; when it is required and nothing gives it, say so rather than make one up.
...
Fix each one with what the request gives; never invent a value to silence a warning.
```

*On forge-cli `main`, not yet in a release ([forge-cli #880](https://github.com/Agenticstiger/forge-cli/pull/880)).* A contract that fails reaches the agent like this:

```text
fluid validate failed for /work/contract.fluid.yaml:
- ERR_CONTRACT_SCHEMA_UNKNOWN_FIELD at /exposes/0/binding/formatt: exposes[0].binding: Additional properties are not allowed ('formatt' was unexpected)
  Fix: Delete or rename the property the message names: the object at the pointer does not take it. Check its spelling and nesting against the schema: fluid validate <contract> --show-schema.
- ERR_CONTRACT_SCHEMA_REQUIRED at /exposes/0/binding: exposes[0].binding: 'format' is a required property
  Fix: Add the property the message names to the object at the pointer: the schema requires it there. fluid validate <contract> --show-schema prints the schema, with the required properties of each object.
Fix these errors, then run: fluid validate /work/contract.fluid.yaml --offline
```

*On forge-cli `main`, not yet in a release ([forge-cli #880](https://github.com/Agenticstiger/forge-cli/pull/880)).* A `Fix:` line is left out when the message already ends with the fix, as the [placeholder and starter-value warnings](./validate.md#placeholders-and-starter-values) do. With a `fluid` older than `issues`, the hook shows the messages without codes.

## Notes

- This is the editor half of the agentic-IDE workflow; the CLI half is [`fluid forge --agent`](./forge.md#headless-agent-mode), which drives Forge headlessly with JSON-Lines progress output.
- The generated MCP server can route LLM calls back through the editor (see [LLM sampling](../advanced/mcp.md#llm-sampling)), so an agentic IDE can run a full AI-assisted forge on its own subscription — no second API key.

## See also

- [`fluid forge`](./forge.md) — AI-assisted scaffolding, including headless `--agent` mode
- [`fluid mcp`](./mcp.md) — the MCP server the generated IDE config points at
- [`fluid scaffold-ci`](./scaffold-ci.md) — the equivalent generator for CI pipelines
- [Advanced MCP server guide](../advanced/mcp.md)
