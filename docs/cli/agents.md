# `fluid agents`

Inspect and clean up the `.fluid/agents/<run-id>/` artifact stack that AI-copilot `fluid forge` runs write — stage records, cost, judge score, transcript, and reasoning receipts. The same directory also holds [custom domain agent specs](#custom-domain-agents).

## Syntax

```bash
fluid agents <list|show|prune> [options]
```

## Subcommands

### `fluid agents list`

Walk `.fluid/agents/<run-id>/` and render a table of runs (`RUN_ID`, `AGE`, `STATUS`, `STAGES`, `COST`, `LAST_STAGE`).

| Option | Description |
| --- | --- |
| `--incomplete` | Only show paused or failed runs (skip completed). |
| `--since <spec>` | Restrict to runs newer than this (e.g. `7d`, `24h`, `2026-04-01`). |
| `--archived` | List runs from the prune-archive bucket (`.fluid/agents/.archived/`) instead of the live dir — mirrors `git stash list`. |
| `--no-trunc` | Force all columns even on narrow terminals (otherwise `COST` drops below 100 cols, then `STAGES` below 80 — `gh` / `kubectl` behaviour). |
| `--root <dir>` | Workspace root to scan (default: cwd). |
| `--json` | Emit machine-readable JSON instead of a table. |

### `fluid agents show <run-id>`

Print every stage record, the cost breakdown, the judge score, and the on-disk receipt paths for one run. Accepts a full run-id or an unambiguous prefix.

| Option | Description |
| --- | --- |
| `--root <dir>` | Workspace root to scan (default: cwd). |
| `--json` | Emit machine-readable JSON instead of a table. |

### `fluid agents prune`

Archive (or permanently delete) old run directories and report the bytes reclaimed. **Defaults to archive** — pruned runs move to `.fluid/agents/.archived/` and stay recoverable.

| Option | Description |
| --- | --- |
| `--older-than <spec>` | Age cutoff (e.g. `30d`, `24h`). Default `30d`. |
| `--run-id <id>` | Prune one specific run-id (skips the age cutoff). |
| `--dry-run` | Show what would be removed without touching disk. |
| `--yes`, `-y` | Skip the confirmation prompt. |
| `--archive` | *(default)* Move pruned runs to `.fluid/agents/.archived/` — reversible. |
| `--delete` | **Permanently** delete pruned runs (irreversible). Mutually exclusive with `--archive`. |
| `--root <dir>` | Workspace root to scan (default: cwd). |

## Examples

```bash
fluid agents list                               # recent runs, newest first
fluid agents list --incomplete                  # only paused / failed runs
fluid agents list --since 7d --json             # last week, machine-readable
fluid agents show 1a2b3c                         # full detail for a run (prefix ok)
fluid agents prune --older-than 30d --dry-run    # preview the cleanup
fluid agents prune --older-than 90d --delete -y  # permanent, no prompt
```

## Notes

- A run-id is minted by each AI-copilot `fluid forge` run. Resume a paused run with [`fluid forge --resume <run-id>`](/forge_docs/cli/forge.html), fork it with `--fork`, or re-run from one stage with `--from-stage` (see [Resume, fork and time-travel](./forge.md#resume-fork-and-time-travel)). There is no `fluid agents resume`.
- `show` surfaces the same receipts the [pre-write preview panel](/forge_docs/advanced/guided-forge-ux.html) persisted (`cost.json`, `reasoning.md`, `transcript.json`), so nothing is lost if you Ctrl-C at the prompt.
- Aggregate cost and judge scores across many runs with [`fluid stats`](/forge_docs/cli/stats.html).

## Custom domain agents

`fluid forge --domain <name>` loads a domain agent: a YAML spec with the interview questions, defaults and tips for one industry or team. Built in: `ai_ready`, `education`, `energy`, `finance`, `government`, `healthcare`, `insurance`, `logistics`, `manufacturing`, `media`, `pharma`, `retail`, `telco`. A spec you add yourself sits in the same directory as the run records above, as a file rather than a run directory:

```text
.fluid/agents/
├── widgets.yaml                 # your spec: fluid forge --domain widgets
└── 1a2b3c.../                   # a forge run
```

A spec named `<name>.yaml` in `.fluid/agents/` of the working directory applies to that project. One in `~/.fluid/agents/` applies everywhere, and a workspace spec shadows a global one, which shadows a built-in one of the same name.

The smallest spec that loads has these keys:

```yaml
name: widgets
domain: Widget Manufacturing
description: Data products for widget production lines and quality control
keywords:                        # optional: mentioning two of these selects the agent
  - widget
  - production line
questions:                       # at least one
  - key: line_type
    question: Which production line does this product describe?
    type: choice                 # choice or text
    required: true
    choices:
      - label: Assembly
        value: assembly
      - label: Packaging
        value: packaging
resolver_defaults:
  line_type: assembly
suggestion_defaults:             # both keys are required
  recommended_template: starter
  recommended_provider: local
```

`name`, `domain`, `description`, `questions` and `suggestion_defaults.recommended_template` / `recommended_provider` are required; a spec that lacks one fails to load, and discovery skips it with a warning. The other keys the loader reads (`keywords`, `rules`, `next_step_tips`, `conditional_next_step_tips`, `supported_data_product_types`, `resolver_defaults`) are optional. Use the built-in specs in the CLI's `fluid_build/cli/agent_specs/` directory as examples.

`fluid init --agent widgets` is meant to write a starter spec for you. As of 0.18.1 it fails with `No such file or directory: '.../fluid_build/cli/agent_specs/custom.yaml.template'`, because the template is missing from the installed package. Write the file by hand from the example above.
