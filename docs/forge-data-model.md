# Forge Data Model

`fluid forge data-model` forges a reviewable data-model contract from a business intent file, raw DDL, or a configured metadata source. It writes a Fluid contract plus a logical model sidecar that downstream generation commands consume.

## When to use it

Use `fluid forge data-model` when you want the CLI to create the semantic data-model layer before you generate dbt or other transformation artifacts.

| Input | Command | Best for |
| --- | --- | --- |
| YAML/JSON intent | `fluid forge data-model from-intent` | A business-first description of the data product you want |
| SQL DDL | `fluid forge data-model from-ddl` | Reverse-engineering existing warehouse tables |
| Catalog metadata | `fluid forge data-model from-source` | Forging from Snowflake, Unity, BigQuery, Dataplex, Glue, DataHub, or DMM metadata |

## From an intent file

An intent file is a YAML or JSON description of the data product you want. The minimum useful shape is:

```yaml
data_product:
  name: customer_orders
  domain: retail
grain:
  entity: order_line
  time_dimension: order_date
dimensions:
  entities: [customer, product, store]
metrics:
  - name: total_revenue
    description: Sum of order line revenue
```

Forge the model:

```bash
fluid forge data-model from-intent intent.yaml \
  --technique dimensional \
  --output customer_orders.fluid.yaml
```

Required minimum:

- `data_product.name`
- `data_product.domain`
- At least one `grain`, `dimensions.entities`, `metrics`, or `data_sources` entry

Useful optional fields:

- `business_context`
- `grain`
- `dimensions`
- `metrics`
- `data_sources`
- `business_rules`
- `modeling.technique`

## Discover the format

The CLI now teaches the intent format directly:

```bash
fluid forge data-model from-intent --example
fluid forge data-model from-intent --example retail
fluid forge data-model from-intent --example telco
fluid forge data-model from-intent --example finance
fluid forge data-model from-intent --schema
fluid forge data-model from-intent --validate intent.yaml
```

`--example` prints parseable YAML to stdout. `--schema` prints the `BusinessIntent` JSON Schema for editors and automation. `--validate` checks the input file only and does not write contract artifacts.

Bundled examples live in the CLI repo under `examples/intents/`:

- `customer_orders.intent.yaml`
- `telco_service.intent.yaml`
- `finance_risk.intent.yaml`

## Field mapping

| Intent field | Forged model meaning |
| --- | --- |
| `data_product` | Contract identity, domain, owner, and description |
| `grain` | Fact grain for dimensional models or the central entity for Data Vault 2.0 |
| `dimensions.entities` | Dimensions in a star model or hubs in Data Vault 2.0 |
| `metrics` | Semantic measures and metrics |
| `data_sources` | Source hints used in model docs and transformation generation |
| `business_rules` | Assumptions and logic notes preserved for reviewers |
| `modeling.technique` | Default modeling technique unless the CLI `--technique` flag overrides it |

## Output artifacts

A successful forge writes:

```text
customer_orders.fluid.yaml
customer_orders.fluid.yaml.model.json
customer_orders.fluid.yaml.model.md
customer_orders.fluid.yaml.semantics.osi.yaml
```

| Artifact | Purpose |
| --- | --- |
| `.fluid.yaml` | Fluid contract with OSI semantic metadata |
| `.model.json` | Canonical logical model sidecar used by downstream generators |
| `.model.md` | Human review document with Mermaid diagram, inventory, grain, metrics, dimensions, source hints, and assumptions |
| `.semantics.osi.yaml` | Standalone OSI semantic sidecar for BI and semantic tooling |

The Markdown model document is on by default. Suppress only that human-readable document with:

```bash
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --no-emit-model-doc
```

The `.model.json` machine sidecar is still written.

## From DDL

```bash
fluid forge data-model from-ddl \
  --ddl legacy/orders.sql legacy/customers.sql \
  --source-type snowflake \
  --technique data-vault-2 \
  --output customer_orders.fluid.yaml
```

For live Snowflake schemas, first dump the DDL:

```bash
fluid forge data-model dump-ddl \
  --database BIZ_LAB \
  --schema SEEDED \
  -o /tmp/biz_lab.sql
```

Then feed the dump to `from-ddl`. Snowflake `GET_DDL` output such as `create or replace TABLE` is parsed by the current DDL path.

## From a metadata source

```bash
fluid ai setup --source snowflake --name snowflake-prod

fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB \
  --schema SEEDED \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml
```

See [Source catalogs](./cli/catalogs/README.md) for the full Snowflake, Unity, BigQuery, Dataplex, Glue, DataHub, and Data Mesh Manager setup.

## Generate dbt after forging

The transformation generator auto-loads the logical sidecar referenced by `labels.modelSidecar` and writes deterministic dbt SQL from the forged model:

```bash
fluid generate transformation customer_orders.fluid.yaml \
  -o ./dbt_customer_orders \
  --dbt-validate
```

For dbt output, the generator fails clearly if it produces zero `models/**/*.sql` files. A normal dbt project includes `dbt_project.yml`, `profiles.yml`, `models/sources.yml` when applicable, and non-empty SQL model files under `models/`.

`fluid generate speed-transformation` and `fluid generate dbt` remain aliases, but docs lead with `fluid generate transformation`.

## Deterministic and strict modes

```bash
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --deterministic
```

`--deterministic` disables cache and tiering for byte-stable replay. For provider validation, use `--require-llm`; it fails loudly if the configured LLM cannot run instead of falling back to heuristics.

```bash
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --llm-provider ollama \
  --llm-model gemma4:latest \
  --require-llm
```

## Review and iteration

Use `--review` to open the logical sidecar in `$EDITOR` before the contract is finalized:

```bash
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --review
```

Compare sidecars after edits:

```bash
fluid forge data-model diff old.model.json new.model.json
```

Validate a forged contract or sidecar:

```bash
fluid forge data-model validate customer_orders.fluid.yaml
```

For agent-driven edits, use the MCP server. It exposes `read_logical_model`, `update_entity`, `add_relationship`, and `regenerate_physical` with path and namespace policy controls.
