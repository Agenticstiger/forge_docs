# `fluid market`

Search and browse data products across configured catalogs and blueprint sources.

## Syntax

```bash
fluid market [options]
```

## Examples

```bash
fluid market
fluid market --domain finance --status active
fluid market --search "customer analytics"
fluid market --layer gold --min-quality 0.9
fluid market --product-type CDP --format json
fluid market --product-id customer-360-v2 --detailed
fluid market --blueprints
```

### Create a contract from a bundled blueprint

```bash
fluid market --blueprints
fluid market --blueprint-id fluid.starter
fluid market --blueprint-id fluid.starter --instantiate \
  --params '{"product_name": "Demo Orders"}' -O contract.fluid.yaml
fluid validate contract.fluid.yaml
```

`--blueprints` lists the blueprints the CLI knows. With no registry configured it lists the four that ship with the CLI, and says so:

```text
No registry configured; showing bundled blueprints. Set FLUID_API_URL or FLUID_PUBLIC_REGISTRY for more.

                                Blueprint Marketplace (4 bundled + 0 registry)
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ ID                      ┃ Name                                  ┃ Category  ┃ Maturity ┃ Source  ┃ Version ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ fluid.starter           │ Starter Data Product                  │ starter   │ stable   │ bundled │  1.0.0  │
│ fluid.analytics-daily   │ Daily Analytics Aggregate             │ analytics │ stable   │ bundled │  1.0.0  │
│ fluid.starter-gcp       │ Starter Data Product (GCP / BigQuery) │ starter   │ stable   │ bundled │  1.0.0  │
│ fluid.starter-snowflake │ Starter Data Product (Snowflake)      │ starter   │ stable   │ bundled │  1.0.0  │
└─────────────────────────┴───────────────────────────────────────┴───────────┴──────────┴─────────┴─────────┘
```

`--blueprint-id <id>` shows one blueprint's parameters. `--instantiate` renders it:

- It needs `--params` or `--interactive`. With neither, it prints `No parameters provided. Use --params or --interactive.` and exits `1`.
- A bundled blueprint renders locally. Any other id is fetched from the blueprint registry, so without a registry it fails with `no_blueprint_marketplace`.
- The contract is printed to the console. It is written to a file only with `-O`/`--output`, and that file is JSON whatever its extension is. JSON is valid YAML, so `fluid validate` reads it.
- The `fluid.starter` blueprint renders a contract with `fluidVersion: 0.7.4`.

## Options

### Search and filters

| Option | Description |
| --- | --- |
| `--search`, `-s` | Text search across product names, descriptions and tags |
| `--domain`, `-d` | Filter by domain; repeatable |
| `--owner`, `-o` | Filter by owner; repeatable |
| `--layer`, `-l` | Filter by data layer; repeatable. One of `raw`, `bronze`, `silver`, `gold`, `analytical`, `operational`, `real_time`. |
| `--product-type` | Filter by Data Mesh product type: `SDP` (source-aligned), `ADP` (aggregated) or `CDP` (consumption-aligned). Equivalent to `--layer` `bronze`, `silver` or `gold` respectively. |
| `--status` | Filter by status; repeatable. One of `active`, `deprecated`, `development`, `staging`, `retired`. |
| `--tags`, `-t` | Filter by tags; repeatable |

### Quality and dates

| Option | Description |
| --- | --- |
| `--min-quality` | Minimum quality score, 0.0 to 1.0 |
| `--created-after` | Show products created after this date (`YYYY-MM-DD`) |
| `--created-before` | Show products created before this date (`YYYY-MM-DD`) |

### Catalogs and output

| Option | Description |
| --- | --- |
| `--catalogs` | Comma-separated list of catalogs to search. Default: all configured. |
| `--list-catalogs` | Show available catalog types and which are configured |
| `--format`, `-f` | Output format: `table` (default), `json` or `detailed` |
| `--output`, `-O` | Write output to a file. Default: stdout. |
| `--limit` | Maximum results per catalog. Default `50`. |
| `--offset` | Pagination offset. Default `0`. |

### Details and statistics

| Option | Description |
| --- | --- |
| `--product-id` | Show a specific product |
| `--detailed` | Show more detail for results |
| `--marketplace-stats` | Show statistics |
| `--config-template` | Generate a configuration template for catalog connections |

### Blueprints

| Option | Description |
| --- | --- |
| `--blueprints` | Search blueprints instead of catalogs |
| `--blueprint-id` | Show a blueprint, or instantiate it with `--instantiate` |
| `--instantiate` | Render the blueprint named by `--blueprint-id` into a contract. Requires `--params` or `--interactive`. |
| `--params` | Blueprint parameters, as a JSON string or the path to a JSON file. Used with `--instantiate`. |
| `--interactive` | Fill the parameters through a wizard. Used with `--instantiate`. |
| `--show-template` | With `--blueprint-id`, print the blueprint's Jinja2 contract template. |

## Command Center integration

`fluid market` auto-detects a FLUID Command Center instance to enrich its discovery results with cross-organization catalog data. Detection is automatic and silent: the local-only path needs no configuration.

For integrators pointing `fluid market` at a specific Command Center deployment, these environment variables control detection:

| Env var | Purpose |
| --- | --- |
| `FLUID_COMMAND_CENTER_URL` | Explicit Command Center URL (overrides config file and default). Strips a trailing slash. |
| `FLUID_DISABLE_CC_DETECTION` | `1`, `true` or `yes` disables detection entirely and forces local-only operation. Useful for air-gapped environments. |
| `FLUID_COMMAND_CENTER_HOST_ALLOWLIST` | Comma-separated host suffixes (`corp.example.com`) that are allowed even when they resolve to a private address. See below. |

Detection priority order:

1. `FLUID_COMMAND_CENTER_URL` env var
2. `command_center.url` in `~/.fluid/config.yaml` (or `~/.fluid/config.yml`, `./fluid.yaml`, `./fluid.yml`)
3. Default `http://localhost:8000`

If none reach a healthy endpoint, `fluid market` falls back to local catalog discovery. The Command Center catalog connector had a broken import until 0.16.5, so earlier releases could not load it.

Detection refuses a Command Center whose host resolves to a private, link-local or cloud-metadata address, because the request carries an API key. It logs a warning and skips detection. `localhost`, `127.0.0.1` and `::1` are always allowed. A Command Center on an internal network needs its host suffix in `FLUID_COMMAND_CENTER_HOST_ALLOWLIST`, which `fluid market` and the apply run report read. `fluid publish --target fluid-command-center` does not read it: see [Publishing to the FLUID Command Center](./publish.md#publishing-to-the-fluid-command-center) for its own settings.
