# `fluid market`

Search and browse data products across configured catalogs and blueprint sources.

## Syntax

```bash
fluid market
```

## Key options

### Search and filters

| Option | Description |
| --- | --- |
| `--search`, `-s` | Text search |
| `--domain`, `-d` | Filter by domain |
| `--owner`, `-o` | Filter by owner |
| `--layer`, `-l` | Filter by data layer |
| `--status` | Filter by status |
| `--tags`, `-t` | Filter by tags |

### Quality and dates

| Option | Description |
| --- | --- |
| `--min-quality` | Minimum quality score |
| `--created-after` | Filter by creation date |
| `--created-before` | Filter by creation date |

### Catalogs and output

| Option | Description |
| --- | --- |
| `--catalogs` | Limit search to selected catalogs |
| `--list-catalogs` | Show available catalog configurations |
| `--format`, `-f` | Output format |
| `--output`, `-O` | Write output to a file |
| `--limit` | Maximum results |
| `--offset` | Pagination offset |

### Details and blueprint mode

| Option | Description |
| --- | --- |
| `--product-id` | Show a specific product |
| `--detailed` | Show more detail for results |
| `--marketplace-stats` | Show statistics |
| `--config-template` | Generate a config template |
| `--blueprints` | Search blueprints instead of catalogs |
| `--blueprint-id` | Inspect a specific blueprint |
| `--instantiate` | Instantiate a blueprint |

## Examples

```bash
fluid market
fluid market --domain finance --status active
fluid market --search "customer analytics"
fluid market --layer gold --min-quality 0.9
fluid market --product-id customer-360-v2 --detailed
fluid market --blueprints
```

## Command Center integration

`fluid market` auto-detects a FLUID Command Center instance to enrich its discovery results with cross-organization catalog data. Detection is automatic and silent — you don't need to configure anything for the local-only path to work.

For enterprise integrators pointing `fluid market` at a specific Command Center deployment, two environment variables override auto-detection:

| Env var | Purpose |
| --- | --- |
| `FLUID_COMMAND_CENTER_URL` | Explicit Command Center URL (overrides config file + default). Strips trailing slash. |
| `FLUID_DISABLE_CC_DETECTION` | `1` / `true` / `yes` to disable detection entirely (forces local-only operation). Useful for air-gapped environments. |

Detection priority order:

1. `FLUID_COMMAND_CENTER_URL` env var
2. `~/.fluid/config.yaml` `command_center.url` key
3. Default `http://localhost:8000`

If none reach a healthy endpoint, `fluid market` falls back to local catalog discovery.
