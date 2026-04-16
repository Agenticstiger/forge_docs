# Blueprints

Reusable, parameterized templates for common data product patterns. Blueprints let you scaffold a complete project — contract, sample data, transformations — in seconds.

## Quick Start

```bash
# List all available blueprints
fluid blueprint list

# Filter by category or provider
fluid blueprint list --category analytics --provider gcp

# Describe a specific blueprint
fluid blueprint describe customer-360-gcp

# Create a project from a blueprint
fluid blueprint create customer-360-gcp --target-dir my-project
```

## CLI Reference

### `fluid blueprint list`

| Option | Description |
|--------|-------------|
| `--category` | Filter by category (e.g. `analytics`, `ml`, `ingestion`) |
| `--complexity` | Filter by complexity level |
| `--provider` | Filter by provider (`gcp`, `aws`, `snowflake`, `local`) |
| `--verbose`, `-v` | Show detailed metadata |

### `fluid blueprint describe <name>`

Show detailed information about a blueprint including its schema, required configuration, estimated setup time, and tags.

### `fluid blueprint create <name>`

| Option | Description |
|--------|-------------|
| `--target-dir`, `-d` | Directory to create the project in |
| `--provider`, `-p` | Override the default provider |
| `--quickstart`, `-q` | Use smart defaults |
| `--dry-run` | Preview what would be created |

### `fluid blueprint search <query>`

Search blueprints by keyword across names, descriptions, and tags.

### `fluid blueprint validate [name]`

Validate one or all blueprints for correctness.

## Available Blueprints

| Blueprint | Category | Providers | Description |
|-----------|----------|-----------|-------------|
| `customer-360` | Analytics | local | Customer analytics data product |
| `customer-360-gcp` | Analytics | gcp | Customer analytics on BigQuery |
| `enterprise-snowflake` | Analytics | snowflake | Enterprise data warehouse |
| `semantic-customer-model` | Analytics | local | Semantic layer with customer data |

## Creating From a Blueprint

```bash
# 1. Browse options
fluid blueprint list --verbose

# 2. Pick one and scaffold
fluid blueprint create customer-360-gcp -d my-analytics --quickstart

# 3. Enter the project
cd my-analytics

# 4. Run the standard workflow
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

## See Also

- [init command](/cli/init) — create projects from scratch or blueprints
- [forge command](/cli/) — AI-powered project generation
- [Getting Started](/getting-started/) — install and run your first project
- [Custom LLM Agents](/advanced/custom-llm-agents) — AI-powered project generation with your own models
- [Contributing](/contributing) — contribute new blueprints
