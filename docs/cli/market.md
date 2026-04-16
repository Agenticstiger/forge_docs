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
