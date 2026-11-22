# `fluid skills`

Manage the workspace's industry skills file (`.fluid/skills.yaml`) — the project-knowledge bundle that Forge Copilot reads to tailor its suggestions.

*(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* In 0.31.0 nothing reads `.fluid/skills.yaml`, because the copilot that read it is gone; the command still writes the file.

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
| `INDUSTRY` | Industry key (`telco`, `retail`, `healthcare`, `finance`, `other`). Optional — omit for an interactive picker. |

## Examples

```bash
fluid skills install
fluid skills install telco
fluid skills update
fluid skills compile
fluid skills show
```

## Agent Skills

Separate from `.fluid/skills.yaml`, forge-cli ships Agent Skills: short guides a coding assistant loads when a task matches. [`fluid scaffold-ide`](./scaffold-ide.md) installs them into the project. *(since 0.37.0)* Three more ship:

| Skill | What it covers |
| --- | --- |
| `adopting-existing-pipelines` | Proposes contracts from existing Spark jobs and Airflow DAGs with `fluid import pyspark` and `fluid import airflow` (dry run first, then the defaults the report asks you to complete). Covers the conventions file the import reads, importer plugins, and taking existing Glue tables over with `--adopt-tables` through a reviewed plan. |
| `releasing-streaming-products` | How a changed Spark stream stops between batches, which runs are cancelled instead, what its probation watches, and when a failed release is rolled back or refused. Also what each Iceberg commit's stamps hold, and how `fluid ship --release-dir` and `fluid runs status --release-dir` name the release in force. |
| `publishing-to-data-mesh-manager` | Publishes a batch as drafts, promotes the drafts a `fluid verify` report shows clean, and reads a migration's status. See [`fluid datamesh-manager`](./datamesh-manager.md#migrating-a-catalog). |

`fluid scaffold-ide` installs them with the others. For the `generic`, `cursor` and `cline` targets they go in `.agents/skills/`, which Codex reads too. Each skill points to [`fluid describe --commands`](./describe.md#every-command-as-json) for every command and flag.

## Notes

- All subcommands require a FLUID workspace (a directory with `fluid.workspace.yaml`, which [`fluid init`](./init.md) writes). Elsewhere the command exits `1` with `Not inside a FLUID workspace. Run 'fluid init' first.`
- `install` writes `.fluid/skills.yaml` and then auto-runs `compile` so the AI copilot picks up the new pack immediately.
- Bundled industry packs are shipped under `fluid_build/cli/industry_skills/`. Unknown keys fall back to a clear error listing the available options (`telco`, `retail`, `healthcare`, `finance`, `other`).
- The file is consumed by [`fluid forge`](./forge.md) to tailor copilot prompts to the installed industry.
