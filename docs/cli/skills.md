# `fluid skills`

Manage the workspace's industry skills file (`.fluid/skills.yaml`) — the project-knowledge bundle that Forge Copilot reads to tailor its suggestions.

## Syntax

```bash
fluid skills update
fluid skills show
fluid skills compile
fluid skills install [INDUSTRY]
```

## Key options

### `skills update`

No options. Refreshes the `tools` section of `.fluid/skills.yaml` to match the installed CLI version, preserving any custom industry section.

### `skills show`

No options. Prints the current `.fluid/skills.yaml` (syntax-highlighted when `rich` is available).

### `skills compile`

No options. Pre-compiles `.fluid/skills.yaml` into `.fluid/skills.compiled.json`, a compact form used to speed up AI copilot runs.

### `skills install`

| Option | Description |
| --- | --- |
| `INDUSTRY` | Industry key (`telco`, `retail`, `healthcare`, `finance`). Optional — omit for an interactive picker. |

## Examples

```bash
fluid skills install
fluid skills install telco
fluid skills update
fluid skills compile
fluid skills show
```

## Notes

- All subcommands require a FLUID workspace; if `find_workspace_root()` returns nothing, the command exits with an error suggesting [`fluid init`](./init.md).
- `install` writes `.fluid/skills.yaml` and then auto-runs `compile` so the AI copilot picks up the new pack immediately.
- Bundled industry packs are shipped under `fluid_build/cli/industry_skills/`. Unknown keys fall back to a clear error listing the available options (`telco`, `retail`, `healthcare`, `finance`, `other`).
- The file is consumed by [`fluid forge`](./forge.md) to tailor copilot prompts to the installed industry.
