# `fluid validate`

Validate a contract against FLUID schema rules and provider-aware checks.

## Syntax

```bash
fluid validate CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay |
| `--schema-version` | Validate against a specific schema version |
| `--min-version` | Minimum acceptable schema version |
| `--max-version` | Maximum acceptable schema version |
| `--strict` | Treat warnings as errors |
| `--offline` | Use only cached or bundled schemas |
| `--force-refresh` | Refresh cached schemas |
| `--clear-cache` | Clear schema cache first |
| `--cache-dir CACHE_DIR` | Custom schema cache directory |
| `--verbose`, `-v` | Detailed validation output |
| `--quiet`, `-q` | Minimal output |
| `--format` | `text` or `json` |
| `--list-versions` | List available schema versions |
| `--show-schema` | Show the schema used for validation |
| `--probe` | Run live external connectivity probes for sources / sinks declared in `acquisition` builds. **Coming on the source-aligned-acquisition branch — schema 0.7.3.** |
| `--report PATH` | Write the structured validation report to a file (in addition to stdout) |

## Examples

```bash
fluid validate contract.fluid.yaml
fluid validate contract.fluid.yaml --env prod
fluid validate contract.fluid.yaml --strict
fluid validate contract.fluid.yaml --schema-version 0.7.2
fluid validate contract.fluid.yaml --verbose --show-schema
```

## `--probe` — live external connectivity checks

::: tip Coming in the next release
The `--probe` flag ships on the `feat/source-aligned-acquisition` branch as part of schema 0.7.3 acquisition support.
:::

By default `fluid validate` is **pure schema validation** — no network. Set `--probe` to additionally test connectivity for every source / sink declared in `acquisition` builds:

```bash
fluid validate contract.fluid.yaml --probe
```

What it checks:

- **Postgres / MySQL / SQLite sources** — connect, run a no-op query, drop the connection
- **Filesystem sources** — readable, files exist
- **S3 / GCS sinks** — bucket exists, current creds can `ListObjects`
- **Airbyte / Kafka Connect endpoints** — health check on the cluster URL
- **Debezium connectors** — Kafka cluster reachable

Probe failures emit `ConnectivityProbeError` ([typed CLI errors](/forge_docs/advanced/typed-cli-errors.html#connectivity-secrets)) with the source coordinate, the underlying network error, and a fix hint. Probes time out at 5 seconds per target so a misconfigured source doesn't hang validation.

Use `--probe` in CI for any environment that has network access to the declared sources; skip it when you're validating offline or on a build agent without source access (the default behavior — pure schema — works there).

## Notes

- A contract can legitimately use `fluidVersion: 0.7.2` even when the installed CLI release is `0.8.0`. Schema 0.7.3 ships on the source-aligned-acquisition branch.
- For most users, plain `fluid validate contract.fluid.yaml` is enough. Reach for explicit schema flags when you are debugging compatibility or working across versions.
