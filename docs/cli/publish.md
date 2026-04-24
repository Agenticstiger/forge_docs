# `fluid publish`

Stage 10 of the 11-stage pipeline. Publish one or more contracts to one or more catalogs.

`0.8.0` renames the single-valued `--catalog X,Y` flag to the repeatable `--target <name>[:<endpoint>]`. Each `--target` invocation pushes to one catalog; pass the flag multiple times to push to several at once. `--catalog` is kept as a deprecation-aliased surface for one release.

## Syntax

```bash
fluid publish CONTRACT_FILES
```

`CONTRACT_FILES` supports one or more paths or glob patterns.

## Key options

| Option | Description |
| --- | --- |
| `--target`, `-t` *(repeatable)* | Target catalog name, with an optional `:<endpoint>` suffix to override the catalog's default URL. Built-in targets include `fluid-command-center`, `datamesh-manager`, `dmm`, and `entropy-data`; additional catalog providers can be configured by name. Pass multiple times to push to several catalogs. |
| `--catalog`, `-c` | **Deprecated** one-release alias for `--target`. Emits a warning; treat it as historical. |
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

### Single target

```bash
fluid publish contract.fluid.yaml --target fluid-command-center
```

### Multiple targets in one call

```bash
fluid publish contract.fluid.yaml \
  --target fluid-command-center \
  --target datamesh-manager
```

The publish report contains a per-target result block, so a partial failure (e.g. DataHub auth problem but DMM succeeded) is distinguishable from a full failure.

### Endpoint override (self-hosted catalogs)

```bash
fluid publish contract.fluid.yaml \
  --target fluid-command-center:https://cc.internal.acme.com \
  --target datamesh-manager:https://dmm.internal.acme.com
```

### Glob input

```bash
fluid publish customer-*.fluid.yaml --target datamesh-manager
```

### Dry-run preview

```bash
fluid publish contract.fluid.yaml --target datamesh-manager --dry-run
```

## Notes

- A typical flow is `validate → plan → apply → verify → publish`.
- Use [`fluid market`](./market.md) to verify discoverability after publishing.
- The legacy form `--catalog a,b,c` (comma-separated) is not equivalent to `--target a --target b --target c`; the new flag is repeatable instead of comma-separated for consistency with kubectl / helm / gh conventions.

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
| `DMM_ODPS_LINEAGE_MODE` | No | `contract` (default) uses Entropy Access agreements for product-to-product lineage; `source-system` is legacy compatibility mode. |
| `DMM_AUTO_APPROVE_ACCESS` | No | Set to `true` only when Access agreements should be approved automatically. |
| `DMM_ALLOW_INSECURE_HTTP` | No | Set to `true` only when intentionally publishing to a non-local HTTP endpoint. |

### Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required) |
| `--dry-run` | Validate and preview the API payload without publishing |
| `--with-contract` | Publish a companion data contract alongside the data product |
| `--team-id ID` | Override team-id resolution; auto-creates the team if it doesn't exist |
| `--data-product-spec VALUE` | Override the data product payload spec. Use `odps` for Entropy ODPS publishes. |
| `--odps-lineage-mode {contract,source-system}` | Choose ODPS lineage behavior. `contract` is the default. |
| `--auto-approve-access` | Approve generated Access agreements immediately. Intended for local sandboxes, not review-based production flows. |
| `--validation-mode {warn,strict}` | Gate on pre-publish schema validation. `warn` (default) logs and continues; `strict` aborts on any violation. Both modes validate against the contract's **own** declared `fluidVersion`, so a 0.5.7 contract is validated against `fluid-schema-0.5.7.json`, a 0.7.2 contract against `fluid-schema-0.7.2.json`, etc. — upgrading the CLI never invalidates a contract that was valid against its own version. |

### Examples

```bash
export DMM_API_KEY="..."
fluid dmm publish contract.fluid.yaml
fluid dmm publish contract.fluid.yaml --dry-run
fluid dmm publish contract.fluid.yaml --with-contract
fluid dmm publish contract.fluid.yaml --data-product-spec odps --odps-lineage-mode contract
fluid dmm publish contract.fluid.yaml --validation-mode strict
```

### What gets sent

- **Data product** via `PUT /api/dataproducts/{id}` — built from FLUID `metadata`, `exposes`, `consumes`.
- **Data contract** (optional, with `--with-contract`) via `PUT /api/datacontracts/{id}` — the ODCS v3.1.0 payload of the contract.
- **Access agreements** from product-to-product `consumes[]` entries. This is the default ODPS lineage path and prevents duplicated SourceSystem graph nodes.
- **Input / output ports** mapped from FLUID `consumes[]` / `exposes[]`. Product-to-product consumes are Access-only in ODPS mode; explicit source-system consumes remain input ports.
- **PII detection** from `schema[].sensitivity` / `classification` fields.
- **Multi-provider location** mapping — BigQuery, Snowflake, S3, Kafka, Redshift, etc.
- **Safe team bootstrap** — if DMM rejects team members because users do not exist yet, the provider retries team creation without `members` while keeping the contact email.
- Retries with backoff for transient failures (`429`, `5xx`).

### Catalog-adapter route

The same behavior is reachable through the generic catalog surface:

```bash
fluid publish contract.fluid.yaml --target datamesh-manager
```

Use the dedicated `fluid dmm publish` entry point when you want `--validation-mode`, `--with-contract`, `--odps-lineage-mode`, or `--auto-approve-access`. Use `fluid publish --target datamesh-manager` when you're treating DMM as one catalog among several behind a common interface.
