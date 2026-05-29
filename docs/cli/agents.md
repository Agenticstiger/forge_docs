# `fluid agents`

Inspect and clean up the `.fluid/agents/<run-id>/` artifact stack that every `fluid forge` run writes — stage records, cost, judge score, transcript, and reasoning receipts.

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

- A run-id is minted by every `fluid forge` invocation. Resume a paused run with [`fluid forge --resume <run-id>`](/forge_docs/cli/forge.html) — there is no `fluid agents resume`.
- `show` surfaces the same receipts the [pre-write preview panel](/forge_docs/advanced/guided-forge-ux.html) persisted (`cost.json`, `reasoning.md`, `transcript.json`), so nothing is lost if you Ctrl-C at the prompt.
- Aggregate cost and judge scores across many runs with [`fluid stats`](/forge_docs/cli/stats.html).
