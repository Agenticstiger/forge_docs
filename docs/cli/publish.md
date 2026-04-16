# `fluid publish`

Publish one or more contracts to a configured catalog.

## Syntax

```bash
fluid publish CONTRACT_FILES
```

`CONTRACT_FILES` supports one or more paths or glob patterns.

## Key options

| Option | Description |
| --- | --- |
| `--catalog`, `-c` | Target catalog name |
| `--list-catalogs` | List configured catalogs |
| `--dry-run` | Validate and preview without publishing |
| `--verify-only` | Check whether a contract is already published |
| `--force` | Force an update |
| `--format`, `-f` | Output format |
| `--verbose`, `-v` | Detailed output |
| `--quiet`, `-q` | Minimal output |
| `--skip-health-check` | Skip catalog health checks |
| `--show-metrics` | Show detailed metrics |

## Examples

```bash
fluid publish contract.fluid.yaml
fluid publish customer-*.fluid.yaml
fluid publish contract.fluid.yaml --catalog fluid-command-center
fluid publish contract.fluid.yaml --dry-run
fluid publish contract.fluid.yaml --verify-only
```

## Notes

- A typical flow is `validate -> apply -> publish`.
- Use [`fluid market`](./market.md) to verify discoverability after publishing.

## Publishing to Data Mesh Manager (Entropy Data)

**Data Mesh Manager** (now Entropy Data) is one of the catalogs Fluid Forge publishes to. It has its own dedicated entry point so data products *and* data contracts can be published with the right payload shape:

```bash
fluid datamesh-manager publish CONTRACT   # or: fluid dmm publish CONTRACT
```

### Setup

| Env var | Required | Purpose |
| --- | --- | --- |
| `DMM_API_KEY` | ✅ Yes | API key. Generate at *Profile → Organization → Settings → API Keys*. |
| `DMM_API_URL` | No | Base URL override (default: `https://api.entropy-data.com`). |

### Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required) |
| `--dry-run` | Validate and preview the API payload without publishing |
| `--with-contract` | Publish a companion data contract alongside the data product |
| `--team-id ID` | Override team-id resolution; auto-creates the team if it doesn't exist |
| `--validation-mode {warn,strict}` | Gate on pre-publish schema validation. `warn` (default) logs and continues; `strict` aborts on any violation. Both modes validate against the contract's **own** declared `fluidVersion`, so a 0.5.7 contract is validated against `fluid-schema-0.5.7.json`, a 0.7.2 contract against `fluid-schema-0.7.2.json`, etc. — upgrading the CLI never invalidates a contract that was valid against its own version. |

### Examples

```bash
export DMM_API_KEY="..."
fluid dmm publish contract.fluid.yaml
fluid dmm publish contract.fluid.yaml --dry-run
fluid dmm publish contract.fluid.yaml --with-contract
fluid dmm publish contract.fluid.yaml --validation-mode strict
```

### What gets sent

- **Data product** via `PUT /api/dataproducts/{id}` — built from FLUID `metadata`, `exposes`, `consumes`.
- **Data contract** (optional, with `--with-contract`) via `PUT /api/datacontracts/{id}` — the ODCS v3.1.0 payload of the contract.
- **Input / output ports** mapped from FLUID `consumes[]` / `exposes[]`.
- **PII detection** from `schema[].sensitivity` / `classification` fields.
- **Multi-provider location** mapping — BigQuery, Snowflake, S3, Kafka, Redshift, etc.
- Retries with backoff for transient failures (`429`, `5xx`).

### Catalog-adapter route

The same behavior is reachable through the generic catalog surface:

```bash
fluid publish contract.fluid.yaml --catalog datamesh-manager
```

Use the dedicated `fluid dmm publish` entry point when you want `--validation-mode` or `--with-contract`. Use `fluid publish --catalog datamesh-manager` when you're treating DMM as one catalog among several behind a common interface.
