# `fluid import`

Convert existing tooling into FLUID contracts. Two modes: scan an existing dbt / Terraform / SQL directory, or import a foreign ingestion-tool project (Meltano, Airbyte, dlt, Singer).

## Syntax

```bash
fluid import [<engine> <source>] [options]
```

## Mode 1 — directory scan

```bash
fluid import
fluid import --dir ./legacy-dbt
fluid import --provider snowflake
fluid import --yes
```

| Option | Description |
| --- | --- |
| `--provider` | Provider for the generated contracts |
| `--dir`, `-C` | Directory to scan |
| `--yes`, `-y` | Skip the confirmation prompt |

This is the promoted migration path for existing dbt, Terraform, or SQL projects.

## Mode 2 — foreign ingestion tool importer

::: tip Coming in the next release
Importers for Meltano, Airbyte, dlt, and Singer ship in `0.8.3` as part of the source-aligned acquisition stack. Pre-0.8.3 releases only support the directory scan above.
:::

Convert an existing ingestion-tool project into FLUID acquisition contracts (one per discovered tap / connector / source):

```bash
fluid import meltano <project-dir>       # Meltano project
fluid import airbyte <workspace-id>      # Airbyte OSS / Cloud workspace
fluid import dlt <pipeline-name>         # dlt pipeline
fluid import singer <tap-config.json>    # Singer tap + target
```

| Option | Description |
| --- | --- |
| `<engine> <source>` | Importer mode + source identifier |
| `--out PATH` | Output contract path (default: one `contract.<id>.fluid.yaml` per discovered source in cwd) |
| `--provider {local\|gcp\|snowflake\|aws\|azure}` | Infrastructure provider for generated contracts. Default `local`. |
| `--yes`, `-y` | Skip the confirmation prompt |

What each importer does:

| Importer | Reads | Emits |
|---|---|---|
| `meltano` | `meltano.yml` + `extract:` block | One `engine: meltano` acquisition contract per tap |
| `airbyte` | Workspace config from REST API | One `engine: airbyte` acquisition contract per source |
| `dlt` | `@dlt.source` modules in the pipeline | One `engine: dlt` acquisition contract per source |
| `singer` | Tap + target config files | One `engine: meltano` acquisition contract (Meltano runs Singer protocol) |

**Secrets are auto-redacted** to `${ENV_VAR}` placeholders so the emitted contracts are safe to commit. Run [`fluid secrets login`](/forge_docs/cli/secrets.html) afterward to populate the keychain backend.

### Example — migrating from Meltano

```bash
fluid import meltano ./my-meltano-project --provider local --yes
fluid validate *.fluid.yaml
fluid apply contract.tap_postgres.fluid.yaml --yes
```

The generated contract preserves Meltano's tap selections and the `state`/`incremental` mode mapping. See [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) for engine-specific properties.

## Notes

- Mode 1 (`fluid import` with no engine arg) is the existing migration path for dbt / Terraform / SQL projects.
- Mode 2 (`fluid import <engine> <source>`) is the new ingestion-tool importer, available in the next release.
- If you want a clean greenfield start instead, use [`fluid init`](./init.md) or [`fluid forge`](./forge.md).
- For source-aligned ingestion from scratch (no existing tool project), [`fluid init --discover`](./init.md#discover) is the one-shot path.
