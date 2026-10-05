# `fluid version`

Show the CLI release, the contract schema versions it understands, and which providers loaded.

## Syntax

```bash
fluid version [--verbose] [--format {text|json}] [--short]
```

## Examples

Print only the release number, for a script or a CI log line:

```bash
fluid version --short
```

```text
0.18.1
```

Gate a pipeline on the schema versions this CLI accepts:

```bash
fluid version --format json
```

```json
{
  "cli": {
    "version": "0.18.1",
    "api_version": "v1",
    "build": "production"
  },
  "spec_versions": {
    "supported": ["0.7.1", "0.7.2", "0.7.3", "0.7.4", "0.7.5", "0.7.6"],
    "default": "0.7.5",
    "latest": "0.7.5",
    "preview": ["0.7.6"]
  },
  "features": {
    "core_validation": true,
    "core_07x_support": true,
    "provider_actions": true,
    "0.7.1_support": true,
    "sovereignty": true,
    "agent_policy": true,
    "airflow_generation": true
  },
  "providers": {
    "local": "available",
    "gcp": "available",
    "aws": "available",
    "snowflake": "available"
  }
}
```

The default text output is a panel with the same information. `--verbose` adds the Python version and the operating system below it:

```bash
fluid version --verbose
```

```text
...
Python: 3.11.15 (darwin)
System: Darwin arm64
```

`fluid --version` is the top-level flag and prints one line, `FLUID Forge CLI v0.18.1`.

## Options

| Option | Description |
| --- | --- |
| `--verbose`, `-v` | Add the Python version and operating system to the output |
| `--format {text\|json}` | Output format. Default `text` |
| `--short` | Print only the version number. Wins over `--format`: `--short --format json` still prints the bare number |

## Reading the schema fields

`spec_versions` lists the contract schema versions the installed CLI bundles.

| Field | Meaning |
| --- | --- |
| `supported` | The schema versions bundled with this CLI, preview versions included. |
| `latest` | The newest **stable** schema. A contract that declares no `fluidVersion` is validated against it first. |
| `default` | The stable version a tool should author against. In 0.18.1 it is computed as the same value as `latest`. |
| `preview` | Schema versions that validate only when a contract declares them, such as `fluidVersion: "0.7.6"`. They are never picked automatically. |

With `--verbose --format json`, the JSON also carries `python` (version, executable, platform) and `system` (platform, system, machine) objects.

See [`fluid validate`](./validate.md#schema-versions-stable-and-preview) for what the preview schema adds and how to validate against a specific version.

## Notes

- `fluid version` reports the CLI release, which is separate from the `fluidVersion` inside `contract.fluid.yaml`. A contract that declares `fluidVersion: 0.7.3` still validates on a newer CLI because the older schemas stay bundled.
- To compare the full capability surface (providers, build engines, command tree) rather than versions, use [`fluid describe --self --json`](./describe.md). To check whether those capabilities work on this machine, use [`fluid doctor`](./doctor.md).
