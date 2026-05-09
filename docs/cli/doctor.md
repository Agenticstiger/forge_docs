# `fluid doctor`

Run built-in health checks for the CLI and local environment.

## Syntax

```bash
fluid doctor
```

## Key options

| Option | Description |
| --- | --- |
| `--scope {authoring\|pipeline\|ingestion\|infra\|catalog\|all}` | Restrict checks to one scope (or run them all). **Coming in the `0.7.3` release.** Default `authoring`. |
| `--out-dir` | Output directory for diagnostics |
| `--features-only` | Only check FLUID feature availability |
| `--extended`, `--comprehensive` | Run optional extended diagnostics |
| `--json` | Emit per-check JSON (stable shape for CI) |
| `--verbose`, `-v` | Detailed output |

## Examples

```bash
fluid doctor
fluid doctor --verbose
fluid doctor --extended
fluid doctor --features-only
fluid doctor --scope ingestion       # check the 6 acquisition engines
fluid doctor --scope all --json      # CI-friendly full report
```

## `--scope` — what each scope checks

::: tip Coming in the next release
The `--scope` flag ships in the upcoming `0.7.3` release. The pinned 0.8.0 baseline runs the equivalent of `--scope authoring` only.
:::

| Scope | What it checks |
|---|---|
| `authoring` | Forge copilot readiness — LLM provider configured, models reachable, tool-use capability |
| `pipeline` | 11-stage pipeline capability — `bundle`, `plan`, `apply` work end-to-end on a fixture |
| `ingestion` | The six acquisition engines — `duckdb`, `dlt`, `meltano`, `airbyte`, `kafka-connect`, `debezium` are importable; optional extras flagged |
| `infra` | Infrastructure readiness — cloud creds, Kubernetes API reachable, provider CLIs on PATH |
| `catalog` | Catalog connectivity — DataHub, OpenMetadata, Unity, Glue, Snowflake Horizon, Data Mesh Manager — only checks the ones declared in any contract under cwd |
| `all` | Run every scope in sequence |

Per-check output is the same five-field shape ([Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html)) — name, severity, detail, fix hint, doc URL. The full-scope run still completes in under 3 seconds even on a fresh laptop.

## Notes

- In current `0.8.0` docs, the default doctor experience is self-contained. Use `--extended` when you explicitly want the optional workspace diagnostics path.
