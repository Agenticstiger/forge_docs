# AI Forge And Data-Model Journeys

This walkthrough shows the main `fluid forge` and `fluid forge data-model` paths a new user can take. AI helps with discovery, interview, semantic modeling, and review. Contract writing, validation, and dbt SQL generation stay deterministic from the forged logical model.

## Credential Safety First

Never put an API key in an intent file, contract, docs page, shell history snippet, or Git commit. Use environment variables or `fluid ai setup`.

```bash
# Pick one hosted provider.
export GOOGLE_API_KEY="<your-gemini-key>"
# or
export OPENAI_API_KEY="<your-openai-key>"
# or
export ANTHROPIC_API_KEY="<your-anthropic-key>"
```

For local-only testing, use Ollama instead:

```bash
export OLLAMA_HOST=http://localhost:11434
export FLUID_OLLAMA_MODEL=gemma4:latest
```

`fluid ai setup` stores provider/model preferences under `~/.fluid/`. API keys go to the OS keyring when available. Plaintext key persistence requires explicit opt-in with `FLUID_ALLOW_PLAINTEXT_AI_SECRETS=1`.

## Choose The Right Entry Point

| Goal | Command | AI needed |
| --- | --- | --- |
| Create a blank contract scaffold | `fluid forge --blank` | No |
| Let the CLI interview you and scaffold a project | `fluid forge` | Optional but recommended |
| Forge a model from YAML/JSON business intent | `fluid forge data-model from-intent` | Optional |
| Reverse-engineer existing SQL DDL | `fluid forge data-model from-ddl` | Optional |
| Forge directly from a metadata catalog | `fluid forge data-model from-source` | Optional for modeling, catalog credentials required |
| Validate a forged artifact | `fluid forge data-model validate` | No |
| Compare two sidecars | `fluid forge data-model diff` | No |
| Teach memory from operator edits | `fluid forge data-model learn` | No |
| Generate dbt SQL | `fluid generate transformation` | No |

## Provider Setup And Model Plan

Inspect the configured provider defaults and tier routing:

```bash
fluid ai models
fluid ai models --provider gemini
fluid ai models --provider openai --json
```

The current tier plan is provider-local:

| Stage | Typical mode |
| --- | --- |
| Interview / clarification | Fast routing model |
| Logical modeler | Deep model |
| Contract forge | Deterministic |
| Transformation/dbt | Deterministic from `.model.json` |
| Validator | Deterministic |
| Self-evaluation | Fast routing model |

For a hosted provider run, either complete interactive setup:

```bash
fluid ai setup
fluid ai status
```

or use environment variables for a single shell session:

```bash
export GOOGLE_API_KEY="<your-gemini-key>"
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --llm-provider gemini \
  --tiered \
  --require-llm
```

Use `--require-llm` when you are validating provider setup. Without it, normal UX may fall back to deterministic heuristics if the hosted provider is unavailable.

## Flow 1: Blank Scaffold, No AI

Use this when you want a contract skeleton and prefer to fill it by hand.

```bash
fluid forge --blank --target-dir ./customer-orders --non-interactive
cd customer-orders
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml --out runtime/plan.json
```

This path writes a contract scaffold only. It does not create a logical model sidecar or dbt project.

## Flow 2: Interactive AI Scaffold

Use this when you want the CLI to discover local context, ask a short interview, and scaffold the first product draft.

```bash
fluid forge
```

Useful variants:

```bash
fluid forge --domain retail
fluid forge --provider gcp --domain finance
fluid forge --discovery-path ./warehouse-ddl --discovery-path ./sample-data
fluid forge --no-discover
fluid forge --no-memory
fluid forge --save-memory
fluid forge --llm-provider openai --llm-model gpt-4.1-mini
fluid forge --llm-provider gemini --tiered --require-llm
```

The interview keeps three concepts separate:

| Interview concept | Meaning |
| --- | --- |
| Data model | Dimensional or Data Vault 2.0 |
| Transformation | dbt, SQL, Spark, Python, or custom code generation |
| Scheduler | None, Airflow, Dagster, or Prefect |

Choosing dbt as the transformation engine does not imply scheduling. Add a scheduler only when you want generated orchestration artifacts.

## Flow 3: Intent To Model Doc To dbt

An intent file is the business request in YAML or JSON. For example:

```yaml
data_product:
  name: customer_orders
  domain: retail
  description: Customer order analytics for revenue, basket, and store performance.

business_context: >
  The team needs a trusted customer order model that can support sales reporting,
  product performance analysis, and store operations.

grain:
  entity: order_line
  time_dimension: order_date

dimensions:
  entities:
    - customer
    - product
    - store
    - promotion

metrics:
  - name: total_revenue
    description: Sum of order line revenue after discounts.
  - name: order_count
    description: Count of unique customer orders.
  - name: average_order_value
    description: Total revenue divided by order count.

data_sources:
  - name: raw_orders
    system: snowflake
    table: RAW_RETAIL.ORDERS
  - name: raw_order_lines
    system: snowflake
    table: RAW_RETAIL.ORDER_LINES

business_rules:
  - Exclude cancelled orders from revenue metrics.
  - Treat returned items as negative revenue.

modeling:
  technique: dimensional
```

Or ask the CLI for a parseable example and schema:

```bash
fluid forge data-model from-intent --example retail > retail.intent.yaml
fluid forge data-model from-intent --schema > business-intent.schema.json
fluid forge data-model from-intent --validate retail.intent.yaml
```

Forge the contract and model artifacts:

```bash
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.fluid.yaml \
  --technique dimensional \
  --emit-osi-sidecar
```

For a deterministic local smoke test, add:

```bash
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.fluid.yaml \
  --technique dimensional \
  --deterministic \
  --emit-osi-sidecar
```

Expected artifacts:

```text
customer_orders.fluid.yaml
customer_orders.fluid.yaml.model.json
customer_orders.fluid.yaml.model.md
customer_orders.fluid.yaml.semantics.osi.yaml
```

The `.model.md` file is the human review layer. It contains a Mermaid diagram, facts/dimensions or hubs/links/satellites, grain, metrics, source hints, and assumptions. The `.model.json` file is the machine source of truth for generation.

Generate dbt from the forged sidecar:

```bash
fluid generate transformation customer_orders.fluid.yaml \
  -o ./dbt_customer_orders \
  --dbt-validate \
  --overwrite
```

For dbt output, zero generated `models/**/*.sql` files is a hard failure. A normal output directory includes `dbt_project.yml`, `profiles.yml`, `models/sources.yml` when source hints exist, and non-empty SQL model files.

## Flow 4: Strict Hosted Provider Smoke

Use this when you want to prove the run really used a provider and did not fall back.

Gemini:

```bash
export GOOGLE_API_KEY="<your-gemini-key>"
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.gemini.fluid.yaml \
  --llm-provider gemini \
  --tiered \
  --require-llm \
  --emit-osi-sidecar
```

OpenAI:

```bash
export OPENAI_API_KEY="<your-openai-key>"
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.openai.fluid.yaml \
  --llm-provider openai \
  --tiered \
  --require-llm \
  --emit-osi-sidecar
```

Anthropic:

```bash
export ANTHROPIC_API_KEY="<your-anthropic-key>"
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.anthropic.fluid.yaml \
  --llm-provider anthropic \
  --tiered \
  --require-llm \
  --emit-osi-sidecar
```

Ollama:

```bash
export OLLAMA_HOST=http://localhost:11434
export FLUID_OLLAMA_MODEL=gemma4:latest
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.ollama.fluid.yaml \
  --llm-provider ollama \
  --llm-model gemma4:latest \
  --require-llm \
  --emit-osi-sidecar
```

After any provider run, validate and generate:

```bash
fluid forge data-model validate customer_orders.gemini.fluid.yaml
fluid generate transformation customer_orders.gemini.fluid.yaml \
  -o ./dbt_customer_orders_gemini \
  --dbt-validate \
  --overwrite
```

## Flow 5: DDL To Model

Use DDL when you already have warehouse table definitions.

```bash
fluid forge data-model from-ddl \
  --ddl warehouse/orders.sql warehouse/customers.sql \
  --source-type snowflake \
  --technique dimensional \
  -o customer_orders_ddl.fluid.yaml \
  --emit-osi-sidecar
```

For live Snowflake schemas, dump first, then forge:

```bash
fluid forge data-model dump-ddl \
  --database BIZ_LAB \
  --schema SEEDED \
  -o biz_lab.sql

fluid forge data-model from-ddl \
  --ddl biz_lab.sql \
  --source-type snowflake \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml
```

DDL is excellent for table and column evidence. If the generated dbt project needs exact physical source mappings, prefer `from-source` or enrich the intent with `data_sources` so `models/sources.yml` can be generated correctly.

## Flow 6: Metadata Catalog To Model

Use `from-source` when metadata already lives in Snowflake, Unity Catalog, BigQuery, Dataplex, Glue, DataHub, or Data Mesh Manager.

One-time source credential setup:

```bash
fluid ai setup --source snowflake --name snowflake-prod
```

Forge from the configured source:

```bash
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB \
  --schema SEEDED \
  --tables CUSTOMER ORDER_LINE PRODUCT \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml \
  --emit-osi-sidecar
```

If running on cloud infrastructure with workload identity, opt in explicitly:

```bash
fluid forge data-model from-source \
  --source bigquery \
  --database analytics-prod \
  --schema sales_mart \
  --allow-metadata-service \
  -o sales_mart.fluid.yaml
```

Catalog credentials are separate from LLM provider credentials. `--credential-id` refers to the source credential created by `fluid ai setup --source ...`.

## Flow 7: Review, Diff, Learn

Review the logical sidecar before finalizing:

```bash
EDITOR=vim fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.fluid.yaml \
  --review
```

Compare two forged sidecars:

```bash
fluid forge data-model diff old.model.json new.model.json
```

Teach memory from a human-edited version:

```bash
fluid forge data-model learn \
  --before customer_orders.fluid.yaml.model.json \
  --after customer_orders.reviewed.fluid.yaml.model.json
```

Use memory intentionally:

```bash
fluid forge --save-memory
fluid forge --no-memory
FLUID_COPILOT_SEMANTIC_MEMORY=1 \
  fluid forge data-model from-intent retail.intent.yaml -o customer_orders.fluid.yaml
```

Memory should store preferences and summaries, not raw data or credentials.

## Flow 8: Add Scheduling Only When Needed

dbt generation and scheduling are separate:

```bash
fluid generate transformation customer_orders.fluid.yaml \
  -o ./dbt_customer_orders \
  --dbt-validate
```

If the contract includes or you choose a scheduler, generate it explicitly:

```bash
fluid generate schedule customer_orders.fluid.yaml \
  --scheduler airflow \
  -o ./dags \
  --overwrite
```

Use `none` during interviews when the team already has its own scheduler or only wants model/dbt artifacts.

## What To Commit

Usually commit:

- The intent file when it is part of the design record.
- `*.fluid.yaml`.
- `*.model.json`.
- `*.model.md`.
- `*.semantics.osi.yaml` when semantic sidecars are part of your review flow.
- Generated dbt SQL when this repo owns transformation code.

Do not commit:

- API keys, tokens, passwords, or private keys.
- `~/.fluid/` contents.
- `.fluid/store/` memory/cache data unless your team has explicitly decided to version a sanitized team memory file.
- dbt logs, `target/`, or local profile secrets.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `--require-llm` fails | Check provider env var, `fluid ai status`, model name, network, and quota. |
| Prompt asks about scheduling after you said no | Treat it as a UX bug and report the exact transcript; transformation and scheduler are separate decisions. |
| No `.model.md` written | Ensure `--no-emit-model-doc` was not passed. The default is to emit it. |
| dbt output is empty | This should fail. Re-run with `--dbt-validate` and inspect the model sidecar. |
| dbt source not found | Add source hints in intent or forge from a catalog source so `models/sources.yml` can be generated correctly. |
| You want CI without AI | Use deterministic checked-in artifacts: `validate`, `generate`, `plan`, `apply`. Do not require live LLM calls in production CI. |
